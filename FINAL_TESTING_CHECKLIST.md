# Final Testing Checklist - 3 Critical Scenarios

## Overview

These 3 scenarios verify the audio framing fix handles edge cases correctly under real-world conditions.

## Scenario 1: 50fps Validation Under Load

**Objective**: Verify consistent 50fps timing even when server is under CPU/IO stress

**How to Test**:
1. Make 2-3 concurrent calls to load the server
2. Monitor logs for `[TX_METRICS]` during active speech
3. Check metrics across all concurrent calls

**Expected Results**:
- ✅ `fps ≈ 50` consistently (47-52 is acceptable)
- ✅ `max_gap_ms < 60ms` (ideally 20-40ms)
- ✅ Metrics stable across all concurrent calls
- ✅ No degradation even under load

**Implementation Coverage**:
- **Clocked sender** (line 11672-11684): Time-based scheduling ensures 50fps regardless of processing delays
- **Clock resync** (line 11679-11681): Handles CPU delays by resyncing clock if behind schedule
- **Per-frame pacing**: Each frame waits for its deadline, preventing bursts

**Why It Works**:
The clock-based approach uses `time.monotonic()` which measures wall-clock time, not CPU time. Even if the server is busy, frames are sent at precise 20ms intervals because we sleep until the deadline, not based on processing speed.

---

## Scenario 2: Barge-in Mid-Sentence (Long Response)

**Objective**: Verify complete cleanup when user interrupts AI during long speech

**How to Test**:
1. Trigger a long AI response (ask for detailed explanation)
2. Interrupt mid-sentence by speaking
3. Listen for any audio remnants or jumps

**Expected Results**:
- ✅ No audio fragments from interrupted sentence
- ✅ Immediate transition to new response
- ✅ No "jumps" forward/backward in audio
- ✅ Clean cutover without clicks or pops

**Implementation Coverage**:
- **Queue flushing** (line 2993-2997): Clears both `realtime_audio_out_queue` and `tx_q`
- **Buffer clearing** (line 3003-3005): Clears `_ai_audio_buf` partial frame buffer
- **Complete cleanup**: All 3 audio state locations cleared on barge-in

**Why It Works**:
When barge-in triggers, `_flush_twilio_tx_queue` is called (line 3535, 3668) which:
1. Drains all frames from OpenAI queue waiting for framing
2. Drains all framed audio from TX queue waiting to be sent
3. Clears partial frame buffer to prevent fragments
This ensures zero remnants from the interrupted response.

---

## Scenario 3: Underrun/Empty Queue (Short AI Responses)

**Objective**: Verify clock reset on empty queue doesn't cause micro-bursts

**How to Test**:
1. Have conversation with very short AI responses (1-2 word answers)
2. Monitor for any audio "bursts" at start of next sentence
3. Check timing metrics for consistency

**Expected Results**:
- ✅ No micro-bursts at sentence start
- ✅ Smooth audio playback across all responses
- ✅ Clock resets cleanly between responses
- ✅ First frame of new response paced normally

**Implementation Coverage**:
- **Clock reset on empty** (line 11654-11656): When queue empties, `next_send = time.monotonic()`
- **Normal pacing resumes** (line 11700-11701): After reset, first frame waits normal 20ms
- **No catch-up bursts**: Reset prevents accumulating "debt" from previous responses

**Why It Works**:
When the queue empties (end of AI response), we reset `next_send = time.monotonic()` which means "start fresh from now". When the next response arrives:
1. First frame gets `next_send = now` (fresh start)
2. We wait until deadline before sending
3. Each subsequent frame advances by 20ms
This prevents any burst because there's no "backlog" to catch up on.

---

## Log Patterns to Look For

### Good Pattern (Expected)
```
[TX_METRICS] last_1s: frames=50, fps=50.0, max_gap_ms=25.3, q=45/1000
[TX_METRICS] last_1s: frames=49, fps=49.0, max_gap_ms=32.1, q=120/1000
🧹 [BARGE-IN FLUSH] OpenAI queue: 12/12 frames | TX queue: 23/23 frames | Buffer: 87B | reason=BARGE_IN
[TX_METRICS] last_1s: frames=51, fps=51.0, max_gap_ms=28.7, q=15/1000
```

**What to notice**:
- fps stays 47-52 range (±3 is normal jitter)
- max_gap_ms under 60ms
- Barge-in shows queue draining
- Metrics resume normally after barge-in

### Bad Pattern (Would indicate issues)
```
[TX_METRICS] last_1s: frames=15, fps=15.0, max_gap_ms=120.5, q=600/1000  ❌ Low fps, high gap
[TX_METRICS] last_1s: frames=200, fps=200.0, max_gap_ms=5.2, q=0/1000   ❌ Burst (>50fps)
🧹 [BARGE-IN FLUSH] OpenAI queue: 0/0 frames | TX queue: 0/0 frames      ❌ Nothing to flush
[TX_METRICS] last_1s: frames=48, fps=48.0, max_gap_ms=903.2, q=950/1000 ❌ Huge gap, queue full
```

**What these would mean**:
- Low fps with high gaps = bursts and pauses (original bug)
- >50fps = clock not pacing correctly
- Nothing to flush on barge-in = queues not accumulating
- 903ms gap = original problem returning

---

## Success Criteria

All 3 scenarios pass if:

1. **Under Load**: `fps ≈ 50 ± 3` consistently
2. **Barge-in**: Clean cutover, zero remnants
3. **Short Responses**: No bursts, smooth playback

If any scenario fails, check:
- Server CPU/memory utilization
- Network latency to Twilio
- WebSocket connection health
- Log for any errors or warnings

---

## Implementation Confidence

All 3 scenarios are covered by the current implementation:

✅ **Scenario 1**: Clock-based pacing + resync handles load
✅ **Scenario 2**: Complete queue+buffer flush on barge-in
✅ **Scenario 3**: Clock reset on empty prevents bursts

The code is defensive and handles edge cases. These tests validate real-world behavior matches design expectations.
