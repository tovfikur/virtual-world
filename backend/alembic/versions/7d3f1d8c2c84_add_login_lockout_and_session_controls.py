"""add login lockout and session controls

Revision ID: 7d3f1d8c2c84
Revises: 5f5ae06c9e1d
Create Date: 2025-12-26 00:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d3f1d8c2c84'
down_revision = '5f5ae06c9e1d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admin_config', sa.Column('login_max_attempts', sa.Integer(), nullable=False, server_default='5'))
    op.add_column('admin_config', sa.Column('lockout_duration_minutes', sa.Integer(), nullable=False, server_default='15'))
    op.add_column('admin_config', sa.Column('max_sessions_per_user', sa.Integer(), nullable=False, server_default='1'))

    op.alter_column('admin_config', 'login_max_attempts', server_default=None)
    op.alter_column('admin_config', 'lockout_duration_minutes', server_default=None)
    op.alter_column('admin_config', 'max_sessions_per_user', server_default=None)


def downgrade() -> None:
    op.drop_column('admin_config', 'max_sessions_per_user')
    op.drop_column('admin_config', 'lockout_duration_minutes')
    op.drop_column('admin_config', 'login_max_attempts')
