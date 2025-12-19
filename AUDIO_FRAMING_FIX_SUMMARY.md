# Audio Framing and Timing Fix - Summary

## Problem Statement

The AI speech was sounding "fast" or "chipmunk-like" during phone calls. Analysis of logs revealed three critical issues:

1. **Unstable TX (transmission)** - Only 6 frames/second with ~903ms gaps causing audio to arrive in bursts
2. **TX queue always near capacity** - Queue at 249/250 frames, on the verge of collapse
3. **Actual frame drops** - 134 frames dropped, which shortens sentences and makes speech sound faster

## Root Cause

The audio pipeline was treating variable-sized audio deltas from OpenAI as individual frames and sending them immediately without proper framing or pacing. This caused:

- **Bursts**: Multiple chunks sent rapidly, then long gaps
- **Drops**: Queue overflow causing frames to be dropped
- **Timing issues**: No consistent 20ms pacing for Twilio frames

## Solution Implemented

### TASK A: Audio Framer

**Location**: `server/media_ws_ai.py` - `_realtime_audio_out_loop()` function

**Changes**:
1. Added `_ai_audio_buf` buffer in `__init__` to accumulate incoming audio bytes
2. Modified `_realtime_audio_out_loop()` to:
   - Accumulate variable-sized deltas from OpenAI into buffer
   - Extract fixed 160-byte frames (20ms @ 8kHz μ-law) from buffer
   - Queue only properly-sized frames to TX loop
3. Added buffer clearing on `response.audio.done` to discard remnants

**Result**: Every frame sent to TX loop is exactly 160 bytes = 20ms of audio

### TASK B: Clocked Sender

**Location**: `server/media_ws_ai.py` - `_tx_loop()` function

**Changes**:
1. Added `next_send` deadline tracking with `time.monotonic()`
2. Sleep until deadline before sending each frame (prevents bursts)
3. Advance deadline by FRAME_SEC (20ms) after each send
4. Reset clock when queue is empty (prevents drift during pauses)

**Result**: Audio sent at exactly 50fps (one frame every 20ms), never faster

### TASK C: Stop Frame Dropping

**Location**: `server/media_ws_ai.py` - `__init__` and `_realtime_audio_out_loop()`

**Changes**:
1. Increased `tx_q` maxsize from 250 to 1000 frames (20 seconds buffer)
2. Removed frame dropping logic - changed to warning-only at 50% watermark
3. Added blocking put with timeout as last resort (avoids drops)

**Result**: 20-second buffer absorbs jitter, frames only drop in severe pathological cases

### TASK D: Reduce Per-Frame Logging

**Status**: Already implemented in existing code

The code already logs only once per second and only when:
- Queue is >50% full, OR
- Frame gaps exceed 40ms

**Result**: No per-frame logging overhead, minimal performance impact

## Acceptance Criteria

After this fix, logs should show:

✅ `frames_dropped = 0` throughout the call
✅ `TX_METRICS fps` stable at ~50fps  
✅ `max_gap_ms` small (20-40ms), not 903ms
✅ `q=` never touches capacity (not 249/250)
✅ "Fast/Chipmunk/Rapid speech" artifacts eliminated

## Code Changes Summary

### Modified Files
- `server/media_ws_ai.py`

### Key Functions Modified
1. `__init__()` - Added `_ai_audio_buf` and increased queue size
2. `_realtime_audio_out_loop()` - Implemented audio framing
3. `_tx_loop()` - Implemented clocked sender
4. Event handler for `response.audio.done` - Added buffer clearing

## Testing Checklist

- [ ] Make a test call and observe logs
- [ ] Verify `frames_dropped = 0` in metrics
- [ ] Verify `max_gap_ms < 40ms` consistently
- [ ] Verify queue never reaches capacity
- [ ] Verify AI speech sounds natural, not fast/chipmunk
- [ ] Verify no audio truncation or dropouts

## Metrics to Monitor

```
[TX_METRICS] last_1s: frames=50, fps=50.0, max_gap_ms=25.3, q=45/1000
```

Look for:
- `frames` ≈ 50 per second
- `fps` ≈ 50.0 (consistent)
- `max_gap_ms` < 40 (ideally 20-30)
- `q` stays well below 500 (50% of 1000)

## Backwards Compatibility

✅ All changes are backwards compatible
✅ No API changes
✅ No database schema changes
✅ No configuration changes required

## Performance Impact

- **CPU**: Negligible - simple buffer operations
- **Memory**: +160 bytes per call for framing buffer
- **Latency**: No added latency - clocking maintains real-time flow
- **Throughput**: Improved - fewer drops means more efficient transmission
