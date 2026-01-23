# WhatsApp Prompt-Only Mode & Lead Name Tracking - Implementation Summary

## תיעוד מלא: פרומפטים לווואטסאפ + שמירת שם לקוח

### סקירה כללית

יישום מלא של שני דרישות עיקריות:
1. **מצב Prompt-Only לווואטסאפ** - ניהול פרומפט AI מהמסד נתונים בלי קוד קשיח
2. **שמירת שם אוטומטית** - שמירה חכמה של שמות לקוחות מווואטסאפ ושיחות טלפון

---

## חלק 1: WhatsApp Prompt-Only Mode

### שדות חדשים בטבלת `business`

```sql
-- פרומפט ייעודי לווואטסאפ
whatsapp_system_prompt TEXT

-- הגדרות AI לווואטסאפ
whatsapp_temperature FLOAT DEFAULT 0.0
whatsapp_model VARCHAR(50) DEFAULT 'gpt-4o-mini'
whatsapp_max_tokens INTEGER DEFAULT 350
```

### עדיפויות טעינת פרומפט (לפי סדר)

#### לווואטסאפ (channel='whatsapp'):
1. **Priority 1**: `business.whatsapp_system_prompt` (אם קיים)
   - טוען גם: `whatsapp_temperature`, `whatsapp_model`, `whatsapp_max_tokens`
   - לוג: `"✅ Loaded WhatsApp prompt from DB: business_id=X chars=Y model=... temp=..."`

2. **Priority 2**: `business_settings.ai_prompt` עם מפתח 'whatsapp'
   - תומך בפורמט JSON: `{"calls": "...", "whatsapp": "..."}`

3. **Priority 3**: `business.system_prompt` (fallback)
   - לוג: `"⚠️ Using fallback business.system_prompt for WhatsApp"`

4. **Priority 4**: פרומפט ברירת מחדל מינימלי
   - לוג: `"❌ ERROR: No WhatsApp prompt configured - using minimal fallback"`

#### לשיחות טלפון (channel='calls'):
השתמש בלוגיקה הקיימת עם `business_settings.ai_prompt`

### לוגים חדשים

```python
# בטעינת פרומפט מהDB
logger.info(f"✅ Loaded WhatsApp prompt from DB: business_id={business_id} chars={len(system_prompt)} model={model} temp={temperature}")

# אם אין פרומפט מוגדר
logger.error(f"❌ ERROR: No WhatsApp prompt configured for business {business_id} - using minimal fallback")
```

### קבצים ששונו
- `server/models_sql.py` - הוספת שדות לטבלת Business
- `server/services/ai_service.py` - לוגיקת טעינת פרומפט חדשה
- `migration_add_whatsapp_prompt_and_lead_name.py` - מיגרציה

---

## חלק 2: שמירת שם לקוח

### שדות חדשים בטבלת `leads`

```sql
-- שם מאוחד מכל המקורות
name VARCHAR(255)

-- מקור השם: 'whatsapp' | 'call' | 'manual'
name_source VARCHAR(32)

-- מתי השם עודכן לאחרונה
name_updated_at TIMESTAMP
```

### מנגנון Upsert חכם

#### כללי החלטה:
1. **לעולם לא לדרוס שם ידני** (`name_source='manual'`)
2. שמות ארוכים יותר בדרך כלל טובים יותר (יותר מידע)
3. כל שם אמיתי עדיף על placeholder (`"ליד חדש"`, `"Unknown"` וכו')

#### שמות שנדחים:
```python
INVALID_NAMES = {
    'unknown', 'whatsapp', 'user', 'customer', 'guest', 
    'לקוח', 'משתמש', 'null', 'none', 'n/a', 'na', 
    'test', 'בדיקה'
}
```

#### ניקוי שם:
```python
def normalize_name(name: str) -> str:
    # 1. Strip whitespace
    # 2. Remove duplicate spaces
    # 3. Limit to 80 chars
    # 4. Reject phone numbers
    # 5. Reject invalid placeholders
    # 6. Must have at least 2 characters
```

### זרימת עבודה - WhatsApp

1. **חילוץ pushName** מההודעה הנכנסת:
```python
push_name = msg.get('pushName', '')
if push_name and push_name.lower() not in ['unknown', '']:
    log.debug(f"[WA-INCOMING] Extracted pushName: {push_name}")
```

2. **העברה ל-CustomerIntelligence**:
```python
customer, lead, was_created = ci_service.find_or_create_customer_from_whatsapp(
    phone_number=phone_or_id,
    message_text=message_text,
    whatsapp_jid=remote_jid,
    whatsapp_jid_alt=remote_jid_alt,
    phone_raw=phone_raw,
    push_name=push_name  # 🆕 פרמטר חדש
)
```

3. **בדיקה ועדכון**:
```python
if push_name:
    normalized_name = normalize_name(push_name)
    
    if normalized_name:
        should_update = is_name_better(
            new_name=normalized_name,
            old_name=lead.name or "",
            new_source='whatsapp',
            old_source=lead.name_source or ""
        )
        
        if should_update:
            lead.name = normalized_name
            lead.name_source = 'whatsapp'
            lead.name_updated_at = datetime.utcnow()
```

### זרימת עבודה - שיחות טלפון

1. **קבלת caller_name** (אם זמין מ-Twilio):
```python
customer, lead, was_created = ci_service.find_or_create_customer_from_call(
    phone_number=clean_phone,
    call_sid=call_sid,
    transcription=transcription,
    conversation_data=conversation_data,
    caller_name=caller_name  # 🆕 פרמטר חדש
)
```

2. **לוגיקת עדכון זהה לווואטסאפ**

### לוגים חדשים

#### הצלחה:
```
lead_upsert: phone=+972501234567 source=whatsapp pushName="עדנה registered nurse" applied=true reason=name_improved
```

#### נדחה - שם קיים טוב יותר:
```
lead_upsert: phone=+972501234567 source=whatsapp pushName="עדנה" applied=false reason=existing_name_better old_name="עדנה כהן" old_source=manual
```

#### נדחה - שם לא תקין:
```
lead_upsert: phone=+972501234567 source=whatsapp pushName="0501234567" applied=false reason=invalid_name
```

### קבצים חדשים/ששונו
- `server/models_sql.py` - שדות חדשים בטבלת Lead + עדכון `full_name` property
- `server/utils/name_utils.py` - 🆕 כלי ניקוי ואימות שמות
- `server/services/customer_intelligence.py` - לוגיקת upsert לווואטסאפ ושיחות
- `server/routes_whatsapp.py` - חילוץ והעברת pushName
- `migration_add_whatsapp_prompt_and_lead_name.py` - מיגרציה

---

## מיגרציה

### הרצה:
```bash
python -m server.db_migrate
```

**חשוב**: המיגרציה מתווספת דרך `server/db_migrate.py` בלבד (Migration 96).
לא להוסיף מיגרציות כקבצים נפרדים!

### מה קורה:
1. הוספת 4 עמודות לטבלת `business`
2. הוספת 3 עמודות לטבלת `leads`
3. מיגרציה אוטומטית של שמות קיימים:
   - `leads.name` = `first_name + ' ' + last_name` (אם קיימים)
   - `leads.name_source` = `'manual'`
   - `leads.name_updated_at` = `updated_at`

---

## בדיקות

### 1. בדיקת פרומפט WhatsApp

```python
# הגדרה ב-UI או DB:
UPDATE business 
SET whatsapp_system_prompt = 'אתה העוזר הדיגיטלי של העסק...',
    whatsapp_temperature = 0.7,
    whatsapp_model = 'gpt-4o',
    whatsapp_max_tokens = 500
WHERE id = 1;

# בדוק לוג:
# ✅ Loaded WhatsApp prompt from DB: business_id=1 chars=250 model=gpt-4o temp=0.7
```

### 2. בדיקת שמירת שם - WhatsApp

```python
# שלח הודעה עם pushName="יוסי כהן"
# בדוק לוג:
# lead_upsert: phone=+972501234567 source=whatsapp pushName="יוסי כהן" applied=true reason=name_improved

# בדוק DB:
SELECT name, name_source, name_updated_at 
FROM leads 
WHERE phone_e164 = '+972501234567';
# name: יוסי כהן
# name_source: whatsapp
# name_updated_at: 2026-01-23 10:30:00
```

### 3. בדיקת אי-דריסת שם ידני

```python
# עדכן ידנית:
UPDATE leads 
SET name = 'יוסף כהן (VIP)', 
    name_source = 'manual' 
WHERE phone_e164 = '+972501234567';

# שלח הודעה עם pushName="יוסי"
# בדוק לוג:
# lead_upsert: phone=+972501234567 source=whatsapp pushName="יוסי" applied=false reason=existing_name_better old_name="יוסף כהן (VIP)" old_source=manual

# בדוק DB - השם לא השתנה:
SELECT name FROM leads WHERE phone_e164 = '+972501234567';
# name: יוסף כהן (VIP)
```

---

## Acceptance Criteria ✅

### חלק 1: פרומפטים
- [x] שינוי `whatsapp_system_prompt` ב-DB משפיע מיד על תשובות WhatsApp
- [x] אין prompt hardcoded בקוד (חוץ מ-fallback קצר)
- [x] לוג: `"Loaded WhatsApp prompt from DB: business_id=... chars=... model=..."`
- [x] תמיכה רב-דיירים (כל business עם prompt משלו)

### חלק 2: שמירת שמות
- [x] כל הודעת WA ראשונה מלקוח חדש יוצרת ליד עם שם מה-pushName (אם קיים)
- [x] ליד קיים בלי שם → מתעדכן אוטומטית
- [x] ליד עם שם ידני (`name_source='manual'`) → לא נדרס
- [x] לוג מפורט: `"lead_upsert: phone=... source=... pushName=... applied=true/false reason=..."`
- [x] אותה לוגיקה גם לשיחות טלפון

---

## מגבלות ידועות

1. **Caller ID מ-Twilio**: תלוי באם Twilio מספק caller name בשיחה נכנסת
2. **Migration מחייב downtime קצר**: הרצת המיגרציה דורשת downtime של ~1-2 שניות
3. **שמות מהשיחה עצמה**: אם הלקוח אמר "שמי X" בשיחה - זה לא נתפס אוטומטית (צריך transcript analysis)

---

## עבודה עתידית אפשרית

1. **UI לעריכת פרומפטים**: ממשק לעריכת `whatsapp_system_prompt` מהUI
2. **חילוץ שם מtranscript**: זיהוי "שמי X" בתוך השיחה
3. **Sync עם CRM חיצוני**: סנכרון שמות עם Salesforce/HubSpot
4. **Name quality score**: ניקוד איכות לשמות (כדי לבחור מי עדיף)

---

## תמיכה

בעיות? בדוק את:
1. **לוגים** - חפש `"lead_upsert:"` או `"Loaded WhatsApp prompt"`
2. **DB Schema** - וודא שהמיגרציה רצה: `\d business` ו-`\d leads`
3. **Permissions** - וודא שהשדות החדשים זמינים ב-SQLAlchemy models

## מחבר
Implementation by GitHub Copilot Agent
Date: 2026-01-23
