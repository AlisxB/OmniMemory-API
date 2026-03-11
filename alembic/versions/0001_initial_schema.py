"""
Migration inicial — cria schema completo + índices otimizados.

Gerado automaticamente a partir dos modelos de domínio.
Execute com: alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Ativar extensão pgvector ───────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Tenants ───────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_key_last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_api_key", "tenants", ["api_key"], unique=True)

    # ── Tenant Settings ────────────────────────────────────────────────────
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("base_prompt", sa.Text(), nullable=True),
        sa.Column("language", sa.String(), server_default="pt-BR"),
        sa.Column("tone", sa.String(), nullable=True),
        sa.Column("session_ttl_minutes", sa.Integer(), server_default="30"),
        sa.Column("max_context_messages", sa.Integer(), server_default="10"),
        sa.Column("buffer_window_seconds", sa.Integer(), server_default="0"),
        sa.Column("rate_limit_rpm", sa.Integer(), server_default="60"),
        sa.Column("daily_token_limit", sa.Integer(), server_default="100000"),
        sa.Column("llm_preferences", sa.JSON(), server_default="{}"),
        sa.Column("privacy_policy", sa.JSON(), server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )

    # ── Users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_external_id", "users", ["external_id"])
    op.create_index("ix_users_channel", "users", ["channel"])
    # Índice composto para busca de usuário por tenant+external_id+channel
    op.create_index("ix_users_lookup", "users", ["tenant_id", "external_id", "channel"])

    # ── Sessions ───────────────────────────────────────────────────────────
    session_status = sa.Enum("active", "closed", "expired", "human_handoff", name="sessionstatus")
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("status", session_status, nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    # Índice parcial: sessões ativas por usuário (query mais frequente)
    op.create_index(
        "ix_sessions_user_active",
        "sessions",
        ["user_id", "status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    # Índice para ordenação por última interação
    op.create_index(
        "ix_sessions_last_interaction",
        "sessions",
        ["tenant_id", sa.text("last_interaction_at DESC")],
    )

    # ── Messages ───────────────────────────────────────────────────────────
    message_role = sa.Enum("user", "assistant", "system", "tool", "human", name="messagerole")
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    # Índice para busca de mensagens por sessão ordenadas por data
    op.create_index(
        "ix_messages_session_created",
        "messages",
        ["session_id", sa.text("created_at DESC")],
    )
    # Índice HNSW para busca vetorial (pgvector)
    op.execute(
        "CREATE INDEX ix_messages_embedding_hnsw ON messages "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── Memories ───────────────────────────────────────────────────────────
    memory_scope = sa.Enum("session", "user", "tenant", name="memoryscope")
    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scope", memory_scope, nullable=False),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memories_tenant_id", "memories", ["tenant_id"])
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_key", "memories", ["key"])
    # Índice composto para a query mais frequente: tenant+user+key
    op.create_index("ix_memories_lookup", "memories", ["tenant_id", "user_id", "key"])
    # Índice HNSW para busca semântica de memórias
    op.execute(
        "CREATE INDEX ix_memories_embedding_hnsw ON memories "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── Webhook Subscriptions ──────────────────────────────────────────────
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("events", sa.JSON(), server_default='["*"]'),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_subscriptions_tenant_id", "webhook_subscriptions", ["tenant_id"])

    # ── Prompt Templates ───────────────────────────────────────────────────
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("slug", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_templates_tenant_id", "prompt_templates", ["tenant_id"])
    op.create_index("ix_prompt_templates_slug", "prompt_templates", ["slug"])
    # Índice para buscar prompt ativo por slug
    op.create_index(
        "ix_prompt_templates_active",
        "prompt_templates",
        ["tenant_id", "slug", sa.text("version DESC")],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_table("webhook_subscriptions")
    op.drop_table("memories")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("tenant_settings")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS messagerole")
    op.execute("DROP TYPE IF EXISTS memoryscope")
