# 🎯 מערכת CRM מתקדמת עם AI ו-WhatsApp Business

## 📋 תיאור הפרויקט

מערכת ניהול לקוחות (CRM) מתקדמת ברמה מסחרית עם יכולות בינה מלאכותית, מוקד שיחות אוטומטי, ואינטגרציה מלאה עם WhatsApp Business. המערכת מיועדת לעסקים הרוצים לשפר את שירות הלקוחות ולהגדיל את יעילות המכירות.

### ✨ תכונות עיקריות

**🤖 מוקד שיחות AI מתקדם:**
- זיהוי דיבור בעברית עם OpenAI Whisper
- עיבוד שיחות חכם עם GPT-4o
- מענה אוטומטי בעברית איכותית
- תמלול ושמירת כל השיחות

**📱 WhatsApp Business Professional:**
- אינטגרציה עם Twilio WhatsApp API
- ניהול שיחות ממוחשב
- מענה אוטומטי חכם
- מעקב סטטוס הודעות

**💼 מערכת CRM מקצועית:**
- ניהול לקוחות מתקדם
- מעקב משימות וזמנים
- אנליטיקה ודוחות
- ניהול תורים ופגישות

**🔐 אבטחה מתקדמת:**
- הרשאות מבוססות תפקידים
- הגנה על נתוני עסקים
- אימות מרובה שכבות
- ניטור פעילות

### 🚀 תכונות מסחריות מתקדמות

**✍️ חתימות דיגיטליות:**
- חתימה על מסמכים דיגיטלית
- שמירה ואימות חתימות
- אינטגרציה עם חשבוניות

**📄 מחולל חשבוניות:**
- יצירת PDF מקצועי בעברית
- שילוב חתימות דיגיטליות
- שליחה אוטומטית ב-WhatsApp

**🏷️ פילוח לקוחות חכם:**
- תיוג אוטומטי לפי התנהגות
- קטגוריות: חם, קר, VIP, לא פעיל
- סיווג והמלצות חכמות

**🌐 טפסי לידים חיצוניים:**
- טפסים מקצועיים לאתרים
- קוד הטמעה מוכן
- עיבוד אוטומטי ל-CRM

**📅 מערכת לוח שנה:**
- ניהול תורים ופגישות
- בדיקת התנגשות זמנים
- תזכורות אוטומטיות

**🔔 מערכת התראות:**
- התראות SMS ואימייל
- זיהוי לידים דחופים
- התראות לנציגים

**📊 דוחות יומיים:**
- דוחות PDF מפורטים
- שליחה אוטומטית למנהלים
- תובנות עסקיות

## 🛠️ טכנולוגיות

### Backend
- **Python 3.11+** - שפת התכנות הראשית
- **Flask** - מסגרת הפיתוח
- **SQLAlchemy** - ORM לבסיס הנתונים
- **PostgreSQL** - בסיס נתונים מקצועי

### AI & Speech
- **OpenAI GPT-4o** - מעבד השיחות החכם
- **OpenAI Whisper** - זיהוי דיבור בעברית
- **Google Cloud TTS** - הופכת טקסט לדיבור

### Communication APIs
- **Twilio** - שיחות טלפון ו-WhatsApp
- **Flask-Mail** - שליחת אימיילים
- **ReportLab** - יצירת PDF

### Frontend
- **Bootstrap 5** - עיצוב ויסטי מקצועי
- **Chart.js** - גרפים ואנליטיקה
- **FullCalendar.js** - לוח שנה אינטראקטיבי

## 📁 מבנה הפרויקט

```
project/
├── app.py                           # הגדרות Flask ובסיס נתונים
├── main.py                          # נקודת כניסה לאפליקציה
├── models.py                        # מודלי בסיס נתונים
├── routes.py                        # נתיבים עיקריים
├── auth.py                          # מערכת אימות
│
├── Enhanced Services/               # שירותים משופרים
├── enhanced_ai_service.py          # שירות AI מתקדם
├── enhanced_twilio_service.py      # שירות Twilio מקצועי
├── enhanced_whatsapp_service.py    # שירות WhatsApp מתקדם
├── enhanced_business_permissions.py # מערכת הרשאות
├── enhanced_admin_dashboard.py     # דשבורד מנהל
├── enhanced_crm_service.py         # שירות CRM מתקדם
│
├── Enterprise Services/            # שירותים מסחריים
├── digital_signature_service.py   # חתימות דיגיטליות
├── invoice_generator.py           # מחולל חשבוניות
├── customer_segmentation_service.py # פילוח לקוחות
├── lead_forms_service.py          # טפסי לידים
├── calendar_service.py            # מערכת לוח שנה
├── notification_service.py        # מערכת התראות
├── daily_reports_service.py       # דוחות יומיים
│
├── templates/                      # תבניות HTML
├── static/                         # קבצים סטטיים
├── static/signatures/              # חתימות דיגיטליות
├── static/invoices/               # חשבוניות
├── static/reports/                # דוחות
│
├── docs/                          # תיעוד
├── README.md                      # קובץ זה
├── deployment_guide.md           # מדריך פריסה
├── todo_implementation_guide.md   # מדריך יישום
└── replit.md                      # הגדרות פרויקט
```

## 🚀 התקנה מהירה

### 1. Clone הפרויקט
```bash
git clone [repository-url]
cd hebrew-ai-call-center
```

### 2. התקנת תלויות
```bash
pip install -r requirements.txt
# או עם uv:
uv add flask openai twilio sqlalchemy reportlab pillow flask-mail
```

### 3. הגדרת משתני סביבה
צור קובץ `.env` עם הפרטים הבאים:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# Twilio
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Optional Services
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-email-password
SESSION_SECRET=your-secret-key
```

### 4. הפעלת המערכת
```bash
python main.py
# או עם Gunicorn:
gunicorn --bind 0.0.0.0:5000 main:app
```

המערכת תהיה זמינה בכתובת: `http://localhost:5000`

## 👤 כניסה למערכת

### משתמש מנהל ברירת מחדל:
- **שם משתמש:** `שי`
- **סיסמה:** `admin123`
- **הרשאות:** מנהל מלא

### יצירת עסק חדש:
1. התחבר כמנהל
2. עבור ל"ניהול עסקים"
3. לחץ "הוסף עסק חדש"
4. מלא פרטים וקבל משתמש+סיסמה אוטומטית

## 📞 הגדרת Webhooks

### עבור Twilio:
1. היכנס לקונסול Twilio
2. הגדר webhook URL: `https://your-domain.com/voice/incoming`
3. הגדר WhatsApp webhook: `https://your-domain.com/webhook/whatsapp`

### בדיקת Webhooks:
```bash
curl -X POST https://your-domain.com/voice/incoming \
  -d "From=+1234567890&To=+0987654321&CallSid=test123"
```

## 🔧 תכונות מתקדמות

### 1. API Endpoints

**לקוחות:**
- `GET /api/customers` - רשימת לקוחות
- `POST /api/customers` - יצירת לקוח חדש
- `PUT /api/customers/<id>` - עדכון לקוח
- `DELETE /api/customers/<id>` - מחיקת לקוח

**משימות:**
- `GET /api/tasks` - רשימת משימות
- `POST /api/tasks` - יצירת משימה חדשה
- `PUT /api/tasks/<id>` - עדכון משימה

**פגישות:**
- `GET /api/appointments` - רשימת פגישות
- `POST /api/appointments` - קביעת פגישה חדשה

### 2. טפסי לידים חיצוניים

```html
<!-- הטמעת טופס באתר -->
<iframe src="https://your-domain.com/lead_form/123/uuid" 
        width="100%" 
        height="600" 
        frameborder="0">
</iframe>
```

### 3. חתימות דיגיטליות

```javascript
// JavaScript לחתימה
const signaturePad = new SignaturePad(canvas);
const signature = signaturePad.toDataURL();

// שליחה לשרת
fetch('/api/save_signature', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        customer_id: 123,
        signature: signature
    })
});
```

## 📊 ניטור ואנליטיקה

### Dashboard מנהל:
- סטטיסטיקות שיחות בזמן אמת
- ביצועי נציגים
- המרת לידים
- זמני מענה ממוצעים

### דוחות אוטומטיים:
- דוח יומי (19:00)
- דוח שבועי
- דוח חודשי
- ייצוא ל-CSV/PDF

### מדדי ביצוע:
- **זמן מענה:** < 30 שניות
- **שיעור המרה:** > 15%
- **שביעות רצון:** > 90%
- **זמינות מערכת:** > 99.5%

## 🛡️ אבטחה

### הגנות יישומיות:
- **Rate Limiting:** 3 ניסיונות כניסה לדקה
- **Session Timeout:** 30 דקות חוסר פעילות
- **CSRF Protection:** הגנה על טפסים
- **XSS Prevention:** ניקוי קלטים

### הגנת נתונים:
- הצפנת סיסמאות bcrypt
- הפרדת נתוני עסקים
- גיבוי אוטומטי
- לוגים מפורטים

## 🔧 פתרון בעיות נפוצות

### 1. שיחות לא עובדות:
```bash
# בדיקת Webhook
curl -X POST https://your-domain.com/voice/incoming \
  -d "From=+1234567890&To=+0987654321"

# בדיקת OpenAI
python -c "import openai; print('OpenAI OK')"
```

### 2. WhatsApp לא עובד:
```bash
# בדיקת Twilio WhatsApp
curl -X POST https://your-domain.com/webhook/whatsapp \
  -d "From=whatsapp:+1234567890&Body=test"
```

### 3. בסיס נתונים:
```bash
# בדיקת חיבור
python -c "from app import db; print('DB OK')"

# יצירת טבלאות
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 4. התראות לא נשלחות:
```bash
# בדיקת SMTP
python -c "from notification_service import notification_service; print('Mail OK')"
```

## 📈 שדרוגים עתידיים

### Phase 1 - AI מתקדם:
- [ ] זיהוי רגשות בשיחות
- [ ] תחזיות מכירות
- [ ] המלצות פעולה אוטומטיות

### Phase 2 - אינטגרציות:
- [ ] Google Calendar sync
- [ ] Zapier webhooks
- [ ] Slack notifications

### Phase 3 - BI מתקדם:
- [ ] Machine Learning predictions
- [ ] Advanced analytics dashboard
- [ ] Customer lifetime value

## 🤝 תמיכה

### דרכי יצירת קשר:
- **Email:** support@company.com
- **Slack:** #ai-call-center
- **Documentation:** https://docs.company.com

### Issues ו-Feature Requests:
- פתח Issue ב-GitHub
- תאר את הבעיה בפירוט
- צרף לוגים רלוונטיים

## 📄 רישיון

MIT License - ראה קובץ LICENSE לפרטים מלאים.

## 🏆 Contributors

- **שי** - מפתח ראשי
- **Agent** - AI Assistant
- **Replit** - פלטפורמת פיתוח

---

**מערכת זו פותחה בגאווה עם טכנולוגיות מתקדמות לשוק הישראלי 🇮🇱**

*עדכון אחרון: יולי 2025*