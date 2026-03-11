"""Modelos de Session e Message com Enum tipados."""
import enum
import uuid

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class SessionStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    expired = "expired"
    human_handoff = "human_handoff"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.active, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_interaction_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, default=dict)

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Session id={self.id!r} status={self.status}>"
