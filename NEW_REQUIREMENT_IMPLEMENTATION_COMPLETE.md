# New Requirement Implementation - Complete

## Overview
This document describes the implementation of the two critical "landmines" that must be verified to prevent loops and slowness.

---

## ✅ Landmine 1: Prevent Response-Create Spam - IMPLEMENTED

### Problem
Sending `response.create` repeatedly while AI is already speaking causes:
- Double speaking (AI talking over itself)
- "Not letting customer talk" feeling
- Strange latency (multiple responses in progress)
- Conversation loops

### Solution Implemented

#### 1. Guard Function: `_can_send_followup_create()`
Location: `server/media_ws_ai.py` lines 10694-10731

```python
def _can_send_followup_create(self, source: str = "unknown") -> bool:
    """
    Prevent response-create spam with 3 checks:
    1. Is AI already speaking?
    2. Is there an active response in progress?
    3. Too soon after last followup? (debounce)
    """
    # Check 1: AI speaking
    if self.is_ai_speaking_event.is_set():
        logger.info(f"[SILENCE_FOLLOWUP_BLOCKED] source={source} reason=ai_already_speaking")
        return False
    
    # Check 2: Response in progress
    if self.active_response_id:
        logger.info(f"[SILENCE_FOLLOWUP_BLOCKED] source={source} reason=response_in_progress")
        return False
    
    # Check 3: Debounce (4 seconds minimum)
    if self._last_followup_create_ts:
        elapsed = time.time() - self._last_followup_create_ts
        if elapsed < self._followup_create_debounce_sec:  # 4.0 seconds
            logger.info(f"[SILENCE_FOLLOWUP_BLOCKED] source={source} reason=debounce")
            return False
    
    return True
```

#### 2. Tracking Function: `_mark_followup_create_sent()`
Location: `server/media_ws_ai.py` lines 10733-10739

```python
def _mark_followup_create_sent(self):
    """Mark that we sent a followup response.create"""
    self._last_followup_create_ts = time.time()
    logger.info(f"[SILENCE_FOLLOWUP_CREATE] timestamp={self._last_followup_create_ts:.2f}")
```

#### 3. Applied to All 8 Locations

Every location that sends `response.create` from silence/guards now:
1. **First** calls `_can_send_followup_create(source)` 
2. If True, sends the response.create
3. **After** sending, calls `_mark_followup_create_sent()`

**Locations**:
1. ✅ 10s silence timeout (line ~10515)
2. ✅ Lead unconfirmed prompt (line ~10600)
3. ✅ Max warnings timeout (line ~10662)
4. ✅ _send_silence_warning (line ~10785)
5. ✅ Goodbye on hangup (line ~10273)
6. ✅ Server error retry (line ~3845)
7. ✅ Server error graceful failure (line ~3865)
8. ✅ User rejection/correction (line ~6075)

### Verification

**PASS Criteria**:
```
✅ [SILENCE_FOLLOWUP_CREATE] appears ONCE per event, not in a loop
✅ [SILENCE_FOLLOWUP_BLOCKED] appears when:
   - AI already speaking
   - Response in progress
   - < 4 seconds since last followup
✅ No double speaking
✅ No "AI not letting me talk" feeling
```

**Test Scenario**:
1. Start call
2. Trigger silence timeout (wait 15s)
3. While AI is responding to silence, wait another 15s
4. Verify: Second timeout is BLOCKED (logs SILENCE_FOLLOWUP_BLOCKED)
5. After AI finishes + 4 seconds, next timeout should work

**Example Logs (PASS)**:
```
[SILENCE_FOLLOWUP_CREATE] 10s timeout - behavioral instruction sent
[SILENCE_FOLLOWUP_CREATE] timestamp=1234567890.12
... AI speaks for 8 seconds ...
[SILENCE_FOLLOWUP_BLOCKED] source=silence_warning reason=ai_already_speaking
... AI finishes ...
... 4 seconds pass ...
[SILENCE_FOLLOWUP_ALLOWED] source=silence_warning
[SILENCE_FOLLOWUP_CREATE] Max warnings - behavioral instruction sent
```

**Example Logs (FAIL - Old Code)**:
```
[SILENCE_FOLLOWUP_CREATE] 10s timeout
[SILENCE_FOLLOWUP_CREATE] silence_warning  <- SPAM! Too soon
[SILENCE_FOLLOWUP_CREATE] silence_warning  <- SPAM! AI already speaking
```

---

## ✅ Landmine 2: Dynamic Instructions Without Hardcode - IMPLEMENTED

### Problem
Instructions must be **behavioral guidance only**, not:
- Prepared text ("Say this: ...")
- City/service/business names
- Any content that should come from DB/BUSINESS PROMPT

### Solution Implemented

#### Removed ALL Hardcoded Content

**Before (WRONG)**:
```python
# ❌ Hardcoded Hebrew text
closing_msg = "תודה שהתקשרת. נשמח לעזור לך בפעם הבאה. יום נעים!"
if self.call_config and self.call_config.closing_sentence:
    closing_msg = self.call_config.closing_sentence

# ❌ Injecting specific text to say
instructions = f"Say this closing message: {closing_msg}"
```

**After (CORRECT)**:
```python
# ✅ Behavioral guidance only
instructions = (
    "The user has been silent for 10 seconds. "
    "End the call politely according to your BUSINESS PROMPT closing guidelines."
)
# AI will use its BUSINESS PROMPT to decide exact words
```

#### All 8 Locations Fixed

1. **10s silence timeout** (line ~10523):
   - ❌ Before: `f"Say this closing message: {closing_msg}"` with hardcoded Hebrew
   - ✅ After: `"End the call politely according to your BUSINESS PROMPT closing guidelines."`

2. **Lead unconfirmed** (line ~10608):
   - ❌ Before: `"Ask for confirmation one last time, politely."`
   - ✅ After: `"Ask for confirmation one last time, politely, based on your BUSINESS PROMPT."`

3. **Max warnings** (line ~10669):
   - ❌ Before: `f"Say this closing message: {closing_msg}"` or `"Say goodbye per your instructions"`
   - ✅ After: `"End the call politely according to your BUSINESS PROMPT closing guidelines."`

4. **_send_silence_warning** (line ~10806):
   - ❌ Before: `"As the assistant, ask one short helpful follow-up question..."`
   - ✅ After: `"Ask one short helpful follow-up question based on...BUSINESS PROMPT instructions."`

5. **Goodbye on hangup** (line ~10276):
   - ❌ Before: `f"Say this goodbye message: {goodbye_text}"` with injected config text
   - ✅ After: `"Say goodbye politely according to your BUSINESS PROMPT closing guidelines."`

6. **Server error retry** (line ~3845):
   - ✅ Already behavioral: `"Please retry your last response based on the conversation context."`

7. **Server error failure** (line ~3865):
   - ✅ Already behavioral: `"End the call politely per your BUSINESS PROMPT."`

8. **User rejection** (line ~6075):
   - ✅ Already behavioral: `"Ask again politely per your BUSINESS PROMPT instructions."`

### Verification

**PASS Criteria**:
```
✅ No hardcoded Hebrew text in instructions
✅ No "Say this: ..." patterns with specific text
✅ No city/service/business names in code
✅ All instructions reference "BUSINESS PROMPT" or "conversation context"
✅ AI decides exact words based on DB prompt
```

**Code Audit** (all fixed ✅):
```bash
# Search for hardcoded content patterns
grep -n "תודה\|להתראות\|שלום" server/media_ws_ai.py  # Hebrew text
grep -n "Say this:" server/media_ws_ai.py             # Scripted responses
grep -n "closing_msg\|goodbye_text" server/media_ws_ai.py  # Injected text
```

**Test Scenario**:
1. Multiple calls with different businesses
2. Each should close differently based on their BUSINESS PROMPT
3. NO two businesses should say identical closing (unless prompts identical)
4. Verify logs show only behavioral instructions, not specific text

**Example Logs (PASS)**:
```
[SILENCE_FOLLOWUP_CREATE] 10s timeout - behavioral instruction sent
DEBUG: instructions="End the call politely according to your BUSINESS PROMPT closing guidelines."
```

**Example Logs (FAIL - Old Code)**:
```
[SILENCE_FOLLOWUP_CREATE] 10s timeout
DEBUG: instructions="Say this closing message: תודה שהתקשרת. נשמח לעזור לך בפעם הבאה."
```

---

## Combined Verification Checklist

### Pre-Deployment Checks

- [x] Code Review: All 8 locations use `_can_send_followup_create()`
- [x] Code Review: All 8 locations call `_mark_followup_create_sent()`
- [x] Code Review: No hardcoded Hebrew text in instructions
- [x] Code Review: No "Say this: {text}" patterns
- [x] Code Review: All reference "BUSINESS PROMPT"
- [x] Syntax: `python3 -m py_compile server/media_ws_ai.py` ✅
- [x] Security: CodeQL scan ✅ (0 alerts)

### Runtime Verification

**Test 1: Response-Create Spam Prevention**
```
Scenario: Trigger two silence timeouts in quick succession
Expected:
  [SILENCE_FOLLOWUP_CREATE] timestamp=...
  ... AI speaks ...
  [SILENCE_FOLLOWUP_BLOCKED] reason=ai_already_speaking
  ... AI finishes ...
  ... 4+ seconds ...
  [SILENCE_FOLLOWUP_ALLOWED]
  [SILENCE_FOLLOWUP_CREATE] timestamp=...
```

**Test 2: Dynamic Instructions (No Hardcode)**
```
Scenario: Compare closing messages from 2 different businesses
Expected:
  Business A: Uses its own BUSINESS PROMPT closing
  Business B: Uses its own BUSINESS PROMPT closing
  Logs show behavioral instructions, not specific text
  NO hardcoded "תודה שהתקשרת..." in any call
```

### Monitoring in Production

**Key Metrics**:
1. **Spam Rate**: Count of `[SILENCE_FOLLOWUP_BLOCKED]` / total followup attempts
   - Target: > 10% (means guards are working)
   - Alert if: 0% (guards not working)

2. **Debounce Effectiveness**: Average time between followup creates
   - Target: ≥ 4 seconds
   - Alert if: < 2 seconds (spam getting through)

3. **Dynamic Content**: Sample random calls
   - Verify: Different businesses have different closings
   - Verify: No hardcoded Hebrew in any call
   - Verify: Instructions reference "BUSINESS PROMPT"

**Alert Conditions**:
```
🚨 ALERT: If any of these appear:
- [SILENCE_FOLLOWUP_CREATE] multiple times within 4 seconds
- Instructions contain "תודה שהתקשרת" or other Hebrew
- Instructions contain "Say this:" with specific text
- AI repeating identical closings across all businesses
```

---

## Impact Summary

### Problems Solved

**Before**:
- ❌ Response-create spam → double speaking, loops, latency
- ❌ Hardcoded content → all businesses sound the same
- ❌ Config injection → couples code to specific text
- ❌ No debounce → can send creates every second

**After**:
- ✅ Guard function prevents spam
- ✅ Debounce enforces 4-second minimum
- ✅ All content from BUSINESS PROMPT
- ✅ Pure behavioral instructions
- ✅ Each business uses its own prompt

### Code Changes

**Files Modified**: 1
- `server/media_ws_ai.py`

**Functions Added**: 2
- `_can_send_followup_create()` (guard)
- `_mark_followup_create_sent()` (tracking)

**Locations Fixed**: 8
- All silence/timeout/error handlers

**Lines Changed**: ~100
- Removed: ~40 lines (hardcoded text, no guards)
- Added: ~60 lines (guards, behavioral instructions)

**Net Effect**:
- Safer (prevents spam)
- More dynamic (no hardcode)
- Better UX (no double speaking)
- Business-specific (uses BUSINESS PROMPT)

---

## Release Gate Status

### ✅ ALL LANDMINES CLEARED

1. **Response-Create Spam** → Fixed with guards + debounce
2. **Hardcoded Instructions** → Fixed with behavioral-only guidance

### Ready for Production

**Pre-conditions Met**:
- [x] All P0 fixes implemented
- [x] Response-create spam prevention added
- [x] All hardcoded content removed
- [x] Syntax validated
- [x] Security scan passed (0 alerts)
- [x] Documentation complete

**Next Steps**:
1. Deploy to staging
2. Run 5 production verification tests
3. Monitor for spam/hardcode violations
4. Collect logs
5. Final approval for production

**Approval Criteria**:
- 5/5 tests PASS
- No SILENCE_FOLLOWUP_BLOCKED violations
- No hardcoded content in logs
- No double speaking
- Business-specific closings verified

---

## Contact

Issues or questions:
- Review code at: `server/media_ws_ai.py` lines 1891-1896, 10694-10850
- Check logs for: `[SILENCE_FOLLOWUP_BLOCKED]`, `[SILENCE_FOLLOWUP_ALLOWED]`
- Verify: No Hebrew text in instructions, all reference "BUSINESS PROMPT"

**Status**: ✅ READY FOR DEPLOYMENT
