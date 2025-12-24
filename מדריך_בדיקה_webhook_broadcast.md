# מדריך בדיקה - תיקון n8n Webhook + דף תפוצה WhatsApp (BUILD 200+)

## סיכום הבעיות שתוקנו

### 1. בעיית n8n Webhook (500 Error)
**בעיה**: `/api/whatsapp/webhook/send` החזיר 500 "WhatsApp service not connected" גם כשהווצאפ היה מחובר.

**פתרון**:
- ✅ הוספת בדיקת בריאות לפני שליחה
- ✅ החזרת 503 במקום 500 כשלא מחובר
- ✅ קוד שגיאה ברור: `wa_not_connected`
- ✅ לוגים משופרים עם פרטי provider
- ✅ וידוא שה-webhook משתמש ב-baileys (לא auto)

### 2. בעיית טעינת קמפיינים (500 Error)
**בעיה**: `/api/whatsapp/broadcasts` (GET) החזיר 500 כשאין קמפיינים.

**פתרון**:
- ✅ תמיד מחזיר `{ok:true, campaigns:[]}` גם אם ריק
- ✅ אף פעם לא 500 - תמיד 200
- ✅ לוגים [WA_CAMPAIGNS] לשגיאות DB

### 3. בעיית נמענים (400 "לא נמצאו נמענים")
**בעיה**: הUI הראה "Loaded X leads with phones" אבל הbackend החזיר 400.

**פתרון**:
- ✅ תמיכה ב-3 פורמטים: `recipients`, `phones`, `lead_ids`
- ✅ נירמול מספרים ל-E.164
- ✅ לוגים מפורטים לפני ואחרי נירמול
- ✅ הודעות שגיאה ברורות עם `error_code`
- ✅ לוג console בfrontend לפני שליחה

---

## בדיקות קבלה (Acceptance Tests)

### בדיקה 1: n8n Webhook - שליחה מוצלחת

**Setup**:
```bash
# וודא ש-WHATSAPP_WEBHOOK_SECRET מוגדר ב-.env
WHATSAPP_WEBHOOK_SECRET=your-secret-here
BAILEYS_BASE_URL=http://baileys:3300
```

**Test Request**:
```bash
curl -X POST https://prosaas.pro/api/whatsapp/webhook/send \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-secret-here" \
  -d '{
    "to": "+972501234567",
    "message": "בדיקה מ-n8n",
    "business_id": 1
  }'
```

**Expected Response** (200):
```json
{
  "ok": true,
  "provider": "baileys",
  "message_id": 123,
  "queued": true,
  "status": "sent"
}
```

**Check Logs**:
```
[WA_WEBHOOK] business_id=1, provider_requested=baileys, provider_resolved=baileys, secret_ok=True
[WA_WEBHOOK] status_from_provider connected=True, active_phone=+972..., hasQR=False, last_seen=...
[WA_WEBHOOK] ✅ Message sent successfully: id=123
```

---

### בדיקה 2: n8n Webhook - לא מחובר (503)

**Scenario**: ווצאפ לא מחובר / צריך QR

**Expected Response** (503):
```json
{
  "ok": false,
  "error_code": "wa_not_connected",
  "provider": "baileys",
  "status_snapshot": {
    "connected": false,
    "hasQR": true,
    "active_phone": null,
    "checked_at": "2025-12-24T22:00:00Z"
  },
  "message": "WhatsApp is not connected. Please scan QR code in settings."
}
```

**Check Logs**:
```
[WA_WEBHOOK] status_from_provider connected=False, active_phone=None, hasQR=True, last_seen=None
```

---

### בדיקה 3: דף תפוצה - טעינת קמפיינים (אף פעם לא 500)

**Test**:
1. פתח את דף התפוצה: `https://prosaas.pro/whatsapp/broadcast`
2. לחץ על טאב "היסטוריה"

**Expected**:
- ✅ הדף נטען בהצלחה (אף פעם לא 500)
- ✅ אם אין קמפיינים: מציג "אין תפוצות עדיין"
- ✅ אם יש קמפיינים: מציג רשימה

**Check Network** (F12 → Network):
```
GET /api/whatsapp/broadcasts
Status: 200
Response: {"ok": true, "campaigns": [...]}
```

**Check Logs**:
```
[WA_CAMPAIGNS] DB query succeeded / failed gracefully
```

---

### בדיקה 4: דף תפוצה - שליחה ל-3 נמענים

**Test**:
1. פתח דף תפוצה
2. בחר "לידים מהמערכת"
3. בחר 3 לידים עם מספרי טלפון
4. כתוב הודעה: "בדיקה"
5. לחץ "שלח תפוצה"

**Expected Response**:
```
✅ התפוצה נוצרה בהצלחה!

נשלח לתור: 3 נמענים
מזהה תפוצה: 456

התפוצה תישלח ברקע. תוכל לעקוב אחרי ההתקדמות בלשונית "היסטוריה".
```

**Check Console** (F12 → Console):
```
📤 Sending broadcast: {
  provider: "meta",
  message_type: "freetext",
  audience_source: "leads",
  lead_ids_count: 3,
  recipient_count: 3
}
📋 Full payload keys: ["provider", "message_type", "audience_source", "lead_ids", "message_text"]
✅ Broadcast response: {ok: true, broadcast_id: 456, queued_count: 3, ...}
```

**Check Backend Logs**:
```
[WA_BROADCAST] Incoming request from business_id=1, user=5
[WA_BROADCAST] Form keys: [...]
[WA_BROADCAST] incoming_keys=[...]
[WA_BROADCAST] audience_source=leads, provider=meta, message_type=freetext
[WA_BROADCAST] Loading 3 leads from system
[WA_BROADCAST] Found 3 leads with phone numbers
[WA_BROADCAST] recipients_count=3, lead_ids_count=3, phones_count=3
[WA_BROADCAST] Normalized 3 phones, invalid=0
[WA_BROADCAST] normalized_count=3 sample=['+972501234567', '+972507654321', ...]
✅ [WA_BROADCAST] broadcast_id=456 total=3 queued=3
🚀 [WA_BROADCAST] Started worker thread for broadcast_id=456
```

---

### בדיקה 5: דף תפוצה - שגיאת נמענים חסרים (400)

**Test**:
1. פתח דף תפוצה
2. בחר "לידים מהמערכת"
3. **אל תבחר שום ליד**
4. לחץ "שלח תפוצה"

**Expected**:
```
Alert: יש לבחור לפחות ליד אחד לשליחה.

כרגע יש 150 לידים זמינים, אך לא נבחר אף אחד.
אנא סמן לידים מהרשימה או לחץ "בחר הכל".
```

**אם עוקפים את האלרט ושולחים בכל זאת**:

**Expected Response** (400):
```json
{
  "ok": false,
  "error_code": "missing_recipients",
  "expected_one_of": ["recipients", "phones", "lead_ids"],
  "got_keys": ["provider", "message_type", "audience_source"],
  "message": "לא נמצאו נמענים",
  "details": {
    "missing_field": "lead_ids",
    "selection_count": 0,
    "diagnostics": {...}
  }
}
```

**Check Backend Logs**:
```
[WA_BROADCAST] recipients_count=0, lead_ids_count=0, phones_count=0
[WA_BROADCAST] No recipients found: {...}
```

---

## לוגים משופרים - מה לחפש

### n8n Webhook Logs
```
[WA_WEBHOOK] business_id=X, provider_requested=Y, provider_resolved=Z, secret_ok=True
[WA_WEBHOOK] status_from_provider connected=True/False, active_phone=..., hasQR=..., last_seen=...
[WA_WEBHOOK] Using base_url=http://baileys:3300
[WA_WEBHOOK] Checking status: http://baileys:3300/whatsapp/business_1/status
[WA_WEBHOOK] ✅ Message sent successfully: id=X
```

### Broadcast Campaigns Logs
```
[WA_CAMPAIGNS] DB query failed (table may not exist): ...
[WA_CAMPAIGNS] error_code: campaigns_load_failed
```

### Broadcast Recipients Logs
```
[WA_BROADCAST] incoming_keys=[provider, message_type, lead_ids, ...]
[WA_BROADCAST] audience_source=leads, provider=meta, message_type=freetext
[WA_BROADCAST] Loading X leads from system
[WA_BROADCAST] recipients_count=X, lead_ids_count=Y, phones_count=Z
[WA_BROADCAST] Normalized X phones, invalid=Y
[WA_BROADCAST] normalized_count=X sample=['+972...', ...]
```

---

## שגיאות נפוצות ופתרונות

### שגיאה: "BAILEYS_BASE_URL contains external domain"
**גורם**: `BAILEYS_BASE_URL=https://prosaas.pro/send`
**פתרון**: 
```bash
# ב-.env
BAILEYS_BASE_URL=http://baileys:3300
```

### שגיאה: "WhatsApp status check timeout"
**גורם**: שירות baileys לא רץ / לא נגיש
**פתרון**:
```bash
docker-compose ps  # וודא ש-baileys רץ
docker-compose logs baileys  # בדוק לוגים
```

### שגיאה: "All phones are invalid"
**גורם**: מספרי טלפון לא בפורמט E.164
**פתרון**: וודא שהלידים במערכת יש להם `phone_e164` תקין (מתחיל ב-+)

### שגיאה: "Campaign loads 500"
**לא אמור לקרות יותר!** אבל אם כן:
1. בדוק לוגים: `[WA_CAMPAIGNS]`
2. וודא שטבלת `whatsapp_broadcasts` קיימת
3. הרץ מיגרציות: `python server/db_migrate.py`

---

## Summary - מה שונה?

| Before (❌) | After (✅) |
|------------|----------|
| n8n webhook: 500 גם כשמחובר | 200 עם message_id כשמחובר |
| n8n webhook: לא ברור למה נכשל | 503 + `wa_not_connected` + status_snapshot |
| Campaigns: 500 כשריק | 200 + `{campaigns: []}` תמיד |
| Broadcast: 400 ללא הסבר | 400 + `error_code` + `expected_one_of` + diagnostics |
| לוגים: מינימליים | לוגים מפורטים בכל שלב |
| Frontend: ללא console logs | Console logs מפורטים |

---

## מה לבדוק לפני Merge?

- [ ] n8n webhook מחזיר 200 עם message_id (כשמחובר)
- [ ] n8n webhook מחזיר 503 עם error_code (כשלא מחובר)
- [ ] דף קמפיינים נטען (אף פעם לא 500)
- [ ] שליחת broadcast ל-3 נמענים מצליחה
- [ ] ניסיון broadcast ללא נמענים נותן 400 ברור
- [ ] כל הלוגים המשופרים מופיעים

---

## איך להריץ בדיקה מלאה?

```bash
# 1. וודא סביבה
cd /home/runner/work/prosaasil/prosaasil
source .venv/bin/activate

# 2. בדוק תחביר
python -m py_compile server/routes_whatsapp.py
echo "✅ Python syntax OK"

# 3. הרץ unit tests
python test_webhook_broadcast_fixes.py
# Expected: 4/5 tests pass (flask import will fail in test env)

# 4. הרץ שרת (development)
python run_server.py

# 5. בדוק endpoints:
# - https://prosaas.pro/whatsapp/broadcast (UI)
# - POST /api/whatsapp/webhook/send (curl)
# - GET /api/whatsapp/broadcasts (curl)
# - POST /api/whatsapp/broadcasts (UI)
```

---

**הערה חשובה**: כל השינויים עוקבים אחרי הדרישות המדויקות מה-problem statement. אם יש בעיה, בדוק קודם את:
1. ה-logs המשופרים - הם אמורים להסביר מה קרה
2. ה-error_code - הוא אמור להיות ברור
3. ה-console.log בfrontend - הוא אמור להראות מה נשלח
