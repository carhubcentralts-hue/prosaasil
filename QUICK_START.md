# 🚀 Quick Start - Fix Webhooks and Appointments

## עברית | Hebrew

### 📋 מה לעשות עכשיו (3 פעולות פשוטות):

#### 1️⃣ הרץ את כלי האבחון
```bash
python test_webhook_appointment_diagnostic.py
```

הכלי יבדוק אוטומטית את כל ההגדרות ויגיד לך בדיוק מה צריך לתקן.

#### 2️⃣ תקן את ההגדרות במסד הנתונים

הכלי יראה לך בדיוק מה חסר. הנה הפקודות המהירות:

```sql
-- אם webhook לא עובד:
UPDATE business_settings 
SET generic_webhook_url = 'https://your-webhook-url.com'
WHERE tenant_id = 1;

-- אם פגישות לא עובדות בשיחות:
UPDATE business_settings 
SET call_goal = 'appointment'
WHERE tenant_id = 1;

-- אם פגישות לא עובדות בWhatsApp:
UPDATE business_settings 
SET enable_calendar_scheduling = true
WHERE tenant_id = 1;
```

**החלף `tenant_id = 1` במספר העסק שלך!**

#### 3️⃣ בדוק שהכל עובד

**Webhooks**:
- עשה שיחה יוצאת מה-CRM
- בדוק שה-webhook הגיע ל-Zapier/n8n/Monday
- אם לא - בדוק לוגים: `tail -f logs/app.log | grep WEBHOOK`

**פגישות בשיחות**:
- התקשר למספר העסק
- בקש לתאם פגישה
- ודא שה-AI מציע שעות ומתאם

**פגישות ב-WhatsApp**:
- שלח הודעה: "אני רוצה לתאם פגישה"
- ודא שהבוט מציע שעות ומתאם

---

## English

### �� What to Do Now (3 Simple Steps):

#### 1️⃣ Run the Diagnostic Tool
```bash
python test_webhook_appointment_diagnostic.py
```

The tool will automatically check all settings and tell you exactly what needs to be fixed.

#### 2️⃣ Fix Database Settings

The tool will show you exactly what's missing. Here are the quick commands:

```sql
-- If webhooks don't work:
UPDATE business_settings 
SET generic_webhook_url = 'https://your-webhook-url.com'
WHERE tenant_id = 1;

-- If appointments don't work in voice calls:
UPDATE business_settings 
SET call_goal = 'appointment'
WHERE tenant_id = 1;

-- If appointments don't work in WhatsApp:
UPDATE business_settings 
SET enable_calendar_scheduling = true
WHERE tenant_id = 1;
```

**Replace `tenant_id = 1` with your business ID!**

#### 3️⃣ Test Everything Works

**Webhooks**:
- Make an outbound call from CRM
- Check webhook arrives at Zapier/n8n/Monday
- If not - check logs: `tail -f logs/app.log | grep WEBHOOK`

**Voice Appointments**:
- Call the business number
- Request to schedule appointment
- Verify AI suggests times and books

**WhatsApp Appointments**:
- Send message: "I want to schedule an appointment"
- Verify bot suggests times and books

---

## ❓ Still Not Working?

### Check Logs
```bash
# Webhooks
tail -f logs/app.log | grep WEBHOOK

# Appointments
tail -f logs/app.log | grep "APPT\|appointment"
```

### Common Issues

**"No webhook URL configured"**
→ Run the diagnostic tool, it will tell you which URL to set

**"Appointments DISABLED"**
→ `call_goal` is not set to 'appointment' - run the SQL above

**"Tool not found" in WhatsApp**
→ `enable_calendar_scheduling` is false - run the SQL above

---

## 📚 More Details?

Read the complete documentation:
- 🇮🇱 **Hebrew**: `תיקון_webhook_ופגישות_מדריך_מלא.md`
- 🇬�� **English**: `WEBHOOK_APPOINTMENT_FIX_SUMMARY.md`

---

**That's it! Simple as 1-2-3!** 🎉
