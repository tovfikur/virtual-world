"""
Ensure listings.buy_now_enabled has a default false
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'r20260104_fix_buynow_defaults'
down_revision = 'r20260104_autoextend'
branch_labels = None
depends_on = None


def upgrade():
    # Backfill any nulls and set default to false so inserts without this column succeed
    op.execute("UPDATE listings SET buy_now_enabled = false WHERE buy_now_enabled IS NULL")
    op.alter_column('listings', 'buy_now_enabled', server_default=sa.text('false'))


def downgrade():
    # Remove default
    op.alter_column('listings', 'buy_now_enabled', server_default=None)
