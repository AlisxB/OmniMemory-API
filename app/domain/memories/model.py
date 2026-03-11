"""Modelo de Memory com suporte a Embeddings e criptografia."""
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class MemoryScope(str, enum.Enum):
    session = "session"
    user = "user"
    tenant = "tenant"


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope = Column(Enum(MemoryScope), nullable=False)
    key = Column(String, index=True)
    value = Column(Text)          # Armazenado criptografado via Fernet
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Vector(768), nullable=True)  # Para busca semântica

    # Relacionamentos
    tenant = relationship("Tenant", back_populates="memories")
    user = relationship("User", back_populates="memories")

    def __repr__(self) -> str:
        return f"<Memory id={self.id} key={self.key!r} scope={self.scope}>"
