"""Endpoints de Prompts — gestão versionada de templates."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...database import get_db
from ...core.responses import wrap_response
from ...core.idempotency import idempotency_key_required
from ...core.cache import cached, invalidate_tenant_prompts
from ...domain.prompts.model import PromptTemplate
from ..deps import validate_tenant_access

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v1 — prompts"])


class PromptCreate(BaseModel):
    slug: str = Field(..., description="Identificador do prompt", example="persona_atendimento")
    content: str = Field(..., min_length=1)
    is_active: bool = True


@router.post("/tenants/{tenant_id}/prompts", summary="Criar prompt template")
@idempotency_key_required
async def create_prompt(
    request: Request,
    tenant_id: str,
    req: PromptCreate,
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo template de prompt. Versões anteriores são preservadas."""
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    # Calcular próxima versão
    last = (await db.execute(
        select(PromptTemplate)
        .filter(PromptTemplate.tenant_id == tenant_id, PromptTemplate.slug == req.slug)
        .order_by(PromptTemplate.version.desc())
    )).scalars().first()

    next_version = (last.version + 1) if last else 1

    # Desativar versões anteriores se is_active=True
    if req.is_active and last:
        last.is_active = False

    prompt = PromptTemplate(
        tenant_id=tenant_id,
        slug=req.slug,
        content=req.content,
        version=next_version,
        is_active=req.is_active,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)

    # Invalidar cache
    await invalidate_tenant_prompts(tenant_id, req.slug)

    return wrap_response(
        {"id": prompt.id, "slug": prompt.slug, "version": prompt.version, "is_active": prompt.is_active},
        request.state.request_id,
    )


@router.get("/tenants/{tenant_id}/prompts/{slug}", summary="Buscar prompt ativo")
async def get_prompt(
    request: Request,
    tenant_id: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Retorna a versão ativa mais recente de um prompt template. Resultado cacheado por 10min."""
    await validate_tenant_access(tenant_id, request.headers.get("X-API-Key"), db)

    prompt = (await db.execute(
        select(PromptTemplate)
        .filter(
            PromptTemplate.tenant_id == tenant_id,
            PromptTemplate.slug == slug,
            PromptTemplate.is_active == True,
        )
        .order_by(PromptTemplate.version.desc())
    )).scalars().first()

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template não encontrado")

    return wrap_response(
        {"id": prompt.id, "slug": prompt.slug, "content": prompt.content, "version": prompt.version},
        request.state.request_id,
    )
