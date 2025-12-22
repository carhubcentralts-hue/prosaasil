# Call Recording Pipeline Fix - Full Documentation

## Overview
This fix addresses critical issues with call recording in the Twilio-based system where recordings were starting mid-call, missing the beginning of conversations, and sometimes failing to generate transcripts or summaries.

## Problem Statement (Original in Hebrew)

### Main Issues Reported:
1. **Recording starts in the middle** - Calls were being recorded only after the stream ended, missing the beginning
2. **Missing transcripts/summaries** - Sometimes no transcript or summary was generated
3. **UI shows "stuck" status** - Calls appeared incomplete in the interface
4. **Webhooks not captured** - Recording completion webhooks weren't being processed properly

### Root Causes:
- Recording relied on TwiML `<Record>` which started AFTER the stream ended
- No deterministic pipeline tracking for recording → transcript → summary
- No retry mechanism for failed stages
- No status visibility in the UI

## Solution Implemented

### 1. Start Full Call Recording from Second 0 (✅ FIXED)

**Before:**
```python
# Recording started AFTER stream ended in stream_ended webhook
def stream_ended():
    threading.Thread(target=_trigger_recording_for_call, args=(call_sid,), daemon=True).start()
```

**After:**
```python
# Recording starts IMMEDIATELY when call connects via Twilio REST API
def incoming_call():
    # ... TwiML response ...
    
    # 🔥 Start recording in background (non-blocking)
    if call_sid:
        threading.Thread(
            target=_start_full_call_recording,
            args=(call_sid, host),
            daemon=True
        ).start()

def _start_full_call_recording(call_sid, host):
    """Start recording from second 0"""
    client = Client(account_sid, auth_token)
    recording = client.calls(call_sid).recordings.create(
        recording_channels='dual',  # Separate customer/AI tracks
        recording_status_callback=f"https://{host}/webhook/handle_recording",
        recording_status_callback_event=['completed']
    )
```

**Key Changes:**
- Recording starts via REST API immediately when call connects
- Uses `recording_channels='dual'` for better quality (separate customer/AI tracks)
- Properly configured `recordingStatusCallback` for completion notification
- Removed `record=True` from outbound call creation (now handled by REST API)

### 2. Add Pipeline Status Tracking (✅ FIXED)

**New Database Fields (Migration 44):**
```python
class CallLog(db.Model):
    # Status fields for deterministic tracking
    recording_status = db.Column(db.String(32), default="pending")  # pending | recording | completed | failed
    transcript_status = db.Column(db.String(32), default="pending")  # pending | processing | completed | failed
    summary_status = db.Column(db.String(32), default="pending")  # pending | processing | completed | failed
    last_error = db.Column(db.Text, nullable=True)  # Error message if any stage failed
    retry_count = db.Column(db.Integer, default=0)  # Number of retry attempts
```

**Status Flow:**
```
Call Started
  ↓
recording_status: pending → recording (REST API call) → completed (webhook)
  ↓
transcript_status: pending → processing (worker starts) → completed/failed
  ↓
summary_status: pending → processing (summary gen) → completed/failed
```

### 3. Error Handling & Status Updates (✅ FIXED)

**Recording Start:**
```python
def _start_full_call_recording(call_sid, host):
    try:
        # Check for duplicate (prevent double recording)
        if call_log.recording_status == 'recording':
            return
        
        # Start recording
        recording = client.calls(call_sid).recordings.create(...)
        
        # Update status immediately
        call_log.recording_status = 'recording'
        call_log.recording_sid = recording.sid
        db.session.commit()
        
    except Exception as e:
        # Handle "already recording" error gracefully
        if '21220' in str(e) or 'already being recorded' in str(e).lower():
            logger.info("Already recording (duplicate request ignored)")
        else:
            # Update DB with failure
            call_log.recording_status = 'failed'
            call_log.last_error = f"Recording start failed: {str(e)[:500]}"
            db.session.commit()
```

**Recording Completion Webhook:**
```python
def handle_recording():
    # ... extract form data ...
    
    if rec_status == 'completed':
        call_log.recording_status = 'completed'
        db.session.commit()
    
    # Queue for transcription
    enqueue_recording(form_copy)
```

**Transcript Processing:**
```python
def process_recording_async(form_data):
    # Update status to processing
    call_log.transcript_status = 'processing'
    db.session.commit()
    
    try:
        final_transcript = transcribe_recording_with_whisper(audio_file, call_sid)
        
        if final_transcript and len(final_transcript) > 10:
            call_log.transcript_status = 'completed'
        else:
            call_log.transcript_status = 'failed'
            call_log.last_error = 'Empty transcript returned'
    except Exception as e:
        call_log.transcript_status = 'failed'
        call_log.last_error = f"Transcript failed: {str(e)[:500]}"
```

**Summary Generation:**
```python
try:
    summary = summarize_conversation(source_text, call_sid, business_type, business_name)
    if summary and len(summary) > 0:
        call_log.summary_status = 'completed'
    else:
        call_log.summary_status = 'failed'
        call_log.last_error = 'Summary generation returned empty'
except Exception as e:
    call_log.summary_status = 'failed'
    call_log.last_error = f"Summary failed: {str(e)[:500]}"
```

## Migration 44 - Pipeline Status Fields

```sql
-- Add status tracking fields
ALTER TABLE call_log 
ADD COLUMN recording_status VARCHAR(32) DEFAULT 'pending',
ADD COLUMN transcript_status VARCHAR(32) DEFAULT 'pending',
ADD COLUMN summary_status VARCHAR(32) DEFAULT 'pending',
ADD COLUMN last_error TEXT,
ADD COLUMN retry_count INTEGER DEFAULT 0;

-- Update existing calls with inferred status
UPDATE call_log SET
    recording_status = CASE
        WHEN recording_url IS NOT NULL THEN 'completed'
        WHEN recording_sid IS NOT NULL THEN 'recording'
        ELSE 'pending'
    END,
    transcript_status = CASE
        WHEN final_transcript IS NOT NULL AND LENGTH(final_transcript) > 50 THEN 'completed'
        WHEN transcription IS NOT NULL AND LENGTH(transcription) > 50 THEN 'completed'
        ELSE 'pending'
    END,
    summary_status = CASE
        WHEN summary IS NOT NULL AND LENGTH(summary) > 20 THEN 'completed'
        ELSE 'pending'
    END
WHERE recording_status = 'pending';  -- Only update rows not explicitly set
```

## Files Changed

### Backend Changes:
1. **server/routes_twilio.py**
   - Added `_start_full_call_recording()` function with duplicate prevention
   - Updated `incoming_call()` to start recording immediately
   - Updated `outbound_call()` to start recording immediately
   - Updated `handle_recording()` to set `recording_status='completed'`
   - Added comprehensive error handling

2. **server/models_sql.py**
   - Added 5 new fields to `CallLog` model:
     - `recording_status`, `transcript_status`, `summary_status`
     - `last_error`, `retry_count`

3. **server/db_migrate.py**
   - Created Migration 44 for pipeline status fields
   - Includes status inference for existing calls

4. **server/tasks_recording.py**
   - Updated `process_recording_async()` to track `transcript_status`
   - Updated `save_call_to_db()` to track `summary_status`
   - Added error handling for transcript failures
   - Added error handling for summary failures

5. **server/routes_outbound.py**
   - Removed `record=True` from call creation (now handled by REST API)

## Benefits

### ✅ Complete Call Recording
- **Recording starts from second 0** - No more missing beginnings
- **Dual-channel recording** - Better quality, separate customer/AI tracks
- **Guaranteed coverage** - REST API ensures recording starts immediately

### ✅ Deterministic Pipeline
- **Status tracking** - Know exactly where each call is in the pipeline
- **Error tracking** - `last_error` shows what went wrong
- **Retry support** - `retry_count` enables automatic retries

### ✅ Better Visibility
- **Clear status** - pending | recording | completed | failed
- **Error messages** - Detailed error information in `last_error`
- **Progress tracking** - See transcript and summary status separately

### ✅ Robust Error Handling
- **Duplicate prevention** - Won't try to record the same call twice
- **Graceful failures** - Errors are tracked, not silent
- **Comprehensive logging** - All failure paths are logged

## Next Steps (Not Yet Implemented)

### UI Changes Needed:
1. **Call Cards** - Display status indicators:
   ```
   📹 Recording: ✅ Completed
   📝 Transcript: ⏳ Processing
   📋 Summary: ❌ Failed [Retry]
   ```

2. **Status Badges** - Color-coded status indicators:
   - 🟢 Green: completed
   - 🟡 Yellow: processing/recording
   - 🔴 Red: failed
   - ⚪ Gray: pending

3. **Retry Buttons** - Allow manual retry of failed stages:
   ```tsx
   {call.transcript_status === 'failed' && (
     <Button onClick={() => retryTranscript(call.id)}>
       Retry Transcript
     </Button>
   )}
   ```

4. **Leads Page** - Show call status by phone number
5. **Recording Player** - Only show player when `recording_status === 'completed'`

## Testing Checklist

### ✅ Backend (Completed)
- [x] REST API recording starts immediately
- [x] Duplicate recording prevention works
- [x] Status fields track progress correctly
- [x] Error tracking captures failures
- [x] Migration adds fields correctly

### ⏳ Integration Testing (Pending)
- [ ] Inbound call records from second 0
- [ ] Outbound call records from second 0
- [ ] Recording webhook updates status correctly
- [ ] Transcript processing updates status
- [ ] Summary generation updates status
- [ ] Failed stages show error in `last_error`
- [ ] Retry mechanism works (when implemented)

### ⏳ UI Testing (Pending)
- [ ] Status indicators display correctly
- [ ] Retry buttons work for failed stages
- [ ] Leads page shows call statuses by phone
- [ ] Recording player only shows for completed recordings

## Deployment Notes

1. **Run Migration 44** before deploying code changes:
   ```bash
   python -m server.db_migrate
   ```

2. **Verify Twilio Credentials** are set:
   ```bash
   echo $TWILIO_ACCOUNT_SID
   echo $TWILIO_AUTH_TOKEN
   ```

3. **Check webhook URLs** are accessible:
   - `https://your-domain/webhook/handle_recording` (for recording completion)
   - `https://your-domain/webhook/call_status` (for call completion)

4. **Monitor logs** for recording start messages:
   ```
   ✅ [RECORDING] Started from second 0 for CAxxxx, recording_sid=RExxxx
   ```

5. **Verify status updates** in database:
   ```sql
   SELECT call_sid, recording_status, transcript_status, summary_status, last_error 
   FROM call_log 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```

## Troubleshooting

### Recording not starting
- Check Twilio credentials are set
- Verify call_sid is valid
- Check logs for "Recording start failed" errors
- Verify webhook URL is accessible from Twilio

### Status stuck in "recording"
- Check if recording webhook is being received
- Verify `handle_recording` endpoint is working
- Check `recording_status` field in database

### Status stuck in "processing"
- Check offline worker is running
- Verify recording file was downloaded
- Check logs for transcript/summary errors
- Review `last_error` field in database

### Multiple recordings for same call
- This should be prevented by duplicate check
- If it happens, check logs for "Already recording" messages
- Verify `recording_status` is being checked correctly

## References

- **Twilio Recording API**: https://www.twilio.com/docs/voice/api/recording
- **Best Practices**: Start recording via REST API for complete coverage
- **Dual-Channel Recording**: Provides separate tracks for better transcription quality

## Author
Fix implemented as part of PR addressing Hebrew issue report about call recording problems.
