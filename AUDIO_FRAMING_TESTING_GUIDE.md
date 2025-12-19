# Testing Guide: Audio Framing Fix

## Prerequisites

1. Deploy the changes to a test environment
2. Have access to server logs in real-time
3. Test phone number configured for the business

## Test Procedure

### Test 1: Basic Call Quality

**Objective**: Verify AI speech sounds natural, not fast/chipmunk

**Steps**:
1. Call the test phone number
2. Listen to the greeting
3. Have a conversation (3-5 exchanges)
4. Ask questions that trigger longer AI responses
5. Interrupt the AI mid-sentence (barge-in test)

**Expected Results**:
- ✅ AI speech sounds natural and properly paced
- ✅ No "fast speech" or "chipmunk" effect
- ✅ No audio dropouts or truncations
- ✅ Smooth transitions between turns
- ✅ Barge-in works without audio artifacts

---

### Test 2: Log Analysis - Framing

**Objective**: Verify frames are properly sized and queued

**Search Pattern**: `[AUDIO_OUT_LOOP]`

**Expected Logs**:
```
🔊 [AUDIO_OUT_LOOP] Started - waiting for OpenAI audio
🔊 [AUDIO_OUT_LOOP] FIRST_CHUNK received! bytes=<varies>, stream_sid=MZ...
✅ [TX_LOOP] FIRST_FRAME_SENT to Twilio! tx=1, stream_sid=MZ...
```

**What to Check**:
- ✅ First chunk received log appears
- ✅ First frame sent log appears shortly after
- ✅ No "Skipping chunk - no stream_sid" warnings after startup
- ✅ No buffer clearing warnings during speech

---

### Test 3: Log Analysis - TX Metrics

**Objective**: Verify stable 50fps with no gaps or drops

**Search Pattern**: `[TX_METRICS]`

**Expected Logs** (only when queue >50% or gaps >40ms):
```
[TX_METRICS] last_1s: frames=50, fps=50.0, max_gap_ms=22.5, q=45/1000
[TX_METRICS] last_1s: frames=49, fps=49.0, max_gap_ms=31.2, q=120/1000
```

**What to Check**:
- ✅ `frames` ≈ 50 per second (47-52 is fine)
- ✅ `fps` ≈ 50.0 consistently
- ✅ `max_gap_ms` typically 20-35ms (never >100ms)
- ✅ `q` (queue size) stays well below 500
- ✅ Logs only appear when queue is filling (50%+) or gaps detected

**Bad Patterns** (what we fixed):
- ❌ fps < 10 (was 6 in bug report)
- ❌ max_gap_ms > 500 (was 903ms in bug report)
- ❌ q near maxsize (was 249/250 in bug report)

---

### Test 4: Log Analysis - Frame Drops

**Objective**: Verify zero frame drops

**Search Pattern**: `frames_dropped` or `[AUDIO DROP]` or `[AUDIO CRITICAL]`

**Expected Results**:
- ✅ No `[AUDIO DROP]` messages
- ✅ No `[AUDIO CRITICAL]` messages
- ✅ If metrics are logged, `frames_dropped=0`

**Bad Patterns** (should NOT see):
- ❌ "Frame lost after wait"
- ❌ "TX queue completely full"
- ❌ frames_dropped > 0

---

### Test 5: Call Metrics - End of Call

**Objective**: Verify overall call quality metrics

**Search Pattern**: `[CALL_METRICS]`

**Expected Logs**:
```
📊 [CALL_METRICS] Call CAxxxx
   Greeting: <1500ms
   First user utterance: <3000ms
   Avg AI turn: <2000ms
   Avg user turn: <3000ms
   Barge-in events: <5
   Silences (10s+): 0
   STT hallucinations dropped: <3
   STT total: >3, empty: 0, short: <2, filler-only: <2
   Audio pipeline: in=<5000, forwarded=<5000, dropped=0
```

**What to Check**:
- ✅ `frames_dropped=0` (most critical!)
- ✅ `frames_forwarded` ≈ `frames_in` (minimal blocking)
- ✅ Reasonable conversation metrics

---

### Test 6: Load Test (Optional)

**Objective**: Verify fix works under concurrent calls

**Steps**:
1. Make 3-5 concurrent calls
2. Monitor server logs
3. Check for any degradation

**Expected Results**:
- ✅ All calls have stable metrics
- ✅ No calls hit queue capacity
- ✅ No frame drops across any calls
- ✅ max_gap_ms stays low across all calls

---

## Success Criteria Summary

The fix is successful if ALL of these are true:

1. ✅ AI speech sounds natural (no fast/chipmunk effect)
2. ✅ `frames_dropped = 0` in all calls
3. ✅ `fps ≈ 50` consistently
4. ✅ `max_gap_ms < 40ms` (typically 20-35ms)
5. ✅ Queue never exceeds 50% capacity
6. ✅ No audio truncation or dropouts
7. ✅ Barge-in works smoothly

---

## Troubleshooting

### If you still see "fast speech":

1. Check if `max_gap_ms` is high - indicates timing issues upstream
2. Check if frames are being dropped - indicates queue overflow
3. Check OpenAI response times - might be delayed deltas
4. Check network latency between server and Twilio

### If queue fills up:

1. Check if TX loop is running (`[AUDIO_TX_LOOP] started`)
2. Check if frames are being sent successfully
3. Check WebSocket connection health
4. Check for CPU throttling on server

### If frames are dropping:

1. Should NOT happen with 1000-frame buffer
2. If it does, indicates severe TX bottleneck
3. Check server CPU, network, WebSocket health
4. Consider increasing queue size further if pathological case

---

## Rollback Plan

If testing reveals issues:

1. Revert the commit: `git revert <commit-hash>`
2. Queue size can be adjusted independently: change `maxsize=1000` back to `maxsize=250`
3. Monitor for any regression in original symptoms

---

## Performance Baseline

### Before Fix (Bug Report)
- fps: 6 frames/second
- max_gap_ms: 903ms
- Queue: 249/250 (99% full)
- frames_dropped: 134

### After Fix (Target)
- fps: 50 frames/second
- max_gap_ms: <40ms (typically 20-35ms)
- Queue: <500/1000 (50% max)
- frames_dropped: 0

### Improvement
- **8x** more frames per second
- **23x** reduction in max gap
- **4x** more buffer capacity
- **100%** reduction in dropped frames
