"""add_biome_land_base_prices_to_admin_config

Revision ID: 8ba58c58f369
Revises: af6d450fcecb
Create Date: 2025-12-25 20:10:59.449139

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ba58c58f369'
down_revision = 'af6d450fcecb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add biome land base price columns to admin_config table
    op.add_column('admin_config', sa.Column('plains_base_price', sa.Float(), nullable=False, server_default='125.0', comment='Base price for plains biome land'))
    op.add_column('admin_config', sa.Column('forest_base_price', sa.Float(), nullable=False, server_default='100.0', comment='Base price for forest biome land'))
    op.add_column('admin_config', sa.Column('beach_base_price', sa.Float(), nullable=False, server_default='90.0', comment='Base price for beach biome land'))
    op.add_column('admin_config', sa.Column('mountain_base_price', sa.Float(), nullable=False, server_default='80.0', comment='Base price for mountain biome land'))
    op.add_column('admin_config', sa.Column('desert_base_price', sa.Float(), nullable=False, server_default='55.0', comment='Base price for desert biome land'))
    op.add_column('admin_config', sa.Column('snow_base_price', sa.Float(), nullable=False, server_default='45.0', comment='Base price for snow biome land'))
    op.add_column('admin_config', sa.Column('ocean_base_price', sa.Float(), nullable=False, server_default='30.0', comment='Base price for ocean biome land'))


def downgrade() -> None:
    # Remove biome land base price columns
    op.drop_column('admin_config', 'ocean_base_price')
    op.drop_column('admin_config', 'snow_base_price')
    op.drop_column('admin_config', 'desert_base_price')
    op.drop_column('admin_config', 'mountain_base_price')
    op.drop_column('admin_config', 'beach_base_price')
    op.drop_column('admin_config', 'forest_base_price')
    op.drop_column('admin_config', 'plains_base_price')
