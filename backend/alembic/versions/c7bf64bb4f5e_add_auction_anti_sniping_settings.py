"""add_auction_anti_sniping_settings

Revision ID: c7bf64bb4f5e
Revises: 5f5ae06c9e1d
Create Date: 2025-12-26 12:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7bf64bb4f5e'
down_revision = '5f5ae06c9e1d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('anti_sniping_enabled', sa.Boolean(), nullable=False, server_default='true', comment='Enable anti-sniping auto-extend near auction end'))
    op.add_column('admin_config', sa.Column('anti_sniping_extend_minutes', sa.Integer(), nullable=False, server_default='5', comment='Minutes to extend when anti-sniping triggers'))
    op.add_column('admin_config', sa.Column('anti_sniping_threshold_minutes', sa.Integer(), nullable=False, server_default='3', comment='If time remaining is below this threshold, extend'))


def downgrade() -> None:
    op.drop_column('admin_config', 'anti_sniping_threshold_minutes')
    op.drop_column('admin_config', 'anti_sniping_extend_minutes')
    op.drop_column('admin_config', 'anti_sniping_enabled')
