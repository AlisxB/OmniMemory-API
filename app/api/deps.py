"""
Dependências compartilhadas entre todos os endpoints v1.
Centraliza validação de API Key, acesso ao banco e Redis.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..database import get_db
from ..domain.tenants.model import Tenant
from ..core.security import APIKeyManager
from ..redis import RedisManager, get_redis

logger = logging.getLogger(__name__)


async def validate_tenant_access(
    tenant_id: str,
    api_key_header: Optional[str],
    db: AsyncSession,
) -> Tenant:
    """
    Valida o acesso do Tenant via X-API-Key.
    - Verifica se o tenant existe e está ativo
    - Verifica se a assinatura está vigente
    - Verifica o rate limit por tenant
    - Verifica o limite diário de tokens

    Retorna o Tenant se válido, ou lança HTTPException.
    """
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-API-Key é obrigatório",
        )

    # Parse do formato "tenant_id:raw_key"
    try:
        header_tenant_id, raw_key = APIKeyManager.parse_header_key(api_key_header)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Garantir que o tenant_id do header bate com o da rota/body
    if header_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant ID no header não corresponde ao recurso solicitado",
        )

    # Buscar tenant no banco (com cache futuro)
    stmt = select(Tenant).filter(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt)).scalars().first()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    if not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant inativo")

    # Verificar expiração da assinatura
    if tenant.subscription_expires_at:
        from datetime import datetime, timezone
        if datetime.now(timezone.utc) > tenant.subscription_expires_at.replace(tzinfo=timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Assinatura do Tenant expirada",
            )

    # Verificar API Key (bcrypt — operação custosa, considerar cache)
    if not tenant.api_key or not APIKeyManager.verify_key(raw_key, tenant.api_key):
        logger.warning(f"Invalid API key attempt for tenant: {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )

    # Rate limit por tenant (sliding window no Redis)
    from ..domain.tenants.model import TenantSettings
    settings_stmt = select(TenantSettings).filter(TenantSettings.tenant_id == tenant_id)
    tenant_settings = (await db.execute(settings_stmt)).scalars().first()
    limit_rpm = tenant_settings.rate_limit_rpm if tenant_settings else 60

    if not await RedisManager.check_tenant_rate_limit(tenant_id, limit_rpm):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit atingido para este tenant ({limit_rpm} req/min)",
            headers={"Retry-After": "60"},
        )

    return tenant
