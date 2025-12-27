# תיקון מערכת Webhooks - שיחות נכנסות ויוצאות

## תקציר הבעיה (Problem Summary)
**בעברית**: הwebhook של שיחות יוצאות לא עובד! רק של השיחות הנכנסות עובד.

**English**: Outgoing call webhooks were not working! Only incoming call webhooks were working.

---

## הבעיה שזוהתה (Root Cause)

### התנהגות לפני התיקון
```python
# ❌ BEFORE: Outbound webhooks had NO fallback
if direction == "outbound":
    webhook_url = settings.outbound_webhook_url
    if not webhook_url:
        return False  # ❌ NO webhook sent!
```

**הבעיה**: כאשר `outbound_webhook_url` לא היה מוגדר, המערכת **לא שלחה webhook בכלל** לשיחות יוצאות.

**The Problem**: When `outbound_webhook_url` was not configured, the system **did not send any webhook** for outbound calls.

### השוואה: שיחות נכנסות vs יוצאות

| סוג שיחה | URL ראשי | Fallback | תוצאה לפני התיקון |
|---------|----------|----------|-------------------|
| נכנסת (Inbound) | `inbound_webhook_url` | `generic_webhook_url` | ✅ עובד |
| יוצאת (Outbound) | `outbound_webhook_url` | ❌ **אין fallback** | ❌ לא עובד |

---

## הפתרון שיושם (Solution Implemented)

### התנהגות אחרי התיקון
```python
# ✅ AFTER: Outbound webhooks now have fallback
if direction == "outbound":
    outbound_url = settings.outbound_webhook_url
    generic_url = settings.generic_webhook_url
    
    webhook_url = outbound_url or generic_url  # ✅ Fallback to generic!
    
    if outbound_url:
        print("✅ Using outbound_webhook_url")
    else:
        print("✅ Using generic_webhook_url (fallback)")
```

### השוואה אחרי התיקון

| סוג שיחה | URL ראשי | Fallback | תוצאה אחרי התיקון |
|---------|----------|----------|-------------------|
| נכנסת (Inbound) | `inbound_webhook_url` | `generic_webhook_url` | ✅ עובד |
| יוצאת (Outbound) | `outbound_webhook_url` | `generic_webhook_url` | ✅ עובד! |

---

## לוגיקת Webhook אחרי התיקון (Webhook Routing Logic)

### 1️⃣ שיחות נכנסות (Inbound Calls)
```
inbound_webhook_url קיים? 
  ✅ כן → שלח ל-inbound_webhook_url
  ❌ לא → generic_webhook_url קיים?
           ✅ כן → שלח ל-generic_webhook_url (fallback)
           ❌ לא → לא שולח webhook
```

### 2️⃣ שיחות יוצאות (Outbound Calls) - 🔥 חדש!
```
outbound_webhook_url קיים?
  ✅ כן → שלח ל-outbound_webhook_url
  ❌ לא → generic_webhook_url קיים?
           ✅ כן → שלח ל-generic_webhook_url (fallback) 🔥 חדש!
           ❌ לא → לא שולח webhook
```

### 3️⃣ אירועים אחרים (Other Events)
- Lead created
- Appointment booked
→ תמיד משתמשים ב-`generic_webhook_url`

### 4️⃣ שינויי סטטוס (Status Changes)
→ משתמשים ב-`status_webhook_url` (מערכת נפרדת)

### 5️⃣ WhatsApp
→ משתמשים ב-n8n integration (מערכת נפרדת)

---

## תרחישי שימוש (Use Cases)

### תרחיש 1: רק URL גנרי מוגדר (Most Common!)
```yaml
Configuration:
  generic_webhook_url: "https://my-webhook.com/events"
  inbound_webhook_url: null
  outbound_webhook_url: null

Result:
  ✅ Inbound calls  → Send to generic_webhook_url
  ✅ Outbound calls → Send to generic_webhook_url (🔥 NOW WORKS!)
  ✅ Other events   → Send to generic_webhook_url
```

### תרחיש 2: URLs נפרדים לכל כיוון
```yaml
Configuration:
  generic_webhook_url: "https://my-webhook.com/events"
  inbound_webhook_url: "https://my-webhook.com/inbound"
  outbound_webhook_url: "https://my-webhook.com/outbound"

Result:
  ✅ Inbound calls  → Send to inbound_webhook_url
  ✅ Outbound calls → Send to outbound_webhook_url
  ✅ Other events   → Send to generic_webhook_url
```

### תרחיש 3: רק URL נכנס מוגדר
```yaml
Configuration:
  generic_webhook_url: "https://my-webhook.com/events"
  inbound_webhook_url: "https://my-webhook.com/inbound"
  outbound_webhook_url: null

Result:
  ✅ Inbound calls  → Send to inbound_webhook_url
  ✅ Outbound calls → Send to generic_webhook_url (🔥 NOW WORKS!)
  ✅ Other events   → Send to generic_webhook_url
```

---

## שינויים בקוד (Code Changes)

### 1. `server/services/generic_webhook_service.py`

#### לפני (Before):
```python
if direction == "outbound":
    webhook_url = getattr(settings, 'outbound_webhook_url', None)
    if not webhook_url:
        return False  # ❌ No fallback!
```

#### אחרי (After):
```python
if direction == "outbound":
    outbound_url = getattr(settings, 'outbound_webhook_url', None)
    generic_url = settings.generic_webhook_url
    webhook_url = outbound_url or generic_url  # ✅ Fallback!
    
    if not webhook_url:
        return False
    
    if outbound_url:
        print("✅ Using outbound_webhook_url")
    else:
        print("✅ Using generic_webhook_url (fallback)")
```

### 2. `server/models_sql.py`

#### עדכון תיעוד:
```python
# Before:
outbound_webhook_url = db.Column(...)  # if not set, outbound calls don't send webhooks

# After:
outbound_webhook_url = db.Column(...)  # fallback to generic_webhook_url if not set
```

### 3. `test_outbound_webhook_fallback.py` (חדש!)

נוצר קובץ בדיקה מקיף שבודק את כל התרחישים:
- ✅ כל ה-URLs מוגדרים
- ✅ רק generic מוגדר
- ✅ generic + inbound מוגדרים
- ✅ generic + outbound מוגדרים
- ✅ שום URL לא מוגדר

---

## איך לבדוק (How to Test)

### 1️⃣ בדיקה אוטומטית
```bash
python test_outbound_webhook_fallback.py
```

**תוצאה צפויה**:
```
✅ ALL TESTS PASSED
🎉 ALL TESTS PASSED! Webhook fallback is working correctly.
```

### 2️⃣ בדיקה ידנית - הגדרת webhook

#### אופציה A: רק URL גנרי (מומלץ לרוב העסקים!)
```sql
UPDATE business_settings 
SET generic_webhook_url = 'https://hooks.zapier.com/hooks/catch/xxxxx/'
WHERE tenant_id = YOUR_BUSINESS_ID;
```

#### אופציה B: URLs נפרדים
```sql
UPDATE business_settings 
SET 
  generic_webhook_url = 'https://hooks.zapier.com/hooks/catch/xxxxx/',
  inbound_webhook_url = 'https://hooks.zapier.com/hooks/catch/xxxxx/inbound/',
  outbound_webhook_url = 'https://hooks.zapier.com/hooks/catch/xxxxx/outbound/'
WHERE tenant_id = YOUR_BUSINESS_ID;
```

### 3️⃣ בדיקה ידנית - שיחות

#### בצע שיחה יוצאת:
```bash
# From CRM → Outbound Call
# Check logs:
tail -f logs/app.log | grep WEBHOOK
```

**לוגים צפויים**:
```
🔍 [WEBHOOK] Checking outbound webhook URLs for business 1:
   - outbound_webhook_url: NOT SET
   - generic_webhook_url: https://hooks.zapier.com/hooks/catch/xxxxx/
✅ [WEBHOOK] Using generic_webhook_url (fallback) for outbound
📤 [WEBHOOK] Sending call.completed to webhook
✅ [WEBHOOK] Successfully sent call.completed (status: 200)
```

### 4️⃣ כלי אבחון
```bash
python test_webhook_config.py YOUR_BUSINESS_ID
```

**תוצאה**:
```
📊 WEBHOOK CONFIGURATION FOR BUSINESS 1
════════════════════════════════════════

🔗 WEBHOOK URLs:
1️⃣ INBOUND Webhook: ❌ NOT SET
2️⃣ OUTBOUND Webhook: ❌ NOT SET
3️⃣ GENERIC Webhook: ✅ CONFIGURED: https://...

🎯 WEBHOOK ROUTING:
   For INBOUND calls:
   ⚠️  Will use: generic_webhook_url (fallback)
   
   For OUTBOUND calls:
   ✅ Will use: generic_webhook_url (fallback)  🔥 NOW WORKS!
```

---

## מבנה Payload של Webhook

### Call Completed (Inbound/Outbound)
```json
{
  "event_type": "call.completed",
  "timestamp": "2025-12-27T18:30:00Z",
  "business_id": "1",
  "call_id": "CA1234567890abcdef",
  "lead_id": "123",
  "phone": "+972501234567",
  "direction": "outbound",  // ⬅️ "inbound" or "outbound"
  "customer_name": "יוסי כהן",
  "city": "תל אביב",
  "service_category": "חשמלאי",
  "duration_sec": 330,
  "transcript": "שיחה לדוגמה...",
  "summary": "סיכום השיחה...",
  "recording_url": "https://..."
}
```

---

## מערכות Webhook במערכת

| מערכת | Field בDB | Fallback | מטרה |
|-------|-----------|----------|------|
| **Call Webhooks** | `inbound_webhook_url` | `generic_webhook_url` | שיחות נכנסות |
| **Call Webhooks** | `outbound_webhook_url` | `generic_webhook_url` | שיחות יוצאות 🔥 |
| **Generic Webhooks** | `generic_webhook_url` | - | ברירת מחדל לכל אירוע |
| **Status Webhooks** | `status_webhook_url` | - | שינויי סטטוס לידים |
| **WhatsApp** | n8n integration | - | הודעות WhatsApp |

---

## קריטריוני הצלחה (Success Criteria)

✅ שיחות יוצאות שולחות webhook גם ללא `outbound_webhook_url` מוגדר  
✅ שיחות יוצאות משתמשות ב-`generic_webhook_url` כ-fallback  
✅ שיחות נכנסות ממשיכות לעבוד כמו קודם  
✅ הלוגים מראים בבירור איזה URL בשימוש  
✅ כל הבדיקות עוברות בהצלחה  
✅ תיעוד מעודכן  

---

## קבצים ששונו (Files Changed)

1. ✅ `server/services/generic_webhook_service.py` - לוגיקת routing
2. ✅ `server/models_sql.py` - תיעוד
3. ✅ `test_outbound_webhook_fallback.py` - בדיקות (חדש!)
4. ✅ `תיקון_webhook_outbound.md` - תיעוד (חדש!)

---

## התאמה לדרישה המקורית (Original Requirement Match)

### הדרישה:
> "הwebhook של שיחות יוצאות לא עובד! רק של השילות הנכנסות עובד, תוודא שהכל יעבוד לפי עסק ויעביר אם מעודכן!! וצמיד יעבוד לפי מה שצריך (נכנסות,יוצאות,סטטוסים, מה שיש שם בwebhook) והכל עובד מושלם!!!"

### הפתרון:
- ✅ **שיחות יוצאות** - עכשיו עובד! משתמש ב-fallback ל-generic_webhook_url
- ✅ **שיחות נכנסות** - ממשיך לעבוד כמו קודם
- ✅ **סטטוסים** - עובד דרך `status_webhook_url`
- ✅ **WhatsApp** - עובד דרך n8n integration
- ✅ **מעודכן לפי עסק** - כל עסק יכול להגדיר URLs שונים או להשתמש ב-generic
- ✅ **הכל עובד מושלם** - כל מערכות ה-webhook פעילות ועובדות

---

## סיכום (Summary)

### Before Fix ❌
```
Inbound:  inbound_webhook_url → generic_webhook_url → ❌ fail
Outbound: outbound_webhook_url → ❌ FAIL (no fallback)
```

### After Fix ✅
```
Inbound:  inbound_webhook_url → generic_webhook_url → ❌ fail
Outbound: outbound_webhook_url → generic_webhook_url → ❌ fail
```

**תאריך**: 27 בדצמבר 2025  
**סטטוס**: ✅ תוקן ונבדק  
**Build**: 350+

---

## הערות נוספות (Additional Notes)

1. **עדיפות**: השימוש ב-`generic_webhook_url` הוא הפשוט ביותר עבור רוב העסקים
2. **גמישות**: עסקים שצריכים ניתוב מורכב יכולים להגדיר URLs נפרדים
3. **תאימות לאחור**: עסקים עם `outbound_webhook_url` מוגדר ימשיכו לעבוד בדיוק כמו קודם
4. **לוגים**: הלוגים מראים בבירור איזה URL בשימוש - מקל על debug
5. **בדיקות**: קיים test suite מקיף לבדיקת כל התרחישים

---

## עזרה ותמיכה (Help & Support)

### בעיות נפוצות:

**❓ Webhook לא נשלח**
```bash
# בדוק את הקונפיגורציה:
python test_webhook_config.py YOUR_BUSINESS_ID

# בדוק את הלוגים:
tail -f logs/app.log | grep WEBHOOK
```

**❓ Webhook נשלח ל-URL הלא נכון**
```bash
# בדוק איזה URL מוגדר:
SELECT 
  generic_webhook_url,
  inbound_webhook_url,
  outbound_webhook_url
FROM business_settings
WHERE tenant_id = YOUR_BUSINESS_ID;
```

**❓ Webhook נכשל (HTTP error)**
- ודא שה-URL תקין ומתחיל ב-`https://` או `http://`
- בדוק שהשרת היעד זמין ומקבל requests
- בדוק את הלוגים לפרטים נוספים

---

**סוף התיעוד** 🎉
