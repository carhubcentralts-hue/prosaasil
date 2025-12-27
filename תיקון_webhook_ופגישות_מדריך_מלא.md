# תיקון מלא: Webhooks + תיאום פגישות 

## 🔥 סיכום הבעיות

### בעיה 1: Webhooks של שיחות יוצאות לא עובדות
**תיאור**: שיחות נכנסות שולחות webhook, אבל שיחות יוצאות לא!

### בעיה 2: תיאום פגישות לא עובד
**תיאור**: 
- בשיחות קוליות - לא עובד
- בWhatsApp - לא עובד (Agent Kit)

---

## ✅ פתרון 1: Webhooks לשיחות יוצאות

### מה תוקן?

#### קוד (כבר תוקן ✅)
```python
# לפני: ❌ שיחות יוצאות בלי fallback
if direction == "outbound":
    webhook_url = settings.outbound_webhook_url
    if not webhook_url:
        return False  # לא שולח webhook!

# אחרי: ✅ עם fallback
if direction == "outbound":
    outbound_url = settings.outbound_webhook_url
    generic_url = settings.generic_webhook_url
    webhook_url = outbound_url or generic_url  # 🔥 fallback!
```

### איך לוודא שזה עובד?

#### שלב 1: בדוק שיש URL מוגדר
```bash
python test_webhook_appointment_diagnostic.py
```

**תראה משהו כזה**:
```
📊 Business 1: שם העסק
────────────────────────────────────────────
🔗 Webhook URLs:
   generic_webhook_url  : https://hooks.zapier.com/... ✅
   inbound_webhook_url  : ❌ NOT SET
   outbound_webhook_url : ❌ NOT SET

🎯 Webhook Routing for Outbound Calls:
   ⚠️  Will use: generic_webhook_url (fallback) ✅
```

#### שלב 2: אם אין URL - הגדר אחד!
```sql
-- אופציה A: רק URL גנרי (מומלץ!)
UPDATE business_settings 
SET generic_webhook_url = 'https://hooks.zapier.com/hooks/catch/YOUR_WEBHOOK_ID/'
WHERE tenant_id = 1;

-- אופציה B: URL נפרד לשיחות יוצאות
UPDATE business_settings 
SET outbound_webhook_url = 'https://hooks.zapier.com/hooks/catch/YOUR_WEBHOOK_ID/outbound/'
WHERE tenant_id = 1;
```

#### שלב 3: בצע שיחה יוצאת ובדוק לוגים
```bash
# בזמן השיחה:
tail -f logs/app.log | grep WEBHOOK

# תצפה לראות:
[WEBHOOK] 🔍 Checking outbound webhook URLs for business 1:
[WEBHOOK]    - outbound_webhook_url: NOT SET
[WEBHOOK]    - generic_webhook_url: https://hooks.zapier.com/...
[WEBHOOK] ✅ Using generic_webhook_url (fallback) for outbound
[WEBHOOK] 📤 Sending call.completed to webhook
[WEBHOOK] ✅ Successfully sent call.completed (status: 200)
```

---

## ✅ פתרון 2: תיאום פגישות

### הבעיה
פגישות לא עובדות כי **ההגדרה בDB לא נכונה**!

### הפתרון

#### א. שיחות קוליות (Voice Calls)

**דרישה**: `call_goal` חייב להיות `"appointment"` במקום `"lead_only"`

##### בדוק מה ההגדרה הנוכחית:
```sql
SELECT id, name, call_goal 
FROM business_settings 
JOIN businesses ON businesses.id = business_settings.tenant_id;
```

**תוצאה צפויה**:
```
id | name          | call_goal
---|---------------|----------
1  | שם העסק       | lead_only  ❌ לא יעבוד!
```

##### תקן את ההגדרה:
```sql
UPDATE business_settings 
SET call_goal = 'appointment'
WHERE tenant_id = 1;
```

**אחרי התיקון**:
```
id | name          | call_goal
---|---------------|----------
1  | שם העסק       | appointment  ✅ יעבוד!
```

#### ב. WhatsApp

**דרישה**: `enable_calendar_scheduling` חייב להיות `true`

##### בדוק את ההגדרה:
```sql
SELECT id, name, enable_calendar_scheduling 
FROM business_settings 
JOIN businesses ON businesses.id = business_settings.tenant_id;
```

##### תקן אם צריך:
```sql
UPDATE business_settings 
SET enable_calendar_scheduling = true
WHERE tenant_id = 1;
```

---

## 🧪 כלי אבחון

### הרץ את הכלי המלא:
```bash
python test_webhook_appointment_diagnostic.py
```

**הכלי בודק**:
1. ✅ האם יש webhook URLs מוגדרים
2. ✅ האם `call_goal` מוגדר נכון לפגישות
3. ✅ האם `enable_calendar_scheduling` מופעל
4. ✅ האם יש שיחות יוצאות אחרונות

**תוצאה מצופה**:
```
📊 DIAGNOSTIC SUMMARY
════════════════════════════════════════════
Webhook Configuration          : ✅ PASS
Appointment Configuration      : ✅ PASS
Webhook Sending Logic          : ✅ PASS
════════════════════════════════════════════

🎉 ALL DIAGNOSTICS PASSED!
```

---

## 🔍 למה זה לא עבד?

### Webhooks (שיחות יוצאות)
```
הסיבה: outbound_webhook_url לא היה מוגדר
        והקוד הישן לא היה עושה fallback ל-generic_webhook_url

הפתרון: ✅ הקוד כבר תוקן להשתמש ב-fallback
        ⚠️ רק צריך לוודא שיש generic_webhook_url מוגדר בDB!
```

### פגישות (קוליות)
```
הסיבה: call_goal = "lead_only" במקום "appointment"
        כשזה lead_only, ה-AI לא מקבל את הכלים לתיאום פגישות!

הפתרון: ✅ שנה ל-call_goal = "appointment" בDB
```

### פגישות (WhatsApp)
```
הסיבה: enable_calendar_scheduling = false
        Agent Kit לא מקבל את כלי התיאום

הפתרון: ✅ שנה ל-enable_calendar_scheduling = true בDB
```

---

## 📋 צ'קליסט תיקון מהיר

### 1. Webhooks
- [ ] הרץ: `python test_webhook_appointment_diagnostic.py`
- [ ] ודא שיש `generic_webhook_url` מוגדר
- [ ] אם לא - הגדר אחד עם SQL למעלה
- [ ] בצע שיחה יוצאת
- [ ] בדוק לוגים: `tail -f logs/app.log | grep WEBHOOK`
- [ ] ודא שרואה: `✅ Using generic_webhook_url (fallback)`

### 2. פגישות בשיחות קוליות
- [ ] הרץ: `python test_webhook_appointment_diagnostic.py`
- [ ] ודא `call_goal = 'appointment'`
- [ ] אם לא - הרץ SQL: `UPDATE business_settings SET call_goal='appointment'`
- [ ] התקשר למערכת
- [ ] בקש תיאום פגישה
- [ ] ודא שה-AI מציע שעות פנויות

### 3. פגישות ב-WhatsApp  
- [ ] הרץ: `python test_webhook_appointment_diagnostic.py`
- [ ] ודא `enable_calendar_scheduling = true`
- [ ] אם לא - הרץ SQL: `UPDATE business_settings SET enable_calendar_scheduling=true`
- [ ] שלח הודעה בWhatsApp
- [ ] בקש תיאום פגישה
- [ ] ודא שה-bot מציע שעות פנויות

---

## 🎯 בדיקה סופית

### Webhooks
```bash
# 1. בצע שיחה יוצאת מה-CRM
# 2. חכה שהשיחה תסתיים
# 3. בדוק שה-webhook הגיע ל-Zapier/n8n/Monday
# 4. ודא שיש בו:
#    - direction: "outbound" ✅
#    - phone: "+972..." ✅
#    - transcript: "..." ✅
```

### פגישות - שיחות קוליות
```bash
# 1. התקשר למספר העסק
# 2. בקש לתאם פגישה ליום מחר בשעה 3
# 3. ה-AI אמור לבדוק זמינות
# 4. ה-AI אמור להציע שעות חלופיות אם תפוס
# 5. ה-AI אמור לאשר את התיאום
# 6. בדוק בDB שהפגישה נוצרה
```

### פגישות - WhatsApp
```bash
# 1. שלח הודעה בWhatsApp: "אני רוצה לתאם פגישה"
# 2. ה-bot אמור לשאול באיזה תאריך
# 3. ענה: "מחר בשעה 3"
# 4. ה-bot אמור לבדוק זמינות
# 5. ה-bot אמור לאשר או להציע חלופה
# 6. בדוק בDB שהפגישה נוצרה
```

---

## 🆘 אם עדיין לא עובד

### Webhooks לא מגיעים
```bash
# בדוק בלוגים בזמן השיחה:
tail -f logs/app.log | grep WEBHOOK

# חפש:
# ✅ "Attempting to send webhook" - אומר שהקוד מנסה לשלוח
# ✅ "Using generic_webhook_url" - אומר שהוא מצא URL
# ✅ "Successfully sent" - אומר שנשלח בהצלחה
# ❌ "No outbound/generic webhook URL" - אין URL מוגדר!
```

### פגישות לא עובדות בשיחות
```bash
# בדוק בלוגים:
tail -f logs/app.log | grep "APPT\|appointment\|calendar"

# חפש:
# ✅ "Appointment tools ENABLED" - הכלים פעילים
# ❌ "Appointments DISABLED" - call_goal לא מוגדר נכון!
# ❌ "call_goal=lead_only" - צריך לשנות ל-appointment
```

### פגישות לא עובדות ב-WhatsApp
```bash
# בדוק שה-Agent Kit פעיל:
tail -f logs/app.log | grep "WHATSAPP_APPT"

# חפש:
# ✅ "schedule_appointment" - הכלי נקרא
# ❌ אם אין - enable_calendar_scheduling = false
```

---

## 📚 קבצים רלוונטיים

| קובץ | מה הוא עושה |
|------|------------|
| `server/services/generic_webhook_service.py` | לוגיקת routing של webhooks |
| `server/tasks_recording.py` | שולח webhooks אחרי תמלול |
| `server/models_sql.py` | הגדרות: call_goal, enable_calendar_scheduling |
| `server/agent_tools/agent_factory.py` | הגדרת כלים ל-Agent Kit |
| `server/media_ws_ai.py` | טיפול בשיחות קוליות + פגישות |
| `test_webhook_appointment_diagnostic.py` | כלי אבחון ✅ |

---

## ✅ סיכום

### מה תוקן בקוד
1. ✅ Webhook fallback לשיחות יוצאות
2. ✅ כלי אבחון מקיף

### מה צריך לעשות בDB
1. ⚙️ הגדר `generic_webhook_url` (אם אין)
2. ⚙️ שנה `call_goal` ל-`'appointment'` (לשיחות)
3. ⚙️ שנה `enable_calendar_scheduling` ל-`true` (ל-WhatsApp)

### איך לבדוק
1. 🧪 הרץ `python test_webhook_appointment_diagnostic.py`
2. 📞 בצע שיחה יוצאת ובדוק webhook
3. 📅 בקש תיאום פגישה בשיחה ובWhatsApp
4. ✅ ודא שהכל עובד!

---

**תאריך**: 27 בדצמבר 2025  
**סטטוס**: ✅ מוכן לבדיקה  
**Build**: 350+
