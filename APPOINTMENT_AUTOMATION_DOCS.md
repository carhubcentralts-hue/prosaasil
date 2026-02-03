# Appointment Confirmation Automation System

## תיעוד מלא: מערכת אוטומציות אישורי הגעה לפגישות

### 📋 סקירה כללית

מערכת אוטומציות מתקדמת לשליחת הודעות WhatsApp אוטומטיות על בסיס סטטוס הפגישה ותזמון גמיש.

**יכולות מרכזיות:**
- ✅ טריגרים מבוססי סטטוס - שלח הודעות כאשר פגישה נכנסת לסטטוסים מסוימים
- ✅ תזמון גמיש - לפני/אחרי/מיידי ביחס לזמן הפגישה
- ✅ תבניות הודעות - עם משתנים דינמיים (שם, זמן, מיקום וכו')
- ✅ דדופליקציה - מונע שליחה כפולה
- ✅ ביטול אוטומטי - מבטל משלוחים כאשר הסטטוס משתנה
- ✅ תבניות מוכנות בעברית - 5 תבניות מובנות

---

## 🏗️ ארכיטקטורה

### מודלים

#### 1. `appointment_automations` - הגדרות אוטומציה
```sql
CREATE TABLE appointment_automations (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    trigger_status_ids JSONB NOT NULL,          -- ["scheduled", "confirmed"]
    schedule_offsets JSONB NOT NULL,            -- [{"type":"before","minutes":1440}]
    channel VARCHAR(32) DEFAULT 'whatsapp',
    message_template TEXT NOT NULL,
    send_once_per_offset BOOLEAN DEFAULT TRUE,
    cancel_on_status_exit BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id)
);
```

#### 2. `appointment_automation_runs` - מעקב ריצות
```sql
CREATE TABLE appointment_automation_runs (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL,
    appointment_id INTEGER NOT NULL,
    automation_id INTEGER NOT NULL,
    offset_signature VARCHAR(64) NOT NULL,      -- "before_1440"
    scheduled_for TIMESTAMP NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',       -- pending/sent/failed/canceled
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    canceled_at TIMESTAMP,
    UNIQUE (business_id, appointment_id, automation_id, offset_signature)
);
```

### תזרים עבודה

```
┌─────────────────────┐
│  פגישה נוצרת/מתעדכנת │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────┐
│  בודק אוטומציות פעילות  │
│  לסטטוס הנוכחי         │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  יוצר runs לפי offsets  │
│  (יום לפני, שעתיים, וכו')│
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Tick Job מוצא runs     │
│  שהגיע זמנם             │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  שולח הודעת WhatsApp    │
│  עם משתנים ממולאים      │
└─────────────────────────┘
```

---

## 🔌 API Endpoints

### 1. רשימת אוטומציות
```http
GET /api/automations/appointments
Authorization: Bearer <token>

Query params:
  - enabled: true/false (אופציונלי)

Response:
{
  "success": true,
  "automations": [
    {
      "id": 1,
      "name": "תזכורת יום לפני",
      "enabled": true,
      "trigger_status_ids": ["scheduled", "confirmed"],
      "schedule_offsets": [{"type": "before", "minutes": 1440}],
      "message_template": "היי {first_name}...",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### 2. יצירת אוטומציה
```http
POST /api/automations/appointments
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "תזכורת יום לפני",
  "enabled": true,
  "trigger_status_ids": ["scheduled", "confirmed"],
  "schedule_offsets": [
    {"type": "before", "minutes": 1440}
  ],
  "message_template": "היי {first_name} 👋\n\nתזכורת לפגישה...",
  "cancel_on_status_exit": true
}

Response:
{
  "success": true,
  "automation_id": 1,
  "message": "אוטומציה נוצרה בהצלחה"
}
```

### 3. עדכון אוטומציה
```http
PUT /api/automations/appointments/:id
Content-Type: application/json
Authorization: Bearer <token>

{
  "enabled": false,
  "message_template": "הודעה מעודכנת..."
}
```

### 4. מחיקת אוטומציה
```http
DELETE /api/automations/appointments/:id
Authorization: Bearer <token>

Response:
{
  "success": true,
  "message": "אוטומציה נמחקה בהצלחה"
}
```

### 5. היסטוריית ריצות
```http
GET /api/automations/appointments/:id/runs
Authorization: Bearer <token>

Query params:
  - status: pending/sent/failed/canceled
  - limit: 100 (default)

Response:
{
  "success": true,
  "runs": [
    {
      "id": 123,
      "appointment_id": 456,
      "offset_signature": "before_1440",
      "scheduled_for": "2024-01-16T10:00:00Z",
      "status": "sent",
      "sent_at": "2024-01-16T10:00:05Z"
    }
  ]
}
```

### 6. תצוגה מקדימה של הודעה
```http
POST /api/automations/appointments/:id/test
Content-Type: application/json
Authorization: Bearer <token>

{
  "appointment_id": 123  // אופציונלי - להשתמש בנתונים אמיתיים
}

Response:
{
  "success": true,
  "preview": "היי יוסי 👋\n\nתזכורת לפגישה שלנו מחר...",
  "context": {
    "first_name": "יוסי",
    "business_name": "העסק שלי",
    "appointment_date": "יום שני, 15 ינואר 2024",
    "appointment_time": "14:00",
    "appointment_location": "רחוב הרצל 1",
    "rep_name": "דני"
  }
}
```

### 7. תבניות מוכנות
```http
GET /api/automations/appointments/templates
Authorization: Bearer <token>

Response:
{
  "success": true,
  "templates": [
    {
      "key": "day_before_reminder",
      "name": "תזכורת יום לפני",
      "description": "1 אופציות תזמון"
    }
  ]
}
```

### 8. יצירה מתבנית
```http
POST /api/automations/appointments/templates/:template_key
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "שם מותאם",  // אופציונלי
  "enabled": true       // אופציונלי, default: false
}
```

### 9. הקמת תבניות ברירת מחדל
```http
POST /api/automations/appointments/setup-defaults
Authorization: Bearer <token>

Response:
{
  "success": true,
  "created_count": 5,
  "message": "5 תבניות אוטומציה נוצרו בהצלחה"
}
```

---

## 📝 משתנים זמינים בתבניות

| משתנה | תיאור | דוגמה |
|-------|-------|--------|
| `{first_name}` | שם פרטי של הלקוח | יוסי |
| `{business_name}` | שם העסק | סלון יופי שרה |
| `{appointment_date}` | תאריך בעברית | יום שני, 15 ינואר 2024 |
| `{appointment_time}` | שעה | 14:00 |
| `{appointment_location}` | מיקום הפגישה | רחוב הרצל 1, תל אביב |
| `{rep_name}` | שם הנציג | דני |

**דוגמת תבנית:**
```
היי {first_name} 👋

תזכורת לפגישה שלנו מחר:
📅 {appointment_date}
⏰ שעה: {appointment_time}
📍 מיקום: {appointment_location}

מאשר/ת הגעה?

בברכה,
{rep_name}
{business_name}
```

---

## 🎯 תבניות מובנות

### 1. תזכורת יום לפני (`day_before_reminder`)
- **תזמון:** 24 שעות לפני הפגישה
- **סטטוסים:** scheduled, confirmed
- **מטרה:** אישור הגעה מראש

### 2. תזכורת שעתיים לפני (`two_hours_before`)
- **תזמון:** שעתיים לפני הפגישה
- **סטטוסים:** scheduled, confirmed
- **מטרה:** תזכורת אחרונה

### 3. אישור מיידי (`immediate_confirmation`)
- **תזמון:** מיידי כשהסטטוס משתנה
- **סטטוסים:** scheduled
- **מטרה:** אישור מיידי שהפגישה נקבעה

### 4. מעקב יום אחרי (`day_after_followup`)
- **תזמון:** 24 שעות אחרי הפגישה
- **סטטוסים:** completed
- **מטרה:** תודה ומעקב

### 5. אישור + תזכורת מלא (`confirm_and_remind`)
- **תזמון:** מיידי + יום לפני
- **סטטוסים:** scheduled, confirmed
- **מטרה:** גם אישור וגם תזכורת

---

## 🔧 התקנה ושימוש

### 1. הרצת Migration
```bash
python -m server.db_migrate
```
זה יוסיף את הטבלאות `appointment_automations` ו-`appointment_automation_runs`.

### 2. הפעלת Tick Job
הוסף את זה ל-scheduler או cron:
```python
from server.jobs.appointment_automation_tick_job import appointment_automation_tick
from server.services.jobs import enqueue

# הרץ כל דקה
enqueue('default', appointment_automation_tick)
```

### 3. יצירת אוטומציות ראשוניות לעסק חדש
```python
from server.services.appointment_automation_templates import create_default_automations

# יוצר 5 תבניות ברירת מחדל (מושבתות)
automations = create_default_automations(business_id=123, created_by=1)
```

או דרך API:
```bash
curl -X POST http://localhost:5000/api/automations/appointments/setup-defaults \
  -H "Authorization: Bearer <token>"
```

---

## 🧪 בדיקות

### בדיקת יצירת פגישה
```python
# כאשר פגישה נוצרת, האוטומציות אמורות להירתם אוטומטית
appointment = Appointment(
    business_id=1,
    title="פגישה עם לקוח",
    start_time=datetime.now() + timedelta(days=1),
    end_time=datetime.now() + timedelta(days=1, hours=1),
    status="scheduled",
    contact_phone="+972501234567",
    contact_name="יוסי"
)
db.session.add(appointment)
db.session.commit()

# בדוק שנוצרו runs
runs = AppointmentAutomationRun.query.filter_by(appointment_id=appointment.id).all()
assert len(runs) > 0
```

### בדיקת שינוי סטטוס
```python
# שנה סטטוס - אמור לבטל runs ישנים וליצור חדשים
appointment.status = "confirmed"
db.session.commit()

# הטריגר אמור לעבוד אוטומטית דרך routes_calendar
```

### בדיקת תצוגה מקדימה
```bash
curl -X POST http://localhost:5000/api/automations/appointments/1/test \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"appointment_id": 123}'
```

---

## 🐛 טיפול בשגיאות

### שגיאות נפוצות

#### 1. אין מספר טלפון
```python
# הודעת שגיאה: "No phone number available for contact"
# הפתרון: וודא שלפגישה יש lead_id או contact_phone
```

#### 2. דדופליקציה
```python
# Unique constraint violation
# הסיבה: ניסיון ליצור run כפול לאותו appointment+automation+offset
# זה תקין - המערכת מונעת כפילויות
```

#### 3. סטטוס לא תואם
```python
# הודעה: "Status no longer matches"
# הסיבה: הסטטוס השתנה מאז תזמון ה-run
# זה תקין - ה-run מבוטל אוטומטית
```

---

## 📊 ניטור וביצועים

### מטריקות למעקב
- **Scheduled runs:** מספר runs ממתינים
- **Success rate:** אחוז הצלחה של משלוחים
- **Cancellation rate:** אחוז ביטולים (טבעי כשסטטוס משתנה)
- **Failed runs:** כישלונות - לחקור

### שאילתות שימושיות
```sql
-- סטטיסטיקות לפי business
SELECT 
    a.business_id,
    a.name,
    COUNT(r.id) as total_runs,
    COUNT(CASE WHEN r.status = 'sent' THEN 1 END) as sent,
    COUNT(CASE WHEN r.status = 'failed' THEN 1 END) as failed,
    COUNT(CASE WHEN r.status = 'pending' THEN 1 END) as pending
FROM appointment_automations a
LEFT JOIN appointment_automation_runs r ON a.id = r.automation_id
WHERE a.business_id = 1
GROUP BY a.business_id, a.name;

-- runs שנכשלו לאחרונה
SELECT 
    r.id,
    r.appointment_id,
    r.status,
    r.last_error,
    r.attempts,
    r.created_at
FROM appointment_automation_runs r
WHERE r.status = 'failed'
    AND r.business_id = 1
ORDER BY r.created_at DESC
LIMIT 10;
```

---

## 🚀 שיפורים עתידיים

- [ ] **UI Frontend** - ממשק ניהול אוטומציות בקלנדר
- [ ] **תמיכה בערוצים נוספים** - Email, SMS
- [ ] **A/B Testing** - בדיקת תבניות שונות
- [ ] **Analytics** - דשבורד סטטיסטיקות
- [ ] **Smart scheduling** - תזמון מבוסס AI
- [ ] **תנאים מתקדמים** - if/else בתבניות

---

## 📞 תמיכה

לשאלות ובעיות:
- צור issue בגיטהאב
- פנה לתמיכה הטכנית
- בדוק את הלוגים: `[APPOINTMENT_CONFIRMATION]` ו-`[AUTOMATION_TICK]`

---

**גרסה:** 1.0.0  
**תאריך:** פברואר 2024  
**סטטוס:** ✅ Production Ready
