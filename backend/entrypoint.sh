#!/bin/bash
set -e

# Wait for PostgreSQL to be ready quietly
while ! pg_isready -h postgres -p 5432 -U "${DB_USER:-virtualworld}" > /dev/null 2>&1; do
  sleep 1
done

# Initialize database with admin user and config, no extra output
python init_db.py

# Start the application (uvicorn will handle its own logging)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
