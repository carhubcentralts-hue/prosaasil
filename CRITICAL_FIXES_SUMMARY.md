# Critical Fixes for Race Condition Handler

## Issues Addressed (Comment #3690267970)

### 1. ✅ ERROR Logging in DEBUG=1 (Minimal Mode)
**Status**: Already correct
- `force_print()` always logs errors regardless of DEBUG level
- `logger.exception()` always logs exceptions with traceback
- No changes needed - errors are never silenced

### 2. ✅ Handle Race with close_session()
**Issue**: If `close_session()` runs early (Twilio STOP), then `transcript.done` arrives late, `maybe_execute_hangup()` would try to execute on a closed session.

**Fix Applied**:
```python
# Check if session is closed (prevent race with close_session)
if getattr(self, 'closed', False):
    return
```

Added as first check in `maybe_execute_hangup()` to prevent execution after session closure.

### 3. ✅ Clear audio_done_by_response_id in close_session()
**Status**: Already implemented (line 8056)
```python
if hasattr(self, 'audio_done_by_response_id'):
    self.audio_done_by_response_id.clear()
```

This prevents stale response_id from previous calls triggering racefix incorrectly.

### 4. ✅ Handle Stuck Frames (300-500ms threshold)
**Issue**: In production, `tx_q.qsize()` sometimes stays at 1 due to thread shutdown, causing "said bye but won't disconnect" situation.

**Fix Applied**:
- Reduced stuck detection from 3 seconds to 500ms
- Changed `STUCK_THRESHOLD` from 30 to 5 iterations (5 * 100ms = 500ms)
- Check if `tx_running` is False (TX thread stopped)
- Proceed with hangup if TX thread is dead and frames are stuck
- Log warning when proceeding with stuck frames

**Code**:
```python
STUCK_THRESHOLD = 5  # 500ms without progress (5 * 100ms)

if stuck_iterations >= STUCK_THRESHOLD:
    tx_running = getattr(self, 'tx_running', False)
    if not tx_running:
        # TX thread stopped but queue has frames - proceed with hangup
        _orig_print(f"⚠️ [POLITE HANGUP] TX thread stopped with {tx_size} frames stuck - proceeding anyway", flush=True)
        break
```

## Updated Conditions in maybe_execute_hangup()

Now checks **8 conditions** (added session closure check):
1. ✅ Session not closed (`self.closed == False`)
2. ✅ `hangup_executed == False`
3. ✅ `pending_hangup == True`
4. ✅ `pending_hangup_response_id == response_id`
5. ✅ `active_response_status != "cancelled"`
6. ✅ `audio_done_by_response_id[response_id] == True`
7. ✅ `tx_q.empty()`
8. ✅ `realtime_audio_out_queue.empty()`

## Expected Behavior in Production

### Normal Goodbye Flow
```
[BOT_BYE_DETECTED] response_id=resp_abc123... text='ביי ולהתראות'
[POLITE_HANGUP] via=audio.done resp_id=resp_abc123...
[HANGUP] executed reason=bot_goodbye_bye_only call_sid=CA123...
```

### Race Condition Flow
```
[BOT_BYE_DETECTED] response_id=resp_abc123... text='ביי ולהתראות'
[POLITE_HANGUP] via=transcript.done_racefix resp_id=resp_abc123...
[HANGUP] executed reason=bot_goodbye_bye_only call_sid=CA123...
```

### Stuck Frames Flow
```
[BOT_BYE_DETECTED] response_id=resp_abc123... text='ביי ולהתראות'
⚠️ [POLITE HANGUP] TX thread stopped with 1 frames stuck - proceeding anyway
[POLITE_HANGUP] via=audio.done resp_id=resp_abc123...
[HANGUP] executed reason=bot_goodbye_bye_only call_sid=CA123...
```

### Condition Failure (DEBUG=0 only)
```
[BOT_BYE_DETECTED] response_id=resp_abc123... text='ביי ולהתראות'
[MAYBE_HANGUP] Conditions not met (via=audio.done): ['tx_empty']
```

## Troubleshooting Guide

If you see `[BOT_BYE_DETECTED]` but no `[POLITE_HANGUP]`:

1. **Check DEBUG=0 logs** for `[MAYBE_HANGUP] Conditions not met` message
2. **Most likely failures**:
   - `tx_empty`: Queue still has frames (should resolve with stuck frame fix)
   - `out_q_empty`: OpenAI queue still has frames (wait longer)
   - `audio_done`: audio.done event didn't arrive (OpenAI API issue)
   - `response_id_match`: Mismatch between pending and received response_id

3. **If stuck forever**:
   - Verify TX thread is running: `tx_running` should be True
   - Check if stuck frame detection kicked in (500ms threshold)
   - Verify queues are actually draining (not stuck at same size)

## Testing Checklist

- [ ] Normal flow: Bot says goodbye → disconnects within 2-3 seconds
- [ ] Race flow: audio.done before transcript.done → still disconnects
- [ ] Stuck frames: TX thread dies with frames in queue → disconnects anyway (500ms)
- [ ] Session closed: transcript.done after close_session → no exception, graceful return
- [ ] Cancelled response: User interrupts goodbye → no disconnect
- [ ] DEBUG=1: Only sees BOT_BYE_DETECTED, POLITE_HANGUP, errors
- [ ] DEBUG=0: Sees condition failures for debugging
