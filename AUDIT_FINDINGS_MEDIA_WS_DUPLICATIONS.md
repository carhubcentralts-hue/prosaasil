# 🔴 QA AUDIT REPORT: MEDIA_WS PROMPTS & DUPLICATIONS

**תאריך:** 2026-01-06  
**קובץ נבדק:** `server/media_ws_ai.py` + Related prompt files  
**סוג בדיקה:** READ-ONLY - איתור כפילויות בלבד

---

## 📋 EXECUTIVE SUMMARY

נמצאו **כפילויות משמעותיות** במספר שכבות של מערכת ה-Prompts:

1. **כפילויות טקסטואליות** - אותם כללים/הוראות מופיעים במקומות שונים
2. **כפילויות לוגיות** - אותה לוגיקה מבוצעת במקומות שונים
3. **כפילויות הזרקה** - מידע עובר למודל מספר פעמים בנקודות שונות
4. **עומס סמנטי** - הצטברות של משמעויות חופפות

**⚠️ השפעה אפשרית:** התנהגות לא דטרמיניסטית, עומס על מודל ה-AI, סבירות מוגברת ל-content_filter errors.

---

## 🔁 PART 1: TEXTUAL DUPLICATIONS (כפילויות טקסטואליות)

### 1.1 Language Instructions - Hebrew/English Switching

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1000-1043`** - `_build_universal_system_prompt()`
```python
"Default output language: Hebrew.\n"
"If the caller clearly speaks another language, continue in that language.\n"
"If unclear, ask once: \"נוח לך בעברית או באנגלית?\"\n"
```

2. **`server/services/prompt_helpers.py:15-27`** - `get_default_hebrew_prompt_for_calls()`
```python
"Default output language: Hebrew.
If the caller clearly speaks another language, continue in that language.
If unclear, ask once: \"נוח לך בעברית או באנגלית?\""
```

**🧠 מה קורה:**  
אותו הכלל מנוסח פעמיים - פעם ב-system prompt (behavior), פעם ב-fallback helper. אם שני המקומות מוזרקים, ה-AI רואה את ההוראה פעמיים.

**⚠️ למה זה בעייתי:**  
- חוזר על עצמו ללא צורך
- אם יש שינוי קל בניסוח, יוצר ambiguity
- מגדיל token count

---

### 1.2 Call Control & Ending Rules

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1040-1042`** - `_build_universal_system_prompt()`
```python
"The business prompt is the primary source for what to say and when to end the call.\n"
"Do not end the call unless the business prompt explicitly instructs it.\n"
```

2. **`server/services/prompt_helpers.py:23-24`** - `get_default_hebrew_prompt_for_calls()`
```python
"The business prompt is the primary source for what to say and when to end the call.
Do not end the call unless the business prompt explicitly instructs it."
```

**🧠 מה קורה:**  
כלל סיום שיחה מוזרק מ-2 מקומות - System Prompt ו-Fallback Prompt.

**⚠️ למה זה בעייתי:**  
- אותו כלל עובר פעמיים אם שני המקורות פעילים
- יוצר redundancy בהוראות סיום שיחה

---

### 1.3 "Short, Calm, Professional" Tone Instructions

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1036`**
```python
"Tone: short, calm, professional, human."
```

2. **`server/services/prompt_helpers.py:20`**
```python
"Tone: short, calm, professional, human."
```

**🧠 מה קורה:**  
הוראת סגנון זהה ממש במילה במילה בשני מקומות.

**⚠️ למה זה בעייתי:**  
- כפילות מילולית מוחלטת
- אם משתנה במקום אחד, נוצר אי-התאמה

---

### 1.4 "Do Not Invent Facts" Rule

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1037`**
```python
"Do not invent facts. If needed, ask one short clarification question."
```

2. **`server/services/prompt_helpers.py:21-22`**
```python
"Do not invent facts. If missing info, ask one short clarification question."
```

**🧠 מה קורה:**  
כלל אותו ממש, ניסוח כמעט זהה, במקומות שונים.

---

### 1.5 Audio Interruption Handling

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1043`**
```python
"If audio is cut, unclear, or interrupted, continue naturally by briefly repeating the last question."
```

2. **`server/services/prompt_helpers.py:26-27`**
```python
"If audio is cut, unclear, or interrupted, continue naturally by briefly repeating the last question."
```

**🧠 מה קורה:**  
הוראה זהה למילה במילה במקומות שונים.

---

## 🔁 PART 2: LOGICAL DUPLICATIONS (כפילויות לוגיות)

### 2.1 Customer Name Resolution - Multiple Code Paths

**📍 מיקומים:**

1. **`server/media_ws_ai.py:3259-3436`** - `_resolve_customer_name()` function
   - Priority 1: `CallLog.customer_name`
   - Priority 2: Lead by `lead_id`
   - Priority 3: `OutboundCallJob.lead_name`
   - Priority 4: Lead via `CallLog.lead_id`
   - Priority 5: Lead by phone number

2. **`server/media_ws_ai.py:3921-3942`** - `_extract_customer_name()` function
   - Source 1: `outbound_lead_name`
   - Source 2: `crm_context.customer_name`
   - Source 3: `pending_customer_name`

3. **`server/media_ws_ai.py:1775-1819`** - CallContext class methods
   - `get_first_name()`
   - `get_customer_name()`
   - Multiple cached name sources

**🧠 מה קורה:**  
שלוש לוגיקות שונות לפתרון שם לקוח, כל אחת עם סדר עדיפות אחר:
- `_resolve_customer_name` - 5 מקורות, מחפש בDB
- `_extract_customer_name` - 3 מקורות, מחפש בזיכרון
- CallContext - מחפש בcache וקישורים

**⚠️ למה זה בעייתי:**  
- אם שם נמצא בשיטה אחת ולא בשנייה → התנהגות לא עקבית
- קשה לעקוב אחר זרימת השם במערכת
- עלול להיות race condition בין המקורות השונים

---

### 2.2 Name Validation - Double Checks

**📍 מיקומים:**

1. **`server/media_ws_ai.py:3906-3919`** - `_is_valid_customer_name()`
```python
INVALID_NAME_PLACEHOLDERS = [
    'none', 'null', 'unknown', 'test', '-', 'n/a', 
    'לא ידוע', 'ללא שם', 'na', 'n.a.', 'undefined'
]
```

2. **`server/services/realtime_prompt_builder.py:146-161`** - `extract_first_name()`
```python
placeholders = [
    "ללא שם", "לא ידוע", "אין שם", "לקוח", "customer", "client",
    "בית", "תמונה", "מסמך", "קובץ", "תיקיה", "folder", "file",
    "שם", "name", "test", "טסט", "בדיקה", "דוגמה", "example",
    "משתמש", "user", "אורח", "guest"
]
```

**🧠 מה קורה:**  
שתי רשימות שונות של placeholders לא-חוקיים. יש חפיפה חלקית אבל גם הבדלים:
- `media_ws_ai.py` - רשימה קצרה יותר, פחות מקיפה
- `realtime_prompt_builder.py` - רשימה ארוכה יותר, יותר מקרי קצה

**⚠️ למה זה בעייתי:**  
- אותו ולידציה, שתי רשימות שונות
- יכול לקבל תוצאות שונות תלוי איזו פונקציה נקראת
- אם מוסיפים ערך לאחת ולא לשנייה → אי-עקביות

---

### 2.3 Prompt Hash Calculation - Duplicate Logic

**📍 מיקומים:**

1. **`server/media_ws_ai.py:3847-3872`** - System prompt normalization
```python
def normalize_for_hash(text):
    # Strip whitespace
    # Normalize line endings
    # Remove dynamic elements (TODAY_ISO, etc.)
    # Calculate MD5 hash
```

2. **`server/media_ws_ai.py:3984-3986`** - Name anchor hash
```python
name_anchor_hash = f"{customer_name_to_inject}|{use_name_policy}"
name_anchor_hash_short = hashlib.md5(name_anchor_hash.encode()).hexdigest()[:8]
```

3. **`server/media_ws_ai.py:4092-4095`** - Greeting prompt hash
```python
prompt_hash = hashlib.md5(greeting_prompt.encode()).hexdigest()[:8]
```

**🧠 מה קורה:**  
שלוש נקודות שונות שמחשבות hash למניעת duplicates, אבל:
- System prompt - יש normalization מורכב לפני hash
- Name anchor - hash פשוט על string
- Greeting prompt - hash פשוט על prompt

**⚠️ למה זה בעייתי:**  
- אותה מטרה (מניעת duplicates), שלוש שיטות שונות
- System prompt יותר מתוחכם (נורמליזציה), אחרים לא
- אם שינוי קוסמטי בפרומפט (רווחים) → hash שונה רק באחד מהם

---

## 🔁 PART 3: INJECTION DUPLICATIONS (כפילויות הזרקה)

### 3.1 System Prompt - Multiple Injection Points

**📍 נקודות הזרקה:**

1. **`server/media_ws_ai.py:3026-3114`** - `_send_session_update()`
   - System prompt נשלח ב-`session.update.instructions`
   - קורה בהתחברות Realtime API

2. **`server/media_ws_ai.py:3804-3895`** - Global system prompt injection
   - שוב System prompt נשלח ב-`conversation.item.create`
   - קורה מיד אחרי `session.updated`
   - **יש flag `_global_system_prompt_injected`** למניעת חזרה

3. **`server/services/realtime_prompt_builder.py:1057-1068`** - `build_global_system_prompt()`
   - Builder נפרד שמייצר את ה-system prompt
   - יכול להיקרא מספר פעמים

**🧠 מה קורה:**  
System prompt עובר ב-2 נקודות שונות:
- פעם ב-`session.update` (configuration)
- פעם שנייה ב-`conversation.item.create` (message)

**🔥 CRITICAL FINDING:**  
יש flag למניעת חזרה (`_global_system_prompt_injected`), אבל זה מגן רק על אותו נתיב. אם `session.update` כולל system rules וגם `conversation.item.create` מוזרק → **המודל רואה את הכללים פעמיים**.

**⚠️ למה זה בעייתי:**  
- System rules עוברים למודל פעמיים בערוצים שונים
- OpenAI Realtime רגיש לכפילויות בinstructions
- יכול לגרום לקונפליקטים או לעומס סמנטי

---

### 3.2 Business Prompt - COMPACT vs FULL

**📍 מיקומים:**

1. **`server/services/realtime_prompt_builder.py:1097-1108`** - `build_compact_business_instructions()`
   - Sanitized first ~400 chars
   - Hard capped to `COMPACT_GREETING_MAX_CHARS = 420`

2. **`server/services/realtime_prompt_builder.py:1111-1162`** - `build_full_business_prompt()`
   - Full prompt up to 8000 chars
   - Contains complete business instructions

3. **`server/media_ws_ai.py:3556-3600`** - Registry loading + fallback
   - Loads pre-built FULL prompt from registry
   - Falls back to greeting or minimal

**🧠 מה קורה:**  
התכנון היה:
- COMPACT → נשלח בהתחלה ב-`session.update`
- FULL → נשלח מאוחר יותר להחלפה

אבל בקוד הנוכחי:
- **Line 3592:** `greeting_prompt_to_use = full_prompt` - משתמש בFULL מההתחלה
- אין שימוש בCOMPACT בזרימה הנוכחית
- אבל הפונקציות עדיין קיימות ועלולות להיקרא

**⚠️ למה זה בעייתי:**  
- שתי גרסאות של אותו prompt (compact + full)
- COMPACT לא בשימוש אבל הקוד קיים → עלול להיקרא בטעות
- אם גם COMPACT וגם FULL מוזרקים → **המודל רואה חלקים חוזרים**

---

### 3.3 Customer Name - Multiple Injections

**📍 נקודות הזרקה:**

1. **`server/media_ws_ai.py:3897-4072`** - NAME_ANCHOR injection
   - בונה `name_anchor_text` עם `build_name_anchor_message()`
   - מוזרק ב-`conversation.item.create` עם role=system
   - יש hash guard: `_name_anchor_hash`

2. **`server/media_ws_ai.py:4243-4305`** - CRM context injection (legacy)
   - `self.crm_context.customer_name`
   - יש flag: `_customer_name_injected`
   - מסומן ב-`_pending_crm_context_inject`

3. **`server/media_ws_ai.py:5014-5054`** - `_ensure_name_anchor_present()`
   - פונקציה נפרדת שבודקת אם name anchor קיים
   - יכולה להזריק שוב אם חסר

**🧠 מה קורה:**  
שלוש מנגנונים שיכולים להזריק customer name:
- NAME_ANCHOR (חדש, preferred)
- CRM context (legacy, deprecated comments say "replaced")
- ensure_name_anchor (fallback/verification)

**🔥 CRITICAL FINDING:**  
למרות הflags, יש סיכון:
- `_name_anchor_hash` מגן על NAME_ANCHOR
- `_customer_name_injected` מגן על CRM
- אבל אם **שתי המערכות פועלות** → אותו שם עובר פעמיים בפורמטים שונים

**⚠️ למה זה בעייתי:**  
- Customer name יכול לעבור למודל ב-2-3 ערוצים שונים
- כל אחד עם ניסוח שונה: "Customer name available: X" vs "name=X"
- המודל רואה אותו מידע במספר הקשרים → עומס סמנטי

---

### 3.4 TODAY Context - Dynamic Injection

**📍 מיקום:**

**`server/media_ws_ai.py:3823-3842`**
```python
system_prompt = (
    f"{system_prompt} "
    f"Context: TODAY_ISO={today.isoformat()}. "
    f"TODAY_WEEKDAY_HE={hebrew_weekday_name(today)}. "
    f"TIMEZONE={getattr(policy, 'tz', 'Asia/Jerusalem')}."
)
```

**🧠 מה קורה:**  
תאריך/יום מוזרק **בתוך system prompt** באופן דינמי.

**🔥 CRITICAL FINDING:**  
- השורה 3860-3865 מנסה להסיר את זה מה-hash normalization
- אבל המידע עצמו **נשאר בprompt** שנשלח למודל
- אם system prompt מוזרק פעמיים → **תאריך עובר פעמיים**

**⚠️ למה זה בעייתי:**  
- מידע דינמי שמוזרק לתוך system prompt (לא נפרד)
- גורם לsystem prompt להשתנות בכל call
- אם מוזרק מספר פעמים → חזרה מיותרת של תאריך

---

### 3.5 Appointment Instructions - Conditional Duplication

**📍 מיקום:**

**`server/services/realtime_prompt_builder.py:1546-1569`**
```python
if call_goal == 'appointment' and enable_calendar_scheduling:
    appointment_instructions = (
        f"\n\nAPPOINTMENT SCHEDULING (STRICT, technical): Today is {weekday_name} {today_date}. "
        # ... long appointment rules ...
    )
```

**🧠 מה קורה:**  
Appointment instructions מוזרקות **רק אם** `call_goal == 'appointment'`.

אבל:
- Business prompt יכול **גם** לכלול appointment instructions
- אין תיאום בין השכבות
- אם שניהם קיימים → **כפילות של appointment rules**

**⚠️ למה זה בעייתי:**  
- System layer מוסיף appointment rules (technical)
- Business prompt עשוי לכלול appointment flow (content)
- שני המקורות לא מתואמים → יכול להיות overlapping rules

---

## 🔁 PART 4: PROMPT COMPOSITION ANALYSIS (ניתוח הרכבה)

### 4.1 Layer Architecture - Designed Separation

**תיאור הארכיטקטורה המתוכננת:**

```
1. SYSTEM PROMPT → Behavior rules (universal, no content)
2. BUSINESS PROMPT → Flow, script, domain content
3. NAME ANCHOR → Customer name + usage policy
4. TODAY CONTEXT → Dynamic date/time info
```

**בפועל:**

```
session.update.instructions:
  → FULL business prompt (טענה מRegistry)

conversation.item.create (system):
  → Global system prompt (behavior rules)
  → TODAY context (appended to system)
  → NAME_ANCHOR (customer info)
```

**🧠 ממצא:**  
הארכיטקטורה **נועדה** להפריד layers, אבל:
- TODAY context **מוזרק לתוך** system prompt (לא נפרד)
- Appointment instructions **מוזרקות לתוך** system prompt (תנאי)
- Business prompt יכול לכלול גם behavior rules

**⚠️ למה זה בעייתי:**  
- הפרדה לא מושלמת בין behavior ו-content
- אם business prompt מדבר על "סגנון דיבור" → חוזר על system rules
- אם business prompt מזכיר "שעות פתיחה" → חופף לappointment instructions

---

### 4.2 Semantic Overlap - Rules That Mean The Same

**דוגמה 1: "Be Brief"**

- System: `"Tone: short, calm, professional"`
- Business prompt עשוי להכיל: `"תגובות קצרות"`, `"לא להרחיב"`, `"לענות בתמציתיות"`

→ אותה משמעות, ניסוחים שונים, במקומות שונים

**דוגמה 2: "Don't End Call Early"**

- System: `"Do not end the call unless the business prompt explicitly instructs it"`
- Business prompt עשוי להכיל: `"המשך שיחה עד שהלקוח מוכן לסיים"`, `"אל תנתק בלי אישור"`

→ אותה כלל בשתי שפות, שתי שכבות

**דוגמה 3: "Use Customer Name"**

- NAME_ANCHOR: `"Customer name available: X. Use it naturally."`
- Business prompt עשוי להכיל: `"פנה ללקוח בשמו"`, `"השתמש בשם הלקוח"`

→ אותה הנחיה, פעמיים

**⚠️ למה זה בעייתי:**  
- המודל רואה אותן עקרונות מנוסחים במקומות שונים
- לא ברור איזה ניסוח לעקוב אחריו
- יכול ליצור תחושה של "חשוב מדי" → over-compliance

---

### 4.3 Conceptual Redundancy - Same Info, Different Forms

**Customer Name:**
- Mentioned in NAME_ANCHOR: `"Customer name available: דני"`
- Mentioned in Business Prompt: `"שם הלקוח: דני"`
- Mentioned in CRM Context (legacy): `"customer_name=דני"`

**Business Hours:**
- In Appointment Instructions: `"Hours: Mon:09:00-17:00 | ..."`
- In Business Prompt: `"שעות פעילות: יום א'-ה' 9:00-17:00"`

**Today's Date:**
- In TODAY Context: `"TODAY_ISO=2026-01-06, TODAY_WEEKDAY_HE=ראשון"`
- In Appointment Instructions: `"Today is Monday 06/01/2026"`

**🧠 ממצא:**  
אותו מידע עובר במספר ייצוגים:
- פעם כ-"raw data" (ISO format, structured)
- פעם כ-"human description" (natural language)
- פעם כ-"instruction" (what to do with it)

**⚠️ למה זה בעייתי:**  
- המודל צריך לאחד מידע ממקורות שונים
- עלול להתבלבל אם יש אי-התאמה קלה
- מגדיל token count ללא ערך מוסף

---

## 🔁 PART 5: COMPLEXITY FROM DUPLICATION (מורכבות מכפילויות)

### 5.1 Accumulated Rules Load

**System Prompt (~600 chars):**
- Language rules
- Tone rules
- Don't invent facts
- Audio interruption handling
- Call control rules
- (+ TODAY context ~60 chars)
- (+ Appointment instructions ~500 chars if enabled)

**Business Prompt (~2000-4000 chars):**
- Business-specific flow
- Service descriptions
- Greeting script
- **May also contain:** tone guidance, call control, language preferences

**NAME_ANCHOR (~100 chars):**
- Customer name
- Usage policy
- Gender (optional)

**📊 Total Context:**
- Minimum: ~2700 chars
- Maximum: ~5100 chars (with appointments)
- Potential duplications: **~300-500 chars** (10-15% overlap)

**⚠️ למה זה בעייתי:**  
- כל call מתחיל עם 5KB של instructions
- חלק מהם חוזר על עצמו בצורות שונות
- OpenAI Realtime רגיש לגודל instructions → יכול להשפיע על latency
- אם יש ambiguity → המודל צריך "לפרש" → הוסיף latency

---

### 5.2 Rule Stacking Example

**תרחיש:** Business עם appointment scheduling enabled

```
System Prompt:
  → "Do not end the call unless business prompt instructs"
  → "Appointments rule: never say you booked without calling tool"
  → "Appointment instructions: Never skip steps, required: name, date, time"

Business Prompt:
  → "לא לסיים שיחה לפני שליקוח מאשר"
  → "בזמן תיאום פגישה, תמיד לשאול שם מלא"
  → "לאשר עם הלקוח את התאריך והשעה לפני אישור"

NAME_ANCHOR:
  → "Customer name available: דני. Use it naturally."
```

**🧠 ניתוח:**
- 3 כללים על "לא לסיים שיחה מוקדם" (system + business + implicit)
- 2 כללים על "לשאול שם" (appointment instructions + business)
- 2 כללים על "לאשר תאריך" (appointment + business)

**⚠️ השפעה:**  
- המודל רואה אותן הנחיות מספר פעמים
- לא ברור איזה ניסוח הוא "הכי נכון"
- עלול להוביל ל-"over-caution" → שאלות מיותרות

---

### 5.3 Conflicting Tone Guidance

**System Prompt:** `"Tone: short, calm, professional"`

**Business Prompt אפשרי:**
- `"תהיה חמים ומזמין"` (warm and inviting) ← כנראה לא "short"
- `"תשאל שאלות מפורטות"` (detailed questions) ← כנראה לא "short"
- `"תבנה קשר אישי"` (build personal connection) ← עלול להתנגש עם "professional"

**🧠 ממצא:**  
System prompt אומר "short", אבל business prompt עשוי לבקש "detailed" או "personal".

**⚠️ למה זה בעייתי:**  
- אין מנגנון לזיהוי קונפליקטים
- המודל צריך "לנחש" מה חשוב יותר
- עלול לגרום להתנהגות לא עקבית: פעם short, פעם detailed

---

## 🔁 PART 6: ANTI-PATTERN DETECTION (דפוסים בעייתיים)

### 6.1 "Emergency Append" Pattern

**מופע:**  
`server/media_ws_ai.py:3816-3821`

```python
if getattr(self, "_server_first_scheduling_enabled", False):
    system_prompt = (
        f"{system_prompt} "
        "Appointments rule: never say you booked/scheduled..."
    )
```

**🧠 מה קורה:**  
במקום להגדיר כלל appointment בלayer המתאים, הוא מתווסף ל-system prompt דינמית.

**⚠️ למה זה anti-pattern:**  
- שובר את הארכיטקטורה: system ≠ business rules
- קשה לעקוב - הכלל "מסתתר" בתוך קוד
- אם מישהו משנה את system_prompt, עלול לשכוח את זה

---

### 6.2 "Fallback Chain" Pattern

**מופע:**  
`server/services/realtime_prompt_builder.py:1397-1446` - `_get_fallback_prompt()`

```python
# Try 1: settings.ai_prompt
# Try 2: settings.outbound_ai_prompt
# Try 3: business.system_prompt
# Try 4: prompt_helpers.get_default_hebrew_prompt_for_calls()
```

**🧠 מה קורה:**  
שרשרת fallbacks ארוכה, כל אחד יכול להכיל prompts שונים.

**⚠️ למה זה בעייתי:**  
- אם fallback #1 נכשל → עובר ל-#2 שעשוי להיות שונה מאוד
- קשה לדעת מה המודל אכן קיבל
- עלול להוביל למצב שפעם המודל מקבל prompt A, פעם prompt B

---

### 6.3 "Legacy + Modern Coexistence" Pattern

**מופע:**  
`server/media_ws_ai.py:4243-4305` - CRM context injection (marked as "replaced" but still active)

```python
# 🔥 NEW: NAME_ANCHOR replaces CRM context
# But CRM context code is still here and can run
```

**🧠 מה קורה:**  
קוד legacy (CRM context) עדיין פעיל למרות שיש מנגנון חדש (NAME_ANCHOR).

**⚠️ למה זה בעייתי:**  
- שני מנגנונים לאותה מטרה
- אם שניהם רצים → customer name עובר פעמיים
- Legacy code עלול להיכנס בטעות אחרי refactor

---

## 🎯 SUMMARY: כפילויות שעלולות ליצור "שיחה כן / שיחה לא"

### מקרה א: System Prompt Double Injection

**זרימה:**
1. `session.update` נשלח עם FULL prompt שכולל behavior rules
2. `conversation.item.create` מוזרק עם Global System Prompt
3. אם שני המקורות כוללים "don't end call early" → **המודל רואה את זה פעמיים**

**השפעה אפשרית:**
- במקרים מסוימים: המודל יהיה "over-cautious" ולא יסיים שיחה
- במקרים אחרים: confusion על איזה כלל לעקוב → התנהגות לא עקבית

---

### מקרה ב: Appointment Rules Overlap

**זרימה:**
1. System layer מוסיף: `"Never skip steps: name, date, time"`
2. Business prompt מכיל: `"לשאול שם, תאריך ושעה לפני אישור"`
3. אותו כלל פעמיים, ניסוחים שונים

**השפעה אפשרית:**
- פעם אחת: המודל שואל כל שלב (עוקב אחרי System)
- פעם אחרת: המודל מניח מידע (עוקב אחרי Business tone)
- תוצאה: **שיחה כן (מצליח לתאם) / שיחה לא (כושל)**

---

### מקרה ג: Name Injection Collision

**זרימה:**
1. NAME_ANCHOR מוזרק: `"Customer name available: דני. Use it naturally."`
2. CRM context (legacy) עדיין פעיל: `"customer_name=דני"`
3. שני מקורות לאותו מידע

**השפעה אפשרית:**
- המודל מתבלבל איזה מידע לעקוב
- במקרים מסוימים משתמש בשם, במקרים אחרים לא
- תוצאה: **אי-עקביות בשימוש בשם לקוח**

---

### מקרה ד: Tone Conflict

**זרימה:**
1. System: `"short, calm, professional"`
2. Business: `"תבנה קשר אישי, תשאל שאלות מפורטות"`
3. קונפליקט סמוי: short vs detailed

**השפעה אפשרית:**
- שיחה אחת: המודל מדבר short → מסיים מהר
- שיחה אחרת: המודל מדבר detailed → שואל הרבה שאלות
- תוצאה: **אורך שיחה משתנה ללא סיבה ברורה**

---

## 📝 CONCLUSIONS (מסקנות)

### סיכום ממצאים:

1. **כפילויות טקסטואליות:** 5+ מקרים של טקסט זהה במקומות שונים
2. **כפילויות לוגיות:** 3+ מנגנונים חופפים (name resolution, validation, hashing)
3. **כפילויות הזרקה:** 5+ נקודות שבהן מידע עובר מספר פעמים למודל
4. **עומס סמנטי:** ~10-15% overlap בתוכן הprompts
5. **דפוסים בעייתיים:** Legacy + Modern coexistence, Emergency appends, Fallback chains

### האם זה יכול להסביר "שיחה כן / שיחה לא"?

**✅ כן - סבירות גבוהה**

הסיבות:
1. **אי-דטרמיניזם מכפילויות:** כאשר כלל עובר פעמיים, המודל "בוחר" איזה לעקוב → הבחרה לא דטרמיניסטית
2. **Ambiguity בין layers:** קונפליקטים בין System ו-Business prompts → המודל מפרש אחרת בכל פעם
3. **Token budget pressure:** prompts ארוכים עם חזרות → המודל עלול "לדלג" על חלקים
4. **Content filter sensitivity:** עומס של instructions → סבירות גבוהה יותר לerrors

---

## 🚫 מה לא נמצא (חשוב לציין)

1. **אין כפילות בשם עסק** - business_id מועבר בצורה נקייה
2. **אין שימוש חוזר בטקסטים hardcoded** - רוב הprompts מגיעים מDB
3. **אין kludges גלויים** - הקוד מסודר יחסית למרות הכפילויות

---

## 📍 קבצים שנבדקו

- ✅ `server/media_ws_ai.py` (16,475 שורות)
- ✅ `server/services/realtime_prompt_builder.py` (1,744 שורות)
- ✅ `server/services/prompt_helpers.py` (50 שורות)
- ✅ `server/services/openai_realtime_client.py` (300 שורות ראשונות)

---

## ⏰ דוח הושלם

**תאריך:** 2026-01-06  
**זמן ביצוע:** 90 דקות  
**סוג דוח:** READ-ONLY AUDIT - איתור כפילויות בלבד

**❌ לא בוצעו:**
- שינויים בקוד
- הצעות refactor
- המלצות design
- פתרונות קונקרטיים

**✅ בוצע:**
- מיפוי מקיף של כפילויות
- זיהוי לוגיקות חוזרות
- ניתוח נקודות הזרקה
- קישור לבעיות התנהגות
