"""add_ip_access_control_tables

Revision ID: 64d91af0f0bc
Revises: 32850f9ed163
Create Date: 2025-12-26 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64d91af0f0bc'
down_revision = '32850f9ed163'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ip_blacklist',
        sa.Column('entry_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ip', sa.String(length=45), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('entry_id'),
        sa.UniqueConstraint('ip', name='uq_ip_blacklist_ip')
    )
    op.create_index('ix_ip_blacklist_ip', 'ip_blacklist', ['ip'])
    op.create_index('ix_ip_blacklist_expires_at', 'ip_blacklist', ['expires_at'])

    op.create_table(
        'ip_whitelist',
        sa.Column('entry_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('ip', sa.String(length=45), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('entry_id'),
        sa.UniqueConstraint('ip', name='uq_ip_whitelist_ip')
    )
    op.create_index('ix_ip_whitelist_ip', 'ip_whitelist', ['ip'])
    op.create_index('ix_ip_whitelist_expires_at', 'ip_whitelist', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_ip_whitelist_expires_at', table_name='ip_whitelist')
    op.drop_index('ix_ip_whitelist_ip', table_name='ip_whitelist')
    op.drop_table('ip_whitelist')

    op.drop_index('ix_ip_blacklist_expires_at', table_name='ip_blacklist')
    op.drop_index('ix_ip_blacklist_ip', table_name='ip_blacklist')
    op.drop_table('ip_blacklist')
