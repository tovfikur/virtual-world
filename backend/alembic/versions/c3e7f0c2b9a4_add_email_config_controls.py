"""add email config controls

Revision ID: c3e7f0c2b9a4
Revises: b5c7a6c4a1c0
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3e7f0c2b9a4"
down_revision = "b5c7a6c4a1c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_config", sa.Column("enable_email", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("smtp_host", sa.String(length=255), nullable=True))
    op.add_column("admin_config", sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"))
    op.add_column("admin_config", sa.Column("smtp_username", sa.String(length=255), nullable=True))
    op.add_column("admin_config", sa.Column("smtp_password", sa.String(length=255), nullable=True))
    op.add_column("admin_config", sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("admin_config", sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("admin_config", sa.Column("default_from_email", sa.String(length=255), nullable=True))
    op.add_column("admin_config", sa.Column("email_rate_limit_per_hour", sa.Integer(), nullable=False, server_default="200"))
    op.add_column("admin_config", sa.Column("email_template_theme", sa.String(length=64), nullable=False, server_default="default"))

    op.alter_column("admin_config", "enable_email", server_default=None)
    op.alter_column("admin_config", "smtp_port", server_default=None)
    op.alter_column("admin_config", "smtp_use_tls", server_default=None)
    op.alter_column("admin_config", "smtp_use_ssl", server_default=None)
    op.alter_column("admin_config", "email_rate_limit_per_hour", server_default=None)
    op.alter_column("admin_config", "email_template_theme", server_default=None)


def downgrade():
    op.drop_column("admin_config", "email_template_theme")
    op.drop_column("admin_config", "email_rate_limit_per_hour")
    op.drop_column("admin_config", "default_from_email")
    op.drop_column("admin_config", "smtp_use_ssl")
    op.drop_column("admin_config", "smtp_use_tls")
    op.drop_column("admin_config", "smtp_password")
    op.drop_column("admin_config", "smtp_username")
    op.drop_column("admin_config", "smtp_port")
    op.drop_column("admin_config", "smtp_host")
    op.drop_column("admin_config", "enable_email")
