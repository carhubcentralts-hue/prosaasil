# 🚀 Deployment Checklist - Scheduled Messages Fixes

## Pre-Deployment

### 1. Verify All Changes
- [x] Code changes committed
- [x] Tests created and passing (9/9 tests ✅)
- [x] Documentation complete
- [x] Syntax validated
- [x] Git history clean

### 2. Review Changes
```bash
# Review the changes
git log --oneline -4
git diff HEAD~3 HEAD --stat

# Key files modified:
# - server/models_sql.py (+1 line)
# - server/services/scheduled_messages_service.py (+16 lines)
# - server/routes_scheduled_messages.py (+4 lines)
# - migration_add_immediate_message.py (new file)
```

### 3. Backup Database (Production Only)
```bash
# Before running migration, backup the database
pg_dump -h <host> -U <user> <database> > backup_before_scheduled_messages_fix_$(date +%Y%m%d).sql
```

---

## Deployment Steps

### Step 1: Deploy Code
```bash
# Pull latest code on server
cd /path/to/prosaasil
git fetch origin
git checkout copilot/optimize-whatsapp-webhook
git pull origin copilot/optimize-whatsapp-webhook
```

### Step 2: Run Database Migration ⭐ UPDATED

**Option 1: Automatic - DB_MIGRATE (Recommended)**
```bash
# Run ALL migrations including Migration 124
python server/db_migrate.py
```

**Option 2: Standalone (Optional)**
```bash
# Run only the immediate_message migration
python migration_add_immediate_message.py
```

Expected output (both options will show similar results):
```
Migration 124: Adding immediate_message to scheduled_message_rules
✅ immediate_message column added
💡 Allows separate message for immediate send vs delayed steps
```

### Step 3: Restart Backend Services
```bash
# Restart the backend (adjust command based on your setup)

# Option 1: Docker Compose
docker-compose restart backend

# Option 2: Systemd
sudo systemctl restart prosaasil-backend

# Option 3: Manual
pkill -f "python.*server"
python run_server.py &
```

### Step 4: Verify Server Started
```bash
# Check logs for successful start
tail -f /path/to/logs/backend.log

# Look for:
# - No errors during startup
# - Server listening on port
# - Database connection successful
```

---

## Post-Deployment Testing

### Test 1: Update Scheduled Message Rule
**Action:** Update an existing rule via UI or API

**API Test:**
```bash
curl -X PATCH http://your-domain/api/scheduled-messages/rules/5 \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{
    "send_immediately_on_enter": true,
    "immediate_message": "שלום! הודעה מיידית"
  }'
```

**Expected Result:**
- ✅ Returns 200 OK
- ✅ No TypeError in response
- ✅ No errors in server logs

**Failure Signs:**
- ❌ 500 Internal Server Error
- ❌ TypeError about 'immediate_message' in logs

---

### Test 2: Change Lead Status
**Action:** Change a lead's status to trigger scheduled messages

**Steps:**
1. Go to a lead in the UI
2. Change the status to one that has a scheduled message rule
3. Check server logs immediately

**Expected Logs:**
```
[INFO] [SCHEDULED-MSG] Found 1 active rule(s) for lead X, status Y, token Z
[INFO] [SCHEDULED-MSG] Scheduled immediate message N for lead X
[INFO] [SCHEDULED-MSG] Created 2 scheduled task(s) for lead X, rule Y
[INFO] [SCHEDULED-MSG] Status change trigger complete: 2 total task(s) created for lead X
```

**Success Indicators:**
- ✅ "Found N active rule(s)" (N > 0)
- ✅ "Created M scheduled task(s)" (M > 0)
- ✅ NO "Failed to create tasks" errors
- ✅ NO TypeError about 'triggered_at'

**Failure Signs:**
- ❌ "0 total task(s) created"
- ❌ TypeError about 'triggered_at' in logs
- ❌ "Failed to create tasks for rule" error

---

### Test 3: Verify Scheduled Messages in Database
**Action:** Check that messages were actually scheduled

```sql
-- Check scheduled messages queue
SELECT 
    id,
    rule_id,
    lead_id,
    message_text,
    scheduled_for,
    status,
    created_at
FROM scheduled_messages_queue
WHERE status = 'pending'
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Result:**
- ✅ See new entries with status='pending'
- ✅ scheduled_for times look correct
- ✅ message_text contains the expected message

---

### Test 4: Wait for Message Send
**Action:** Wait for the scheduled time and verify message is sent

**Monitor:**
```bash
# Watch the worker logs
tail -f /path/to/logs/worker.log

# Look for:
# [SCHEDULED-MSG] Claimed N message(s) for sending
# [SCHEDULED-MSG] Marked message X as sent
```

**Check Database:**
```sql
-- Check that message status changed from 'pending' to 'sent'
SELECT id, status, sent_at, updated_at
FROM scheduled_messages_queue
WHERE id = <message_id>;
```

**Expected:**
- ✅ status changes to 'sent'
- ✅ sent_at timestamp populated
- ✅ Message appears in WhatsApp

---

## Monitoring (First 24 Hours)

### Key Metrics to Watch
1. **Error Rate:**
   - Monitor for TypeErrors in logs
   - Should be ZERO after deployment

2. **Message Creation Rate:**
   - Count "Created N scheduled task(s)" logs
   - Should be > 0 when statuses change

3. **Message Send Rate:**
   - Count "Marked message X as sent" logs
   - Should match pending messages over time

4. **User Reports:**
   - Check for complaints about messages not sending
   - Should be ZERO

### Log Patterns to Monitor

**Good Signs:**
```
[INFO] [SCHEDULED-MSG] Created N scheduled task(s)
[INFO] [SCHEDULED-MSG] Marked message X as sent
```

**Bad Signs (Should NOT appear):**
```
[ERROR] TypeError: unexpected keyword argument
[ERROR] Failed to create tasks for rule
[INFO] 0 total task(s) created  # When rules exist
```

---

## Rollback Plan (If Needed)

### If Critical Issues Occur

**Step 1: Revert Code**
```bash
git checkout <previous-commit-hash>
git push -f origin production  # If needed
```

**Step 2: Restart Services**
```bash
# Restart with old code
docker-compose restart backend
# or your restart command
```

**Step 3: Rollback Database (Optional)**
⚠️ **Only if the new column causes issues:**
```sql
ALTER TABLE scheduled_message_rules DROP COLUMN immediate_message;
```

**Note:** The column can safely remain even with old code because:
- It's nullable (no data requirement)
- Old code uses `getattr()` which handles missing attributes
- No breaking changes introduced

---

## Success Criteria

Deployment is successful when:

1. ✅ Server starts without errors
2. ✅ Migration completed successfully
3. ✅ Rules can be updated with immediate_message
4. ✅ Status changes create scheduled tasks (N > 0)
5. ✅ No TypeErrors in logs
6. ✅ Messages are sent at scheduled time
7. ✅ Users report messages are working
8. ✅ No error increase in monitoring

---

## Support

### Common Issues

**Issue:** Migration fails with "column already exists"
**Solution:** This is OK - migration is idempotent, column was already added

**Issue:** TypeError about 'immediate_message' still occurs
**Solution:** Server might not have restarted - restart backend services

**Issue:** TypeError about 'triggered_at' still occurs  
**Solution:** Old code is running - ensure latest code deployed and restarted

**Issue:** No tasks created (0 total task(s))
**Solution:** 
1. Check that rules exist for the status
2. Verify rules are active (is_active=True)
3. Check lead has valid WhatsApp JID or phone

---

## Quick Reference

### Files Modified
- `server/models_sql.py`
- `server/services/scheduled_messages_service.py`
- `server/routes_scheduled_messages.py`

### New Files
- `migration_add_immediate_message.py`

### Documentation
- `SCHEDULED_MESSAGES_FIXES_SUMMARY.md`
- `BEFORE_AFTER_SCHEDULED_MESSAGES.md`
- This checklist

### Test Files
- `test_immediate_message_fix.py`
- `test_triggered_at_fix.py`

---

## Final Verification

Before considering deployment complete:

- [ ] Migration ran successfully
- [ ] Server restarted successfully
- [ ] Rule update test passed
- [ ] Status change test passed
- [ ] Database shows pending messages
- [ ] At least one message sent successfully
- [ ] No errors in logs
- [ ] User confirms it's working

**When all checked:** 🎉 **Deployment Complete!** 🚀

---

**Estimated Deployment Time:** 10-15 minutes
**Downtime Required:** 30-60 seconds (for restart)
**Risk Level:** Low (backward compatible, well-tested)
