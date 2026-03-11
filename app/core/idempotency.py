"""
Idempotência baseada em Redis — versão async corrigida.

CORREÇÃO do projeto original:
- Usava redis_client síncrono em contexto async
- Agora usa RedisManager async

Funcionamento:
- Se X-Idempotency-Key presente e já processado → retorna resultado cacheado
- Se não presente → processa normalmente (sem exigir a chave)
- TTL: 24h
"""
import json
import logging
from functools import wraps
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from ..redis import RedisManager

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 86400  # 24 horas


def idempotency_key_required(func: Callable):
    """
    Decorator que implementa idempotência via X-Idempotency-Key.
    Aplique em qualquer endpoint de escrita (POST com efeito colateral).
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        idempotency_key = request.headers.get("X-Idempotency-Key")

        if not idempotency_key:
            # Chave não enviada — processa normalmente
            return await func(request, *args, **kwargs)

        # Determinar tenant_id para namespacing da chave
        req_body = kwargs.get("req") or kwargs.get("body")
        tenant_id = getattr(req_body, "tenant_id", "global")
        redis_key = f"idempotency:{tenant_id}:{idempotency_key}"

        # Verificar se já existe resultado cacheado
        cached = await RedisManager.get_cache(redis_key)
        if cached is not None:
            logger.info(f"Idempotency hit: key={idempotency_key} tenant={tenant_id}")
            return JSONResponse(content=cached)

        # Executar a função original
        result = await func(request, *args, **kwargs)

        # Cachear o resultado para futuras requisições com a mesma chave
        try:
            if hasattr(result, "body"):
                body = json.loads(result.body)
            else:
                from fastapi.encoders import jsonable_encoder
                body = jsonable_encoder(result)
            await RedisManager.set_cache(redis_key, body, ttl_seconds=IDEMPOTENCY_TTL)
        except Exception as e:
            logger.warning(f"Idempotency cache failed: {e}")

        return result

    return wrapper
