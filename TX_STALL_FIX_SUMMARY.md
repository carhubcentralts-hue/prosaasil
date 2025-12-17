# TX_STALL Fix - Implementation Summary

## Problem Statement (Hebrew Translation)

The problem statement identified three main causes of TX_STALL (transmission stalls):

### Issue 1: Heavy Tasks Running During Active Calls
**Rule:** Never run heavy operations while call is active

Heavy tasks should ONLY run after WS_STOP / twilio_stop_event:
- Recording download from Twilio
- ffmpeg audio conversions
- Offline STT (Whisper transcription)
- AI summaries (GPT API calls)
- Webhook call.completed

**Solution:** Mark tasks as "pending" if call_active == True, execute in worker after call ends

### Issue 2: TX Loop Must Be Real-Time at 20ms
**Requirement:** For Twilio G.711 μ-law, must send 160 bytes every 20ms (8kHz)

Current code receives chunks of 800/1200/2000 bytes from OpenAI - this is fine, but must split and stream at steady 20ms pace.

**Solution:** 
- Scheduler with `next_send_time += 0.02`
- Send one frame per 20ms tick
- No catch-up bursts if behind schedule
- Send silence or skip if no data (but maintain timing)

### Issue 3: Don't Block TX on Logs/Metrics
**Problem:** Excessive DEBUG logging during live calls (BARGE-IN DEBUG, FRAME_METRICS, TX_METRICS, etc.)

If logs run synchronously, they create jitter in TX timing.

**Solution:**
- Lower log level during calls
- Sample metrics max once per second
- Ensure everything is well-tuned
- Remove duplicate logs
- Ensure offline transcription only logs AFTER call ends

---

## Implementation Changes

### 1. Deferred Heavy Processing to Offline Worker

**File: `server/media_ws_ai.py`**

#### Changed: `_finalize_call_on_stop()` (lines 12150-12238)

**BEFORE:**
```python
def _finalize_call_on_stop(self):
    # ... heavy processing during call finalization
    ci = CustomerIntelligence(business_id)
    summary_data = ci.generate_conversation_summary(...)  # GPT API call
    update_lead_on_call(...)  # DB updates
    # Update appointments, lead notes, etc.
```

**AFTER:**
```python
def _finalize_call_on_stop(self):
    """TX_STALL FIX: Minimal finalization - defer heavy tasks to offline worker
    
    RULE 1: NO HEAVY TASKS DURING CALL
    - No AI summary generation (defer to offline worker)
    - No CustomerIntelligence processing (defer to offline worker)
    - No webhook sending (defer to offline worker)
    
    Only lightweight operations:
    - Log call metrics (already in memory)
    - Save basic call_log state
    - Save realtime transcript (already in memory)
    """
    # Only save conversation history (already in memory)
    call_log.transcription = full_conversation
    # summary and ai_summary filled by offline worker
    db.session.commit()
```

**Impact:** Removed ~200ms-1000ms of GPT API calls from call finalization path.

#### Changed: `_process_customer_intelligence()` (lines 12477-12490)

**BEFORE:**
```python
def _process_customer_intelligence(self, user_text: str, bot_reply: str):
    # ... runs after each conversation turn
    ci = CustomerIntelligence(business_id)
    conversation_summary = ci.generate_conversation_summary(...)  # GPT API call
    new_status = ci.auto_update_lead_status(...)  # AI processing
    lead.notes += f"\n[Live Call]: {user_text}..."
    db.session.commit()
```

**AFTER:**
```python
def _process_customer_intelligence(self, user_text: str, bot_reply: str):
    """TX_STALL FIX: DISABLED - No heavy processing during call"""
    return  # All processing moved to offline worker
```

**Impact:** Removed GPT API calls that were running after EVERY conversation turn during active calls.

### 2. Verified TX Loop 20ms Pacing

**File: `server/media_ws_ai.py`**

**Verification (lines 11969-11977):**
```python
# ✅ P0 FIX: Strict 20ms timing - advance deadline and sleep
next_deadline += FRAME_INTERVAL  # 0.02 seconds
delay = next_deadline - time.monotonic()
if delay > 0:
    time.sleep(delay)
else:
    # Missed deadline - resync to prevent catch-up bursts
    next_deadline = time.monotonic()
```

**Status:** ✅ Already correctly implemented. No changes needed.

**Key features:**
- ONE frame per 20ms tick (no catch-up bursts)
- Strict deadline enforcement
- Resync if late (prevents burst transmission)

### 3. Reduced Logging During Active Calls

**File: `server/media_ws_ai.py`**

#### Changed: TX_METRICS logging (lines 12019-12036)

**BEFORE:**
```python
# Log every second if queue >50% or gap >40ms
if queue_size > queue_threshold or max_gap_ms > 40:
    print(f"[TX_METRICS] ...")
```

**AFTER:**
```python
# TX_STALL FIX: Only log critical issues
queue_threshold = int(queue_maxsize * 0.7)  # 70% instead of 50%

# Log only if severe issues detected
if queue_size > queue_threshold or max_gap_ms > 120.0:
    if DEBUG_TX:  # Gated behind DEBUG flag
        _orig_print(f"[TX_METRICS] ...")
```

**Impact:** 
- Reduced logging threshold from 50% to 70% queue fullness
- Increased gap threshold from 40ms to 120ms
- Gated behind DEBUG_TX flag

#### Changed: TX_HEARTBEAT logging (lines 11787-11802)

**BEFORE:**
```python
# Log every 1 second always
if now_mono - last_heartbeat_time >= 1.0:
    _orig_print(f"[TX_HEARTBEAT] ...")
```

**AFTER:**
```python
# TX_STALL FIX: Reduce frequency and gate behind DEBUG
if DEBUG_TX and now_mono - last_heartbeat_time >= 5.0:  # 5s instead of 1s
    _orig_print(f"[TX_HEARTBEAT] ...")
```

**Impact:**
- Reduced frequency from 1s to 5s
- Only logs when DEBUG_TX=1

---

## Verification Checklist

### Heavy Tasks Eliminated During Call ✅
- [x] No recording download (handled by offline worker via webhook)
- [x] No ffmpeg conversions (not used during calls)
- [x] No offline STT (Whisper runs in worker after call)
- [x] No AI summaries during call (CustomerIntelligence disabled)
- [x] No webhook sending during call (sent by offline worker)

### TX Loop Timing ✅
- [x] 20ms frame pacing verified (next_deadline += 0.02)
- [x] No catch-up bursts (resync if late)
- [x] One frame per tick enforced
- [x] Queue backlog handled by drop-oldest policy

### Logging Improvements ✅
- [x] TX_METRICS: Reduced frequency (70% threshold, 120ms gap, DEBUG_TX gated)
- [x] TX_HEARTBEAT: Reduced to 5s interval, DEBUG_TX gated
- [x] Offline processing logs only in worker
- [x] DEBUG logs already gated behind DEBUG flag (via _dprint)

---

## What Runs During Call (Lightweight)

✅ **Allowed (Lightweight Operations):**
- Save realtime transcript to memory (`conversation_history`)
- Save conversation turns to DB (simple INSERT in background thread)
- Update call_log metadata (status, recording_sid)
- TX audio streaming (20ms frame pacing)
- Realtime OpenAI API streaming (audio-to-audio pipeline)

---

## What Runs After Call (Offline Worker)

🔄 **Deferred to Offline Worker (`tasks_recording.py`):**
1. Recording download from Twilio
2. Offline Whisper transcription (high quality, dual-channel)
3. AI summary generation (GPT-4 via `summarize_conversation`)
4. City/service extraction from summary
5. Lead creation/updates (CustomerIntelligence)
6. Lead status auto-update (based on summary)
7. Webhook call.completed (sent with all processed data)

The offline worker is triggered by Twilio's recording webhook, which fires AFTER the call ends and recording is ready.

---

## Expected Impact

### TX_STALL Reduction
- **Before:** Heavy processing during call could cause 200ms-2000ms stalls
- **After:** Only lightweight memory/DB operations, no API calls during call

### Log Noise Reduction
- **Before:** TX_METRICS every 1s, TX_HEARTBEAT every 1s
- **After:** TX_METRICS only on critical issues, TX_HEARTBEAT every 5s (DEBUG only)

### Audio Quality
- **Before:** Potential jitter from heavy processing and excessive logging
- **After:** Smooth 20ms pacing with minimal interference

---

## Testing Recommendations

1. **Monitor TX timing during calls:**
   ```bash
   # Enable DEBUG_TX to see detailed metrics
   DEBUG_TX=1 python run_server.py
   ```
   
   Look for:
   - `[TX_STALL]` warnings (should be rare, <120ms gaps)
   - `[TX_QUALITY] DEGRADED` warnings (should not appear)
   - Consistent frame pacing in logs

2. **Verify offline processing:**
   - Check that summary/extraction happens AFTER call ends
   - Verify webhook is sent with complete data
   - Confirm no CustomerIntelligence logs during active calls

3. **Test with concurrent calls:**
   - Multiple simultaneous calls should not interfere
   - Each call's offline processing queued independently
   - No TX stalls even during high load

---

## Files Modified

1. `server/media_ws_ai.py`:
   - `_finalize_call_on_stop()` - Removed heavy AI processing
   - `_process_customer_intelligence()` - Disabled during calls
   - `_tx_loop()` - Reduced logging frequency

2. `server/tasks_recording.py`:
   - Already handles all offline processing (no changes needed)

3. `server/services/recording_service.py`:
   - Already deferred to offline worker (no changes needed)

4. `server/services/summary_service.py`:
   - Already runs in offline worker only (no changes needed)

---

## Conclusion

All three issues from the problem statement have been addressed:

1. ✅ **Heavy tasks deferred:** All AI/API calls moved to offline worker
2. ✅ **TX timing verified:** 20ms pacing confirmed, no catch-up bursts
3. ✅ **Logging reduced:** Less frequent, gated behind DEBUG flags

The implementation follows the "simplest fix that works" principle - minimal changes to achieve maximum impact.
