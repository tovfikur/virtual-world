"""add_starter_land_config

Revision ID: 4bb0e68e56f8
Revises: e68b670b646e
Create Date: 2025-11-04 22:34:07.627983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4bb0e68e56f8'
down_revision = 'e68b670b646e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add land allocation settings to admin_config
    op.add_column('admin_config', sa.Column('starter_land_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('admin_config', sa.Column('starter_land_min_size', sa.Integer(), nullable=False, server_default='36'))
    op.add_column('admin_config', sa.Column('starter_land_max_size', sa.Integer(), nullable=False, server_default='1000'))
    op.add_column('admin_config', sa.Column('starter_land_buffer_units', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('admin_config', sa.Column('starter_shape_variation_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove land allocation settings
    op.drop_column('admin_config', 'starter_shape_variation_enabled')
    op.drop_column('admin_config', 'starter_land_buffer_units')
    op.drop_column('admin_config', 'starter_land_max_size')
    op.drop_column('admin_config', 'starter_land_min_size')
    op.drop_column('admin_config', 'starter_land_enabled')
