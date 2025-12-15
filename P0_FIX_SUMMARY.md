# P0 Fix: Audio Loop Blocking & Barge-in Issues

## Problem Summary (from logs5006.rtf)

### Issue 1: Audio Jitter/Stalls (3-5.6 second gaps)
**Symptoms:**
- TX_METRICS showing max_gap_ms of 3013ms, 5602ms, 5648ms
- Audio comes out in bursts, causing choppy calls
- Most noticeable in outbound calls

**Root Cause:**
- Blocking I/O operations (Twilio REST API calls, DB commits) in audio loops
- These sync operations block the event loop, causing audio to queue up
- When unblocked, audio plays in a burst (the "boom" effect)

### Issue 2: Barge-in Not Working (barge_in_events=0)
**Symptoms:**
- CALL_METRICS showing barge_in_events=0
- Users cannot interrupt AI during responses
- AI keeps talking even when user tries to speak

**Root Cause:**
- Audio blocked before VAD (Voice Activity Detection) could process it
- OpenAI's server-side VAD never received audio during greeting
- No speech_started events → no barge-in triggers

## Solutions Implemented

### Fix 1: Move Blocking Operations to Background Threads

#### Changed Locations:
1. **Line ~2796** (audio sender loop):
   - **Before:** `twilio_client.calls(self.call_sid).update(status='completed')` - BLOCKING!
   - **After:** Wrapped in `terminate_call_async()` → background thread
   - **Impact:** Audio loop no longer blocked during call termination

2. **Line ~9358** (auto-hangup):
   - **Before:** `client.calls(self.call_sid).update(status='completed')` - BLOCKING!
   - **After:** Wrapped in `hangup_async()` → background thread
   - **Impact:** Auto-hangup no longer blocks call handling

3. **Line ~6270** (appointment creation):
   - **Before:** `db.session.commit()` - BLOCKING!
   - **After:** `update_call_session_async()` → background thread with fresh app context
   - **Impact:** Appointment confirmation no longer blocks audio loop

### Fix 2: Enable VAD Before Gating

#### Changed Location:
**Line ~2707** (audio sender to OpenAI):
- **Before:** 
  ```python
  if self.greeting_mode_active and not self.greeting_completed:
      # Block audio - don't send to OpenAI
      continue
  ```
- **After:** 
  ```python
  # 🔥 P0 FIX: VAD MUST RUN BEFORE GATING
  # ALWAYS send audio to OpenAI so VAD can run
  # Handle greeting protection via event filtering
  ```
- **Impact:** OpenAI's VAD now receives all audio, can detect speech during greeting

### Fix 3: Enhanced Monitoring & Logging

#### Added Logging:
1. **Line ~11508**: BLOCKING_DETECTED alerts
   ```
   🚨 BLOCKING_DETECTED max_gap_ms={X}ms (threshold=200ms)
   ```

2. **Line ~3469**: Barge-in candidate detection
   ```
   [BARGE_IN] candidate vad_frames={X} rms={Y} noise_floor={Z}
   ```

3. **Line ~3562**: Cancel event sent
   ```
   [BARGE_IN] cancel sent response_id={ID}
   ```

4. **Line ~3603**: TX queue flush
   ```
   [BARGE_IN] tx_flush cleared_frames={X}
   ```

5. **Line ~3224**: Post-cancel audio violations
   ```
   [BARGE_IN] post_cancel_audio_violation response_id={ID}
   ```

## Expected Results

### Before Fix:
```
[TX_METRICS] max_gap_ms=3013ms  # 3+ second gap!
[TX_METRICS] max_gap_ms=5602ms  # 5+ second gap!
[CALL_METRICS] barge_in_events=0  # Not working
```

### After Fix:
```
[TX_METRICS] fps=50.0, max_gap_ms=45ms  # Smooth audio
[CALL_METRICS] barge_in_events=5  # Working!
# No BLOCKING_DETECTED warnings
```

## Testing Instructions

### 1. Monitor TX_METRICS
Look for smooth audio delivery:
```bash
grep "TX_METRICS" logs.txt | tail -20
```
**Expected:** fps ≈ 50, max_gap_ms < 60ms

### 2. Monitor CALL_METRICS
Look for working barge-in:
```bash
grep "CALL_METRICS" logs.txt
```
**Expected:** barge_in_events > 0

### 3. Check for Blocking
Look for blocking detection:
```bash
grep "BLOCKING_DETECTED" logs.txt
```
**Expected:** No results (no blocking!)

### 4. Test Barge-in Scenarios

#### Test A: Interrupt Greeting
1. Start call
2. While AI greeting plays, start talking
3. **Expected:** AI stops, starts listening to user

#### Test B: Interrupt Response
1. Ask AI a question
2. While AI responds, start talking
3. **Expected:** AI stops mid-sentence, starts listening

#### Test C: Outbound Calls
1. Make outbound call
2. Monitor for jitter/gaps
3. **Expected:** Smooth audio, no gaps > 60ms

## Verification Checklist

- [ ] TX_METRICS shows fps ≈ 50
- [ ] TX_METRICS shows max_gap_ms < 60ms consistently
- [ ] No BLOCKING_DETECTED warnings in logs
- [ ] CALL_METRICS shows barge_in_events > 0
- [ ] Can interrupt greeting
- [ ] Can interrupt AI responses
- [ ] Outbound calls are smooth
- [ ] No audio choppy/"boom" effect

## Technical Details

### Thread Safety
All background operations use proper Flask app contexts:
```python
app = _get_flask_app()  # Singleton
with app.app_context():
    # DB operations here
```

### Barge-in Flow
1. User speaks → OpenAI detects → `speech_started` event
2. Check if AI is speaking → Yes → Trigger barge-in
3. Send `response.cancel` to OpenAI
4. Flush TX queue (clear pending audio)
5. Filter any audio deltas from cancelled response
6. Let user speech through

### Why Greeting Block Was Removed
**Old logic:** Block audio during greeting to prevent cancellation
**Problem:** VAD never sees audio → Can't detect barge-in
**New logic:** Always send audio, handle barge-in at event level
**Result:** VAD runs first, barge-in works, greeting protection via event filtering

## Files Modified

- `server/media_ws_ai.py` - Main WebSocket audio handler

## Commits

1. `P0 fix: Move Twilio REST calls to background threads`
2. `P0 fix: Enable barge-in by removing audio blocking before VAD`
3. `P0 fix: Move appointment DB commit to background thread`
4. `Code review fixes: Remove redundant imports and fix DB session thread-safety`

## Support

If issues persist:
1. Collect full logs with TX_METRICS and CALL_METRICS
2. Note specific call_sid where issues occur
3. Check for BLOCKING_DETECTED warnings
4. Verify barge_in_events in CALL_METRICS
