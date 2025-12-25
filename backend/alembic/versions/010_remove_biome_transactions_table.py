"""Remove redundant biome_transactions table

Revision ID: 010
Revises: 009
Create Date: 2025-12-26 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_biome_transactions_user', table_name='biome_transactions')
    op.drop_index('idx_biome_transactions_biome', table_name='biome_transactions')
    op.drop_index('idx_biome_transactions_type', table_name='biome_transactions')
    
    # Drop the table
    op.drop_table('biome_transactions')
    
    # Drop biome_transaction_type enum if not used elsewhere
    op.execute('DROP TYPE IF EXISTS biome_transaction_type CASCADE')


def downgrade() -> None:
    # Recreate the enum
    op.execute('''
        CREATE TYPE biome_transaction_type AS ENUM (
            'buy',
            'sell'
        )
    ''')
    
    # Recreate the table
    op.create_table(
        'biome_transactions',
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('biome', sa.String(50), nullable=False),
        sa.Column('type', sa.Enum('buy', 'sell', name='biome_transaction_type'), nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('price_per_share_bdt', sa.Integer(), nullable=False),
        sa.Column('total_amount_bdt', sa.Integer(), nullable=False),
        sa.Column('realized_gain_bdt', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['biome'], ['biome_markets.biome'], ),
        sa.PrimaryKeyConstraint('transaction_id')
    )
    
    # Recreate indexes
    op.create_index('idx_biome_transactions_user', 'biome_transactions', ['user_id', 'created_at'])
    op.create_index('idx_biome_transactions_biome', 'biome_transactions', ['biome', 'created_at'])
    op.create_index('idx_biome_transactions_type', 'biome_transactions', ['type'])
