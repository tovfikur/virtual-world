"""add payment monitoring controls

Revision ID: b5c7a6c4a1c0
Revises: 8c2c51fa9b17
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b5c7a6c4a1c0"
down_revision = "8c2c51fa9b17"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "admin_config",
        sa.Column(
            "payment_alert_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "admin_config",
        sa.Column(
            "payment_alert_failure_threshold",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )
    op.add_column(
        "admin_config",
        sa.Column(
            "payment_reconcile_tolerance",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.alter_column(
        "admin_config",
        "payment_alert_window_minutes",
        server_default=None,
    )
    op.alter_column(
        "admin_config",
        "payment_alert_failure_threshold",
        server_default=None,
    )
    op.alter_column(
        "admin_config",
        "payment_reconcile_tolerance",
        server_default=None,
    )


def downgrade():
    op.drop_column("admin_config", "payment_reconcile_tolerance")
    op.drop_column("admin_config", "payment_alert_failure_threshold")
    op.drop_column("admin_config", "payment_alert_window_minutes")
