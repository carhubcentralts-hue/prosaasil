# Production Verification Testing Guide

## Overview
This document provides detailed instructions for the 5 required production verification tests as specified in the Master Instruction.

---

## Pre-Test Setup

### 1. Enable Debug Logging
Ensure the following environment variables are set:
```bash
DEBUG=1  # Enable detailed logging
```

### 2. Test Environment
- Use production or staging environment with real Twilio connection
- Ensure OpenAI Realtime API is available
- Have access to log aggregation/viewing tools

### 3. Log Collection
For each test, collect logs containing these markers:
- `[LOCAL_VAD]`
- `[BARGE-IN]`
- `[STT_ACCEPT]` / `[STT_DROP]`
- `[SILENCE]`
- `[SILENCE_FOLLOWUP_CREATE]`
- `[TURN_LATENCY]`
- `[BOTTLE_NECK]`
- `[PROMPT_BIND]`

---

## Test 1: Barge-in During AI Speech

### Objective
Verify that the system immediately stops AI speech when user speaks over it, using LOCAL-VAD force cancel.

### Test Steps
1. Start a call
2. Wait for AI to start speaking a response (multi-sentence response preferred)
3. **While AI is speaking**, start talking immediately (interrupt mid-sentence)
4. Continue speaking for 0.2-0.3 seconds
5. Verify AI stops immediately

### Expected Behavior
- AI stops speaking within 200-250ms
- User voice is captured without delay
- System transitions to listening mode

### Success Criteria (PASS)

**Required Logs**:
```
[LOCAL_VAD] 🔶 CANDIDATE barge-in detected: 8 voice_frames → enabling forward + flush_preroll | ai_speaking=True
🛑 [BARGE-IN FORCE] local_vad_frames=10, rms=85.3, response_id=resp_abc...
✅ [BARGE-IN FORCE] cancel sent for resp_abc...
✅ [BARGE-IN FORCE] Twilio TX queue flushed
✅ [BARGE-IN FORCE] Marked as confirmed
```

OR (if STT confirms first):
```
[BARGE-IN] 🔶 CANDIDATE: Possible user speech detected while AI speaking
[BARGE-IN] ✅ CONFIRMED: word_count>=2 text='כן, אני רוצה...'
[BARGE-IN] Cancelled AI response: resp_abc...
✅ [BARGE-IN] ✅ CONFIRMED flush: 25 frames cleared
```

**PASS if**:
- ✅ Either `[BARGE-IN FORCE]` OR `[BARGE-IN] ✅ CONFIRMED` appears
- ✅ AI stops speaking immediately
- ✅ No continued audio after cancellation
- ✅ User utterance is captured and processed

**FAIL if**:
- ❌ No `[BARGE-IN FORCE]` or `[BARGE-IN] CONFIRMED` logs
- ❌ AI continues speaking over user
- ❌ Delay > 300ms before AI stops

---

## Test 2: Fast Answer (0.1-0.3s Response)

### Objective
Verify that fast user responses are NOT dropped as echo, preventing conversation loops.

### Test Steps
1. Start a call
2. Wait for AI to ask a question requiring a city/service name (e.g., "איזו עיר?")
3. **Immediately** answer with a Hebrew city name (within 0.1-0.3s): "בית שמש" or "בית שאן"
4. Verify the answer is accepted and AI progresses (does NOT repeat the question)

### Expected Behavior
- User's fast answer is accepted
- AI acknowledges and moves forward
- NO loop ("איזו עיר?" repeated)

### Success Criteria (PASS)

**Required Logs**:
```
[STT_ACCEPT] reason=echo_bypass bypass_conditions=sustained_vad_7frames, fast_response_150ms, hebrew_city_or_service candidate=True vad=7 text='בית שמש'
```

OR at minimum:
```
[STT_ACCEPT] reason=echo_bypass bypass_conditions=sustained_vad_5frames candidate=True vad=5 text='בית שאן'
```

**PASS if**:
- ✅ `[STT_ACCEPT] reason=echo_bypass` appears
- ✅ Text matches user's city/service input
- ✅ AI progresses to next question (does NOT repeat "איזו עיר?")

**FAIL if**:
- ❌ `[STT_DROP] reason=echo_window text='בית שאן'` appears
- ❌ AI repeats the same question again
- ❌ Conversation enters a loop

---

## Test 3: Silence (20 seconds)

### Objective
Verify that silence handling does NOT send SYSTEM messages as user input, and behaves correctly based on mode.

### Test Steps
1. Start a call
2. Wait for greeting to complete
3. Speak once (to set `user_has_spoken=true`)
4. **Remain completely silent** for 20+ seconds
5. Observe AI behavior

### Expected Behavior

**SIMPLE_MODE**:
- AI does NOT prompt or intervene
- Line stays open
- Logs show passive monitoring

**Normal Mode**:
- AI may ask "are you there?" after configured silence timeout
- Uses `response.create` with instructions (NOT user input)

### Success Criteria (PASS)

**SIMPLE_MODE Logs**:
```
🔇 [SILENCE] SIMPLE_MODE - keeping line open after 20.0s silence
[SILENCE] keeping open... no AI intervention in SIMPLE_MODE
```

**Normal Mode Logs**:
```
✅ [SILENCE_FOLLOWUP_CREATE] Max warnings - response.create sent
```

OR:
```
✅ [SILENCE] response.create sent successfully
```

**PASS if**:
- ✅ **NO** `[AI_INPUT_BLOCKED]` logs containing "User silent" or "[SYSTEM]"
- ✅ SIMPLE_MODE: No AI intervention, only logs
- ✅ Normal Mode: `[SILENCE_FOLLOWUP_CREATE]` appears
- ✅ If AI speaks, it's from `response.create`, not user input injection

**FAIL if**:
- ❌ `[AI_INPUT_BLOCKED] kind=server_event reason=never_send_to_model text_preview='[SYSTEM] User silent...'`
- ❌ AI receives SYSTEM message as user input
- ❌ Silent drop (no logs, call just hangs)

---

## Test 4: Latency Measurement

### Objective
Verify comprehensive latency tracking identifies bottlenecks accurately.

### Test Steps
1. Start a call
2. Have a normal conversation (2-3 exchanges)
3. Collect `[TURN_LATENCY]` and `[BOTTLE_NECK]` logs from each turn

### Expected Behavior
- Every turn logs detailed timing breakdown
- Bottlenecks are identified when thresholds are exceeded
- Total latency is stable (not varying wildly)

### Success Criteria (PASS)

**Required Logs** (every turn):
```
[TURN_LATENCY] stop→commit=50ms | commit→stt=650ms | stt→create=180ms | create→audio1=850ms | total(stop→audio1)=1680ms | direction=inbound business_id=123
```

**Optional** (if bottlenecks exist):
```
⚠️ [BOTTLE_NECK] Slow stages: STT=920ms>800ms, AUDIO1=1350ms>1200ms_OPENAI/NETWORK?
```

**PASS if**:
- ✅ `[TURN_LATENCY]` appears for EVERY user turn
- ✅ Breakdown shows: `stt_ms`, `create_ms`, `first_audio_ms`, `total_ms`
- ✅ `[BOTTLE_NECK]` appears ONLY when thresholds exceeded
- ✅ Total latency is generally stable (< 2500ms for normal turns)

**Thresholds** (informational, not FAIL criteria):
- **Target**: stt_ms < 900ms
- **Target**: create_ms < 300ms (if exceeded → check DB/locks)
- **Target**: first_audio_ms < 1200ms (if exceeded → check OpenAI/network)

**FAIL if**:
- ❌ No `[TURN_LATENCY]` logs
- ❌ Missing timing components (stt_ms, create_ms, etc.)
- ❌ Total latency consistently > 4000-5000ms (indicates real problem)

---

## Test 5: Stability Close

### Objective
Verify clean call termination with no double-close errors or ASGI issues.

### Test Steps
1. Start a call
2. Have a brief conversation (1-2 exchanges)
3. Say goodbye (e.g., "תודה, להתראות")
4. Wait for AI to say goodbye
5. Call should end cleanly

### Expected Behavior
- AI says goodbye politely
- Call terminates cleanly
- No errors in logs during shutdown

### Success Criteria (PASS)

**Required Logs**:
```
✅ [SILENCE_FOLLOWUP_CREATE] Goodbye response.create sent
🔇 [SILENCE] Monitor exiting - call state is CLOSING
```

OR:
```
[CALL_STATE] ACTIVE → CLOSING (reason: user_goodbye)
```

**PASS if**:
- ✅ No double-close errors
- ✅ No `Unexpected ASGI message 'websocket.close'` errors
- ✅ No `WebSocket already closed` errors
- ✅ Clean shutdown sequence in logs
- ✅ Call ends within 3-5 seconds of goodbye

**FAIL if**:
- ❌ `Unexpected ASGI message 'websocket.close' after sending 'websocket.close'`
- ❌ Double-close errors
- ❌ Crash/exception during shutdown
- ❌ Call hangs after goodbye (doesn't end)

---

## Additional Verification: Prompt Binding

### Objective
Verify dynamic prompt configuration with no hardcoding.

### Test Steps
1. Check logs at call start (first 30 seconds)

### Success Criteria (PASS)

**Required Logs** (at call start):
```
📋 [PROMPT_BIND] business=123, hash=a3f2c1b4, direction=inbound, goal=lead_collection
[PROMPT_BIND] business_id=123 prompt_hash=a3f2c1b4 direction=inbound call_goal=lead_collection scheduling=True
```

**PASS if**:
- ✅ `[PROMPT_BIND]` appears within first 10 seconds of call
- ✅ Contains: `business_id`, `prompt_hash`, `direction`
- ✅ `prompt_hash` is consistent throughout call (no mid-call changes)
- ✅ No hardcoded city/service/script logic in logs

**FAIL if**:
- ❌ No `[PROMPT_BIND]` log
- ❌ Missing required fields
- ❌ `prompt_hash` changes mid-call

---

## Test Results Template

Use this template to record results:

```markdown
## Test Results - [Date/Time]

### Environment
- Mode: [SIMPLE_MODE / Normal Mode]
- Business ID: [...]
- Call SID: [...]

### Test 1: Barge-in
- **Result**: [PASS / FAIL]
- **Latency**: [... ms]
- **Logs**: 
  ```
  [paste key logs here]
  ```
- **Notes**: [...]

### Test 2: Fast Answer
- **Result**: [PASS / FAIL]
- **City Tested**: [בית שמש / בית שאן / ...]
- **Logs**:
  ```
  [paste key logs here]
  ```
- **Notes**: [...]

### Test 3: Silence
- **Result**: [PASS / FAIL]
- **Duration**: [... seconds]
- **Logs**:
  ```
  [paste key logs here]
  ```
- **Notes**: [...]

### Test 4: Latency
- **Result**: [PASS / FAIL]
- **Average Total**: [... ms]
- **Bottlenecks**: [STT / CREATE / AUDIO1 / None]
- **Logs**:
  ```
  [paste key logs here]
  ```
- **Notes**: [...]

### Test 5: Stability Close
- **Result**: [PASS / FAIL]
- **Logs**:
  ```
  [paste key logs here]
  ```
- **Notes**: [...]

### Prompt Binding
- **Result**: [PASS / FAIL]
- **Business ID**: [...]
- **Prompt Hash**: [...]
- **Logs**:
  ```
  [paste key logs here]
  ```

## Overall Assessment
- **PASS Count**: [... / 5]
- **FAIL Count**: [... / 5]
- **Status**: [READY FOR PRODUCTION / NEEDS FIXES]
- **Action Items**: [...]
```

---

## Troubleshooting

### No BARGE-IN FORCE Logs
**Possible Causes**:
1. `local_vad_frames` not reaching threshold (check RMS levels)
2. User speaking too quietly (increase volume)
3. AI not actually speaking when interrupt attempted

**Check**: Look for `[LOCAL_VAD]` logs with voice_frames count

### Fast Answer Still Dropped
**Possible Causes**:
1. Answer TOO fast (< 50ms after AI stops)
2. Low similarity to Hebrew lexicon (gibberish detection)
3. VAD not detecting voice

**Check**: Look for `[STT_DROP]` logs with full reasoning

### AI_INPUT_BLOCKED Still Appearing
**Possible Causes**:
1. Different code path not updated
2. Old cached code

**Action**: 
1. Verify all commits are deployed
2. Check for any other `_send_text_to_ai("[SYSTEM]")` calls
3. Restart service to clear any cached modules

### High Latency Bottlenecks
**If CREATE stage slow**:
- Check for DB locks or heavy queries
- Profile post-turn processing
- Move heavy operations to background

**If AUDIO1 stage slow**:
- Check OpenAI API status
- Verify network latency
- Consider regional endpoint changes

---

## Success Criteria Summary

**READY FOR PRODUCTION** if:
- ✅ 5/5 tests PASS
- ✅ No AI_INPUT_BLOCKED violations
- ✅ No double-close errors
- ✅ Barge-in < 300ms
- ✅ Echo_window bypass working
- ✅ Latency tracked and stable

**NEEDS FIXES** if:
- ❌ Any test FAILS
- ❌ AI_INPUT_BLOCKED violations present
- ❌ Stability issues (crashes, hangs)
- ❌ Barge-in > 500ms or not working
- ❌ Loops detected

---

## Contact

If any test fails:
1. Collect logs (20-40 lines around failure)
2. Note exact reproduction steps
3. Share with engineering team for analysis
4. Include call_sid and timestamp

**Good luck with testing! 🚀**
