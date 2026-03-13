"""
Endpoints de Context — resolve, message e search.
Núcleo da API v1: gerencia sessões, mensagens e busca semântica.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ...database import get_db
from ...core.responses import wrap_response
from ...core.idempotency import idempotency_key_required
from ...core.security import CryptoManager
from ...core.embeddings import EmbeddingService
from ...core.cache import invalidate_user_memories
from ...redis import RedisManager
from ...domain.tenants.model import Tenant, TenantSettings
from ...domain.users.model import User
from ...domain.sessions.model import Session, SessionStatus
from ...domain.messages.model import Message, MessageRole
from ...domain.memories.model import Memory
from ...infrastructure.summarizer import SummarizerService
from ...infrastructure.buffer import MessageBufferService
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — context"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ContextResolveRequest(BaseModel):
    """Resolve ou cria uma sessão ativa para um usuário."""
    tenant_id: str = Field(..., description="ID do tenant", example="clinica_sorriso")
    external_user_id: str = Field(
        ..., description="Identificador externo do usuário (WhatsApp, email, etc.)", example="+5511999990000",
        min_length=3, max_length=100,
    )
    channel: Literal["whatsapp", "telegram", "web", "api"] = Field(
        default="whatsapp", description="Canal de comunicação"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados livres")
    query: Optional[str] = Field(None, description="Query semântica para filtrar memórias relevantes")


class MessageCreate(BaseModel):
    """Persistir uma mensagem em uma sessão."""
    role: MessageRole = Field(default=MessageRole.user)
    content: str = Field(..., min_length=1, max_length=32000)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    # Identificação da sessão — uma das duas formas:
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    external_user_id: Optional[str] = None
    channel: Optional[str] = "whatsapp"
    
    # Tracking de Uso (n8n / Workflow)
    execution_id: Optional[str] = Field(None, description="ID da execução no n8n")
    tokens_used: Optional[int] = Field(0, description="Quantidade de tokens usados")


class SearchRequest(BaseModel):
    """Busca semântica por similaridade vetorial."""
    tenant_id: str = Field(..., description="ID do tenant")
    query: str = Field(..., min_length=2, max_length=512)
    limit: int = Field(default=5, ge=1, le=20)


class MessageUsageUpdate(BaseModel):
    """Atualização de uso de tokens para uma mensagem específica."""
    tokens_used: int = Field(..., ge=0)
    execution_id: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/context/resolve", summary="Resolver contexto do usuário")
async def resolve_context(
    request: Request,
    req: ContextResolveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Ponto de entrada do orquestrador (n8n/LangChain).
    Resolve o usuário, gerencia a sessão com TTL e retorna o contexto completo.
    """
    tenant = await validate_tenant_access(req.tenant_id, request.headers.get("X-API-Key"), db)

    # Carregar settings com cache L2
    await db.refresh(tenant, ["settings"])
    ts = tenant.settings
    session_ttl = ts.session_ttl_minutes if ts else 30
    max_ctx_msgs = ts.max_context_messages if ts else 10
    buffer_window = ts.buffer_window_seconds if ts else 0
    llm_prefs = ts.llm_preferences if ts else {}

    lock_key = f"{req.tenant_id}:{req.external_user_id}"
    async with await RedisManager.get_session_lock(lock_key):
        # Resolver ou criar usuário
        user = (await db.execute(
            select(User).filter(
                and_(
                    User.tenant_id == req.tenant_id,
                    User.external_id == req.external_user_id,
                    User.channel == req.channel,
                )
            )
        )).scalars().first()

        if not user:
            user = User(tenant_id=req.tenant_id, external_id=req.external_user_id, channel=req.channel)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        user_id = user.id

        # Resolver sessão ativa
        now = datetime.now(timezone.utc)
        is_new = False
        active_session_id = await RedisManager.get_active_session_id(req.tenant_id, req.external_user_id)
        session = None

        if active_session_id:
            session = (await db.execute(
                select(Session).filter(Session.id == active_session_id)
            )).scalars().first()
            if not session:
                await RedisManager.delete_session(req.tenant_id, req.external_user_id)

        if not session:
            session = (await db.execute(
                select(Session).filter(
                    and_(Session.user_id == user_id, Session.status == SessionStatus.active)
                ).order_by(Session.last_interaction_at.desc())
            )).scalars().first()

            if session:
                # Verificar se expirou por inatividade
                last = session.last_interaction_at.replace(tzinfo=timezone.utc)
                if (now - last) > timedelta(minutes=session_ttl):
                    expired_id = session.id
                    session.status = SessionStatus.expired
                    session.ended_at = now
                    await db.commit()
                    background_tasks.add_task(SummarizerService.summarize_session, expired_id)
                    session = None

        if not session:
            session = Session(tenant_id=req.tenant_id, user_id=user_id, status=SessionStatus.active)
            if req.metadata:
                session.metadata_json = req.metadata
            db.add(session)
            await db.commit()
            await db.refresh(session)
            is_new = True
        else:
            if req.metadata:
                current = dict(session.metadata_json or {})
                current.update(req.metadata)
                session.metadata_json = current
            session.last_interaction_at = now
            await db.commit()

        session_id = session.id
        session_status = session.status

        await RedisManager.set_session_active(req.tenant_id, req.external_user_id, session_id, session_ttl)

    # Mensagens recentes (fora do lock)
    messages = (await db.execute(
        select(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(max_ctx_msgs)
    )).scalars().all()
    messages = list(reversed(messages))

    # Memórias — com cache L2
    cache_key = f"memories_cache:{req.tenant_id}:{user_id}"
    memory_map = await RedisManager.get_cache(cache_key)

    if memory_map is None:
        stmt_mem = select(Memory).filter(
            and_(Memory.user_id == user_id, Memory.tenant_id == req.tenant_id)
        )
        if req.query:
            query_vec = EmbeddingService.get_embedding(req.query)
            stmt_mem = stmt_mem.order_by(Memory.embedding.cosine_distance(query_vec)).limit(5)
        else:
            stmt_mem = stmt_mem.order_by(Memory.created_at.desc()).limit(5)

        res_mems = (await db.execute(stmt_mem)).scalars().all()
        memory_map = {m.key: CryptoManager.decrypt(m.value) for m in res_mems}
        await RedisManager.set_cache(cache_key, memory_map, ttl_seconds=120)

    return wrap_response(
        {
            "session": {"id": session_id, "status": session_status, "is_new": is_new},
            "settings": {
                "session_ttl_minutes": session_ttl,
                "max_context_messages": max_ctx_msgs,
                "buffer_window_seconds": buffer_window,
                "llm_preferences": llm_prefs,
            },
            "context": {
                "messages": [
                    {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
                    for m in messages
                ],
                "memory": memory_map,
            },
        },
        request.state.request_id,
    )


@router.post("/context/message", summary="Persistir mensagem na sessão")
@idempotency_key_required
async def post_message(
    request: Request,
    req: MessageCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Salva uma mensagem na sessão ativa. Dispara webhooks e buffer inteligente."""
    session = None

    if req.session_id:
        session = (await db.execute(
            select(Session).filter(Session.id == req.session_id).options(selectinload(Session.user))
        )).scalars().first()
    elif req.tenant_id and req.external_user_id:
        user = (await db.execute(
            select(User).filter(
                and_(User.tenant_id == req.tenant_id, User.external_id == req.external_user_id)
            )
        )).scalars().first()
        if not user:
            user = User(tenant_id=req.tenant_id, external_id=req.external_user_id, channel=req.channel or "unknown")
            db.add(user)
            await db.flush()

        active_sid = await RedisManager.get_active_session_id(req.tenant_id, req.external_user_id)
        if active_sid:
            session = (await db.execute(
                select(Session).filter(Session.id == active_sid).options(selectinload(Session.user))
            )).scalars().first()

        if not session:
            session = (await db.execute(
                select(Session).filter(
                    and_(Session.user_id == user.id, Session.status == SessionStatus.active)
                ).order_by(Session.last_interaction_at.desc()).options(selectinload(Session.user))
            )).scalars().first()

        if not session:
            session = Session(tenant_id=req.tenant_id, user_id=user.id, status=SessionStatus.active)
            db.add(session)
            await db.flush()
            session.user = user

    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada e não pôde ser resolvida.")

    tenant_id = session.tenant_id
    user_id = session.user_id
    session_id = session.id
    external_user_id = session.user.external_id
    user_channel = session.user.channel if session.user else "unknown"

    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    # Gerar embedding
    emb = None
    if req.content and req.content.strip():
        emb = EmbeddingService.get_embedding(req.content)

    # Salvar mensagem
    db_message = Message(
        session_id=session_id,
        role=req.role,
        content=req.content,
        raw_payload=req.raw_payload,
        embedding=emb,
        execution_id=req.execution_id,
        tokens_used=req.tokens_used or 0,
    )
    db.add(db_message)

    session.last_interaction_at = datetime.now(timezone.utc)
    if req.role == MessageRole.human:
        session.status = SessionStatus.human_handoff

    # Renovar TTL da sessão no Redis
    tenant_settings = (await db.execute(
        select(TenantSettings).filter(TenantSettings.tenant_id == tenant_id)
    )).scalars().first()

    if tenant_settings:
        await RedisManager.set_session_active(tenant_id, external_user_id, session_id, tenant_settings.session_ttl_minutes)

    await db.commit()
    await db.refresh(db_message)

    # Lógica de Buffer e Webhooks
    has_buffer = tenant_settings and (tenant_settings.buffer_window_seconds or 0) > 0
    should_trigger_webhook = req.role != MessageRole.assistant

    if should_trigger_webhook:
        if req.role == MessageRole.user and has_buffer:
            # Buffer ativo — session.ready vai disparar no lugar de message.created
            logger.info(f"Buffer ativo para session={session_id}, adiando webhook message.created")
        else:
            await invalidate_user_memories(tenant_id, user_id)
            from ...workers.webhook_worker import WebhookWorker
            await WebhookWorker.enqueue(
                tenant_id,
                "message.created",
                {
                    "session_id": str(session_id),
                    "sessionid": str(session_id),
                    "tenant_id": str(tenant_id),
                    "external_user_id": str(external_user_id),
                    "channel": str(user_channel),
                    "role": str(req.role),
                    "content": str(req.content),
                },
            )

    if has_buffer and req.role == MessageRole.user:
        buf_window = tenant_settings.buffer_window_seconds
        background_tasks.add_task(MessageBufferService.process_message, session_id, req.content, buf_window)

    # Registrar uso
    await RedisManager.record_usage(tenant_id, tokens=req.tokens_used or 0)

    return wrap_response(
        {
            "id": db_message.id,
            "session_id": db_message.session_id,
            "role": db_message.role,
            "content": db_message.content,
            "created_at": db_message.created_at,
            "execution_id": db_message.execution_id,
            "tokens_used": db_message.tokens_used,
        },
        request.state.request_id,
    )


@router.patch("/context/messages/{message_id}/usage", summary="Atualizar uso de tokens da mensagem")
async def update_message_usage(
    request: Request,
    message_id: int,
    req: MessageUsageUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Atualiza o consumo de tokens de uma mensagem após a execução do workflow.
    Útil para n8n que só sabe o total de tokens ao final da execução.
    """
    stmt = select(Message).filter(Message.id == message_id).options(selectinload(Message.session))
    db_message = (await db.execute(stmt)).scalars().first()

    if not db_message:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")

    tenant_id = db_message.session.tenant_id
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    # Calcular a diferença para atualizar o Redis corretamente
    diff = req.tokens_used - (db_message.tokens_used or 0)
    
    db_message.tokens_used = req.tokens_used
    if req.execution_id:
        db_message.execution_id = req.execution_id

    await db.commit()
    
    if diff != 0:
        await RedisManager.record_usage(tenant_id, tokens=diff)

    return wrap_response(
        {
            "id": db_message.id,
            "tokens_used": db_message.tokens_used,
            "execution_id": db_message.execution_id,
        },
        request.state.request_id,
    )


@router.get("/context/search", summary="Busca semântica (GET)")
async def semantic_search_get(
    request: Request,
    tenant_id: str,
    query: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Busca por similaridade semântica via query params."""
    return await _perform_search(request, tenant_id, query, limit, db)


@router.post("/context/search", summary="Busca semântica (POST)")
async def semantic_search_post(
    request: Request,
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Busca por similaridade semântica via JSON body (ideal para n8n AI Agents)."""
    return await _perform_search(request, req.tenant_id, req.query, req.limit, db)


async def _perform_search(request: Request, tenant_id: str, query: str, limit: int, db: AsyncSession):
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    query_vec = EmbeddingService.get_embedding(query)

    memories = (await db.execute(
        select(Memory)
        .filter(Memory.tenant_id == tenant_id)
        .order_by(Memory.embedding.cosine_distance(query_vec))
        .limit(limit)
    )).scalars().all()

    messages = (await db.execute(
        select(Message)
        .join(Session)
        .filter(Session.tenant_id == tenant_id)
        .order_by(Message.embedding.cosine_distance(query_vec))
        .limit(limit)
    )).scalars().all()

    return wrap_response(
        {
            "memories": [{"key": m.key, "value": CryptoManager.decrypt(m.value)} for m in memories],
            "messages": [{"content": m.content, "role": m.role, "created_at": m.created_at} for m in messages],
        },
        request.state.request_id,
    )
