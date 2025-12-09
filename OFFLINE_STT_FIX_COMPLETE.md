# Offline STT Recording Download Fix - Complete

## Problem Summary

The offline transcription system was failing because:

1. **Recording not ready**: Twilio recordings show `duration=-1` immediately after call ends (still processing)
2. **Immediate 404 errors**: The system tried to download too quickly and got 404, then gave up
3. **Wrong URL format**: Used `.mp3` suffix instead of trying multiple formats like the UI does
4. **No retry mechanism**: Failed on first 404 without waiting for recording to be ready

## Solution Implemented

### 1. ✅ Copied Working UI Download Logic

The UI endpoint (`/api/calls/<call_sid>/download` in `routes_calls.py`) uses this approach:
- Remove `.json` from URL if present
- Try multiple URL formats: base URL, `.mp3`, `.wav`
- Use requests with Twilio auth
- Handle 404 gracefully

**Copied this exact logic to `download_recording()` in `tasks_recording.py`**

### 2. ✅ Added Retry Mechanism for duration=-1

When recording is fetched from Twilio SDK:
```python
recording = client.recordings(recording_sid).fetch()
```

If `recording.duration` is `None` or `-1`:
- **NOT a final failure** - recording is still processing
- Log: `[OFFLINE_STT] Recording not ready yet, will retry in Xs (attempt N/5)`
- Wait with backoff: 3s, 5s, 5s, 10s, 10s
- Retry up to 5 times before giving up
- Only after all retries: `❌ [OFFLINE_STT] Giving up on recording CA... after 5 attempts`

### 3. ✅ Added Retry for 404 Responses

When downloading media:
- If first URL format returns 404, wait 5 seconds before trying next format
- Try all formats: base URL (no extension), `.mp3`, `.wav`
- Only give up after trying all formats and all attempts

### 4. ✅ Verified Transcript Priority (Already Correct)

In `media_ws_ai.py` (lines 9981-9986):
```python
if call_log and call_log.final_transcript:
    final_transcript = call_log.final_transcript
    print(f"✅ [WEBHOOK] Using OFFLINE transcript ({len(final_transcript)} chars)")
else:
    final_transcript = full_conversation
    print(f"ℹ️ [WEBHOOK] Offline transcript missing → using realtime ({len(full_conversation)} chars)")
```

**No length thresholds, no extra conditions** - strict offline-first priority.

## Expected Logs After Fix

On a successful call, you should see:

```
[OFFLINE_STT] Recording fetched: RE..., duration=-1s
[OFFLINE_STT] Recording not ready yet, will retry in 3s (attempt 1/5)
[OFFLINE_STT] Recording fetched: RE..., duration=-1s
[OFFLINE_STT] Recording not ready yet, will retry in 5s (attempt 2/5)
[OFFLINE_STT] Recording fetched: RE..., duration=42s
[OFFLINE_STT] Trying recording URL (format 1/3): https://api.twilio.com/...
[OFFLINE_STT] Download status: 200, bytes=524288
[OFFLINE_STT] ✅ Successfully downloaded 524288 bytes
[OFFLINE_STT] ✅ Recording saved to disk: server/recordings/CA....mp3 (524288 bytes)
[OFFLINE_STT] Starting Whisper transcription for CA...
[OFFLINE_STT] ✅ Transcript obtained: 1234 chars for CA...
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CA...
...
✅ [WEBHOOK] Using OFFLINE transcript (1234 chars)
```

## Key Changes to `server/tasks_recording.py`

### Before:
- Tried to download immediately after call ends
- Used single `.mp3` URL format
- No retry for `duration=-1`
- Gave up on first 404

### After:
- Waits for recording to be ready (up to 5 attempts with backoff)
- Uses same multi-format approach as UI (base URL, .mp3, .wav)
- Retries when `duration=-1` or `None`
- Only gives up after exhausting all retries and formats

## Testing Instructions

1. **Make a test call** to the system
2. **Monitor logs** for the sequence above
3. **Verify**:
   - You see retry attempts with `Recording not ready yet`
   - Eventually see `duration=XXs` (positive number)
   - See `Download status: 200`
   - See `✅ Transcript obtained`
   - See `✅ [WEBHOOK] Using OFFLINE transcript`

## Files Modified

- `/workspace/server/tasks_recording.py` - `download_recording()` function completely rewritten

## Files Verified (No Changes Needed)

- `/workspace/server/routes_calls.py` - UI download logic (used as reference)
- `/workspace/server/media_ws_ai.py` - Transcript priority already correct

---

**Status**: ✅ Implementation Complete
**Next Step**: Test with a real call to verify the fix works
