"""add_admin_panel_tables

Revision ID: c5fdfb72b9e5
Revises: 4bb0e68e56f8
Create Date: 2025-11-05 02:25:41.258723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5fdfb72b9e5'
down_revision = '4bb0e68e56f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create bans table
    op.create_table(
        'bans',
        sa.Column('ban_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('banned_by', sa.UUID(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('ban_type', sa.String(20), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['banned_by'], ['users.user_id']),
        sa.PrimaryKeyConstraint('ban_id')
    )
    op.create_index('idx_bans_user_id', 'bans', ['user_id'])
    op.create_index('idx_bans_is_active', 'bans', ['is_active'])

    # Create announcements table
    op.create_table(
        'announcements',
        sa.Column('announcement_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('target_audience', sa.String(50), nullable=True),
        sa.Column('display_location', sa.String(20), nullable=True),
        sa.Column('start_date', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('end_date', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id']),
        sa.PrimaryKeyConstraint('announcement_id')
    )
    op.create_index('idx_announcements_active', 'announcements', ['start_date', 'end_date'])

    # Create reports table
    op.create_table(
        'reports',
        sa.Column('report_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reporter_id', sa.UUID(), nullable=False),
        sa.Column('reported_user_id', sa.UUID(), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.UUID(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('assigned_to', sa.UUID(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['reported_user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.user_id']),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index('idx_reports_status', 'reports', ['status'])
    op.create_index('idx_reports_created_at', 'reports', ['created_at'])

    # Create feature_flags table
    op.create_table(
        'feature_flags',
        sa.Column('flag_id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('flag_name', sa.String(100), nullable=False, unique=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['updated_by'], ['users.user_id']),
        sa.PrimaryKeyConstraint('flag_id')
    )

    # Add columns to users table
    op.add_column('users', sa.Column('is_suspended', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('suspension_reason', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('suspended_until', sa.TIMESTAMP(timezone=True), nullable=True))

    # Add columns to admin_config table
    op.add_column('admin_config', sa.Column('max_lands_per_user', sa.Integer(), nullable=True))
    op.add_column('admin_config', sa.Column('max_listings_per_user', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('admin_config', sa.Column('auction_bid_increment', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('admin_config', sa.Column('enable_registration', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove columns from admin_config
    op.drop_column('admin_config', 'enable_registration')
    op.drop_column('admin_config', 'auction_bid_increment')
    op.drop_column('admin_config', 'max_listings_per_user')
    op.drop_column('admin_config', 'max_lands_per_user')

    # Remove columns from users
    op.drop_column('users', 'suspended_until')
    op.drop_column('users', 'suspension_reason')
    op.drop_column('users', 'is_suspended')

    # Drop tables
    op.drop_table('feature_flags')
    op.drop_index('idx_reports_created_at', 'reports')
    op.drop_index('idx_reports_status', 'reports')
    op.drop_table('reports')
    op.drop_index('idx_announcements_active', 'announcements')
    op.drop_table('announcements')
    op.drop_index('idx_bans_is_active', 'bans')
    op.drop_index('idx_bans_user_id', 'bans')
    op.drop_table('bans')
