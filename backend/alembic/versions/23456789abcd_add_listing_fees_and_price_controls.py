"""add listing fees and price controls

Revision ID: 23456789abcd
Revises: 123456789abc
Create Date: 2025-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '23456789abcd'
down_revision = '123456789abc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('admin_config', sa.Column('listing_creation_fee_bdt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('admin_config', sa.Column('premium_listing_fee_bdt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('admin_config', sa.Column('success_fee_mode', sa.String(length=16), nullable=False, server_default='percent'))
    op.add_column('admin_config', sa.Column('success_fee_percent', sa.Float(), nullable=False, server_default='2.0'))
    op.add_column('admin_config', sa.Column('success_fee_flat_bdt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('admin_config', sa.Column('max_price_deviation_percent', sa.Float(), nullable=False, server_default='25.0'))
    op.add_column('admin_config', sa.Column('parcel_size_limit', sa.Integer(), nullable=False, server_default='0'))

    op.alter_column('admin_config', 'listing_creation_fee_bdt', server_default=None)
    op.alter_column('admin_config', 'premium_listing_fee_bdt', server_default=None)
    op.alter_column('admin_config', 'success_fee_mode', server_default=None)
    op.alter_column('admin_config', 'success_fee_percent', server_default=None)
    op.alter_column('admin_config', 'success_fee_flat_bdt', server_default=None)
    op.alter_column('admin_config', 'max_price_deviation_percent', server_default=None)
    op.alter_column('admin_config', 'parcel_size_limit', server_default=None)


def downgrade():
    op.drop_column('admin_config', 'parcel_size_limit')
    op.drop_column('admin_config', 'max_price_deviation_percent')
    op.drop_column('admin_config', 'success_fee_flat_bdt')
    op.drop_column('admin_config', 'success_fee_percent')
    op.drop_column('admin_config', 'success_fee_mode')
    op.drop_column('admin_config', 'premium_listing_fee_bdt')
    op.drop_column('admin_config', 'listing_creation_fee_bdt')
