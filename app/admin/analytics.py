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
from ..domain.sessions.model import Session, SessionStatus
from ..domain.tenants.model import Tenant
from ..domain.users.model import User
from ..domain.messages.model import Message
from ..domain.memories.model import Memory
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
    total_memories = (await db.execute(select(func.count(Memory.id)))).scalar_one()
    
    # Sessões Ativas
    active_sessions = (await db.execute(
        select(func.count(Session.id)).filter(Session.status == SessionStatus.active)
    )).scalar_one()

    # Total de Tokens (Soma de todas as mensagens)
    total_tokens = (await db.execute(
        select(func.sum(Message.tokens_used))
    )).scalar_one() or 0

    return wrap_response(
        {
            "total_tenants": total_tenants,
            "total_users": total_users,
            "total_messages": total_messages,
            "total_memories": total_memories,
            "active_sessions": active_sessions,
            "total_tokens": int(total_tokens),
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
    processed_count = await RedisManager.get_metric("webhook:processed")
    failed_count = await RedisManager.get_metric("webhook:failed")

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
            "webhook_processed_count": processed_count,
            "webhook_failed_count": failed_count,
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

    # Top 5 tenants por mensagens (Requisições) + Tokens
    msg_stmt = (
        select(
            Message.tenant_id,
            Tenant.name,
            func.count(Message.id).label("msgs"),
            func.sum(Message.tokens_used).label("tokens")
        )
        .join(Tenant, Message.tenant_id == Tenant.id)
        .group_by(Message.tenant_id, Tenant.name)
        .order_by(func.count(Message.id).desc())
        .limit(5)
    )

    top_tenants_msgs = (await db.execute(msg_stmt)).all()

    return wrap_response(
        {
            "top_tenants_by_users": [
                {"tenant_id": row.tenant_id, "count": row.count}
                for row in top_tenants_users
            ],
            "top_tenants_by_usage": [
                {
                    "tenant_id": row.tenant_id, 
                    "name": row.name, 
                    "requests": row.msgs, 
                    "tokens": int(row.tokens or 0)
                }
                for row in top_tenants_msgs
            ]
        },
        getattr(request.state, "request_id", None)
    )
@router.get("/memory-growth", summary="Série temporal de crescimento de memórias")
async def get_memory_growth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """
    Retorna a contagem de novas memórias por dia nos últimos 7 dias.
    """
    from datetime import datetime, timedelta, timezone
    
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Agrupar por data de criação
    stmt = (
        select(
            func.date(Memory.created_at).label("day"),
            func.count(Memory.id).label("count")
        )
        .filter(Memory.created_at >= seven_days_ago)
        .group_by(func.date(Memory.created_at))
        .order_by(func.date(Memory.created_at).asc())
    )
    
    results = (await db.execute(stmt)).all()
    
    # Preencher lacunas de dias sem dados
    growth_data = []
    current_date = seven_days_ago.date()
    end_date = datetime.now(timezone.utc).date()
    
    results_map = {row.day: row.count for row in results}
    
    while current_date <= end_date:
        growth_data.append({
            "date": current_date.strftime("%d %b"),
            "count": results_map.get(current_date, 0)
        })
        current_date += timedelta(days=1)

    return wrap_response(growth_data, getattr(request.state, "request_id", None))


@router.get("/recent-activity", summary="Feed de atividades recentes")
async def get_recent_activity(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """
    Retorna os 5 eventos mais recentes (mensagens e memórias) do sistema.
    """
    # 1. Buscar últimas 5 mensagens
    msg_stmt = select(Message).order_by(Message.created_at.desc()).limit(5)
    messages = (await db.execute(msg_stmt)).scalars().all()

    # 2. Buscar últimas 5 memórias
    memo_stmt = select(Memory).order_by(Memory.created_at.desc()).limit(5)
    memories = (await db.execute(memo_stmt)).scalars().all()

    # 3. Combinar e formatar
    activities = []
    for m in messages:
        activities.append({
            "id": f"msg_{m.id}",
            "type": "message",
            "title": "Mensagem Processada",
            "detail": f"Tenant: {m.tenant_id}",
            "timestamp": m.created_at,
            "icon": "💬"
        })
    
    for m in memories:
        activities.append({
            "id": f"memo_{m.id}",
            "type": "memory",
            "title": "Fato Armazenado",
            "detail": f"Chave: {m.key}",
            "timestamp": m.created_at,
            "icon": "🧠"
        })

    # Ordenar por timestamp desc e pegar top 5
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Converter datetime para string para o JSON
    final_feed = []
    for act in activities[:5]:
        act["timestamp"] = act["timestamp"].isoformat()
        final_feed.append(act)

    return wrap_response(final_feed, getattr(request.state, "request_id", None))


@router.get("/tenants/{tenant_id}", summary="Analytics detalhado de um tenant")
async def get_tenant_analytics(
    request: Request,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """
    Retorna métricas agregadas de um tenant específico para o administrador.
    Mesma lógica do v1, mas autenticado via admin JWT.
    """
    from ..domain.sessions.model import Session
    from ..domain.users.model import User
    from ..domain.messages.model import Message

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
        getattr(request.state, "request_id", None),
    )
