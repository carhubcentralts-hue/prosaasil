# 🔥 FIX: Call Completion Webhook Not Being Sent

## Problem Summary

**Issue**: Webhooks were not being sent at the end of calls, despite the logs showing successful offline processing.

**Symptoms**:
- Logs showed: `✅ [OFFLINE_STT] Completed processing for {call_sid}`
- But no webhook logs like `[WEBHOOK] Preparing...` or `[WEBHOOK] ✅ Success`
- External systems (n8n, Zapier, etc.) were not receiving call completion notifications

**Root Cause**: The `process_recording_async()` function in `tasks_recording.py` completed all offline processing (transcription, summary, extraction) but **never called** `send_call_completed_webhook()` at the end of the pipeline.

---

## Solution Implemented

### 1. Added Webhook Call to Offline Worker Pipeline

**File**: `server/tasks_recording.py`

Added webhook sending at the end of `process_recording_async()` function (after line 303):

```python
# 🔥 5. Send call_completed webhook - CRITICAL FIX!
try:
    from server.services.generic_webhook_service import send_call_completed_webhook
    # ... fetch call details from DB ...
    
    webhook_sent = send_call_completed_webhook(
        business_id=business.id,
        call_id=call_sid,
        phone=call_log.from_number,
        direction=call_log.direction or "inbound",
        # ... all other fields ...
    )
except Exception as webhook_err:
    # Don't fail pipeline if webhook fails - just log
    log.error(f"[WEBHOOK] Failed to send webhook: {webhook_err}")
```

**Key Features**:
- Webhook is sent AFTER all processing completes (transcription → summary → extraction)
- Properly handles call direction (inbound vs outbound)
- Fails gracefully - webhook errors don't crash the entire pipeline
- Comprehensive error logging

---

### 2. Enhanced Webhook Routing Logic

**File**: `server/services/generic_webhook_service.py`

Improved the existing inbound/outbound routing logic with better logging:

**Inbound Calls**:
- Uses `inbound_webhook_url` if configured
- Falls back to `generic_webhook_url` if inbound URL not set
- Skips webhook if neither is configured

**Outbound Calls**:
- Uses ONLY `outbound_webhook_url` - **no fallback**
- Skips webhook if not configured (prevents outbound calls from "contaminating" inbound webhooks)

**Code**:
```python
if direction == "outbound":
    # ONLY use outbound_webhook_url - no fallback
    webhook_url = settings.outbound_webhook_url
    if not webhook_url:
        print(f"[WEBHOOK] ⚠️ No outbound webhook URL - skipping")
        return False
        
elif direction == "inbound":
    # Use inbound_webhook_url, fallback to generic
    webhook_url = settings.inbound_webhook_url or settings.generic_webhook_url
```

---

### 3. Comprehensive Logging

Added detailed logging at every step:

**Before webhook send**:
```
[WEBHOOK] 📞 send_call_completed_webhook called:
[WEBHOOK]    call_id=CA..., business_id=10, direction=inbound
[WEBHOOK]    phone=+972..., city=בית שאן, service=שיווק נכס
[WEBHOOK]    duration=26s, transcript=141 chars, summary=582 chars
[WEBHOOK] ✅ Using inbound_webhook_url for business 10: https://...
[WEBHOOK] 📦 Payload preview (1234 bytes): {"event_type":"call.completed",...}
```

**During send**:
```
[WEBHOOK] Sending call.completed to https://... (attempt 1)
```

**After send**:
```
[WEBHOOK] ✅ Success: call.completed sent to webhook
[WEBHOOK]    Status: 200, Response: {"success":true}
```

---

## Database Schema

The `BusinessSettings` table already has the required fields (added in BUILD 183):

```sql
-- Inbound calls webhook (with fallback to generic)
inbound_webhook_url VARCHAR(512) NULL

-- Outbound calls webhook (NO fallback - only sent if configured)
outbound_webhook_url VARCHAR(512) NULL

-- Generic webhook (used as fallback for inbound if inbound_webhook_url is null)
generic_webhook_url VARCHAR(512) NULL
```

---

## Call Flow (Complete Pipeline)

### Realtime Phase (During Call)
1. Twilio → `/webhook/call_status`
2. WebSocket stream → OpenAI Realtime API
3. Conversation happens
4. Call ends → `[CLEAN PIPELINE] Call ended - realtime handler done`
5. **NO webhook sent here** - delegated to worker

### Offline Phase (After Call - Worker)
1. Recording job enqueued → `RECORDING_QUEUE`
2. Worker picks up job → `process_recording_async()`
3. **Step 1**: Download recording (if needed)
4. **Step 2**: Whisper transcription → `final_transcript`
5. **Step 3**: GPT summary generation
6. **Step 4**: City/Service extraction from summary
7. **Step 5**: Save to database
8. **🔥 Step 6 (NEW)**: Send webhook with complete data
   - Includes: transcript, summary, city, service, duration, etc.
   - Routed correctly by direction (inbound vs outbound)

---

## Testing Guide

### Test 1: Inbound Call Webhook

1. Configure `inbound_webhook_url` in BusinessSettings for your business
2. Make an inbound test call
3. Check logs for:
   ```
   [WEBHOOK] 📞 send_call_completed_webhook called:
   [WEBHOOK]    direction=inbound
   [WEBHOOK] ✅ Using inbound_webhook_url for business X
   [WEBHOOK] ✅ Success: call.completed sent to webhook
   ```
4. Verify webhook received in n8n/Zapier with proper payload

### Test 2: Outbound Call Webhook

1. Configure `outbound_webhook_url` in BusinessSettings
2. Make an outbound test call
3. Check logs for:
   ```
   [WEBHOOK]    direction=outbound
   [WEBHOOK] ✅ Using outbound_webhook_url for business X
   [WEBHOOK] ✅ Success: call.completed sent to webhook
   ```
4. Verify it does NOT go to inbound_webhook_url

### Test 3: No Webhook URL Configured

1. Remove both inbound and outbound webhook URLs
2. Make a call
3. Check logs for:
   ```
   [WEBHOOK] ⚠️ No inbound/generic webhook URL configured - skipping webhook send
   ```
4. Verify offline processing still completes successfully (webhook is optional)

---

## Payload Example

```json
{
  "event_type": "call.completed",
  "timestamp": "2025-12-10T14:23:45Z",
  "business_id": "10",
  "call_id": "CA9dd13ec4fcb895203d2162ca7e0297fc",
  "lead_id": "123",
  "phone": "+972501234567",
  "customer_name": "",
  "direction": "inbound",
  "city": "בית שאן",
  "service_category": "שיווק נכס",
  "started_at": "2025-12-10T14:23:19Z",
  "ended_at": "2025-12-10T14:23:45Z",
  "duration_sec": 26,
  "transcript": "היי, זה מאתר המנולן...",
  "summary": "### סוג הפנייה והתחום...",
  "agent_name": "Assistant",
  "metadata": {}
}
```

---

## Files Changed

1. **`server/tasks_recording.py`** - Added webhook call at end of pipeline (lines ~303-360)
2. **`server/services/generic_webhook_service.py`** - Enhanced logging (lines ~71-110, ~208-212, ~136-140)

---

## Known Limitations

1. **Webhook is sent AFTER offline processing** - not immediately when call ends (typically 5-30 seconds delay)
   - This is by design - we want complete data (transcript, summary, extraction)
   - If immediate notification is needed, add a separate "call.ended" event earlier

2. **Only successful calls with recordings send webhooks**
   - Failed calls (no-answer, busy, failed, canceled) do NOT send call.completed webhooks
   - This is correct behavior - these calls have no transcript/summary to send
   - If you need notifications for failed calls, add separate event handling in `/webhook/call_status`

3. **Outbound calls without outbound_webhook_url** - no webhook sent
   - This is intentional - prevents mixing inbound/outbound data
   - Configure outbound_webhook_url if you need outbound notifications

4. **Webhook failures don't retry** - fires once with 3 HTTP retries
   - If all 3 attempts fail, webhook is lost (not persisted for later retry)
   - External system should implement idempotency based on call_id

---

## Success Criteria

✅ Every completed call sends exactly one webhook (or zero if not configured)  
✅ Inbound calls go to `inbound_webhook_url` (or `generic_webhook_url` fallback)  
✅ Outbound calls go ONLY to `outbound_webhook_url` (no fallback)  
✅ Webhook includes complete call data (transcript, summary, city, service)  
✅ Webhook failures are logged but don't crash the pipeline  
✅ Clear logs make debugging easy  

---

## Maintenance Notes

- Webhook sending happens in `tasks_recording.py` line ~303-360
- Routing logic in `generic_webhook_service.py` line ~71-89
- To add new webhook types: extend `send_generic_webhook()` function
- To change payload structure: modify `send_call_completed_webhook()` data dict

---

**Status**: ✅ FIXED - Ready for testing  
**Build**: Custom fix for webhook completion issue  
**Date**: December 10, 2025
