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
    # 1. Limpar duplicatas antes de aplicar a restrição
    # Mantém apenas o registro mais recente (maior ID) para cada tenant
    op.execute("""
        DELETE FROM webhook_subscriptions
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY id DESC) as row_num
                FROM webhook_subscriptions
            ) t
            WHERE t.row_num > 1
        )
    """)

    # 2. Adicionar restrição de unicidade
    op.create_unique_constraint('uq_webhook_subscriptions_tenant_id', 'webhook_subscriptions', ['tenant_id'])


def downgrade():
    op.drop_constraint('uq_webhook_subscriptions_tenant_id', 'webhook_subscriptions', type_='unique')
