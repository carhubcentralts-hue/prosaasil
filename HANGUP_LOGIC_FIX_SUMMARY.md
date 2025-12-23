# Hangup Logic Fix - Summary

## Problem Statement (Hebrew)

הבעיה: המערכת הייתה תולה ניתוק על אירועים טכניים כמו `response.audio.done` או "OpenAI queue empty", ואז עושה `pending_hangup=True` ומבצעת `delayed_hangup()` גם בלי סיבת ניתוק אמיתית.

## Root Cause

The system was triggering hangups based on technical events (audio completion, queue drain) instead of only on explicit user/bot actions. This caused premature disconnects during normal conversations.

## Solution

### 1. Fixed `response.audio.done` Handler

**Before:**
- `response.audio.done` event could trigger hangup flow
- Mixed audio state management with hangup logic

**After:**
- `response.audio.done` ONLY updates audio state (`ai_speaking=False`)
- Does NOT trigger hangup by itself
- Only executes hangup when `pending_hangup` was PREVIOUSLY set by a valid reason
- Added clear logging to distinguish between:
  - Audio state update (normal): `[AUDIO_STATE] AI finished speaking`
  - Hangup execution (only when requested): `[HANGUP FLOW] Hangup was PREVIOUSLY requested`

**Key Rule:** `response.audio.done` = "AI finished speaking", NOT a hangup trigger

### 2. Added Reason Validation Gate

Created an allow-list in `request_hangup()` to validate hangup reasons:

**Allowed Reasons:**
- `hard_silence_timeout` - True 20-second silence (no RX + no TX)
- `user_goodbye` - User said goodbye/bye/etc (closing phrases)
- `bot_goodbye` - Bot said goodbye/bye/etc (closing phrases)
- `silence_timeout` - Regular silence warnings exceeded
- `idle_timeout_no_user_speech` - User never spoke after 30s
- `voicemail_detected` - AMD detection
- `flow_completed` - Bot completed script and user confirmed

**Blocked Reasons:**
- Empty/None
- `queue_empty`
- `audio_done`
- `response.done`
- `response.audio.done`

**Logging:**
- Every hangup request now logs: `[HANGUP_DECISION] allowed=True/False reason=... source=...`
- This makes debugging much easier

**Key Rule:** `pending_hangup` is set ONLY by `request_hangup(reason)`, NOT by OpenAI events

### 3. Fixed Activity Tracking

**Problem:** Silence watchdog could trigger false positives if `last_ai_audio_ts` wasn't updated properly.

**Solution:**
- `last_ai_audio_ts` now updates on EVERY TX frame sent to Twilio (not just when received from OpenAI)
- This ensures the silence watchdog knows AI audio was sent recently
- Prevents false "silence" detection mid-conversation

**Location:** `_tx_loop()` at line ~13850:
```python
if success:
    self.tx += 1
    frames_sent_total += 1
    # 🔥 FIX: Update last_ai_audio_ts to prevent false silence detection
    self.last_ai_audio_ts = time.time()
```

### 4. Verified 20-Second Silence Timeout

**Already Correct:** The existing silence watchdog implementation properly checks:
- Condition: No RX (user) AND no TX (AI) for 20 seconds straight
- Only when call is in-progress/answered
- Uses: `max(last_user_voice, last_ai_audio)` to detect true silence
- Reason: `hard_silence_timeout`

**Location:** `_start_silence_monitor()` at line ~10823-10843

## Verification Tests

### Test 1: Normal Conversation
**Scenario:** Bot speaks, user responds, no "bye"
**Expected:** Should NOT disconnect
**Reason:** No valid hangup reason set

### Test 2: True 20-Second Silence
**Scenario:** Both parties silent for 20 seconds
**Expected:** Should disconnect with `reason=hard_silence_timeout`
**Reason:** Valid reason from silence watchdog

### Test 3: AI Finishes Speaking
**Scenario:** AI completes response, `response.audio.done` fires
**Expected:** Should NOT disconnect, just update `ai_speaking=False`
**Reason:** No pending hangup, so audio.done only updates state

### Test 4: User Says Goodbye
**Scenario:** User says "ביי" or "להתראות"
**Expected:** Should disconnect with `reason=user_goodbye`
**Reason:** Valid reason from user transcript analysis

## Log Examples

### Normal Flow (No Hangup)
```
🔇 [AUDIO_STATE] AI finished speaking (response.audio.done) - ai_speaking=False
✅ [AUDIO_STATE] Normal flow: AI finished speaking, continuing conversation
```

### Hangup Flow (Valid Reason)
```
[HANGUP_DECISION] allowed=True reason=user_goodbye source=transcript - Request accepted
[HANGUP_REQUEST] user_goodbye pending=true response_id=resp_xxx...
🔇 [AUDIO_STATE] AI finished speaking (response.audio.done) - ai_speaking=False
📞 [HANGUP FLOW] Hangup was PREVIOUSLY requested with valid reason: reason=user_goodbye, source=transcript
📞 [HANGUP FLOW] Now executing hangup because AI audio finished (response.audio.done)
[POLITE_HANGUP] audio.done matched -> hanging up
```

### Blocked Hangup (Invalid Reason)
```
[HANGUP_DECISION] allowed=False reason=queue_empty source=delayed_hangup - BLOCKED (not in allow-list)
```

## Key Principles

1. **Separation of Concerns:**
   - Audio state management ≠ Hangup logic
   - `response.audio.done` manages audio state
   - `request_hangup(reason)` manages hangup logic

2. **Explicit Intent:**
   - Hangups require explicit reasons
   - Technical events (audio.done, queue_empty) are NOT valid reasons
   - Only user actions or timeout conditions trigger hangups

3. **Fail-Safe Design:**
   - Invalid reasons are blocked at the gate
   - Clear logging for every decision
   - Activity tracking prevents false positives

## Modified Files

- `server/media_ws_ai.py`:
  - `request_hangup()` - Added reason validation gate (lines 11414-11458)
  - `response.audio.done` handler - Improved logging and separation (lines 4871-5003)
  - `_tx_loop()` - Added activity tracking (line ~13850)

## Testing Checklist

- [ ] Normal conversation continues without premature disconnect
- [ ] True 20-second silence triggers `hard_silence_timeout`
- [ ] `response.audio.done` only updates audio state, doesn't trigger hangup
- [ ] User goodbye phrases trigger `user_goodbye` hangup
- [ ] Bot goodbye phrases trigger `bot_goodbye` hangup
- [ ] Invalid reasons are blocked and logged
- [ ] All hangup decisions are logged with `[HANGUP_DECISION]`

## Deployment Notes

- No database changes required
- No configuration changes required
- Changes are backward compatible
- Existing hangup flows continue to work (with improved validation)
- New logging provides better visibility for debugging

## Rollback Plan

If issues arise, revert commits:
- `7cb24ae` - Fix code review issues: remove duplicate comment, consolidate reasons
- `499e942` - Fix hangup logic: add reason validation, improve audio state tracking

The system will revert to the previous behavior (which had the premature disconnect issue).
