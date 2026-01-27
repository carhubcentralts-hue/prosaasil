# AudioPlayer Recording Download Fix - Troubleshooting Guide

## Problem Description
Users are experiencing 404 errors when trying to play call recordings. The AudioPlayer component shows:
- "File not ready (404), retrying..."
- Multiple retry attempts
- Eventually gives up with error message

## Root Cause
Recordings need to be downloaded from Twilio before they can be played. This download happens asynchronously via an RQ worker. The issue occurs when:
1. Recording downloads are slow (large files can take 2-3 minutes)
2. RQ worker is not running or not processing jobs
3. Download jobs fail silently

## Solution Implemented

### Frontend Changes (AudioPlayer.tsx)
1. **Extended retry patience**: Increased from 5 retries (48s) to 12 retries (~3 minutes)
2. **Progressive backoff**: 3s → 5s → 8s → 10s → 15s → 15s...
3. **Better user feedback**: Shows total wait time and clearer messages
4. **Manual retry button**: Allows users to retry after exhausting automatic retries

### Backend Changes (routes_recordings.py)
1. **Improved job detection**: Now checks for both 'download' and 'full' job types
2. **Better logging**: Shows job type and status when download is in progress
3. **Clearer error messages**: Explains that large files may take up to 3 minutes

## Diagnostics

### 1. Check if RQ Worker is Running
```bash
# In production
docker-compose -f docker-compose.prod.yml ps worker

# Check worker logs
docker-compose -f docker-compose.prod.yml logs worker --tail=100 -f
```

### 2. Run Diagnostic Script
```bash
# Run from project root
python check_recording_worker.py
```

This script checks:
- Redis connectivity
- RQ queue status (jobs waiting, failed jobs)
- RecordingRun database entries
- Recordings directory and file count
- System health summary

### 3. Check Specific Recording
```bash
# Check if recording file exists on disk
ls -lh server/recordings/<CALL_SID>.mp3

# Check RecordingRun entries for a call
docker-compose exec prosaas-api python -c "
from server.app_factory import get_process_app
from server.models_sql import RecordingRun
app = get_process_app()
with app.app_context():
    runs = RecordingRun.query.filter_by(call_sid='<CALL_SID>').all()
    for run in runs:
        print(f'Run {run.id}: status={run.status} job_type={run.job_type} error={run.error_message}')
"
```

## Common Issues and Solutions

### Issue 1: Worker Not Running
**Symptoms**: Jobs in RQ queue but no completions

**Solution**:
```bash
docker-compose -f docker-compose.prod.yml restart worker
```

### Issue 2: Redis Connection Failed
**Symptoms**: "REDIS_URL not set" or connection errors

**Solution**: Check Redis is running and REDIS_URL env var is set
```bash
docker-compose ps redis
echo $REDIS_URL
```

### Issue 3: Download Jobs Failing
**Symptoms**: Failed jobs in RQ failed_job_registry

**Solution**: Check worker logs for errors, ensure Twilio credentials are valid
```bash
docker-compose logs worker --tail=100 | grep -i "error\|failed"
```

### Issue 4: Recordings Directory Not Mounted
**Symptoms**: "recordings directory does not exist"

**Solution**: Check docker-compose volume mounts
```bash
docker volume ls | grep recordings
docker-compose -f docker-compose.prod.yml config | grep recordings_data
```

### Issue 5: Twilio Recording Not Ready Yet
**Symptoms**: All infrastructure works but still 404

**Explanation**: Twilio takes time to process recordings after call ends (usually 30-60 seconds)

**Solution**: Wait a bit longer, or check if recording_url is set in CallLog

## Testing the Fix

### Manual Test
1. Make a test call that records audio
2. Wait for call to end
3. Navigate to call details page
4. Try to play recording
5. Observe:
   - Should show "בודק זמינות הקלטה..." (Checking recording availability)
   - Then "ממתין להקלטה... (Xs)" (Waiting for recording)
   - Finally play audio or show retry button if timeout

### Expected Behavior
- **Immediate playback**: If file already downloaded
- **Wait 30-180s**: For new recordings to download
- **Manual retry**: If download takes longer than 3 minutes

## Monitoring in Production

### Key Metrics to Watch
1. **RecordingRun completion rate**: `completed / (completed + failed)` should be > 95%
2. **Average download time**: Most should complete within 60 seconds
3. **Failed job count**: Should be near zero
4. **Queue backlog**: Should stay under 10 jobs

### Logs to Monitor
```bash
# Watch for download jobs being enqueued
docker-compose logs -f prosaas-api | grep "RECORDING.*Enqueueing"

# Watch for worker processing jobs
docker-compose logs -f worker | grep "RQ_RECORDING"

# Watch for errors
docker-compose logs -f worker | grep -i error
```

## Rollback Plan
If issues persist after this fix:
1. The changes are minimal and safe - they only extend retry timeouts
2. No breaking changes to data structures or APIs
3. Can revert by running: `git revert <commit-hash>`

## Future Improvements
1. **Pre-download optimization**: Trigger downloads immediately in recording callback webhook
2. **Progress indicator**: Show actual download progress if available
3. **Caching layer**: Use CDN or faster storage for frequently accessed recordings
4. **Queue priority**: Give UI-triggered downloads higher priority than batch jobs
