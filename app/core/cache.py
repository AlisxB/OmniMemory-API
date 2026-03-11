"""
Cache L2 — Decorator e helpers para caching de dados frequentemente lidos.

Dados cacheados com TTLs ajustados:
- TenantSettings: 5 min (muda raramente)
- PromptTemplate ativo: 10 min (muda raramente)
- Memórias do usuário: 2 min (invalidado ao escrever)
"""
import logging
from typing import Any, Callable, Optional
from functools import wraps

from ..redis import RedisManager

logger = logging.getLogger(__name__)


def cached(ttl_seconds: int, key_fn: Callable[..., str]):
    """
    Decorator de cache genérico para funções async.

    Args:
        ttl_seconds: Tempo de vida em segundos
        key_fn: Função que recebe os mesmos args da função e retorna a cache key

    Uso:
        @cached(ttl_seconds=300, key_fn=lambda tid: f"tenant_settings:{tid}")
        async def get_tenant_settings(tenant_id: str) -> dict: ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = key_fn(*args, **kwargs)

            # Tentar retornar do cache
            cached_data = await RedisManager.get_cache(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_data

            # Cache miss — executar função
            result = await func(*args, **kwargs)

            # Armazenar no cache
            if result is not None:
                await RedisManager.set_cache(cache_key, result, ttl_seconds=ttl_seconds)
                logger.debug(f"Cache SET: {cache_key} (ttl={ttl_seconds}s)")

            return result
        return wrapper
    return decorator


# ─── Funções de invalidação de cache ─────────────────────────────────────────

async def invalidate_tenant_settings(tenant_id: str):
    """Invalida o cache de configurações de um tenant."""
    await RedisManager.delete_cache(f"tenant_settings:{tenant_id}")

async def invalidate_tenant_prompts(tenant_id: str, slug: str):
    """Invalida o cache de um prompt template específico."""
    await RedisManager.delete_cache(f"prompt_template:{tenant_id}:{slug}")

async def invalidate_user_memories(tenant_id: str, user_id: int):
    """Invalida o cache de memórias de um usuário."""
    await RedisManager.delete_cache(f"memories_cache:{tenant_id}:{user_id}")

async def invalidate_tenant_all(tenant_id: str):
    """Invalida todos os caches relacionados a um tenant."""
    await RedisManager.delete_cache(f"tenant_cache:{tenant_id}")
    await RedisManager.delete_cache(f"tenant_settings:{tenant_id}")
