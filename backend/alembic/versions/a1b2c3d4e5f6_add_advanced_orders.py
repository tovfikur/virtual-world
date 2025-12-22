"""Add advanced order fields and trailing_stop enum value"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "7f5c1d3c0d6b"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    has_table = conn.execute(text("SELECT to_regclass('public.orders')")).scalar()
    if not has_table:
        return

    # Extend enum safely if it exists
    try:
        op.execute("ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'trailing_stop';")
    except Exception:
        pass

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("trailing_offset", sa.Numeric(24, 8), nullable=True))
        batch_op.add_column(sa.Column("oco_group_id", sa.String(length=64), nullable=True))


def downgrade():
    conn = op.get_bind()
    has_table = conn.execute(text("SELECT to_regclass('public.orders')")).scalar()
    if not has_table:
        return
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("oco_group_id")
        batch_op.drop_column("trailing_offset")
    # Enum value removal is intentionally skipped (not supported safely without recreation).
