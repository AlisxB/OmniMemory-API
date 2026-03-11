"""
conftest.py — Fixtures globais para todos os testes.

Estratégia:
- Banco de dados SQLite em memória (async) para isolamento e velocidade
- Redis mockado via fakeredis para não depender de infra externa
- Client HTTP assíncrono (httpx.AsyncClient) via ASGITransport
- Tenant e API Key pré-criados para cada test session
"""
import asyncio
import pytest
import pytest_asyncio
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Configurar env de teste ANTES de qualquer import da app ────────────────
import os
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_32_chars_minimum_!!")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_pass")
os.environ.setdefault("SUPER_ADMIN_KEY", "test_super_admin_key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("GROQ_API_KEY", "test_groq_key")
os.environ.setdefault("ENCRYPTION_KEY", "")  # Sem criptografia nos testes

from app.database import Base
from app.main import create_app
from app.core.security import APIKeyManager

# ─── Engine de teste (SQLite async em memória) ──────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Event loop único para toda a sessão de testes."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Cria todas as tabelas uma vez por session de teste."""
    # SQLite não tem pgvector — importamos models sem o Vector
    async with test_engine.begin() as conn:
        # Criar tabelas sem a extensão pgvector
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Sessão de DB isolada por teste com rollback automático."""
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ─── Tenant + API Key de teste ───────────────────────────────────────────────

TENANT_ID = "test_tenant"
TENANT_NAME = "Test Tenant"
RAW_API_KEY = "omni_test_raw_key_abc123xyz"


@pytest_asyncio.fixture(scope="session")
async def tenant_data():
    """Cria o tenant de teste e retorna os dados de acesso."""
    from app.domain.tenants.model import Tenant, TenantSettings

    async with TestSessionLocal() as session:
        from sqlalchemy.future import select
        existing = (await session.execute(
            select(Tenant).filter(Tenant.id == TENANT_ID)
        )).scalars().first()

        if not existing:
            tenant = Tenant(
                id=TENANT_ID,
                name=TENANT_NAME,
                api_key=APIKeyManager.hash_key(RAW_API_KEY),
                is_active=True,
            )
            session.add(tenant)
            session.add(TenantSettings(
                tenant_id=TENANT_ID,
                session_ttl_minutes=30,
                rate_limit_rpm=1000,  # Alto para não limitar nos testes
                buffer_window_seconds=0,
            ))
            await session.commit()

    return {
        "tenant_id": TENANT_ID,
        "api_key_header": f"{TENANT_ID}:{RAW_API_KEY}",
    }


# ─── HTTP Client de teste ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP que usa a app ASGI diretamente (sem bind de porta).
    Injeta a sessão de DB de teste e mocka o Redis.
    """
    app = create_app()

    # Override da dependência de DB
    from app.database import get_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Mock do Redis para não depender de infra
    mock_redis = _build_mock_redis()

    with patch("app.redis._redis_pool", mock_redis), \
         patch("app.redis.get_redis", return_value=mock_redis):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


def _build_mock_redis() -> MagicMock:
    """Constrói um mock do Redis com operações básicas simuladas."""
    mock = AsyncMock()

    # Rate limit: sempre permite
    mock.zremrangebyscore = AsyncMock(return_value=0)
    mock.zadd = AsyncMock(return_value=1)
    mock.zcard = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.pipeline = MagicMock(return_value=_build_mock_pipeline())

    # Session management
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.rpush = AsyncMock(return_value=1)
    mock.lrange = AsyncMock(return_value=[])
    mock.incr = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    mock.lock = MagicMock(return_value=_build_mock_lock())
    mock.blpop = AsyncMock(return_value=None)
    mock.hincrby = AsyncMock(return_value=1)
    mock.hgetall = AsyncMock(return_value={"tokens": "0", "requests": "0"})

    return mock


def _build_mock_pipeline() -> MagicMock:
    pipe = AsyncMock()
    pipe.zremrangebyscore = AsyncMock()
    pipe.zadd = AsyncMock()
    pipe.zcard = AsyncMock()
    pipe.expire = AsyncMock()
    pipe.lrange = AsyncMock()
    pipe.delete = AsyncMock()
    pipe.hincrby = AsyncMock()
    pipe.execute = AsyncMock(return_value=[0, 1, 1, True])
    # Suporta uso como context manager
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)
    return pipe


def _build_mock_lock():
    lock = AsyncMock()
    lock.__aenter__ = AsyncMock(return_value=lock)
    lock.__aexit__ = AsyncMock(return_value=None)
    return lock


# ─── Headers de autenticação ──────────────────────────────────────────────────

@pytest.fixture
def auth_headers():
    """Headers com API Key válida para endpoints v1."""
    return {"X-API-Key": f"{TENANT_ID}:{RAW_API_KEY}"}


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    """Obtém token JWT admin para testes do admin."""
    response = await client.post(
        "/admin/auth/login",
        data={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]},
    )
    assert response.status_code == 200, f"Admin login falhou: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
