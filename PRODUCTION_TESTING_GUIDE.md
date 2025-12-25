# Production Testing Guide for Webhook Secret

This guide addresses the 3 verification points from the PR comment.

## 1. Verify Migration 47 in Production

### Check if column exists in database:

```sql
-- Connect to production database
psql -U your_user -d your_database

-- Check if webhook_secret column exists
SELECT column_name, data_type, is_nullable, character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'business' 
AND column_name = 'webhook_secret';

-- Expected output:
-- column_name    | data_type        | is_nullable | character_maximum_length
-- webhook_secret | character varying| YES         | 128

-- Check for unique constraint
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'business'::regclass
AND contype = 'u'
AND conname LIKE '%webhook_secret%';

-- OR check with this query:
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'business'
AND indexdef LIKE '%webhook_secret%';
```

### Run migration if not present:

```bash
# On production server
cd /path/to/prosaasil
python -m server.db_migrate

# Look for this output:
# 🔧 MIGRATION CHECKPOINT: Migration 47: WhatsApp Webhook Secret for n8n integration
# ✅ Added webhook_secret column to business table for n8n webhook authentication
```

## 2. Test Blueprint Registration and nginx Routing

### A. Test GET endpoint (masked secret)

```bash
# Test with authenticated session (replace with your production domain)
curl -i -X GET https://prosaas.pro/api/business/settings/webhook-secret \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -H "Content-Type: application/json"

# Expected response (no secret set):
# HTTP/1.1 200 OK
# Content-Type: application/json
# {
#   "ok": true,
#   "webhook_secret_masked": null,
#   "has_secret": false
# }

# Expected response (secret exists):
# HTTP/1.1 200 OK
# Content-Type: application/json
# {
#   "ok": true,
#   "webhook_secret_masked": "wh_n8n_****...b7",
#   "has_secret": true
# }
```

### B. Test POST endpoint (generate secret)

```bash
# Generate/rotate secret
curl -i -X POST https://prosaas.pro/api/business/settings/webhook-secret/rotate \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -H "Content-Type: application/json"

# Expected response (one-time full secret):
# HTTP/1.1 200 OK
# Content-Type: application/json
# {
#   "ok": true,
#   "webhook_secret": "wh_n8n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0b7",
#   "webhook_secret_masked": "wh_n8n_************************************b7"
# }
```

### Common Issues:

**If you get HTML instead of JSON:**
```
This means nginx is not routing to the Flask app correctly.
```

**Fix:** Check nginx configuration for `/api/business/settings/webhook-secret` routing:

```nginx
# In your nginx config
location /api/ {
    proxy_pass http://localhost:5000;  # or your Flask port
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**If you get 401 Unauthorized:**
```
This means you're not authenticated or don't have the right role.
```

**Required roles:**
- system_admin
- owner
- admin
- manager

**Not allowed:**
- agent
- business (read-only)
- unauthenticated users

**If you get 404 Not Found:**
```
Blueprint not registered properly.
```

Check `app_factory.py` has:
```python
from server.routes_webhook_secret import webhook_secret_bp
app.register_blueprint(webhook_secret_bp)
```

## 3. Verify Tenant Isolation (Per-Business Secret)

### Test with multiple businesses:

```bash
# Login as Business 1 admin
# Generate secret for Business 1
curl -X POST https://prosaas.pro/api/business/settings/webhook-secret/rotate \
  -H "Cookie: session=BUSINESS1_SESSION"

# Response: secret1 = "wh_n8n_abc123..."

# Login as Business 2 admin
# Generate secret for Business 2
curl -X POST https://prosaas.pro/api/business/settings/webhook-secret/rotate \
  -H "Cookie: session=BUSINESS2_SESSION"

# Response: secret2 = "wh_n8n_xyz789..."

# Verify they are different
echo "secret1 != secret2" # Should be true
```

### Verify in database:

```sql
-- Check secrets are unique per business
SELECT id, name, 
       SUBSTRING(webhook_secret, 1, 10) as secret_prefix,
       SUBSTRING(webhook_secret, -5) as secret_suffix
FROM business
WHERE webhook_secret IS NOT NULL;

-- Expected output:
-- id | name       | secret_prefix | secret_suffix
-- 1  | Business A | wh_n8n_abc   | ...x1y2z
-- 2  | Business B | wh_n8n_xyz   | ...a3b4c
-- 3  | Business C | wh_n8n_def   | ...m5n6p
```

### Test tenant isolation security:

```bash
# Try to access Business 2's secret while logged in as Business 1
# This should return Business 1's secret, NOT Business 2's
curl -X GET https://prosaas.pro/api/business/settings/webhook-secret \
  -H "Cookie: session=BUSINESS1_SESSION"

# Should return Business 1's masked secret only
```

## 4. Test n8n Integration

### Setup in n8n:

1. Create HTTP Request node in n8n
2. Configure:
   ```
   URL: https://your-webhook-endpoint.com
   Method: POST
   Headers:
     X-Webhook-Secret: wh_n8n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0b7
   ```

3. Test the workflow
4. Verify webhook receives the request with correct header

### Verify on server side:

```python
# In your webhook handler (example)
from flask import request

@app.route('/your-webhook-endpoint', methods=['POST'])
def webhook_handler():
    # Get secret from header
    provided_secret = request.headers.get('X-Webhook-Secret')
    
    # Get business secret from database
    business = Business.query.filter_by(id=business_id).first()
    expected_secret = business.webhook_secret
    
    # Validate
    if provided_secret != expected_secret:
        return jsonify({"error": "Invalid webhook secret"}), 403
    
    # Process webhook
    return jsonify({"ok": True})
```

## 5. UI Testing

### Access Settings Page:

1. Login as admin/owner/manager
2. Navigate to: Settings → Integrations tab
3. Scroll to "WhatsApp Webhook Secret" section

### Test Generate Flow:

1. Click "צור Secret" button
2. Confirmation modal appears
3. Click "צור" to confirm
4. Full secret displays: `wh_n8n_...`
5. Yellow warning banner appears
6. Copy button is enabled
7. Click Copy → Toast: "✅ הועתק ללוח"
8. Paste into n8n
9. Refresh page
10. Only masked secret shows: `wh_n8n_****...b7`
11. Copy button is hidden

### Test Rotate Flow:

1. When secret already exists
2. Button text: "סובב Secret"
3. Click button
4. Modal warning: "תשבור workflows קיימים"
5. Click "סובב"
6. New secret generated
7. Old secret invalidated
8. Update n8n workflows with new secret

## 6. Troubleshooting

### Migration didn't run:

```bash
# Manually run migration
python -m server.db_migrate

# Check logs for errors
tail -f /var/log/prosaasil/app.log
```

### Routes not accessible:

```bash
# Check if Flask app is running
ps aux | grep python | grep run_server

# Check Flask logs
tail -f /var/log/prosaasil/flask.log

# Restart Flask if needed
sudo systemctl restart prosaasil
```

### UI not showing section:

```bash
# Check if frontend built correctly
cd /path/to/prosaasil/client
npm run build

# Check browser console for errors
# Open DevTools → Console
```

## 7. Security Checklist

- [ ] Migration 47 ran successfully
- [ ] Unique constraint on webhook_secret exists
- [ ] GET endpoint never returns full secret
- [ ] POST endpoint requires authentication
- [ ] Only admin/owner/manager can access endpoints
- [ ] Each business has unique secret
- [ ] Tenant isolation enforced (no cross-business access)
- [ ] Full secret shown only once after rotation
- [ ] Secrets not logged in plain text
- [ ] nginx routes correctly to Flask app

## 8. Success Criteria

✅ **Migration Success:**
- Column exists in database
- Unique constraint enforced
- No data loss during migration

✅ **API Success:**
- GET returns JSON (not HTML)
- POST generates unique secret
- Authentication enforced
- Proper error responses (401, 403, 404)

✅ **Tenant Isolation Success:**
- Different businesses get different secrets
- Cross-business access blocked
- Session-based business context works

✅ **UI Success:**
- Section visible in Settings → Integrations
- Generate/Rotate buttons work
- Copy functionality works
- Confirmation modals appear
- One-time reveal works correctly

✅ **n8n Integration Success:**
- Webhook receives X-Webhook-Secret header
- Server validates secret correctly
- Invalid secrets rejected (403)
