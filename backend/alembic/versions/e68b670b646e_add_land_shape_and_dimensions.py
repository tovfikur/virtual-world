"""add_land_shape_and_dimensions

Revision ID: e68b670b646e
Revises: 
Create Date: 2025-11-04 22:32:38.178747

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e68b670b646e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type for land shape (only if it doesn't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE landshape AS ENUM ('square', 'circle', 'triangle', 'rectangle');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Add shape column (default to square for existing lands)
    op.add_column('lands', sa.Column('shape', sa.Enum('square', 'circle', 'triangle', 'rectangle', name='landshape'), nullable=False, server_default='square'))

    # Add width column (default to 1 for single-unit lands)
    op.add_column('lands', sa.Column('width', sa.Integer(), nullable=False, server_default='1'))

    # Add height column (default to 1 for single-unit lands)
    op.add_column('lands', sa.Column('height', sa.Integer(), nullable=False, server_default='1'))

    # Add index for faster queries on land shapes
    op.create_index('idx_lands_shape', 'lands', ['shape'])


def downgrade() -> None:
    # Remove index
    op.drop_index('idx_lands_shape', table_name='lands')

    # Remove columns
    op.drop_column('lands', 'height')
    op.drop_column('lands', 'width')
    op.drop_column('lands', 'shape')

    # Drop enum type
    op.execute("DROP TYPE landshape")
