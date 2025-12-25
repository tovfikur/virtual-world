"""add_marketplace_fee_tiers_to_admin_config

Revision ID: b222e15ef629
Revises: 21898356c9ef
Create Date: 2025-12-25 20:24:10.184620

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b222e15ef629'
down_revision = '21898356c9ef'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('fee_tier_1_threshold', sa.Integer(), nullable=False, server_default='10000', comment='Amount threshold (BDT) for tier 1'))
    op.add_column('admin_config', sa.Column('fee_tier_1_percent', sa.Float(), nullable=False, server_default='5.0', comment='Platform fee percent for amounts below tier 1 threshold'))
    op.add_column('admin_config', sa.Column('fee_tier_2_threshold', sa.Integer(), nullable=False, server_default='50000', comment='Amount threshold (BDT) for tier 2'))
    op.add_column('admin_config', sa.Column('fee_tier_2_percent', sa.Float(), nullable=False, server_default='3.5', comment='Platform fee percent for amounts between tier 1 and tier 2'))
    op.add_column('admin_config', sa.Column('fee_tier_3_threshold', sa.Integer(), nullable=False, server_default='100000', comment='Amount threshold (BDT) for tier 3'))
    op.add_column('admin_config', sa.Column('fee_tier_3_percent', sa.Float(), nullable=False, server_default='2.0', comment='Platform fee percent for amounts above tier 2'))


def downgrade() -> None:
    op.drop_column('admin_config', 'fee_tier_3_percent')
    op.drop_column('admin_config', 'fee_tier_3_threshold')
    op.drop_column('admin_config', 'fee_tier_2_percent')
    op.drop_column('admin_config', 'fee_tier_2_threshold')
    op.drop_column('admin_config', 'fee_tier_1_percent')
    op.drop_column('admin_config', 'fee_tier_1_threshold')
