# WhatsApp Send Endpoint - Configuration Guide

## ⚠️ Critical: 405 Error Fix

### Problem
If you're getting **405 Method Not Allowed** from nginx, it means you're calling the wrong URL path.

**Wrong:** `POST https://prosaas.pro/send`  
**Correct:** `POST https://prosaas.pro/api/whatsapp/send`

---

## 📍 Correct Endpoint

### Single Message Send
**URL:** `POST /api/whatsapp/send`

**Headers:**
```
Content-Type: application/json
Cookie: session=... (from browser login)
```

**Note:** This endpoint requires active session authentication from the web app. For automated services (n8n, Zapier), use the webhook endpoint below instead.

**Request Body:**
```json
{
  "to": "+972501234567",
  "message": "Hello World"
}
```

**Response (Success):**
```json
{
  "ok": true,
  "message_id": 123,
  "provider": "baileys",
  "status": "sent"
}
```

**Response (Error):**
```json
{
  "ok": false,
  "error": "missing_required_fields"
}
```

---

### Webhook Endpoint (for n8n/automation)
**URL:** `POST /api/whatsapp/webhook/send`

**Headers:**
```
Content-Type: application/json
X-Webhook-Secret: <secret-from-env>
```

**⚠️ Use this for n8n! Don't use session/cookie authentication for automated services.**

**Request Body:**
```json
{
  "to": "+972501234567",
  "message": "Hello World",
  "business_id": 1
}
```

**Response:** Same as above

---

## 🔧 n8n Integration

### Step 1: Configure HTTP Request Node

**⚠️ Important: Use the webhook endpoint with X-Webhook-Secret header!**

1. **Method:** `POST`
2. **URL:** `https://prosaas.pro/api/whatsapp/webhook/send`
3. **Authentication:** None (we use custom header below)
4. **Send Headers:** ON
   - Add Header:
     - **Name:** `X-Webhook-Secret`
     - **Value:** `your-secret-from-env-file`
5. **Send Body:** ON
6. **Body Content Type:** `JSON`
7. **Specify Body:** `Using JSON`

**Do NOT use:**
- ❌ Session cookies (they expire)
- ❌ Authorization: Bearer tokens (for web app only)
- ✅ Use X-Webhook-Secret header only

### Step 2: Configure Body

**Option A: Simple Static Message**
```json
{
  "to": "+972501234567",
  "message": "היי, זו הודעת בדיקה"
}
```

**Option B: Dynamic from Previous Node**
```json
{
  "to": "={{ $json.phone }}",
  "message": "היי {{ $json.name }}, זו הודעה ממערכת ProSaaS"
}
```

**Option C: From Webhook Body**
```json
{
  "to": "={{ $json.body.phone }}",
  "message": "={{ $json.body.message }}"
}
```

### ⚠️ Common Mistakes to Avoid

❌ **Wrong URL (causes 405):**
```
POST https://prosaas.pro/send
```

❌ **Wrong Content-Type:**
```
Content-Type: application/x-www-form-urlencoded
```

❌ **Malformed Body (querystring format):**
```
to=+972...
message=test
```

✅ **Correct:**
```json
{
  "to": "+972501234567",
  "message": "test"
}
```

---

## 🔒 Security Setup

### For n8n/External Services (REQUIRED)

The webhook endpoint is already implemented and secured with a secret header.

**Setup Steps:**

**1. Generate a secure secret:**
```bash
openssl rand -hex 32
```

**2. Add to `.env` file:**
```bash
WHATSAPP_WEBHOOK_SECRET=<paste-generated-secret-here>
```

**3. Restart backend:**
```bash
docker-compose restart backend
```

**4. Configure n8n:**
- **URL:** `https://prosaas.pro/api/whatsapp/webhook/send`
- **Method:** POST
- **Headers:**
  - Name: `X-Webhook-Secret`
  - Value: `<same-secret-from-env>`
- **Body:** JSON (see examples above)

**⚠️ Critical:**
- ❌ Do NOT use session cookies for n8n (they expire)
- ❌ Do NOT use Authorization: Bearer tokens (for web app only)
- ✅ ONLY use `X-Webhook-Secret` header for automated services

---

## 🧪 Testing

### Test 1: Check if endpoint is reachable

```bash
# Test 1a: Check OPTIONS (CORS/routing)
curl -i -X OPTIONS https://prosaas.pro/api/whatsapp/send

# Test 1b: Test POST with empty body (check if route exists)
curl -i -X POST https://prosaas.pro/api/whatsapp/send \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Results:**
- **If returns JSON with error** (400/401) → ✅ Route exists, reached Flask backend
- **If returns HTML with nginx header** → ❌ nginx blocking, not reaching backend
- **If returns 404** → ❌ Route doesn't exist

**Common Responses:**
- `401 Unauthorized` (JSON) → Backend reached, needs auth
- `400 Bad Request` (JSON) → Backend reached, missing fields
- `405 Method Not Allowed` with nginx HTML → nginx blocking POST
- `405 Method Not Allowed` (JSON) → Backend reached but wrong method

### Test 2: Test with authentication

```bash
curl -i -X POST https://prosaas.pro/api/whatsapp/send \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR-TOKEN" \
  -d '{"to":"+972501234567","message":"test"}'
```

**Expected:** `200 OK` with JSON response

### Test 3: Test from n8n

1. Create a simple workflow
2. Add "HTTP Request" node
3. Configure as shown above
4. Execute and check response

---

## 🐛 Troubleshooting

### Error: 405 Method Not Allowed (nginx)

**Cause:** Wrong URL path (missing `/api/` prefix)

**Fix:** Use `https://prosaas.pro/api/whatsapp/send`

---

### Error: 401 Unauthorized

**Cause:** Missing or invalid authentication

**Fix:** 
1. Check you're logged in (for browser)
2. Add `Authorization: Bearer <token>` header
3. Or use webhook secret method

---

### Error: 400 missing_required_fields

**Cause:** Request body is missing `to` or `message` fields

**Fix:** Check your JSON body structure:
```json
{
  "to": "+972...",
  "message": "..."
}
```

---

### Error: 503 whatsapp_service_unavailable

**Cause:** WhatsApp (Baileys) is not connected

**Fix:** 
1. Go to WhatsApp settings in ProSaaS
2. Scan QR code to connect
3. Verify status shows "מחובר"

---

## 📚 Related Endpoints

### Check WhatsApp Connection Status
```
GET /api/whatsapp/status
```

### Send Broadcast (Multiple Recipients)
```
POST /api/whatsapp/broadcasts
```

### Get Conversation Messages
```
GET /api/whatsapp/conversation/{phone_number}
```

---

## 🔗 URL Formats

### Development (Local)
```
http://localhost:5000/api/whatsapp/send
```

### Production (HTTPS)
```
https://prosaas.pro/api/whatsapp/send
```

### Docker Internal (from n8n container)
```
http://backend:5000/api/whatsapp/send
```

---

## ✅ Quick Reference

| Item | Value |
|------|-------|
| Method | POST |
| Path | `/api/whatsapp/send` |
| Content-Type | `application/json` |
| Auth | `Authorization: Bearer <token>` or Session |
| Body | `{"to": "+972...", "message": "..."}` |

---

**Last Updated:** 2025-12-24  
**Related Issue:** 405 Method Not Allowed from nginx
