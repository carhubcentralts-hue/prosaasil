# Must-Have Verification Before Production Deployment

This document addresses the 3 critical concerns raised in PR review:

## ✅ 1. count_active_outbound_calls is DB-based SSOT (Not In-Memory)

**Location**: `server/services/call_limiter.py` lines 48-66

**Verification**:
```python
def count_active_outbound_calls(business_id: int) -> int:
    """Count active outbound calls for a business"""
    count = CallLog.query.filter(
        CallLog.business_id == business_id,  # ← DB query, not in-memory
        CallLog.direction == 'outbound',
        CallLog.status.in_(ACTIVE_CALL_STATUSES),
        ...
    ).count()
    return count
```

**Why it's correct**:
- Uses `CallLog.query` (SQLAlchemy DB query)
- Works across all workers/pods/instances
- True SSOT - all processes see the same data
- No in-memory dicts or process-local state

**Test**:
```bash
# Start 2 worker processes for same business
# Both will query the same CallLog table
# Each will see the other's active calls
# Total will never exceed 3 per business
```

---

## ✅ 2. Slot Filling is Atomic (No Race Conditions)

**Location**: `server/routes_outbound.py` lines 1757-1776

**Verification**:
```python
# Step 1: Generate unique lock token
lock_token = str(uuid.uuid4())

# Step 2: Atomic UPDATE with lock acquisition
result = db.session.execute(text("""
    UPDATE outbound_call_jobs 
    SET status='dialing', 
        dial_started_at=NOW(), 
        dial_lock_token=:lock_token
    WHERE id=:job_id 
        AND status='queued'           # ← Only if still queued
        AND twilio_call_sid IS NULL   # ← Only if not dialed
        AND dial_lock_token IS NULL   # ← Only if not locked
"""), {"job_id": next_job.id, "lock_token": lock_token})

db.session.commit()

# Step 3: Check if we won the lock
if result.rowcount == 0:
    # Someone else got it, skip
    continue

# Step 4: Only now create the Twilio call
```

**Why it's correct**:
- Uses DB-level atomic UPDATE (not SELECT then UPDATE)
- Multiple workers can try to lock same job
- Only ONE will succeed (rowcount=1)
- Others will get rowcount=0 and skip
- No FOR UPDATE needed because UPDATE itself is atomic with WHERE conditions

**Test**:
```bash
# Run 2 workers simultaneously on same queue
# Both will try to lock jobs
# Each job will only be locked by one worker
# No duplicates, no race conditions
```

---

## ✅ 3. public_host Always Available (Fail Fast)

**Location**: `server/routes_outbound.py` lines 94-119

**Changes Made**:
```python
def get_public_host() -> str:
    """Get public host for webhook URLs - FAIL FAST if missing"""
    
    # Try PUBLIC_HOST env var
    public_host = os.environ.get('PUBLIC_HOST', '...')
    if public_host:
        return public_host
    
    # Try Replit domains
    replit_host = os.environ.get('REPLIT_DEV_DOMAIN') or ...
    if replit_host:
        return replit_host
    
    # Localhost only in development
    if os.environ.get('FLASK_ENV') == 'development':
        log.warning("⚠️ Using localhost for webhooks")
        return 'localhost'
    
    # FAIL FAST in production
    error_msg = "❌ CRITICAL: No public host configured!"
    log.error(error_msg)
    raise RuntimeError(error_msg)  # ← Stops execution immediately
```

**Worker Verification** (lines 1734-1747, 1948-1961):
```python
try:
    host = get_public_host()
    log.info(f"[BulkCall] Run {run_id}: public_host={host}")
except RuntimeError as e:
    log.error(f"[BulkCall] Run {run_id} FAILED: {e}")
    run.status = "failed"
    run.last_error = "No public host configured"
    db.session.commit()
    return  # Exit immediately
```

**Why it's correct**:
- Raises RuntimeError if no host (not silent fallback)
- Worker catches exception and marks run as failed
- Clear error message in logs
- No silent failures with broken callbacks

**Test**:
```bash
# Unset PUBLIC_HOST
unset PUBLIC_HOST
unset REPLIT_DEV_DOMAIN

# Try to start bulk call
# Should see in logs:
# ❌ CRITICAL: No public host configured!
# Run marked as failed immediately
```

---

## Manual Integration Test (10 minutes)

### Test 1: Single Business, 20 Leads
```bash
# Start bulk call with 20 leads
# Watch logs:
tail -f logs/app.log | grep -i "bulkcall\|active"

# Expected in logs:
# ✅ [BulkCall] Run 123: public_host=myapp.com
# ✅ Started call for lead=1
# ✅ Started call for lead=2
# ✅ Started call for lead=3
# ⏸️  Business 1 at max (3/3), waiting...
# ✅ Call completed for lead=1
# ✅ Started call for lead=4
```

### Test 2: Verify Max 3 Concurrent
```sql
-- Run repeatedly during bulk call
SELECT COUNT(*) as active_count
FROM call_log
WHERE business_id = 1
  AND direction = 'outbound'
  AND status IN ('initiated', 'ringing', 'in-progress')
  AND created_at > NOW() - INTERVAL '30 minutes';

-- Expected: active_count <= 3 always
```

### Test 3: Mixed Direct + Bulk Calls
```bash
# 1. Start bulk call with 50 leads (will queue 50)
# 2. Immediately start 1 direct call via API
# 3. Watch active count

# Expected behavior:
# - Bulk queue sees: business_active=1 (from direct call)
# - Bulk only starts 2 more calls (3 - 1 = 2)
# - Total active: 3 (1 direct + 2 bulk) ✅
```

### Test 4: Multiple Workers (Race Condition Test)
```bash
# Start 2 worker processes
python -m gunicorn -w 2 ...

# Start bulk call with 100 leads
# Both workers will process the queue

# Check for duplicates:
SELECT lead_id, COUNT(*) as call_count
FROM outbound_call_jobs
WHERE run_id = 123
GROUP BY lead_id
HAVING COUNT(*) > 1;

-- Expected: Empty result (no duplicates)
```

### Test 5: Missing Host (Fail Fast)
```bash
# Temporarily remove PUBLIC_HOST
export PUBLIC_HOST=""

# Start bulk call
# Expected:
# ❌ [BulkCall] Run 123 FAILED: No public host configured
# Run status: 'failed'
# No calls created
```

---

## Production Deployment Checklist

Before deploying to production, verify:

- [ ] `PUBLIC_HOST` environment variable is set correctly
- [ ] Test with 20 leads: max 3 concurrent calls
- [ ] Test with mixed direct + bulk: total respects limit
- [ ] Test with 2 workers: no duplicate calls
- [ ] Check logs show `public_host=...` at start
- [ ] Verify `count_active_outbound_calls()` uses DB
- [ ] Verify atomic UPDATE with lock_token works
- [ ] Test fail-fast behavior with missing host

---

## Key Architecture Summary

### SSOT (Single Source of Truth)
✅ **Call Counting**: DB-based via `CallLog.query` (not in-memory)
✅ **Call Limiting**: `call_limiter.py` used by all workers/routes
✅ **Atomic Locking**: DB-level UPDATE with WHERE conditions

### No Race Conditions
✅ **Slot Selection**: Atomic UPDATE with lock_token
✅ **Duplicate Prevention**: Multiple WHERE conditions (status, sid, token)
✅ **Multi-Worker Safe**: Each worker queries same DB, sees others' locks

### Fail Fast
✅ **Missing Host**: Raises RuntimeError, marks run as failed
✅ **Clear Errors**: Detailed error messages in logs
✅ **No Silent Failures**: Worker exits immediately on critical errors

---

## References

- Call limiter SSOT: `server/services/call_limiter.py:48-66`
- Atomic locking: `server/routes_outbound.py:1757-1776`
- Fail-fast host: `server/routes_outbound.py:94-119`
- Worker verification: `server/routes_outbound.py:1734-1747, 1948-1961`
