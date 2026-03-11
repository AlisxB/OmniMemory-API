"""Endpoints de Analytics — métricas de tenant."""
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...database import get_db
from ...core.responses import wrap_response
from ...domain.sessions.model import Session, SessionStatus
from ...domain.users.model import User
from ...domain.messages.model import Message
from ...redis import RedisManager
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — analytics"])


@router.get("/tenants/{tenant_id}/analytics", summary="Métricas do tenant")
async def get_analytics(
    request: Request,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retorna métricas agregadas: sessões, usuários, mensagens e uso de tokens."""
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    total_sessions = (await db.execute(
        select(func.count(Session.id)).filter(Session.tenant_id == tenant_id)
    )).scalar_one()

    total_users = (await db.execute(
        select(func.count(User.id)).filter(User.tenant_id == tenant_id)
    )).scalar_one()

    total_messages = (await db.execute(
        select(func.count(Message.id)).join(Session).filter(Session.tenant_id == tenant_id)
    )).scalar_one()

    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0

    status_result = await db.execute(
        select(Session.status, func.count(Session.id))
        .filter(Session.tenant_id == tenant_id)
        .group_by(Session.status)
    )

    daily_usage = await RedisManager.get_daily_usage(tenant_id)

    return wrap_response(
        {
            "summary": {
                "total_sessions": total_sessions,
                "total_users": total_users,
                "total_messages": total_messages,
                "avg_messages_per_session": round(avg_messages, 2),
            },
            "session_status": {s.value: c for s, c in status_result.all()},
            "today": daily_usage,
        },
        request.state.request_id,
    )


@router.get("/tenants/{tenant_id}/sessions", summary="Listar sessões do tenant")
async def list_sessions(
    request: Request,
    tenant_id: str,
    status: SessionStatus = None,
    db: AsyncSession = Depends(get_db),
):
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    query = select(Session).filter(Session.tenant_id == tenant_id)
    if status:
        query = query.filter(Session.status == status)

    sessions = (await db.execute(
        query.order_by(Session.last_interaction_at.desc()).limit(100)
    )).scalars().all()

    return wrap_response(
        [{"id": s.id, "user_id": s.user_id, "status": s.status, "started_at": s.started_at, "last_interaction_at": s.last_interaction_at} for s in sessions],
        request.state.request_id,
    )


@router.get("/sessions/{session_id}/messages", summary="Histórico de mensagens")
async def get_messages(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    from ...domain.messages.model import Message as Msg
    session = (await db.execute(select(Session).filter(Session.id == session_id))).scalars().first()
    if session:
        await validate_tenant_access(session.tenant_id, request.headers.get("X-API-Key"), db)

    messages = (await db.execute(
        select(Msg).filter(Msg.session_id == session_id).order_by(Msg.created_at.asc())
    )).scalars().all()

    return wrap_response(
        [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at} for m in messages],
        request.state.request_id,
    )
