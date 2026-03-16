import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_cannot_register_duplicate_webhook(client: AsyncClient, auth_headers: dict, tenant_data: dict):
    """
    Testa se o sistema impede o registro de um segundo webhook para o mesmo tenant.
    """
    tenant_id = tenant_data["tenant_id"]
    webhook_url = "https://webhook.site/test1"
    
    # 1. Registrar o primeiro webhook
    payload = {
        "url": webhook_url,
        "events": ["*"],
        "is_active": True
    }
    
    # Usamos o header Idempotency-Key pois o endpoint o exige
    headers = {**auth_headers, "X-Idempotency-Key": "first-request"}
    
    resp1 = await client.post(
        f"/api/v1/tenants/{tenant_id}/webhooks",
        json=payload,
        headers=headers
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["url"] == webhook_url
    
    # 2. Tentar registrar um segundo webhook para o mesmo tenant
    webhook_url_2 = "https://webhook.site/test2"
    payload_2 = {
        "url": webhook_url_2,
        "events": ["*"],
        "is_active": True
    }
    
    # Usamos uma chave de idempotência diferente
    headers_2 = {**auth_headers, "X-Idempotency-Key": "second-request"}
    
    resp2 = await client.post(
        f"/api/v1/tenants/{tenant_id}/webhooks",
        json=payload_2,
        headers=headers_2
    )
    
    # Deve retornar 400 Bad Request devido à nossa nova verificação
    assert resp2.status_code == 400
    assert "já possui um webhook registrado" in resp2.json()["error"]["message"]
