# Offline Recording Transcription Worker - Fix Summary

## Problem
Recording jobs were being "queued" but never processed because:
- No worker loop was running to process the queue
- Each recording spawned a new thread directly instead of using a queue
- No [OFFLINE_STT] logs were appearing

## Solution Implemented

### 1. Created Queue-Based Worker System (`server/tasks_recording.py`)

**Global Queue:**
```python
RECORDING_QUEUE = queue.Queue()
```

**New Functions:**
- `enqueue_recording_job(call_sid, recording_url, business_id, from_number, to_number)`
  - Adds jobs to the shared queue
  - Logs: `✅ [OFFLINE_STT] Job enqueued for {call_sid}`

- `start_recording_worker(app)`
  - Background loop that processes jobs from the queue
  - Logs: `✅ [OFFLINE_STT] Recording worker loop started`
  - For each job: `🎧 [OFFLINE_STT] Starting offline transcription for {call_sid}`
  - On completion: `✅ [OFFLINE_STT] Completed processing for {call_sid}`

- `enqueue_recording(form_data)` - Legacy wrapper
  - Maintains backward compatibility
  - Extracts business_id from phone numbers
  - Calls `enqueue_recording_job()`

### 2. Wired Worker into App Startup (`server/app_factory.py`)

Added before `return app`:
```python
# Recording transcription worker (offline STT + lead extraction)
try:
    from server.tasks_recording import start_recording_worker
    import threading
    
    recording_thread = threading.Thread(
        target=start_recording_worker,
        args=(app,),
        daemon=True,
        name="RecordingWorker"
    )
    recording_thread.start()
    print("✅ [BACKGROUND] Recording worker started")
except Exception as e:
    print(f"⚠️ [BACKGROUND] Could not start recording worker: {e}")
```

### 3. Webhook Integration (No Changes Required)

Existing webhooks in `server/routes_twilio.py`:
- `_trigger_recording_for_call()` - Line 119: `enqueue_recording(form_data)`
- `handle_recording()` - Line 648: `enqueue_recording(form_copy)`

Both continue to work via the legacy wrapper function.

## Expected Log Flow (After Fix)

After a call ends, you should see:

```
✅ Found existing recording for CAf33cf5d6ca520ebbb2c33a0071910085: /2010-04-01/Accounts/.../Recordings/REdcdf8ac0b9706e4c0ac30ce39954da5d.json
✅ Recording queued for processing: CAf33cf5d6ca520ebbb2c33a0071910085
✅ [OFFLINE_STT] Job enqueued for CAf33cf5d6ca520ebbb2c33a0071910085
🎧 [OFFLINE_STT] Starting offline transcription for CAf33cf5d6ca520ebbb2c33a0071910085
[OFFLINE_STT] Starting offline transcription for CAf33cf5d6ca520ebbb2c33a0071910085
[OFFLINE_STT] ✅ Transcript obtained: 1234 chars
[OFFLINE_EXTRACT] Starting extraction for CAf33cf5d6ca520ebbb2c33a0071910085
[OFFLINE_EXTRACT] ✅ Extracted: service='מנעולן', city='עפולה', confidence=0.95
[OFFLINE_EXTRACT] ✅ Updated lead 79 service_type: 'מנעולן'
[OFFLINE_EXTRACT] ✅ Updated lead 79 city: 'עפולה'
✅ [OFFLINE_STT] Completed processing for CAf33cf5d6ca520ebbb2c33a0071910085
```

## Startup Logs

On app startup, you should see:
```
✅ [OFFLINE_STT] Recording worker loop started
✅ [BACKGROUND] Recording worker started
```

## Architecture

### Before:
```
Webhook → enqueue_recording() → spawn new thread for each job
                                ↓
                        process_recording_async() (direct)
```

### After:
```
Webhook → enqueue_recording() → enqueue_recording_job()
                                        ↓
                                RECORDING_QUEUE (shared)
                                        ↓
                        start_recording_worker() (single loop)
                                        ↓
                        process_recording_async() (from queue)
```

## Files Modified

1. **server/tasks_recording.py**
   - Added `RECORDING_QUEUE` global queue
   - Added `enqueue_recording_job()` function
   - Modified `enqueue_recording()` to use queue
   - Added `start_recording_worker()` loop

2. **server/app_factory.py**
   - Added worker thread startup before `return app`
   - Thread name: "RecordingWorker"
   - Daemon mode: True (exits with app)

## Testing Verification

To verify the fix works:

1. **Check startup logs** - should see:
   - `✅ [OFFLINE_STT] Recording worker loop started`
   - `✅ [BACKGROUND] Recording worker started`

2. **Make a test call** - should see complete flow:
   - `✅ Recording queued for processing`
   - `✅ [OFFLINE_STT] Job enqueued`
   - `🎧 [OFFLINE_STT] Starting offline transcription`
   - `[OFFLINE_STT] ✅ Transcript obtained`
   - `[OFFLINE_EXTRACT]` logs (if extraction succeeds)
   - `✅ [OFFLINE_STT] Completed processing`

3. **Check lead in DB** - should have:
   - `final_transcript` populated
   - `extracted_service` populated (if found)
   - `extracted_city` populated (if found)
   - `extraction_confidence` value

## Benefits

1. **Single worker thread** - More efficient than spawning threads per job
2. **Queue-based processing** - Jobs are processed in order, never lost
3. **Proper logging** - Clear [OFFLINE_STT] tags for debugging
4. **App context** - Worker runs with Flask app context for DB access
5. **Graceful failure** - Errors don't crash the worker, just logged
6. **Backward compatible** - Existing webhook code unchanged

## Rollback

If issues occur, temporarily disable by commenting out in `app_factory.py`:
```python
# Recording transcription worker (offline STT + lead extraction)
# try:
#     from server.tasks_recording import start_recording_worker
#     ...
```

Recordings will still be stored but won't be transcribed offline.
