"""Add biome trading fields to transactions table

Revision ID: 009
Revises: 008
Create Date: 2025-12-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make land_id and seller_id nullable for biome trades
    op.alter_column('transactions', 'land_id',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=True)
    op.alter_column('transactions', 'seller_id',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=True)
    
    # Add biome trading fields
    op.add_column('transactions', sa.Column('biome', sa.String(50), nullable=True))
    op.add_column('transactions', sa.Column('shares', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('price_per_share_bdt', sa.Integer(), nullable=True))
    
    # Create index on biome for faster queries
    op.create_index('idx_transactions_biome', 'transactions', ['biome'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_transactions_biome', table_name='transactions')
    
    # Remove biome trading columns
    op.drop_column('transactions', 'price_per_share_bdt')
    op.drop_column('transactions', 'shares')
    op.drop_column('transactions', 'biome')
    
    # Make land_id and seller_id non-nullable again
    op.alter_column('transactions', 'seller_id',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=False)
    op.alter_column('transactions', 'land_id',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=False)
