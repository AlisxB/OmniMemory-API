"""Modelo de User."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    external_id = Column(String, index=True)  # Número WhatsApp, e-mail, etc.
    channel = Column(String, index=True)      # "whatsapp", "telegram", "web", "api"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} external_id={self.external_id!r} channel={self.channel!r}>"
