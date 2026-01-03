"""add biome land market table for economy system

Revision ID: 2026_01_03_001
Revises: 1de27dadc797
Create Date: 2026-01-03 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_01_03_001'
down_revision = '1de27dadc797'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create biome land market table
    op.create_table(
        'biome_land_markets',
        sa.Column('biome', sa.String(50), primary_key=True, nullable=False),
        sa.Column('sold_lands_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_price_bdt', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_market_value_bdt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_transaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('biome_land_markets')
