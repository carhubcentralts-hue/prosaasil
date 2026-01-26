# WhatsApp Broadcast Unification - Deployment Guide

## Overview
This fix unifies WhatsApp message sending so that broadcasts use the exact same code path as regular sends (chat, lead page). This prevents HTTP 500 errors and retry loops.

## Changes Made

### 1. Created Unified Send Service ✅
**File:** `server/services/whatsapp_send_service.py`

- Single source of truth (SSOT) for all WhatsApp sends
- Handles phone normalization consistently
- Routes to correct provider (Baileys/Meta) based on business settings
- Context-aware retry logic
- Used by: chat, lead page, **broadcasts**

### 2. Updated Broadcast Worker ✅
**File:** `server/services/broadcast_worker.py`

**Changes:**
- Now uses `whatsapp_send_service.send_message()` instead of calling `BaileysProvider` directly
- Passes `context='broadcast'` to distinguish from regular sends
- Passes `retries=0` to disable provider-level retries (broadcast_worker handles retries)
- Continue-on-error: individual recipient failures don't kill entire job
- Consistent phone normalization using `normalize_whatsapp_to()`

### 3. Fixed Runtime Migration ✅
**Files:** 
- `migration_add_broadcast_cursor.py` (NEW)
- `server/jobs/broadcast_job.py` (FIXED)

**Problem:** `broadcast_job.py` was doing `ALTER TABLE` at runtime in production
**Solution:** Moved to proper migration file

### 4. Single Retry Layer ✅
**Before:** 
- Provider: 2 attempts
- Broadcast worker: 3 attempts
- Total: Up to 6 attempts per message!

**After:**
- Provider: 0 retries (when context='broadcast')
- Broadcast worker: 3 attempts
- Total: 3 attempts per message

## Deployment Steps

### 1. Run Database Migration
**CRITICAL:** This must be done before deploying the code!

```bash
# From the project root
python migration_add_broadcast_cursor.py
```

This adds the `last_processed_recipient_id` column to `whatsapp_broadcasts` table.

### 2. Deploy Code
Deploy the updated code with the following files:
- `server/services/whatsapp_send_service.py` (NEW)
- `server/services/broadcast_worker.py` (UPDATED)
- `server/jobs/broadcast_job.py` (UPDATED - removed ALTER TABLE)
- `migration_add_broadcast_cursor.py` (NEW)

### 3. Restart Workers
Restart the broadcast worker to pick up the changes:
```bash
# Restart RQ workers
# (Exact command depends on your deployment)
supervisorctl restart worker:*
# or
systemctl restart rq-worker
```

### 4. Test Broadcast
1. Create a small test broadcast (2-3 recipients)
2. Check logs for:
   - `[WA_SEND] broadcast_id=X` entries
   - Phone normalization: `to=+972... → jid=972...@s.whatsapp.net`
   - No HTTP 500 errors
   - No duplicate retries
3. Verify sent/failed counts update correctly

## What to Look For in Logs

### Good Signs ✅
```
[WA_SEND_SERVICE] business_id=1 to=+972501234567 → jid=972501234567@s.whatsapp.net source=to context=broadcast
✅ [WA_SEND] broadcast_id=123 to=972501234567 status=sent
```

### Bad Signs ❌
```
Baileys returned 500
WhatsApp not connected - QR code scan required
Failed after 2 attempts  # Provider retries (should be 0)
ALTER TABLE whatsapp_broadcasts  # Runtime migration (should not happen)
```

## Rollback Plan
If issues occur:

1. **Quick Fix:** Revert to previous code version
2. **Keep Migration:** The `last_processed_recipient_id` column is safe to keep
3. **Check Baileys:** Most likely issue is Baileys not connected - check QR code

## Verification Checklist
- [ ] Migration `migration_add_broadcast_cursor.py` ran successfully
- [ ] No errors during deployment
- [ ] Workers restarted successfully
- [ ] Test broadcast sends to 2+ recipients
- [ ] No HTTP 500 errors in logs
- [ ] No "ALTER TABLE" in runtime logs
- [ ] sent_count and failed_count update correctly
- [ ] Individual recipient failures don't stop entire broadcast

## Key Benefits

1. **Same Logic Everywhere:** Broadcast now uses identical code as regular sends
2. **No Duplicate Retries:** Single retry layer prevents retry storms
3. **Better Error Handling:** Individual failures don't kill entire broadcast
4. **Proper Migrations:** No more runtime schema changes
5. **Consistent Normalization:** All phone numbers normalized the same way

## Technical Details

### Phone Normalization
Uses `normalize_whatsapp_to()` from `server/utils/whatsapp_utils.py`:
- Input: `+972501234567` or `972501234567`
- Output: `972501234567@s.whatsapp.net`
- Validates: No groups (@g.us), broadcasts, or status updates

### Provider Selection
Based on `Business.whatsapp_provider` field:
- `baileys` → BaileysProvider (default)
- `meta` → MetaWhatsAppClient

### Context Parameter
- `context='broadcast'` → retries=0 at provider level
- `context='chat'` or `context='lead'` → retries=2 at provider level

## Support

If you encounter issues:
1. Check Baileys connection status: `/api/whatsapp/status`
2. Check logs for error patterns
3. Verify migration ran: Check if `last_processed_recipient_id` column exists
4. Test with single recipient first

## Success Metrics

After deployment, monitor:
- Broadcast completion rate
- HTTP 500 error rate (should be near 0)
- Average time per broadcast
- Recipient failure rate
- No runtime migrations in logs
