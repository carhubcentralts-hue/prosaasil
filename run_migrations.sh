#!/usr/bin/env bash
# Database Migration Runner for Docker
# Usage: ./run_migrations.sh or docker exec <container> /app/run_migrations.sh

set -e

echo "========================================="
echo "Database Migration Runner"
echo "========================================="

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Run migrations using Python module
export MIGRATION_MODE=1
export ASYNC_LOG_QUEUE=0

echo "Running migrations..."
python -m server.db_migrate

echo "========================================="
echo "✅ Migration completed"
echo "========================================="
