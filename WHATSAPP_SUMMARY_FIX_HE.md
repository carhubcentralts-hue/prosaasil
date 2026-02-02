# תיקון סיכומי WhatsApp - BUILD 170.2

## 🎯 הבעיה המקורית
1. **סיכומים לא נוצרים** - משתמש דיווח שלא מקבל סיכומי שיחה
2. **זמן אי-פעילות ארוך מדי** - 15 דקות זה יותר מדי, צריך 5 דקות
3. **צריך סיכום לכל שיחה** - גם לשיחות קצרות

## ✅ מה תוקן

### 1. שינוי זמן אי-פעילות: 15 דקות → 5 דקות

**קובץ**: `server/services/whatsapp_session_service.py`
```python
# לפני:
INACTIVITY_MINUTES = 15

# אחרי:
INACTIVITY_MINUTES = 5  # 🔥 FIX: Changed from 15 to 5 minutes for faster summaries
```

**השפעה**: עכשיו סיכום נוצר **5 דקות** אחרי ההודעה האחרונה מהלקוח (לא 15!)

---

### 2. שיפור יצירת סיכומים - גם לשיחות קצרות

**קובץ**: `server/services/whatsapp_session_service.py` → `generate_session_summary()`

#### לפני (דרישה מחמירה מדי):
```python
if not messages or len(messages) < 2:
    logger.info(f"[WA-SESSION] Not enough messages for summary")
    return None
```

#### אחרי (דרישה גמישה):
```python
# 🔥 FIX: Require at least 1 message (was 2, too strict!)
if not messages or len(messages) < 1:
    logger.info(f"[WA-SESSION] No messages for summary")
    return None

# Count customer messages to ensure there's actual conversation
customer_messages = [m for m in messages if m["direction"] == "in"]
if not customer_messages:
    logger.info(f"[WA-SESSION] No customer messages for summary")
    return None
```

**מה השתנה?**
- דרישה: **1 הודעה מהלקוח** (לא 2 הודעות סה"כ)
- **גם שיחה של הודעה אחת** מקבלת סיכום
- הבדיקה היא על **הודעות מהלקוח** (לא סך הכל הודעות)

---

### 3. שיפור ה-prompt לסיכום חכם יותר

**קובץ**: `server/services/whatsapp_session_service.py` → `generate_session_summary()`

#### הוספנו:
```python
# 🔥 ADD: Include conversation length context for AI
msg_count = len(messages)
customer_count = len(customer_messages)
context_note = f"\n\n(שיחה: {msg_count} הודעות, {customer_count} מהלקוח)\n"
```

#### שיפרנו את ההנחיות ל-AI:
```python
כללים:
- כתוב רק מה שנאמר בפועל
- אם השיחה קצרה/לא הגיעה לסיכום - ציין זאת בקצרה
- 1-4 משפטים מספיקים (תלוי באורך השיחה)
- גם שיחה של הודעה אחת צריכה סיכום (למשל: "לקוח שאל על X, טרם נענה")
```

---

### 4. לוגינג מפורט יותר

**קובץ**: `server/services/whatsapp_session_service.py` → `process_stale_sessions()`

הוספנו מונים מפורטים:
```python
processed = 0      # סיכומים שנוצרו בהצלחה
failed = 0         # שגיאות
no_summary = 0     # לא היה מספיק תוכן לסיכום
```

ולוג מפורט בסוף:
```python
logger.info(f"[WA-SESSION] ✅ Completed: {processed} with summary, {no_summary} without summary, {failed} failed (total {len(stale)})")
```

---

### 5. עדכון טקסטים בממשק משתמש

**קבצים**:
- `client/src/pages/Leads/LeadDetailPage.tsx`
- `client/src/pages/wa/WhatsAppPage.tsx`

**לפני**: "סיכום נוצר אוטומטית אחרי 15 דקות..."

**אחרי**: "סיכום נוצר אוטומטית אחרי 5 דקות..."

---

## 📊 איך זה עובד עכשיו?

### תהליך יצירת סיכום:

1. **הודעה נכנסת** → `update_session_activity()` מעדכן `last_customer_message_at`
2. **Scheduler רץ כל 5 דקות** → `whatsapp_sessions_cleanup_job()`
3. **מוצא sessions שעברו 5 דקות** → `get_stale_sessions()`
4. **יוצר סיכום AI** → `generate_session_summary()`
   - דורש: לפחות **1 הודעה מלקוח**
   - יוצר סיכום גם לשיחות קצרות
5. **שומר סיכום** → `close_session()` + עדכון `Lead.last_summary`

### Timeline דוגמה:

```
10:00:00 - לקוח שולח הודעה: "שלום, אני רוצה לשמוע על מחיר"
10:00:05 - בוט עונה: "היי! בטח, אשמח לספר..."
10:01:30 - לקוח: "תודה, אשמור את הפרטים"
         └─ last_customer_message_at = 10:01:30
         
10:05:00 - Scheduler רץ (tick #1) → Session עדיין פעיל (לא עברו 5 דקות)
10:06:30 - ✅ עברו 5 דקות מ-10:01:30!
10:10:00 - Scheduler רץ (tick #2) → מוצא session stale
         └─ generate_session_summary() → "לקוח שאל על מחירים. קיבל מידע. אמר ששומר את הפרטים."
         └─ close_session() + עדכון Lead.last_summary
```

---

## 🔍 איך לבדוק שזה עובד?

### 1. בדוק שה-scheduler רץ
```bash
# חפש בלוגים:
grep "WA-SESSION" logs/*.log | grep "Found.*stale"
```

תראה:
```
[WA-SESSION] 📱 Found 3 stale sessions to process
[WA-SESSION] Processing session 142 (customer=97250123...)
[WA-SESSION] ✅ Generated summary for session 142: לקוח שאל על...
```

### 2. בדוק sessions במאגר
```sql
-- כמה sessions פתוחות?
SELECT COUNT(*) FROM whatsapp_conversation WHERE is_open = true;

-- כמה sessions עם סיכום?
SELECT COUNT(*) FROM whatsapp_conversation WHERE summary IS NOT NULL;

-- sessions אחרונות עם סיכום
SELECT 
    id,
    customer_wa_id,
    summary,
    last_customer_message_at,
    summary_created
FROM whatsapp_conversation 
WHERE summary IS NOT NULL 
ORDER BY updated_at DESC 
LIMIT 5;
```

### 3. בדוק בממשק
1. עבור ל- **ליד עם שיחת WhatsApp**
2. טאב **"WhatsApp"** או **"שיחות"**
3. צריך לראות:
   - **"סיכום שיחה אחרון"**
   - טקסט הסיכום
   - תאריך ושעה

---

## ⚠️ בעיות אפשריות ופתרונות

### בעיה: לא רואה סיכומים בכלל

**אבחון**:
```bash
# 1. בדוק שה-scheduler רץ
grep "whatsapp_sessions_cleanup" logs/*.log

# 2. בדוק שה-job מריץ בפועל
grep "WA-SESSION.*Found.*stale" logs/*.log
```

**פתרונות**:
- וודא ש-scheduler service רץ (`SERVICE_ROLE=scheduler`)
- בדוק שאין שגיאות בלוגים
- בדוק שיש `OPENAI_API_KEY` ב-environment

---

### בעיה: סיכום מופיע רק אחרי זמן רב

**אבחון**:
```python
# בדוק את הערך בקוד
from server.services.whatsapp_session_service import INACTIVITY_MINUTES
print(f"INACTIVITY_MINUTES = {INACTIVITY_MINUTES}")  # צריך להיות 5
```

**פתרון**: עשה deploy מחדש של הקוד

---

### בעיה: sessions לא נסגרות

**אבחון**:
```sql
-- כמה sessions פתוחות מעל 10 דקות?
SELECT COUNT(*) 
FROM whatsapp_conversation 
WHERE is_open = true 
  AND last_customer_message_at < NOW() - INTERVAL '10 minutes';
```

**פתרון**: רץ ידנית:
```python
from server.services.whatsapp_session_service import process_stale_sessions
process_stale_sessions()
```

---

## 📝 סיכום השינויים

| #   | שינוי                      | קובץ                                | השפעה                                     |
| --- | -------------------------- | ----------------------------------- | ----------------------------------------- |
| 1   | INACTIVITY_MINUTES: 15→5   | whatsapp_session_service.py         | סיכום מהיר יותר (5 דקות במקום 15)        |
| 2   | דרישה: 2→1 הודעות          | whatsapp_session_service.py         | סיכום גם לשיחות קצרות                    |
| 3   | בדיקה על הודעות לקוח       | whatsapp_session_service.py         | סיכום רק אם הלקוח כתב משהו                |
| 4   | שיפור prompt               | whatsapp_session_service.py         | AI מבין שיחות קצרות טוב יותר             |
| 5   | לוגינג מפורט               | whatsapp_session_service.py         | קל יותר לאתר בעיות                        |
| 6   | טקסט ממשק: 15→5 דקות      | LeadDetailPage.tsx, WhatsAppPage.tsx | משתמש רואה זמן נכון                       |
| 7   | עדכון תיאורים ב-jobs       | whatsapp_session_job.py + cleanup   | תיעוד נכון                                |

---

## ✅ אישור שהכל עובד

רץ את הפקודות הבאות:

```bash
# 1. בדוק שהקוד השתנה
grep "INACTIVITY_MINUTES = 5" server/services/whatsapp_session_service.py

# 2. בדוק sessions אחרונות
psql $DATABASE_URL -c "SELECT id, summary, last_customer_message_at FROM whatsapp_conversation WHERE summary IS NOT NULL ORDER BY updated_at DESC LIMIT 3;"

# 3. בדוק logs (אחרי deploy)
docker logs prosaasil-backend-1 2>&1 | grep "WA-SESSION" | tail -20
```

---

## 🚀 Deploy

```bash
# Frontend + Backend
git add .
git commit -m "FIX: WhatsApp summary - 5min timeout + support short conversations"
git push

# Production
./scripts/deploy_production.sh
```

---

**מסמך זה נוצר**: 2026-02-03  
**תיקון**: WhatsApp Summary - BUILD 170.2
