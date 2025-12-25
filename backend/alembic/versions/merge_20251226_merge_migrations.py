"""merge migrations

Revision ID: merge_20251226
Revises: 23456789abcd, 6f0fb3cfe4a5, f3c1a7b6d2f5
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_20251226'
down_revision = ('23456789abcd', '6f0fb3cfe4a5', 'f3c1a7b6d2f5')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
