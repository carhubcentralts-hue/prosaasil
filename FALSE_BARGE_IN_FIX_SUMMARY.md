# False Barge-In and Outbound AMD Fixes - Implementation Summary

## Problem Statement

The system had two critical issues causing poor call quality:

1. **Outbound calls not speaking**: AMD (Answering Machine Detection) results were not connected to the `human_confirmed` flag, causing the bot to wait indefinitely without greeting the customer.

2. **False barge-in causing mid-sentence stops**: The bot would start speaking and then suddenly stop, even when the user wasn't interrupting. This was caused by:
   - Incorrect AI speaking state (set before audio actually starts playing)
   - Canceling responses that were already done or too new
   - Late transcripts triggering false barge-in
   - Poor error handling for `response_cancel_not_active`

## Root Cause Analysis

### Issue 1: "False Barge-In" State Bug

The problem occurred when:
1. AI response is created (`response.created` event)
2. Code sets `is_ai_speaking=True` immediately (wrong!)
3. But audio hasn't actually started playing yet
4. User utterance arrives or late transcription commits
5. Code thinks "AI is speaking", tries to cancel
6. Response hasn't really started yet → `response_cancel_not_active` error
7. Response gets cut off, no retry, silence follows

### Issue 2: Canceling Too-New Responses

Even when audio was starting:
1. Response created at T+0ms
2. Audio starts playing at T+50ms
3. User speaks at T+60ms
4. Cancel sent at T+60ms
5. Response barely started → feels like "starts then stops"

### Issue 3: Late Transcript False Barge-In

When transcription processing is delayed:
1. User speaks at T+0ms (speech_started fires)
2. AI finishes speaking at T+500ms
3. Transcription arrives at T+700ms (late!)
4. Code thinks "AI still speaking", cancels active response
5. But AI already done → false barge-in → "starts then stops"

## Solutions Implemented

### 1. Single Source of Truth: is_ai_speaking Set ONLY in TX Loop

**Before:**
```python
# In audio.delta handler (WRONG)
if event_type == "response.audio.delta":
    self.is_ai_speaking_event.set()  # Too early!
```

**After:**
```python
# In TX loop (_tx_loop method)
if not _first_frame_sent:
    _first_frame_sent = True
    if not self.is_ai_speaking_event.is_set():
        self.is_ai_speaking_event.set()  # Only when actually sent to Twilio
```

**Impact:** is_ai_speaking is now accurate - only True when audio is actually being transmitted to Twilio.

### 2. Response Age Guard (150ms Minimum)

**Added to `_can_cancel_response()`:**
```python
# Don't cancel response that's too new (< 150ms old)
if hasattr(self, '_response_created_times') and self.active_response_id in self._response_created_times:
    response_age_ms = (now - self._response_created_times[self.active_response_id]) * 1000
    if response_age_ms < 150:
        logger.debug(f"[CANCEL_GUARD] Skip cancel: response too new ({response_age_ms:.0f}ms < 150ms)")
        return False
```

**Impact:** Responses get at least 150ms to start playing before they can be interrupted. Fixes "starts speaking then stops" issue.

### 3. Graceful response_cancel_not_active Handling

**Before:**
```python
except Exception as cancel_err:
    logger.error(f"Cancel failed: {cancel_err}")
    # No recovery - stuck state!
```

**After:**
```python
except Exception as cancel_err:
    error_str = str(cancel_err).lower()
    if 'not_active' in error_str:
        # Clear state flags immediately (NO FLUSH!)
        self.ai_response_active = False
        self.is_ai_speaking_event.clear()
        self.active_response_id = None
        self._response_done_ids.add(cancelled_response_id)
        # Continue creating new response
```

**Impact:** Error is treated as "response already ended", state is cleaned up, and new response is created normally.

### 4. AMD → human_confirmed Connection

**Added AMD cache in routes_twilio.py:**
```python
_amd_cache = {}  # {call_sid: {"result": "human", "timestamp": time.time()}}
_amd_cache_lock = threading.Lock()
AMD_CACHE_TTL_SEC = 60
```

**AMD webhook handler:**
```python
if is_human and call_sid:
    handler = _get_handler(call_sid)
    if handler:
        handler.human_confirmed = True
        handler._outbound_gate_state = "CONFIRMED"
    else:
        _set_amd_in_cache(call_sid, "human")  # Store for later
```

**Handler registration checks cache:**
```python
if self.call_sid:
    _register_handler(self.call_sid, self)
    # Check AMD cache
    amd_result = _get_amd_from_cache(self.call_sid)
    if amd_result == "human":
        self.human_confirmed = True
        self._outbound_gate_state = "CONFIRMED"
```

**Impact:** Outbound calls will trigger greeting as soon as AMD detects human, regardless of webhook timing.

### 5. Enhanced Cancel Guards

The `_can_cancel_response()` method now checks ALL of these conditions:

1. ✅ active_response_id exists
2. ✅ ai_response_active == True
3. ✅ response not in _response_done_ids
4. ✅ response not in _audio_done_received
5. ✅ last_audio_out_ts < 700ms ago (recent audio)
6. ✅ response_age >= 150ms (not too new)
7. ✅ cooldown period passed (200ms since last cancel)

**Impact:** Cancel only happens when ALL conditions are met, preventing false barge-in.

### 6. Late Transcript Detection (NEW)

**Problem:** Transcriptions that arrive >600ms after user started speaking can trigger false barge-in.

**Solution:** Calculate speech age based on local VAD timestamp instead of event timestamps.

```python
# In transcription.completed handler, before barge-in logic:
now = time.time()
speech_age_ms = (now - (self._last_user_voice_started_ts or now)) * 1000
is_late_transcript = speech_age_ms > 600

logger.info(f"[BARGE_IN] late_check: speech_age_ms={speech_age_ms:.0f} late={is_late_transcript}")

# Skip barge-in if late
if ai_is_speaking and active_response_id and not is_late_transcript:
    # Proceed with barge-in logic
    ...
elif ai_is_speaking and active_response_id and is_late_transcript:
    logger.info(f"[BARGE_IN] SKIP late_utterance: age_ms={speech_age_ms:.0f}")
    # Treat as regular turn after AI done
```

**Why It Works:**
- Uses `_last_user_voice_started_ts` set on `speech_started` event (reliable local timestamp)
- Not dependent on event metadata which may be missing or inconsistent
- Calculates real elapsed time from when user actually started speaking

**Impact:** Prevents "thought they spoke when they didn't" false barge-in. Expected 1-5% of transcriptions to be marked as late.

### 7. Retry Logic for Failed Response Creation

**After barge-in fails:**
```python
if not triggered:
    # Schedule retry with 200ms delay
    async def retry_pending_response():
        await asyncio.sleep(0.2)
        if hasattr(self, '_pending_barge_in_utterance'):
            retry_success = await self.trigger_response(...)
```

**Impact:** Failed response creation is retried once after 200ms, reducing watchdog dependency.

## Testing

Created comprehensive test suite in `test_false_barge_in_fixes.py`:

- ✅ Response age check logic
- ✅ Flag reset on audio.done
- ✅ AMD cache storage and retrieval
- ✅ cancel_not_active error handling
- ✅ is_ai_speaking state management
- ✅ Late transcript detection (NEW)

All tests passing.

- ✅ Response age check logic
- ✅ Flag reset on audio.done
- ✅ AMD cache storage and retrieval
- ✅ cancel_not_active error handling
- ✅ is_ai_speaking state management

All tests passing.

## Expected Behavior After Fixes

### Outbound Calls
- ✅ Bot speaks immediately after AMD detects human
- ✅ No waiting for STT or timeout when AMD says "human"
- ✅ Cache handles race condition between AMD webhook and handler registration

### Barge-In
- ✅ Only triggers when AI is ACTUALLY playing (not just created)
- ✅ Response gets 150ms to start before it can be interrupted
- ✅ No "starts speaking then stops" issue
- ✅ Graceful handling of cancel errors

### Error Recovery
- ✅ response_cancel_not_active doesn't break the flow
- ✅ State is cleaned up properly on errors
- ✅ New response is created from pending utterance
- ✅ Retry mechanism for failed response creation

## Logging Added

All critical operations now log:
- `[BARGE_IN_FIX]` - State changes related to barge-in fixes
- `[CANCEL_GUARD]` - When cancel is blocked and why
- `[AMD_CACHE]` - AMD result storage and retrieval
- `[OUTBOUND_GATE]` - AMD human detection and confirmation

## Files Modified

1. **server/routes_twilio.py**
   - Added AMD cache mechanism
   - Updated amd_status webhook to set human_confirmed
   - Added cache helper functions

2. **server/media_ws_ai.py**
   - Moved is_ai_speaking.set() to TX loop only
   - Removed is_ai_speaking.set() from audio.delta handlers
   - Added response_age tracking and check
   - Enhanced _can_cancel_response() with 7 conditions
   - Improved response_cancel_not_active handling
   - Added AMD cache check on handler registration
   - Added retry logic for failed response creation
   - Added double cleanup on response.done

3. **test_false_barge_in_fixes.py** (new)
   - Comprehensive test suite for all fixes

## Deployment Notes

1. These changes are backward compatible
2. No database schema changes required
3. No environment variables added
4. Existing AMD configuration works as-is
5. Logs may be slightly more verbose (helpful for debugging)

## Monitoring Recommendations

After deployment, watch for:
- Reduction in `response_cancel_not_active` errors (should be near zero)
- Increase in outbound call greeting rate (closer to 100%)
- Reduction in "silent calls" where bot doesn't speak
- Fewer mid-sentence interruptions reported by users

## References

Based on expert Hebrew analysis in problem statement:
- Single Source of Truth for is_ai_speaking
- 150ms grace period before cancel
- Graceful error handling for cancel_not_active
- AMD → human_confirmed pathway
