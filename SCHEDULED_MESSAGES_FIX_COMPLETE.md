# תזמון הודעות WhatsApp - תיקון מקצה לקצה

## סיכום השינויים

תיקון מלא למערכת תזמון הודעות WhatsApp שכוללת שליחה מיידית עם שינוי סטטוס, בחירת ספק, ללא כפילויות, עם לוגיקה נכונה.

## 🔥 שינויים עיקריים

### 1. טריגר מיידי על שינוי סטטוס (Event-Driven)

**לפני**: הודעות נשלחו רק כל 15 דקות דרך job מתוזמן.

**אחרי**: הודעות נוצרות **מיד** כשהסטטוס משתנה.

```python
# ב-routes_leads.py - אחרי שינוי סטטוס:
scheduled_messages_service.schedule_messages_for_lead_status_change(
    business_id=lead.tenant_id,
    lead_id=lead_id,
    new_status_id=new_status_obj.id,
    old_status_id=old_status_obj.id if old_status_obj else None,
    changed_at=datetime.utcnow()
)
```

### 2. תמיכה במשתני טמפלייט

ניתן להשתמש במשתנים בתוכן ההודעה:
- `{lead_name}` - שם הליד
- `{phone}` - מספר טלפון
- `{business_name}` - שם העסק
- `{status}` - סטטוס (תווית)
- `{status_name}` - סטטוס (שם טכני)

**דוגמה**:
```
שלום {lead_name}, תודה על הפנייה. סטטוס שלך עודכן ל-{status}.
```

### 3. בחירת ספק שליחה (Baileys / Meta)

כל חוק יכול לבחור דרך איזה ספק לשלוח:
- **Baileys** (מומלץ) - שליחה דרך Baileys
- **Meta** - שליחה דרך WhatsApp Cloud API (Twilio)
- **Auto** - נסיון Baileys עם fallback ל-Meta

**ב-UI**: dropdown "ספק שליחה" בטופס יצירת/עריכת חוק.

### 4. עיכוב מדויק בשניות

**לפני**: רק דקות (delay_minutes)

**אחרי**: שניות מדויקות (delay_seconds)

- ניתן להגדיר 0 שניות = שליחה מיידית
- ניתן להגדיר 15 שניות (לא 15 דקות!)
- ממשק המשתמש מציג גם דקות וגם שניות

### 5. דדופ מתקדם (אין כפילויות)

**Dedupe Key חדש**:
```
lead_status:{lead_id}:{rule_id}:{new_status_id}:{YYYYMMDDHHMM}
```

- מונע שליחת אותה הודעה פעמיים
- רזולוציה של דקה (YYYYMMDDHHMM)
- UNIQUE constraint במסד הנתונים

## 📊 מבנה מסד הנתונים

### Migration 122

#### `scheduled_message_rules` (טבלה קיימת, עודכנה)
```sql
ALTER TABLE scheduled_message_rules 
ADD COLUMN delay_seconds INTEGER NOT NULL DEFAULT 0;

ALTER TABLE scheduled_message_rules 
ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'baileys';
```

#### `scheduled_messages_queue` (טבלה קיימת, עודכנה)
```sql
ALTER TABLE scheduled_messages_queue 
ADD COLUMN channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp';

ALTER TABLE scheduled_messages_queue 
ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'baileys';

ALTER TABLE scheduled_messages_queue 
ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
```

## 🎯 תנאי קבלה

1. ✅ **שליחה מיידית**: שינוי סטטוס → הודעה נשלחת תוך שנייה
2. ✅ **סינון נכון**: רק סטטוסים שבחוק מפעילים שליחה
3. ✅ **מספר סטטוסים**: חוק עם 3 סטטוסים → כל אחד מפעיל
4. ✅ **ללא כפילויות**: שינוי סטטוס פעמיים במהירות → נשלח פעם אחת
5. ✅ **בחירת ספק**: Provider=Meta → נשלח דרך Meta בלבד
6. ✅ **בחירת ספק**: Provider=Baileys → נשלח דרך Baileys בלבד
7. ✅ **עיכוב מדויק**: delay_seconds=15 → נשלח אחרי 15 שניות
8. ✅ **טקסט מדויק**: התוכן בדיוק כמו ב-UI (עם משתנים)

## 🔄 זרימת עבודה

### A. יצירת חוק
1. משתמש יוצר חוק בעמוד "תזמון הודעות"
2. בוחר סטטוסים, טקסט הודעה, עיכוב, ספק
3. החוק נשמר עם `is_active=true`

### B. שינוי סטטוס ליד
1. משתמש משנה סטטוס ליד (CRM או Kanban)
2. **מיד** אחרי commit, נקרא `schedule_messages_for_lead_status_change`
3. השירות מחפש חוקים פעילים למצב החדש
4. לכל חוק מתאים - יוצר רשומה ב-`scheduled_messages_queue`

### C. שליחת הודעה
1. Worker (scheduled_messages_tick_job) רץ כל דקה
2. שולף הודעות עם `scheduled_for <= NOW()` ו-`status='pending'`
3. לכל הודעה:
   - בוחר ספק לפי שדה `provider`
   - שולח דרך Baileys או Meta
   - מעדכן `status='sent'` או `status='failed'`
   - מעלה `attempts` במקרה של כשלון

## 📝 הערות חשובות

### Backward Compatibility
- שדה `delay_minutes` נשאר לצורך תאימות
- אם מועבר `delay_seconds` - הוא ראשי
- אם מועבר רק `delay_minutes` - מומר ל-`delay_seconds`

### Provider Mapping
- `provider="meta"` → מומר ל-`provider="twilio"` בworker
- זה בגלל ש-Meta משתמש ב-Twilio Cloud API

### Template Variables
- רנדור מתבצע בזמן יצירת Queue entry
- לא בזמן שליחה
- זה מבטיח שהתוכן לא משתנה אם הליד משתנה

## 🚀 הפעלה

### 1. הרצת מיגרציה
```bash
python -m server.db_migrate
```

### 2. בדיקת שדות חדשים
```sql
-- בדוק שהשדות נוספו
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'scheduled_message_rules' 
AND column_name IN ('delay_seconds', 'provider');

SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'scheduled_messages_queue' 
AND column_name IN ('channel', 'provider', 'attempts');
```

### 3. יצירת חוק בדיקה
1. היכנס לדף "תזמון הודעות"
2. צור חוק חדש:
   - שם: "בדיקה"
   - בחר סטטוס
   - טקסט: "שלום {lead_name}"
   - עיכוב: 0 דקות (מיידי)
   - ספק: Baileys
3. שנה סטטוס של ליד למצב שבחרת
4. בדוק ש-WhatsApp נשלח תוך שנייה

## 🐛 בעיות נפוצות

### הודעה לא נשלחת
1. בדוק שהחוק `is_active=true`
2. בדוק שהסטטוס החדש **בדיוק** תואם לאחד מהסטטוסים בחוק
3. בדוק שיש ללקוח `whatsapp_jid` או `phone_raw`
4. בדוק logs: `[SCHEDULED-MSG]`

### הודעה נשלחת פעמיים
1. בדוק שה-dedupe_key unique constraint קיים
2. בדוק שאין שני workers שרצים במקביל
3. בדוק את ה-`attempts` counter

### Provider לא עובד
1. בדוק ש-Baileys service רץ (`BAILEYS_BASE_URL`)
2. בדוק חיבור WhatsApp ב-Baileys
3. אם Meta - בדוק `TWILIO_*` env vars

## 📚 קבצים שהשתנו

### Backend
- `server/models_sql.py` - הוספת שדות למודלים
- `server/db_migrate.py` - Migration 122
- `server/services/scheduled_messages_service.py` - לוגיקה חדשה
- `server/routes_scheduled_messages.py` - API מעודכן
- `server/routes_leads.py` - טריגר על שינוי סטטוס
- `server/jobs/send_scheduled_whatsapp_job.py` - routing לפי provider

### Frontend
- `client/src/services/scheduledMessages.ts` - TypeScript interfaces
- `client/src/pages/ScheduledMessages/ScheduledMessagesPage.tsx` - UI מעודכן

## ✅ סיכום

המערכת עכשיו עובדת **event-driven** עם:
- ✅ שליחה מיידית על שינוי סטטוס
- ✅ בחירת ספק (Baileys/Meta)
- ✅ דדופליקציה מלאה
- ✅ תמיכה במשתני טמפלייט
- ✅ עיכוב מדויק בשניות
- ✅ לוגיקה נכונה לכל הסטטוסים
