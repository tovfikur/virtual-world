"""add biome trading tables

Revision ID: 1de27dadc797
Revises: 7f5c1d3c0d6b
Create Date: 2025-12-25 12:49:01.590373

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1de27dadc797'
down_revision = '7f5c1d3c0d6b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reuse existing biome enum created by earlier migrations
    biome_enum = postgresql.ENUM(
        'ocean', 'beach', 'plains', 'forest', 'desert', 'mountain', 'snow',
        name='biome',
        create_type=False,
        validate_strings=True
    )

    biometransactiontype_enum = sa.Enum(
        'buy', 'sell',
        name='biometransactiontype'
    )

    # biome_markets
    op.create_table(
        'biome_markets',
        sa.Column('biome', biome_enum, nullable=False),
        sa.Column('market_cash_bdt', sa.Integer(), nullable=False),
        sa.Column('attention_score', sa.Float(), nullable=False),
        sa.Column('share_price_bdt', sa.Float(), nullable=False),
        sa.Column('total_shares', sa.Integer(), nullable=False),
        sa.Column('last_redistribution', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('biome')
    )
    op.create_index('idx_biome_markets_biome', 'biome_markets', ['biome'], unique=True)
    op.create_index('idx_biome_markets_updated', 'biome_markets', ['updated_at'], unique=False)

    # biome_holdings
    op.create_table(
        'biome_holdings',
        sa.Column('holding_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('biome', biome_enum, nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('average_buy_price_bdt', sa.Float(), nullable=False),
        sa.Column('total_invested_bdt', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['biome'], ['biome_markets.biome'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('holding_id'),
        sa.UniqueConstraint('user_id', 'biome', name='idx_biome_holdings_user_biome'),
        sa.CheckConstraint('shares >= 0', name='check_positive_shares')
    )
    op.create_index('idx_biome_holdings_user', 'biome_holdings', ['user_id'], unique=False)

    # biome_transactions
    op.create_table(
        'biome_transactions',
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('biome', biome_enum, nullable=False),
        sa.Column('type', biometransactiontype_enum, nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('price_per_share_bdt', sa.Float(), nullable=False),
        sa.Column('total_amount_bdt', sa.Integer(), nullable=False),
        sa.Column('realized_gain_bdt', sa.Float(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['biome'], ['biome_markets.biome'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('transaction_id')
    )
    op.create_index('idx_biome_transactions_user', 'biome_transactions', ['user_id', 'executed_at'], unique=False)
    op.create_index('idx_biome_transactions_biome', 'biome_transactions', ['biome', 'executed_at'], unique=False)
    op.create_index('idx_biome_transactions_type', 'biome_transactions', ['type'], unique=False)

    # biome_price_history
    op.create_table(
        'biome_price_history',
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('biome', biome_enum, nullable=False),
        sa.Column('price_bdt', sa.Float(), nullable=False),
        sa.Column('market_cash_bdt', sa.Integer(), nullable=False),
        sa.Column('attention_score', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['biome'], ['biome_markets.biome'], ),
        sa.PrimaryKeyConstraint('record_id')
    )
    op.create_index('idx_biome_price_history_biome_time', 'biome_price_history', ['biome', 'timestamp'], unique=False)
    op.create_index('idx_biome_price_history_timestamp', 'biome_price_history', ['timestamp'], unique=False)

    # attention_scores
    op.create_table(
        'attention_scores',
        sa.Column('score_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('biome', biome_enum, nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['biome'], ['biome_markets.biome'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('score_id'),
        sa.UniqueConstraint('user_id', 'biome', name='idx_attention_scores_user_biome')
    )
    op.create_index('idx_attention_scores_biome', 'attention_scores', ['biome'], unique=False)
    op.create_index('idx_attention_scores_updated', 'attention_scores', ['updated_at'], unique=False)



def downgrade() -> None:
    op.drop_index('idx_attention_scores_updated', table_name='attention_scores')
    op.drop_index('idx_attention_scores_biome', table_name='attention_scores')
    op.drop_constraint('idx_attention_scores_user_biome', 'attention_scores', type_='unique')
    op.drop_table('attention_scores')

    op.drop_index('idx_biome_price_history_timestamp', table_name='biome_price_history')
    op.drop_index('idx_biome_price_history_biome_time', table_name='biome_price_history')
    op.drop_table('biome_price_history')

    op.drop_index('idx_biome_transactions_type', table_name='biome_transactions')
    op.drop_index('idx_biome_transactions_biome', table_name='biome_transactions')
    op.drop_index('idx_biome_transactions_user', table_name='biome_transactions')
    op.drop_table('biome_transactions')

    op.drop_index('idx_biome_holdings_user', table_name='biome_holdings')
    op.drop_constraint('idx_biome_holdings_user_biome', 'biome_holdings', type_='unique')
    op.drop_table('biome_holdings')

    op.drop_index('idx_biome_markets_updated', table_name='biome_markets')
    op.drop_index('idx_biome_markets_biome', table_name='biome_markets')
    op.drop_table('biome_markets')

    biometransactiontype_enum = sa.Enum('buy', 'sell', name='biometransactiontype')
    biometransactiontype_enum.drop(op.get_bind(), checkfirst=True)
