# Customer Name Usage Fix - Complete Summary

## Problem Statement (Hebrew)
```
יש לי בעיה, פעם אם שם היה מעודכן במערכת, אז אם הייתי רושם בפרומפט של העסק 
"תשתמשי בשם של הלקוח במהלך השיחה", אז היא הייתה משתמשת בו יפה! 
ככשיו פתאום זה לא עובד! תבדוק מה הבעיה! זב חשוב!!
```

**Translation:** Names were working before when written in business prompt, but suddenly stopped working.

## User's Exact Business Prompt
```
במידה וקיים שם לקוח, השתמש בשם שלו באופן טבעי לאורך השיחה כדי ליצור קרבה.
אם אין שם – המשך כרגיל בלי להזכיר זאת.
```

**Translation:** "If a customer name exists, use their name naturally throughout the conversation to create closeness. If no name - continue normally without mentioning it."

## Root Causes Identified

### Issue #1: Placeholder Name Injection
**Problem:** Names like "unknown", "test", "-" were being injected into AI context  
**Impact:** AI received invalid placeholder values as if they were real names

### Issue #2: Vague Recognition Instructions
**Problem:** System prompt said "use name ONLY if Business Prompt requests" but didn't explain HOW to recognize such requests in Hebrew  
**Impact:** AI couldn't reliably identify when to use customer names, especially with Hebrew phrasings

## Solutions Implemented

### Solution #1: Name Validation (Commit a32c34d)

**Added validation function:**
```python
def _is_valid_customer_name(name: str) -> bool:
    """Validate that customer name is real data, not a placeholder."""
    if not name:
        return False
    
    name_lower = name.strip().lower()
    if not name_lower:
        return False
    
    # Reject common placeholder values
    invalid_values = ['unknown', 'test', '-', 'null', 'none', 'n/a', 'na']
    if name_lower in invalid_values:
        return False
    
    return True
```

**Applied in two locations:**
1. `_extract_customer_name()` - validates during extraction
2. CRM context marking - validates before injection

**Result:** Only real customer names are injected into AI conversation context

### Solution #2: Enhanced Recognition Patterns (Commit d95fbd8)

**Before:**
```
"- Use the customer's name ONLY if the Business Prompt requests name usage."
```

**After:**
```
"- RULE: Use the customer's name ONLY if the Business Prompt explicitly instructs you to use it.
- Name usage instructions may appear in various forms (watch for these phrases):
  Hebrew: 'השתמש בשם', 'פנה בשמו', 'קרא בשם', 'לפנות בשם', 'ליצור קרבה', 'באופן טבעי'
  Conditional: 'אם קיים שם', 'במידה וקיים שם', 'אם יש שם'
  English: 'use name', 'use their name', 'address by name', 'call by name'
- IMPORTANT: Any Business Prompt mentioning 'שם' (name) with action verbs like השתמש/פנה/קרא means USE IT.
- If the Business Prompt contains ANY phrase about using/addressing/calling with the customer's name → USE it naturally throughout the conversation."
```

**Result:** AI can now recognize name usage requests in both Hebrew and English

## Files Modified

1. **server/media_ws_ai.py**
   - Added `_is_valid_customer_name()` validation function
   - Updated `_extract_customer_name()` to validate all sources
   - Added validation check before marking for injection

2. **server/services/realtime_prompt_builder.py**
   - Enhanced "Customer Name Usage" section with explicit patterns
   - Added Hebrew and English examples
   - Added clear actionable rule

3. **מדריך_שימוש_בשם_לקוח.md**
   - Updated validation section
   - Added documentation about new validation logic

## Tests Created

1. **test_customer_name_validation.py**
   - Tests validation accepts real names
   - Tests validation rejects placeholders

2. **test_placeholder_name_filtering.py**
   - Tests extraction with multiple sources
   - Tests fallback to valid names when placeholders exist

3. **test_business_prompt_name_recognition.py**
   - Tests user's exact phrasing is recognized
   - Tests various Hebrew and English patterns

## Test Results

✅ **All tests pass:**
- Customer name flow: ✅ Names reach AI correctly
- Validation: ✅ Real names accepted, placeholders rejected
- Recognition: ✅ User's exact phrasing is recognized

## Expected Behavior Now

### Scenario 1: Valid Name + Name Usage Request in Business Prompt
**Business Prompt:** "במידה וקיים שם לקוח, השתמש בשם שלו באופן טבעי"  
**Customer Name:** "דוד"  
**Result:** ✅ AI uses "דוד" naturally throughout conversation

### Scenario 2: Placeholder Name + Name Usage Request
**Business Prompt:** "במידה וקיים שם לקוח, השתמש בשם שלו"  
**Customer Name:** "unknown"  
**Result:** ✅ Name is filtered out, AI continues without using a name  
**Log:** `⚠️ [CRM_CONTEXT] Invalid/placeholder name detected, skipping injection: 'unknown'`

### Scenario 3: Valid Name + No Name Usage Request
**Business Prompt:** "אתה נציג שירות מקצועי. עזור ללקוח."  
**Customer Name:** "דוד"  
**Result:** ✅ Name is available but NOT used (respects business prompt)

### Scenario 4: No Name + Name Usage Request
**Business Prompt:** "אם קיים שם לקוח, השתמש בשם שלו"  
**Customer Name:** (none)  
**Result:** ✅ AI continues normally without mentioning name

## Commits

1. **a32c34d** - Add validation to filter out placeholder customer names
2. **d95fbd8** - Improve system prompt to better recognize name usage requests in business prompts

## Verification Steps for User

1. **Check logs for name injection:**
   ```
   ✅ [CRM_CONTEXT] Injected customer name: 'דוד'
   ```

2. **Verify name appears in AI responses when business prompt requests it:**
   - Business prompt: "במידה וקיים שם לקוח, השתמש בשם שלו באופן טבעי"
   - Expected: AI says "היי דוד, מה שלומך?" or similar

3. **Verify placeholders are filtered:**
   ```
   ⚠️ [CRM_CONTEXT] Invalid/placeholder name detected, skipping injection: 'unknown'
   ```

## Summary

The issue had TWO root causes:
1. ❌ **Placeholder names** were being injected → Fixed with validation
2. ❌ **AI couldn't recognize Hebrew name usage requests** → Fixed with explicit pattern examples

Both are now fixed. The AI will correctly use customer names when the business prompt requests it (including the user's exact phrasing), while filtering out invalid placeholder values.
