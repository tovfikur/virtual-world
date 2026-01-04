"""ensure biome_land_markets table exists

Revision ID: r20260104_biome_land_market
Revises: r20260104_fix_buynow_defaults
Create Date: 2026-01-04 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "r20260104_biome_land_market"
down_revision = "r20260104_fix_buynow_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create biome_land_markets table if it is missing (fresh dev DBs)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS biome_land_markets (
            biome biome PRIMARY KEY,
            sold_lands_count INTEGER NOT NULL DEFAULT 0,
            average_price_bdt DOUBLE PRECISION NOT NULL DEFAULT 0,
            total_market_value_bdt INTEGER NOT NULL DEFAULT 0,
            last_transaction_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Ensure helpful indexes exist
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_biome_land_markets_biome ON biome_land_markets (biome)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_biome_land_markets_updated ON biome_land_markets (updated_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS biome_land_markets")
