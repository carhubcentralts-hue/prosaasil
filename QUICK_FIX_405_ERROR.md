# Quick Fix: 405 Error for WhatsApp Send

## ⚠️ Problem
Getting **405 Method Not Allowed** from nginx when trying to send WhatsApp messages.

## ✅ Solution
You were calling the wrong URL. Here's the fix:

### Wrong URL (causes 405)
```
❌ POST https://prosaas.pro/send
```

### Correct URLs

#### Option 1: Authenticated (for logged-in users)
```
✅ POST https://prosaas.pro/api/whatsapp/send
   Headers:
     Authorization: Bearer <token>
     Content-Type: application/json
   Body:
     {"to": "+972...", "message": "..."}
```

#### Option 2: Webhook (for n8n/external services) - NEW!
```
✅ POST https://prosaas.pro/api/whatsapp/webhook/send
   Headers:
     X-Webhook-Secret: <your-secret>
     Content-Type: application/json
   Body:
     {"to": "+972...", "message": "..."}
```

---

## 🔧 n8n Setup (3 Steps)

### Step 1: Set Environment Variable
Add to your `.env` file:
```bash
WHATSAPP_WEBHOOK_SECRET=abc123xyz789  # Change this!
```

Generate secure secret:
```bash
openssl rand -hex 32
```

### Step 2: Configure n8n HTTP Request Node
- **Method:** POST
- **URL:** `https://prosaas.pro/api/whatsapp/webhook/send`
- **Send Headers:** ON
  - Name: `X-Webhook-Secret`
  - Value: `abc123xyz789` (your secret)
- **Send Body:** ON
- **Body Content Type:** JSON
- **Body:**
  ```json
  {
    "to": "={{ $json.body.phone }}",
    "message": "היי, זו הודעה מהמערכת"
  }
  ```

### Step 3: Test
Send a test request. You should get:
```json
{
  "ok": true,
  "message_id": 123,
  "provider": "baileys",
  "status": "sent"
}
```

---

## 🐛 Troubleshooting

### Still getting 405?
**Check:** Is your URL correct?
- Must start with `/api/`
- Full path: `/api/whatsapp/webhook/send`

### Getting 401 Unauthorized?
**Check:** Is your webhook secret correct?
- Header name: `X-Webhook-Secret`
- Value must match `.env` file

### Getting 400 missing_to or missing_message?
**Check:** Is your JSON body correct?
```json
{
  "to": "+972501234567",    ← Must be a string
  "message": "Hello World"  ← Must be a string
}
```

### Getting 503 whatsapp_service_unavailable?
**Check:** Is WhatsApp connected?
- Go to ProSaaS → WhatsApp → Status
- Must show "מחובר" (connected)
- Scan QR code if needed

---

## 📝 Test Commands

### Test 1: Check endpoint exists
```bash
curl -i https://prosaas.pro/api/whatsapp/webhook/send
```
Expected: `401 Unauthorized` (means it exists!)

### Test 2: Send with secret
```bash
curl -i -X POST https://prosaas.pro/api/whatsapp/webhook/send \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: abc123xyz789" \
  -d '{"to":"+972501234567","message":"test"}'
```
Expected: `200 OK` with JSON response

---

## 📚 Full Documentation
See `WHATSAPP_SEND_ENDPOINT_GUIDE.md` for complete details.

## 🔗 Import Example
Import `n8n_whatsapp_send_workflow.json` into n8n as a starting point.

---

**Last Updated:** 2025-12-24  
**Commit:** 76ab283
