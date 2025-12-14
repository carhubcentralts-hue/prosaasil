# Manual Verification Guide - Post-Call Pipeline
# ================================================

This guide helps you verify the post-call pipeline is working correctly in production.

## 0️⃣ PREFLIGHT CHECKS (Before Making Test Calls)

### 0A. Database Migration - recording_sid Column

Run this SQL query in your database:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='call_log' AND column_name='recording_sid';
```

**Expected Result:**
```
 column_name   | data_type
---------------+------------------
 recording_sid | character varying
```

✅ **PASS:** Column exists
❌ **FAIL:** No rows returned → Run migration: `python -m server.db_migrate`

---

### 0B. ffmpeg Availability (Optional but Recommended)

Check if ffmpeg is installed:

```bash
# In backend container or server
ffmpeg -version
```

✅ **PASS:** Shows ffmpeg version
⚠️  **FALLBACK:** Not installed → Will use original audio (still works, just lower quality)

**To install (recommended):**
```bash
# Ubuntu/Debian
apt-get update && apt-get install -y ffmpeg

# Alpine (Docker)
apk add ffmpeg
```

---

### 0C. Webhook Configuration (Optional)

Check your webhook URLs are configured:

```sql
SELECT 
    tenant_id,
    inbound_webhook_url,
    outbound_webhook_url
FROM business_settings
LIMIT 3;
```

✅ **PASS:** URLs are configured (or intentionally empty)
⚠️  **INFO:** If empty, webhooks won't be sent (OK for testing)

---

## 1️⃣ INBOUND CALL TEST (10-20 seconds)

Make a short inbound call to your Twilio number.

### What to Check in Logs

After the call ends, search for these log patterns:

#### ✅ Required Success Messages:

```
✅ Recording started for {call_sid}: {recording_sid}
✅ [FINALIZE] Saved recording_sid: RE...
✅ handle_recording: Saved recording_sid RE... for {call_sid}
✅ [OFFLINE_STT] Processing recording: {call_sid}
✅ [OFFLINE_STT] Audio converted to optimal format (WAV 16kHz mono)
   (or: Using original audio file - if ffmpeg not available)
✅ [OFFLINE_STT] Transcript obtained: XXX chars for {call_sid}
✅ Saved final_transcript (XXX chars) for {call_sid}
✅ Extracted: service='...', city='...'
✅ [WEBHOOK] Webhook queued for call {call_sid}
```

#### ❌ Errors That Should NOT Appear:

```
❌ UndefinedColumn: column call_log.recording_sid
❌ 'property' object has no attribute 'ilike'
❌ Error closing websocket: Unexpected ASGI message 'websocket.close'
❌ Could not identify business for recording
```

---

## 2️⃣ DATABASE VERIFICATION

After making a test call, run this query:

```sql
SELECT 
    call_sid,
    recording_url,
    recording_sid,
    LENGTH(final_transcript) as transcript_chars,
    extracted_city,
    extracted_service,
    status,
    direction,
    created_at
FROM call_log
ORDER BY created_at DESC
LIMIT 3;
```

### Expected Results for Recent Call:

| Field | Expected Value |
|-------|----------------|
| `call_sid` | Should be populated (CA...) |
| `recording_url` | ✅ Should be populated (https://api.twilio.com/...) |
| `recording_sid` | ✅ Should be populated (RE...) **[NEW FIX]** |
| `transcript_chars` | ✅ Should be > 0 (e.g., 150) |
| `extracted_city` | Should have city name (or empty if not detected) |
| `extracted_service` | Should have service type (or empty if not detected) |
| `status` | Should be "processed" or "completed" |
| `direction` | Should be "inbound" or "outbound" |

---

## 3️⃣ OUTBOUND CALL TEST (Optional)

If you have outbound calling enabled, make a test outbound call.

### Same Checks Apply:

- Check logs for success messages
- Verify database has `recording_sid`, `final_transcript`, etc.
- Confirm `direction = 'outbound'`

---

## 4️⃣ WEBHOOK VERIFICATION (If Configured)

If you have webhook URLs configured, check your webhook receiver:

### Expected Webhook Payload:

```json
{
  "event": "call_completed",
  "call_id": "CA...",
  "business_id": 1,
  "direction": "inbound",
  "phone": "+1234567890",
  "duration_sec": 25,
  "transcript": "Full transcript text...",
  "summary": "Short summary...",
  "city": "Tel Aviv",
  "service_category": "Plumbing"
}
```

✅ **PASS:** Webhook received with all fields populated
⚠️  **WARNING:** Webhook not received → Check webhook URL configuration

---

## 5️⃣ SUCCESS CRITERIA

### ✅ ALL CRITICAL ITEMS MUST PASS:

- [ ] Database has `recording_sid` column
- [ ] No `UndefinedColumn` errors in logs
- [ ] No `'property' object has no attribute 'ilike'` errors
- [ ] No websocket double-close errors
- [ ] `recording_url` saved in DB
- [ ] `recording_sid` saved in DB (**NEW**)
- [ ] `final_transcript` has content (> 0 chars)
- [ ] Logs show offline STT processing
- [ ] No crashes in post-call pipeline

### ⚪ OPTIONAL ITEMS:

- [ ] ffmpeg installed (improves transcription quality)
- [ ] `extracted_city` populated
- [ ] `extracted_service` populated
- [ ] Webhook sent successfully

---

## 6️⃣ TROUBLESHOOTING

### Issue: recording_sid is NULL in database

**Possible Causes:**
1. Migration not run → Run `python -m server.db_migrate`
2. Old call from before fix → Make a new test call
3. Twilio not sending RecordingSid → Check Twilio webhook logs

---

### Issue: final_transcript is empty

**Possible Causes:**
1. Recording not downloaded → Check recording_url is valid
2. Offline worker not running → Check background workers
3. Audio file corrupt → Check recording is playable

---

### Issue: Still seeing old errors

**Possible Causes:**
1. Code not deployed → Verify latest code is running
2. Old logs cached → Clear log view and check new logs
3. Different instance → Ensure checking correct server/container

---

## 7️⃣ QUICK SMOKE TEST SCRIPT

Copy and paste this into your database tool:

```sql
-- Check migration
SELECT column_name FROM information_schema.columns 
WHERE table_name='call_log' AND column_name='recording_sid';

-- Check last 3 calls
SELECT 
    call_sid,
    CASE WHEN recording_url IS NOT NULL THEN '✅ YES' ELSE '❌ NO' END as has_recording_url,
    CASE WHEN recording_sid IS NOT NULL THEN '✅ YES' ELSE '❌ NO' END as has_recording_sid,
    CASE WHEN LENGTH(final_transcript) > 0 THEN '✅ YES' ELSE '❌ NO' END as has_transcript,
    extracted_city,
    extracted_service,
    status,
    created_at
FROM call_log
ORDER BY created_at DESC
LIMIT 3;
```

**Expected Output:**
```
 call_sid | has_recording_url | has_recording_sid | has_transcript | ...
----------+-------------------+-------------------+----------------+----
 CA123... | ✅ YES            | ✅ YES            | ✅ YES         | ...
```

---

## 8️⃣ DEPLOYMENT CHECKLIST

Before deploying to production:

- [ ] Run `verify_post_call_pipeline.py` script (code checks)
- [ ] Review migration #38 in `server/db_migrate.py`
- [ ] Backup database before migration
- [ ] Run migration: `python -m server.db_migrate`
- [ ] Verify migration success (check 0A above)
- [ ] Deploy code
- [ ] Restart services
- [ ] Make test inbound call
- [ ] Check logs (section 1)
- [ ] Check database (section 2)
- [ ] Confirm no errors appear

---

## 9️⃣ ROLLBACK PLAN (If Needed)

If something goes wrong:

### Code Rollback:
```bash
git revert e694ea6..6a4987f  # Revert all 6 commits
```

### Database Rollback (NOT RECOMMENDED):
```sql
-- Only if absolutely necessary (data loss risk)
ALTER TABLE call_log DROP COLUMN recording_sid;
```

**Note:** The migration only ADDS a column, doesn't modify existing data. Safe to keep.

---

## 🎯 SUMMARY

**Files Modified:**
- ✅ `server/db_migrate.py` - Migration #38
- ✅ `server/tasks_recording.py` - Business lookup fix
- ✅ `server/media_ws_ai.py` - Websocket guard + recording_sid save
- ✅ `server/routes_twilio.py` - Extract RecordingSid
- ✅ `server/services/lead_extraction_service.py` - Audio conversion

**Pipeline Flow:**
```
Call Ends → Webhook → Save recording_sid + URL
         → Worker → Download → Convert WAV 16kHz
         → Whisper → Summary → Extract → Webhook
```

**Status:** Ready for Production ✅
