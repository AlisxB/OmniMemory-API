"""Modelo de WebhookSubscription com validação SSRF."""
import secrets

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...database import Base


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, unique=True)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=False, default=lambda: secrets.token_hex(32))
    is_active = Column(Boolean, default=True)
    events = Column(JSON, default=lambda: ["*"])  # ["*"] = todos os eventos
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="webhooks")

    def __repr__(self) -> str:
        return f"<WebhookSubscription id={self.id} url={self.url!r}>"
