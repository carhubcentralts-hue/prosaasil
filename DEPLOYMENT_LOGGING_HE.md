# 🔥 מדריך פריסה - לוגים פרודקשן (עברית)

**מטרה**: לוגים מינימליים ונקיים בפרודקשן (הפחתה של 90-95% מהתפתחות)

---

## 📋 סיכום מהיר

### הגדרות פרודקשן (לוגים מינימליים)
```bash
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

### הגדרות פיתוח (לוגים מלאים)
```bash
LOG_LEVEL=DEBUG
PYTHONUNBUFFERED=1
```

---

## 🎯 משתני סביבה (Environment Variables)

### `LOG_LEVEL` - רמת הלוגים

**פרודקשן (מומלץ)**:
```bash
LOG_LEVEL=INFO
```

זה יוריד **90-95% מהלוגים**:
- ✅ רק לוגים חיוניים: התחלה/סיום שיחה, שגיאות, אזהרות
- ✅ בלי לוגים של frame-by-frame (אודיו כל 20ms)
- ✅ בלי "TX_RESPONSE start/end" לכל תגובה
- ✅ בלי "Found 0 stale sessions" כל 5 דקות
- ✅ ספריות חיצוניות (uvicorn, sqlalchemy) מושתקות

**פיתוח**:
```bash
LOG_LEVEL=DEBUG
```
- לוגים מלאים לדיבוג
- כל frame-by-frame נראה
- כל המודולים הפנימיים

**רמות אחרות**:
- `WARNING` - רק אזהרות ושגיאות (מאוד שקט)
- `ERROR` - רק שגיאות (למציאת באגים)

### `PYTHONUNBUFFERED` - חובה!

```bash
PYTHONUNBUFFERED=1
```

חובה כדי שהלוגים יכתבו מיד (בלי buffer).

### `LOG_JSON` - אופציונלי

למערכות איסוף לוגים (Datadog, CloudWatch):

```bash
LOG_JSON=1  # JSON format
LOG_JSON=0  # Human-readable (ברירת מחדל)
```

---

## 🚀 הגדרות פריסה

### Docker Compose Production

**קובץ**: `docker-compose.prod.yml`

כל השירותים כבר מוגדרים עם `LOG_LEVEL=INFO`:

```yaml
services:
  prosaas-api:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
  
  prosaas-calls:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
  
  worker:
    environment:
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
```

### Railway / Replit / פריסה בענן

הוסף משתנים אלה לפריסה שלך:

```bash
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

---

## 📊 נפח לוגים צפוי

### לפני הניקיון

**שיחה אחת מייצרת**:
- 500-2000+ שורות לוג
- לוגים של frame-by-frame (כל 20ms)
- TX_RESPONSE start/end לכל תגובה
- "Found 0 stale sessions" כל 5 דקות

**דוגמה לספאם**:
```
[TX_RESPONSE] start response_id=resp_12345...
[AUDIO_DELTA] response_id=resp_12345, bytes=320
[AUDIO_DELTA] response_id=resp_12345, bytes=320
... (חוזר 100+ פעמים)
[TX_RESPONSE] end response_id=resp_12345
[WHATSAPP_SESSION] Check #45: Found 0 stale sessions
```

### אחרי הניקיון (פרודקשן)

**שיחה אחת מייצרת**:
- **10-30 שורות** בלבד! (הפחתה של 95%!)
- רק אירועים חשובים
- בלי frame-by-frame
- בלי "Found 0"

**דוגמה ללוגים בפרודקשן**:
```
[INFO] 🚀 [CALL_START] call_sid=CA123, business_id=456, direction=inbound
[INFO] ✅ [DB] נטען הקשר לקוח: name=דוד, phone=+972...
[INFO] 🔌 [REALTIME] התחבר ל-OpenAI ב-234ms
[INFO] 🎤 [GREETING] מנגן ברכה
[INFO] 💬 [TRANSCRIPT] לקוח: "שלום, אני רוצה לתאם פגישה"
[INFO] 🤖 [RESPONSE_CREATED] response_id=resp_123
[INFO] 📅 [TOOL_CALL] בדיקת זמינות: 2024-01-25 14:00
[INFO] ✅ [TOOL_RESULT] 3 זמנים פנויים
[INFO] 💬 [TRANSCRIPT] AI: "יש לי זמינות ב..."
[INFO] 🔚 [CALL_END] משך=45s, סיבה=customer_hangup
```

---

## 🔍 מה נשאר בפרודקשן (LOG_LEVEL=INFO)

### ✅ תמיד נרשם (INFO)

**שיחות/Realtime**:
- התחלת שיחה: `call_sid`, `business_id`, `כיוון`, `מצב`
- טעינת הקשר מ-DB
- סטטוס חיבור OpenAI וזמן תגובה
- תמלול לקוח (לפי תור, לא מילה-מילה)
- תגובת AI נוצרה/הסתיימה (סיכום)
- קריאות לכלים (פגישות וכו')
- barge-in (פעם אחת)
- סיום שיחה: משך, סיבה, מטריקות
- שגיאות (עם stacktrace מלא)

**WhatsApp**:
- שינויי סטטוס חיבור
- הודעה התקבלה (מזהה בלבד, לא תוכן)
- נמצאו sessions ישנות (רק אם > 0)
- שגיאות וניסיונות חוזרים

**Worker**:
- Worker התחיל
- Job התווסף/הסתיים/נכשל

### ❌ לא נרשם בפרודקשן (DEBUG)

**מושתק ב-LOG_LEVEL=INFO**:
- frame-by-frame אודיו
- TX_RESPONSE start/end לכל תגובה
- בדיקות watchdog
- "Found 0 stale sessions"
- חישובי RMS/volume לכל frame
- payload previews
- בדיקות גודל תור
- health check pings

---

## 🔧 פתרון בעיות

### הפעל DEBUG זמנית

אם צריך לדבג בעיה בפרודקשן:

1. **שנה משתנה סביבה**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **אתחל את השירות**:
   ```bash
   docker compose restart prosaas-calls
   ```

3. **אסוף לוגים**:
   ```bash
   docker compose logs -f prosaas-calls > debug.log
   ```

4. **אחרי הדיבוג, החזר לפרודקשן**:
   ```bash
   LOG_LEVEL=INFO
   docker compose restart prosaas-calls
   ```

---

## 📝 סיכום - העתק הדבק לפרודקשן

```bash
# ========================================
# הגדרות לוגים לפרודקשן
# ========================================
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
LOG_JSON=0
```

---

## ✅ צ'קליסט פריסה

לפני פריסה לפרודקשן:

- [ ] הגדרת `LOG_LEVEL=INFO` בסביבה
- [ ] הגדרת `PYTHONUNBUFFERED=1` בסביבה
- [ ] עדכון `docker-compose.prod.yml`
- [ ] בדיקה: שיחה אחת = 10-30 שורות בלבד
- [ ] אין "Found 0" spam
- [ ] אין frame-by-frame spam
- [ ] שגיאות עדיין נרשמות עם stacktrace מלא

---

## 🎯 התוצאה הסופית

עם ההגדרות האלה תקבל:
- **95% פחות לוגים** בפרודקשן
- **לוגים נקיים וקריאים**
- **ביצועים טובים יותר** (פחות I/O)
- **latency נמוך יותר** (פחות כתיבה)
- **עדיין מלא DEBUG** כשצריך (LOG_LEVEL=DEBUG)

---

**עודכן לאחרונה**: 21.01.2024  
**גרסה**: 1.0  
**סטטוס**: ✅ מוכן לפרודקשן
