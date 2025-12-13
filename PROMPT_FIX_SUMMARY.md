# Prompt Confusion Fix Summary

## Problem Statement (Hebrew)
אם עדיין יש "היא עונה לא קשור / מחרטטת" — זה כמעט תמיד בגלל אחד מאלה:
1. prompt mismatch (inbound/outbound מתחלפים, או cache key לא כולל direction+mode)
2. transcript repair שעושה "מה מדם → מה המצב" בטעות ואז המודל עונה בהתאם
3. המודל מקבל SYSTEM/assistant text שלא אמור להישלח (למשל "are you still there" נשלח כמו user)

Translation: If there are still issues with "she answers irrelevantly / rambling" - it's almost always because of one of these:
1. prompt mismatch (inbound/outbound swapping, or cache key doesn't include direction+mode)
2. transcript repair that does "מה מדם → מה המצב" incorrectly and then the model responds accordingly
3. The model receives SYSTEM/assistant text that shouldn't be sent (e.g., "are you still there" sent as user)

## Issues Identified & Fixed

### Issue #3: SYSTEM/SERVER Messages Sent as User Input ✅ FIXED

**Problem:** The code was sending messages like `[SYSTEM] Technical error occurred` and `[SERVER] הלקוח אמר שלום!` using `conversation.item.create` with `role="user"`. This violated the "transcription is truth" principle - the AI thought the **customer** was saying these things!

**Root Cause:**
- `_send_text_to_ai()` in media_ws_ai.py (line ~9726)
- `_send_server_event_to_ai()` in media_ws_ai.py (line ~5506)

Both functions sent messages with `role="user"`, making the AI believe synthetic system messages were actual customer speech.

**Fix:**
- Disabled both functions by adding early returns that block `[SYSTEM]` and `[SERVER]` prefixed messages
- Added logging to track blocked messages
- Preserved backward compatibility for non-system messages (with warning)

**Impact:**
- AI will no longer receive confusing synthetic messages
- AI responses will be based ONLY on actual customer speech transcripts
- Eliminates cases where AI responds to things the customer never said

**Files Modified:**
- `server/media_ws_ai.py`: Lines ~5506-5560 and ~9726-9755

---

### Issue #2: Transcript Repair Too Aggressive ✅ FIXED

**Problem:** The `semantic_repair()` function was changing valid Hebrew words incorrectly, such as "מה מדם" → "מה המצב" when the customer actually said "מה מדם" and meant something else.

**Root Cause:**
- `semantic_repair()` in `server/services/dynamic_stt_service.py` (line ~460)
- Was trying to repair even when there was no business vocabulary to guide it
- Had vague instructions to the LLM ("תקן לביטוי הסביר ביותר")
- No validation of repair quality (length changes, etc.)

**Fix:**
1. **Skip repair if no vocabulary:** If business has no defined vocabulary, don't attempt semantic repair (too risky)
2. **More conservative prompt:** Changed LLM instructions to only fix if "100% certain" ("תקן רק אם אתה 100% בטוח")
3. **Validation checks:** 
   - Skip if only whitespace/punctuation changed
   - Skip if length changed by >50% (suspicious)
   - Skip if no real content change detected
4. **Better logging:** Log when repairs are skipped and why

**Impact:**
- Fewer incorrect repairs that change customer's actual words
- Only repairs obvious transcription errors with high confidence
- Preserves customer intent more accurately

**Files Modified:**
- `server/services/dynamic_stt_service.py`: Lines ~460-570

---

### Issue #1: Prompt Cache Direction Mismatch ✅ VERIFIED (Already Working)

**Problem Claimed:** Cache key doesn't include direction+mode, causing inbound/outbound prompt mixing.

**Investigation Results:** 
The cache implementation was actually **already correct**:

1. **Cache key includes direction:**
   - `prompt_cache.py` line 47: `f"{business_id}:{direction}"`
   - Example: "123:inbound" vs "123:outbound"

2. **Separate inbound/outbound prompt builders:**
   - `build_inbound_system_prompt()` - includes call control settings
   - `build_outbound_system_prompt()` - pure prompt mode
   - Router correctly calls the right builder based on `call_direction`

3. **Separate webhook prebuild functions:**
   - `/webhook/incoming_call` → `_prebuild_prompts_async()` → builds inbound prompts
   - `/webhook/outbound_call` → `_prebuild_prompts_async_outbound()` → builds outbound prompts

4. **Direction passed correctly everywhere:**
   - `build_realtime_system_prompt(business_id, call_direction=call_direction)`
   - `build_compact_greeting_prompt(business_id, call_direction=call_direction)`
   - `cache.get(business_id, direction=call_direction)`
   - `cache.set(business_id, ..., direction=call_direction)`

**Enhancement Made:**
Added extensive logging to verify direction handling:
- Log when building INBOUND vs OUTBOUND prompts
- Log cache hits/misses with direction
- Verify final prompt contains correct "CALL TYPE: INBOUND/OUTBOUND" marker

**Files Modified:**
- `server/services/realtime_prompt_builder.py`: Added logging at lines ~387-390, ~688-689, ~797-798
- `server/media_ws_ai.py`: Added direction logging at line ~2270

---

## Testing Recommendations

### 1. Test SYSTEM Message Blocking
**Test:** Make an inbound call and trigger silence timeout
**Expected:** AI should NOT receive messages like "[SYSTEM] User silent too long"
**Verify:** Check logs for "🛡️ [PROMPT_FIX] BLOCKED synthetic message"

### 2. Test Semantic Repair Conservation
**Test:** Say unusual Hebrew phrases that are valid but might look garbled
**Expected:** Transcript should preserve original words unless clearly wrong
**Verify:** Check logs for "[STT_REPAIRED] SKIPPED" vs actual repairs

### 3. Test Inbound/Outbound Separation
**Test:** Make both inbound and outbound calls to the same business
**Expected:** 
- Inbound: Should mention appointment scheduling
- Outbound: Should follow outbound script
**Verify:** Check logs for "CALL TYPE: INBOUND" vs "CALL TYPE: OUTBOUND"

### 4. Test Prompt Cache
**Test:** Make multiple calls to same business
**Expected:** First call builds prompt, subsequent calls use cache
**Verify:** Check logs for "✅ [PROMPT CACHE HIT]" with correct direction

---

## Summary

The three issues have been addressed:

1. ✅ **SYSTEM Messages**: Blocked from being sent as user input
2. ✅ **Transcript Repair**: Made more conservative with validation
3. ✅ **Prompt Cache**: Verified already working correctly, added logging

All fixes maintain the "transcription is truth" principle and ensure the AI only responds to actual customer speech, not synthetic system messages.

## Expected Outcome

After these fixes:
- AI should stay on topic and respond to what customer **actually said**
- Fewer cases of AI "rambling" or responding to non-existent questions
- Better preservation of customer's actual words
- Clear separation between inbound and outbound call handling
