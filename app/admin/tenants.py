"""
Admin API — Gestão de Tenants.
Protegido por JWT (get_current_admin).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..core.responses import wrap_response
from ..core.security import APIKeyManager, validate_webhook_url
from ..domain.tenants.model import Tenant, TenantSettings
from ..domain.webhooks.model import WebhookSubscription
from ..redis import RedisManager
from ..config import settings
from .auth import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin — tenants"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    id: str = Field(..., description="Slug único do tenant", example="clinica_sorriso")
    name: str = Field(..., description="Nome da operação", example="Clínica Sorriso")
    subscription_expires_at: Optional[datetime] = None
    settings: Optional[Dict[str, Any]] = None


class WebhookSync(BaseModel):
    url: str = Field(..., description="URL do webhook (HTTPS recomendado)")


# ─── Dependency: Super Admin Key (para operações sensíveis) ──────────────────

async def require_super_admin(request: Request):
    """Valida X-Super-Admin-Key para operações críticas (delete, rotate key)."""
    key = request.headers.get("X-Super-Admin-Key", "")
    import secrets as _secrets
    if not _secrets.compare_digest(key, settings.super_admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin required")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/tenants", summary="Listar todos os tenants")
async def list_tenants(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    stmt = (
        select(Tenant)
        .options(
            selectinload(Tenant.settings),
            selectinload(Tenant.webhooks),
        )
        .limit(limit)
        .offset(offset)
        .order_by(Tenant.created_at.desc())
    )
    tenants = (await db.execute(stmt)).scalars().all()

    tenant_list = []
    for t in tenants:
        usage = await RedisManager.get_daily_usage(t.id)

        # Verificar se a API Key está com mais de 90 dias sem rotação
        key_age_days = None
        key_needs_rotation = False
        if t.api_key_last_rotated_at:
            delta = datetime.now(timezone.utc) - t.api_key_last_rotated_at.replace(tzinfo=timezone.utc)
            key_age_days = delta.days
            key_needs_rotation = key_age_days > 90

        tenant_list.append({
            "id": t.id,
            "name": t.name,
            "is_active": t.is_active,
            "created_at": t.created_at,
            "subscription_expires_at": t.subscription_expires_at,
            "usage": usage,
            "api_key_info": {
                "suffix": t.api_key[-8:] if t.api_key else None,
                "age_days": key_age_days,
                "needs_rotation": key_needs_rotation,
            },
            "webhook_configured": len(t.webhooks) > 0 if t.webhooks else False,
            "settings": {
                "rate_limit_rpm": t.settings.rate_limit_rpm if t.settings else 60,
                "daily_token_limit": t.settings.daily_token_limit if t.settings else 100_000,
                "buffer_window_seconds": t.settings.buffer_window_seconds if t.settings else 0,
            },
            "webhook_configured": bool(t.webhooks and any(w.is_active for w in t.webhooks)),
        })

    return wrap_response(tenant_list, getattr(request.state, "request_id", None))


@router.post("/tenants", summary="Criar novo tenant")
async def create_tenant(
    request: Request,
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    existing = (await db.execute(select(Tenant).filter(Tenant.id == body.id))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant ID já existe")

    raw_key = APIKeyManager.generate_key()
    tenant = Tenant(
        id=body.id,
        name=body.name,
        api_key=APIKeyManager.hash_key(raw_key),
        subscription_expires_at=body.subscription_expires_at,
        api_key_last_rotated_at=datetime.now(timezone.utc),
    )
    db.add(tenant)

    settings_data = body.settings or {}
    db.add(TenantSettings(tenant_id=body.id, **settings_data))

    await db.commit()
    logger.info(f"Tenant criado: {body.id}")

    return wrap_response(
        {
            "tenant_id": body.id,
            "name": body.name,
            "api_key": f"{body.id}:{raw_key}",  # Exibido UMA VEZ apenas
            "subscription_expires_at": body.subscription_expires_at,
        },
        getattr(request.state, "request_id", None),
    )


@router.post(
    "/tenants/{tenant_id}/rotate-key",
    summary="Rotacionar API Key do tenant",
    dependencies=[Depends(require_super_admin)],
)
async def rotate_tenant_key(
    request: Request,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Gera nova API Key. A chave antiga é imediatamente invalidada."""
    tenant = (await db.execute(select(Tenant).filter(Tenant.id == tenant_id))).scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    raw_key = APIKeyManager.generate_key()
    tenant.api_key = APIKeyManager.hash_key(raw_key)
    tenant.api_key_last_rotated_at = datetime.now(timezone.utc)
    await db.commit()

    # Invalidar cache do tenant
    await RedisManager.delete_cache(f"tenant_cache:{tenant_id}")

    logger.info(f"API Key rotacionada: tenant_id={tenant_id}")

    return wrap_response(
        {"tenant_id": tenant_id, "api_key": f"{tenant_id}:{raw_key}"},
        getattr(request.state, "request_id", None),
    )


@router.patch("/tenants/{tenant_id}", summary="Atualizar tenant")
async def update_tenant(
    request: Request,
    tenant_id: str,
    updates: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    stmt = select(Tenant).filter(Tenant.id == tenant_id).options(selectinload(Tenant.settings))
    tenant = (await db.execute(stmt)).scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    for field in ("is_active", "name", "subscription_expires_at"):
        if field in updates:
            setattr(tenant, field, updates[field])

    if "settings" in updates and tenant.settings:
        for field in ("rate_limit_rpm", "daily_token_limit", "buffer_window_seconds"):
            if field in updates["settings"]:
                setattr(tenant.settings, field, updates["settings"][field])

    await db.commit()
    await RedisManager.delete_cache(f"tenant_cache:{tenant_id}")

    return wrap_response({"detail": "Tenant atualizado"}, getattr(request.state, "request_id", None))


@router.delete(
    "/tenants/{tenant_id}",
    summary="Deletar tenant (irreversível)",
    dependencies=[Depends(require_super_admin)],
)
async def delete_tenant(
    request: Request,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    tenant = (await db.execute(select(Tenant).filter(Tenant.id == tenant_id))).scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    await db.delete(tenant)
    await db.commit()
    await RedisManager.delete_cache(f"tenant_cache:{tenant_id}")

    logger.warning(f"Tenant removido: {tenant_id}")
    return wrap_response({"detail": f"Tenant {tenant_id} removido"}, getattr(request.state, "request_id", None))


@router.post("/tenants/{tenant_id}/webhooks/sync", summary="Configurar webhook do tenant")
async def sync_webhook(
    request: Request,
    tenant_id: str,
    body: WebhookSync,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Cria ou atualiza o webhook principal do tenant com validação SSRF."""
    # Proteção SSRF
    try:
        validated_url = validate_webhook_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stmt = select(WebhookSubscription).filter(WebhookSubscription.tenant_id == tenant_id)
    webhook = (await db.execute(stmt)).scalars().first()

    import secrets
    if webhook:
        webhook.url = validated_url
        webhook.is_active = True
    else:
        webhook = WebhookSubscription(
            tenant_id=tenant_id,
            url=validated_url,
            events=["*"],
            secret=secrets.token_hex(16),
            is_active=True,
        )
        db.add(webhook)

    await db.commit()
    return wrap_response({"detail": "Webhook configurado", "url": validated_url}, getattr(request.state, "request_id", None))


@router.get("/stats", summary="Estatísticas gerais do sistema")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    from ..domain.users.model import User
    from ..domain.messages.model import Message

    total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar_one()
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar_one()

    return wrap_response(
        {"total_tenants": total_tenants, "total_users": total_users, "total_messages": total_messages},
        getattr(request.state, "request_id", None),
    )
