# Name Extraction Fix for Outbound Calls - Implementation Summary

## תיקון חילוץ שם לקוח לשיחות יוצאות

### 🔍 בעיה מקורית (Original Problem)

הלוגים הראו שבשיחות יוצאות:
- `[NAME_POLICY] ... result=True` ✅ → הפרומפט העסקי דורש שימוש בשם
- אבל:
  - `outbound_lead_name: ריק`
  - `crm_context exists: False`
  - `pending_customer_name: None`
  - `extracted name: None`
- תוצאה: או מדלג או מזריק `name='None'` (באג)

### 🎯 שורש הבעיה (Root Cause)

השם לא הגיע בכלל לשכבת השיחה. הבעיה הייתה שהשם לא נטען מה-DB בתחילת השיחה.

### ✅ הפתרון שיושם (Solution Implemented)

#### 1. מניעת הזרקת None (Prevent None Injection)

**קובץ**: `server/media_ws_ai.py`
**פונקציה**: `_ensure_name_anchor_present()`

```python
# 🔥 FIX: Skip re-injection if name is None or invalid
if not current_name or not str(current_name).strip():
    logger.debug(f"[NAME_ANCHOR] ensure: skipping - no valid name available")
    return

# Validate name is not a placeholder
name_lower = str(current_name).lower().strip()
if name_lower in INVALID_NAME_PLACEHOLDERS:
    logger.debug(f"[NAME_ANCHOR] ensure: skipping - invalid name '{current_name}'")
    return
```

**תוצאה**: לא מזריק יותר `name='None'` או ערכים לא תקינים.

#### 2. הרחבת חיפוש שם לפי lead_id (Enhanced Name Resolution)

**קובץ**: `server/media_ws_ai.py`
**פונקציה**: `_resolve_customer_name()`

**סדר עדיפויות חדש (New Priority Order)**:

1. **CallLog.customer_name** (קיים) - אם השם כבר שמור ב-CallLog
2. **✨ NEW: Lead by lead_id** - חיפוש ישיר לפי lead_id מ-customParameters
3. **OutboundCallJob.lead_name** (קיים) - עבור שיחות בתור
4. **Lead via CallLog.lead_id** (קיים) - דרך הקשר של CallLog
5. **✨ NEW: Lead by phone** - גיבוי - חיפוש לפי מספר טלפון

```python
def _resolve_customer_name(
    call_sid: str, 
    business_id: int, 
    lead_id: Optional[int] = None,  # ✨ NEW
    phone_number: Optional[str] = None  # ✨ NEW
) -> tuple:
```

#### 3. העברת lead_id דרך WebSocket (Pass lead_id Through)

**זרימה מלאה (Full Flow)**:

1. **routes_outbound.py** → יוצר שיחה עם `lead_id`:
   ```python
   result = create_outbound_call(
       to_phone=normalized_phone,
       from_phone=from_phone,
       business_id=tenant_id,
       host=host,
       lead_id=lead.id,  # ✅ מועבר כאן
       business_name=business_name
   )
   ```

2. **twilio_outbound_service.py** → מוסיף ל-webhook URL:
   ```python
   webhook_url = f"https://{host}/webhook/outbound_call?business_id={business_id}"
   if lead_id:
       webhook_url += f"&lead_id={lead_id}"  # ✅ מועבר כאן
   ```

3. **routes_twilio.py** → מוסיף כ-stream parameter:
   ```python
   stream.parameter(name="lead_id", value=lead_id)  # ✅ מועבר כאן
   ```

4. **media_ws_ai.py** → קורא מ-customParameters:
   ```python
   self.outbound_lead_id = custom_params.get("lead_id")  # ✅ נשמר כאן
   
   # ואז משתמש בו:
   lead_id = getattr(self, 'outbound_lead_id', None)
   resolved_name, name_source = _resolve_customer_name(
       self.call_sid, 
       business_id_safe,
       lead_id=lead_id,  # ✅ מועבר לפתרון
       phone_number=phone_number
   )
   ```

#### 4. לוגים מפורטים (Comprehensive Logging)

```python
# בתחילת הפתרון:
logger.info(f"[NAME_RESOLVE] Starting resolution: call_sid={call_sid[:8]}, lead_id={lead_id}, phone={phone_number}")

# כשמוצא שם:
logger.info(f"[NAME_RESOLVE] source=lead_id name=\"{name}\" lead_id={lead_id}")

# כשלא מוצא:
print(f"⚠️ [NAME_ANCHOR DEBUG] Name resolution FAILED:")
print(f"   lead_id from customParameters: {lead_id}")
print(f"   phone_number for fallback: {phone_number}")
print(f"   Result: No name found in any source")
```

### 📊 אימות (Verification)

**רצף נכון אחרי התיקון (Correct Sequence After Fix)**:

```
[NAME_POLICY] ... result=True
[NAME_RESOLVE DEBUG] call_sid=CA1234... lead_id=123 phone=+972501234567
[NAME_RESOLVE] source=lead_id name="דוד כהן" lead_id=123
[NAME_ANCHOR DEBUG] Resolved from DB:
   call_sid: CA1234...
   lead_id from customParameters: 123
   resolved_name: דוד כהן
   name_source: lead_id
[NAME_ANCHOR] Injected enabled=True name="דוד כהן"
[PROMPT_SUMMARY] system=1 business=0 name_anchor=1
```

### 🧪 בדיקות (Tests)

נוצרה סוויטת בדיקות מקיפה: `test_name_extraction_fix.py`

**5 בדיקות שעברו בהצלחה**:
1. ✅ None Injection Prevention - אין הזרקת None
2. ✅ Lead ID Resolution - חיפוש לפי lead_id
3. ✅ Phone Number Fallback - גיבוי לפי טלפון
4. ✅ Debug Logging - לוגים מפורטים
5. ✅ Outbound Parameters - העברת פרמטרים

### 🔒 אבטחה (Security)

✅ **CodeQL Security Scan**: No vulnerabilities found
✅ **Code Review**: All feedback addressed

### 🎨 שיפורים נוספים (Additional Improvements)

1. **קבוע למחרוזות לא תקינות** (Constant for Invalid Names):
   ```python
   INVALID_NAME_PLACEHOLDERS = [
       'none', 'null', 'unknown', 'test', '-', 'n/a', 
       'לא ידוע', 'ללא שם', 'na', 'n.a.', 'undefined'
   ]
   ```

2. **שימוש חוזר בקבוע** - כל פונקציות האימות משתמשות באותו קבוע (DRY)

3. **לוגים משופרים** - שימוש ב-`logger.exception()` במקום print traceback

### 📝 סיכום (Summary)

התיקון פותר את הבעיה המקורית ב-3 שכבות:

1. **מניעה** - לא מזריק None או ערכים לא תקינים
2. **פתרון שורש** - טוען את השם מה-DB לפי lead_id
3. **גיבוי** - אם אין lead_id, מחפש לפי טלפון

**הכי חשוב**: עכשיו השם מגיע לשכבת השיחה כבר בהתחלה, לא צריך לנחש!

---

**Files Changed**:
- `server/media_ws_ai.py` - Main fixes
- `test_name_extraction_fix.py` - Comprehensive test suite

**No Breaking Changes**: All changes are backward compatible and improve existing behavior.
