"""merge biome land market migration

Revision ID: fec18c323805
Revises: 2026_01_03_001, f4e8c9b2d5a1, merge_20251226
Create Date: 2026-01-03 15:55:01.378627

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fec18c323805'
down_revision = ('2026_01_03_001', 'f4e8c9b2d5a1', 'merge_20251226')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
