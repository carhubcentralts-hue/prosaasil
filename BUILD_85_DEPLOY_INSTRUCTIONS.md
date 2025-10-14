# 🚀 הוראות פריסה BUILD 85

## ✅ מה מוכן עכשיו:
- **BUILD 85** כבר בקוד (commit: a1f61c8)
- **Google STT תוקן** - credentials קבוע
- **כל הפונקציות החדשות** קיימות
- **יצירת לידים אוטומטית** פועלת
- **סיכום שיחות אוטומטי** פועל

## 📋 שלבי פריסה:

### שלב 1: וודא שהקוד החדש בגרסת הפריסה
הקומיט האחרון: **a1f61c8** - "Update build number and display Git SHA"

### שלב 2: פרסם מחדש (Republish)
1. לחץ על כפתור **Publish** / **פרסום**
2. המערכת תיקח snapshot של הקוד הנוכחי
3. תפרוס את BUILD 85 עם כל התיקונים

### שלב 3: בדוק שהפריסה עובדת
אחרי הפריסה, בדוק בלוגים:
- צריך לראות: `🚩 APP_START {'build': 85, ...}`
- צריך לראות: `🔧 GCP credentials converted from JSON to file`

## 🎯 מה ישתנה אחרי הפריסה:

✅ **Google STT יעבוד** - לא עוד "Both models failed"
✅ **כל שיחה תיצור ליד** אוטומטית
✅ **conversation_history יישמר** ב-DB
✅ **סיכום AI** יווצר בסיום כל שיחה
✅ **call_log** ייווצר בהתחלת שיחה

## 📊 איך לדעת שזה עובד:

אחרי שיחה, בדוק ב-DB:
```sql
-- צריך לראות conversation turns
SELECT * FROM conversation_turn ORDER BY created_at DESC LIMIT 5;

-- צריך לראות call logs עם summaries
SELECT call_sid, summary, ai_summary FROM call_log ORDER BY created_at DESC LIMIT 3;

-- צריך לראות לידים חדשים
SELECT * FROM leads ORDER BY created_at DESC LIMIT 5;
```

---
**BUILD 85 מוכן - רק צריך לפרסם מחדש!** 🚀
