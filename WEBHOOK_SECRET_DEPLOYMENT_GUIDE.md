# Webhook Secret Deployment Guide

## Problem Fixed
The n8n webhook endpoint `/api/whatsapp/webhook/send` was defaulting to `business_id=1`, causing WhatsApp messages to fail when business_1 wasn't connected. Now it properly resolves the business from the webhook secret.

## Changes Made

### 1. Database Schema
- Added `webhook_secret` column to `business` table (VARCHAR(255), UNIQUE, NULLABLE)
- Created unique index for fast lookups

### 2. Webhook Route Logic
- `/api/whatsapp/webhook/send` now resolves business from `X-Webhook-Secret` header
- Returns 401 if secret is invalid or missing
- No default fallback to business_id=1
- Enhanced logging shows resolved business details

### 3. Status Check Fix
- Status endpoint now checks the correct business's connection (e.g., `business_6` instead of `business_1`)
- Uses resolved business_id from webhook secret

## Deployment Steps

### Step 1: Run Database Migration
```bash
# SSH into production server or run from backend container
cd /path/to/prosaasil
source .venv/bin/activate  # or use appropriate python environment
python migration_add_webhook_secret.py
```

Expected output:
```
🔧 Running webhook_secret migration...
✅ Migration completed successfully
ℹ️  To set webhook secret for a business, run:
   UPDATE business SET webhook_secret='wh_n8n_your_random_string' WHERE id=<business_id>;
```

### Step 2: Generate Webhook Secrets for Each Business

**CRITICAL:** Secrets must be ≥32 characters, random, and unique per business!

For each business that needs WhatsApp integration with n8n:

1. **Generate a secure random secret** (recommended method):

```bash
# Best practice: Use Python secrets module (cryptographically secure)
python -c "import secrets; print('wh_n8n_' + secrets.token_hex(16))"

# Alternative: Use OpenSSL
openssl rand -hex 16 | awk '{print "wh_n8n_" $1}'

# Example output: wh_n8n_a1b2c3d4e5f6789012345678abcdef01
```

2. **Update the business record:**

```sql
-- Example for business ID 6 (the one actually connected to WhatsApp)
UPDATE business 
SET webhook_secret = 'wh_n8n_a1b2c3d4e5f6789012345678abcdef01' 
WHERE id = 6;

-- Example for business ID 10
UPDATE business 
SET webhook_secret = 'wh_n8n_9f8e7d6c5b4a3210fedcba9876543210'
WHERE id = 10;
```

**IMPORTANT:** 
- ✅ Each business MUST have a unique secret
- ✅ Minimum 32 characters (wh_n8n_ prefix + 32 hex chars = 39 total)
- ✅ Use cryptographically secure random generator
- ❌ Never reuse secrets across businesses
- ❌ Never use predictable patterns (sequential numbers, dates, etc.)

### Step 3: Update n8n Workflow

In your n8n workflow that sends WhatsApp messages:

1. Update the HTTP Request node configuration:
   - URL: `https://prosaas.pro/api/whatsapp/webhook/send`
   - Method: `POST`
   - Headers:
     ```json
     {
       "Content-Type": "application/json",
       "X-Webhook-Secret": "wh_n8n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
     }
     ```
   - Body (JSON):
     ```json
     {
       "to": "+9725XXXXXXXX",
       "message": "Your message here"
     }
     ```

2. **REMOVE** the `business_id` field from the body - it's now automatically resolved from the secret!

### Step 4: Verify the Fix

Run this test from the server (or use curl):

```bash
curl -X POST "https://prosaas.pro/api/whatsapp/webhook/send" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: wh_n8n_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" \
  -d '{
    "to": "+9725XXXXXXXX",
    "message": "Test message from n8n webhook"
  }'
```

Expected response (success):
```json
{
  "ok": true,
  "provider": "baileys",
  "message_id": "3EB0...",
  "db_id": 123,
  "delivered": true,
  "status": "sent"
}
```

### Step 5: Check Logs

In the backend logs, you should now see (with SHA256 hash masking):

```
[WA_WEBHOOK] secret_hash=4ea862, resolved_business_id=6, resolved_business_name=My Business, provider=baileys
[WA_WEBHOOK] Using base_url=http://baileys:3300, tenant_id=business_6
[WA_WEBHOOK] Checking connection status: http://baileys:3300/whatsapp/business_6/status
[WA_WEBHOOK] Connection status: connected=True, active_phone=+9725XXXXXXXX, hasQR=False, last_seen=...
[WA_WEBHOOK] Sending message to +9725XXXXXXXX@s.whatsapp.net via baileys
[WA_WEBHOOK] ✅ Message sent successfully: db_id=123, provider_msg_id=3EB0...
```

**Note:** `secret_hash` is the first 6 characters of SHA256 hash for identification without exposing the actual secret.

## 🎯 Acceptance Checklist

Before marking the deployment as complete, verify ALL of these:

### Critical Success Criteria:

- [ ] **Migration ran successfully** - `webhook_secret` column exists in `business` table
- [ ] **Secrets are set** - Each business has a unique webhook_secret (≥32 chars)
- [ ] **n8n is updated** - Workflows use business-specific secrets in headers
- [ ] **business_id removed** - No `business_id` field in n8n request body

### Log Verification (MUST SEE):

- [ ] `resolved_business_id=<correct_id>` (NOT 1 unless that's the actual business)
- [ ] `resolved_business_name=<actual_business_name>`
- [ ] `tenant_id=business_<correct_id>`
- [ ] `status check: .../whatsapp/business_<correct_id>/status`
- [ ] `connected=True` (if business is actually connected)
- [ ] `✅ Message sent successfully`

### Negative Tests (MUST FAIL CORRECTLY):

- [ ] Invalid secret returns `401` with `"error_code": "invalid_webhook_secret"`
- [ ] Missing secret returns `401` with `"error_code": "missing_webhook_secret"`
- [ ] Empty secret returns `401`

### End-to-End Verification:

- [ ] Test message via curl succeeds
- [ ] Test message via n8n workflow succeeds
- [ ] **WhatsApp message is actually received by the end user** ⭐
- [ ] Message is saved in DB with correct business_id
- [ ] Logs show NO references to business_1 (unless that's the intended business)

### Security Verification:

- [ ] Secrets are NOT visible in logs (only 6-char SHA256 hash shown)
- [ ] Each business has a unique secret (no duplicates)
- [ ] Secrets are ≥32 characters
- [ ] No hardcoded secrets in code or configs

## 🚨 FAILURE MODES - If You See These, Fix Is NOT Working:

```
❌ [WA_WEBHOOK] business_id=1 ... resolved_business_id=1
   → Secret not resolving correctly, still using default

❌ status check: .../whatsapp/business_1/status
   → Using wrong business for status check

❌ connected=False (when business IS connected)
   → Checking wrong business's connection

❌ Full secret visible in logs
   → Secret masking not working

❌ {"ok": false, "error_code": "wa_not_connected"}
   → Wrong business or actually not connected
```

If you see ANY of these after deployment, the fix is NOT complete!

## Troubleshooting

### Issue: "Invalid webhook secret"
**Cause:** Secret in n8n doesn't match any business.webhook_secret in DB
**Fix:** Double-check the secret value in n8n and database

### Issue: connected=False in logs
**Cause:** The business is not actually connected to WhatsApp via Baileys
**Fix:** 
1. Go to WhatsApp settings in UI for that business
2. Scan QR code to connect
3. Verify `business_6` (or correct business) shows as connected

### Issue: Still using business_1
**Cause:** Migration not run or webhook_secret not set
**Fix:** Run migration and update business table

## Security Notes

1. **Keep webhook secrets private** - they grant access to send messages as that business
2. **Use long, random secrets** - at least 32 characters
3. **Rotate secrets periodically** - update both DB and n8n when rotating
4. **Never commit secrets** - store in environment variables or secure config management
5. **Monitor failed auth attempts** - check logs for unauthorized access

## Rollback Plan

If something goes wrong:

1. The `webhook_secret` column is nullable - old behavior won't break
2. To revert to env-based auth temporarily:
   ```python
   # In routes_whatsapp.py, temporarily restore old code
   expected_secret = os.getenv('WHATSAPP_WEBHOOK_SECRET')
   if webhook_secret != expected_secret:
       return 401
   business_id = data.get('business_id', 1)
   ```
3. Deploy the fix properly once issues are resolved

## Benefits of This Fix

✅ Correct business resolution - messages go through the right WhatsApp connection
✅ No hardcoded defaults - explicit error if secret is wrong
✅ Better security - per-business secrets instead of global secret
✅ Better logging - can trace exactly which business a webhook call is for
✅ Multi-tenant ready - different businesses can have different WhatsApp connections
