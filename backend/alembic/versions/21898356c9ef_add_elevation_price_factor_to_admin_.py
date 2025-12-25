"""add_elevation_price_factor_to_admin_config

Revision ID: 21898356c9ef
Revises: 8ba58c58f369
Create Date: 2025-12-25 20:21:15.785549

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21898356c9ef'
down_revision = '8ba58c58f369'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add elevation price factor columns with defaults
    op.add_column(
        'admin_config',
        sa.Column(
            'elevation_price_min_factor',
            sa.Float(),
            nullable=False,
            server_default='0.8',
            comment='Minimum elevation price factor (elevation=0)'
        )
    )
    op.add_column(
        'admin_config',
        sa.Column(
            'elevation_price_max_factor',
            sa.Float(),
            nullable=False,
            server_default='1.2',
            comment='Maximum elevation price factor (elevation=1)'
        )
    )


def downgrade() -> None:
    op.drop_column('admin_config', 'elevation_price_max_factor')
    op.drop_column('admin_config', 'elevation_price_min_factor')
