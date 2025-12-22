#!/bin/bash
set -e

# Wait for PostgreSQL to be ready quietly
while ! pg_isready -h postgres -p 5432 -U "${DB_USER:-virtualworld}" > /dev/null 2>&1; do
  sleep 1
done

# Create tables if they don't exist (for fresh database), without extra output
python - << 'PY'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.config import settings

# Import all models to register them with Base.metadata
from app.models.user import User
from app.models.land import Land
from app.models.admin_config import AdminConfig
from app.models.transaction import Transaction
from app.models.instrument import Instrument
from app.models.order import Order
from app.models.trade import Trade
from app.models.market_status import MarketStatus


async def create_tables():
    engine = create_async_engine(str(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


asyncio.run(create_tables())
PY

# Mark migrations as applied (stamp head) quietly
alembic stamp head

# Initialize database with admin user and config, no extra output
python init_db.py

# Start the application (uvicorn will handle its own logging)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
