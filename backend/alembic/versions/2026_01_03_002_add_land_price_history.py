"""add land price history table

Revision ID: 2026_01_03_002
Revises: fec18c323805
Create Date: 2026-01-03 16:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_01_03_002'
down_revision = 'fec18c323805'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'land_price_history',
        sa.Column('history_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('land_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('previous_owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('new_owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price_bdt', sa.Integer(), nullable=False),
        sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['land_id'], ['lands.land_id'], ),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.listing_id'], ),
        sa.ForeignKeyConstraint(['new_owner_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['previous_owner_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.transaction_id'], ),
        sa.PrimaryKeyConstraint('history_id')
    )
    op.create_index('idx_land_price_history_land', 'land_price_history', ['land_id'])
    op.create_index('idx_land_price_history_created', 'land_price_history', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_land_price_history_created', table_name='land_price_history')
    op.drop_index('idx_land_price_history_land', table_name='land_price_history')
    op.drop_table('land_price_history')
