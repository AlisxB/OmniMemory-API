"""unique_tenant_webhook

Revision ID: 601e876c111c
Revises: 3cf4b14d599b
Create Date: 2026-03-15 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '601e876c111c'
down_revision = '3cf4b14d599b'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar restrição de unicidade no tenant_id para webhook_subscriptions
    # Nota: Se houver duplicatas, esta operação falhará no PostgreSQL.
    op.create_unique_constraint('uq_webhook_subscriptions_tenant_id', 'webhook_subscriptions', ['tenant_id'])


def downgrade():
    op.drop_constraint('uq_webhook_subscriptions_tenant_id', 'webhook_subscriptions', type_='unique')
