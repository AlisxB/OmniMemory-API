"""Endpoints de Memories — CRUD com criptografia e embeddings."""
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from ...database import get_db
from ...core.responses import wrap_response
from ...core.idempotency import idempotency_key_required
from ...core.security import CryptoManager
from ...core.embeddings import EmbeddingService
from ...core.cache import invalidate_user_memories
from ...domain.memories.model import Memory, MemoryScope
from ...workers.webhook_worker import WebhookWorker
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — memories"])


class MemoryCreate(BaseModel):
    tenant_id: str
    external_user_id: Optional[str] = Field(None, description="ID externo (celular, e-mail)")
    user_id: Optional[int] = Field(None, description="ID interno (opcional)")
    scope: MemoryScope = Field(default=MemoryScope.user)
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1)
    expires_at: Optional[datetime] = None


@router.post("/memory", summary="Salvar ou atualizar memória")
@idempotency_key_required
async def save_memory(
    request: Request,
    req: MemoryCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Salva um fato sobre o usuário. Se a chave já existir, atualiza.
    Suporta external_user_id para facilidade de integração.
    """
    await validate_tenant_access(req.tenant_id, request.headers.get("X-API-Key"), db)

    # 1. Resolver UserID interno se external_user_id for fornecido
    memo_user_id = req.user_id
    if req.external_user_id and not memo_user_id:
        from ...domain.users.model import User
        # Buscar usuário pelo ID externo
        res_user = (await db.execute(
            select(User).filter(User.external_id == req.external_user_id, User.tenant_id == req.tenant_id)
        )).scalars().first()
        
        if not res_user:
            # Se não existir, criar um usuário básico para ancorar a memória
            res_user = User(tenant_id=req.tenant_id, external_id=req.external_user_id, channel="api")
            db.add(res_user)
            await db.flush()
        
        memo_user_id = res_user.id

    # 2. Buscar memória existente para atualização (Upsert)
    existing = (await db.execute(
        select(Memory).filter(
            Memory.tenant_id == req.tenant_id,
            Memory.user_id == memo_user_id,
            Memory.key == req.key,
        )
    )).scalars().first()

    encrypted = CryptoManager.encrypt(req.value)
    emb = EmbeddingService.get_embedding(req.value)

    if existing:
        existing.value = encrypted
        existing.scope = req.scope
        existing.expires_at = req.expires_at
        existing.embedding = emb
        db_memory = existing
    else:
        db_memory = Memory(
            tenant_id=req.tenant_id,
            user_id=memo_user_id,
            scope=req.scope,
            key=req.key,
            value=encrypted,
            expires_at=req.expires_at,
            embedding=emb,
        )
        db.add(db_memory)

    await db.commit()
    await db.refresh(db_memory)

    # 3. Invalidar cache + disparar webhook
    if memo_user_id:
        await invalidate_user_memories(req.tenant_id, memo_user_id)
    
    # await WebhookWorker.enqueue(
    #     req.tenant_id,
    #     "memory.updated",
    #     {
    #         "external_user_id": req.external_user_id,
    #         "user_id": memo_user_id, 
    #         "key": req.key, 
    #         "scope": str(req.scope)
    #     },
    # )

    return wrap_response(
        {
            "id": db_memory.id,
            "tenant_id": db_memory.tenant_id,
            "user_id": db_memory.user_id,
            "scope": db_memory.scope,
            "key": db_memory.key,
            "value": CryptoManager.decrypt(db_memory.value),
            "expires_at": db_memory.expires_at,
            "created_at": db_memory.created_at,
        },
        request.state.request_id,
    )


@router.get("/tenants/{tenant_id}/users/{user_id}/memories", summary="Listar memórias do usuário")
async def list_user_memories(
    request: Request,
    tenant_id: str,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    memories = (await db.execute(
        select(Memory)
        .filter(and_(Memory.tenant_id == tenant_id, Memory.user_id == user_id))
        .order_by(Memory.created_at.desc())
    )).scalars().all()

    return wrap_response(
        [{"id": m.id, "key": m.key, "value": CryptoManager.decrypt(m.value), "scope": m.scope} for m in memories],
        request.state.request_id,
    )


@router.delete("/tenants/{tenant_id}/users/{user_id}", summary="Remover usuário (LGPD)")
async def delete_user_data(
    request: Request,
    tenant_id: str,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Direito ao esquecimento — remove todos os dados do usuário (cascade)."""
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    from ...domain.users.model import User
    user = (await db.execute(
        select(User).filter(User.id == user_id, User.tenant_id == tenant_id)
    )).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    await db.delete(user)  # Cascade: sessões, mensagens e memórias
    await db.commit()

    return wrap_response({"detail": "Dados do usuário removidos com sucesso"}, request.state.request_id)
