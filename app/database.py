"""
Conexão assíncrona com o PostgreSQL via SQLAlchemy + asyncpg.
Pool de conexões otimizado para produção.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging

from .config import settings

logger = logging.getLogger(__name__)

# ─── Engine com pool otimizado ───────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url_async,
    pool_size=20,           # Conexões permanentes no pool
    max_overflow=10,        # Conexões extras sob carga (total máx = 30)
    pool_pre_ping=True,     # Verifica se conexão está viva antes de usar
    pool_recycle=3600,      # Recicla conexões a cada 1h (evita "stale connections")
    echo=settings.is_development,
)

# ─── Session Factory ─────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Evita lazy-loading após commit
    autocommit=False,
    autoflush=False,
)


# ─── Base Declarativa ────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─── Dependency FastAPI ───────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    Dependency do FastAPI que fornece uma sessão async do banco de dados.
    Garante que a sessão seja fechada ao final de cada request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Verifica se o banco está acessível. Usado no health check."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
