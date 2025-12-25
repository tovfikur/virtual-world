"""add_auction_duration_limits_to_admin_config

Revision ID: a5ccbcac5fb6
Revises: b222e15ef629
Create Date: 2025-12-25 20:27:42.627411

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5ccbcac5fb6'
down_revision = 'b222e15ef629'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('auction_min_duration_hours', sa.Integer(), nullable=False, server_default='1', comment='Minimum allowed auction duration in hours'))
    op.add_column('admin_config', sa.Column('auction_max_duration_hours', sa.Integer(), nullable=False, server_default='168', comment='Maximum allowed auction duration in hours (7 days)'))


def downgrade() -> None:
    op.drop_column('admin_config', 'auction_max_duration_hours')
    op.drop_column('admin_config', 'auction_min_duration_hours')
