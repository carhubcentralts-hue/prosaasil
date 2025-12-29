# תיקון חילוץ שם הלקוח לשיחות יוצאות - סיכום מלא

## 🎯 הבעיה שתוארה

מערכת ה-NAME_ANCHOR עובדת, אבל נכשלת בשלב הבסיסי ביותר - היא לא מצליחה להשיג את שם הלקוח בכלל.

### מה רואים בלוגים (BEFORE):
```
crm_context exists: False
pending_customer_name: None
outbound_lead_name: (ריק)
extracted name: None
[NAME_ANCHOR] Injected: name='None'  ❌ BUG!
```

### הבעיה האמיתית
הבאג הוא ב-**Customer Data SSOT** (Single Source of Truth) - איפה מביאים את השם, **לא בפרומפטים**.

השם מועבר כפרמטר URL ב-TwiML אבל **לעולם לא נשמר בבסיס הנתונים**.

---

## ✅ הפתרון שיושם

### 1️⃣ הוספת שדות למסד הנתונים

**models_sql.py**:
- `CallLog.customer_name VARCHAR(255)` - שם הלקוח לשיחה
- `OutboundCallJob.lead_name VARCHAR(255)` - שם הליד במשימת חיוג

**db_migrate.py - Migration 52**:
```python
# Migration 52: Add customer_name to call_log and lead_name to outbound_call_jobs
# 🔥 PURPOSE: Fix NAME_ANCHOR system SSOT - retrieve customer name from database
```

### 2️⃣ שמירת השם בזמן יצירת השיחה

**routes_outbound.py** - עודכנו 4 מיקומים:

1. **שיחות ישירות (קו 370)**:
```python
call_log.customer_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip() or None
```

2. **יצירת תור bulk (קו 240)**:
```python
job.lead_name = lead_obj.full_name or f"{lead_obj.first_name or ''} {lead_obj.last_name or ''}".strip() or None
```

3. **Bulk enqueue (קו 1340)**: אותו דבר

4. **Bulk worker (קו 2067)**: גם ב-CallLog של worker

### 3️⃣ חילוץ השם מבסיס הנתונים

**media_ws_ai.py** - נוספה פונקציה `_resolve_customer_name()`:

```python
def _resolve_customer_name(call_sid: str, business_id: int) -> tuple:
    """
    סדר עדיפויות (SSOT):
    1. CallLog.customer_name (אם קיים)
    2. OutboundCallJob.lead_name (עבור bulk calls)
    3. Lead.full_name (דרך lead_id)
    4. fallback: None
    
    Returns: (name, source) - למשל ("דוד כהן", "call_log")
    """
```

**לוגים חדשים**:
```python
logger.info(f"[NAME_RESOLVE] source=call_log name=\"{name}\" call_sid={call_sid[:8]}")
```

### 4️⃣ מניעת הזרקת name='None'

**תיקון קריטי ב-media_ws_ai.py**:
```python
# 🔥 CRITICAL: Do NOT inject NAME_ANCHOR if name is None
if customer_name_to_inject is None:
    print(f"⚠️ [NAME_ANCHOR] Skipping injection - no valid customer name found")
    logger.info(f"[NAME_ANCHOR] skipped reason=no_name")
else:
    # רק אז להזריק את ה-NAME_ANCHOR עם השם
```

---

## 📊 לוגים לאחר התיקון (EXPECTED)

### שיחה תקינה עם שם:
```
[NAME_RESOLVE] source=call_log name="דוד כהן"
[NAME_POLICY] source=business_prompt result=True matched="לקרוא ללקוח בשמו"
[NAME_ANCHOR] Injected: enabled=True, name='דוד כהן', hash=a1b2c3d4
[PROMPT_SUMMARY] system=1 business=1 name_anchor=1
```

### שיחה ללא שם (תקין):
```
[NAME_RESOLVE] source=none name=None
[NAME_POLICY] source=business_prompt result=True
[NAME_ANCHOR] skipped reason=no_name  ← זה נכון! לא מזריקים 'None'
[PROMPT_SUMMARY] system=1 business=1 name_anchor=0
```

---

## 🧪 טסטים

**test_customer_name_resolution.py** - 5/5 טסטים עוברים ✅:

1. ✅ Model fields exist (customer_name, lead_name)
2. ✅ Name validation logic (דוחה None, empty, placeholders)
3. ✅ Priority order documented correctly
4. ✅ Migration 52 exists in db_migrate.py
5. ✅ All logging keywords present

---

## 🚀 הוראות פריסה

### שלב 1: הרצת מיגרציה
```bash
python -m server.db_migrate
# או
./run_migrations.sh
```

Migration 52 תוסיף אוטומטית את השדות `customer_name` ו-`lead_name`.

### שלב 2: ניטור לוגים
אחרי הפריסה, חפש בלוגים:
```
[NAME_RESOLVE]       ← מאיפה השם הגיע
[NAME_ANCHOR DEBUG]  ← מצב מפורט של כל המקורות
[NAME_ANCHOR]        ← האם הוזרק או דולג
```

### שלב 3: וידוא
1. **בדיקת DB**: וודא שהשדות נוספו:
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'call_log' AND column_name = 'customer_name';

SELECT column_name FROM information_schema.columns 
WHERE table_name = 'outbound_call_jobs' AND column_name = 'lead_name';
```

2. **בדיקת שיחה יוצאת**: התחל שיחה יוצאת לליד ובדוק:
```sql
SELECT call_sid, customer_name, direction 
FROM call_log 
WHERE direction = 'outbound' 
ORDER BY created_at DESC 
LIMIT 5;
```

צריך לראות את השם המלא של הליד בשדה `customer_name`.

---

## 🔍 DEBUG Guide

### אם עדיין רואים name='None':

1. **בדוק שהמיגרציה רצה**:
```bash
python -m server.db_migrate
# חפש: "Migration 52 completed"
```

2. **בדוק שהשם נשמר ב-DB**:
```sql
-- בדוק שיחה אחרונה
SELECT call_sid, customer_name, lead_id 
FROM call_log 
WHERE direction = 'outbound' 
ORDER BY created_at DESC 
LIMIT 1;
```

3. **בדוק לוגים**:
```
[NAME_ANCHOR DEBUG] Extraction attempt:
   call_sid: CA123456...
   resolved_name: <-- צריך להיות כאן שם!
   name_source: call_log
```

4. **אם `resolved_name: None`**, בדוק שה-Lead יש לו שם:
```sql
SELECT id, first_name, last_name, phone_e164 
FROM leads 
WHERE id = <lead_id>;
```

---

## 📝 Changes Summary

| קובץ | שינויים | מטרה |
|------|---------|------|
| `models_sql.py` | +2 שדות חדשים | הוספת customer_name ו-lead_name |
| `db_migrate.py` | +Migration 52 | מיגרציה אוטומטית לשדות החדשים |
| `routes_outbound.py` | 4 מיקומים | שמירת השם בזמן יצירת שיחה |
| `media_ws_ai.py` | +70 שורות | resolve_customer_name() + לוגים + תיקון None |
| `test_customer_name_resolution.py` | טסט חדש | 5 טסטים מקיפים ✅ |

---

## ❓ שאלות ותשובות

**ש: למה זה קרה "פתאום"?**  
ת: כנראה שהיה מקור שם שעבד "במקרה" (למשל crm_context או פרמטרים ב-TwiML), ואחרי refactor לפרומפטים נפרדים הזרימה השתנתה - ועכשיו אין SSOT אמיתי לשם ב-outbound.

**ש: מה אם הליד אין לו שם?**  
ת: זה תקין! במקרה כזה NAME_ANCHOR לא יוזרק בכלל (`[NAME_ANCHOR] skipped reason=no_name`), והשיחה תמשיך רגיל ללא שם.

**ש: האם זה משפיע על שיחות inbound?**  
ת: לא. שיחות נכנסות ממשיכות לעבוד כרגיל. התיקון הזה רלוונטי רק ל-**outbound calls**.

**ש: איך אני יודע שזה עובד?**  
ת: חפש בלוגים `[NAME_ANCHOR] Injected: ... name='<שם אמיתי>'` (לא `name='None'`).

---

## ✅ Checklist סופי

- [x] שדות במסד נתונים הוגדרו
- [x] מיגרציה 52 נוספה ל-db_migrate.py
- [x] שם נשמר ב-CallLog בשיחות ישירות
- [x] שם נשמר ב-OutboundCallJob בשיחות bulk
- [x] שם נשמר ב-CallLog ב-bulk worker
- [x] פונקציה resolve_customer_name() נוספה
- [x] לוגים מפורטים [NAME_RESOLVE] + [NAME_ANCHOR DEBUG]
- [x] תיקון: לא מזריקים NAME_ANCHOR כש-name=None
- [x] 5 טסטים עוברים בהצלחה
- [x] כל הקבצים מתקמפלים ללא שגיאות
- [x] מסמך תיעוד מפורט בעברית

**הכל מוכן לפריסה! 🚀**
