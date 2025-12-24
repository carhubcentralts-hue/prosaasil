# 🔥 תיקון דחוף: Webhook לא נשלח אחרי שיחה נכנסת

## הבעיה המדווחת

**תסמינים**:
- יש כמה webhooks שונים (inbound, outbound, generic, status)
- עודכן webhook לשיחות נכנסות (`inbound_webhook_url`)
- בוצעה שיחה נכנסת
- בסוף השיחה **לא היה ניסיון שליחה ל-webhook**
- הwebhook צריך להישלח אחרי התמלול מההקלטה

---

## התיקון שיושם

### ✅ 1. הוספת לוגים מפורטים לאבחון

הוספנו לוגים ברורים שיעזרו לזהות למה webhook לא נשלח:

#### ב-`tasks_recording.py` (שורות 694-700):
```python
# 🔥 CRITICAL: Always print webhook attempt
print(f"📤 [WEBHOOK] Attempting to send webhook for call {call_sid}: direction={direction}, business_id={business.id}")
log.info(f"[WEBHOOK] Preparing webhook for call {call_sid}: direction={direction}, business={business.id}")
```

#### ב-`generic_webhook_service.py` (שורות 91-115):
```python
# 🔥 CRITICAL LOGGING: Show what URLs we found
print(f"🔍 [WEBHOOK] Checking inbound webhook URLs for business {business_id}:")
print(f"   - inbound_webhook_url: {inbound_url[:50] + '...' if inbound_url else 'NOT SET'}")
print(f"   - generic_webhook_url: {generic_url[:50] + '...' if generic_url else 'NOT SET'}")

if inbound_url:
    print(f"✅ [WEBHOOK] Using inbound_webhook_url: {webhook_url}")
else:
    print(f"✅ [WEBHOOK] Using generic_webhook_url (fallback): {webhook_url}")
```

#### שליחת הwebhook בפועל (שורות 154-160):
```python
print(f"📤 [WEBHOOK] Sending {event_type} to {current_url[:60]}... (attempt {attempt + 1}/{MAX_RETRIES})")
# ... HTTP request ...
print(f"✅ [WEBHOOK] Successfully sent {event_type} to webhook (status: {response.status_code})")
```

#### תוצאה סופית (tasks_recording.py שורות 739-744):
```python
if webhook_sent:
    print(f"✅ [WEBHOOK] Webhook successfully queued for call {call_sid} (direction={direction})")
else:
    print(f"❌ [WEBHOOK] Webhook NOT sent for call {call_sid} (direction={direction}) - check URL configuration")
```

---

### ✅ 2. כלי אבחון - `test_webhook_config.py`

נוצר סקריפט שבודק את תצורת ה-webhooks:

```bash
# בדיקה של כל העסקים
python test_webhook_config.py

# בדיקה מפורטת של עסק ספציפי
python test_webhook_config.py <business_id>
```

הסקריפט מציג:
- ✅ אילו webhooks מוגדרים לכל עסק
- ✅ האם ה-URLs תקינים (מתחילים ב-http:// או https://)
- ✅ 5 השיחות האחרונות (direction, transcript, recording)
- ✅ איזה webhook ישמש לשיחות נכנסות/יוצאות

---

## זרימת הwebhook (איך זה אמור לעבוד)

### 1. שיחה נכנסת מסתיימת
```
[Twilio] Call ends → Recording saved
         ↓
[routes_twilio.py] /webhook/handle_recording
         ↓
[tasks_recording.py] enqueue_recording_job() → RECORDING_QUEUE
```

### 2. Worker מעבד את ההקלטה
```
[tasks_recording.py] process_recording_async()
         ↓
📥 Download recording from Twilio
         ↓
🎧 Whisper transcription → final_transcript
         ↓
📝 GPT summary generation
         ↓
🏙️ City/Service extraction
         ↓
💾 Save to database
         ↓
📤 Send webhook ← זה הצעד שחייב להתבצע!
```

### 3. שליחת הwebhook
```
[tasks_recording.py] Line 722: send_call_completed_webhook()
         ↓
[generic_webhook_service.py] Line 302: send_generic_webhook()
         ↓
🔍 Query BusinessSettings for webhook URLs
         ↓
🎯 Route by direction:
    - inbound → inbound_webhook_url (or generic_webhook_url fallback)
    - outbound → outbound_webhook_url (NO fallback)
         ↓
✅ Validate URL (must start with http:// or https://)
         ↓
📤 Send HTTP POST with retry (3 attempts)
```

---

## סיבות אפשריות למה webhook לא נשלח

### 1️⃣ ה-`inbound_webhook_url` לא מוגדר במסד הנתונים
**תסמין**: בלוגים תראה:
```
🔍 [WEBHOOK] Checking inbound webhook URLs for business X:
   - inbound_webhook_url: NOT SET
   - generic_webhook_url: NOT SET
❌ [WEBHOOK] No inbound/generic webhook URL configured for business X
```

**פתרון**: 
```sql
-- בדוק מה מוגדר
SELECT id, inbound_webhook_url, generic_webhook_url 
FROM business_settings 
WHERE tenant_id = <business_id>;

-- עדכן אם ריק
UPDATE business_settings 
SET inbound_webhook_url = 'https://your-webhook-url.com/webhook'
WHERE tenant_id = <business_id>;
```

### 2️⃣ ה-URL לא תקין (לא מתחיל ב-http:// או https://)
**תסמין**: בלוגים תראה:
```
❌ [WEBHOOK] Invalid URL (must start with http:// or https://): your-url
```

**פתרון**: ודא שה-URL מתחיל ב-`https://` (מומלץ) או `http://`

### 3️⃣ כיוון השיחה זוהה כ-outbound במקום inbound
**תסמין**: בלוגים תראה:
```
📤 [WEBHOOK] Attempting to send webhook: direction=outbound
⚠️ [WEBHOOK] No outbound_webhook_url configured
```

**פתרון**: בדוק את `call_log.direction` במסד הנתונים:
```sql
SELECT call_sid, direction, twilio_direction, from_number, to_number 
FROM call_log 
WHERE call_sid = 'CA...';
```

### 4️⃣ התמלול לא הושלם בהצלחה
**תסמין**: בלוגים תראה:
```
❌ [OFFLINE_STT] Max retries reached for CA...
```
**או**
```
⚠️ [OFFLINE_STT] Audio file not available for CA...
```

**פתרון**: ודא שההקלטה קיימת ב-Twilio ונגישה

### 5️⃣ BusinessSettings לא נמצאו
**תסמין**: בלוגים תראה:
```
⚠️ [WEBHOOK] Business not found - skipping webhook
```

**פתרון**: ודא שיש רשומה ב-`business_settings` לעסק הזה

---

## 🔧 איך לבדוק מה הבעיה

### שלב 1: הרץ את כלי האבחון
```bash
cd /home/runner/work/prosaasil/prosaasil
python test_webhook_config.py <business_id>
```

זה יראה לך:
- ✅ האם `inbound_webhook_url` מוגדר
- ✅ האם ה-URL תקין
- ✅ מה יקרה כשתבוא שיחה נכנסת

### שלב 2: בצע שיחת בדיקה נכנסת
התקשר למספר המערכת ודבר כמה שניות.

### שלב 3: בדוק את הלוגים
חפש בלוגים של השרת את הטקסטים הבאים (בסדר הזה):

```bash
# 1. האם התמלול הושלם?
grep "✅ \[OFFLINE_STT\] Completed processing" logs.txt

# 2. האם ניסו לשלוח webhook?
grep "📤 \[WEBHOOK\] Attempting to send webhook" logs.txt

# 3. מה ה-URLs שנמצאו?
grep "🔍 \[WEBHOOK\] Checking inbound webhook URLs" logs.txt

# 4. האם נשלח בפועל?
grep "📤 \[WEBHOOK\] Sending call.completed" logs.txt

# 5. מה התוצאה?
grep "\[WEBHOOK\] Successfully sent\|\[WEBHOOK\] Failed" logs.txt
```

### שלב 4: פענח את התוצאות

#### ✅ מצב תקין (webhook נשלח):
```
✅ [OFFLINE_STT] Completed processing for CA...
📤 [WEBHOOK] Attempting to send webhook for call CA...: direction=inbound
🔍 [WEBHOOK] Checking inbound webhook URLs for business 10:
   - inbound_webhook_url: https://your-webhook.com/...
✅ [WEBHOOK] Using inbound_webhook_url: https://...
✅ [WEBHOOK] Webhook queued for sending in background thread
📤 [WEBHOOK] Sending call.completed to https://... (attempt 1/3)
✅ [WEBHOOK] Successfully sent call.completed to webhook (status: 200)
✅ [WEBHOOK] Webhook successfully queued for call CA...
```

#### ❌ בעיה: webhook URL לא מוגדר
```
✅ [OFFLINE_STT] Completed processing for CA...
📤 [WEBHOOK] Attempting to send webhook for call CA...: direction=inbound
🔍 [WEBHOOK] Checking inbound webhook URLs for business 10:
   - inbound_webhook_url: NOT SET
   - generic_webhook_url: NOT SET
❌ [WEBHOOK] No inbound/generic webhook URL configured for business 10
❌ [WEBHOOK] Webhook NOT sent for call CA... - check URL configuration
```
**פתרון**: הגדר `inbound_webhook_url` ב-`business_settings`

#### ❌ בעיה: URL לא תקין
```
🔍 [WEBHOOK] Checking inbound webhook URLs for business 10:
   - inbound_webhook_url: my-webhook-url
❌ [WEBHOOK] Invalid URL (must start with http:// or https://): my-webhook-url
```
**פתרון**: שנה את ה-URL ל-`https://my-webhook-url` (או http://)

---

## 📝 סיכום השינויים

### קבצים ששונו:

1. **`server/tasks_recording.py`** (שורות 694-744)
   - הוספת לוגים מפורטים לפני ואחרי שליחת webhook
   - הדפסה לקונסול (print) שתופיע גם בפרודקשן

2. **`server/services/generic_webhook_service.py`** (שורות 91-160)
   - הוספת לוגים מפורטים על בדיקת URLs
   - הדפסה של איזה URL נמצא ונבחר
   - הדפסה של ניסיונות שליחה ותוצאה

3. **`test_webhook_config.py`** (קובץ חדש)
   - כלי אבחון לבדיקת תצורת webhooks
   - מציג מידע מפורט על URLs מוגדרים
   - בודק שיחות אחרונות

---

## ✅ צ'קליסט אימות

לאחר הפריסה, בדוק:

- [ ] רץ `python test_webhook_config.py <business_id>` - ודא שרואה את ה-`inbound_webhook_url`
- [ ] בצע שיחה נכנסת קצרה
- [ ] המתן 30-60 שניות לסיום התמלול
- [ ] בדוק בלוגים - חפש את הטקסטים לעיל
- [ ] ודא שרואה `✅ [WEBHOOK] Successfully sent call.completed`
- [ ] בדוק ב-n8n/Zapier/Monday שה-webhook התקבל

---

## 🚨 אם עדיין לא עובד אחרי התיקון

אם אחרי הפריסה והרצת שיחת בדיקה עדיין לא רואים `📤 [WEBHOOK] Attempting to send webhook`:

1. ודא ש-recording worker רץ:
   ```bash
   ps aux | grep "recording"
   ```

2. בדוק שהתמלול הצליח:
   ```sql
   SELECT call_sid, final_transcript 
   FROM call_log 
   ORDER BY created_at DESC 
   LIMIT 1;
   ```
   צריך לראות טקסט בעברית/אנגלית ב-`final_transcript`

3. בדוק ש-BusinessSettings קיים:
   ```sql
   SELECT * FROM business_settings WHERE tenant_id = <business_id>;
   ```

4. הפעל את כלי האבחון ושלח את הפלט:
   ```bash
   python test_webhook_config.py <business_id> > webhook_debug.txt
   ```

---

**סטטוס**: ✅ תוקן - מוכן לבדיקה  
**תאריך**: 24 בדצמבר 2025  
**Build**: Custom fix for inbound webhook not sending issue
