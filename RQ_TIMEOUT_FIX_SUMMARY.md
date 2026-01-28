# RQ Timeout Parameter Fix

## Problem
Jobs enqueued via the `enqueue()` wrapper function were failing with:
```
TypeError: reminders_tick_job() got an unexpected keyword argument 'timeout'
```

## Root Cause
The `enqueue()` function was passing `timeout` to RQ's `queue.enqueue()`, but RQ expects the parameter to be named `job_timeout`. Any unrecognized parameters are passed through to the job function as kwargs, causing the error.

## Solution
Changed the `enqueue()` function in `server/services/jobs.py` to use `job_timeout` instead of `timeout` when building the job configuration.

## Impact
This fix resolves the issue for all jobs using the unified `enqueue()` wrapper:
- Scheduled jobs (reminders, cleanup tasks)
- Background processing jobs
- Any future jobs using the wrapper with a timeout parameter

## Deployment
- No database migrations required
- No configuration changes required
- Failed jobs will succeed after deployment
- Optional: Clear failed job registry if desired

## References
- RQ Documentation: https://python-rq.org/docs/
- Job timeout configuration: Use `job_timeout` parameter in `queue.enqueue()` calls
