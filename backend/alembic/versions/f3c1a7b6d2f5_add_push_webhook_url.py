"""add push webhook url

Revision ID: f3c1a7b6d2f5
Revises: e4f9c0d9a8a1
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3c1a7b6d2f5"
down_revision = "e4f9c0d9a8a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_config", sa.Column("push_webhook_url", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("admin_config", "push_webhook_url")
