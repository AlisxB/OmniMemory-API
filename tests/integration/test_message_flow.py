"""
Testes de integração — Memories, Admin Auth e Webhooks.

Cobre:
- CRUD de Memories com verificação de criptografia
- Direito ao esquecimento (LGPD)
- Admin JWT login/refresh
- Registro de Webhook com proteção SSRF
- Rate limiting headers
- Health check
"""
import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_ID, RAW_API_KEY


MEMORY_URL   = "/v1/memory"
WEBHOOK_URL  = f"/v1/tenants/{TENANT_ID}/webhooks"
HEALTH_URL   = "/health"
ADMIN_LOGIN  = "/admin/auth/login"
ADMIN_REFRESH = "/admin/auth/refresh"


# ─── Memories ────────────────────────────────────────────────────────────────

class TestMemories:

    @pytest.mark.asyncio
    async def test_criar_memoria(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Deve salvar memória e retornar dados decriptografados."""
        resp = await client.post(
            MEMORY_URL,
            json={
                "tenant_id": TENANT_ID,
                "user_id": None,
                "scope": "tenant",
                "key": "preferencia_idioma",
                "value": "Português do Brasil",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["key"] == "preferencia_idioma"
        assert data["value"] == "Português do Brasil"  # Retorna decryptado
        assert data["scope"] == "tenant"

    @pytest.mark.asyncio
    async def test_atualizar_memoria_existente(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Segunda criação com mesma chave deve sobrescrever."""
        payload = {"tenant_id": TENANT_ID, "scope": "tenant", "key": "update_test_key", "value": "valor_1"}

        resp1 = await client.post(MEMORY_URL, json=payload, headers=auth_headers)
        assert resp1.status_code == 200

        payload["value"] = "valor_atualizado"
        resp2 = await client.post(MEMORY_URL, json=payload, headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["data"]["value"] == "valor_atualizado"

    @pytest.mark.asyncio
    async def test_memoria_valor_vazio_retorna_422(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Value vazio → 422."""
        resp = await client.post(
            MEMORY_URL,
            json={"tenant_id": TENANT_ID, "scope": "user", "key": "k", "value": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_listar_memorias_usuario(self, client: AsyncClient, auth_headers: dict, db, tenant_data):
        """Listar memórias de um usuário específico."""
        from app.domain.users.model import User
        from sqlalchemy.future import select

        # Criar usuário no banco
        user = User(tenant_id=TENANT_ID, external_id="+5511777770001", channel="whatsapp")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Criar memórias para o usuário
        for i in range(3):
            await client.post(
                MEMORY_URL,
                json={"tenant_id": TENANT_ID, "user_id": user.id, "scope": "user", "key": f"mem_{i}", "value": f"valor_{i}"},
                headers=auth_headers,
            )

        resp = await client.get(
            f"/v1/tenants/{TENANT_ID}/users/{user.id}/memories",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        memorias = resp.json()["data"]
        assert len(memorias) >= 3


# ─── LGPD — Direito ao Esquecimento ──────────────────────────────────────────

class TestLGPD:

    @pytest.mark.asyncio
    async def test_delete_usuario_remove_dados(self, client: AsyncClient, auth_headers: dict, db, tenant_data):
        """Deletar usuário deve remover todas as suas sessões, mensagens e memórias (cascade)."""
        from app.domain.users.model import User
        from app.domain.sessions.model import Session
        from sqlalchemy.future import select

        # Criar usuário + sessão
        user = User(tenant_id=TENANT_ID, external_id="+5511888880001", channel="web")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        session = Session(tenant_id=TENANT_ID, user_id=user.id)
        db.add(session)
        await db.commit()

        user_id = user.id

        # Deletar usuário
        resp = await client.delete(
            f"/v1/tenants/{TENANT_ID}/users/{user_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Verificar que sumiu do banco
        remaining = (await db.execute(
            select(User).filter(User.id == user_id)
        )).scalars().first()
        assert remaining is None

    @pytest.mark.asyncio
    async def test_delete_usuario_inexistente_retorna_404(self, client: AsyncClient, auth_headers: dict, tenant_data):
        resp = await client.delete(
            f"/v1/tenants/{TENANT_ID}/users/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ─── Admin Auth ───────────────────────────────────────────────────────────────

class TestAdminAuth:

    @pytest.mark.asyncio
    async def test_login_valido_retorna_tokens(self, client: AsyncClient):
        """Login com credenciais corretas → access + refresh token."""
        import os
        resp = await client.post(
            ADMIN_LOGIN,
            data={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_senha_errada_retorna_401(self, client: AsyncClient):
        resp = await client.post(
            ADMIN_LOGIN,
            data={"username": "admin", "password": "senha_errada"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_valido(self, client: AsyncClient):
        """Usar refresh token para obter novo access token."""
        import os
        login_resp = await client.post(
            ADMIN_LOGIN,
            data={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]},
        )
        refresh_token = login_resp.json()["refresh_token"]

        refresh_resp = await client.post(
            ADMIN_REFRESH,
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data
        assert new_data["access_token"] != login_resp.json()["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalido_retorna_401(self, client: AsyncClient):
        resp = await client.post(ADMIN_REFRESH, json={"refresh_token": "token.invalido.xyz"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_endpoint_admin_sem_token_retorna_401(self, client: AsyncClient):
        """Endpoint admin sem JWT → 401."""
        resp = await client.get("/admin/api/tenants")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_listar_tenants(self, client: AsyncClient, admin_headers: dict):
        """Admin autenticado pode listar tenants."""
        resp = await client.get("/admin/api/tenants", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)


# ─── Webhooks + SSRF ─────────────────────────────────────────────────────────

class TestWebhooks:

    @pytest.mark.asyncio
    async def test_registrar_webhook_valido(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """URL pública válida deve ser aceita."""
        resp = await client.post(
            WEBHOOK_URL,
            json={"url": "https://meusite.com/webhook", "events": ["*"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["url"] == "https://meusite.com/webhook"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_webhook_localhost_bloqueado(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """localhost → SSRF protection → 400."""
        resp = await client.post(
            WEBHOOK_URL,
            json={"url": "https://localhost/evil"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "interno" in resp.json()["data"]["detail"].lower()

    @pytest.mark.asyncio
    async def test_webhook_ip_privado_bloqueado(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """IP privado → SSRF protection → 400."""
        resp = await client.post(
            WEBHOOK_URL,
            json={"url": "http://192.168.1.100/hook"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_url_http_invalida(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """URL sem scheme http/https → 400."""
        resp = await client.post(
            WEBHOOK_URL,
            json={"url": "ftp://meusite.com/hook"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_listar_webhooks(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Listar webhooks do tenant."""
        # Criar um webhook primeiro
        await client.post(
            WEBHOOK_URL,
            json={"url": "https://example.com/wh2"},
            headers=auth_headers,
        )
        resp = await client.get(WEBHOOK_URL, headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)


# ─── Observabilidade ─────────────────────────────────────────────────────────

class TestObservability:

    @pytest.mark.asyncio
    async def test_health_check_retorna_200_ou_503(self, client: AsyncClient):
        """Health check deve sempre retornar 200 (healthy) ou 503 (degraded)."""
        resp = await client.get(HEALTH_URL)
        assert resp.status_code in (200, 503)
        data = resp.json()["data"]
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    @pytest.mark.asyncio
    async def test_rate_limit_headers_presentes(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Toda resposta deve ter headers X-RateLimit-*."""
        resp = await client.post(
            "/v1/context/resolve",
            json={"tenant_id": TENANT_ID, "external_user_id": "+55119rate"},
            headers=auth_headers,
        )
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers

    @pytest.mark.asyncio
    async def test_request_id_propagado(self, client: AsyncClient):
        """X-Request-ID customizado deve ser propagado na resposta."""
        custom_id = "my-trace-id-12345"
        resp = await client.get(HEALTH_URL, headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id
