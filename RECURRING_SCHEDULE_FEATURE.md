# תזמון הודעות חוזר - Recurring Scheduled Messages

## 🎯 סקירה כללית

פיצ'ר חדש שמאפשר לשלוח הודעות WhatsApp בימים ושעות ספציפיים באופן חוזר, בנוסף לתזמון הקיים לפי שינוי סטטוס.

## ✨ יכולות

### תזמון לפי שינוי סטטוס (קיים)
- הודעות נשלחות כאשר ליד נכנס לסטטוס מסוים
- אפשרות לעיכוב (delay) לפני השליחה
- תמיכה בשלבים מרובים (multi-step)

### תזמון חוזר (חדש!)
- **ימים ספציפיים**: בחירת ימי השבוע (ראשון-שבת)
- **שעות ספציפיות**: הגדרת שעות מדויקות (למשל: 09:00, 15:00)
- **סטטוסים**: בחירת סטטוסים שעבורם תישלח ההודעה
- **אוטומטי**: המערכת שולחת הודעות לכל הלידים בסטטוסים אלו בזמנים שנקבעו

## 📊 דוגמה לשימוש

**תרחיש**: שליחת תזכורת שבועית ללקוחות פוטנציאליים

```
- סוג תזמון: תזמון חוזר
- ימים: ראשון, רביעי
- שעות: 10:00, 16:00
- סטטוסים: "ליד חם", "ממתין להחלטה"
- הודעה: "שלום {lead_name}, רציתי לבדוק אם יש לך שאלות נוספות?"
```

**תוצאה**: כל יום ראשון ורביעי בשעות 10:00 ו-16:00, כל הלידים בסטטוסים "ליד חם" ו"ממתין להחלטה" יקבלו את ההודעה.

## 🔧 שינויים טכניים

### Database (Migration 136)
```sql
ALTER TABLE scheduled_message_rules 
ADD COLUMN schedule_type VARCHAR(32) NOT NULL DEFAULT 'STATUS_CHANGE';

ALTER TABLE scheduled_message_rules 
ADD COLUMN recurring_times JSON NULL;
```

- `schedule_type`: "STATUS_CHANGE" או "RECURRING_TIME"
- `recurring_times`: מערך של שעות בפורמט "HH:MM" (למשל: `["09:00", "15:00"]`)

### Backend Changes
1. **scheduled_messages_service.py**
   - עדכון `create_rule()` - תמיכה בפרמטרים החדשים
   - עדכון `update_rule()` - תמיכה בפרמטרים החדשים
   - תיקון ולידציה לאפשר delay=0

2. **routes_scheduled_messages.py**
   - עדכון API endpoints
   - ולידציה של פורמט זמן (HH:MM)
   - תמיכה ב-schedule_type ו-recurring_times

3. **recurring_scheduled_messages_job.py** (חדש!)
   - Job שרץ כל שעה בדקה 00
   - בודק כללים עם schedule_type="RECURRING_TIME"
   - יוצר הודעות עבור לידים בסטטוסים המתאימים

4. **scheduler/run_scheduler.py**
   - רישום ה-job החדש לרוץ כל שעה

### Frontend Changes
1. **scheduledMessages.ts**
   - עדכון TypeScript interfaces
   - תמיכה בשדות החדשים

2. **ScheduledMessagesPage.tsx**
   - בוחר סוג תזמון (radio buttons)
   - UI לבחירת ימים (buttons)
   - UI לבחירת שעות (time inputs)
   - ולידציה מותאמת לכל סוג תזמון

## 🔄 Flow

### תזמון חוזר
1. משתמש יוצר חוק עם `schedule_type="RECURRING_TIME"`
2. בוחר ימים: `active_weekdays=[0, 3]` (ראשון ורביעי)
3. בוחר שעות: `recurring_times=["10:00", "16:00"]`
4. בוחר סטטוסים
5. כותב הודעה

**כל שעה (:00):**
1. `recurring_scheduled_messages_job` מתעורר
2. בודק את השעה והיום הנוכחיים
3. מוצא כללים מתאימים
4. מחפש לידים בסטטוסים הרלוונטיים
5. יוצר הודעות ב-`scheduled_messages_queue`
6. `scheduled_messages_tick_job` (רץ כל דקה) שולח את ההודעות

## 🐛 תיקון באג

תוקן באג בולידציה שגרם לשגיאה `delay_minutes must be between 1 and 43200` בעת עריכת חוק:

- **לפני**: delay_minutes היה חובה להיות ≥1 תמיד
- **אחרי**: 
  - תזמון חוזר: delay=0 (לא רלוונטי)
  - שליחה מיידית: delay=0 מותר
  - תזמון רגיל: delay≥1 נדרש

## 📝 Variables זמינים בהודעות

- `{lead_name}`: שם הליד
- `{phone}`: טלפון
- `{business_name}`: שם העסק
- `{status}`: הסטטוס הנוכחי

## ⚙️ הגדרות

### Scheduler
- Job רץ כל שעה בדקה 00
- Timeout: 5 דקות
- TTL: 1 שעה

### Deduplication
כדי למנוע שליחת כפילויות אם ה-job רץ יותר מפעם אחת, יש מנגנון deduplication:
- `dedupe_key` כולל את התאריך
- בודק אם כבר נוצרה הודעה היום עבור הליד+חוק

## 🧪 בדיקות

### Manual Testing Checklist
- [ ] יצירת חוק חדש עם תזמון חוזר
- [ ] בחירת ימים ושעות
- [ ] שמירת החוק בהצלחה
- [ ] וידוא שהחוק מופיע ברשימה עם האינדיקטורים הנכונים
- [ ] עריכת חוק קיים בלי שגיאות
- [ ] וידוא ש-job רץ בשעות הנכונות
- [ ] וידוא שהודעות נשלחות ללידים הנכונים

### Screenshots Needed
1. UI של בחירת סוג תזמון
2. UI של הגדרת תזמון חוזר (ימים + שעות)
3. רשימת חוקים עם חוק חוזר
4. תור ההודעות עם הודעות מתזמון חוזר

## 🚀 Deployment

1. Pull השינויים
2. המיגרציה תרוץ אוטומטית בעליית השרת
3. Scheduler יטען את ה-job החדש אוטומטית
4. הפיצ'ר זמין לשימוש!

## 📞 Support

בעיות או שאלות? פנה למפתח.
