# NAME_ANCHOR System - Complete Implementation Summary

## ✅ Problem Fixed

Customer names were not being used throughout conversation because:
1. Name usage policy was not detected from business prompt
2. Name context disappeared after PROMPT_UPGRADE
3. Wrong phrase "ליצור קרבה" triggered name usage (it's NOT a name instruction!)
4. No persistent tracking of name across session

## 🎯 Solution: NAME_ANCHOR System

A permanent system message that:
- Detects if business prompt requests name usage (use_name_policy)
- Injects customer name + usage policy as conversation context
- Persists through PROMPT_UPGRADE by re-injection
- Uses EXPLICIT instructions when enabled

## ✅ Three Critical Checks Verified

### 1. Correct Operation Order ✅

```
1. System prompt (rules)              → Line ~3045
2. NAME_POLICY calculated             → Line 3100-3113
3. NAME_ANCHOR injected (system msg)  → Line 3126-3160
4. Greeting triggered                 → Line 3211
```

**Verified**: NAME_ANCHOR injected BEFORE greeting, so AI has name context from first response.

### 2. Short & Deterministic ANCHOR ✅

**Format when enabled:**
```
[CRM Context]
Customer name: דוד כהן
Name usage policy: ENABLED - Business prompt requests using this name.
ACTION REQUIRED: Use 'דוד כהן' naturally throughout the conversation.
```

**Format when disabled:**
```
[CRM Context]
Customer name: שרה לוי
Name usage policy: DISABLED - Do not use this name in conversation.
```

**Format when no name:**
```
[CRM Context]
Customer name: NOT AVAILABLE
Name usage policy: REQUESTED BUT UNAVAILABLE - Continue without name.
```

**Rules:**
- ✅ Short and clear (no duplicate instructions from system prompt)
- ✅ No "unknown" placeholders (validated before injection)
- ✅ EXPLICIT "ACTION REQUIRED" when name should be used

### 3. Real ensure() After PROMPT_UPGRADE ✅

**Implementation:**
```python
async def _ensure_name_anchor_present(self, client):
    # Check if name/policy changed
    needs_update = (current_name != stored_name) or (current_policy != stored_policy)
    
    if needs_update:
        # Re-inject NAME_ANCHOR
        await client.send_event(...)
        logger.info("[NAME_ANCHOR] re-injected enabled=... name=... item_id=...")
    else:
        # No change needed
        logger.info("[NAME_ANCHOR] ensured ok (no change)")
```

**Called after PROMPT_UPGRADE:** Line 4347

## 📋 Name Policy Detection

### EXPLICIT Patterns That Trigger Name Usage:

**Hebrew:**
- `השתמש בשם` - "use name"
- `תשתמש בשם` - "you will use name"
- `פנה בשמו` - "address by his name"
- `תפנה בשם` - "you will address by name"
- `קרא לו בשם` - "call him by name"

**English:**
- `use name` / `use the customer's name`
- `use their name`
- `address by name` / `address them by name`
- `call by name` / `call them by name`

**CRITICAL FIX:** Removed `ליצור קרבה` (create closeness) - NOT a name instruction!

### Patterns That Do NOT Trigger:
- `ליצור קרבה` - create closeness (general, not name-specific)
- General mentions of "שם" without action verbs
- Business name references

## 🔍 Verification - Expected Logs

### Call Start with Name:
```
[PROMPT_SEPARATION] global_system_prompt=injected
[NAME_POLICY] use_name_policy=True reason=תשתמש בשם
[NAME_ANCHOR] injected enabled=True name="דוד כהן" item_id=item_ABqYZ...
[GREETING_LOCK] activated
```

### After PROMPT_UPGRADE:
```
[PROMPT_UPGRADE] call_sid=CA1234... hash=abc123de type=EXPANSION_NOT_REBUILD
[NAME_ANCHOR] ensured ok (no change)
```

Or if name changed (rare):
```
[NAME_ANCHOR] re-injected enabled=True name="..." item_id=...
```

## ✅ Data Source Verification

Customer name is still read from **same sources** (only injection changed):
1. `outbound_lead_name` - for outbound calls
2. `crm_context.customer_name` - from CRM
3. `pending_customer_name` - from temporary storage

**Validation:** Rejects placeholder values: "unknown", "test", "-", "null", "none"

## 🧪 Tests

All 11 tests pass:
- ✅ Detects Hebrew: 'השתמש בשם', 'תשתמש בשם', 'פנה בשמו'
- ✅ Detects English: 'use name', 'use their name'
- ✅ CRITICAL: 'ליצור קרבה' correctly IGNORED
- ✅ NAME_ANCHOR messages explicit with ACTION REQUIRED
- ✅ No duplicate instructions

## 📁 Files Changed

1. **server/services/realtime_prompt_builder.py**
   - Added `detect_name_usage_policy()` - EXPLICIT detection only
   - Added `build_name_anchor_message()` - SHORT with ACTION REQUIRED
   - Fixed system prompt: removed "ליצור קרבה", added "תשתמש בשם"

2. **server/media_ws_ai.py**
   - Replaced CRM context injection with NAME_ANCHOR system
   - Added name policy detection at session start
   - Added `_ensure_name_anchor_present()` for post-upgrade re-injection
   - Proper logging format matching verification requirements

3. **test_name_policy_detection.py** (new)
   - Tests for name policy detection
   - Tests for NAME_ANCHOR message generation

4. **verify_name_anchor_logs.py** (new)
   - Log verification guide
   - Shows expected log patterns

## 🚀 Deployment Checklist

- [x] Code compiles without errors
- [x] All tests pass
- [x] Logging format matches requirements
- [x] Operation order verified (system → policy → anchor → greeting)
- [x] ensure() function actually re-injects when needed
- [x] Customer name data sources preserved
- [x] Removed "ליצור קרבה" from detection and system prompt

## 🎯 Expected Behavior After Deployment

**With name + name usage requested:**
- AI will use customer name naturally in greeting
- AI will continue using name throughout conversation
- Name usage persists after PROMPT_UPGRADE

**With name but NOT requested:**
- AI has name available but won't use it
- Name only for internal reference if needed

**Without name but requested:**
- AI knows name was requested but not available
- Continues conversation normally without name

**Without name and NOT requested:**
- Normal conversation without name references

## 📊 Success Metrics

Monitor these logs to verify deployment:
1. `[NAME_POLICY]` appears in every call with business prompt check
2. `[NAME_ANCHOR] injected` appears BEFORE `[GREETING]`
3. `[NAME_ANCHOR] ensured` appears after every `[PROMPT_UPGRADE]`
4. Customer reports name being used naturally throughout calls

## ⚠️ Red Flags to Watch For

- No `[NAME_ANCHOR]` log → Not injected!
- `[NAME_ANCHOR]` after `[GREETING]` → Wrong order!
- No `[NAME_ANCHOR] ensured` after upgrade → Not checking!
- Name only used in greeting, not throughout → Context lost

---

**Implementation Date:** 2025-12-29
**Status:** ✅ COMPLETE - Ready for deployment
**Verification:** Send 15-20 lines of logs including NAME_POLICY/NAME_ANCHOR/PROMPT_UPGRADE for confirmation
