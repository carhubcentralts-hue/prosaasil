# Hebrew Natural AI + Customer Name Handling Implementation

## 🎯 Overview

This implementation adds two critical features to the AI phone agent system:

1. **Hebrew Natural Language**: AI thinks and speaks in native Israeli Hebrew (not translated)
2. **Customer Name Handling**: Prompt-driven name usage (controlled by business prompt)

## 🔥 Key Principle: 100% Prompt-Driven

**NO hardcoded logic** - Everything is controlled through prompts:
- System Prompt: Behavior rules only (universal)
- Business Prompt: All content, flow, and business-specific instructions

## 📋 Implementation Details

### 1. System Prompt Enhancement (Hebrew Naturalness)

Location: `server/services/realtime_prompt_builder.py` → `_build_universal_system_prompt()`

#### Hebrew Language Rules Added:
```
Hebrew Language Rules:
- You think, reason, and formulate responses ONLY in native Israeli Hebrew
- Do NOT translate from English
- Do NOT use book-style, academic, or formal Hebrew
- Do NOT use unnatural sentence order or foreign phrasing
- Your Hebrew must sound like a native Israeli, born and raised in Israel
- Prefer short, clear sentences
- Use natural Israeli phrasing
- Avoid high-register words like לרבות, לפיכך, בנוסף לכך, בהתאם לכך
- Before responding, internally rewrite the sentence to sound like spoken Israeli Hebrew
- If a sentence sounds translated or unnatural, rewrite it
```

#### Benefits:
✅ AI thinks in Hebrew (not English → Hebrew translation)
✅ Natural, conversational Israeli Hebrew
✅ Avoids formal/academic language
✅ Internal rewrite for naturalness

### 2. Customer Name Handling (Prompt-Driven)

Location: Same file, same function

#### Customer Name Rules Added:
```
Customer Name Rules:
- If customer data includes a name, you may use it ONLY if explicitly instructed in the business prompt
- If the business prompt does NOT instruct you to use the customer's name:
  * Do NOT mention it
  * Do NOT hint at it
  * Do NOT ask about it
- If the business prompt DOES instruct you to use the customer's name:
  * Use it naturally
  * Only if it exists
  * Never ask for it
  * Never guess it
  * Never fabricate it
- When using the customer's name:
  * Use it sparingly
  * Typically once in greeting, and at most once more if natural
  * Do not repeat the name unnecessarily
- If no name exists, speak normally without mentioning it
```

#### How It Works:

**Lead Data Structure** (already exists in code):
```python
class CallCrmContext:
    business_id: int
    customer_phone: str
    customer_name: Optional[str] = None  # Available to AI if set
    lead_id: Optional[int] = None
```

**Business Prompt Controls Usage**:

✅ **Example 1: Business wants to use name**
```
במהלך השיחה:
- אם יש שם לקוח בליד, פנה אליו בשמו כדי ליצור קרבה
- פנה בשם גם בברכה הראשונית
- עשה זאת בצורה טבעית ולא מוגזמת
```

Result: AI will use name if available: "היי דני, מדבר מהמרכז..."

❌ **Example 2: Business doesn't want to use name**
```
(no instruction about name in business prompt)
```

Result: AI won't use name even if available: "היי, מדבר מהמרכז..."

### 3. Lead Data Injection Pattern

The system already injects lead data into conversations through `CallCrmContext`. The name handling rules ensure:

1. **Name is available** as `customer_name` field in CRM context
2. **AI sees the name** in the conversation context
3. **AI uses it ONLY** if business prompt instructs it
4. **AI never asks** for name if not present (unless business prompt says to)

### 4. Test Scenarios (4 Cases)

| Has Name | Business Prompt Instructs | Expected Behavior |
|----------|---------------------------|-------------------|
| ✅ Yes   | ✅ Yes                     | Uses name naturally |
| ✅ Yes   | ❌ No                      | Does NOT use name |
| ❌ No    | ✅ Yes                     | Does NOT use name (not available) |
| ❌ No    | ❌ No                      | Does NOT use name |

## 🔧 Technical Changes

### File Modified:
- `server/services/realtime_prompt_builder.py`

### Function Modified:
- `_build_universal_system_prompt(call_direction: Optional[str] = None)`

### Changes Made:
1. Added Hebrew Language Rules section
2. Added Customer Name Rules section
3. Updated docstring to document new rules
4. Increased `max_chars` from 1200 → 2000 in `build_global_system_prompt()`

### Prompt Length:
- Inbound: ~1925 chars
- Outbound: ~1919 chars
- Well within 2000 char limit

## ✅ Verification

Run the following to verify:

```python
from server.services.realtime_prompt_builder import _build_universal_system_prompt

prompt = _build_universal_system_prompt(call_direction="inbound")

# Check for key elements
assert "Hebrew Language Rules" in prompt
assert "Customer Name Rules" in prompt
assert "native Israeli Hebrew" in prompt
assert "internally rewrite" in prompt
assert "sparingly" in prompt
print("✅ All checks passed!")
```

## 🎯 Usage Guidelines

### For Business Prompt Authors:

**To enable name usage:**
```
במהלך השיחה:
- אם יש שם לקוח, פנה אליו בשמו כדי ליצור קרבה
- פנה בשם גם בברכה הראשונית
- עשה זאת בצורה טבעית ולא מוגזמת
```

**To disable name usage:**
Simply don't mention anything about using the customer's name in your business prompt.

**Aggressive name usage:**
```
- השתמש בשם הלקוח לאורך כל השיחה כדי ליצור קרבה אישית
- חזור על השם במהלך השיחה לפחות 2-3 פעמים
```

**Subtle name usage:**
```
- אם יש שם לקוח, השתמש בו פעם אחת בברכה
- המשך השיחה באופן טבעי ללא חזרה על השם
```

## 🚀 Benefits

### Hebrew Naturalness:
1. ✅ Sounds like native Israeli speaker
2. ✅ No translation artifacts
3. ✅ Conversational and warm
4. ✅ Avoids formal/academic Hebrew
5. ✅ Professional but natural

### Name Handling:
1. ✅ 100% prompt-driven (no hardcoded logic)
2. ✅ Full business control
3. ✅ Safe defaults (don't use unless instructed)
4. ✅ Prevents name abuse (sparing usage)
5. ✅ Handles missing names gracefully

## 🔒 Safety Features

1. **Never fabricates names** - only uses what's in lead data
2. **Never asks for name** unless business prompt instructs
3. **Graceful fallback** - if no name, continues naturally
4. **Sparing usage** - prevents "creepy" overuse
5. **Prompt isolation** - name rules in system prompt, usage in business prompt

## 📊 Impact

### Before:
- Hebrew sounded translated from English
- No control over customer name usage
- Hardcoded logic for language handling

### After:
- Native Israeli Hebrew
- Full prompt-driven name control
- Clean separation of concerns (system vs business prompts)

## 🔍 Code Locations

- **System Prompt Builder**: `server/services/realtime_prompt_builder.py:96-172`
- **Lead Data Context**: `server/media_ws_ai.py:347-360` (CallCrmContext)
- **Lead Data Injection**: `server/media_ws_ai.py:3185-3196` (CRM context hydration)

## 📝 Notes

- All changes are in the system prompt layer
- No changes to business logic or hardcoded flows
- Compatible with existing business prompts
- Backward compatible (default is to NOT use name)
- Hebrew rules apply to all conversations automatically
- Name rules require explicit opt-in via business prompt

## 🎓 Example Business Prompts

### Example 1: Tax Return Service (with name)
```
אתה נציג מהמרכז להחזרי מס. 

במהלך השיחה:
- אם יש שם לקוח, פנה אליו בשמו כדי ליצור קרבה
- פנה בשם גם בברכה הראשונית

זרימה:
1. ברכה: "היי [שם], מדבר מהמרכז להחזרי מס"
2. שאל על שירות מבוקש
3. קבל פרטים
4. סיכום וסגירה
```

### Example 2: Plumber Service (no name)
```
אתה נציג משרד שרברבים. 

זרימה:
1. ברכה: "היי, מדבר משרברב מקצועי"
2. שאל מה הבעיה
3. קבע תור
4. סיכום וסגירה
```

Note: The second example doesn't mention name usage, so AI won't use it even if available.
