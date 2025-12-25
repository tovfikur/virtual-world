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
    
    # Create index on the underlying table to improve view query performance
    op.create_index('idx_transactions_source', 'transactions', 
                   [sa.text("CASE WHEN transaction_type IN ('BIOME_BUY', 'BIOME_SELL') THEN 'biome' ELSE 'marketplace' END")])


def downgrade() -> None:
    # Drop the view and index
    op.drop_index('idx_transactions_source', table_name='transactions')
    op.execute('DROP VIEW IF EXISTS v_unified_transactions')
