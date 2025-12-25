"""add_listing_limits_to_admin_config

Revision ID: 6f0fb3cfe4a5
Revises: e1b99f2ac1d0
Create Date: 2025-12-26 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f0fb3cfe4a5'
down_revision = 'e1b99f2ac1d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('max_lands_per_listing', sa.Integer(), nullable=False, server_default='50', comment='Maximum number of land tiles allowed per listing'))
    op.add_column('admin_config', sa.Column('max_listing_duration_days', sa.Integer(), nullable=False, server_default='30', comment='Maximum listing duration for auctions in days'))
    op.add_column('admin_config', sa.Column('listing_cooldown_minutes', sa.Integer(), nullable=False, server_default='5', comment='Cooldown between listings per seller'))
    op.add_column('admin_config', sa.Column('min_reserve_price_percent', sa.Integer(), nullable=False, server_default='50', comment='Minimum reserve price as percent of starting price'))


def downgrade() -> None:
    op.drop_column('admin_config', 'min_reserve_price_percent')
    op.drop_column('admin_config', 'listing_cooldown_minutes')
    op.drop_column('admin_config', 'max_listing_duration_days')
    op.drop_column('admin_config', 'max_lands_per_listing')
