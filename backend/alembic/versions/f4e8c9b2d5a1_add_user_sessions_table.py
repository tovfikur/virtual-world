"""add user sessions table for single-session enforcement

Revision ID: f4e8c9b2d5a1
Revises: 7d3f1d8c2c84
Create Date: 2026-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'f4e8c9b2d5a1'
down_revision = '7d3f1d8c2c84'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_sessions table for tracking active sessions."""
    op.create_table(
        'user_sessions',
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('session_token', sa.String(512), nullable=False),
        sa.Column('device_fingerprint', sa.String(255), nullable=False),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id')
    )

    # Create indexes for efficient queries
    op.create_index('idx_user_sessions_user_id_active', 'user_sessions',
                    ['user_id', 'is_active'])
    op.create_index('idx_user_sessions_device_fingerprint', 'user_sessions',
                    ['device_fingerprint'])
    op.create_index('idx_user_sessions_expires_at', 'user_sessions',
                    ['expires_at'])
    op.create_index('idx_user_sessions_session_token', 'user_sessions',
                    ['session_token'], unique=True)


def downgrade() -> None:
    """Drop user_sessions table."""
    op.drop_table('user_sessions')
