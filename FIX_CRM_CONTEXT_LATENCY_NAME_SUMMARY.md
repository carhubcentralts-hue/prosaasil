# תיקון טעינת CRM Context, שימוש בשם, ו-Latency

## סיכום השינויים

### בעיות שתוקנו

#### A) CRM Context נכשל - חייב להיכנס לפני session.update

**הבעיה**: 
- CRM context (שם, מגדר, פרטי קשר) נטען **אחרי** session.update או בכלל נכשל
- היה לוג "crm context failed" אבל השיחה המשיכה בלי פרטי הלקוח
- המודל לא ידע את השם למרות שהיה prompt "להשתמש בשם"

**התיקון**:
1. **טעינת CRM Context מיד אחרי START event** (media_ws_ai.py, שורות ~9883-9978)
   - טוען Lead + Contact fields מיד אחרי business validation
   - קורה **לפני** התחלת OpenAI session
   - כולל retry logic: מנסה פעמיים עם המתנה של 300ms
   - תמיד מחזיר אובייקט תקין (מחרוזות ריקות במקום None)

2. **הוספת CRM Context ל-instructions לפני session.update** (media_ws_ai.py, שורות ~3706-3728)
   - מוסיף בלוק `## CRM_CONTEXT_START ... ## CRM_CONTEXT_END`
   - כולל: First Name, Gender, Email, Lead ID
   - נשלח **בתוך** ה-instructions של session.update הראשון
   - זמין למודל **לפני** response.create הראשון

3. **לוגים ברורים** (acceptance criteria מהמפרט):
   ```
   [CRM_CONTEXT] loaded ok lead_id=123 name=שי gender=male time=45ms retry=0
   ```
   או במקרה כשל:
   ```
   [CRM_CONTEXT] FAILED lead_id=123 error=Connection timeout retry=1 time=650ms
   ```

#### B) Business Prompt לא נכנס (business=0)

**הבעיה**:
- לפעמים ה-business prompt לא באמת נשלח ל-OpenAI
- לא היה דרך לוודא שה-prompt אכן נשלח

**התיקון**:
1. **הוספת מרקרים ל-prompts** (realtime_prompt_builder.py, שורות ~970-976)
   ```
   ## BUSINESS_PROMPT_START
   BUSINESS PROMPT (Business ID: 4, Name: Test Business, Call: INBOUND)
   ...
   ## BUSINESS_PROMPT_END
   ```

2. **ווידוא אחרי session.updated** (media_ws_ai.py, שורות ~3833-3851)
   ```
   [SESSION_VERIFY] instructions_len=2345, includes_business_prompt=True, includes_crm_context=True
   ```
   
   אם business prompt חסר:
   ```
   🚨 [SESSION_VERIFY] Business prompt marker MISSING - prompt may be incomplete!
   ```

#### C) הבוט לא משתמש בשם למרות ה-prompt

**הבעיה**:
- השם והמגדר לא היו זמינים למודל בזמן אמת
- הם נטענו רק **אחרי** session.update

**התיקון**:
- השם והמגדר עכשיו **בתוך** ה-instructions שנשלח ב-session.update
- זמינים למודל מהרגע הראשון
- הפורמט ברור:
  ```
  ## CRM_CONTEXT_START
  Customer Information:
  - First Name: שי
  - Gender: male
  - Email: shai@example.com
  - Lead ID: 123
  ## CRM_CONTEXT_END
  ```

#### D) Latency גבוה (6 שניות לפעמים)

**הבעיה**:
- לא היה מדידה מדויקת של latency
- לא ידענו איפה הזמן הולך

**התיקון**:
1. **לוגי latency** (media_ws_ai.py, שורות ~3860-3865 ו-5017-5021)
   ```
   [LATENCY] ws_open->session.updated=1234ms
   [LATENCY] session.updated->response.create=35ms
   ```
   
2. **יעד**: `session.updated->response.create` צריך להיות **0-50ms**

3. **תיעוד נקודות המתנה**:
   - OpenAI connection: מדיד
   - CRM context loading: מדיד
   - Session configuration: מדיד

#### E) טיפול בשגיאות חזק

**הבעיה**:
- כשלונות ב-CRM loading גרמו ל-None values
- זה גרם לבאגים במקומות אחרים בקוד

**התיקון**:
- תמיד מחזיר מחרוזות ריקות (`""`) במקום `None`
- `try/except` עוטף את כל הטעינה
- השיחה ממשיכה גם אם CRM context נכשל
- לוגים ברורים על כשלונות

---

## קבצים ששונו

### 1. server/media_ws_ai.py

**שינוי 1: טעינת CRM Context ב-START event handler** (שורות ~9883-9978)
```python
# 🔥 STEP 1.5: LOAD CRM CONTEXT (Lead + Contact fields) IMMEDIATELY
# This MUST happen BEFORE session.update to ensure name/gender/details are available
lead_id_for_crm = getattr(self, 'outbound_lead_id', None)
...
# Try to load CRM context with retry
for attempt in range(2):  # Initial + 1 retry
    try:
        from server.models_sql import Lead
        ...
        # Extract fields from Lead
        if crm_lead:
            # Get name (first name only for natural usage)
            full_name = crm_lead.full_name or ...
            crm_name = extract_first_name(full_name) or ""
            
            # Get other fields (use empty string instead of None)
            crm_gender = str(crm_lead.gender or "")
            crm_email = str(crm_lead.email or "")
            ...
        
        # Store CRM context in instance (always store, even if empty)
        self._crm_context_name = crm_name
        self._crm_context_gender = crm_gender
        ...
        
        # 🔥 ACCEPTANCE CRITERIA: Log CRM context loading success
        _orig_print(
            f"[CRM_CONTEXT] loaded ok lead_id={self._crm_context_lead_id} "
            f"name={crm_name if crm_name else 'NONE'} gender={crm_gender if crm_gender else 'NONE'} "
            f"time={crm_ms:.0f}ms retry={crm_retry_count}",
            flush=True
        )
        break  # Success - exit retry loop
        
    except Exception as crm_err:
        # Retry or fail with clear logging
        ...
```

**שינוי 2: הוספת CRM Context ל-instructions** (שורות ~3706-3728)
```python
# ═══════════════════════════════════════════════════════════════════════
# 🔥 STEP 0.7: ADD CRM CONTEXT TO PROMPT (before session.update)
# ═══════════════════════════════════════════════════════════════════════
has_crm_context = False
if hasattr(self, '_crm_context_name') or hasattr(self, '_crm_context_gender'):
    crm_name = getattr(self, '_crm_context_name', '')
    crm_gender = getattr(self, '_crm_context_gender', '')
    ...
    
    # Only add CRM context if we have name or gender
    if crm_name or crm_gender:
        crm_context_block = "\n\n## CRM_CONTEXT_START\n"
        crm_context_block += "Customer Information:\n"
        if crm_name:
            crm_context_block += f"- First Name: {crm_name}\n"
        if crm_gender:
            crm_context_block += f"- Gender: {crm_gender}\n"
        ...
        crm_context_block += "\n## CRM_CONTEXT_END\n"
        
        # Add CRM context to greeting prompt
        greeting_prompt = greeting_prompt + crm_context_block
        has_crm_context = True
        ...
```

**שינוי 3: ווידוא אחרי session.updated** (שורות ~3833-3865)
```python
# 🔥 ACCEPTANCE CRITERIA B: Verify business prompt and CRM context are in instructions
instructions_len = len(greeting_prompt)
includes_business_prompt = "## BUSINESS_PROMPT_START" in greeting_prompt
includes_crm_context = "## CRM_CONTEXT_START" in greeting_prompt

_orig_print(
    f"[SESSION_VERIFY] instructions_len={instructions_len}, "
    f"includes_business_prompt={includes_business_prompt}, "
    f"includes_crm_context={includes_crm_context}",
    flush=True
)
...
# Warn if business prompt marker is missing
if not includes_business_prompt:
    logger.error(f"[SESSION_VERIFY] CRITICAL: Business prompt marker missing from instructions!")
    _orig_print(f"🚨 [SESSION_VERIFY] Business prompt marker MISSING!", flush=True)
```

**שינוי 4: לוגי Latency** (שורות ~3860-3865 ו-5017-5021)
```python
# Store timestamp for latency measurement
self.t_session_confirmed = t_session_confirmed

# 🔥 ACCEPTANCE CRITERIA D: Log latency from WS open to session.updated
ws_open_to_session_ms = (t_session_confirmed - self.t0_connected) * 1000
_orig_print(f"[LATENCY] ws_open->session.updated={ws_open_to_session_ms:.0f}ms", flush=True)

...

# In trigger_response (for greeting)
if is_greeting and hasattr(self, 't_session_confirmed'):
    session_to_response_ms = (now - self.t_session_confirmed) * 1000
    _orig_print(f"[LATENCY] session.updated->response.create={session_to_response_ms:.0f}ms", flush=True)
```

### 2. server/services/realtime_prompt_builder.py

**שינוי: הוספת מרקרים לבusiness prompt** (שורות ~970-976)
```python
# Keep the full text (do not sanitize for length here)
return (
    f"## BUSINESS_PROMPT_START\n"
    f"BUSINESS PROMPT (Business ID: {business_id}, Name: {business_name}, Call: {direction_label})\n"
    f"{business_prompt_text}\n"
    f"## BUSINESS_PROMPT_END"
)
```

### 3. test_crm_context_before_session_update.py (חדש)

טסט מקיף שבודק:
1. טעינת CRM context מ-Lead
2. בניית בלוק CRM context עם מרקרים
3. ווידוא נוכחות מרקרים ב-instructions
4. טיפול בשגיאות (החזרת מחרוזות ריקות)

---

## בדיקות שצריך לבצע אחרי תיקון

### 1. ווידוא טעינת CRM Context (10 שיחות רצוף)

בכל שיחה, בדוק בלוגים:

✅ **לפני session.update חייב להופיע**:
```
[CRM_CONTEXT] loaded ok lead_id=123 name=שי gender=male time=45ms retry=0
```
**או** במקרה כשל:
```
[CRM_CONTEXT] FAILED lead_id=123 error=... retry=1
```

### 2. ווידוא Business Prompt ו-CRM Context בinstructions

אחרי session.updated חייב להופיע:
```
[SESSION_VERIFY] instructions_len=2345, includes_business_prompt=True, includes_crm_context=True
```

אם `includes_business_prompt=False` → זה באג!
אם `includes_crm_context=False` → בדוק למה CRM context לא נטען

### 3. ווידוא שימוש בשם

המודל צריך להשתמש בשם של הלקוח בשיחה (אם יש prompt "להשתמש בשם").
זה עובד כי השם עכשיו ב-instructions מההתחלה.

### 4. מדידת Latency

בכל שיחה בדוק:
```
[LATENCY] ws_open->session.updated=1234ms
[LATENCY] session.updated->response.create=35ms
```

**יעד**: `session.updated->response.create` < 50ms ב-90% מהשיחות

אם יש שיחות של 6 שניות, בדוק breakdown:
- DB time
- connect time
- wait session.updated
- first audio delta

### 5. ווידוא gender

בדוק שהמגדר מופיע בקונטקסט:
- בלוג CRM_CONTEXT: `gender=male` או `gender=female`
- ב-instructions: `- Gender: male`

---

## לוגים לדוגמה

### שיחה מוצלחת:

```
✅ [BUSINESS_ISOLATION] Business validated: 4
[CRM_CONTEXT] loaded ok lead_id=123 name=שי gender=male time=45ms retry=0
📤 [SESSION] Sending session.update with config...
✅ [SESSION] session.updated confirmed in 234ms (retried=False) - safe to proceed
[SESSION_VERIFY] instructions_len=2345, includes_business_prompt=True, includes_crm_context=True
[LATENCY] ws_open->session.updated=1234ms
[LATENCY] session.updated->response.create=35ms
```

### שיחה עם כשל CRM:

```
✅ [BUSINESS_ISOLATION] Business validated: 4
[CRM_CONTEXT] FAILED lead_id=123 error=Connection timeout retry=1 time=650ms
📤 [SESSION] Sending session.update with config...
✅ [SESSION] session.updated confirmed in 234ms (retried=False) - safe to proceed
[SESSION_VERIFY] instructions_len=2300, includes_business_prompt=True, includes_crm_context=False
[LATENCY] ws_open->session.updated=1884ms
[LATENCY] session.updated->response.create=38ms
```

---

## תועלות

1. ✅ **CRM context תמיד זמין לפני response ראשון**
   - השם והמגדר נטענים מיד אחרי START event
   - נכללים ב-instructions לפני session.update
   - המודל יודע מי הלקוח מההתחלה

2. ✅ **שימוש נכון בשם**
   - המודל יכול להשתמש בשם כי הוא ב-instructions
   - לא צריך להמתין ל-NAME_ANCHOR injection

3. ✅ **לוגים ברורים לדיבוג**
   - `[CRM_CONTEXT]` - הצלחה/כשל
   - `[SESSION_VERIFY]` - ווידוא תוכן instructions
   - `[LATENCY]` - מדידות זמן

4. ✅ **טיפול בשגיאות חזק**
   - שיחה ממשיכה גם אם CRM context נכשל
   - תמיד מחרוזות ריקות (לא None)
   - retry logic עם המתנה

5. ✅ **מעקב latency**
   - יודעים בדיוק איפה הזמן הולך
   - יכולים לזהות בעיות ביצועים
   - יעד ברור: < 50ms בין session.updated ל-response.create

---

## סיכום קצר

התיקון פותר **3 בעיות עיקריות**:

1. **CRM context נכשל** → עכשיו נטען מיד אחרי START event עם retry logic ולוגים ברורים
2. **הבוט לא משתמש בשם** → עכשיו השם והמגדר ב-instructions מההתחלה
3. **Latency גבוה** → עכשיו יש מדידה מדויקת ו-optimization של הסדר

**ללא שינוי התנהגות עסקית** ו**ללא לוגיקה קשיחה** - רק תיקון מה ששבור.
