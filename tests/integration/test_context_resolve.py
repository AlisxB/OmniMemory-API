"""
Testes de integração — Fluxo completo de Context Resolve.

Cobre:
- POST /v1/context/resolve: nova sessão
- POST /v1/context/resolve: reutilizar sessão ativa
- POST /v1/context/message: persistir mensagem user + assistant
- POST /v1/context/search: busca semântica
- Autenticação: sem header, header inválido, tenant inativo
"""
import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_ID, RAW_API_KEY


# ─── Helpers ──────────────────────────────────────────────────────────────────

RESOLVE_URL = "/v1/context/resolve"
MESSAGE_URL = "/v1/context/message"
SEARCH_URL  = "/v1/context/search"

BASE_RESOLVE = {
    "tenant_id": TENANT_ID,
    "external_user_id": "+5511999990001",
    "channel": "whatsapp",
}


# ─── Context Resolve ─────────────────────────────────────────────────────────

class TestContextResolve:

    @pytest.mark.asyncio
    async def test_resolve_nova_sessao(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Primeira chamada deve criar sessão nova."""
        resp = await client.post(RESOLVE_URL, json=BASE_RESOLVE, headers=auth_headers)
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert data["session"]["is_new"] is True
        assert data["session"]["status"] == "active"
        assert "id" in data["session"]
        assert "messages" in data["context"]
        assert "memory"   in data["context"]
        assert "settings" in data

    @pytest.mark.asyncio
    async def test_resolve_reutiliza_sessao(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Segunda chamada com mesmo usuário deve retornar a mesma sessão."""
        user = {**BASE_RESOLVE, "external_user_id": "+5511999990002"}

        resp1 = await client.post(RESOLVE_URL, json=user, headers=auth_headers)
        resp2 = await client.post(RESOLVE_URL, json=user, headers=auth_headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        session1_id = resp1.json()["data"]["session"]["id"]
        session2_id = resp2.json()["data"]["session"]["id"]
        is_new2 = resp2.json()["data"]["session"]["is_new"]

        assert session1_id == session2_id, "Sessão deveria ser reutilizada"
        assert is_new2 is False

    @pytest.mark.asyncio
    async def test_resolve_sem_api_key_retorna_401(self, client: AsyncClient, tenant_data):
        """Sem header X-API-Key → 401."""
        resp = await client.post(RESOLVE_URL, json=BASE_RESOLVE)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_api_key_invalida_retorna_401(self, client: AsyncClient, tenant_data):
        """API Key errada → 401."""
        headers = {"X-API-Key": f"{TENANT_ID}:omni_wrong_key_xyz"}
        resp = await client.post(RESOLVE_URL, json=BASE_RESOLVE, headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_canal_invalido_retorna_422(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Canal não permitido → 422 de validação."""
        payload = {**BASE_RESOLVE, "channel": "fax"}
        resp = await client.post(RESOLVE_URL, json=payload, headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_resolve_tenant_inexistente_retorna_4xx(self, client: AsyncClient, tenant_data):
        """Tenant que não existe → 404."""
        headers = {"X-API-Key": "nao_existe:omni_qualquer"}
        payload = {**BASE_RESOLVE, "tenant_id": "nao_existe"}
        resp = await client.post(RESOLVE_URL, json=payload, headers=headers)
        assert resp.status_code in (401, 404)

    @pytest.mark.asyncio
    async def test_resolve_retorna_request_id(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Toda resposta deve conter X-Request-ID no header."""
        resp = await client.post(RESOLVE_URL, json=BASE_RESOLVE, headers=auth_headers)
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio
    async def test_resolve_com_metadados(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Metadados da sessão devem ser persistidos."""
        payload = {
            **BASE_RESOLVE,
            "external_user_id": "+5511999990003",
            "metadata": {"origem": "campanha_verao", "utm_source": "instagram"},
        }
        resp = await client.post(RESOLVE_URL, json=payload, headers=auth_headers)
        assert resp.status_code == 200


# ─── Context Message ──────────────────────────────────────────────────────────

class TestContextMessage:

    @pytest.mark.asyncio
    async def test_post_mensagem_user(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Deve salvar mensagem do usuário e retornar os dados."""
        # Primeiro resolver sessão
        resolve_resp = await client.post(
            RESOLVE_URL,
            json={**BASE_RESOLVE, "external_user_id": "+5511999990010"},
            headers=auth_headers,
        )
        session_id = resolve_resp.json()["data"]["session"]["id"]

        resp = await client.post(
            MESSAGE_URL,
            json={"session_id": session_id, "role": "user", "content": "Olá! Preciso de ajuda."},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        data = resp.json()["data"]
        assert data["role"] == "user"
        assert data["content"] == "Olá! Preciso de ajuda."
        assert data["session_id"] == session_id
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_post_mensagem_assistant(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Mensagem do assistente deve ser salva mas não disparar webhook."""
        resolve_resp = await client.post(
            RESOLVE_URL,
            json={**BASE_RESOLVE, "external_user_id": "+5511999990011"},
            headers=auth_headers,
        )
        session_id = resolve_resp.json()["data"]["session"]["id"]

        resp = await client.post(
            MESSAGE_URL,
            json={"session_id": session_id, "role": "assistant", "content": "Posso ajudar!"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_post_mensagem_conteudo_vazio_retorna_422(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Conteúdo vazio → 422."""
        resolve_resp = await client.post(
            RESOLVE_URL,
            json={**BASE_RESOLVE, "external_user_id": "+5511999990012"},
            headers=auth_headers,
        )
        session_id = resolve_resp.json()["data"]["session"]["id"]

        resp = await client.post(
            MESSAGE_URL,
            json={"session_id": session_id, "role": "user", "content": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_mensagens_aparecem_no_contexto(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Mensagens salvas devem aparecer no próximo /resolve."""
        user_data = {**BASE_RESOLVE, "external_user_id": "+5511999990013"}

        resolve_resp = await client.post(RESOLVE_URL, json=user_data, headers=auth_headers)
        session_id = resolve_resp.json()["data"]["session"]["id"]

        await client.post(MESSAGE_URL, json={"session_id": session_id, "role": "user", "content": "Mensagem 1"}, headers=auth_headers)
        await client.post(MESSAGE_URL, json={"session_id": session_id, "role": "assistant", "content": "Resposta 1"}, headers=auth_headers)

        # Novo resolve deve trazer as mensagens no contexto
        resolve2 = await client.post(RESOLVE_URL, json=user_data, headers=auth_headers)
        messages = resolve2.json()["data"]["context"]["messages"]

        assert len(messages) >= 2
        contents = [m["content"] for m in messages]
        assert "Mensagem 1" in contents
        assert "Resposta 1" in contents

    @pytest.mark.asyncio
    async def test_idempotencia_mensagem(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Mesma X-Idempotency-Key deve retornar resultado cacheado."""
        resolve_resp = await client.post(
            RESOLVE_URL,
            json={**BASE_RESOLVE, "external_user_id": "+5511999990014"},
            headers=auth_headers,
        )
        session_id = resolve_resp.json()["data"]["session"]["id"]

        idempotency_headers = {**auth_headers, "X-Idempotency-Key": "unique-key-abc-123"}
        payload = {"session_id": session_id, "role": "user", "content": "Mensagem idempotente"}

        resp1 = await client.post(MESSAGE_URL, json=payload, headers=idempotency_headers)
        resp2 = await client.post(MESSAGE_URL, json=payload, headers=idempotency_headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Ambos devem ter o mesmo ID de mensagem (segunda foi do cache)
        assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]


# ─── Context Search ───────────────────────────────────────────────────────────

class TestContextSearch:

    @pytest.mark.asyncio
    async def test_search_get(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """GET /v1/context/search deve funcionar com query params."""
        resp = await client.get(
            SEARCH_URL,
            params={"tenant_id": TENANT_ID, "query": "ajuda suporte", "limit": 3},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "memories" in data
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_search_post(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """POST /v1/context/search deve funcionar com JSON body."""
        resp = await client.post(
            SEARCH_URL,
            json={"tenant_id": TENANT_ID, "query": "ajuda suporte", "limit": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_query_muito_curta_retorna_422(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Query com 1 caractere → 422."""
        resp = await client.post(
            SEARCH_URL,
            json={"tenant_id": TENANT_ID, "query": "a"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_limit_maximo(self, client: AsyncClient, auth_headers: dict, tenant_data):
        """Limit > 20 → 422."""
        resp = await client.post(
            SEARCH_URL,
            json={"tenant_id": TENANT_ID, "query": "teste query válida", "limit": 99},
            headers=auth_headers,
        )
        assert resp.status_code == 422
