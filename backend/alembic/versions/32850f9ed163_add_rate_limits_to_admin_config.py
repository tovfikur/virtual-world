"""add_rate_limits_to_admin_config

Revision ID: 32850f9ed163
Revises: a5ccbcac5fb6
Create Date: 2025-12-25 20:38:40.656649

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32850f9ed163'
down_revision = 'a5ccbcac5fb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('api_requests_per_minute', sa.Integer(), nullable=False, server_default='120', comment='General API requests per minute per user'))
    op.add_column('admin_config', sa.Column('marketplace_actions_per_hour', sa.Integer(), nullable=False, server_default='200', comment='Marketplace actions per hour per user'))
    op.add_column('admin_config', sa.Column('chat_messages_per_minute', sa.Integer(), nullable=False, server_default='60', comment='Chat messages per minute per user'))
    op.add_column('admin_config', sa.Column('biome_trades_per_minute', sa.Integer(), nullable=False, server_default='120', comment='Biome trade operations per minute per user'))


def downgrade() -> None:
    op.drop_column('admin_config', 'biome_trades_per_minute')
    op.drop_column('admin_config', 'chat_messages_per_minute')
    op.drop_column('admin_config', 'marketplace_actions_per_hour')
    op.drop_column('admin_config', 'api_requests_per_minute')
