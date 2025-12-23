# Production Hangup Rules (Simplified)

## Overview
The system now has **exactly 2** hangup conditions. No other triggers are active.

## Rule 1: Silence-Based Hangup (hard_silence_30s)

**Trigger:** 30 seconds of complete inactivity
- No user voice (RX) AND no AI audio sent to Twilio (TX)
- Activity tracking:
  - `_last_user_voice_started_ts` - Updated on `speech_started` events
  - `last_ai_audio_ts` - Updated on every TX frame sent to Twilio
- Cancellation: If user starts speaking during pending silence hangup, it's cancelled

**Implementation:**
- Timeout: `_hard_silence_hangup_sec = 30.0`
- Reason: `"hard_silence_30s"`
- Watchdog location: `_start_silence_monitor()` at line ~10885

## Rule 2: Bot Goodbye (bot_goodbye)

**Trigger:** Bot says goodbye phrases
- Detection: From bot's transcript (`response.audio_transcript.done`)
- Phrases: ביי, להתראות, תודה להתראות, תודה ולהתראות
- **IMPORTANT:** User saying "ביי" does NOT trigger hangup
- Execution: After `response.audio.done` to let audio finish playing

**Implementation:**
- Reason: `"bot_goodbye"`
- Detection location: `response.audio_transcript.done` handler at line ~5068

## Disabled Hangup Triggers

The following triggers are **completely disabled**:

- ❌ `user_goodbye` - User saying goodbye (wrapped in `if False`)
- ❌ `silence_timeout` - Soft silence warnings (wrapped in `if False`)
- ❌ `idle_timeout_no_user_speech` - Redundant (commented out)
- ❌ `flow_completed` - Flow completion (removed from allow-list)
- ❌ `voicemail_detected` - AMD detection (removed from allow-list)
- ❌ All technical events: `queue_empty`, `audio_done`, `response.done`, `response.audio.done`

## Verification Tests

### Test 1: Normal Conversation
**Scenario:** 2-3 minute conversation, user responds normally, no "bye" from bot
**Expected:** NO disconnect
**Reason:** No valid hangup reason triggered

### Test 2: Complete Silence
**Scenario:** Both parties silent for 31+ seconds
**Expected:** Disconnect after 30 seconds
**Reason:** `hard_silence_30s`

### Test 3: Bot Says Goodbye
**Scenario:** Bot says "תודה, יום טוב, להתראות"
**Expected:** Audio finishes playing, then disconnect
**Reason:** `bot_goodbye`

### Test 4: User Says Goodbye
**Scenario:** User says "ביי" but bot doesn't
**Expected:** NO disconnect, conversation continues
**Reason:** User goodbye disabled

## Technical Details

### Allow-List (Module Constants)
```python
ALLOWED_HANGUP_REASONS = {
    "hard_silence_30s",  # 30 seconds of complete silence
    "bot_goodbye",       # Bot said goodbye (ONLY bot, not user)
}
```

### Block-List (Module Constants)
```python
BLOCKED_HANGUP_REASONS = [
    "queue_empty", "audio_done", "response.done", "response.audio.done",
    "silence_timeout", "hard_silence_timeout", "user_goodbye", 
    "flow_completed", "idle_timeout_no_user_speech", "voicemail_detected"
]
```

### Activity Tracking
- **TX Activity:** `last_ai_audio_ts` updates in `_tx_loop()` on every frame sent
- **RX Activity:** `_last_user_voice_started_ts` updates on `speech_started` events

### Cancellation Logic
```python
if pending_reason == "hard_silence_30s":
    # Cancel silence hangup when user speaks
    self.pending_hangup = False
    # ... (reset all pending hangup state)
```

## Log Examples

### Silence Hangup
```
🔇 [HARD_SILENCE] 30.0s inactivity - hanging up (last_activity=31.2s ago)
[HANGUP_DECISION] allowed=True reason=hard_silence_30s source=silence_watchdog
[HANGUP_REQUEST] hard_silence_30s pending=true ...
```

### Bot Goodbye Hangup
```
🤖 [REALTIME] AI said: תודה רבה, להתראות
[HANGUP_DECISION] allowed=True reason=bot_goodbye source=response.audio_transcript.done
[HANGUP_REQUEST] bot_goodbye pending=true ...
🔇 [AUDIO_STATE] AI finished speaking (response.audio.done) - ai_speaking=False
📞 [HANGUP FLOW] Hangup was PREVIOUSLY requested with valid reason: reason=bot_goodbye
[POLITE_HANGUP] audio.done matched -> hanging up
```

### Cancelled Silence Hangup
```
[HANGUP_REQUEST] hard_silence_30s pending=true ...
🎤 [SPEECH_STARTED] User started speaking
[HANGUP_CANCEL] User spoke - cancelling silence hangup (reason=hard_silence_30s)
```

### Blocked Hangup
```
[HANGUP_DECISION] allowed=False reason=user_goodbye source=transcript - BLOCKED (not in allow-list)
```

## Code Locations

- **Constants:** Lines 1311-1325
- **Timeout:** Line 2004
- **Hard silence watchdog:** Lines 10870-10886
- **Bot goodbye detection:** Lines 5061-5075
- **Cancellation logic:** Lines 4322-4343
- **Disabled soft timeout:** Lines 10909-11005 (wrapped in `if False`)
- **Disabled user goodbye:** Lines 6569-6585 (wrapped in `if False`)

## Migration from Previous Version

### Removed Features
- Multi-warning silence system (warnings 1, 2, 3, then hangup)
- User goodbye detection
- Flow completion hangup
- Idle timeout for users who never spoke
- Voicemail detection hangup

### Why These Changes?
Simplified to avoid premature disconnects and ensure bot only hangs up when:
1. True bilateral silence (30 seconds)
2. Bot explicitly says goodbye

This prevents false disconnects from:
- Technical events (audio.done, queue_empty)
- User saying goodbye (keeps conversation open)
- Flow completion (bot decides when to end, not system)
- Complex multi-warning logic
