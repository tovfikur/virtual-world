"""add parcel system

Revision ID: f9d2c4a1b8e3
Revises: c5fdfb72b9e5
Create Date: 2025-12-17 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f9d2c4a1b8e3'
down_revision = 'c5fdfb72b9e5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrate marketplace from single-land listings to parcel system.

    Steps:
    1. Cancel all existing active listings
    2. Reset for_sale on all lands
    3. Create listing_lands junction table
    4. Drop land_id from listings table
    """

    # Step 1: Cancel all existing active listings
    op.execute("""
        UPDATE listings
        SET status = 'CANCELLED'::listingstatus
        WHERE status = 'ACTIVE'::listingstatus
    """)

    # Step 2: Reset for_sale on all lands
    op.execute("""
        UPDATE lands
        SET for_sale = FALSE
    """)

    # Step 3: Create listing_lands junction table
    op.create_table(
        'listing_lands',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('land_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.listing_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['land_id'], ['lands.land_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('listing_id', 'land_id', name='uq_listing_land')
    )

    # Create indexes
    op.create_index('idx_listing_lands_listing', 'listing_lands', ['listing_id'])
    op.create_index('idx_listing_lands_land', 'listing_lands', ['land_id'])

    # Step 4: Drop land_id column from listings
    op.drop_constraint('listings_land_id_fkey', 'listings', type_='foreignkey')
    op.drop_index('ix_listings_land_id', table_name='listings')
    op.drop_column('listings', 'land_id')


def downgrade():
    """
    Rollback parcel system changes.

    Warning: This will lose all listing_lands data!
    """

    # Re-add land_id to listings (but can't restore data)
    op.add_column('listings', sa.Column('land_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_listings_land_id', 'listings', ['land_id'])
    op.create_foreign_key('listings_land_id_fkey', 'listings', 'lands', ['land_id'], ['land_id'])

    # Drop listing_lands table
    op.drop_index('idx_listing_lands_land', table_name='listing_lands')
    op.drop_index('idx_listing_lands_listing', table_name='listing_lands')
    op.drop_table('listing_lands')
