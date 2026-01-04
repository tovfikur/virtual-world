"""disable listing cooldown for better UX

Revision ID: r20260104_disable_cooldown
Revises: r20260104_biome_land_market
Create Date: 2026-01-04 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "r20260104_disable_cooldown"
down_revision = "r20260104_biome_land_market"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set listing cooldown to 0 (disabled) for better user experience
    # Users can list multiple times without waiting
    op.execute(
        """
        UPDATE admin_config SET listing_cooldown_minutes = 0
        WHERE listing_cooldown_minutes = 5
        """
    )


def downgrade() -> None:
    # Restore 5-minute cooldown on downgrade
    op.execute(
        """
        UPDATE admin_config SET listing_cooldown_minutes = 5
        WHERE listing_cooldown_minutes = 0
        """
    )
