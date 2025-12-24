# Recording Streaming Fix - 502 Error Resolution

## Problem
When users try to play recordings in the UI, they often get **502 Bad Gateway** errors because:
1. The download endpoint downloads recordings from Twilio **synchronously** during the UI request
2. If Twilio is slow or the network is congested, the request times out
3. Nginx/proxy returns 502 to the browser

## Solution

### Backend Changes (`server/routes_calls.py`)

Added a new **asynchronous streaming endpoint**: `/api/recordings/<call_sid>/stream`

**Flow:**
1. Check if recording exists locally in `/app/server/recordings/<call_sid>.mp3`
2. **If YES**: Serve immediately with Range support (200 OK)
3. **If NO**: 
   - Enqueue a background job to download from Twilio
   - Return `202 Accepted` with `{"status": "processing"}`
   - UI will retry after a delay

**Status Codes:**
- `200 OK` - Recording served successfully
- `202 Accepted` - Recording is being prepared, retry later
- `400 Bad Request` - Missing business_id
- `403 Forbidden` - Call doesn't belong to user's tenant
- `404 Not Found` - Call or recording doesn't exist
- `410 Gone` - Recording expired (>7 days old)

### Frontend Changes

#### 1. AudioPlayer Component (`client/src/shared/components/AudioPlayer.tsx`)

Enhanced to handle async recording downloads:
- Detects streaming URLs (`/api/recordings/<call_sid>/stream`)
- Handles 202 responses with automatic retry logic
- Shows "מכין הקלטה..." (preparing recording) message
- Displays retry count: "מכין הקלטה... (נסיון 3/10)"
- Retries every 2 seconds for up to 20 seconds (10 attempts)

#### 2. CallsPage (`client/src/pages/calls/CallsPage.tsx`)

Updated `loadRecordingBlob` function:
- Uses new streaming endpoint `/api/recordings/<call_sid>/stream`
- Implements retry logic with MAX_RETRIES = 10, RETRY_DELAY = 2000ms
- Shows error messages for expired/failed recordings

#### 3. OutboundCallsPage (`client/src/pages/calls/OutboundCallsPage.tsx`)

Updated to use streaming endpoint:
```tsx
<AudioPlayer src={`/api/recordings/${call.call_sid}/stream`} />
```

## How It Works

### First Play (Recording Not Cached)
```
User clicks Play
    ↓
UI: GET /api/recordings/CAxxxx/stream
    ↓
Backend: File not cached → Enqueue job
    ↓
Backend: 202 Accepted {"status": "processing"}
    ↓
UI: Shows "מכין הקלטה... (נסיון 1/10)"
    ↓
Wait 2 seconds
    ↓
UI: GET /api/recordings/CAxxxx/stream (retry)
    ↓
Backend: File ready → 200 OK + audio
    ↓
UI: Plays recording
```

### Subsequent Plays (Recording Cached)
```
User clicks Play
    ↓
UI: GET /api/recordings/CAxxxx/stream
    ↓
Backend: File exists → 200 OK + audio
    ↓
UI: Plays immediately
```

## Testing

### Manual Testing Steps

1. **Test with uncached recording:**
   ```bash
   # Remove cached recordings
   rm -rf /app/server/recordings/*.mp3
   
   # Try to play a recording in the UI
   # Should show "מכין הקלטה..." and retry until ready
   ```

2. **Test with cached recording:**
   ```bash
   # After first play, try playing again
   # Should load immediately without "מכין הקלטה..." message
   ```

3. **Test expired recording:**
   ```bash
   # Try to play a recording older than 7 days
   # Should show error message about expiration
   ```

4. **Test permission denied:**
   ```bash
   # Try to access recording from different business_id
   # Should return 404 (not found) to prevent info leak
   ```

### Automated Testing

The Python syntax has been verified:
```bash
python -m py_compile server/routes_calls.py
# ✅ No errors
```

### Unit Test
Run the test file:
```bash
python test_streaming_endpoint.py
```

This verifies:
- Streaming endpoint is registered
- Recording service functions work correctly
- Job enqueueing works
- check_local_recording_exists function works

## Benefits

1. **No more 502 errors** - Downloads happen in background, not during UI request
2. **Better UX** - Clear feedback when recording is being prepared
3. **Proper error messages** - 403/404/410 instead of generic 502
4. **Tenant isolation** - Security check ensures users only access their recordings
5. **Efficient caching** - Once downloaded, recordings play instantly

## Rollback Plan

If issues occur, the old endpoint `/api/calls/<call_sid>/download` still exists and works.

To rollback:
1. Revert AudioPlayer.tsx to use old endpoint
2. Revert CallsPage.tsx to use old endpoint
3. Revert OutboundCallsPage.tsx to use old endpoint

The new streaming endpoint can remain in place without causing issues.

## Monitoring

Look for these log messages:

**Success:**
```
[RECORDING_SERVICE] ✅ Cache HIT - using existing local file
Stream recording: File cached for call_sid=CAxxxx, serving immediately
```

**Processing:**
```
Stream recording: File not cached for call_sid=CAxxxx, enqueuing download job
✅ [OFFLINE_STT] Job enqueued for CAxxxx
```

**Errors:**
```
Stream recording: Call not found or access denied (403/404)
Stream recording: Recording expired for call_sid=CAxxxx (410)
```
