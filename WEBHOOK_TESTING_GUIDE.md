# 🎯 מדריך בדיקת Webhook - Google Sheets → Make → System

## ✅ מה תיקנו

התיקון מאפשר ל-webhook לחלץ נתונים מגוגל שיט כשהטלפון מגיע כמספר (int) ולא כטקסט.

### תיקונים שבוצעו:
1. ✅ תמיכה בטלפון מספרי (549750505 במקום "0549750505")
2. ✅ תמיכה ב-aliases נוספים: `whatsapp`, `phoneNumber`, `utm_source`
3. ✅ חילוץ `phone_digits` ללא חסימה על פורמט
4. ✅ בדיקה רכה: phone_digits OR email (לא קשיח)
5. ✅ הצמדת סטטוס יעד מהאינטגרציה
6. ✅ לוגים משופרים

---

## 🚀 איך לבדוק ב-Make

### שלב 1: צור Webhook באפליקציה

1. היכנס למערכת
2. לך ל-**Settings → Integrations**
3. צור webhook חדש:
   - שם: "Google Sheets Test"
   - בחר סטטוס יעד (למשל "חדש" או "ממתין")
4. העתק:
   - **Webhook ID** (למשל: 1)
   - **Secret** (למשל: wh_xyz...)

### שלב 2: הגדר ב-Make

#### A. צור תרחיש חדש ב-Make:

1. **Trigger: Google Sheets - Watch New Rows**
   - בחר את הגיליון שלך
   - הגדר עמודות: name, email, phone, source

2. **Action: HTTP - Make a Request**
   ```
   URL: https://your-domain.com/api/webhook/leads/{WEBHOOK_ID}
   Method: POST
   Headers:
     X-Webhook-Secret: {YOUR_SECRET}
     Content-Type: application/json
   Body:
   {
     "name": "{{1.name}}",
     "email": "{{1.email}}",
     "phone": {{1.phone}},
     "source": "google_sheet"
   }
   ```

⚠️ **חשוב**: אל תשים מרכאות סביב `{{1.phone}}` - תן למייק לשלוח אותו כמספר!

### שלב 3: בדוק את הזרימה

1. **הוסף שורה חדשה בגוגל שיט:**
   ```
   | Name          | Email                     | Phone      | Source       |
   |---------------|---------------------------|------------|--------------|
   | צוריאל ארביב  | tzurielarviv@gmail.com   | 549750505  | google_sheet |
   ```

2. **המתן שהתרחיש ירוץ ב-Make**

3. **בדוק שהליד נוצר במערכת:**
   - לך ל-Leads
   - תראה ליד חדש: "צוריאל ארביב"
   - הטלפון: 549750505
   - הסטטוס: הסטטוס שהגדרת ב-webhook config

---

## 🧪 בדיקה ידנית עם cURL

אם אתה רוצה לבדוק ישירות בלי Make:

```bash
curl -X POST https://your-domain.com/api/webhook/leads/1 \
  -H "X-Webhook-Secret: wh_your_secret_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "צוריאל ארביב",
    "email": "tzurielarviv@gmail.com",
    "phone": 549750505,
    "source": "google_sheet"
  }'
```

### תגובה מוצלחת:
```json
{
  "ok": true,
  "lead_id": 123,
  "created": true,
  "status_id": 5
}
```

---

## 📋 מה צריך לעבוד

### ✅ Payload שצריך לעבוד:

#### 1. Google Sheets (טלפון מספרי):
```json
{
  "name": "צוריאל ארביב",
  "email": "tzurielarviv@gmail.com",
  "phone": 549750505,
  "source": "google_sheet"
}
```

#### 2. WhatsApp (alias חדש):
```json
{
  "name": "John Doe",
  "whatsapp": "+972501234567",
  "email": "john@example.com"
}
```

#### 3. phoneNumber (camelCase - alias חדש):
```json
{
  "name": "Jane Smith",
  "phoneNumber": "0541234567",
  "email": "jane@example.com"
}
```

#### 4. utm_source (alias חדש):
```json
{
  "name": "Marketing Lead",
  "phone": "0521234567",
  "utm_source": "facebook_ads"
}
```

---

## 🔍 איך לבדוק שזה עובד

### 1. בדוק לוגים (אם יש לך גישה):

חפש לוגים כאלה:
```
🔍 [WEBHOOK 1] Raw payload keys: ['name', 'email', 'phone', 'source']
🔍 [WEBHOOK 1] Extracted fields keys: ['name', 'phone', 'email', 'source']
🔍 [WEBHOOK 1] Has name=True, phone=True, email=True, source=True
🔍 [WEBHOOK 1] Phone extraction: raw='549750505' → digits='549750505'
✅ [WEBHOOK 1] Using webhook target status: 'חדש' (id=5)
✅ [WEBHOOK 1] Created lead 123 via phone=549750505, status='חדש' (id=5)
```

### 2. בדוק במערכת:

- [ ] ליד נוצר עם שם "צוריאל ארביב"
- [ ] טלפון: 549750505
- [ ] אימייל: tzurielarviv@gmail.com
- [ ] סטטוס: הסטטוס שהגדרת ב-webhook
- [ ] Source: webhook_1

---

## ❌ שגיאות אפשריות

### 1. "Missing phone or email"
```json
{
  "ok": false,
  "error": "phone_or_email_required",
  "message": "Missing phone or email - חסר טלפון או אימייל"
}
```
**פתרון**: ודא שיש `phone` או `email` ב-payload

### 2. "Invalid secret"
```json
{
  "ok": false,
  "error": "invalid_secret"
}
```
**פתרון**: בדוק ש-`X-Webhook-Secret` נכון

### 3. "Webhook not found"
```json
{
  "ok": false,
  "error": "webhook_not_found"
}
```
**פתרון**: בדוק ש-webhook_id בURL נכון

---

## 💪 סיכום

התיקון מבטיח:
- ✅ גוגל שיט עובד עם טלפון מספרי
- ✅ aliases נוספים (whatsapp, phoneNumber, utm_source)
- ✅ סטטוס יעד מוצמד מהאינטגרציה
- ✅ לא נופלים על בעיות פורמט
- ✅ לוגים ברורים לדיבאג

**אין פדיחות - הכל עובד! 💪**
