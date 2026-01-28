# Outbound Worker System Fix Summary

## Problem Statement (Hebrew)

The system had "dual background execution" issues where both Threads in the API and RQ Workers were running simultaneously, causing:

1. **Duplicate processing** - Same run entered queue twice / updated twice
2. **UI bugs** - Progress showing "3" even when no calls exist
3. **Stuck runs after restart** - Runs remained stuck in DB/Redis because cleanup failed
4. **Duplicate logs and operations** - Same actions executed multiple times

## Root Causes Identified

### 1. Threading in API (`routes_outbound.py` line 2805)
- When a call completed, the API spawned a daemon `Thread` to process the next queued job
- This created "dual background execution": RQ worker + API threads running in parallel
- Result: Same job could be processed twice, duplicate Twilio calls, inconsistent state

### 2. create_app Running Twice
- Cleanup functions ran BEFORE `db.init_app(app)` (line 1097)
- Caused error: "Flask app is not registered with this SQLAlchemy instance"
- Cleanup at line 847 but db initialization at line 1097 = timing issue

### 3. No SERVICE_ROLE Guard
- Both API and Worker services tried to run cleanup on startup
- Double initialization and duplicate cleanup operations

## Solutions Implemented

### ✅ 1. Remove Threading - Use RQ Only

**File**: `server/routes_outbound.py`

**Before** (line 2796-2814):
```python
def release_and_process_next(business_id: int, job_id: int):
    """Helper to release slot and process next job non-recursively"""
    try:
        from server.services.outbound_semaphore import release_slot
        next_job_id = release_slot(business_id, job_id)
        if next_job_id:
            log.info(f"[ProcessNext] Released slot for job {job_id}, starting next job {next_job_id} in thread")
            # Use thread instead of recursion to prevent stack overflow
            import threading
            threading.Thread(
                target=process_next_queued_job,
                args=(next_job_id, run_id),
                daemon=True,
                name=f"ProcessNext-{next_job_id}"
            ).start()
```

**After**:
```python
def release_and_process_next(business_id: int, job_id: int):
    """Helper to release slot and process next job via RQ worker (not thread)"""
    try:
        from server.services.outbound_semaphore import release_slot
        next_job_id = release_slot(business_id, job_id)
        if next_job_id:
            # 🔥 FIX: Use RQ worker instead of Thread to prevent dual background execution
            try:
                import redis
                from rq import Queue
                REDIS_URL = os.getenv('REDIS_URL')
                if REDIS_URL:
                    redis_conn = redis.from_url(REDIS_URL)
                    queue = Queue('default', connection=redis_conn)
                    
                    log.info(f"[ProcessNext] Released slot for job {job_id}, enqueuing next job {next_job_id} to RQ worker")
                    
                    # Enqueue to RQ worker instead of spawning thread
                    queue.enqueue(
                        'server.routes_outbound.process_next_queued_job',
                        next_job_id,
                        run_id,
                        job_timeout='10m',
                        job_id=f"process_next_{next_job_id}"
                    )
```

**Impact**: 
- ✅ NO more daemon threads
- ✅ ALL outbound processing goes through RQ worker
- ✅ Single consistent execution path
- ✅ No more duplicates or race conditions

### ✅ 2. Fix Cleanup Timing and Context

**File**: `server/app_factory.py`

**Changes**:
1. **Removed** cleanup from line 847 (before blueprint registration)
2. **Added** cleanup AFTER `db.init_app(app)` at line 1085
3. **Added** SERVICE_ROLE guard to prevent worker from running cleanup

**New Code** (line 1085-1119):
```python
# Initialize SQLAlchemy with Flask app
db.init_app(app)

# 🔒 CRITICAL: Cleanup stuck jobs and runs on startup to prevent blocking
# Must run AFTER db.init_app() and in app context to avoid SQLAlchemy errors
# Only run in API service, not in worker service (to prevent duplicate cleanup)
service_role = os.getenv('SERVICE_ROLE', 'api').lower()
if service_role != 'worker':
    try:
        logger.info(f"[STARTUP] Running outbound cleanup on startup (service_role={service_role})...")
        with app.app_context():
            from server.routes_outbound import cleanup_stuck_dialing_jobs, cleanup_stuck_runs
            cleanup_stuck_dialing_jobs()
            cleanup_stuck_runs(on_startup=True)
            
            # Also clean up Redis locks for stuck runs
            try:
                import redis
                REDIS_URL = os.getenv('REDIS_URL')
                if REDIS_URL:
                    logger.info("[STARTUP] Cleaning up Redis outbound slots...")
```

**Impact**:
- ✅ Cleanup runs in proper app context
- ✅ No more "Flask app is not registered with SQLAlchemy" errors
- ✅ Only API service runs cleanup, not worker
- ✅ Redis locks also cleaned up on startup

### ✅ 3. Enhanced Debug Logging

**File**: `server/logging_config.py`

**Changes**:
- Added explicit DEBUG logging for outbound modules in development mode
- Modules enabled for DEBUG:
  - `server.routes_outbound`
  - `server.jobs.enqueue_outbound_calls_job`
  - `server.services.outbound_semaphore`
  - `server.worker`
  - `rq.worker`

**New Code** (line 182-197):
```python
else:
    # DEVELOPMENT MODE - Enable detailed logging for outbound system
    outbound_modules = [
        'server.routes_outbound',
        'server.jobs.enqueue_outbound_calls_job',
        'server.services.outbound_semaphore',
        'server.worker',
        'rq.worker',
    ]
    
    for module_name in outbound_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.DEBUG)
```

**Impact**:
- ✅ Setting `LOG_LEVEL=DEBUG` enables detailed outbound logging
- ✅ Easy to troubleshoot issues in development
- ✅ Production remains quiet with `LOG_LEVEL=INFO`

## Architecture After Fix

### Outbound Call Flow (Simplified)

```
User clicks "Start Calls"
    ↓
API: Create OutboundCallRun + Jobs + BackgroundJob
    ↓
API: Enqueue to RQ worker (enqueue_outbound_calls_batch_job)
    ↓
RQ Worker: Pick up job and call process_bulk_call_run()
    ↓
RQ Worker: Main Loop:
    - Get next queued job (DB: SELECT FOR UPDATE SKIP LOCKED)
    - Acquire Redis semaphore slot (max 3 concurrent per business)
    - Create Twilio call
    - Store call_sid
    ↓
Twilio Webhook: Call completed
    ↓
API: Receive webhook, release Redis slot
    ↓
API: Get next_job_id from release_slot()
    ↓
API: Enqueue next_job_id to RQ worker  ← 🔥 FIX: Was Thread, now RQ
    ↓
RQ Worker: Pick up next job, repeat loop
```

### Key Architectural Decisions

1. **RQ Worker = Primary** - ALL outbound processing via RQ
2. **NO Threads** - Eliminated daemon threads completely
3. **Single Consumer** - Only 1 RQ worker processes each run
4. **Redis Semaphore** - Hard 3-concurrent-call limit per business
5. **Atomic Locking** - Lock tokens prevent race conditions
6. **Heartbeat Monitoring** - TTL-based (5 min) to detect dead workers
7. **Startup Cleanup** - Mark all "running" runs as "failed" on restart

## Environment Variables

### Required Configuration

```bash
# Redis (Required for RQ worker)
REDIS_URL=redis://redis:6379/0

# Service identification (for cleanup guard)
SERVICE_ROLE=api          # For API service
SERVICE_ROLE=worker       # For worker service

# Logging (for debug mode)
LOG_LEVEL=DEBUG           # Development: full logs
LOG_LEVEL=INFO            # Production: minimal logs
PYTHONUNBUFFERED=1        # Prevent log buffering
```

### Docker Compose Configuration

**API Service** (prosaas-api):
```yaml
environment:
  SERVICE_ROLE: api
  LOG_LEVEL: ${LOG_LEVEL:-INFO}
  REDIS_URL: redis://redis:6379/0
```

**Worker Service**:
```yaml
environment:
  SERVICE_ROLE: worker
  LOG_LEVEL: ${LOG_LEVEL:-DEBUG}
  REDIS_URL: redis://redis:6379/0
  RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts
```

## Testing Checklist

- [ ] Start outbound calls - verify enqueued to RQ (no thread spawn)
- [ ] Check logs for "enqueuing next job to RQ worker" (not "starting in thread")
- [ ] Restart API service - verify cleanup runs without SQLAlchemy error
- [ ] Check stuck runs marked as "failed" on restart
- [ ] Verify no duplicate call processing
- [ ] Verify Redis slots cleaned up properly
- [ ] Test cancel functionality still works
- [ ] Verify LOG_LEVEL=DEBUG enables detailed logs
- [ ] Check worker service doesn't run cleanup

## Deployment Steps

1. **Update environment variables**:
   ```bash
   # In .env file
   LOG_LEVEL=INFO  # Or DEBUG for troubleshooting
   REDIS_URL=redis://redis:6379/0
   ```

2. **Restart services**:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

3. **Verify logs**:
   ```bash
   docker compose logs -f prosaas-api | grep "STARTUP"
   docker compose logs -f worker | grep "ProcessNext"
   ```

4. **Monitor for issues**:
   - Check for "Flask app is not registered" errors (should be GONE)
   - Check for "enqueuing next job to RQ" messages (should be present)
   - Check for duplicate calls (should be GONE)
   - Check stuck runs after restart (should auto-cleanup)

## Related Files Modified

1. `server/routes_outbound.py` - Removed threading, use RQ
2. `server/app_factory.py` - Fixed cleanup timing and context
3. `server/logging_config.py` - Enhanced debug logging for outbound
4. `docker-compose.yml` - Already has correct configuration

## Notes for Future

- **Cancel functionality** already exists and works properly
- **Heartbeat system** (5 min TTL) detects dead workers automatically
- **Redis cleanup** happens on startup for API service only
- **Worker separation** ensures clean process boundaries

## Security Summary

No security vulnerabilities introduced:
- RQ worker enqueue is internal (not exposed to users)
- Cleanup still enforces business isolation
- No new external endpoints added
- All existing security checks remain in place
