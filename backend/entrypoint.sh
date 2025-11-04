#!/bin/bash
set -e

echo "=========================================="
echo "Virtual Land World - Backend Startup"
echo "=========================================="
echo ""

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h postgres -p 5432 -U "${DB_USER:-virtualworld}" > /dev/null 2>&1; do
  sleep 1
done
echo "✓ PostgreSQL is ready!"
echo ""

# Create tables if they don't exist (for fresh database)
echo "⏳ Creating database tables..."
python -c "
import asyncio
from app.db.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

# Import all models to register them with Base.metadata
from app.models.user import User
from app.models.land import Land
from app.models.admin_config import AdminConfig
from app.models.transaction import Transaction

async def create_tables():
    engine = create_async_engine(str(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(create_tables())
print('✓ Tables created successfully!')
"
echo ""

# Mark migrations as applied (stamp head)
echo "⏳ Marking migrations as applied..."
alembic stamp head
echo "✓ Migrations marked as applied!"
echo ""

# Initialize database with admin user and config
echo "⏳ Initializing database..."
python init_db.py
echo ""

# Start the application
echo "=========================================="
echo "🚀 Starting FastAPI server..."
echo "=========================================="
echo ""
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
