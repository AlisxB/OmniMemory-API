"""
Cliente Redis assíncrono para a OmniMemory API.

CORREÇÃO CRÍTICA do projeto original:
O projeto Michel usava `redis.Redis` (SÍNCRONO) dentro de um contexto async,
o que bloqueia o event loop do FastAPI/asyncio, causando degradação de performance.

Esta versão usa `redis.asyncio` (assíncrono nativo), resolvendo o problema.
"""
import json
import time
import logging
from typing import Any, Optional
import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger(__name__)

# ─── Pool de conexões Redis (singleton) ─────────────────────────────────────
_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Retorna cliente Redis assíncrono (singleton com connection pool)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis():
    """Fecha o pool de conexões. Chamado no shutdown da aplicação."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# ─── Manager de Alto Nível ───────────────────────────────────────────────────
class RedisManager:
    """Abstração de alto nível sobre o Redis para as operações da API."""

    # ── Session State ───────────────────────────────────────────────────────

    @staticmethod
    async def get_session_lock(session_id: str, timeout: int = 10):
        """Adquire um distributed lock para a sessão (evita race conditions)."""
        r = await get_redis()
        return r.lock(f"lock:session:{session_id}", timeout=timeout)

    @staticmethod
    async def set_session_active(
        tenant_id: str, external_user_id: str, session_id: str, ttl_minutes: int
    ):
        """Marca sessão como ativa com TTL automático."""
        r = await get_redis()
        key = f"active_session:{tenant_id}:{external_user_id}"
        await r.setex(key, ttl_minutes * 60, session_id)

    @staticmethod
    async def get_active_session_id(
        tenant_id: str, external_user_id: str
    ) -> Optional[str]:
        """Recupera o ID da sessão ativa do Redis."""
        r = await get_redis()
        key = f"active_session:{tenant_id}:{external_user_id}"
        return await r.get(key)

    @staticmethod
    async def delete_session(tenant_id: str, external_user_id: str):
        """Remove a referência da sessão ativa."""
        r = await get_redis()
        key = f"active_session:{tenant_id}:{external_user_id}"
        await r.delete(key)

    # ── Message Buffer ──────────────────────────────────────────────────────

    @staticmethod
    async def add_to_buffer(session_id: str, content: str):
        """Adiciona conteúdo ao buffer de mensagens da sessão."""
        r = await get_redis()
        key = f"buffer:{session_id}"
        count = await r.rpush(key, content)
        await r.expire(key, 3600)
        logger.debug(f"Redis buffer [{key}]: {count} messages")

    @staticmethod
    async def get_and_clear_buffer(session_id: str) -> str:
        """Drena e retorna todo o conteúdo do buffer, limpando-o atomicamente."""
        r = await get_redis()
        key = f"buffer:{session_id}"
        pipe = r.pipeline()
        pipe.lrange(key, 0, -1)
        pipe.delete(key)
        results = await pipe.execute()
        messages = results[0]
        logger.debug(f"Redis buffer drained [{key}]: {len(messages)} messages")
        return "\n".join(messages)

    @staticmethod
    async def set_last_message_id(session_id: str) -> int:
        """Incrementa e retorna o ID da última mensagem (controle de buffer)."""
        r = await get_redis()
        return await r.incr(f"last_msg_id:{session_id}")

    @staticmethod
    async def get_last_message_id(session_id: str) -> int:
        """Retorna o ID da última mensagem."""
        r = await get_redis()
        res = await r.get(f"last_msg_id:{session_id}")
        return int(res) if res else 0

    # ── Rate Limiting (Sliding Window) ──────────────────────────────────────

    @staticmethod
    async def check_rate_limit_sliding(
        key: str, limit: int, window_seconds: int = 60
    ) -> bool:
        """
        Rate limiting com Sliding Window usando Redis Sorted Sets.
        Mais preciso que Fixed Window — impede burst no limiar de janelas.

        Returns True se a requisição está dentro do limite, False se excedeu.
        """
        r = await get_redis()
        now = time.time()
        window_start = now - window_seconds

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # Remove entradas expiradas
        pipe.zadd(key, {str(now): now})               # Adiciona requisição atual
        pipe.zcard(key)                               # Conta total na janela
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        count = results[2]
        return count <= limit

    @staticmethod
    async def check_tenant_rate_limit(tenant_id: str, limit_rpm: int) -> bool:
        """Verifica rate limit por tenant com sliding window de 60s."""
        key = f"rate_limit:tenant:{tenant_id}"
        return await RedisManager.check_rate_limit_sliding(key, limit_rpm, 60)

    # ── Cache Genérico ──────────────────────────────────────────────────────

    @staticmethod
    async def set_cache(key: str, data: Any, ttl_seconds: int = 300):
        """Serializa e salva dados no cache Redis."""
        try:
            r = await get_redis()
            from fastapi.encoders import jsonable_encoder
            await r.setex(key, ttl_seconds, json.dumps(jsonable_encoder(data)))
        except Exception as e:
            logger.error(f"Cache SET error [{key}]: {e}")

    @staticmethod
    async def get_cache(key: str) -> Optional[Any]:
        """Recupera e desserializa dados do cache Redis."""
        try:
            r = await get_redis()
            data = await r.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Cache GET error [{key}]: {e}")
            return None

    @staticmethod
    async def delete_cache(key: str):
        """Remove uma chave do cache."""
        try:
            r = await get_redis()
            await r.delete(key)
        except Exception as e:
            logger.error(f"Cache DELETE error [{key}]: {e}")

    # ── Métricas de Uso ─────────────────────────────────────────────────────

    @staticmethod
    async def record_usage(tenant_id: str, tokens: int = 0):
        """Registra uso de tokens e requests do dia (para billing/analytics)."""
        from datetime import datetime
        day = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"usage:{tenant_id}:{day}"

        r = await get_redis()
        pipe = r.pipeline()
        pipe.hincrby(key, "tokens", tokens)
        pipe.hincrby(key, "requests", 1)
        pipe.expire(key, 86400 * 35)  # Retém 35 dias para auditoria
        await pipe.execute()

    @staticmethod
    async def get_daily_usage(tenant_id: str) -> dict:
        """Retorna uso do dia atual."""
        from datetime import datetime
        day = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"usage:{tenant_id}:{day}"
        r = await get_redis()
        res = await r.hgetall(key)
        return {
            "tokens": int(res.get("tokens", 0) or 0),
            "requests": int(res.get("requests", 0) or 0),
        }

    @staticmethod
    async def check_daily_token_limit(tenant_id: str, limit: int) -> bool:
        """Verifica se o limite diário de tokens foi atingido."""
        if not limit or limit <= 0:
            return True  # Sem limite configurado
        usage = await RedisManager.get_daily_usage(tenant_id)
        return usage["tokens"] < limit

    # ── Health Check ────────────────────────────────────────────────────────

    @staticmethod
    async def ping() -> bool:
        """Verifica se o Redis está acessível."""
        try:
            r = await get_redis()
            return await r.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    # ── Admin & Analytics Helpers ───────────────────────────────────────────

    @staticmethod
    async def get_list_length(key: str) -> int:
        """Retorna o tamanho de uma lista no Redis."""
        r = await get_redis()
        return await r.llen(key)

    @staticmethod
    async def scan_keys(match_pattern: str):
        """Iterador assíncrono para escanear chaves no Redis."""
        r = await get_redis()
        async for key in r.scan_iter(match=match_pattern):
            yield key

    @staticmethod
    async def incr_metric(metric_name: str, amount: int = 1):
        """Incrementa um contador global de métrica."""
        r = await get_redis()
        await r.incr(f"metric:{metric_name}", amount)

    @staticmethod
    async def get_metric(metric_name: str) -> int:
        """Recupera o valor de um contador global de métrica."""
        r = await get_redis()
        val = await r.get(f"metric:{metric_name}")
        return int(val) if val else 0
