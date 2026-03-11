"""
Testes unitários — Middleware de Rate Limit.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.rate_limit import RateLimitMiddleware


def create_test_app(global_limit=5, admin_limit=2, window_seconds=60):
    """Cria uma app Starlette mínima com o middleware de rate limit."""

    async def ok_endpoint(request):
        return JSONResponse({"status": "ok"})

    async def admin_endpoint(request):
        return JSONResponse({"status": "admin_ok"})

    app = Starlette(routes=[
        Route("/api/test", ok_endpoint),
        Route("/admin/dashboard", admin_endpoint),
        Route("/health", ok_endpoint),
    ])
    app.add_middleware(
        RateLimitMiddleware,
        global_limit=global_limit,
        admin_limit=admin_limit,
        window_seconds=window_seconds,
    )
    return app


class TestRateLimitMiddleware:

    def test_dentro_do_limite_retorna_200(self):
        """Requisições dentro do limite devem passar."""
        app = create_test_app(global_limit=10)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(5):
            resp = client.get("/api/test")
            assert resp.status_code == 200

    def test_exceder_limite_retorna_429(self):
        """Exceder o limite deve retornar 429."""
        app = create_test_app(global_limit=3, window_seconds=60)
        client = TestClient(app, raise_server_exceptions=False)

        resps = [client.get("/api/test") for _ in range(5)]
        status_codes = [r.status_code for r in resps]

        assert 429 in status_codes
        # As 3 primeiras passam, a 4ª ou 5ª bloqueia
        assert status_codes[:3] == [200, 200, 200]

    def test_limite_admin_mais_restritivo(self):
        """Rotas /admin/* têm limite menor."""
        app = create_test_app(global_limit=100, admin_limit=2)
        client = TestClient(app, raise_server_exceptions=False)

        # 2 chamadas OK no admin
        r1 = client.get("/admin/dashboard")
        r2 = client.get("/admin/dashboard")
        r3 = client.get("/admin/dashboard")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429

    def test_health_nao_conta_no_rate_limit(self):
        """Endpoints de observabilidade não consomem cota."""
        app = create_test_app(global_limit=2)
        client = TestClient(app, raise_server_exceptions=False)

        # Saturar o limite
        client.get("/api/test")
        client.get("/api/test")
        client.get("/api/test")  # Deve retornar 429

        # Health não deve ser afetado
        health = client.get("/health")
        assert health.status_code == 200

    def test_headers_rate_limit_presentes(self):
        """Toda resposta deve ter X-RateLimit-* headers."""
        app = create_test_app(global_limit=10)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert resp.headers["x-ratelimit-limit"] == "10"

    def test_header_retry_after_em_429(self):
        """Resposta 429 deve ter Retry-After."""
        app = create_test_app(global_limit=1)
        client = TestClient(app, raise_server_exceptions=False)

        client.get("/api/test")  # Consume o limite
        resp = client.get("/api/test")

        assert resp.status_code == 429
        assert "retry-after" in resp.headers
        assert int(resp.headers["retry-after"]) > 0

    def test_ips_diferentes_nao_se_afetam(self):
        """IPs diferentes têm contadores independentes."""
        app = create_test_app(global_limit=2)

        # Simular dois IPs diferentes via X-Forwarded-For
        client = TestClient(app, raise_server_exceptions=False)

        # IP A: satura
        client.get("/api/test", headers={"X-Forwarded-For": "1.2.3.4"})
        client.get("/api/test", headers={"X-Forwarded-For": "1.2.3.4"})
        r3_ip_a = client.get("/api/test", headers={"X-Forwarded-For": "1.2.3.4"})

        # IP B: não deve ser afetado
        r1_ip_b = client.get("/api/test", headers={"X-Forwarded-For": "5.6.7.8"})

        assert r3_ip_a.status_code == 429
        assert r1_ip_b.status_code == 200
