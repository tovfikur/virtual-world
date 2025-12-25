"""add_biome_market_controls_to_admin_config

Revision ID: af6d450fcecb
Revises: efe08093a173
Create Date: 2025-12-25 20:03:49.681080

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af6d450fcecb'
down_revision = 'efe08093a173'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add biome trade fee column
    op.add_column('admin_config', sa.Column('biome_trade_fee_percent', sa.Float(), nullable=False, server_default='2.0', comment='Platform fee for biome share trading (separate from marketplace)'))
    
    # Add biome market control columns
    op.add_column('admin_config', sa.Column('max_price_move_percent', sa.Float(), nullable=False, server_default='5.0', comment='Maximum price movement per redistribution cycle'))
    op.add_column('admin_config', sa.Column('max_transaction_percent', sa.Float(), nullable=False, server_default='10.0', comment='Maximum single transaction as % of market cap'))
    op.add_column('admin_config', sa.Column('redistribution_pool_percent', sa.Float(), nullable=False, server_default='25.0', comment='Percentage of total market cash to redistribute'))
    
    # Add emergency circuit breaker columns
    op.add_column('admin_config', sa.Column('biome_trading_paused', sa.Boolean(), nullable=False, server_default='false', comment='Emergency pause for all biome trading'))
    op.add_column('admin_config', sa.Column('biome_prices_frozen', sa.Boolean(), nullable=False, server_default='false', comment='Freeze biome prices (no redistribution)'))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column('admin_config', 'biome_prices_frozen')
    op.drop_column('admin_config', 'biome_trading_paused')
    op.drop_column('admin_config', 'redistribution_pool_percent')
    op.drop_column('admin_config', 'max_transaction_percent')
    op.drop_column('admin_config', 'max_price_move_percent')
    op.drop_column('admin_config', 'biome_trade_fee_percent')
