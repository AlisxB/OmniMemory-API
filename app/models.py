"""
Modelos SQLAlchemy organizados por domínio.

Cada entidade tem seu próprio arquivo em app/domain/<entidade>/model.py.
Este arquivo central apenas importa todos para facilitar o Alembic e o `create_all`.
"""

from .domain.tenants.model import Tenant, TenantSettings
from .domain.users.model import User
from .domain.sessions.model import Session, SessionStatus
from .domain.messages.model import Message, MessageRole
from .domain.memories.model import Memory, MemoryScope
from .domain.webhooks.model import WebhookSubscription
from .domain.prompts.model import PromptTemplate

__all__ = [
    "Tenant",
    "TenantSettings",
    "User",
    "Session",
    "SessionStatus",
    "Message",
    "MessageRole",
    "Memory",
    "MemoryScope",
    "WebhookSubscription",
    "PromptTemplate",
]
