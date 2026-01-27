# Manual Testing Guide - Recording Playback Loop Fix

## Issue Fixed
Previously, clicking Play on a recording once resulted in:
- Dozens of stream requests in Network tab
- Repeated "Streaming from..." logs in Console
- Multiple duplicate Jobs created in the worker

## What Changed

### Backend Changes
1. **routes_calls.py** - `/api/recordings/<call_sid>/stream` endpoint
   - Now checks RecordingRun table for existing queued/running jobs
   - Returns 202 status if job already exists (no new job created)
   - Prevents race conditions by checking DB first

2. **tasks_recording.py** - `enqueue_recording_download_only` function
   - Checks DB for existing queued/running RecordingRun before creating new entry
   - Creates RecordingRun BEFORE enqueueing to RQ (establishes ownership)
   - Returns (False, "duplicate") if job already exists

### Frontend Changes
1. **AudioPlayer.tsx** - Audio player component
   - Added `isCheckingRef` guard to prevent concurrent HEAD requests
   - Added `AbortController` to cancel pending requests
   - Aborts requests on cleanup and when src changes
   - Improved error handling for AbortError

## Testing Instructions

### Setup
1. Ensure you have recordings in the system
2. Open Chrome DevTools
3. Navigate to Network tab and filter by "stream"
4. Navigate to Console tab

### Test 1: Single Play Click
**Expected behavior:** ✅
- Click Play button on a recording
- **Network tab:** 1 request to `/api/recordings/<id>/stream?explicit_user_action=true`
  - If recording is not cached: First request returns 202, subsequent polls return 200
  - If recording is cached: Single 200 response
- **Console tab:** Single log "Streaming from: ..." (or none if cached)
- **Audio:** Starts playing when ready

**Failure indicators:** ❌
- More than 2-3 stream requests in Network tab
- Repeated "Streaming from..." logs in Console
- Audio doesn't play

### Test 2: Multiple Recordings
**Expected behavior:** ✅
- Open recording 1, click Play
- Switch to recording 2, click Play
- **Network tab:** Each recording gets its own stream request
- **Console tab:** One log per recording
- Previous requests should be aborted (check for cancelled requests)

**Failure indicators:** ❌
- Requests for previous recording continue after switching
- Duplicate requests for same recording

### Test 3: Recording Not Ready (202 Response)
**Expected behavior:** ✅
- Click Play on a recording that hasn't been downloaded yet
- **UI:** Shows "בודק זמינות הקלטה..." or "ממתין להקלטה... (Xs)"
- **Network tab:** 
  - Initial HEAD request gets 202 Accepted
  - Retry requests at 3s, 5s, 8s intervals (exponential backoff)
  - Final 200 OK when ready
- **Audio:** Starts playing after download completes

**Failure indicators:** ❌
- Dozens of rapid 202 responses without delay
- No backoff between retries
- Audio never plays

### Test 4: Worker Job Deduplication
**Expected behavior:** ✅
- Click Play on uncached recording
- Check worker logs or RecordingRun table
- **Database:** Only ONE RecordingRun entry with status 'queued' or 'running'
- **Worker:** Only ONE job processing this call_sid

**Failure indicators:** ❌
- Multiple RecordingRun entries for same call_sid with status 'queued'
- Multiple jobs in worker for same recording

### Test 5: Quick Successive Clicks
**Expected behavior:** ✅
- Rapidly click Play/Pause/Play on a recording
- **Network tab:** Minimal requests (previous aborted)
- **Console tab:** Clean logs, no spam

**Failure indicators:** ❌
- Each click creates new request
- No requests are cancelled
- Flood of requests

## Verification Commands

### Check RecordingRun in Database
```sql
-- Check for duplicate jobs (should return 0 or very few rows)
SELECT call_sid, COUNT(*) as count
FROM recording_runs
WHERE status IN ('queued', 'running')
GROUP BY call_sid
HAVING COUNT(*) > 1;

-- Check recent recording runs for a specific call
SELECT id, call_sid, status, created_at, started_at
FROM recording_runs
WHERE call_sid = 'CA...'
ORDER BY created_at DESC
LIMIT 5;
```

### Check Worker Logs
```bash
# Check for duplicate job enqueues
docker-compose logs worker | grep "RQ_ENQUEUE" | grep "call_sid=CA..."

# Check for dedup blocks
docker-compose logs worker | grep "Duplicate enqueue blocked"
```

### Check Redis Keys
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check for job locks
KEYS job:download:*

# Check specific job
GET job:download:1:CA...
TTL job:download:1:CA...
```

## Success Criteria

✅ **All tests pass if:**
1. Single Play click results in 1-2 stream requests maximum
2. No flood of `stream?explicit_user_action=true` requests
3. Console doesn't print "Streaming from..." in loop
4. Worker creates only ONE download job per call_sid
5. RecordingRun table has no duplicate queued/running entries for same call_sid

## Rollback Instructions

If issues occur, rollback by reverting these files:
```bash
git checkout HEAD~1 -- server/routes_calls.py
git checkout HEAD~1 -- server/tasks_recording.py
git checkout HEAD~1 -- client/src/shared/components/AudioPlayer.tsx
```

## Additional Notes

- The fix uses multiple layers of deduplication:
  1. Frontend: Prevents concurrent checks with `isCheckingRef`
  2. Backend: Checks RecordingRun table before creating jobs
  3. Backend: Redis key prevents rapid duplicate enqueues
  
- Exponential backoff for 202 responses: 3s → 5s → 8s → 12s → 20s
- Maximum 5 retries before giving up
- AbortController ensures old requests are cancelled when switching recordings
