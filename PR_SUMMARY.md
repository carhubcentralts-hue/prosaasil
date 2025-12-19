# Pull Request: Fix "Fast Speech" Audio Issue

## Summary

This PR fixes the "fast speech" or "chipmunk-like" audio quality issue in AI phone calls by implementing proper audio framing and clocked transmission timing.

## Problem

Analysis of production logs revealed three critical issues causing distorted audio:

1. **Unstable TX** - Only 6 frames/second with ~903ms gaps causing audio bursts
2. **TX queue always near capacity** - Queue at 249/250 frames (99% full)
3. **Frame drops** - 134 frames dropped per call, shortening sentences

## Solution

Implemented 4 tasks as specified in the problem statement:

### ✅ TASK A: Audio Framer
- Added `_ai_audio_buf` bytearray to accumulate variable-sized audio deltas from OpenAI
- Segments audio into fixed 160-byte frames (20ms @ 8kHz μ-law) before queueing
- Clears remnants on `response.audio.done` to avoid artifacts

### ✅ TASK B: Clocked Sender
- Implemented time-based scheduling in `_tx_loop()` with `next_send` deadline
- Enforces precise 50fps pacing (one 20ms frame every 20ms)
- Prevents bursts by sleeping until deadline
- Resets clock when queue is empty to avoid drift

### ✅ TASK C: Stop Frame Dropping
- Increased TX queue from 250 to 1000 frames (20 seconds buffer)
- Removed frame dropping logic - only warnings at 50% watermark
- Added blocking put with timeout as last resort (backpressure instead of drops)

### ✅ TASK D: Reduce Per-Frame Logging
- Already implemented - logs only once per second
- Only logs when queue >50% full or gaps >40ms detected
- Minimal performance impact

## Changes

### Modified Files
- `server/media_ws_ai.py` (171 insertions, 73 deletions)
  - `__init__()` - Added `_ai_audio_buf` and increased queue size to 1000
  - `_realtime_audio_out_loop()` - Implemented audio framing
  - `_tx_loop()` - Implemented clocked sender
  - Event handler for `response.audio.done` - Added buffer clearing

### New Documentation
- `AUDIO_FRAMING_FIX_SUMMARY.md` - Technical summary (English)
- `AUDIO_FRAMING_TESTING_GUIDE.md` - Testing procedures (English)
- `AUDIO_FRAMING_FIX_HEBREW.md` - Summary for stakeholders (Hebrew)

## Expected Results

After deployment, call logs should show:

✅ `frames_dropped = 0` throughout calls
✅ `fps ≈ 50` consistently (not 6)
✅ `max_gap_ms < 40ms` (not 903ms)
✅ Queue never exceeds 50% capacity (not 99%)
✅ Natural speech without "fast" artifacts

## Testing

See `AUDIO_FRAMING_TESTING_GUIDE.md` for comprehensive testing procedures.

### Quick Test
1. Make a test call
2. Verify AI speech sounds natural (not fast/chipmunk)
3. Check logs for `[TX_METRICS]` - should show fps≈50, max_gap_ms<40
4. Check for zero `frames_dropped` in final metrics

## Performance Impact

- **CPU**: Negligible - simple buffer operations
- **Memory**: +160 bytes per call for framing buffer
- **Latency**: No added latency - maintains real-time flow
- **Throughput**: Improved - fewer drops means more efficient transmission

## Backwards Compatibility

✅ No API changes
✅ No database schema changes
✅ No configuration changes required
✅ Fully backwards compatible

## Security

✅ CodeQL scan passed with zero alerts

## Code Review

✅ Addressed all review feedback:
- Added defensive programming comments
- Clarified race condition handling
- Improved fallback logic documentation
- Fixed documentation headers

## Deployment

1. Deploy to test environment
2. Run test calls following `AUDIO_FRAMING_TESTING_GUIDE.md`
3. Verify metrics match expected results
4. Deploy to production
5. Monitor first production calls for metrics

## Rollback Plan

If issues arise:
1. Revert commits: `git revert HEAD~3..HEAD`
2. Or adjust queue size independently: change `maxsize=1000` back to `maxsize=250`
3. Monitor for regression in original symptoms

## References

- Original problem statement (Hebrew) provided in issue
- Logs analysis showing 6fps, 903ms gaps, 249/250 queue, 134 drops
- Solution requirements: TASK A (Framer), B (Clocked), C (No Drops), D (Logging)

---

**Ready for Review** ✅

This PR is complete and ready for:
1. Code review
2. Testing in test environment
3. Production deployment
