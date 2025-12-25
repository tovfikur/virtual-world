"""add push notification controls

Revision ID: e4f9c0d9a8a1
Revises: d2f4b7d8c1e2
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e4f9c0d9a8a1"
down_revision = "d2f4b7d8c1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_config", sa.Column("enable_push_notifications", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("push_system_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("admin_config", sa.Column("push_marketing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("push_daily_limit", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("admin_config", sa.Column("push_quiet_hours_start", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("admin_config", sa.Column("push_quiet_hours_end", sa.Integer(), nullable=False, server_default="0"))

    op.alter_column("admin_config", "enable_push_notifications", server_default=None)
    op.alter_column("admin_config", "push_system_enabled", server_default=None)
    op.alter_column("admin_config", "push_marketing_enabled", server_default=None)
    op.alter_column("admin_config", "push_daily_limit", server_default=None)
    op.alter_column("admin_config", "push_quiet_hours_start", server_default=None)
    op.alter_column("admin_config", "push_quiet_hours_end", server_default=None)


def downgrade():
    op.drop_column("admin_config", "push_quiet_hours_end")
    op.drop_column("admin_config", "push_quiet_hours_start")
    op.drop_column("admin_config", "push_daily_limit")
    op.drop_column("admin_config", "push_marketing_enabled")
    op.drop_column("admin_config", "push_system_enabled")
    op.drop_column("admin_config", "enable_push_notifications")
