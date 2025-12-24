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
Authorization: Bearer <your-token>
```

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

## 🔧 n8n Integration

### Step 1: Configure HTTP Request Node

1. **Method:** `POST`
2. **URL:** `https://prosaas.pro/api/whatsapp/send`
3. **Authentication:** Choose "Header Auth" or "Generic Credential Type"
   - **Name:** `Authorization`
   - **Value:** `Bearer <your-token>`
4. **Send Body:** ON
5. **Body Content Type:** `JSON`
6. **Specify Body:** `Using JSON`

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

## 🔒 Security: Add Webhook Secret

### For External Webhooks (n8n, Zapier, etc.)

To prevent unauthorized access, you have two options:

### Option 1: Use Session Authentication
Login to ProSaaS and use your session token.

### Option 2: Create a Webhook-Specific Endpoint

Add this to your backend (recommended for n8n):

```python
@whatsapp_bp.route('/webhook/send', methods=['POST'])
@csrf.exempt
def send_via_webhook():
    """Send WhatsApp message via webhook - for n8n/external services"""
    
    # Verify webhook secret
    webhook_secret = request.headers.get('X-Webhook-Secret')
    expected_secret = os.getenv('WHATSAPP_WEBHOOK_SECRET')
    
    if not webhook_secret or webhook_secret != expected_secret:
        log.error("[WA-WEBHOOK] Unauthorized access attempt")
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    
    # Get data
    data = request.get_json(force=True)
    to_number = data.get('to')
    message = data.get('message')
    business_id = data.get('business_id', 1)  # Default or from header
    
    if not to_number or not message:
        return jsonify({"ok": False, "error": "missing_required_fields"}), 400
    
    # Send message
    # ... (rest of send logic)
```

Then in `.env`:
```bash
WHATSAPP_WEBHOOK_SECRET=your-secret-key-here-generate-random
```

And in n8n:
- **Header Name:** `X-Webhook-Secret`
- **Header Value:** `your-secret-key-here-generate-random`

---

## 🧪 Testing

### Test 1: Check if endpoint is reachable

```bash
curl -i https://prosaas.pro/api/whatsapp/send
```

**Expected:** `401 Unauthorized` or `405 Method Not Allowed` (means it reaches the backend)
**Problem:** If you get `404 Not Found`, the route doesn't exist

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
