# Fix: user_has_spoken State Bug in SIMPLE_MODE

## Problem Summary

When the first user utterance was misrecognized by STT and filtered as hallucination:
1. The hallucination filter would reject the transcription
2. **Critical Bug**: `user_has_spoken` flag remained `False`
3. A guard would block all AI audio responses until `user_has_spoken=True`
4. **Result**: Even when the user continued speaking, the bot would not respond because the system thought the user never spoke

### Example Scenario
1. User says "מי אתם" (Who are you)
2. STT outputs "מה מדם" (misrecognition due to 8kHz telephony quality)
3. Hallucination filter rejects it → `user_has_spoken` stays `False`
4. User continues talking, but all AI responses are blocked by guard
5. User thinks bot is ignoring them

## Root Cause Analysis

The issue was in the event flow:

### Before Fix:
```
speech_started event → Mark as candidate, DON'T set user_has_spoken
↓
transcription.completed → Validate utterance
↓
If INVALID → Drop it, DON'T set user_has_spoken ← BUG!
↓
Guard checks user_has_spoken=False → BLOCK all responses
```

### Key Code Location:
- `speech_started` event (line 3418): Did NOT set `user_has_spoken`
- `transcription.completed` validation (line 4565): On rejection, did NOT set `user_has_spoken`
- Guard (line 3699): Blocked all AI audio if `user_has_spoken=False`

## Solution Implemented

### 1. Early Detection in SIMPLE_MODE (speech_started event)

**File**: `server/media_ws_ai.py`  
**Location**: Lines 3428-3444

```python
# 🔥 FIX: Set user_has_spoken=True early when real speech is detected
# Even if STT later produces hallucination, we know user is trying to speak
if SIMPLE_MODE and not self.user_has_spoken:
    # Check if this is real speech (high RMS + sufficient duration)
    utterance_rms = self._utterance_start_rms
    utterance_noise_floor = self._utterance_start_noise_floor
    rms_delta = utterance_rms - utterance_noise_floor
    
    # If RMS is significantly above noise floor, mark as user speaking
    # Use 1.5x threshold for confidence
    if rms_delta >= MIN_RMS_DELTA * 1.5:
        print(f"[STT_DECISION] Speech detected with high RMS - marking user_has_spoken=True early")
        self.user_has_spoken = True
```

**Logic**:
- In SIMPLE_MODE, trust VAD + RMS detection
- Mark `user_has_spoken=True` when speech_started fires with high RMS
- Don't wait for STT validation
- Even if transcription is later rejected, the conversation is "open"

### 2. Disable Guard in SIMPLE_MODE

**File**: `server/media_ws_ai.py`  
**Location**: Lines 3716-3718

```python
# 🛡️ GUARD: Block AI audio before first real user utterance (non-greeting)
# 🔥 FIX: Disabled in SIMPLE_MODE to prevent blocking legitimate responses
if not SIMPLE_MODE and not self.user_has_spoken:
    # Block AI audio...
```

**Logic**:
- In SIMPLE_MODE, don't enforce the pre-user-utterance guard
- Trust that speech_started + RMS already validated real speech
- Prevents blocking responses after hallucinated first utterance

### 3. Enhanced Logging

**File**: `server/media_ws_ai.py`  
**Locations**: Lines 4587-4595, 4619-4626, 4638-4645

Added detailed `[STT_DECISION]` logs for every transcription outcome:

```
[STT_DECISION] raw='מה מדם?' normalized='מה מדם?'
               is_filler_only=False
               is_hallucination=True
               user_has_spoken_before=False → after=True
               will_generate_response=False
```

**Benefits**:
- Track state transitions clearly
- See when `user_has_spoken` changes
- Understand why responses are/aren't generated
- Debug similar issues in the future

## After Fix:

```
speech_started event → HIGH RMS detected
↓
In SIMPLE_MODE → Set user_has_spoken=True IMMEDIATELY ← FIX!
↓
transcription.completed → Validate utterance
↓
If INVALID → Drop transcription (but user_has_spoken already True)
↓
Guard checks user_has_spoken=True → ALLOW next response ✅
```

## Configuration

The fix is controlled by the `SIMPLE_MODE` flag in `server/config/calls.py`:

```python
AUDIO_CONFIG = {
    "simple_mode": True,  # Enable fix
    ...
}
```

When `SIMPLE_MODE=True`:
- Early `user_has_spoken` marking is **enabled**
- Pre-user-utterance guard is **disabled**
- Trust VAD + RMS for speech detection

When `SIMPLE_MODE=False`:
- Original behavior (wait for validated transcription)
- Guard remains active

## Testing Recommendations

### Test Case 1: Misrecognized First Utterance
1. Start call
2. User speaks unclear/misrecognized phrase (e.g., "מי אתם" → "מה מדם")
3. **Expected**: System sets `user_has_spoken=True` on speech_started
4. User continues speaking
5. **Expected**: Bot generates responses normally

### Test Case 2: Multiple Hallucinations
1. Start call  
2. User has poor connection, multiple utterances rejected
3. **Expected**: `user_has_spoken=True` after first real speech detected
4. **Expected**: Bot responds to next valid utterance

### Test Case 3: Verify Logging
1. Check logs for `[STT_DECISION]` entries
2. Verify state transitions are logged
3. Confirm `user_has_spoken_before → after` shows changes

## Log Examples

### Successful Early Detection:
```
🎤 [REALTIME] Speech started - marking as candidate (will validate on transcription)
[STT_DECISION] Speech detected with high RMS - marking user_has_spoken=True early
               rms=125.3, noise_floor=45.2, delta=80.1
```

### Hallucination Dropped (but user_has_spoken already True):
```
[STT_GUARD] Ignoring hallucinated/invalid utterance: 'מה מדם?'
[STT_DECISION] raw='מה מדם?' normalized='מה מדם?'
               is_filler_only=False
               is_hallucination=True (failed validation)
               user_has_spoken_before=True → after=True
               will_generate_response=False (hallucination dropped)
```

### Next Valid Utterance Processed:
```
[STT_GUARD] Accepted utterance: 1250ms, rms=120.5, noise_floor=45.2, text_len=25
[STT_DECISION] raw='אני רוצה לקבוע תור' normalized='אני רוצה לקבוע תור'
               is_filler_only=False
               is_hallucination=False (passed validation)
               user_has_spoken_before=True → after=True
               will_generate_response=True
```

## Related Code

### Key Constants
- `MIN_RMS_DELTA` (line 1063): Base RMS threshold for speech detection
- `SIMPLE_MODE` (config/calls.py): Master flag for simple telephony mode
- `ECHO_SUPPRESSION_WINDOW_MS` (line 1065): Echo rejection window

### Key Functions
- `should_accept_realtime_utterance()` (line 1127): STT validation logic
- `is_valid_transcript()` (line 1084): Filler detection

## Impact

### Before Fix:
- ❌ First utterance misrecognition would "lock" the conversation
- ❌ User had to hang up and call again
- ❌ Poor user experience, especially with telephony audio quality

### After Fix:
- ✅ First utterance misrecognition is gracefully handled
- ✅ Conversation continues normally
- ✅ Improved user experience in noisy/low-quality connections
- ✅ Better logging for debugging

## Notes

1. **SIMPLE_MODE is default**: This fix is active by default for all calls
2. **Telephony-specific**: Designed for 8kHz G.711 telephony where STT errors are common
3. **Conservative thresholds**: Uses 1.5x RMS threshold to ensure real speech
4. **No regression**: Guard still active in non-SIMPLE_MODE for backward compatibility
