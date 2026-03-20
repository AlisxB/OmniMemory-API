"""
OmniMemory API — Entry Point

Factory pattern: create_app() garante que a aplicação seja configurada
de forma testável e reproduzível.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import text

from .config import settings
from .database import engine, AsyncSessionLocal
from .redis import close_redis
from .middleware.logging import configure_logging
from .middleware.tracing import RequestIDMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .core.responses import wrap_response
from . import models  # Importa todos os modelos para o Alembic

# ─── OpenAPI Metadata ────────────────────────────────────────────────────────
tags_metadata = [
    {
        "name": "v1 — Context & Memory",
        "description": "Endpoints principais de persistência. Gerenciam o 'cérebro' do agente.",
    },
    {
        "name": "v1 — Memories",
        "description": "Busca e deleção de memórias específicas. Conformidade LGPD.",
    },
    {
        "name": "v1 — Webhooks",
        "description": "Gestão de notificações e eventos em tempo real.",
    },
    {
        "name": "v1 — Audio",
        "description": "Processamento de voz para texto via Whisper.",
    },
    {
        "name": "admin",
        "description": "Operações administrativas globais.",
    },
    {
        "name": "admin — auth",
        "description": "Autenticação JWT para administradores.",
    },
    {
        "name": "admin — tenants",
        "description": "Gestão de chaves, limites e status de clientes (tenants).",
    },
    {
        "name": "admin — analytics",
        "description": "Monitoramento de filas, infra e estatísticas de uso.",
    },
    {
        "name": "observability",
        "description": "Health checks e status da infraestrutura.",
    },
]

# ─── Logging (deve ser o primeiro a ser configurado) ─────────────────────────
configure_logging()
logger = logging.getLogger(__name__)


# ─── Sentry ──────────────────────────────────────────────────────────────────
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.2 if settings.is_production else 1.0,
        environment=settings.environment,
        send_default_pii=False,  # Não enviar PII ao Sentry
    )


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia recursos da aplicação no startup e shutdown."""
    logger.info(f"🧠 OmniMemory API v{settings.api_version} iniciando... env={settings.environment}")

    # ── Startup ────────────────────────────────────────────────────────────
    # 1. Garantir extensão pgvector no PostgreSQL
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("PostgreSQL pgvector: OK")

    # 2. Criar tabelas (Alembic gerencia migrations em produção)
    #    Em desenvolvimento, criamos automaticamente para conveniência.
    if settings.is_development:
        from .database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables: synced (development mode)")

    # 3. Iniciar workers em background
    from .workers.webhook_worker import WebhookWorker
    asyncio.create_task(WebhookWorker.process_queue())
    logger.info("WebhookWorker: started")

    logger.info("✅ OmniMemory API pronta para receber requests")

    yield  # ── Aplicação ativa ────────────────────────────────────────────

    # ── Shutdown ───────────────────────────────────────────────────────────
    await close_redis()
    await engine.dispose()
    logger.info("🛑 OmniMemory API encerrada com segurança")


# ─── Factory ─────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="OmniMemory API",
        description=(
            "Enterprise-grade Headless Context & Memory API. "
            "O 'cérebro persistente' para agentes de IA conversacional."
        ),
        version=settings.api_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        lifespan=lifespan,
        openapi_tags=tags_metadata,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    # ── Middlewares (ordem importa!) ────────────────────────────────────────
    # 1. CORS (deve ser o mais externo)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Rate Limit global (proteção antes de qualquer processamento)
    app.add_middleware(
        RateLimitMiddleware,
        global_limit=settings.global_rate_limit_rpm,
        admin_limit=settings.admin_rate_limit_rpm,
        window_seconds=60,
    )

    # 3. Request ID (tracing)
    app.add_middleware(RequestIDMiddleware)

    # ── Exception Handlers ──────────────────────────────────────────────────
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=wrap_response({"detail": exc.detail}, request_id=request_id),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            errors.append(f"{loc}: {error['msg']}")
        return JSONResponse(
            status_code=422,
            content=wrap_response(
                {"detail": "Erro de validação nos dados enviados", "errors": errors},
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=wrap_response({"detail": "Internal Server Error"}, request_id=request_id),
        )

    # ── Routers ─────────────────────────────────────────────────────────────
    from .api.v1.router import router as v1_router
    from .admin.router import router as admin_router

    app.include_router(v1_router, prefix="/v1", tags=["v1 — Context & Memory"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    # ── Endpoints Utilitários ───────────────────────────────────────────────
    @app.get("/health", tags=["observability"], summary="Health check da infraestrutura")
    async def health_check(request: Request):
        from .database import check_db_connection
        from .redis import RedisManager

        request_id = getattr(request.state, "request_id", None)

        db_ok = await check_db_connection()
        redis_ok = await RedisManager.ping()

        checks = {
            "database": {"status": "ok" if db_ok else "error"},
            "redis": {"status": "ok" if redis_ok else "error"},
        }

        is_healthy = db_ok and redis_ok
        overall = "healthy" if is_healthy else "degraded"
        status_code = 200 if is_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content=wrap_response(
                {
                    "status": overall,
                    "version": settings.api_version,
                    "environment": settings.environment,
                    "checks": checks,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                request_id=request_id,
            ),
        )

    @app.get("/", tags=["observability"], include_in_schema=False)
    def root():
        """Endpoint raiz anonimizado (segurança)."""
        return {"status": "online"}

    return app


# ─── Instância da aplicação ───────────────────────────────────────────────────
app = create_app()
