"""Create unified transaction audit view

Revision ID: 011
Revises: 010
Create Date: 2025-12-26 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure transactiontype enum supports biome trading.
    # Postgres requires enum additions to be COMMITTED before they can be used.
    with op.get_context().autocommit_block():
        op.execute("""
        DO $$ BEGIN
            ALTER TYPE transactiontype ADD VALUE 'BIOME_BUY';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """)
        op.execute("""
        DO $$ BEGIN
            ALTER TYPE transactiontype ADD VALUE 'BIOME_SELL';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """)

    # Create unified view combining marketplace and biome transactions
    op.execute('''
    CREATE VIEW v_unified_transactions AS
    SELECT 
        transaction_id,
        buyer_id,
        seller_id,
        land_id,
        listing_id,
        transaction_type,
        amount_bdt,
        status,
        platform_fee_bdt,
        gateway_fee_bdt,
        gateway_name,
        gateway_transaction_id,
        completed_at,
        created_at,
        biome,
        shares,
        price_per_share_bdt,
        CASE 
            WHEN transaction_type IN ('BIOME_BUY', 'BIOME_SELL') THEN 'biome'
            WHEN transaction_type IN ('BUY_NOW', 'FIXED_PRICE', 'AUCTION', 'TRANSFER') THEN 'marketplace'
            WHEN transaction_type = 'TOPUP' THEN 'wallet'
            ELSE 'unknown'
        END AS transaction_source
    FROM transactions
    ORDER BY created_at DESC
    ''')


def downgrade() -> None:
    # Drop the view
    op.execute('DROP VIEW IF EXISTS v_unified_transactions')
