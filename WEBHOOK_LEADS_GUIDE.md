# Webhook Lead Ingestion - מדריך שימוש

## סקירה כללית

מערכת Webhook Lead Ingestion מאפשרת לקבל לידים אוטומטית ממקורות חיצוניים כמו Make.com, Zapier, טפסים מותאמים אישית ועוד.

## תכונות עיקריות

- **עד 3 webhooks לעסק** - כל webhook יכול לייצר לידים בסטטוס שונה
- **אימות מאובטח** - כל webhook מגיע עם secret ייחודי
- **מניעת כפילויות** - אם ליד עם אותו טלפון או אימייל קיים, הוא מתעדכן במקום ליצור כפילות
- **שמירת נתונים גולמיים** - ה-payload המקורי נשמר ל-debugging
- **מיפוי חכם** - המערכת מזהה אוטומטית שדות נפוצים (name, phone, email, city, notes)

## איך להתחיל

### שלב 1: יצירת Webhook

1. היכנס להגדרות → Integrations
2. גלול למטה ל-"Webhooks ללידים"
3. לחץ על "צור Webhook"
4. מלא:
   - **שם תיאורי** - לדוגמה "מקור Make 1" או "טופס Facebook"
   - **סטטוס יעד** - בחר את הסטטוס שהלידים ייווצרו בו
5. לחץ "צור"

### שלב 2: קבלת פרטי ה-Webhook

לאחר יצירת ה-Webhook תקבל:

- **Webhook URL** - כתובת ייחודית לקבלת לידים
  ```
  https://yourdomain.com/api/webhook/leads/123
  ```

- **Secret** - מפתח אבטחה ייחודי
  ```
  wh_abc123...
  ```

### שלב 3: הגדרה ב-Make.com

1. צור HTTP Request module
2. הגדר:
   - **Method**: POST
   - **URL**: העתק את ה-Webhook URL
   - **Headers**:
     ```
     X-Webhook-Secret: [העתק את ה-Secret]
     Content-Type: application/json
     ```
   - **Body**: JSON עם פרטי הליד

#### דוגמה ל-Body (JSON):

```json
{
  "name": "ישראל ישראלי",
  "phone": "0501234567",
  "email": "israel@example.com",
  "city": "תל אביב",
  "message": "מעוניין בשירות X",
  "source": "טופס אתר"
}
```

### שלב 4: הגדרה ב-Zapier

1. צור Webhooks action → POST
2. **URL**: העתק את ה-Webhook URL
3. **Payload Type**: JSON
4. **Headers**:
   ```
   X-Webhook-Secret: [העתק את ה-Secret]
   ```
5. **Data**: מפה את השדות מה-Trigger שלך

## שדות נתמכים

המערכת מחפשת את השדות הבאים (case-insensitive):

| קטגוריה | שמות שדה אפשריים |
|----------|-------------------|
| **שם** | name, full_name, fullname, first_name+last_name |
| **טלפון** | phone, mobile, tel, telephone, phone_number |
| **אימייל** | email, email_address, emailaddress |
| **עיר** | city, location |
| **הערות** | message, notes, description, comment, details |
| **מקור** | source, lead_source, origin |

### דרישות מינימום

לפחות אחד מהשדות הבאים **חייב** להיות:
- `phone` (טלפון)
- `email` (אימייל)

אם לא מסופק אף אחד מהם, הבקשה תיכשל עם שגיאה 400.

## תגובות (Responses)

### הצלחה - ליד חדש (201)
```json
{
  "ok": true,
  "lead_id": 456,
  "updated": false
}
```

### הצלחה - עדכון ליד קיים (200)
```json
{
  "ok": true,
  "lead_id": 123,
  "updated": true
}
```

### שגיאות

| קוד | תיאור | דוגמה |
|-----|-------|-------|
| 400 | חסר phone או email | `{"ok": false, "error": "missing_contact_identifier", "expected_one_of": ["phone", "email"]}` |
| 401 | Secret שגוי או חסר | `{"ok": false, "error": "invalid_secret"}` |
| 404 | Webhook לא קיים או כבוי | `{"ok": false, "error": "webhook_not_found"}` |
| 500 | שגיאת שרת | `{"ok": false, "error": "internal_server_error"}` |

## מניעת כפילויות

המערכת מונעת יצירת לידים כפולים:

1. **חיפוש לפי טלפון** (עדיפות ראשונה)
   - אם יש ליד עם אותו מספר טלפון באותו עסק → עדכון
   
2. **חיפוש לפי אימייל** (עדיפות שנייה)
   - אם אין התאמת טלפון, מחפש לפי אימייל → עדכון

3. **ליד חדש**
   - אם אין התאמה → יצירת ליד חדש

### מה קורה בעדכון?

- שדות ריקים בליד הקיים **מתעדכנים** עם ערכים חדשים
- שדות שכבר מלאים **לא משתנים**
- הערה חדשה מתווספת לנושטס הקיימות

## ניהול Webhooks

### הפעלה/השבתה

לחץ על אייקון ה-Power כדי להפעיל/להשבית webhook.
כאשר webhook כבוי, בקשות אליו יחזירו 404.

### שינוי סטטוס יעד

1. לחץ "שנה" ליד שדה הסטטוס
2. בחר סטטוס חדש מהרשימה
3. הליד הבא שיתקבל ייווצר בסטטוס החדש

### החלפת Secret

1. לחץ על אייקון ה-Refresh
2. אשר את ההחלפה
3. **חשוב**: עדכן את ה-Secret החדש במקור החיצוני (Make/Zapier)

### מחיקת Webhook

1. לחץ על אייקון הפח
2. אשר מחיקה
3. **שים לב**: פעולה זו בלתי הפיכה

## דוגמאות שימוש

### דוגמה 1: 3 webhooks למקורות שונים

```
Webhook 1: "מקור Make" → סטטוס "חדש"
Webhook 2: "טופס Facebook" → סטטוס "ממתין להצעת מחיר"
Webhook 3: "טופס אתר" → סטטוס "חם"
```

### דוגמה 2: שילוב עם Make.com

```
Trigger: Google Forms Response
↓
HTTP Request: POST to Webhook URL
  Headers: X-Webhook-Secret
  Body: {name, phone, email, ...}
↓
Lead created in CRM automatically
```

### דוגמה 3: cURL לבדיקה

```bash
curl -X POST https://yourdomain.com/api/webhook/leads/123 \
  -H "X-Webhook-Secret: wh_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ישראל כהן",
    "phone": "0501234567",
    "email": "test@example.com"
  }'
```

## טיפים והמלצות

1. **תן שמות ברורים** - כדי לזהות בקלות מאיפה הליד הגיע
2. **השתמש בשדה source** - כדי לעקוב אחר מקור הליד
3. **בדוק את raw_payload** - אם יש בעיה, ה-payload המקורי שמור בליד
4. **החלף Secret באופן קבוע** - לאבטחה מקסימלית
5. **השתמש בסטטוסים שונים** - כדי להפריד בין מקורות מידע

## פתרון בעיות

### הבקשה נכשלת עם 401

- ודא שה-Header `X-Webhook-Secret` מוגדר נכון
- ודא שהעתקת את ה-Secret המלא (ללא רווחים)

### לידים לא נוצרים

1. בדוק שה-Webhook פעיל (אייקון ירוק)
2. ודא שיש לפחות `phone` או `email` ב-payload
3. בדוק שה-URL נכון
4. בדוק לוגים של Make/Zapier לשגיאות

### לידים כפולים נוצרים

- ודא שהטלפון בפורמט אחיד (עם או בלי +972)
- ודא שה-webhook שולח באמת אותו מספר פעמיים

## אבטחה

- כל webhook מאובטח עם secret ייחודי
- Secret מועבר ב-header (לא ב-URL)
- שגיאות לא חושפות מידע רגיש
- רק users מורשים יכולים ליצור/לערוך webhooks
- ה-endpoint הציבורי בודק רק secret (לא authentication מלא)

## מגבלות

- **מקסימום 3 webhooks** לעסק
- Payload חייב להיות JSON תקני
- גודל מקסימלי של payload: 1MB (הגבלת Flask)
- Rate limiting: כפי שמוגדר בשרת

## תמיכה

צריך עזרה? צור קשר עם התמיכה שלנו או בדוק את הדוקומנטציה המלאה.
