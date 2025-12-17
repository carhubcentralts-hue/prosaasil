# TX Loop Purity Fix - Recording Trigger

## Issue
Original implementation had `threading.Thread(target=self._start_call_recording, daemon=True).start()` inside the `_tx_loop()` method, which violated the golden rule:

> "TX loop is Real-Time code. If an operation can take more than 1ms — it doesn't go in there."

Even though the recording itself ran in a background thread, **spawning the thread** from within the TX loop was still a violation.

## Root Cause
The TX loop had this code:
```python
if not _first_frame_sent:
    _first_frame_sent = True
    _orig_print(f"✅ [TX_LOOP] FIRST_FRAME_SENT...")
    # ❌ WRONG: Thread spawning in TX loop
    if not getattr(self, '_recording_started', False):
        self._recording_started = True
        threading.Thread(target=self._start_call_recording, daemon=True).start()
```

## Solution
Use a **flag-based trigger pattern**:

1. **TX loop sets a flag** (< 1μs operation):
   ```python
   if not _first_frame_sent:
       _first_frame_sent = True
       _orig_print(f"✅ [TX_LOOP] FIRST_FRAME_SENT...")
       # ✅ CORRECT: Just set a flag
       self._first_audio_sent = True
   ```

2. **Background thread checks flag and triggers recording**:
   ```python
   # In _realtime_audio_out_loop() - already a background thread
   if getattr(self, '_first_audio_sent', False) and not getattr(self, '_recording_started', False):
       self._recording_started = True
       _orig_print(f"✅ [AUDIO_OUT_LOOP] Starting recording...")
       threading.Thread(target=self._start_call_recording, daemon=True).start()
   ```

## TX Loop Purity Verification

### ✅ What TX loop contains now:
- `get frame` from queue (< 1ms)
- `send to Twilio` via WebSocket (< 1ms typically)
- `sleep(20ms)` for pacing
- Set flag `_first_audio_sent = True` (< 1μs)
- Lightweight logging (< 1ms)

### ❌ What was removed from TX loop:
- No `threading.Thread().start()` calls
- No REST/DB operations
- No heavy diagnostics (`traceback.print_stack()`)
- No queue flushing logic
- No session close logic

## Benefits

1. **TX loop stays real-time**: Only operations < 1ms
2. **Recording still deferred**: Starts after FIRST_AUDIO_SENT, not during greeting
3. **Clean separation**: TX loop = data flow, background threads = side effects
4. **No blocking**: Thread spawning happens outside hot path

## Files Modified
- `server/media_ws_ai.py`:
  - Lines 11878-11883 (TX loop - first location)
  - Lines 11902-11907 (TX loop - second location)
  - Lines 6753-6758 (`_realtime_audio_out_loop` - trigger point)

## Commit
- Hash: `3945198`
- Message: "Fix: Move recording trigger outside TX loop to background thread"

## Testing
Recording functionality unchanged - still starts after first audio sent. Only the trigger mechanism changed from direct thread spawn to flag-based trigger.

## Golden Rule Compliance ✅
**"TX loop = real-time. If operation > 1ms, it doesn't go there."**

TX loop is now 100% compliant with this rule.
