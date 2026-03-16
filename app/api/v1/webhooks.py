"""Endpoints de Webhooks — subscribe, list, delete com proteção SSRF."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...database import get_db
from ...core.responses import wrap_response
from ...core.idempotency import idempotency_key_required
from ...core.security import validate_webhook_url
from ...domain.webhooks.model import WebhookSubscription
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — webhooks"])


class WebhookCreate(BaseModel):
    url: str = Field(..., description="URL pública HTTPS para receber eventos")
    events: List[str] = Field(default=["*"], description="Eventos a receber. ['*'] = todos")
    is_active: bool = True


@router.post("/tenants/{tenant_id}/webhooks", summary="Registrar webhook")
@idempotency_key_required
async def subscribe_webhook(
    request: Request,
    tenant_id: str,
    req: WebhookCreate,
    db: AsyncSession = Depends(get_db),
):
    """Registra uma URL para receber eventos do tenant. Proteção SSRF aplicada."""
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    # Validação SSRF
    try:
        validated_url = validate_webhook_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verificar se já existe um webhook para este tenant
    existing = (await db.execute(
        select(WebhookSubscription).filter(WebhookSubscription.tenant_id == tenant_id)
    )).scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Este tenant já possui um webhook registrado. Remova-o antes de registrar um novo."
        )

    webhook = WebhookSubscription(tenant_id=tenant_id, url=validated_url, events=req.events, is_active=req.is_active)
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return wrap_response(
        {"id": webhook.id, "url": webhook.url, "events": webhook.events, "is_active": webhook.is_active},
        request.state.request_id,
    )


@router.get("/tenants/{tenant_id}/webhooks", summary="Listar webhooks")
async def list_webhooks(
    request: Request,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)
    subs = (await db.execute(
        select(WebhookSubscription).filter(WebhookSubscription.tenant_id == tenant_id)
    )).scalars().all()

    return wrap_response(
        [{"id": s.id, "url": s.url, "events": s.events, "is_active": s.is_active, "created_at": s.created_at} for s in subs],
        request.state.request_id,
    )


@router.delete("/webhooks/{webhook_id}", summary="Remover webhook")
async def delete_webhook(
    request: Request,
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
):
    sub = (await db.execute(
        select(WebhookSubscription).filter(WebhookSubscription.id == webhook_id)
    )).scalars().first()

    if not sub:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")

    await validate_tenant_access(sub.tenant_id, request.headers.get("X-API-Key"), db)
    await db.delete(sub)
    await db.commit()

    return wrap_response({"detail": "Webhook removido com sucesso"}, request.state.request_id)
