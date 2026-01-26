# Pre-Deployment Checklist - Migration Lock & Recording Worker Fix

## ✅ Changes Summary

This PR fixes critical production issues:
1. Migration lock timeouts causing system crashes
2. Multiple containers fighting over migration locks
3. Recording worker loop - jobs enqueued but not processed

---

## 🔍 Pre-Deployment Verification

### 1. Code Changes Review
- [x] `server/db_migrate.py` - Migration lock with retry logic
- [x] `server/app_factory.py` - Handle 'skip' gracefully
- [x] `server/tasks_recording.py` - Enhanced worker logging
- [x] `docker-compose.yml` - RUN_MIGRATIONS env vars
- [x] `docker-compose.prod.yml` - RUN_MIGRATIONS env vars

### 2. Testing
- [x] All tests pass (`test_migration_lock_timeout_fix.py`)
- [x] CodeQL security scan: 0 vulnerabilities
- [x] Code review feedback addressed

### 3. Documentation
- [x] Environment variables documented (`MIGRATION_LOCK_FIX_ENV_VARS.md`)
- [x] Hebrew summary created (`תיקון_מיגרציות_והקלטות_סיכום.md`)
- [x] Deployment checklist (this file)

---

## 🚀 Deployment Steps

### Step 1: Backup
```bash
# Backup database (optional but recommended)
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: Verify Environment Variables
Check that docker-compose files have correct settings:

**docker-compose.yml:**
```yaml
prosaas-api:
  environment:
    RUN_MIGRATIONS: "1"  # ✅ Only API runs migrations

worker:
  environment:
    RUN_MIGRATIONS: "0"  # ✅ Worker never runs migrations

prosaas-calls:
  environment:
    RUN_MIGRATIONS: "0"  # ✅ Calls never runs migrations
```

**docker-compose.prod.yml:**
```yaml
prosaas-api:
  environment:
    RUN_MIGRATIONS: "1"  # ✅ Only API runs migrations

worker:
  environment:
    RUN_MIGRATIONS: "0"  # ✅ Worker never runs migrations

prosaas-calls:
  environment:
    RUN_MIGRATIONS: "0"  # ✅ Calls never runs migrations
```

### Step 3: Deploy
```bash
# Pull latest code
git pull origin copilot/fix-migration-lock-timeout

# Stop all containers
docker-compose down

# Rebuild images (if using local builds)
docker-compose build

# Start services
docker-compose up -d

# Or for production:
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Step 4: Monitor Logs
```bash
# Watch API service logs for migration activity
docker-compose logs -f prosaas-api | grep -E "MIGRATION|LOCK"

# Watch worker logs for recording processing
docker-compose logs -f worker | grep -E "WORKER_|RECORDING"
```

### Step 5: Verify Migration Success
Look for these log patterns:

**✅ Success Pattern (API):**
```
🔧 MIGRATION CHECKPOINT: Starting apply_migrations()
✅ Set statement_timeout to 120s for migration connection
✅ Acquired migration lock
... migrations ...
✅ Released migration lock
```

**✅ Graceful Skip Pattern (other services):**
```
🚫 MIGRATIONS_DISABLED: RUN_MIGRATIONS is not set to '1'
   Migrations are disabled for this service
```

**✅ Worker Activity Pattern:**
```
🎯 [WORKER_PICKED] job_type=download_only call_sid=CA...
✅ [WORKER_SLOT_ACQUIRED] call_sid=CA... business_id=42
✅ [WORKER_DOWNLOAD_DONE] call_sid=CA... file=CA....mp3 bytes=123456
🔓 [WORKER_RELEASE_SLOT] call_sid=CA... business_id=42 reason=success
```

### Step 6: Verify Services Health
```bash
# Check all services are running
docker-compose ps

# Verify health endpoints
curl http://localhost/api/health
curl http://localhost/health
```

---

## 🔥 Rollback Plan (if needed)

If issues occur, rollback to previous version:

```bash
# Stop containers
docker-compose down

# Checkout previous commit
git checkout <previous-commit-hash>

# Restart
docker-compose up -d
```

**Note:** No database changes are destructive, so rollback is safe.

---

## 📊 Post-Deployment Verification

### Verify Migration Behavior
1. **Check only API runs migrations:**
   ```bash
   docker-compose logs prosaas-api | grep "MIGRATION CHECKPOINT"
   docker-compose logs worker | grep "MIGRATIONS_DISABLED"
   docker-compose logs prosaas-calls | grep "MIGRATIONS_DISABLED"
   ```

2. **Verify no lock conflicts:**
   ```bash
   # Should NOT see these errors:
   docker-compose logs | grep "Failed to acquire migration lock"
   docker-compose logs | grep "statement timeout"
   ```

### Verify Worker Processing
1. **Check worker is picking up jobs:**
   ```bash
   docker-compose logs worker | grep "WORKER_PICKED"
   ```

2. **Check recordings are being processed:**
   ```bash
   docker-compose logs worker | grep "WORKER_DOWNLOAD_DONE"
   ```

3. **Check slots are being released:**
   ```bash
   docker-compose logs worker | grep "WORKER_RELEASE_SLOT"
   ```

### Test Recording Playback
1. Make a test call
2. Wait for recording to process
3. Try to play recording in UI
4. Should see these logs:
   ```
   [WORKER_PICKED] job_type=download_only
   [WORKER_DOWNLOAD_DONE] bytes=...
   ```

---

## 🐛 Troubleshooting

### Issue: Container crashes with "Migration failed"
**Symptoms:**
```
❌ MIGRATION FAILED: ...
System cannot start with failed migrations
```

**Solution:**
1. Check if database is accessible:
   ```bash
   docker-compose exec prosaas-api python -c "from server.db import db; print(db.engine.url)"
   ```

2. Check lock timeout setting:
   ```bash
   # Increase wait time
   export MIGRATION_LOCK_WAIT_SECONDS=60
   docker-compose up -d
   ```

3. Ensure only one service has RUN_MIGRATIONS=1

---

### Issue: No migrations running
**Symptoms:**
- Database schema outdated
- No migration logs in any service

**Solution:**
1. Verify at least one service has RUN_MIGRATIONS=1:
   ```bash
   docker-compose config | grep -A5 prosaas-api | grep RUN_MIGRATIONS
   ```

2. Check API service logs:
   ```bash
   docker-compose logs prosaas-api | grep MIGRATION
   ```

---

### Issue: Worker not processing recordings
**Symptoms:**
- No [WORKER_PICKED] logs
- Recordings stuck in "processing" state

**Solution:**
1. Verify worker is running:
   ```bash
   docker-compose ps worker
   ```

2. Check worker command:
   ```bash
   docker-compose exec worker ps aux | grep worker
   ```

3. Verify queue has jobs:
   ```bash
   docker-compose exec worker python -c "
   import os
   import redis
   r = redis.from_url(os.getenv('REDIS_URL'))
   from server.tasks_recording import RECORDING_QUEUE
   print(f'Queue size: {RECORDING_QUEUE.qsize()}')
   "
   ```

---

### Issue: Multiple containers trying to run migrations
**Symptoms:**
```
⚠️ Another process is running migrations - waiting...
⚠️ MIGRATION CHECKPOINT: Could not acquire lock in time
```

**Solution:**
Set RUN_MIGRATIONS=0 for all services except prosaas-api:
```yaml
worker:
  environment:
    RUN_MIGRATIONS: "0"

prosaas-calls:
  environment:
    RUN_MIGRATIONS: "0"
```

---

## 📈 Success Metrics

After successful deployment, you should see:

✅ **Zero migration lock timeout errors**
- No "statement timeout" in logs
- No "Failed to acquire migration lock" errors

✅ **Single migration runner**
- Only prosaas-api logs "Running migrations"
- Other services log "MIGRATIONS_DISABLED"

✅ **Active worker processing**
- Regular [WORKER_PICKED] logs
- [WORKER_DOWNLOAD_DONE] logs matching recordings
- [WORKER_RELEASE_SLOT] logs showing cleanup

✅ **Recording playback works**
- Users can play recordings in UI
- No infinite "loading" state
- Recordings download within 10 seconds

---

## 🎯 Performance Expectations

### Migration Lock Acquisition
- **Immediate success:** < 1 second (typical)
- **With contention:** < 30 seconds (max wait time)
- **Graceful skip:** If lock busy after 30s, container starts anyway

### Worker Processing
- **Job pickup:** Immediate (no delay)
- **Download time:** 2-10 seconds per recording
- **Slot release:** Immediate after download

### System Startup
- **API service:** 20-40 seconds (with migrations)
- **Other services:** 10-20 seconds (skip migrations)
- **Overall system:** ~1 minute ready

---

## 🔒 Security Verification

Verify no sensitive data in logs:
```bash
# Should NOT contain full file paths
docker-compose logs worker | grep "/app/server/recordings"

# Should NOT contain database connection details
docker-compose logs | grep "postgresql://"

# Should NOT contain detailed error stack traces
docker-compose logs worker | grep -A10 "WORKER_JOB_FAILED"
```

All logs should be sanitized ✅

---

## 📞 Support

If issues persist after following this checklist:
1. Capture full logs: `docker-compose logs > deployment_logs.txt`
2. Check service status: `docker-compose ps`
3. Review error patterns in logs
4. Contact team with logs and error details

---

**Deployment Checklist Complete** ✅

Ready for production deployment!
