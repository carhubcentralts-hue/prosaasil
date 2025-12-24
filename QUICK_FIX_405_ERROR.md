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

#### Option 1: Session-Authenticated (for web app only)
```
✅ POST https://prosaas.pro/api/whatsapp/send
   Headers:
     Content-Type: application/json
     Cookie: session=... (from browser)
   Body:
     {"to": "+972...", "message": "..."}
```
**Note:** Only for logged-in web app users. Don't use for n8n!

#### Option 2: Webhook (for n8n/external services) - RECOMMENDED
```
✅ POST https://prosaas.pro/api/whatsapp/webhook/send
   Headers:
     X-Webhook-Secret: <your-secret>
     Content-Type: application/json
   Body:
     {"to": "+972...", "message": "...", "business_id": 1}
```
**This is the one to use for n8n!**

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

### Understanding 405 Errors

**405 can come from two places:**

1. **nginx (before reaching Flask):**
   - Response: HTML page with `Server: nginx` header
   - Cause: URL path not proxied to backend OR POST method blocked
   - Fix: Check nginx.conf routing

2. **Flask backend (after nginx):**
   - Response: JSON with error message
   - Cause: Route exists but wrong HTTP method
   - Fix: Check you're using POST, not GET

**How to tell the difference:**
```bash
curl -i -X POST https://prosaas.pro/api/whatsapp/webhook/send -d '{}'
```
- Returns HTML = nginx issue (not reaching backend)
- Returns JSON = backend issue (backend reached)

### Still getting 405?

**Step 1:** Verify it's reaching the backend
```bash
curl -i -X POST https://prosaas.pro/api/whatsapp/webhook/send \
  -H "Content-Type: application/json" \
  -d '{}'
```

**If you get JSON response (400/401):** ✅ Backend is working!
- 401 = Missing/wrong webhook secret
- 400 = Missing required fields (to/message)

**If you get HTML with nginx header:** ❌ nginx blocking
- Check your URL path is exactly: `/api/whatsapp/webhook/send`
- Verify nginx proxies `/api/` to backend
- Check for any `limit_except` directives in nginx.conf

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
# Test with OPTIONS
curl -i -X OPTIONS https://prosaas.pro/api/whatsapp/webhook/send

# Test with POST (empty body)
curl -i -X POST https://prosaas.pro/api/whatsapp/webhook/send \
  -H "Content-Type: application/json" \
  -d '{}'
```

**What to look for:**
- ✅ Returns JSON with error (400/401) = Backend is working
- ❌ Returns HTML from nginx = nginx blocking request
- ❌ Returns 404 = Route doesn't exist

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
