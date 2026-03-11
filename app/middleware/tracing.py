"""Middleware de Request ID para rastreabilidade distribuída."""
import uuid
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injeta um X-Request-ID único em cada request.
    Usado para correlacionar logs e respostas da API.
    """

    async def dispatch(self, request: Request, call_next):
        # Reutiliza o ID do cliente se fornecido, ou gera um novo
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.monotonic()

        logger.info(
            f"→ {request.method} {request.url.path} | req_id={request_id}"
        )

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            f"← {response.status_code} {request.url.path} | "
            f"req_id={request_id} | {duration_ms}ms"
        )

        return response
