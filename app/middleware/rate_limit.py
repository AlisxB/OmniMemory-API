"""
Rate Limiting Middleware refatorado.

Melhorias em relação ao original:
- Sliding Window (mais preciso que Fixed Window)
- Limites diferenciados por rota (global vs admin)
- Headers informativos de rate limit (X-RateLimit-*)
- Retorna 429 antes de processar o request (fail-fast)
"""
import time
import logging
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting por IP com Sliding Window.

    Limites diferenciados:
    - Rotas /admin/*: limit_admin (default 10 req/min)
    - Demais rotas: limit_global (default 200 req/min)
    """

    def __init__(self, app, global_limit: int = 200, admin_limit: int = 10, window_seconds: int = 60):
        super().__init__(app)
        self.global_limit = global_limit
        self.admin_limit = admin_limit
        self.window_seconds = window_seconds
        self._store: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _get_client_ip(self, request: Request) -> str:
        """Extrai o IP real do cliente (considera X-Forwarded-For do proxy)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_limit(self, key: str, limit: int) -> tuple[bool, int, int]:
        """
        Verifica o rate limit usando Sliding Window em memória.
        Returns: (allowed, current_count, retry_after_seconds)
        """
        now = time.monotonic()
        window_start = now - self.window_seconds

        with self._lock:
            queue = self._store[key]

            # Remove timestamps fora da janela
            while queue and queue[0] <= window_start:
                queue.popleft()

            count = len(queue)
            if count >= limit:
                # Calcular quando a requisição mais antiga expira
                oldest = queue[0] if queue else now
                retry_after = int(oldest - window_start) + 1
                return False, count, retry_after

            queue.append(now)
            return True, count + 1, 0

    async def dispatch(self, request: Request, call_next):
        # Excluir endpoints de observabilidade
        if request.url.path in ("/health", "/", "/metrics"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        is_admin = request.url.path.startswith("/admin")
        limit = self.admin_limit if is_admin else self.global_limit
        key = f"{'admin' if is_admin else 'global'}:{ip}"

        allowed, count, retry_after = self._check_limit(key, limit)

        if not allowed:
            logger.warning(f"Rate limit exceeded | ip={ip} path={request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": {
                        "detail": "Too Many Requests. Tente novamente em instantes.",
                        "retry_after_seconds": retry_after,
                    },
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Adicionar headers informativos
        remaining = max(0, limit - count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = f"{self.window_seconds}s"

        return response
