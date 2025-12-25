"""add_payment_gateway_settings_to_admin_config

Revision ID: e1b99f2ac1d0
Revises: 64d91af0f0bc
Create Date: 2025-12-26 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1b99f2ac1d0'
down_revision = '64d91af0f0bc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('enable_bkash', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('admin_config', sa.Column('enable_nagad', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('admin_config', sa.Column('enable_rocket', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('admin_config', sa.Column('enable_sslcommerz', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('admin_config', sa.Column('bkash_mode', sa.String(length=10), nullable=False, server_default='test'))
    op.add_column('admin_config', sa.Column('nagad_mode', sa.String(length=10), nullable=False, server_default='test'))
    op.add_column('admin_config', sa.Column('rocket_mode', sa.String(length=10), nullable=False, server_default='test'))
    op.add_column('admin_config', sa.Column('sslcommerz_mode', sa.String(length=10), nullable=False, server_default='test'))
    op.add_column('admin_config', sa.Column('topup_min_bdt', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('admin_config', sa.Column('topup_max_bdt', sa.Integer(), nullable=False, server_default='100000'))
    op.add_column('admin_config', sa.Column('topup_daily_limit_bdt', sa.Integer(), nullable=False, server_default='200000'))
    op.add_column('admin_config', sa.Column('topup_monthly_limit_bdt', sa.Integer(), nullable=False, server_default='1000000'))


def downgrade() -> None:
    op.drop_column('admin_config', 'topup_monthly_limit_bdt')
    op.drop_column('admin_config', 'topup_daily_limit_bdt')
    op.drop_column('admin_config', 'topup_max_bdt')
    op.drop_column('admin_config', 'topup_min_bdt')
    op.drop_column('admin_config', 'sslcommerz_mode')
    op.drop_column('admin_config', 'rocket_mode')
    op.drop_column('admin_config', 'nagad_mode')
    op.drop_column('admin_config', 'bkash_mode')
    op.drop_column('admin_config', 'enable_sslcommerz')
    op.drop_column('admin_config', 'enable_rocket')
    op.drop_column('admin_config', 'enable_nagad')
    op.drop_column('admin_config', 'enable_bkash')
