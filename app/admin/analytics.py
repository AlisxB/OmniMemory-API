"""
Admin API — Analytics & System Monitoring.
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..database import get_db
from ..core.responses import wrap_response
from ..redis import RedisManager
from ..domain.tenants.model import Tenant
from ..domain.users.model import User
from ..domain.messages.model import Message
from .auth import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["admin — analytics"])


@router.get("/system-stats", summary="Estatísticas gerais do sistema")
async def get_system_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """
    Retorna contagens totais de todas as entidades do sistema.
    """
    total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar_one()
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar_one()

    return wrap_response(
        {
            "total_tenants": total_tenants,
            "total_users": total_users,
            "total_messages": total_messages,
        },
        getattr(request.state, "request_id", None),
    )


@router.get("/queue-status", summary="Monitoramento das filas Redis")
async def get_queue_status(
    request: Request,
    _: dict = Depends(get_current_admin),
):
    """
    Retorna o estado das filas do Redis (Webhooks, Buffers, Rate Limits).
    """
    webhook_queue_size = await RedisManager.get_list_length("webhook_queue")

    # Escaneia chaves de buffer ativas
    # Nota: Em sistemas gigantes, scan pode ser lento. Usamos um iterador controlado.
    active_buffers_count = 0
    async for key in RedisManager.scan_keys("buffer:*"):
        active_buffers_count += 1

    # Escaneia chaves de rate limit ativas nos últimos 10 minutos
    rate_limited_tenants = []
    async for key in RedisManager.scan_keys("rate_limit:tenant:*"):
        tenant_id = key.split(":")[-1]
        if tenant_id not in rate_limited_tenants:
            rate_limited_tenants.append(tenant_id)

    return wrap_response(
        {
            "webhook_queue_size": webhook_queue_size,
            "active_buffers_count": active_buffers_count,
            "rate_limited_tenants_count": len(rate_limited_tenants),
            "rate_limited_tenants": rate_limited_tenants,
        },
        getattr(request.state, "request_id", None),
    )


@router.get("/tenant-distribution", summary="Distribuição de uso por tenant")
async def get_tenant_distribution(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """
    Retorna os tenants com maior volume de mensagens e usuários.
    """
    # Top 5 tenants por usuários
    user_stmt = select(
        User.tenant_id,
        func.count(User.id).label("count")
    ).group_by(User.tenant_id).order_by(func.count(User.id).desc()).limit(5)

    top_tenants_users = (await db.execute(user_stmt)).all()

    # Top 5 tenants por mensagens
    msg_stmt = select(
        Message.tenant_id,
        func.count(Message.id).label("count")
    ).group_by(Message.tenant_id).order_by(func.count(Message.id).desc()).limit(5)

    top_tenants_msgs = (await db.execute(msg_stmt)).all()

    return wrap_response(
        {
            "top_tenants_by_users": [
                {"tenant_id": row.tenant_id, "count": row.count}
                for row in top_tenants_users
            ],
            "top_tenants_by_messages": [
                {"tenant_id": row.tenant_id, "count": row.count}
                for row in top_tenants_msgs
            ]
        },
        getattr(request.state, "request_id", None)
    )
