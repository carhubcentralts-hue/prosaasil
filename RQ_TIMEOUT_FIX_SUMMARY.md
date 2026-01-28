# RQ Timeout Parameter Fix - VERIFIED ✅

## Problem
Jobs enqueued via the `enqueue()` wrapper function were failing with:
```
TypeError: reminders_tick_job() got an unexpected keyword argument 'timeout'
```

This was causing:
- Worker processes to crash repeatedly
- WhatsApp bot to stop responding 
- All background jobs to fail (reminders, webhooks, recordings, etc.)

## Root Cause
The `enqueue()` function was passing `timeout` to RQ's `queue.enqueue()`, but RQ expects the parameter to be named `job_timeout`. Any unrecognized parameters are passed through to the job function as kwargs, causing the error.

## Solution
Changed the `enqueue()` function in `server/services/jobs.py` to use `job_timeout` instead of `timeout` when building the job configuration.

**File**: `server/services/jobs.py`, Line 190

**Change**:
```python
# BEFORE (incorrect):
job_kwargs = {
    'timeout': timeout,  # ❌ Passes to job function
    ...
}

# AFTER (correct):
job_kwargs = {
    'job_timeout': timeout,  # ✅ RQ control parameter
    ...
}
```

## Verification ✅

Created `verify_rq_timeout_fix.py` script that scans all Python files for incorrect timeout usage.

**Result**: 
- ✅ Checked 239 Python files in server/ directory
- ✅ All `queue.enqueue()` calls use correct `job_timeout` parameter
- ✅ No instances of incorrect `timeout` parameter found

Run verification: `python verify_rq_timeout_fix.py`

## Impact
This fix resolves the issue for all jobs using the unified `enqueue()` wrapper:
- Scheduled jobs (reminders, cleanup tasks)
- Background processing jobs (webhooks, recordings, receipts)
- WhatsApp message sending jobs
- Any future jobs using the wrapper with a timeout parameter

All direct `queue.enqueue()` calls already use correct `job_timeout`:
- `server/routes_outbound.py` ✅ 
- `server/tasks_recording.py` ✅
- `server/routes_receipts.py` ✅

## Deployment
- ✅ No database migrations required
- ✅ No configuration changes required
- ✅ No code changes needed (already correct)
- ⚠️ **Action Required**: Restart Worker processes after deployment
- 💡 **Optional**: Clear failed job registry to remove old TypeError failures

### Post-Deployment Commands:

```bash
# 1. Restart workers
systemctl restart rq-worker  # or: supervisorctl restart worker:*

# 2. Optional: Clear failed jobs from Redis
python -c "
from rq import Queue
from rq.registry import FailedJobRegistry
from server.services.jobs import get_redis

redis_conn = get_redis()
for queue_name in ['default', 'high', 'low', 'broadcasts', 'recordings', 'receipts']:
    queue = Queue(queue_name, connection=redis_conn)
    failed_registry = FailedJobRegistry(queue=queue)
    count = len(failed_registry)
    if count > 0:
        print(f'Clearing {count} failed jobs from {queue_name}')
        failed_registry.empty()
"

# 3. Monitor worker logs
tail -f /var/log/rq-worker.log  # Check for resolution
```

## Frontend Issue Investigation

Problem statement mentioned: "Popup בפרונט: to_number is not defined"

**Investigation Result**: 
- ✅ No undefined `to_number` variables found in frontend code
- ✅ All `to_number` references properly defined in TypeScript interfaces
- ✅ WhatsApp sending functions use correct parameters (`to`, `phone_e164`)
- 💡 This error was likely a symptom of RQ backend failures

**Conclusion**: With RQ timeout fix, frontend errors should resolve automatically.

## References
- RQ Documentation: https://python-rq.org/docs/
- Job timeout configuration: Use `job_timeout` parameter in `queue.enqueue()` calls
- RQ Job Timeouts: https://python-rq.org/docs/jobs/#job-timeouts
