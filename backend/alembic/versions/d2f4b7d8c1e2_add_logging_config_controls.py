"""add logging config controls

Revision ID: d2f4b7d8c1e2
Revises: c3e7f0c2b9a4
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d2f4b7d8c1e2"
down_revision = "c3e7f0c2b9a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_config", sa.Column("log_level", sa.String(length=20), nullable=False, server_default="INFO"))
    op.add_column("admin_config", sa.Column("log_retention_days", sa.Integer(), nullable=False, server_default="30"))
    op.alter_column("admin_config", "log_level", server_default=None)
    op.alter_column("admin_config", "log_retention_days", server_default=None)


def downgrade():
    op.drop_column("admin_config", "log_retention_days")
    op.drop_column("admin_config", "log_level")
