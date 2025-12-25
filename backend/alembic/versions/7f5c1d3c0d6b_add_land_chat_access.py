"""add land chat access table

Revision ID: 7f5c1d3c0d6b
Revises: f9d2c4a1b8e3
Create Date: 2025-12-19 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7f5c1d3c0d6b"
down_revision = "f9d2c4a1b8e3"
branch_labels = None
depends_on = None


def upgrade():
    """Create land_chat_access table for per-land chat permissions."""
    op.create_table(
        "land_chat_access",
        sa.Column("access_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("land_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["land_id"], ["lands.land_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("access_id"),
        sa.UniqueConstraint("land_id", "user_id", name="uq_land_chat_access"),
    )
    op.create_index(
        "ix_land_chat_access_land_id", "land_chat_access", ["land_id"], unique=False
    )
    op.create_index(
        "ix_land_chat_access_user_id", "land_chat_access", ["user_id"], unique=False
    )


def downgrade():
    """Drop land_chat_access table."""
    op.drop_index("ix_land_chat_access_user_id", table_name="land_chat_access")
    op.drop_index("ix_land_chat_access_land_id", table_name="land_chat_access")
    op.drop_table("land_chat_access")
