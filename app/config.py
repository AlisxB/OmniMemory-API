"""
Configurações centralizadas e validadas da OmniMemory API.
Substitui todos os os.getenv() espalhados pelo código.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── Aplicação ─────────────────────────────────────────────────────────────
    environment: str = "development"
    api_version: str = "2.0.0"
    secret_key: str  # OBRIGATÓRIO — levanta ValueError se ausente

    # ─── Banco de Dados ─────────────────────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@postgres:5432/omnimemory"

    # ─── Redis ──────────────────────────────────────────────────────────────────
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # ─── Segurança / Autenticação ───────────────────────────────────────────────
    admin_password: str  # OBRIGATÓRIO
    super_admin_key: str  # OBRIGATÓRIO
    allowed_origins: List[str] = ["*"]

    # JWT (Admin Dashboard)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ─── Rate Limiting ───────────────────────────────────────────────────────────
    global_rate_limit_rpm: int = 200     # Limitação global (fallback)
    admin_rate_limit_rpm: int = 200      # Admin routes — compatível com dashboard polling

    # ─── Crypto ─────────────────────────────────────────────────────────────────
    encryption_key: str = ""  # Fernet key para AES-256 — gerada via CLI se vazio

    # ─── Observabilidade ────────────────────────────────────────────────────────
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    # ─── Serviços Externos ──────────────────────────────────────────────────────
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # ─── Sincronização de Workflows (n8n) ──────────────────────────────────────
    n8n_url: str = ""
    n8n_api_key: str = ""

    # ─── Feature Flags ──────────────────────────────────────────────────────────
    enable_embeddings: bool = True
    enable_audio: bool = True
    enable_webhooks: bool = True

    # ─── Propriedades Derivadas ─────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def docs_url(self) -> str | None:
        return "/docs" if self.is_development else None

    @property
    def redoc_url(self) -> str | None:
        return "/redoc" if self.is_development else None

    @property
    def database_url_async(self) -> str:
        """Retorna a URL do banco com o driver asyncpg."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância singleton das configurações (cacheada)."""
    return Settings()


# Instância global para uso direto
settings = get_settings()
