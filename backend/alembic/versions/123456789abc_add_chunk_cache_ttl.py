"""add chunk cache ttl to admin config

Revision ID: 123456789abc
Revises: a4d9f2c6e9b7
Create Date: 2025-12-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '123456789abc'
down_revision = 'a4d9f2c6e9b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'admin_config',
        sa.Column('chunk_cache_ttl_seconds', sa.Integer(), nullable=False, server_default='3600')
    )
    op.alter_column('admin_config', 'chunk_cache_ttl_seconds', server_default=None)


def downgrade():
    op.drop_column('admin_config', 'chunk_cache_ttl_seconds')
