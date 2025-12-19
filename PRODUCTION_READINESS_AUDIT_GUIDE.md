# ✅ Production Readiness Audit - Verification Guide

## Overview

This document provides comprehensive verification procedures for the production readiness audit requirements. Each section corresponds to a requirement from the audit specification.

**🎯 CRITICAL: This guide includes 4 critical additions + Audit Walkthrough for zero-surprise deployment.**

---

## A) Realtime Audio Pipeline Verification

### A1. Audio Rate and Timing Verification ✅

**What to check in logs:**
- `[TX_METRICS]` appears **every second** during active call
- `fps` value should be ≈50 (acceptable range: 47-52)
- `max_gap_ms` should be <60ms
- At call end, check `[CALL_METRICS]` for `frames_dropped=0`

**✅ PASS Criteria:**
```
[TX_METRICS] fps=50.2, max_gap_ms=23.5, frames=50, q=0/500
...
[CALL_METRICS] ... frames_dropped=0
```

**❌ FAIL Patterns:**
```
[TX_METRICS] fps=8.3, max_gap_ms=850.2  # Low FPS, high gaps
[CALL_METRICS] ... frames_dropped=234   # Frames dropped
```

**Location in code:**
- `server/media_ws_ai.py:12262-12274` - TX_METRICS logging
- `server/media_ws_ai.py:12950-13006` - CALL_METRICS logging

---

### 🔥 A1+ (Speech Continuity) - CRITICAL ADDITION

**Test scenario:** Trigger long AI response (10-20 seconds)

**✅ PASS:**
```
[TX_METRICS] fps=49.8, max_gap_ms=35.2
[TX_METRICS] fps=50.1, max_gap_ms=42.0
[TX_METRICS] fps=50.3, max_gap_ms=38.5
# No silence mid-sentence
# No max_gap_ms jumping above 200ms
# Continuous speech until response.audio.done
```

**❌ FAIL:**
```
[TX_METRICS] fps=50.2, max_gap_ms=55.0
# [SILENCE FOR 500ms - NO LOGS]
[TX_METRICS] fps=49.8, max_gap_ms=520.0  # GAP SPIKE!
# AI resumes mid-sentence
```

**What this catches:** TX underrun, scheduling jitter, queue drain issues, race between threads

---

### A2. Half-Duplex Voice Detection ✅

**What to verify in code:**
- Local VAD is computed **before** "Blocking audio to OpenAI" decision
- CANDIDATE barge-in can be detected while AI is speaking

**✅ PASS:**
```
[LOCAL_VAD] CANDIDATE barge-in detected: 12 voice_frames → enabling forward
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
```

**Location in code:**
- `server/media_ws_ai.py:2897-2941` - Local VAD computed first, then blocking decision

---

### 🔥 B1+ (Hard Case: Early Interrupt) - CRITICAL ADDITION

**Test scenario:** Start speaking **immediately** when AI starts (0-200ms into response), not just 300-700ms

**✅ PASS:**
```
[BARGE-IN] AI starting to speak - response_id=resp_abc...
[LOCAL_VAD] 🔶 CANDIDATE barge-in detected: 9 voice_frames
[BARGE-IN] ✅ CONFIRMED: intent_aware_single_token text='כן'
🧹 [BARGE-IN FLUSH] ...
```

**❌ FAIL:**
```
[BARGE-IN] AI starting to speak
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
# NO CANDIDATE appears during entire user speech
# AI continues talking, ignoring user
```

**What this catches:** Noise gate / half-duplex blocking audio forwarding too early → STT never arrives → AI keeps talking

**Audit point:** Verify in code that `local VAD` computation happens BEFORE any `continue` statement in half-duplex block.

---

### A3. Double Speaking Prevention ✅

**Test scenario:** Interrupt AI mid-sentence, then stay silent

**✅ PASS:**
```
🧹 [BARGE-IN FLUSH] OpenAI queue: 45/50 frames | TX queue: 12/15 frames
# After flush, no more audio from old response_id
# active_response_id resets to None
```

**❌ FAIL:**
- Old AI response continues after barge-in flush
- Same response_id appears in audio.delta after cancellation

**Location in code:**
- `server/media_ws_ai.py:3176-3178` - Barge-in flush logging
- `server/media_ws_ai.py:3458-3464` - Cancelled response filtering

---

## B) Barge-In Two-Stage Verification

### B1. Real Interrupt ✅

**Test scenario:** Interrupt AI after 300-700ms of speaking

**✅ PASS logs:**
```
[LOCAL_VAD] 🔶 CANDIDATE: Possible user speech detected
[BARGE-IN] ✅ CONFIRMED: intent_aware_single_token text='כן'
[BARGE-IN] Cancelled AI response: resp_abc123...
🧹 [BARGE-IN FLUSH] ...
[CALL_METRICS] ... barge_in_events=3
```

**❌ FAIL:**
- `barge_in_events=0` despite interrupting
- AI continues speaking after CONFIRMED
- Cancel happens without CONFIRMED

**Location in code:**
- `server/media_ws_ai.py:2924-2931` - CANDIDATE detection
- `server/media_ws_ai.py:5093-5124` - CONFIRMED barge-in
- `server/media_ws_ai.py:12966` - barge_in_events metric

---

### B2. Noise Rejection ✅

**Test scenario:** Breathing/background noise while AI speaks

**✅ PASS:**
```
[LOCAL_VAD] CANDIDATE barge-in detected
[BARGE-IN] ❌ NOT CONFIRMED: filler_only text='אממ'
# AI continues speaking - no cancellation
```

**Location in code:**
- `server/media_ws_ai.py:5125-5127` - NOT CONFIRMED logging

---

### B3. No Spurious OpenAI turn_detected ✅

**What to check:**

**✅ PASS:**
```
[RESPONSE] Cancelled: reason=turn_detected
✅ [B3] turn_detected after confirmed barge-in (expected)
```

**❌ FAIL:**
```
⚠️ [B3 VIOLATION] OpenAI turn_detected cancellation WITHOUT confirmed barge-in!
```

This indicates audio is leaking to OpenAI during AI speech (half-duplex not working).

**Location in code:**
- `server/media_ws_ai.py:3477-3495` - turn_detected detection and logging

---

## C) STT Quality + Echo Window

### C1. Echo Window Bypass on Real Speech ✅

**Test scenario:** Answer "בית שאן" very quickly (0.1-0.3s) after AI asks "איזו עיר?"

**✅ PASS:**
```
[C1 STT_GUARD] Accepted (echo_window bypass: fast_response_150ms) text='בית שאן'
# AI proceeds with response, doesn't ask again
```

**❌ FAIL:**
```
[STT_FILTER] drop reason=echo_window ... text='בית שאן'
# AI asks "איזו עיר?" again → creates loop
```

**Location in code:**
- `server/media_ws_ai.py:1238-1289` - Enhanced echo window bypass with fast_response detection

---

### C2. Hallucinations Don't Drop Real Words ✅

**What to verify:**
- Real city names, numbers, yes/no answers are accepted even if short
- Intent-aware validation allows single-token meaningful responses

**✅ PASS:**
```
[STT_GUARD] Accepted short phrase: 'כן' (valid Hebrew phrase in whitelist)
[BARGE-IN] ✅ CONFIRMED: intent_aware_single_token text='כן'
```

**Location in code:**
- `server/media_ws_ai.py:1273-1293` - Minimum word count with valid short phrase whitelist
- `server/media_ws_ai.py:5047-5090` - Intent-aware single token barge-in

---

### C3. Noise Gate - Re-enabled Correctly ✅

**What to verify:**
- Noise gate is active when AI speaks (blocks noise from being sent to OpenAI)
- But does NOT choke local VAD or CANDIDATE detection

**✅ PASS:**
```
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
[LOCAL_VAD] CANDIDATE barge-in detected: 10 voice_frames
# Both can happen - gate blocks but VAD still runs
```

**Location in code:**
- `server/media_ws_ai.py:2933-2941` - Half-duplex blocking
- `server/media_ws_ai.py:2897-2912` - Local VAD runs independently

---

## D) Appointment Scheduling End-to-End

### D1. Precise Activation Conditions ✅

**What to check in logs:**

**✅ PASS (tools enabled):**
```
[D1 TOOLS ENABLED] business_id=123, call_goal=appointment, enable_calendar_scheduling=True, tools_count=2
```

**✅ PASS (tools disabled):**
```
[D1 TOOLS DISABLED] business_id=123, call_goal=lead_only, enable_calendar_scheduling=False, tools_count=0
```

**Location in code:**
- `server/media_ws_ai.py:1878-2005` - Tool building with dual condition check
- `server/media_ws_ai.py:1912` - Explicit check: `call_goal == 'appointment' and enable_scheduling`

---

### D2. Two-Tool Workflow Enforced ✅

**What to verify:**
- AI always calls `check_availability` first
- Only after successful check → calls `book_appointment`

**✅ PASS:**
```
📅 [CHECK_AVAIL] Request from AI: {...}
✅ [CHECK_AVAIL] Found 3 available slot(s)
📅 [BOOK_APPT] Request from AI: {...}
✅ [BOOK_APPT] SUCCESS! ID=456
```

**❌ FAIL:**
- AI calls `book_appointment` without prior `check_availability`

**Tool definitions:**
- `server/media_ws_ai.py:1915-1949` - check_availability tool
- `server/media_ws_ai.py:1952-1990` - book_appointment tool (description requires checking first)

---

### 🔥 D2+ (No Fake Booking) - CRITICAL ADDITION

**Test scenario:** Force tool to fail (invalid slot, timeout, or DB error)

**✅ PASS:**
```
❌ [BOOK_APPT] APPT_TOOL_FAILED: ...
[D5 APPT_TOOL_FAILED] Exception in book_appointment
[D5 FALLBACK_LEAD_CREATED] Activating fallback flow
✅ [BOOK_APPT] Lead verified/created for follow-up
# AI says: "לקחתי פרטים ונציג יחזור אליך"
# NOT: "קבעתי לך פגישה" (lie!)
```

**❌ FAIL:**
```
# Tool fails silently
# AI says: "הפגישה נקבעה בהצלחה!"
# But no BOOK_APPT SUCCESS in logs
```

**What this catches:** AI hallucinating successful booking when tool failed

**Audit point:** Verify ALL exception handlers return `function_call_output` + `response.create`, never silent fail.

---

### D3. Handler Output Correctness ✅

**What to verify:**
- **Every path** (success, validation error, exception) returns:
  1. `function_call_output` with JSON
  2. `response.create` to continue conversation

**✅ PASS paths:**

**check_availability:**
- Success: Lines 10985-11015
- No slots: Lines 11002-11015
- Validation error: Lines 10916-10930
- Exception: Lines 11017-11034

**book_appointment:**
- Success: Lines 11163-11178
- Validation error: Lines 11064-11078
- Duplicate: Lines 11083-11096
- Creation failed: Lines 11186-11198
- Exception: Lines 11200-11231

All paths end with `await client.send_event({"type": "response.create"})`

---

### D4. Timezone + ISO Correctness ✅

**What to check in logs:**

**✅ PASS:**
```
[D4 TIMEZONE] Localized naive datetime to Asia/Jerusalem: 2025-12-15T14:00:00+02:00
📅 [BOOK_APPT] Creating: 2025-12-15T14:00:00+02:00 -> 2025-12-15T15:00:00+02:00
```

**Location in code:**
- `server/media_ws_ai.py:11110-11132` - Timezone normalization with logging

---

### D5. Real Fallback Path ✅

**Test scenario:** Force DB/Calendar failure (e.g., invalid business_id)

**✅ PASS:**
```
❌ [BOOK_APPT] APPT_TOOL_FAILED: ...
[D5 APPT_TOOL_FAILED] Exception in book_appointment
[D5 FALLBACK_LEAD_CREATED] Activating fallback flow
✅ [BOOK_APPT] Lead verified/created for follow-up
# AI response: "לקחתי את הפרטים ונציג יחזור אליך"
```

**Location in code:**
- `server/media_ws_ai.py:11200-11231` - Exception handler with fallback logging

---

## E) Prompt / Business Context Integrity

### E1. Prompt Upgrade & Binding ✅

**What to check:**

**✅ PASS:**
```
🔄 [PROMPT UPGRADE] Upgrading from COMPACT (800 chars) to FULL (3500 chars)
✅ [PROMPT UPGRADE] Successfully upgraded to FULL prompt in 45ms
[E1 PROMPT UPGRADE] business_id=123, upgrade_duration_ms=45, policy={'call_goal': 'appointment', ...}
```

**Location in code:**
- `server/media_ws_ai.py:3516-3554` - Prompt upgrade with enhanced logging

---

### E2. System + Business Prompt Order ✅

**What to verify:**
- Prompts are injected in fixed order: system → business
- No override after call starts that removes critical rules

**Location in code:**
- `server/media_ws_ai.py:2367-2429` - Prompt building with fixed order
- Business prompt is embedded within system instructions consistently

---

## F) Cleanup / Threads / Stability

### F1. Flags Reset ✅

**What to check at call end:**

**✅ PASS:**
```
🧹 [CLEANUP] Resetting all state flags...
✅ [CLEANUP] All state flags reset successfully
# All flags reset: _barge_pending, _barge_confirmed, _appointment_created_this_session, etc.
```

**Location in code:**
- `server/media_ws_ai.py:8159-8252` - Comprehensive state reset

---

### F2. No Background Threads Stuck ✅

**What to check:**

**✅ PASS:**
```
🧹 Waiting for 4 background threads...
✅ Background thread 0 completed
✅ Background thread 1 completed
✅ Background thread 2 completed
✅ Background thread 3 completed
✅ All background threads cleanup complete
```

**❌ FAIL:**
```
⚠️ [F2 VIOLATION] Background thread 2 (RealtimeThread) still running after 5s timeout
⚠️ [F2 VIOLATION] 2/4 threads still alive after cleanup
```

**Location in code:**
- `server/media_ws_ai.py:8131-8149` - Enhanced thread cleanup with better logging

---

### F3. WebSocket Close Errors ✅

**What to verify:**

**✅ PASS:**
```
✅ [F3] WebSocket closed successfully
```

**Also acceptable (graceful handling):**
```
[F3] WebSocket wrapper doesn't support close() - connection already terminated
[F3] Websocket already closed (expected): ...
```

**❌ FAIL (red alert errors):**
```
Unexpected ASGI message 'websocket.close'...
SyncWebSocketWrapper has no close
# Without [F3] prefix or proper handling
```

**Location in code:**
- `server/media_ws_ai.py:8254-8277` - Enhanced WebSocket close with AttributeError handling

---

## G) Anti-Loop Guard

### G1. Duplicate Question Detection ✅

**Test scenario:** Let AI ask "איזו עיר?" twice without user speaking

**✅ PASS:**
```
⚠️ [G ANTI-LOOP] Duplicate question detected! Similarity=92% | Current: 'איזו עיר אתה נמצא?' | Previous: 'איזו עיר?'
[SYSTEM] Message sent: אתה שואל את אותה שאלה שוב. המתן לתשובת הלקוח...
# AI pauses and waits for user
```

**❌ FAIL:**
- Same question appears 3+ times in a row
- No loop detection warning
- AI doesn't pause after duplicate

**Location in code:**
- `server/media_ws_ai.py:4512-4563` - Enhanced loop detection with consecutive duplicate check

---

### 🔥 End (Call End Sanity) - CRITICAL ADDITION

**Test scenario:** After "תודה ולהתראות" from user

**✅ PASS (auto-hangup enabled):**
```
[GOODBYE] User said goodbye
[GOODBYE] will_hangup=True - goal=lead_only, user said goodbye
[HANGUP] Triggering hangup: user_goodbye
# Call ends cleanly
```

**✅ PASS (auto-hangup disabled):**
```
[GOODBYE] User said goodbye
# Silence - no more prompts
# AI doesn't loop back to questions
```

**❌ FAIL:**
```
[GOODBYE] User said goodbye
# AI says: "איזו עיר?" (loops back to questions)
# OR: [HANGUP BLOCKED] despite clear goodbye
# OR: Double/overlapping speech after goodbye
```

**What this catches:** Prompts continuing conversation after closing, loops after goodbye, hangup logic broken

**Audit point:** Check `auto_end_on_goodbye` flag + `call_goal` interaction in goodbye detection logic.

---

## 🔍 AUDIT WALKTHROUGH - Code Review Checklist

### 1) server/media_ws_ai.py — Audio Input from Twilio

**File:** `server/media_ws_ai.py:2760-3000`

**What to verify:**
- ✅ Local VAD computed **before** any `return` or `continue` in half-duplex block
- ✅ Ring buffer / preroll always fills
- ❌ NO path where `[HALF-DUPLEX] Blocking...` happens before `_local_vad_voice_frames` increment

**Code audit:**
```python
# GOOD - VAD first, then blocking decision
# Lines 2897-2912: Local VAD computation
if frame_rms > speech_threshold:
    self._local_vad_voice_frames += 1
    
# Lines 2913-2941: Then check if should block
if ai_currently_speaking and not self._barge_pending:
    # Block audio
    continue
```

---

### 2) echo_window + STT Filters

**File:** `server/media_ws_ai.py:1190-1310`

**What to verify:**
- ✅ Bypass conditions are limited and measured:
  - Only when `candidate_user_speaking=True`
  - OR `local_vad_frames >= 8`
  - OR `fast_response_100ms` with Hebrew text
- ❌ NO "always bypass" logic (would let noise through)

**Code audit:**
```python
# Lines 1238-1271
should_bypass_echo_window = (
    has_user_speech_candidate or 
    has_sustained_vad or 
    is_new_content or 
    is_fast_but_real_response  # ✅ Specific conditions
)
```

---

### 3) Barge-in State Machine

**File:** `server/media_ws_ai.py:2920-2940, 5090-5130`

**What to verify:**
- ✅ CANDIDATE does NOT cancel/flush (only sets `_barge_pending`)
- ✅ CONFIRMED always does:
  - Cancel `active_response_id`
  - TX flush (including `_ai_audio_buf`)
  - Reset flags (`_barge_pending`, `_barge_confirmed`)
- ❌ NO path that skips reset at end of utterance/call

**Code audit:**
```python
# Lines 2924-2931: CANDIDATE
if local_vad_frames >= 8:
    self._barge_pending = True  # ✅ Only flag, no cancel
    
# Lines 5093-5124: CONFIRMED
if should_confirm_barge_in:
    # Cancel response ✅
    await client.cancel_response(...)
    # Flush TX ✅
    self._flush_twilio_tx_queue(reason="BARGE_IN_CONFIRMED")
    # Reset flags happen in speech_stopped handler ✅
```

---

### 4) TX Loop / Framer / Pacing

**File:** `server/media_ws_ai.py:12150-12290`

**What to verify:**
- ✅ Framer sends only 160B frames (20ms μ-law)
- ✅ Clock pacing at 20ms (`FRAME_SEC = 0.020`)
- ✅ Resync if behind schedule (no sleep with negative delay)
- ❌ NO drop logic that returned accidentally
- ✅ `avg_fps` at call end should be ≈50, not 6-20

**Code audit:**
```python
# Lines 12170-12171
FRAME_SEC = 0.020  # ✅ 20ms
next_send = time.monotonic()

# Lines 12216-12223: Resync if behind
if delay < 0:
    next_send = now  # ✅ Resync, don't sleep negative
elif delay > 0:
    time.sleep(delay)
```

---

### 5) Tools: check_availability / book_appointment

**File:** `server/media_ws_ai.py:10903-11231`

**What to verify:**
- ✅ Tool activation condition (call_goal + enable_scheduling) in ONE clear place
- ✅ Every handler path ends with:
  - `function_call_output`
  - THEN `response.create`
- ❌ NO "silent fail" (exception without output)

**Code audit:**
```python
# Lines 1912: Single activation check
if call_goal == 'appointment' and enable_scheduling:
    # Add tools ✅

# Lines 10916-10930, 10985-11015, 11017-11034: All paths
await client.send_event({
    "type": "conversation.item.create",
    "item": {"type": "function_call_output", ...}
})
await client.send_event({"type": "response.create"})  # ✅
```

---

### 6) Prompt Binding

**File:** `server/media_ws_ai.py:2367-2429, 3516-3554`

**What to verify:**
- ✅ Order is fixed: system → business prompt
- ✅ Prompt upgrade doesn't delete critical rules (tools, no-hallucination)
- ❌ NO "prompt-only" messages that block user input causing silence/loop

**Code audit:**
```python
# Lines 2367-2429: Initial prompt construction
system_prompt = "..." + business_context  # ✅ Order fixed

# Lines 3516-3554: Upgrade
# Check that full_prompt still contains tool rules ✅
```

---

### 7) Cleanup / Threads / WebSocket Close

**File:** `server/media_ws_ai.py:8131-8277`

**What to verify:**
- ✅ All threads join without "still running after timeout"
- ✅ WebSocket close doesn't throw unhandled "Unexpected ASGI message"
- ❌ NO cleanup happening while TX loop still running

**Code audit:**
```python
# Lines 8131-8149: Thread join with 5s timeout
for thread in self.background_threads:
    thread.join(timeout=5.0)
    if thread.is_alive():
        logger.warning("⚠️ [F2 VIOLATION] ...still running")  # ✅

# Lines 8254-8277: WebSocket close with guards
try:
    if not self._ws_closed and hasattr(self.ws, 'close'):
        self.ws.close()
except AttributeError as ae:
    # Handle "SyncWebSocketWrapper has no close" ✅
```

---

## 📋 RELEASE GATE - Required Logs from 3 Test Calls

### Call 1: Normal Conversation + Barge-in

**Required logs:**
```
✅ [CALL_METRICS] ... fps≈50, gaps<60, dropped=0, barge_in_events>0
✅ [TX_METRICS] fps=49.8, max_gap_ms=42.0 (at least 3 consecutive lines during AI speech)
✅ [BARGE-IN] 🔶 CANDIDATE ... ✅ CONFIRMED ... 🧹 FLUSH
✅ No [B3 VIOLATION] or [F2 VIOLATION] warnings
```

### Call 2: Appointment Flow (if enabled)

**Required logs:**
```
✅ [D1 TOOLS ENABLED] ... tools_count=2
✅ 📅 [CHECK_AVAIL] Request ... ✅ Found N available slots
✅ 📅 [BOOK_APPT] Request ... ✅ SUCCESS! ID=XXX
✅ [D4 TIMEZONE] ... Asia/Jerusalem: ...+02:00
```

**OR (if fallback triggered):**
```
✅ ❌ [BOOK_APPT] APPT_TOOL_FAILED
✅ [D5 FALLBACK_LEAD_CREATED] ... Lead saved
```

### Call 3: Fast Response + Loop Prevention

**Required logs:**
```
✅ [C1 STT_GUARD] Accepted (echo_window bypass: fast_response_150ms) text='בית שאן'
✅ [G ANTI-LOOP] Duplicate question detected (if triggered)
✅ [GOODBYE] User said goodbye ... will_hangup=True (or silence)
✅ No repeat questions after goodbye
```

---

## Definition of Done (Release Gate)

### Checklist

All test scenarios must pass:

- [ ] **A1**: fps≈50, gaps<60, dropped=0 in CALL_METRICS
- [ ] **A1+**: No mid-sentence silence, max_gap_ms stays <60ms during long speech
- [ ] **A2**: Local VAD computed before blocking
- [ ] **A3**: No double speaking after barge-in flush
- [ ] **B1**: barge_in_events>0 when interrupting, cancel only after CONFIRMED
- [ ] **B1+**: CANDIDATE appears even when interrupting at 0-200ms (early interrupt)
- [ ] **B2**: Noise doesn't trigger CONFIRMED (filler_only)
- [ ] **B3**: No turn_detected without confirmed barge-in
- [ ] **C1**: Fast responses like "בית שאן" not dropped by echo_window
- [ ] **C2**: Real Hebrew words not dropped as hallucinations
- [ ] **C3**: Noise gate active but doesn't block local VAD
- [ ] **D1**: Tools only when call_goal='appointment' AND scheduling=True
- [ ] **D2**: check_availability → book_appointment workflow enforced
- [ ] **D2+**: Tool failure doesn't cause AI to lie about booking
- [ ] **D3**: All handler paths have function_call_output + response.create
- [ ] **D4**: Timezone is Asia/Jerusalem with +02:00
- [ ] **D5**: Fallback works: APPT_TOOL_FAILED → FALLBACK_LEAD_CREATED
- [ ] **E1**: PROMPT UPGRADE logged with business_id and policy
- [ ] **E2**: System + business prompt order fixed
- [ ] **F1**: Full state reset at call end
- [ ] **F2**: No stuck threads (all complete within 5s)
- [ ] **F3**: No WebSocket close errors
- [ ] **G**: No duplicate question loops
- [ ] **End**: No looping/prompts after goodbye, clean hangup

### Test Call Requirements

**Minimum 3 test calls covering:**
1. **Successful flow with barge-in**: Normal conversation + user interrupts AI mid-sentence
2. **Appointment flow**: check_availability → book_appointment → success (OR fallback on failure)
3. **Edge cases**: Fast responses + goodbye/hangup

**For each call, attach:**
- 40-80 lines of logs around critical moments (barge-in, tool calls, goodbye)
- Full `CALL_METRICS` line
- At least 3 consecutive `[TX_METRICS]` lines during AI speech
- call_sid and stream_sid

### Failure Reporting

If any check fails, provide:
- 40-80 lines of log context around failure
- call_sid and stream_sid
- Exact timestamp of failure
- Specific requirement violated (e.g., "B3 VIOLATION", "D2+ FAIL")

---

## 🐛 DEBUGGING GUIDE - Common Failures

### "AI doesn't stop when I talk over her"

**Logs to send:**
```
# 40-80 lines around:
- When you started talking
- Any CANDIDATE / CONFIRMED messages (or lack thereof)
- HALF-DUPLEX Blocking messages
```

**Likely causes:**
1. No CANDIDATE appears → Local VAD not detecting / half-duplex blocking too early
2. CANDIDATE but no CONFIRMED → STT dropped by echo_window or filler filter
3. CONFIRMED but AI continues → Cancel/flush not working

**Audit checks:**
- Verify local VAD runs before any `continue` in half-duplex block
- Check if `echo_window` bypass conditions are too strict
- Ensure cancel + flush happen in CONFIRMED path

---

### "AI loops on same question"

**Logs to send:**
```
# 40-80 lines showing:
- AI asking question
- User answer (or lack thereof)
- AI asking same question again
- Any STT_FILTER drops
```

**Likely causes:**
1. User answer dropped by `echo_window` (too fast after AI)
2. User answer classified as `hallucination` or `filler_only`
3. Anti-loop guard not triggering

**Audit checks:**
- Check if `fast_response` bypass is working (C1)
- Verify STT validation isn't too strict (C2)
- Ensure loop detection similarity threshold is reasonable (G)

---

### "AI says mid-sentence, stops, then continues"

**Logs to send:**
```
# TX_METRICS around the gap
# Any response.audio.done or error messages
```

**Likely causes:**
1. TX underrun - frames not arriving fast enough
2. Scheduling jitter - sleep/timing issues
3. Race condition between threads

**Audit checks:**
- Verify `avg_fps` is close to 50 (not 6-20)
- Check for high `max_gap_ms` spikes
- Ensure no blocking operations in TX loop

---

## Implementation Summary

### Files Modified - Backend
- `server/media_ws_ai.py` - Main realtime audio handler (all requirements)

### Files Modified - Frontend (Timezone Fix)
- `client/src/shared/utils/format.ts` - Timezone-aware formatters
- 17 page files using date/time display

### Key Changes Made

1. **TX_METRICS (A1, A1+)**: Always log every second, track continuity
2. **turn_detected Detection (B3)**: B3 violation warning
3. **Early Interrupt (B1+)**: Local VAD before half-duplex blocking
4. **Echo Window Bypass (C1)**: Fast response bypass
5. **Anti-Loop Guard (G, End)**: Consecutive duplicate detection + goodbye sanity
6. **Tool Logging (D1, D2+)**: Explicit conditions, no-hallucination check
7. **Timezone Fix**: All UI times use Asia/Jerusalem

### Backward Compatibility
✅ All changes are additive or logging enhancements
✅ No breaking changes to existing functionality
✅ All existing flows continue to work

---

**Document Version:** 2.0  
**Date:** 2025-12-14  
**Updates:** Added 4 critical additions + Audit Walkthrough + Release Gate  
**Author:** Production Readiness Audit - Complete Edition

### A1. Audio Rate and Timing Verification ✅

**What to check in logs:**
- `[TX_METRICS]` appears **every second** during active call
- `fps` value should be ≈50 (acceptable range: 47-52)
- `max_gap_ms` should be <60ms
- At call end, check `[CALL_METRICS]` for `frames_dropped=0`

**✅ PASS Criteria:**
```
[TX_METRICS] fps=50.2, max_gap_ms=23.5, frames=50, q=0/500
...
[CALL_METRICS] ... frames_dropped=0
```

**❌ FAIL Patterns:**
```
[TX_METRICS] fps=8.3, max_gap_ms=850.2  # Low FPS, high gaps
[CALL_METRICS] ... frames_dropped=234   # Frames dropped
```

**Location in code:**
- `server/media_ws_ai.py:12262-12274` - TX_METRICS logging
- `server/media_ws_ai.py:12950-13006` - CALL_METRICS logging

---

### A2. Half-Duplex Voice Detection ✅

**What to verify in code:**
- Local VAD is computed **before** "Blocking audio to OpenAI" decision
- CANDIDATE barge-in can be detected while AI is speaking

**✅ PASS:**
```
[LOCAL_VAD] CANDIDATE barge-in detected: 12 voice_frames → enabling forward
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
```

**Location in code:**
- `server/media_ws_ai.py:2897-2941` - Local VAD computed first, then blocking decision

---

### A3. Double Speaking Prevention ✅

**Test scenario:** Interrupt AI mid-sentence, then stay silent

**✅ PASS:**
```
🧹 [BARGE-IN FLUSH] OpenAI queue: 45/50 frames | TX queue: 12/15 frames
# After flush, no more audio from old response_id
# active_response_id resets to None
```

**❌ FAIL:**
- Old AI response continues after barge-in flush
- Same response_id appears in audio.delta after cancellation

**Location in code:**
- `server/media_ws_ai.py:3176-3178` - Barge-in flush logging
- `server/media_ws_ai.py:3458-3464` - Cancelled response filtering

---

## B) Barge-In Two-Stage Verification

### B1. Real Interrupt ✅

**Test scenario:** Interrupt AI after 300-700ms of speaking

**✅ PASS logs:**
```
[LOCAL_VAD] 🔶 CANDIDATE: Possible user speech detected
[BARGE-IN] ✅ CONFIRMED: intent_aware_single_token text='כן'
[BARGE-IN] Cancelled AI response: resp_abc123...
🧹 [BARGE-IN FLUSH] ...
[CALL_METRICS] ... barge_in_events=3
```

**❌ FAIL:**
- `barge_in_events=0` despite interrupting
- AI continues speaking after CONFIRMED
- Cancel happens without CONFIRMED

**Location in code:**
- `server/media_ws_ai.py:2924-2931` - CANDIDATE detection
- `server/media_ws_ai.py:5093-5124` - CONFIRMED barge-in
- `server/media_ws_ai.py:12966` - barge_in_events metric

---

### B2. Noise Rejection ✅

**Test scenario:** Breathing/background noise while AI speaks

**✅ PASS:**
```
[LOCAL_VAD] CANDIDATE barge-in detected
[BARGE-IN] ❌ NOT CONFIRMED: filler_only text='אממ'
# AI continues speaking - no cancellation
```

**Location in code:**
- `server/media_ws_ai.py:5125-5127` - NOT CONFIRMED logging

---

### B3. No Spurious OpenAI turn_detected ✅

**What to check:**

**✅ PASS:**
```
[RESPONSE] Cancelled: reason=turn_detected
✅ [B3] turn_detected after confirmed barge-in (expected)
```

**❌ FAIL:**
```
⚠️ [B3 VIOLATION] OpenAI turn_detected cancellation WITHOUT confirmed barge-in!
```

This indicates audio is leaking to OpenAI during AI speech (half-duplex not working).

**Location in code:**
- `server/media_ws_ai.py:3477-3495` - turn_detected detection and logging

---

## C) STT Quality + Echo Window

### C1. Echo Window Bypass on Real Speech ✅

**Test scenario:** Answer "בית שאן" very quickly (0.1-0.3s) after AI asks "איזו עיר?"

**✅ PASS:**
```
[C1 STT_GUARD] Accepted (echo_window bypass: fast_response_150ms) text='בית שאן'
# AI proceeds with response, doesn't ask again
```

**❌ FAIL:**
```
[STT_FILTER] drop reason=echo_window ... text='בית שאן'
# AI asks "איזו עיר?" again → creates loop
```

**Location in code:**
- `server/media_ws_ai.py:1238-1289` - Enhanced echo window bypass with fast_response detection

---

### C2. Hallucinations Don't Drop Real Words ✅

**What to verify:**
- Real city names, numbers, yes/no answers are accepted even if short
- Intent-aware validation allows single-token meaningful responses

**✅ PASS:**
```
[STT_GUARD] Accepted short phrase: 'כן' (valid Hebrew phrase in whitelist)
[BARGE-IN] ✅ CONFIRMED: intent_aware_single_token text='כן'
```

**Location in code:**
- `server/media_ws_ai.py:1273-1293` - Minimum word count with valid short phrase whitelist
- `server/media_ws_ai.py:5047-5090` - Intent-aware single token barge-in

---

### C3. Noise Gate - Re-enabled Correctly ✅

**What to verify:**
- Noise gate is active when AI speaks (blocks noise from being sent to OpenAI)
- But does NOT choke local VAD or CANDIDATE detection

**✅ PASS:**
```
[HALF-DUPLEX] Blocking audio to OpenAI - AI speaking
[LOCAL_VAD] CANDIDATE barge-in detected: 10 voice_frames
# Both can happen - gate blocks but VAD still runs
```

**Location in code:**
- `server/media_ws_ai.py:2933-2941` - Half-duplex blocking
- `server/media_ws_ai.py:2897-2912` - Local VAD runs independently

---

## D) Appointment Scheduling End-to-End

### D1. Precise Activation Conditions ✅

**What to check in logs:**

**✅ PASS (tools enabled):**
```
[D1 TOOLS ENABLED] business_id=123, call_goal=appointment, enable_calendar_scheduling=True, tools_count=2
```

**✅ PASS (tools disabled):**
```
[D1 TOOLS DISABLED] business_id=123, call_goal=lead_only, enable_calendar_scheduling=False, tools_count=0
```

**Location in code:**
- `server/media_ws_ai.py:1878-2005` - Tool building with dual condition check
- `server/media_ws_ai.py:1912` - Explicit check: `call_goal == 'appointment' and enable_scheduling`

---

### D2. Two-Tool Workflow Enforced ✅

**What to verify:**
- AI always calls `check_availability` first
- Only after successful check → calls `book_appointment`

**✅ PASS:**
```
📅 [CHECK_AVAIL] Request from AI: {...}
✅ [CHECK_AVAIL] Found 3 available slot(s)
📅 [BOOK_APPT] Request from AI: {...}
✅ [BOOK_APPT] SUCCESS! ID=456
```

**❌ FAIL:**
- AI calls `book_appointment` without prior `check_availability`

**Tool definitions:**
- `server/media_ws_ai.py:1915-1949` - check_availability tool
- `server/media_ws_ai.py:1952-1990` - book_appointment tool (description requires checking first)

---

### D3. Handler Output Correctness ✅

**What to verify:**
- **Every path** (success, validation error, exception) returns:
  1. `function_call_output` with JSON
  2. `response.create` to continue conversation

**✅ PASS paths:**

**check_availability:**
- Success: Lines 10985-11015
- No slots: Lines 11002-11015
- Validation error: Lines 10916-10930
- Exception: Lines 11017-11034

**book_appointment:**
- Success: Lines 11163-11178
- Validation error: Lines 11064-11078
- Duplicate: Lines 11083-11096
- Creation failed: Lines 11186-11198
- Exception: Lines 11200-11231

All paths end with `await client.send_event({"type": "response.create"})`

---

### D4. Timezone + ISO Correctness ✅

**What to check in logs:**

**✅ PASS:**
```
[D4 TIMEZONE] Localized naive datetime to Asia/Jerusalem: 2025-12-15T14:00:00+02:00
📅 [BOOK_APPT] Creating: 2025-12-15T14:00:00+02:00 -> 2025-12-15T15:00:00+02:00
```

**Location in code:**
- `server/media_ws_ai.py:11110-11132` - Timezone normalization with logging

---

### D5. Real Fallback Path ✅

**Test scenario:** Force DB/Calendar failure (e.g., invalid business_id)

**✅ PASS:**
```
❌ [BOOK_APPT] APPT_TOOL_FAILED: ...
[D5 APPT_TOOL_FAILED] Exception in book_appointment
[D5 FALLBACK_LEAD_CREATED] Activating fallback flow
✅ [BOOK_APPT] Lead verified/created for follow-up
# AI response: "לקחתי את הפרטים ונציג יחזור אליך"
```

**Location in code:**
- `server/media_ws_ai.py:11200-11231` - Exception handler with fallback logging

---

## E) Prompt / Business Context Integrity

### E1. Prompt Upgrade & Binding ✅

**What to check:**

**✅ PASS:**
```
🔄 [PROMPT UPGRADE] Upgrading from COMPACT (800 chars) to FULL (3500 chars)
✅ [PROMPT UPGRADE] Successfully upgraded to FULL prompt in 45ms
[E1 PROMPT UPGRADE] business_id=123, upgrade_duration_ms=45, policy={'call_goal': 'appointment', ...}
```

**Location in code:**
- `server/media_ws_ai.py:3516-3554` - Prompt upgrade with enhanced logging

---

### E2. System + Business Prompt Order ✅

**What to verify:**
- Prompts are injected in fixed order: system → business
- No override after call starts that removes critical rules

**Location in code:**
- `server/media_ws_ai.py:2367-2429` - Prompt building with fixed order
- Business prompt is embedded within system instructions consistently

---

## F) Cleanup / Threads / Stability

### F1. Flags Reset ✅

**What to check at call end:**

**✅ PASS:**
```
🧹 [CLEANUP] Resetting all state flags...
✅ [CLEANUP] All state flags reset successfully
# All flags reset: _barge_pending, _barge_confirmed, _appointment_created_this_session, etc.
```

**Location in code:**
- `server/media_ws_ai.py:8159-8252` - Comprehensive state reset

---

### F2. No Background Threads Stuck ✅

**What to check:**

**✅ PASS:**
```
🧹 Waiting for 4 background threads...
✅ Background thread 0 completed
✅ Background thread 1 completed
✅ Background thread 2 completed
✅ Background thread 3 completed
✅ All background threads cleanup complete
```

**❌ FAIL:**
```
⚠️ [F2 VIOLATION] Background thread 2 (RealtimeThread) still running after 5s timeout
⚠️ [F2 VIOLATION] 2/4 threads still alive after cleanup
```

**Location in code:**
- `server/media_ws_ai.py:8131-8149` - Enhanced thread cleanup with better logging

---

### F3. WebSocket Close Errors ✅

**What to verify:**

**✅ PASS:**
```
✅ [F3] WebSocket closed successfully
```

**Also acceptable (graceful handling):**
```
[F3] WebSocket wrapper doesn't support close() - connection already terminated
[F3] Websocket already closed (expected): ...
```

**❌ FAIL (red alert errors):**
```
Unexpected ASGI message 'websocket.close'...
SyncWebSocketWrapper has no close
# Without [F3] prefix or proper handling
```

**Location in code:**
- `server/media_ws_ai.py:8254-8277` - Enhanced WebSocket close with AttributeError handling

---

## G) Anti-Loop Guard

### G1. Duplicate Question Detection ✅

**Test scenario:** Let AI ask "איזו עיר?" twice without user speaking

**✅ PASS:**
```
⚠️ [G ANTI-LOOP] Duplicate question detected! Similarity=92% | Current: 'איזו עיר אתה נמצא?' | Previous: 'איזו עיר?'
[SYSTEM] Message sent: אתה שואל את אותה שאלה שוב. המתן לתשובת הלקוח...
# AI pauses and waits for user
```

**❌ FAIL:**
- Same question appears 3+ times in a row
- No loop detection warning
- AI doesn't pause after duplicate

**Location in code:**
- `server/media_ws_ai.py:4512-4563` - Enhanced loop detection with consecutive duplicate check

---

## Definition of Done (Release Gate)

### Checklist

All test scenarios must pass:

- [ ] **A1**: fps≈50, gaps<60, dropped=0 in CALL_METRICS
- [ ] **A2**: Local VAD computed before blocking
- [ ] **A3**: No double speaking after barge-in flush
- [ ] **B1**: barge_in_events>0 when interrupting, cancel only after CONFIRMED
- [ ] **B2**: Noise doesn't trigger CONFIRMED (filler_only)
- [ ] **B3**: No turn_detected without confirmed barge-in
- [ ] **C1**: Fast responses like "בית שאן" not dropped by echo_window
- [ ] **C2**: Real Hebrew words not dropped as hallucinations
- [ ] **C3**: Noise gate active but doesn't block local VAD
- [ ] **D1**: Tools only when call_goal='appointment' AND scheduling=True
- [ ] **D2**: check_availability → book_appointment workflow enforced
- [ ] **D3**: All handler paths have function_call_output + response.create
- [ ] **D4**: Timezone is Asia/Jerusalem with +02:00
- [ ] **D5**: Fallback works: APPT_TOOL_FAILED → FALLBACK_LEAD_CREATED
- [ ] **E1**: PROMPT UPGRADE logged with business_id and policy
- [ ] **E2**: System + business prompt order fixed
- [ ] **F1**: Full state reset at call end
- [ ] **F2**: No stuck threads (all complete within 5s)
- [ ] **F3**: No WebSocket close errors
- [ ] **G**: No duplicate question loops

### Test Call Requirements

Minimum 3 test calls covering:
1. **Successful appointment flow**: check_availability → book_appointment → success
2. **Barge-in scenario**: User interrupts AI mid-sentence
3. **Fallback scenario**: Appointment tool fails → lead created

For each call, verify:
- Log files contain all required markers ([TX_METRICS], [CALL_METRICS], etc.)
- No violations or failures
- Call completes cleanly with proper cleanup

### Failure Reporting

If any check fails, provide:
- 40-80 lines of log context around failure
- call_sid and stream_sid
- Exact timestamp of failure
- Specific requirement violated (e.g., "B3 VIOLATION")

---

## Implementation Summary

### Files Modified
- `server/media_ws_ai.py` - Main realtime audio handler

### Key Changes Made

1. **TX_METRICS (A1)**: Always log every second (removed conditional logging)
2. **turn_detected Detection (B3)**: Added B3 violation warning when cancelled without confirmed barge-in
3. **Echo Window Bypass (C1)**: Added fast_response bypass (100ms+ with Hebrew content)
4. **Anti-Loop Guard (G)**: Enhanced with consecutive duplicate detection (>85% similarity) and force pause
5. **Tool Activation Logging (D1)**: Enhanced with explicit conditions and counts
6. **Timezone Verification (D4)**: Added timezone logging for normalization
7. **Fallback Logging (D5)**: Enhanced with D5 markers for APPT_TOOL_FAILED flow
8. **Prompt Upgrade (E1)**: Added business_id and policy logging
9. **Thread Cleanup (F2)**: Increased timeout to 5s, better logging with thread names
10. **WebSocket Close (F3)**: Added AttributeError handling for SyncWebSocketWrapper

### Backward Compatibility
✅ All changes are additive (logging enhancements and guard improvements)
✅ No breaking changes to existing functionality
✅ All existing flows continue to work

---

## Next Steps

1. Deploy to staging environment
2. Run comprehensive test suite covering all scenarios
3. Review logs for all required markers
4. Fix any violations found
5. Repeat until all checks pass
6. Deploy to production with monitoring

---

**Document Version:** 1.0  
**Date:** 2025-12-14  
**Author:** Production Readiness Audit Implementation
