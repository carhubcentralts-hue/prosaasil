# RQ Timeout Parameter Fix - Summary

## Problem
When using `queue.enqueue()` with a `timeout` parameter, RQ was passing it as a keyword argument to the job function itself, causing:

```
TypeError: reminders_tick_job() got an unexpected keyword argument 'timeout'
```

## Root Cause
RQ's `parse_args()` method in `rq/queue.py` looks for `job_timeout` (not `timeout`) in the kwargs:

```python
# From rq/queue.py line 23
timeout = kwargs.pop('job_timeout', None)
```

When we pass `timeout=120` to `queue.enqueue()`, RQ doesn't recognize it as a job configuration parameter and instead passes it through to the function as a kwarg.

## The Fix
Changed the `enqueue()` function in `server/services/jobs.py` line 190:

**Before:**
```python
job_kwargs = {
    'job_id': job_id,
    'meta': meta,
    'ttl': ttl,
    'timeout': timeout,  # ❌ Wrong parameter name
    'description': description or f"{func.__name__}",
}
```

**After:**
```python
job_kwargs = {
    'job_id': job_id,
    'meta': meta,
    'ttl': ttl,
    'job_timeout': timeout,  # ✅ Correct parameter name for RQ
    'description': description or f"{func.__name__}",
}
```

## Impact
This fix affects all jobs enqueued via the unified `enqueue()` function, including:
- `reminders_tick_job` (every minute)
- `whatsapp_sessions_cleanup_job` (every 5 minutes)
- `reminders_cleanup_job` (daily)
- `cleanup_old_recordings_job` (daily)
- Any future jobs using the `enqueue()` wrapper with a timeout parameter

## Verification
✅ All direct `queue.enqueue()` calls in the codebase already use `job_timeout=` correctly:
- `server/routes_outbound.py` - Uses `job_timeout='2h'`, `job_timeout='30m'`, etc.
- `server/tasks_recording.py` - Uses `job_timeout='30m'`
- `server/routes_receipts.py` - Uses `job_timeout='1h'`
- `test_worker_integration.py` - Uses `job_timeout=30`

✅ The fix ensures consistency across the entire codebase.

## Testing
The fix was verified by:
1. Checking RQ's source code to confirm `job_timeout` is the correct parameter
2. Verifying the transformation is applied in `jobs.py`
3. Confirming other direct enqueue calls already use `job_timeout`

## Deployment Notes
- No database migrations required
- No configuration changes required
- Jobs currently failing with the timeout error will succeed after deployment
- No need to clear failed job registry (old failed jobs can be ignored or manually removed)

## Optional: Clean Failed Jobs
If you want to clean up old failed jobs from the error, you can run:

```bash
# Connect to Redis
redis-cli -u $REDIS_URL

# List failed jobs
LRANGE rq:queue:failed 0 -1

# Or use RQ CLI
rq info --failed
rq requeue --all  # Requeue all failed jobs (they should now succeed)
```

## References
- RQ Documentation: https://python-rq.org/docs/
- RQ Source Code: https://github.com/rq/rq
- Specific RQ parse_args method: `rq/queue.py` line 923-963
