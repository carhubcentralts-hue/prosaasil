# 🛠 Offline Transcript Usage Fix - Summary

## 🎯 Problem
The offline recording worker was running and saving `final_transcript` to the database, but the webhook and UI were still using the realtime transcript instead of the high-quality offline Whisper transcript.

### Root Cause
The `call_log` object loaded at the beginning of `_finalize_call_on_stop()` was stale. When the offline worker updated `final_transcript` in the database after the call ended, the in-memory `call_log` object was not refreshed, so it still had `final_transcript = None`.

## ✅ Solution Applied

### 1️⃣ Enhanced Worker Logging (`server/tasks_recording.py`)
Added explicit debug logs after saving to DB to confirm the offline worker is working:

```python
db.session.commit()

# ✅ Explicit debug to confirm final_transcript was saved
print(f"[OFFLINE_STT] ✅ Saved to DB for {call_sid}:")
print(f"[OFFLINE_STT]    - final_transcript: {len(final_transcript) if final_transcript else 0} chars")
print(f"[OFFLINE_STT]    - extracted_service: {extracted_service or 'None'}")
print(f"[OFFLINE_STT]    - extracted_city: {extracted_city or 'None'}")
print(f"[OFFLINE_STT]    - confidence: {extraction_confidence or 'N/A'}")
```

### 2️⃣ Fixed Webhook to Reload Fresh CallLog (`server/media_ws_ai.py`)
**Before webhook construction, reload `CallLog` from database to get offline worker updates:**

```python
# 🔁 CRITICAL: Re-load fresh CallLog from DB to get offline worker updates
# The offline recording worker may have updated:
# - final_transcript (high-quality Whisper transcription)
# - extracted_city / extracted_service (AI extraction from recording)
# The call_log loaded at the start may be stale
print(f"[DEBUG] 🔁 Re-loading CallLog from DB to check for offline worker updates...")
fresh_call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
if fresh_call_log:
    print(f"[DEBUG] Fresh CallLog for {self.call_sid}:")
    print(f"[DEBUG]    - final_transcript: {len(fresh_call_log.final_transcript) if fresh_call_log.final_transcript else 0} chars")
    print(f"[DEBUG]    - extracted_service: {fresh_call_log.extracted_service or 'None'}")
    print(f"[DEBUG]    - extracted_city: {fresh_call_log.extracted_city or 'None'}")
    print(f"[DEBUG]    - extraction_confidence: {fresh_call_log.extraction_confidence or 'N/A'}")
```

### 3️⃣ Use Fresh CallLog for All Webhook Data
Updated the code to use `fresh_call_log` instead of stale `call_log`:

```python
# Use offline extracted fields
if fresh_call_log:
    if fresh_call_log.extracted_city:
        city = fresh_call_log.extracted_city
        print(f"✅ [WEBHOOK] Using offline extracted city from CallLog: '{city}'...")
    if fresh_call_log.extracted_service:
        service_category = fresh_call_log.extracted_service
        print(f"✅ [WEBHOOK] Using offline extracted service from CallLog: '{service_category}'...")

# Use final_transcript (high-quality Whisper)
final_transcript = full_conversation  # Default to realtime
if fresh_call_log and fresh_call_log.final_transcript:
    final_transcript = fresh_call_log.final_transcript
    print(f"✅ [WEBHOOK] Using offline final_transcript ({len(final_transcript)} chars) instead of realtime ({len(full_conversation)} chars)")
else:
    print(f"ℹ️ [WEBHOOK] No offline final_transcript available yet for {self.call_sid} - using realtime transcript ({len(full_conversation)} chars)")
```

## 🔍 Expected Log Flow

After a call ends, you should see this sequence in the logs:

### 1. Worker processes recording:
```
🎧 [OFFLINE_STT] Starting offline transcription for CAxxxx
[OFFLINE_STT] ✅ Transcript obtained: 1234 chars
[OFFLINE_EXTRACT] ✅ Extracted: service='חשמלאי', city='תל אביב', confidence=0.95
[OFFLINE_STT] ✅ Saved to DB for CAxxxx:
[OFFLINE_STT]    - final_transcript: 1234 chars
[OFFLINE_STT]    - extracted_service: חשמלאי
[OFFLINE_STT]    - extracted_city: תל אביב
[OFFLINE_STT]    - confidence: 0.95
```

### 2. Webhook reloads fresh data:
```
[DEBUG] 🔁 Re-loading CallLog from DB to check for offline worker updates...
[DEBUG] Fresh CallLog for CAxxxx:
[DEBUG]    - final_transcript: 1234 chars
[DEBUG]    - extracted_service: חשמלאי
[DEBUG]    - extracted_city: תל אביב
[DEBUG]    - extraction_confidence: 0.95
✅ [WEBHOOK] Using offline extracted city from CallLog: 'תל אביב' (confidence: 0.95)
✅ [WEBHOOK] Using offline extracted service from CallLog: 'חשמלאי' (confidence: 0.95)
✅ [WEBHOOK] Using offline final_transcript (1234 chars) instead of realtime (567 chars)
✅ [WEBHOOK] Call completed webhook queued: phone=+972..., city=תל אביב, service=חשמלאי
```

## 📋 Files Modified
1. `server/tasks_recording.py` - Added explicit debug logs after DB commit
2. `server/media_ws_ai.py` - Reload fresh CallLog before webhook construction

## 🧪 Testing
After deployment:
1. Make a test call
2. Wait for offline worker to process (~30-60 seconds after call ends)
3. Check logs for the sequence above
4. Verify webhook receives high-quality transcript (longer, cleaner text)
5. Verify UI shows the offline transcript instead of realtime

## ⚠️ Important Notes
- The webhook is sent BEFORE the offline worker completes, so initially it will use realtime transcript
- This is expected behavior - the webhook can't wait for the worker
- The fix ensures that IF the worker has completed by the time webhook is sent, the fresh data is used
- For a complete solution where webhook always waits for offline transcript, we would need to:
  - Delay webhook sending until worker completes, OR
  - Send a second "updated" webhook after worker completes

## 🎯 Current Behavior
- **Realtime transcript** → Used immediately when call ends (for fast webhook delivery)
- **Offline transcript** → Used if worker completes before webhook is sent
- **Best quality** → Offline Whisper transcript (when available)

This fix ensures the system prefers offline transcript when available, while maintaining fast webhook delivery when it's not ready yet.
