# Database Migration Guide

## Problem Fixed
Previously, running `apply_migrations()` would hang indefinitely because:
- `create_app()` started background threads, warmup jobs, and eventlet workers
- These required eventlet monkey patching which conflicted with SQLAlchemy
- No logging checkpoints made debugging impossible

## Solution
Migrations now run in **MIGRATION_MODE** which:
- ✅ Skips ALL background threads and workers
- ✅ Disables eventlet-based async logging
- ✅ Uses minimal Flask app (just SQLAlchemy + DB config)
- ✅ Adds explicit logging checkpoints throughout
- ✅ Creates tables from metadata if database is empty
- ✅ Exits cleanly after completion

## Running Migrations

### Local Development
```bash
# Set environment variable
export DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Run migrations
python -m server.db_migrate
```

### Docker Production
```bash
# Method 1: Using the script (recommended)
docker exec prosaasil-backend /app/run_migrations.sh

# Method 2: Direct Python command
docker exec prosaasil-backend python -m server.db_migrate

# Method 3: Interactive shell
docker exec -it prosaasil-backend bash
python -m server.db_migrate
exit
```

### Docker Compose
```bash
# If using docker-compose
docker-compose exec backend python -m server.db_migrate
```

### Manual Docker Command
```bash
# Run migrations in a one-off container
docker run --rm \
  -e DATABASE_URL=postgresql://user:pass@host:5432/dbname \
  -e MIGRATION_MODE=1 \
  prosaasil-backend:latest \
  python -m server.db_migrate
```

## What Happens During Migration

The migration runner will:

1. **Set MIGRATION_MODE=1** - Disables all background workers
2. **Create minimal Flask app** - Only SQLAlchemy + DB config
3. **Check if DB is empty** - If yes, creates all tables from metadata
4. **Run incremental migrations** - Adds columns, indexes, tables as needed
5. **Verify data protection** - Ensures no FAQs or leads are deleted
6. **Commit changes** - Saves migrations to database
7. **Exit cleanly** - Returns 0 on success, 1 on failure

## Expected Output

```
🔧 MIGRATION CHECKPOINT: ================================================================================
🔧 MIGRATION CHECKPOINT: DATABASE MIGRATION RUNNER - Standalone Mode
🔧 MIGRATION CHECKPOINT: ================================================================================
🔧 MIGRATION CHECKPOINT: Database: postgresql://***
🔧 MIGRATION CHECKPOINT: Creating minimal Flask app context...
🔧 MIGRATION CHECKPOINT: Running migrations within app context...
🔧 MIGRATION CHECKPOINT: Starting apply_migrations()
🔧 MIGRATION CHECKPOINT: Checking if database is completely empty...
🔧 MIGRATION CHECKPOINT: Found 0 existing tables: []...
🔧 MIGRATION CHECKPOINT: Database is empty - creating all tables from SQLAlchemy metadata
🔧 MIGRATION CHECKPOINT: ✅ All tables created successfully from metadata
🔧 MIGRATION CHECKPOINT: Starting data protection layer 1 - counting existing data
🔧 MIGRATION CHECKPOINT: Committing migrations to database...
🔧 MIGRATION CHECKPOINT: ✅ Applied 1 migrations: create_all_tables_from_metadata...
🔧 MIGRATION CHECKPOINT: Starting data protection layer 3 - verifying no data loss
🔧 MIGRATION CHECKPOINT: ✅ Migration completed successfully!
🔧 MIGRATION CHECKPOINT: ================================================================================
🔧 MIGRATION CHECKPOINT: ✅ SUCCESS - Applied 1 migrations
🔧 MIGRATION CHECKPOINT: ================================================================================
```

## Troubleshooting

### Migration hangs or times out
- ❌ **DO NOT** run migrations from `wsgi.py` or after `eventlet.monkey_patch()`
- ✅ **USE** the standalone runner: `python -m server.db_migrate`

### Database connection error
```
❌ MIGRATION FAILED: connection to server at "localhost" failed
```
- Check DATABASE_URL is correctly set
- Verify database server is running
- Check network connectivity from container to database

### No output or silent failure
- The migration runner ALWAYS logs checkpoints
- If you see no output, check:
  - Python path is correct
  - DATABASE_URL is set
  - Stdout/stderr are not redirected to /dev/null

### Tables already exist
This is normal! The migration runner:
- Checks if tables exist before creating
- Only applies missing migrations
- Skips migrations that are already applied

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `MIGRATION_MODE` | Auto-set | 1 | Disables background workers |
| `ASYNC_LOG_QUEUE` | Auto-set | 0 | Disables eventlet logging |

## Architecture Notes

### Why MIGRATION_MODE is needed
1. Normal `create_app()` starts:
   - Background initialization thread
   - Service warmup (async)
   - Recording worker thread
   - WhatsApp session processor
   - Agent factory warmup
   - TTS pre-warming

2. These use eventlet which requires:
   - `eventlet.monkey_patch()` (from wsgi.py)
   - Green threads and async workers
   - WebSocket handling

3. SQLAlchemy doesn't work well with monkey patching
4. **Solution**: MIGRATION_MODE creates minimal app without any workers

### Files Modified
- `server/app_factory.py` - Added `create_minimal_app()` and MIGRATION_MODE checks
- `server/db_migrate.py` - Added checkpoints and `__main__` section
- `server/__main__.py` - Alternative entry point
- `run_migrations.sh` - Convenience script for Docker

## Integration with CI/CD

Add to your deployment pipeline:

```bash
# Build and push Docker image
docker build -f Dockerfile.backend -t prosaasil-backend:$BUILD_ID .
docker push prosaasil-backend:$BUILD_ID

# Run migrations before starting new containers
docker run --rm \
  -e DATABASE_URL=$DATABASE_URL \
  prosaasil-backend:$BUILD_ID \
  python -m server.db_migrate

# If migrations succeed, deploy new version
docker-compose up -d backend
```

## Security Notes
- Migrations run with same database credentials as app
- No sensitive data is logged (credentials are masked)
- Migration runner exits immediately - no lingering processes
- Failed migrations return exit code 1 (can stop deployment)
