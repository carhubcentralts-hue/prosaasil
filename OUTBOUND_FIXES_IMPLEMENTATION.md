# Outbound Call Fixes - Implementation Summary

## Overview
This document summarizes the implementation of fixes for outbound call issues as specified in the problem statement. The fixes address critical issues with outbound calls where the bot would start speaking before the human picked up, leading to failed calls.

## Problem Statement Summary
The original issue was that in outbound calls:
1. Bot would speak before detecting real human speech (speaking to "טוט טוט" tones)
2. Human confirmation trigger was unstable - didn't generate response immediately
3. STT events continued after session close, causing errors
4. Watchdog would retry response.create even after hangup was requested
5. Frame drops were not properly categorized for diagnostics

## Implementation Details

### ✅ Phase 1: Outbound Human Confirmation Logic

**Location**: `server/media_ws_ai.py`

#### 1.1 Enhanced `contains_human_greeting()` Function (Lines ~1485-1560)

**Added dial tone filtering:**
```python
DIAL_TONE_NOISE_PATTERNS = {
    "טוט", "טוּט", "תוּת", "ביפ", "beep", "tone", "טון", "בּיפּ"
}
```

**Robust validation logic:**
- Filters OUT: Dial tones, single short gibberish words (< 3 chars), empty text
- ACCEPTS: Known human greetings, multi-word phrases (≥ 2 words), valid Hebrew text (≥ 3 chars)
- Returns detailed logging for each decision path

**Logging examples:**
- `[OUTBOUND] human_confirmed=false reason=tone_detected text='טוט'`
- `[OUTBOUND] human_confirmed=false reason=too_short chars=1 text='ט'`
- `[OUTBOUND] human_confirmed=true reason=greeting_detected phrase='שלום' text='שלום'`

#### 1.2 Adjusted Minimum Duration (Line ~1318)
- Changed from 600ms to 400ms (400-600ms range per requirements)
- Ensures faster response to human speech while still filtering tones

#### 1.3 Added `outbound_first_response_sent` Lock (Line ~2278)
- Prevents multiple greeting triggers on same utterance
- Set immediately when human_confirmed triggers greeting
- Reset only on error to allow retry

### ✅ Phase 2: Bot Speaks First Logic Fix

**Location**: `server/media_ws_ai.py` (Lines ~6309-6385)

#### 2.1 Immediate Greeting Trigger
- **Removed 0.1s delay** - greeting now triggers immediately after human confirmation
- Changed `await asyncio.sleep(0.1)` → removed delay entirely
- Greeting label changed from "GREETING_DELAYED" to "OUTBOUND_HUMAN_CONFIRMED"

#### 2.2 Enhanced Logging
```python
logger.info(f"[OUTBOUND] response.create triggered text='{text[:50]}'")
logger.error(f"[OUTBOUND] response.create FAILED after human_confirmed")
```

### ✅ Phase 3: STT After Close Guard

**Location**: `server/media_ws_ai.py` (Lines ~6160-6170)

#### 3.1 Early Exit on Session Close
Added guard at start of STT event handler:
```python
if getattr(self, 'closing', False) or getattr(self, 'session_closed', False) or self.call_state == CallState.CLOSING:
    logger.info(f"[STT_GUARD] Ignoring STT after session close...")
    continue
```

**Prevents:**
- Processing STT events after `twilio_stop_event`
- Attempting response.create on closed sessions
- Late-arriving transcriptions from causing errors

### ✅ Phase 4: Hangup Logic (Already Correct)

**Location**: `server/media_ws_ai.py` (Lines ~5481-5507)

**Verified existing implementation:**
1. ✅ Detects "ביי" and "להתראות" in `response.audio_transcript.done`
2. ✅ Calls `request_hangup("bot_goodbye", ...)` - sets pending flag only
3. ✅ Actual hangup triggered in `response.audio.done` via `delayed_hangup()`
4. ✅ Waits for both OpenAI and Twilio queues to drain before executing
5. ✅ 2-second network buffer after queues empty

**No changes needed** - logic already matches simplified Phase 1 requirements.

### ✅ Phase 5: Watchdog Hangup Prevention

**Location**: `server/media_ws_ai.py`

#### 5.1 Set `closing` Flag (Lines ~12503-12534)
When `request_hangup()` is called:
```python
self.closing = True  # Prevents new response.create
```

#### 5.2 Cancel Background Tasks (Lines ~12517-12534)
```python
# Cancel watchdog task
watchdog_task = getattr(self, '_watchdog_task', None)
if watchdog_task and not watchdog_task.done():
    watchdog_task.cancel()

# Cancel turn_end task  
turn_end_task = getattr(self, '_turn_end_task', None)
if turn_end_task and not turn_end_task.done():
    turn_end_task.cancel()
```

#### 5.3 Existing Watchdog Guards (Lines ~6470-6476)
Already has comprehensive checks:
```python
if getattr(self, "closing", False) or getattr(self, "hangup_pending", False):
    logger.debug("[WATCHDOG] Skip retry: closing or hangup pending")
    return
```

### ✅ Phase 6: Frame Drop Classification

**Location**: `server/media_ws_ai.py`

#### 6.1 Centralized `_drop_frames()` Method (Lines ~2307-2345)
```python
def _drop_frames(self, reason: str, count: int):
    """
    Centralized frame drop tracking with proper categorization.
    
    Reasons: greeting_lock, filters, queue_full, bargein_flush, 
             tx_overflow, shutdown_drain
    """
    self._frames_dropped_total += count
    
    if reason == "shutdown_drain":
        self._frames_dropped_shutdown_drain += count
    elif reason == "bargein_flush":
        self._frames_dropped_bargein_flush += count
    # ... etc
    else:
        self._frames_dropped_unknown += count  # Should be 0!
        logger.error(f"[FRAME_DROP] UNKNOWN reason='{reason}'")
```

#### 6.2 Updated All Queue Cleanup Locations
- **Polite hangup TX cleanup** (Line ~5466): `self._drop_frames("shutdown_drain", cleared)`
- **Twilio close TX cleanup** (Line ~8606): `self._drop_frames("shutdown_drain", cleared)`
- **Twilio close audio out cleanup** (Line ~8617): `self._drop_frames("shutdown_drain", cleared)`
- **Barge-in interrupt** (Line ~10007): `self._drop_frames("bargein_flush", cleared_count)`

## Acceptance Criteria Verification

### ✅ 1. Outbound calls wait silently until real human speech detected
- `contains_human_greeting()` filters dial tones
- `human_confirmed` stays False until valid greeting + duration check
- No response.create until human_confirmed=True

### ✅ 2. "טוט טוט" tones do not trigger greeting
- `DIAL_TONE_NOISE_PATTERNS` includes "טוט", "ביפ", "beep", "tone"
- Returns False immediately on tone detection
- Logs: `[OUTBOUND] human_confirmed=false reason=tone_detected`

### ✅ 3. Bot responds immediately after human says "שלום"/"הלו"
- Removed 0.1s delay in greeting trigger
- `_trigger_outbound_greeting()` calls response.create immediately
- Flag `outbound_first_response_sent` prevents duplicate triggers

### ✅ 4. No response.create after hangup_pending=True
- `self.closing = True` set in `request_hangup()`
- Watchdog checks `closing` and `hangup_pending` flags
- Background tasks cancelled when hangup requested

### ✅ 5. Hangup only after bot says "ביי"/"להתראות" and audio completes
- Detection in `response.audio_transcript.done`
- Execution in `response.audio.done` after queues drain
- 2-second network buffer ensures audio played

### ✅ 6. All frame drops are properly categorized
- Centralized `_drop_frames()` method for all drops
- All queue cleanups updated to use this method
- `frames_dropped_unknown` should be 0 in production

## Testing Recommendations

### Manual Test Scenarios

#### Scenario 1: Outbound to Voicemail/IVR
**Expected:**
- Call connects, hears "טוט טוט" → Bot stays silent
- Call connects, hears IVR "Press 1 for..." → Bot stays silent
- Logs: `[OUTBOUND] human_confirmed=false reason=tone_detected`

#### Scenario 2: Outbound to Real Human
**Expected:**
- Call connects, human says "שלום" → Bot starts speaking immediately
- Logs: 
  - `[HUMAN_CONFIRMED] Set to True: text='שלום', duration=XXXms`
  - `[OUTBOUND] response.create triggered text='שלום'`
  - `frames_sent > 0` (TX started)

#### Scenario 3: Bot Says Goodbye
**Expected:**
- Bot says "תודה, ביי" → Hangup request logged
- Audio plays completely → Queues drain
- Hangup executes after 2s buffer
- Logs:
  - `[HANGUP_REQUEST] bot_goodbye pending=true`
  - `[POLITE HANGUP] Queues empty, waiting 2s for network...`
  - `[HANGUP] executing reason=bot_goodbye`

#### Scenario 4: Frame Drop Tracking
**Expected:**
- All frame drops categorized (no unknown drops)
- Logs at end: `frames_dropped_unknown=0`
- If non-zero: `🚨 SIMPLE_MODE BUG: X frames dropped for UNKNOWN reason!`

## Logs to Verify in Production

### Outbound Human Confirmation
```
[OUTBOUND] Skipping greeting trigger - waiting for human confirmation
[HUMAN_CONFIRMED] Not yet: text='טוט', greeting=False, duration=200ms/400ms
[OUTBOUND] human_confirmed=false reason=tone_detected text='טוט טוט'
[HUMAN_CONFIRMED] Set to True: text='שלום', duration=650ms
[OUTBOUND] response.create triggered text='שלום'
```

### Hangup Flow
```
[HANGUP_DECISION] allowed=True reason=bot_goodbye source=response.audio_transcript.done
[HANGUP_REQUEST] bot_goodbye pending=true response_id=resp_xxx
[POLITE HANGUP] audio.done matched -> hanging up
[POLITE HANGUP] OpenAI queue empty after 100ms
[POLITE HANGUP] Twilio TX queue empty after 400ms
[POLITE HANGUP] Queues empty, waiting 2s for network...
[HANGUP] executing reason=bot_goodbye response_id=resp_xxx call_sid=CA...
[HANGUP] success call_sid=CA...
```

### Frame Drop Summary
```
[CALL_METRICS] frames_dropped_unknown=0
Drop breakdown: greeting=0, filters=0, queue=0, bargein=0, tx_overflow=0, shutdown=25, unknown=0
```

## Files Modified

- `server/media_ws_ai.py` (141 insertions, 17 deletions)

## Backward Compatibility

✅ All changes are backward compatible:
- Inbound calls: No behavior changes (human_confirmed=True by default)
- Existing hangup logic: No changes (already correct)
- Frame drop counters: New method adds tracking, doesn't break existing code
- Watchdog: Additional guards, doesn't affect normal operation

## Security Considerations

✅ No security implications:
- No new network calls or external dependencies
- No changes to authentication/authorization
- No exposure of sensitive data in logs (text truncated to 50 chars)
