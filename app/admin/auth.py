"""
Router de autenticação do Admin Dashboard.
Emite JWT de curta duração substituindo o HTTP Basic Auth primitivo.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from ..core.security import JWTManager
from ..core.responses import wrap_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["admin — auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Dependency ──────────────────────────────────────────────────────────────

async def get_current_admin(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency que valida o JWT e retorna o payload."""
    payload = JWTManager.decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Login do Admin Dashboard")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Autentica o administrador e retorna tokens JWT.
    - `username`: qualquer valor (ex: "admin")
    - `password`: ADMIN_PASSWORD configurado no .env
    """
    if not JWTManager.verify_admin_credentials(form_data.password):
        logger.warning(f"Admin login failed for username={form_data.username!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {"sub": form_data.username, "role": "admin"}
    access_token = JWTManager.create_access_token(payload)
    refresh_token = JWTManager.create_refresh_token(payload)

    logger.info(f"Admin login successful: username={form_data.username!r}")

    from ..config import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Renovar token de acesso")
async def refresh_token(body: RefreshRequest):
    """Renova o access token usando o refresh token."""
    payload = JWTManager.decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )

    new_payload = {"sub": payload.get("sub"), "role": "admin"}
    access_token = JWTManager.create_access_token(new_payload)
    new_refresh = JWTManager.create_refresh_token(new_payload)

    from ..config import settings
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", summary="Logout (invalida sessão client-side)")
async def logout():
    """
    Logout do Admin. Como JWTs são stateless, o cliente deve descartar os tokens.
    Em uma versão futura, implementar blocklist de JWTs no Redis.
    """
    return wrap_response({"detail": "Logout realizado com sucesso"})
