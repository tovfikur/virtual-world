"""add chat and announcement controls

Revision ID: a4d9f2c6e9b7
Revises: c7bf64bb4f5e
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a4d9f2c6e9b7"
down_revision = "c7bf64bb4f5e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_config", sa.Column("chat_max_length", sa.Integer(), nullable=False, server_default="500"))
    op.add_column("admin_config", sa.Column("chat_profanity_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("chat_block_keywords", sa.String(length=1024), nullable=True))
    op.add_column("admin_config", sa.Column("chat_retention_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("admin_config", sa.Column("chat_pm_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("admin_config", sa.Column("chat_group_max_members", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("admin_config", sa.Column("announcement_allow_high_priority", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("announcement_max_priority", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("admin_config", sa.Column("announcement_rate_limit_per_hour", sa.Integer(), nullable=False, server_default="20"))

    op.alter_column("admin_config", "chat_max_length", server_default=None)
    op.alter_column("admin_config", "chat_profanity_filter_enabled", server_default=None)
    op.alter_column("admin_config", "chat_retention_days", server_default=None)
    op.alter_column("admin_config", "chat_pm_enabled", server_default=None)
    op.alter_column("admin_config", "chat_group_max_members", server_default=None)
    op.alter_column("admin_config", "announcement_allow_high_priority", server_default=None)
    op.alter_column("admin_config", "announcement_max_priority", server_default=None)
    op.alter_column("admin_config", "announcement_rate_limit_per_hour", server_default=None)


def downgrade():
    op.drop_column("admin_config", "announcement_rate_limit_per_hour")
    op.drop_column("admin_config", "announcement_max_priority")
    op.drop_column("admin_config", "announcement_allow_high_priority")
    op.drop_column("admin_config", "chat_group_max_members")
    op.drop_column("admin_config", "chat_pm_enabled")
    op.drop_column("admin_config", "chat_retention_days")
    op.drop_column("admin_config", "chat_block_keywords")
    op.drop_column("admin_config", "chat_profanity_filter_enabled")
    op.drop_column("admin_config", "chat_max_length")
