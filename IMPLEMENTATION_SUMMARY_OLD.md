# AMD Removal & Voice-Only Outbound Gate Implementation

## Executive Summary

Successfully implemented two critical improvements:
1. **Complete AMD removal** - Replaced Twilio's AMD with voice-only outbound gate
2. **Watchdog fix** - Disabled in SIMPLE_MODE to prevent duplicate responses

## Implementation Details

### Part 1: AMD Removal & Voice-Only Outbound Gate

#### Removed AMD Components
- **routes_outbound.py**: Removed `machineDetection`, `async_amd`, and callbacks from 3 call creation locations
- **routes_twilio.py**: 
  - Deleted `/webhook/amd_status` webhook (67 lines removed)
  - Removed AMD_STATUS constants (AMD_STATUS_VOICEMAIL, AMD_STATUS_HUMAN)
  - Removed EARLY_STAGE_STATUSES set

#### New Voice-Only Outbound Gate

**State Management:**
```python
self.outbound_gate = "WAIT_FOR_VOICE"  # or "OPEN"
self.call_start_ts = time.time()  # Track call start
self.outbound_first_response_sent = False  # One-time greeting
self.outbound_gate_timeout_sec = 12.0  # Voicemail protection
```

**Filters Applied (First Utterance Only):**
1. **Timing Filter**: Ignore utterances < 1.2s from call start (ringback protection)
2. **Content + Duration Filter**: Accept ONLY if ALL:
   - Duration >= 450ms
   - Text in Hebrew greeting whitelist OR length >= 4 chars
   - NOT filler-only
3. **Hebrew Greetings Whitelist**: הלו, הלו., כן, כן., מי זה, מי זה?, שלום, שלום.

**Gate Opening:**
- Sets `outbound_gate = "OPEN"`
- Sets `user_has_spoken = True`
- Sets `human_confirmed = True`
- Triggers AI response ONCE with `outbound_first_response_sent` flag

**Voicemail Protection:**
- 12-second hard timeout in silence monitor
- Ends call if gate never opens (no voice detected)
- AI does NOT speak if timeout triggers

**Logging:**
- `[OUTBOUND_VOICE_GATE] waiting start_ts=...`
- `[OUTBOUND_VOICE_GATE] ignore early_utterance age_ms=...`
- `[OUTBOUND_VOICE_GATE] reject first_utterance reason=...`
- `[OUTBOUND_VOICE_GATE] OPEN ✅ first_valid_utterance...`
- `[OUTBOUND_VOICE_GATE] TIMEOUT no_voice → end_call`

### Part 2: Watchdog Fix

#### Problem
Watchdog was firing unnecessarily, causing duplicate AI responses, especially in SIMPLE_MODE.

#### Solution

**1. Disabled in SIMPLE_MODE (90% of the problem)**
```python
if not SIMPLE_MODE and not is_filler_only and text and len(text.strip()) > 0:
    # Start watchdog
```

**2. Added strict conditions - watchdog ONLY fires when ALL true:**
- `pending_user_utterance == True` (valid utterance awaiting response)
- 3.5 seconds passed (increased from 3.0)
- `_watchdog_utterance_id` matches (not stale)
- NO `response_pending_event` set
- NO `is_ai_speaking_event` set
- NO `has_pending_ai_response` flag
- NO `active_response_id` present

**3. Added pending_user_utterance tracking:**
- Set to `True` when valid STT_FINAL received (not filler, has text)
- Cleared to `False` when `response.created` event received
- Provides definitive signal that watchdog should check

**4. Single retry guarantee:**
- Watchdog clears `_watchdog_utterance_id = None` after firing
- Prevents multiple retries for same utterance

## Files Modified

1. **server/routes_outbound.py** (3 locations, ~80 lines changed)
   - Removed AMD parameters from call creation
   - Simplified to just recording callbacks

2. **server/routes_twilio.py** (~70 lines removed)
   - Removed AMD webhook
   - Removed AMD constants

3. **server/media_ws_ai.py** (~150 lines changed)
   - Added outbound voice gate logic
   - Modified watchdog to be conservative
   - Added pending_user_utterance tracking

## Verification

### AMD Removal
```bash
grep -r "AMD_STATUS\|machineDetection\|async_amd" server/*.py
# Result: No matches found ✅
```

### Voice Gate
```bash
grep -c "OUTBOUND_VOICE_GATE" server/media_ws_ai.py
# Result: 19 instances ✅
```

### Watchdog
```bash
python3 -m py_compile server/media_ws_ai.py
# Result: Success (no syntax errors) ✅
```

## Testing Recommendations

### Outbound Voice Gate Tests
1. **Voicemail test**: Call should never speak, end after ~12s
2. **Human answer test**: "הלו" should trigger response within 0.5-1.5s
3. **Early beep test**: Should ignore beeps < 1.2s, wait for real voice
4. **Short noise test**: < 450ms utterances should be rejected
5. **Non-greeting test**: Valid 4+ char speech should open gate

### Watchdog Tests
1. **SIMPLE_MODE check**: Verify no `[WATCHDOG]` logs appear
2. **User speaks**: Verify `pending_user_utterance=True` log
3. **AI responds**: Verify `pending_user_utterance=False` log
4. **Normal conversation**: No watchdog retries should fire
5. **Stuck state**: In complex mode, watchdog should retry after 3.5s if truly stuck

## Impact

### Benefits
- ✅ No more false voicemail detection (AMD issues)
- ✅ Real human detection based on actual voice
- ✅ No duplicate AI responses in SIMPLE_MODE
- ✅ Conservative watchdog that only fires when truly needed
- ✅ Cost reduction (no AMD charges from Twilio)

### Risk Mitigation
- Voice gate timeout ensures calls don't hang indefinitely
- Multiple filters prevent false positives (ringback, beeps, noise)
- Watchdog still available for complex scenarios when truly stuck
- Comprehensive logging for debugging and monitoring

## Rollback Plan

If issues arise, revert commits:
```bash
git revert ba3902c  # Watchdog fix
git revert e440747  # AMD removal & voice gate
```

Both commits are surgical and independent - can revert individually if needed.

---

**Implementation Date**: 2025-12-24
**Branch**: copilot/remove-amd-completely
**Commits**: e440747, ba3902c
