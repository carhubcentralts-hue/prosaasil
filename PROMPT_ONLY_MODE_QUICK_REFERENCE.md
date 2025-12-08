# 🔥 PROMPT-ONLY MODE - Quick Reference

## What Changed?

The realtime call system now operates in **100% prompt-only mode** by default.

## Key Changes

### 1️⃣ No Hardcoded Fields
- ❌ Before: System required `['name', 'preferred_time']` by default
- ✅ After: System requires `[]` (nothing) by default
- **Result:** Business prompt defines what's needed, not Python code

### 2️⃣ Smart Hangup is Prompt-Only
- ❌ Before: Hangup depended on collecting specific fields
- ✅ After: Hangup relies on goodbye phrase + user interaction only
- **Result:** Call ends naturally based on conversation, not field checklist

### 3️⃣ Negative Answer Reset
- ❌ Before: User saying "לא" had partial handling
- ✅ After: Strong "לא" triggers full reset + generic system message
- **Result:** Clean restart without hardcoded field assumptions

### 4️⃣ Server Error Retry
- ❌ Before: No automatic retry on OpenAI server errors
- ✅ After: One automatic retry, then graceful Hebrew failure message
- **Result:** Better reliability and user experience

### 5️⃣ Generic Prompt Rules
- ❌ Before: Meta-rules might mention specific fields
- ✅ After: All meta-rules are field-agnostic
- **Result:** Works with any business prompt without code changes

---

## How It Works

### Default Behavior (No required_lead_fields configured)
```python
required_lead_fields = []  # Empty by default
```

1. **Conversation Flow:** 100% driven by business ai_prompt
2. **Field Collection:** AI collects what prompt says to collect
3. **Verification:** AI verifies according to prompt instructions
4. **Hangup:** Happens on goodbye phrase + auto_end_on_goodbye flag

### When User Says "לא" (No/Rejection)

```python
if is_strong_rejection:  # Short "לא" utterance
    # 1. Reset all state
    self._verification_state = None
    self._lead_candidate = {}
    
    # 2. Clear locked fields
    self._city_locked = False
    self._service_locked = False
    
    # 3. Send generic system message (in Hebrew)
    system_msg = "המשתמש דחה את ההבנה הקודמת שלך..."
```

**AI receives instruction to:**
- Apologize briefly
- Ask user to repeat all important details
- Handle partial info by asking only for missing pieces
- Follow business instructions (not hardcoded rules)

### Server Error Handling

```python
if response.status == "failed" and error.type == "server_error":
    if not self._server_error_retried:
        # First time: Retry
        self._server_error_retried = True
        await self._send_text_to_ai("היתה שגיאה זמנית...")
        await client.send_event({"type": "response.create"})
    else:
        # Second time: Graceful failure
        failure_msg = "יש בעיה טכנית זמנית במערכת..."
        # AI tells user, says goodbye, call ends
```

---

## Business Configuration

### Option A: Prompt-Only (Default)
```python
# BusinessSettings
required_lead_fields = None  # or []
```
**Result:** System adapts to whatever business prompt says

### Option B: Explicit Field Requirements (Legacy)
```python
# BusinessSettings
required_lead_fields = ['name', 'email']
```
**Result:** System validates these fields are collected before hangup

---

## Testing Checklist

- [ ] Call flows naturally without forcing specific fields
- [ ] User saying "לא" triggers reset and re-collection
- [ ] Hangup happens on goodbye phrase (not field completion)
- [ ] OpenAI server_error retries once, then fails gracefully
- [ ] Different business prompts work without code changes

---

## Files Modified

1. **server/media_ws_ai.py** (158 lines changed)
   - Removed hardcoded defaults
   - Updated `_check_lead_captured()`
   - Enhanced SMART_HANGUP
   - Implemented negative answer reset
   - Added server_error retry

2. **server/services/realtime_prompt_builder.py** (21 lines changed)
   - Added generic rejection handling rules
   - Added partial information handling guidance
   - Removed any field-specific language

---

## Migration Path

**Existing Businesses:**
- Businesses with configured `required_lead_fields` continue working
- No changes needed to existing configurations

**New Businesses:**
- Default to prompt-only mode automatically
- No configuration required unless specific validation needed

---

## Support

For detailed technical documentation, see:
- `REFACTOR_PROMPT_ONLY_MODE_SUMMARY.md` - Complete technical spec
- `server/media_ws_ai.py` - Implementation
- `server/services/realtime_prompt_builder.py` - Prompt generation

---

**Version:** December 8, 2025  
**Status:** ✅ Production Ready
