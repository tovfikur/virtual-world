"""add gateway fee config and payment events

Revision ID: 8c2c51fa9b17
Revises: 7d3f1d8c2c84
Create Date: 2025-12-26 00:35:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8c2c51fa9b17'
down_revision = '7d3f1d8c2c84'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('gateway_fee_mode', sa.String(length=16), nullable=False, server_default='absorb'))
    op.add_column('admin_config', sa.Column('gateway_fee_percent', sa.Float(), nullable=False, server_default='1.5'))
    op.add_column('admin_config', sa.Column('gateway_fee_flat_bdt', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'payment_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gateway', sa.String(length=32), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )

    op.create_index('ix_payment_events_status_created_at', 'payment_events', ['status', 'created_at'])
    op.create_index('ix_payment_events_gateway_created_at', 'payment_events', ['gateway', 'created_at'])

    op.alter_column('admin_config', 'gateway_fee_mode', server_default=None)
    op.alter_column('admin_config', 'gateway_fee_percent', server_default=None)
    op.alter_column('admin_config', 'gateway_fee_flat_bdt', server_default=None)


def downgrade() -> None:
    op.drop_index('ix_payment_events_gateway_created_at', table_name='payment_events')
    op.drop_index('ix_payment_events_status_created_at', table_name='payment_events')
    op.drop_table('payment_events')
    op.drop_column('admin_config', 'gateway_fee_flat_bdt')
    op.drop_column('admin_config', 'gateway_fee_percent')
    op.drop_column('admin_config', 'gateway_fee_mode')
