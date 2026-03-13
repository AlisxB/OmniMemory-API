"""Modelo de Message com suporte a Embeddings vetoriais."""
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"
    human = "human"  # Operador humano (handoff)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    raw_payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    embedding = Column(Vector(768), nullable=True)  # Gemini text-embedding-004
    
    # Tracking de Uso (n8n / Workflow)
    execution_id = Column(String(255), nullable=True, index=True)
    tokens_used = Column(Integer, server_default="0", nullable=False)

    # Relacionamentos
    session = relationship("Session", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} session={self.session_id!r}>"
