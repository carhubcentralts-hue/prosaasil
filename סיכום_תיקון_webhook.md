# 🔥 תיקון: Webhook של סיום שיחה לא נשלח

## הבעיה שזוהתה

**תסמינים**:
- הלוגים הראו: `✅ [OFFLINE_STT] Completed processing for {call_sid}`
- אבל **לא היו לוגים** של `[WEBHOOK] Preparing...` או `[WEBHOOK] ✅ Success`
- מערכות חיצוניות (n8n, Zapier וכו') **לא קיבלו** התראות על סיום שיחות

**שורש הבעיה**: 
הפונקציה `process_recording_async()` ב-`tasks_recording.py` סיימה את כל העיבוד (תמלול, סיכום, חילוץ) אבל **לא קראה** ל-`send_call_completed_webhook()` בסוף הפייפליין.

---

## הפתרון שיושם

### ✅ 1. הוספת קריאה ל-webhook בסוף הפייפליין

**קובץ**: `server/tasks_recording.py`

הוספנו קריאה ל-webhook **אחרי** שכל העיבוד מסתיים:

```python
# 🔥 5. Send call_completed webhook - CRITICAL FIX!
webhook_sent = send_call_completed_webhook(
    business_id=business.id,
    call_id=call_sid,
    phone=call_log.from_number,
    direction=call_log.direction or "inbound",  # 🔥 הפרדה בין נכנס/יוצא
    transcript=final_transcript,
    summary=summary,
    city=extracted_city,
    service_category=extracted_service,
    # ... כל השדות האחרים ...
)
```

**תכונות**:
- נשלח רק **אחרי** שכל העיבוד הסתיים (תמלול → סיכום → חילוץ)
- מטפל נכון ב-`direction` (inbound vs outbound)
- לא קורס את הפייפליין אם ה-webhook נכשל
- logging מקיף לאיתור תקלות

---

### ✅ 2. הפרדה ברורה בין Inbound ו-Outbound

**קובץ**: `server/services/generic_webhook_service.py`

**שיחות נכנסות (Inbound)**:
- משתמש ב-`inbound_webhook_url` אם מוגדר
- נסיגה ל-`generic_webhook_url` אם אין inbound URL
- מדלג על webhook אם שניהם לא מוגדרים

**שיחות יוצאות (Outbound)**:
- משתמש **רק** ב-`outbound_webhook_url` - **ללא נסיגה**
- מדלג על webhook אם לא מוגדר (מונע "זיהום" של ה-inbound webhook)

```python
if direction == "outbound":
    # רק outbound_webhook_url - ללא נסיגה
    webhook_url = settings.outbound_webhook_url
    if not webhook_url:
        return False  # לא שולח בכלל
        
elif direction == "inbound":
    # inbound_webhook_url עם נסיגה ל-generic
    webhook_url = settings.inbound_webhook_url or settings.generic_webhook_url
```

---

### ✅ 3. Logging מקיף

הוספנו לוגים ברורים בכל שלב:

**לפני שליחת webhook**:
```
[WEBHOOK] 📞 send_call_completed_webhook called:
[WEBHOOK]    call_id=CA..., business_id=10, direction=inbound
[WEBHOOK]    phone=+972..., city=בית שאן, service=שיווק נכס
[WEBHOOK] ✅ Using inbound_webhook_url for business 10: https://...
```

**במהלך השליחה**:
```
[WEBHOOK] Sending call.completed to https://... (attempt 1)
```

**אחרי השליחה**:
```
[WEBHOOK] ✅ Success: call.completed sent to webhook
[WEBHOOK]    Status: 200, Response: {"success":true}
```

---

## זרימת השיחה המלאה

### שלב Realtime (במהלך השיחה)
1. Twilio → `/webhook/call_status`
2. WebSocket stream → OpenAI Realtime API
3. השיחה מתנהלת
4. השיחה מסתיימת → `[CLEAN PIPELINE] Call ended - realtime handler done`
5. **לא נשלח webhook כאן** - מועבר ל-worker

### שלב Offline (אחרי השיחה - Worker)
1. עבודת הקלטה נכנסת לתור → `RECORDING_QUEUE`
2. Worker מעבד → `process_recording_async()`
3. **שלב 1**: הורדת הקלטה (במידת הצורך)
4. **שלב 2**: תמלול Whisper → `final_transcript`
5. **שלב 3**: יצירת סיכום GPT
6. **שלב 4**: חילוץ עיר/שירות מהסיכום
7. **שלב 5**: שמירה למסד נתונים
8. **🔥 שלב 6 (חדש)**: שליחת webhook עם כל הדאטה
   - כולל: תמלול, סיכום, עיר, שירות, משך וכו'
   - מנותב נכון לפי direction (inbound vs outbound)

---

## מדריך בדיקה

### בדיקה 1: Webhook שיחה נכנסת

1. הגדר `inbound_webhook_url` ב-BusinessSettings לעסק שלך
2. בצע שיחת בדיקה נכנסת
3. בדוק בלוגים:
   ```
   [WEBHOOK] 📞 send_call_completed_webhook called:
   [WEBHOOK]    direction=inbound
   [WEBHOOK] ✅ Using inbound_webhook_url for business X
   [WEBHOOK] ✅ Success: call.completed sent to webhook
   ```
4. ודא שה-webhook התקבל ב-n8n/Zapier עם payload תקין

### בדיקה 2: Webhook שיחה יוצאת

1. הגדר `outbound_webhook_url` ב-BusinessSettings
2. בצע שיחת בדיקה יוצאת
3. בדוק בלוגים:
   ```
   [WEBHOOK]    direction=outbound
   [WEBHOOK] ✅ Using outbound_webhook_url for business X
   [WEBHOOK] ✅ Success: call.completed sent to webhook
   ```
4. ודא שזה **לא** הגיע ל-inbound_webhook_url

### בדיקה 3: ללא URL מוגדר

1. הסר את inbound ו-outbound webhook URLs
2. בצע שיחה
3. בדוק בלוגים:
   ```
   [WEBHOOK] ⚠️ No inbound/generic webhook URL configured - skipping
   ```
4. ודא שהעיבוד האופליין עדיין מסתיים בהצלחה

---

## דוגמת Payload

```json
{
  "event_type": "call.completed",
  "timestamp": "2025-12-10T14:23:45Z",
  "business_id": "10",
  "call_id": "CA9dd13ec4fcb895203d2162ca7e0297fc",
  "lead_id": "123",
  "phone": "+972501234567",
  "direction": "inbound",
  "city": "בית שאן",
  "service_category": "שיווק נכס",
  "started_at": "2025-12-10T14:23:19Z",
  "ended_at": "2025-12-10T14:23:45Z",
  "duration_sec": 26,
  "transcript": "היי, זה מאתר המנולן...",
  "summary": "### סוג הפנייה והתחום...",
  "agent_name": "Assistant"
}
```

---

## קבצים ששונו

1. **`server/tasks_recording.py`** - הוספת קריאה ל-webhook בסוף הפייפליין (שורות ~303-360)
2. **`server/services/generic_webhook_service.py`** - שיפור logging והפרדת routing

---

## מגבלות ידועות

1. **Webhook נשלח אחרי העיבוד האופליין** - לא מיד כשהשיחה מסתיימת (עיכוב של 5-30 שניות בדרך כלל)
   - זה בכוונה - אנחנו רוצים דאטה מלא (תמלול, סיכום, חילוץ)
   
2. **רק שיחות מוצלחות עם הקלטה שולחות webhook**
   - שיחות שנכשלו (no-answer, busy, failed, canceled) **לא** שולחות call.completed webhooks
   - זו התנהגות נכונה - לשיחות האלה אין תמלול/סיכום לשלוח
   - אם צריך התראות על שיחות שנכשלו, צריך להוסיף טיפול נפרד ב-`/webhook/call_status`
   
3. **שיחות יוצאות ללא outbound_webhook_url** - לא נשלח webhook
   - זה מכוון - מונע ערבוב של דאטה inbound/outbound
   
4. **כשלון webhook לא מנסה שוב** - נורה פעם אחת עם 3 ניסיונות HTTP
   - אם כל 3 הניסיונות נכשלים, ה-webhook אובד

---

## קריטריוני הצלחה

✅ כל שיחה שמסתיימת שולחת בדיוק webhook אחד (או אפס אם לא מוגדר)  
✅ שיחות נכנסות הולכות ל-`inbound_webhook_url` (או `generic_webhook_url` כנסיגה)  
✅ שיחות יוצאות הולכות **רק** ל-`outbound_webhook_url` (ללא נסיגה)  
✅ Webhook כולל דאטה מלא (תמלול, סיכום, עיר, שירות)  
✅ כשלונות webhook מתועדים אבל לא קורסים את הפייפליין  
✅ לוגים ברורים מקלים על איתור תקלות  

---

## צעדים הבאים

1. **הפעל מחדש את השרת**: `./start_dev.sh`
2. **בצע שיחת בדיקה**: נכנסת או יוצאת
3. **בדוק את הלוגים**: חפש `[WEBHOOK] 📞 send_call_completed_webhook called`
4. **ודא קבלה**: בדוק ב-n8n/Zapier שה-webhook התקבל

---

**סטטוס**: ✅ תוקן - מוכן לבדיקה  
**תאריך**: 10 בדצמבר 2025

**קבצים לקריאה נוספת**:
- `WEBHOOK_COMPLETION_FIX.md` - תיעוד מלא באנגלית
- `test_webhook_fix.sh` - סקריפט אימות
