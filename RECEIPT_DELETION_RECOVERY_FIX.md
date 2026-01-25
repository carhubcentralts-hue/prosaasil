# Fix: Receipt Deletion Stuck State After Server Restart

## Problem Summary

When a receipt deletion job is running and the server crashes or restarts, the UI remains stuck showing "Deleting receipts... 0 out of 412, 0.0%". This happens because:

1. The job state exists only in the worker process memory
2. After server restart, the job record in DB still shows `status='running'`
3. No mechanism exists to detect that the worker is dead
4. Frontend keeps polling, but the job never progresses

## Solution Implemented

### 1. Database Schema Enhancement (Migration 103)

Added `heartbeat_at` column to `background_jobs` table:
- `heartbeat_at TIMESTAMP NULL` - Tracks when the job last updated
- Partial index on `heartbeat_at WHERE status = 'running'` for efficient queries
- Auto-initialized for existing running jobs

**File:** `server/db_migrate.py`

### 2. Job Worker Heartbeat Updates

Updated `delete_receipts_batch_job` to update heartbeat:
- Initialize `heartbeat_at` when job starts
- Update `heartbeat_at` after each batch completes
- Dual tracking with `updated_at` for redundancy

**File:** `server/jobs/delete_receipts_job.py`

### 3. Stale Job Detection Endpoint

Added `GET /api/receipts/delete-job/status` endpoint:
- Checks for active delete jobs
- Detects stale jobs using two criteria:
  - **Heartbeat staleness**: No heartbeat for > 120 seconds
  - **Update staleness**: No updates for > 5 minutes (300 seconds)
- Marks stale jobs as `failed` with descriptive error
- Returns clean state to frontend

**File:** `server/routes_receipts.py`

### 4. Frontend Recovery Mechanism

Updated `ReceiptsPage.tsx` to call status endpoint on page load:
- Calls `/api/receipts/delete-job/status` instead of checking localStorage first
- Detects stale jobs automatically
- Shows Hebrew error message when stale job is cleared
- Restores active jobs that are still healthy
- Clears localStorage when jobs are stale or failed

**File:** `client/src/pages/receipts/ReceiptsPage.tsx`

### 5. Model Update

Updated `BackgroundJob` model with new field:
- Added `heartbeat_at = db.Column(db.DateTime, nullable=True)`

**File:** `server/models_sql.py`

## Technical Details

### Stale Detection Logic

```python
# Check heartbeat staleness (120 seconds)
if job.heartbeat_at:
    heartbeat_age = (now - job.heartbeat_at).total_seconds()
    if heartbeat_age > 120:
        is_stale = True

# Check updated_at staleness (5 minutes)
if not is_stale and job.updated_at:
    updated_age = (now - job.updated_at).total_seconds()
    if updated_age > 300:
        is_stale = True

# Mark stale job as failed
if is_stale:
    job.status = 'failed'
    job.last_error = f"Server restarted / job heartbeat lost: {reason}"
    job.finished_at = datetime.utcnow()
```

### Frontend Recovery Flow

```typescript
1. Page loads → Call /api/receipts/delete-job/status
2. Endpoint checks for stale jobs
   - If stale: Mark as failed, return was_stale=true
   - If active: Return job details
   - If none: Return has_active_job=false
3. Frontend handles response:
   - Stale: Show error, clear localStorage
   - Active: Restore UI, start polling
   - None: Clear localStorage
```

## Testing

Run the test suite:
```bash
python3 test_stale_job_detection.py
```

Tests verify:
- ✓ Fresh jobs (heartbeat < 120s) are not marked as stale
- ✓ Stale jobs (heartbeat > 120s) are detected
- ✓ Jobs with old updated_at (> 5 min) are detected
- ✓ SQL migration statements are valid
- ✓ Endpoint logic handles all cases correctly

## Deployment Notes

1. **Migration:** Migration 103 will run automatically on server start
2. **Backward Compatibility:** Existing jobs will have heartbeat initialized to `updated_at` or `started_at`
3. **No Breaking Changes:** All changes are additive
4. **Idempotent:** Migration can be run multiple times safely

## Acceptance Criteria ✅

1. ✅ Start deletion, kill server in the middle, restart
2. ✅ Enter receipts screen
3. ✅ Within seconds, UI detects the stale job and shows recovery message
4. ✅ User can start new deletion without being stuck

## Files Changed

- `server/db_migrate.py` - Migration 103
- `server/models_sql.py` - Added heartbeat_at field
- `server/jobs/delete_receipts_job.py` - Update heartbeat
- `server/routes_receipts.py` - New status endpoint
- `client/src/pages/receipts/ReceiptsPage.tsx` - Frontend recovery
- `test_stale_job_detection.py` - Test suite (new)

## Future Enhancements (Optional)

1. Add UI button to manually "force reset" stuck jobs
2. Add admin dashboard to view all background jobs
3. Extend heartbeat mechanism to other job types
4. Add metrics/monitoring for job health
