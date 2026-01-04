"""
Add auto_extend to listings (and ensure auction_end_time exists)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'r20260104_autoextend'
# Align with actual revision id from land price history migration
down_revision = '2026_01_03_002'
branch_labels = None
depends_on = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = inspect(bind)
    cols = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade():
    bind = op.get_bind()

    if not _has_column(bind, 'listings', 'auto_extend'):
        op.add_column(
            'listings',
            sa.Column('auto_extend', sa.Boolean(), nullable=False, server_default=sa.text('true'))
        )
        # remove server default after backfill
        op.alter_column('listings', 'auto_extend', server_default=None)

    if not _has_column(bind, 'listings', 'auction_end_time'):
        op.add_column(
            'listings',
            sa.Column('auction_end_time', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    bind = op.get_bind()

    if _has_column(bind, 'listings', 'auction_end_time'):
        op.drop_column('listings', 'auction_end_time')

    if _has_column(bind, 'listings', 'auto_extend'):
        op.drop_column('listings', 'auto_extend')
