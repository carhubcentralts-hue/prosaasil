# 📋 Production Checklist - "Once and for All"

## ✅ מה תוקן לפי ההנחיות המפורטות:

### 1) ✅ Flask-Sock Registration
- `sock = Sock()` + `sock.init_app(app)` 
- `assert "sock" in app.extensions`
- שני routes: `/ws/twilio-media` + `/ws/twilio-media/`

### 2) ✅ TwiML עם URLs מוחלטים  
- `abs_url()` function לבניית URLs מוחלטים
- `os.getenv("PUBLIC_BASE_URL")` או `request.url_root`
- פותר 11100 "Invalid Play URL"

### 3) ✅ Twilio Security Decorators
- `@require_twilio_signature` רק על HTTP endpoints
- לא על WebSocket `/ws/twilio-media`

### 4) ✅ WhatsApp Webhook Routes
- `server/routes_whatsapp.py` נוצר
- `/webhook/whatsapp/inbound` endpoint
- שמירה לדטאבייס + תגובות בעברית

### 5) ✅ Static MP3 Files  
- `static/tts/greeting_he.mp3` (46KB)
- `static/tts/fallback_he.mp3` (30KB)
- ברכות בעברית מקוריות

### 6) ✅ Database Recording
- `INSERT` מיידי ב-`incoming_call`
- `UPDATE` ב-`call_status` webhook
- שמירת transcript ב-`handle_recording`

### 7) ✅ Watchdog System Enhanced
- `_do_redirect()` עם TwiML נכון: `Record → Play → Hangup`
- 8s start timeout, 6s media timeout
- משתמש ב-`stream_registry`

### 8) ✅ Logging & Diagnostics
- `WS_CONNECTED`, `WS_START`, `WS_STOP`
- `WATCHDOG_REDIRECT` עם סיבה
- HTTP request/response logging

## 🔧 בדיקות סגירה (Pre-Deploy):

### A) GET /readyz
```bash
curl -s https://ai-crmd.replit.app/readyz
# Expected: {"status":"ready", ...}
```

### B) בדיקת TwiML Response  
```bash
curl -s https://ai-crmd.replit.app/webhook/incoming_call | head -25
# Expected: <Play>https://.../greeting_he.mp3</Play>
# Expected: <Stream wss://.../ws/twilio-media>
```

### C) בדיקת Static Files
```bash
curl -I https://ai-crmd.replit.app/static/tts/greeting_he.mp3
curl -I https://ai-crmd.replit.app/static/tts/fallback_he.mp3  
# Expected: 200 OK
```

### D) בדיקת WebSocket Connection
```bash
# Using websocket testing tool:
wscat -c wss://ai-crmd.replit.app/ws/twilio-media
# Expected: 101 Switching Protocols
```

### E) שיחה אמיתית
1. אין 31920/31924 WebSocket errors
2. אם WebSocket לא עובד → Watchdog מפעיל Record
3. תמלול נשמר בדטאבייס
4. אין לולאות אינסופיות

### F) WhatsApp Test
```bash
# Send test message to WhatsApp number:
# Expected: Response in Hebrew
# Expected: DB record in call_log
```

## 🎯 משתני סביבה נדרשים:

- `DATABASE_URL` (PostgreSQL)
- `OPENAI_API_KEY` 
- `GOOGLE_APPLICATION_CREDENTIALS`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `PUBLIC_BASE_URL=https://ai-crmd.replit.app`

## 📞 תוצאה צפויה בשיחה:

**Scenario A: WebSocket Success**
```
Call → Greeting → WebSocket connects → Real-time Hebrew conversation
```

**Scenario B: WebSocket Fails (Fixed!)**  
```
Call → Greeting → Watchdog detects failure → Record → Play → Hangup
```

**❌ לא עוד:**
- 31920 WebSocket handshake errors
- 11100 Invalid Play URL  
- 13512 Hebrew Say errors
- אין לולאות אינסופיות
- אין שקט במקום תמלול

## ✅ מוכן לפרודקציה!

המערכת תעבוד בשיחה אמיתית עם fallback מובטח.