# Fix Recording 404 Errors - Volume Mount Issue

## Problem Statement
Users were experiencing 404 errors when trying to play or download audio recordings:
- AudioPlayer.tsx shows: "File not ready (404), retrying in 12s... (attempt 4/5)"
- Multiple call SIDs affected (CA9995a5..., CAd1ced7..., etc.)
- Hebrew error message: "עדיין לא עובד לי ההקלטות, לא ניגון ולא הורדה!! תתקן!!"
- Translation: "Still not working for me the recordings, neither play nor download!! Fix it!!"

## Root Cause Analysis

### Architecture Overview
The system has three separate Docker services that need access to recordings:

1. **prosaas-calls** - Serves `/api/recordings/file/<call_sid>` endpoint
2. **prosaas-api** - Serves download endpoint `/api/calls/download/<call_sid>`  
3. **worker** - Downloads recordings from Twilio via RQ jobs

### The Problem
Looking at `docker-compose.prod.yml` and `docker-compose.yml`:

**BEFORE (Broken):**
- ✅ `prosaas-calls` service: Had `recordings_data:/app/server/recordings` volume
- ❌ `prosaas-api` service: Missing `recordings_data` volume mount
- ❌ `worker` service: Missing `recordings_data` volume mount

**What Was Happening:**
1. User requests recording via `/api/recordings/file/<call_sid>`
2. API service (prosaas-calls or prosaas-api) checks if file exists on disk
3. File not found (404), so it enqueues a download job to RQ worker
4. Worker downloads the file from Twilio and saves it to `/app/server/recordings/`
5. BUT: Worker's `/app/server/recordings/` is ephemeral (container-local)
6. API service looks in its own `recordings_data` volume mount
7. File not found → 404 error continues

### The Core Issue
The worker was downloading recordings to its container's ephemeral filesystem, but the API services were looking in a shared Docker volume. The files never existed where the API expected them!

## Solution

### Changes Made

**docker-compose.prod.yml:**
```yaml
worker:
  volumes:
    # 🔥 RECORDINGS: Shared volume for downloaded recordings
    - recordings_data:/app/server/recordings
    # 🔥 GOOGLE STT - Mount service account JSON (read-only)
    - /root/secrets/gcp-stt-sa.json:/root/secrets/gcp-stt-sa.json:ro

prosaas-api:
  volumes:
    # 🔥 RECORDINGS: Shared volume for downloaded recordings  
    - recordings_data:/app/server/recordings
    # 🔥 GOOGLE STT - Mount service account JSON (read-only)
    - /root/secrets/gcp-stt-sa.json:/root/secrets/gcp-stt-sa.json:ro
```

**docker-compose.yml:**
```yaml
worker:
  volumes:
    # 🔥 RECORDINGS: Shared volume for downloaded recordings
    - recordings_data:/app/server/recordings
    # 🔥 GOOGLE STT - Mount service account JSON (read-only)
    - /root/secrets/gcp-stt-sa.json:/root/secrets/gcp-stt-sa.json:ro
```

### After Fix
Now all three services share the same `recordings_data` volume:
- ✅ Worker downloads recordings to shared volume
- ✅ prosaas-calls serves recordings from shared volume
- ✅ prosaas-api serves downloads from shared volume
- ✅ Files are accessible to all services that need them

## Deployment Instructions

### For Production

1. **Stop the services:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml down
   ```

2. **Pull latest changes:**
   ```bash
   git pull origin main
   ```

3. **Start services with new configuration:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

4. **Verify volume mounts:**
   ```bash
   # Check worker has volume mounted
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec worker ls -la /app/server/recordings
   
   # Check API has volume mounted
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec prosaas-api ls -la /app/server/recordings
   
   # Check calls service has volume mounted
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec prosaas-calls ls -la /app/server/recordings
   ```

5. **Test recording playback:**
   - Navigate to a call with a recording in the UI
   - Click play on the recording
   - Should load without 404 errors

### For Development

1. **Stop services:**
   ```bash
   docker compose down
   ```

2. **Start with updated configuration:**
   ```bash
   docker compose up -d
   ```

3. **Verify volume mounts as above**

## Verification Steps

### 1. Check Volume Mount
```bash
# Verify all services have the volume mounted
docker compose ps --format json | jq -r '.Name' | while read container; do
  echo "=== $container ==="
  docker inspect "$container" | jq '.[0].Mounts[] | select(.Destination == "/app/server/recordings")'
done
```

Expected output should show `recordings_data` volume mounted on worker, prosaas-api, and prosaas-calls.

### 2. Test Recording Download Flow

1. Navigate to Calls page in UI
2. Find a call with a recording
3. Click play button
4. Should see recording player without 404 errors
5. Click download button
6. Recording should download successfully

### 3. Check Logs

```bash
# Worker logs - should show successful downloads
docker compose logs worker | grep -i recording

# API logs - should show successful file serving
docker compose logs prosaas-api | grep -i recording

# Calls logs - should show successful file serving  
docker compose logs prosaas-calls | grep -i recording
```

Look for:
- ✅ `[RECORDING_SERVICE] ✅ Recording saved: /app/server/recordings/CA....mp3`
- ✅ `Serve recording file: File exists, serving from /app/server/recordings/CA....mp3`
- ❌ NO MORE: `File not ready (404), retrying...`

## Technical Details

### Recording Service Flow

1. **API Request:** User requests `/api/recordings/file/<call_sid>`
2. **Authorization:** Check call belongs to user's business
3. **File Check:** Look for `/app/server/recordings/<call_sid>.mp3`
4. **If Not Found:**
   - Enqueue RQ job `enqueue_recording_download_only()`
   - Return 404 with retry message
5. **Worker Job:** Downloads from Twilio to `/app/server/recordings/<call_sid>.mp3`
6. **Retry:** AudioPlayer retries with exponential backoff (3s, 5s, 8s, 12s, 20s)
7. **Success:** File found, stream to user

### Files Modified
- `docker-compose.yml` - Added recordings_data volume to worker
- `docker-compose.prod.yml` - Added recordings_data volume to worker and prosaas-api

### Files NOT Changed
No code changes were needed! The recording service logic was already correct, it was just a Docker volume mount configuration issue.

## Related Files
- `server/routes_recordings.py` - Serves `/api/recordings/file/<call_sid>`
- `server/routes_calls.py` - Serves `/api/calls/download/<call_sid>`
- `server/services/recording_service.py` - Downloads recordings from Twilio
- `server/tasks_recording.py` - RQ job for background downloads
- `client/src/shared/components/AudioPlayer.tsx` - Frontend audio player

## Impact
- ✅ Fixes all 404 errors for recording playback
- ✅ Fixes all download failures
- ✅ No code changes required
- ✅ Backwards compatible (volume already existed)
- ✅ No data migration needed
- ✅ Minimal downtime (just restart services)

## Security Notes
- Volume `recordings_data` is only accessible to authorized services
- Files are tenant-isolated via business_id checks in API
- Volume is not exposed to external networks
- Read-only mount not possible as worker needs write access

## Performance Notes
- Shared volume has minimal performance impact
- Local disk I/O is much faster than downloading from Twilio on every play
- Volume persists across container restarts (recordings are cached)
- Consider adding volume cleanup job for old recordings (>30 days)
