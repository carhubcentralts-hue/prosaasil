# Master Instruction Implementation - Detailed Analysis

## Current State Assessment (Based on Code Review)

### ✅ ALREADY WORKING (Do NOT touch unless broken):

1. **Audio TX Loop** (lines 12269-12407):
   - Already has clocked 50fps sender
   - Already logs TX_METRICS (fps, max_gap_ms)
   - Already uses 20ms frame pacing
   - Already has queue management

2. **STT Filtering** (lines 5000-5500):
   - Already has hallucination detection
   - Already has filler detection
   - Already has echo window
   - Already has gibberish detection

3. **Barge-In** (lines 5104-5220):
   - Already has two-stage detection (CANDIDATE + CONFIRMED)
   - Already cancels AI response
   - Already flushes TX queue
   - Already has word_count confirmation

4. **Prompt Building** (realtime_prompt_builder.py):
   - Already separates inbound/outbound
   - Already loads from DB (no hardcode)
   - Already has business_id binding

5. **Call Direction** (multiple locations):
   - Already tracks call_direction ('inbound' / 'outbound')
   - Already uses in prompt building
   - Already disables loop guard for outbound

---

## 🔥 REQUIRED CHANGES (Per Master Instruction)

### PHASE 0: Enhanced Logging (HIGHEST PRIORITY)
**Goal**: Add comprehensive metrics to verify system is working

#### 0.1 - Add Missing Logs:
- [ ] [DIRECTION] at call start (log call_sid + direction)
- [ ] [PROMPT_BIND] at session config (business_id + prompt_hash + direction)
- [ ] [BARGE-IN] CANDIDATE stage log (when VAD detects voice during AI)
- [ ] [BARGE-IN] CONFIRMED stage log (when STT confirms)
- [ ] [VAD_VIOLATION] when rms > threshold but voice_frames stays 0
- [ ] [STT_DROP] reason for EVERY dropped utterance

#### 0.2 - Fix Existing Logs:
- [ ] TX_METRICS already exists - verify it logs correctly
- [ ] CALL_METRICS already exists (_log_call_metrics) - verify it includes direction
- [ ] STT_FILTER logs - ensure ALL paths log drop reason

---

### PHASE 1: Echo Window Fix (C1 REQUIREMENT)
**Problem**: Fast answers (0.1-0.3s) after AI question are being dropped
**Solution**: Already partially implemented (lines 5240-5294), needs enhancement

Current bypass conditions (line 5268):
- candidate_user_speaking OR
- local_vad_voice_frames >= 8 OR
- is_new_content OR
- is_fast_but_real_response

✅ This is CORRECT - just needs verification via logging

---

### PHASE 2: Half-Duplex with Preroll
**Current State**: Code mentions half-duplex (line 5218) but implementation unclear
**Need**: Verify local VAD runs BEFORE half-duplex gate

Lines to check:
- Audio sender task (where Twilio → OpenAI forwarding happens)
- Preroll buffer implementation
- Half-duplex gating logic

---

### PHASE 3: Conversation Pacing
**Problem**: AI talks again too quickly (3s instead of 8-12s)
**Need**: Add silence windows

Current silence handling:
- Line 3407-3408: Loop guard for inbound calls
- Line 4024: Loop guard engagement
- Line 4660: Loop guard disabled for outbound

**Required**:
- MIN_LISTEN_AFTER_AI_MS = 1500-2500ms
- SILENCE_FOLLOWUP_1 = 8000-12000ms (not 3000ms)
- SILENCE_FOLLOWUP_2 = 15000-20000ms

---

### PHASE 4: Barge-In State Reset
**Problem**: Barge-in can get stuck
**Solution**: Add forced reset when ai_speaking=False AND active_response_id=None

Location: After line 5228 (end of barge-in confirmation)

---

### PHASE 5: Prompt Binding Verification
**Goal**: Ensure NO hardcoded content in prompts

Files to verify:
- realtime_prompt_builder.py (lines 561-856)
- media_ws_ai.py (where prompts are loaded)

Check for:
- ❌ Hardcoded city names
- ❌ Hardcoded service names  
- ❌ Hardcoded business names
- ❌ Hardcoded scripts
- ✅ All content from DB

---

### PHASE 6: Direction Detection Enhancement
**Current**: call_direction set from registry (line 2402)
**Need**: Ensure it comes from Twilio params

Check routes_twilio.py:
- How is direction determined?
- Is it logged at call start?

---

## Implementation Priority

### IMMEDIATE (Can implement now):
1. Add [DIRECTION] log at call start
2. Add [PROMPT_BIND] log at session config
3. Add [BARGE-IN] CANDIDATE/CONFIRMED logs
4. Add [VAD_VIOLATION] log
5. Verify [STT_DROP] logs all paths

### NEXT (Requires testing):
1. Verify echo window bypass works for fast answers
2. Add conversation pacing windows
3. Add barge-in state reset
4. Verify half-duplex + preroll

### VERIFICATION (After logging):
1. Run test calls with new logs
2. Verify TX_METRICS shows fps 47-52
3. Verify barge-in shows CANDIDATE → CONFIRMED
4. Verify fast answers not dropped
5. Verify silence pacing is 8-12s, not 3s

---

## Files to Modify

1. **media_ws_ai.py** (main changes):
   - Add missing logs
   - Add conversation pacing
   - Add state reset
   - Verify half-duplex

2. **realtime_prompt_builder.py** (verification only):
   - Check for hardcoded content
   - Add prompt_hash logging

3. **routes_twilio.py** (if needed):
   - Verify direction detection
   - Add direction logging

---

## Testing Checklist (Per Master Instruction)

After implementation, run these 4 tests:

### Test 1: Barge-In
- Interrupt AI at 300-700ms into speech
- ✅ PASS: See [BARGE-IN] CANDIDATE → CONFIRMED → cancel+flush
- ✅ PASS: AI stops immediately
- ❌ FAIL: AI continues or stutters

### Test 2: Fast Answer
- AI asks "איזו עיר?"
- Answer within 0.2s
- ✅ PASS: Answer accepted, no repeat loop
- ❌ FAIL: Answer dropped, AI repeats question

### Test 3: Silence Pacing  
- AI speaks, user stays silent
- ✅ PASS: AI waits 8-12s before follow-up
- ❌ FAIL: AI speaks again after 3s

### Test 4: Audio Stability
- Check logs during call
- ✅ PASS: TX_METRICS shows fps 47-52, max_gap <60ms, frames_dropped=0
- ❌ FAIL: fps < 45 or max_gap > 80ms or frames_dropped > 0

---

## Rollout Strategy

1. **Week 1**: Add all logging (no behavior changes)
2. **Week 2**: Run test calls, collect logs
3. **Week 3**: Fix only what logs show is broken
4. **Week 4**: Final verification + production deploy

**Golden Rule**: If tests pass with current code + new logs, DON'T change behavior!

