"""Modelo de Tenant e suas configurações."""
import secrets
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True)  # Slug: "clinica_sorriso"
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=True)  # bcrypt hash
    is_active = Column(Boolean, default=True, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)  # None = vitalício
    api_key_last_rotated_at = Column(DateTime(timezone=True), nullable=True)  # Rastrear rotação
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    settings = relationship(
        "TenantSettings", back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="tenant", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="tenant", cascade="all, delete-orphan")
    webhooks = relationship(
        "WebhookSubscription", back_populates="tenant", cascade="all, delete-orphan"
    )
    prompts = relationship(
        "PromptTemplate", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id!r} name={self.name!r}>"


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    base_prompt = Column(Text, nullable=True)
    language = Column(String, default="pt-BR")
    tone = Column(String, nullable=True)
    session_ttl_minutes = Column(Integer, default=30)
    max_context_messages = Column(Integer, default=10)
    buffer_window_seconds = Column(Integer, default=0)  # 0 = desabilitado
    rate_limit_rpm = Column(Integer, default=60)         # Requests por minuto (por tenant)
    daily_token_limit = Column(Integer, default=100_000) # Tokens por dia
    llm_preferences = Column(JSON, default=dict)
    privacy_policy = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="settings")
