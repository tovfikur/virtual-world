"""add auth and password policy to admin config

Revision ID: 5f5ae06c9e1d
Revises: 64d91af0f0bc
Create Date: 2025-12-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f5ae06c9e1d'
down_revision = '64d91af0f0bc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('access_token_expire_minutes', sa.Integer(), nullable=False, server_default='60'))
    op.add_column('admin_config', sa.Column('refresh_token_expire_days', sa.Integer(), nullable=False, server_default='7'))
    op.add_column('admin_config', sa.Column('password_min_length', sa.Integer(), nullable=False, server_default='12'))
    op.add_column('admin_config', sa.Column('password_require_uppercase', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
    op.add_column('admin_config', sa.Column('password_require_lowercase', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
    op.add_column('admin_config', sa.Column('password_require_number', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
    op.add_column('admin_config', sa.Column('password_require_special', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))

    # Clean up server defaults after backfill
    op.alter_column('admin_config', 'access_token_expire_minutes', server_default=None)
    op.alter_column('admin_config', 'refresh_token_expire_days', server_default=None)
    op.alter_column('admin_config', 'password_min_length', server_default=None)
    op.alter_column('admin_config', 'password_require_uppercase', server_default=None)
    op.alter_column('admin_config', 'password_require_lowercase', server_default=None)
    op.alter_column('admin_config', 'password_require_number', server_default=None)
    op.alter_column('admin_config', 'password_require_special', server_default=None)


def downgrade() -> None:
    op.drop_column('admin_config', 'password_require_special')
    op.drop_column('admin_config', 'password_require_number')
    op.drop_column('admin_config', 'password_require_lowercase')
    op.drop_column('admin_config', 'password_require_uppercase')
    op.drop_column('admin_config', 'password_min_length')
    op.drop_column('admin_config', 'refresh_token_expire_days')
    op.drop_column('admin_config', 'access_token_expire_minutes')
