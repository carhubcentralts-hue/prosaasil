# Deployment Instructions - immediate_message Fix

## Overview
This fix resolves the `TypeError: update_rule() got an unexpected keyword argument 'immediate_message'` error that occurs when updating scheduled message rules.

## Pre-Deployment Checklist
- [x] Code changes committed to branch
- [x] Tests created and passing
- [x] Documentation written
- [ ] Database migration ready to run
- [ ] Backup taken (if deploying to production)

## Deployment Steps

### Step 1: Apply Code Changes
The code changes are already in the branch `copilot/optimize-whatsapp-webhook`:
- `server/models_sql.py`
- `server/services/scheduled_messages_service.py`
- `server/routes_scheduled_messages.py`
- `migration_add_immediate_message.py`

```bash
# If not already on the branch:
git checkout copilot/optimize-whatsapp-webhook
git pull origin copilot/optimize-whatsapp-webhook
```

### Step 2: Run Database Migration
```bash
# Make sure you're in the project directory
cd /path/to/prosaasil

# Activate virtual environment (if using one)
source .venv/bin/activate  # or your venv path

# Run the migration
python migration_add_immediate_message.py
```

Expected output:
```
🔧 Running immediate_message migration...
✅ Migration completed successfully

ℹ️  immediate_message column added to scheduled_message_rules table
   This allows separate messages for immediate send vs delayed steps
   If not set, message_text will be used for backward compatibility
```

### Step 3: Restart Backend Services
```bash
# Restart the backend server
# The exact command depends on your deployment setup:

# Option 1: Docker Compose
docker-compose restart backend

# Option 2: Systemd service
sudo systemctl restart prosaasil-backend

# Option 3: Manual process
# Kill the old process and start new one
pkill -f "python.*server"
python run_server.py
```

### Step 4: Verify Deployment
1. Check that the server starts without errors:
   ```bash
   # Check logs
   tail -f /path/to/logs/backend.log
   # or
   docker-compose logs -f backend
   ```

2. Verify the database column exists:
   ```sql
   \d scheduled_message_rules
   -- Should show immediate_message column
   ```

3. Test the API endpoint:
   ```bash
   # Update a rule with immediate_message parameter
   curl -X PATCH http://localhost:5000/api/scheduled-messages/rules/5 \
     -H "Content-Type: application/json" \
     -H "Cookie: session=..." \
     -d '{
       "send_immediately_on_enter": true,
       "immediate_message": "Hello!"
     }'
   ```

4. Check for the specific error in logs - it should NOT appear anymore:
   ```bash
   # This error should no longer occur:
   # TypeError: update_rule() got an unexpected keyword argument 'immediate_message'
   ```

## Rollback Plan (If Needed)
If something goes wrong:

### Step 1: Revert Code Changes
```bash
git checkout main  # or your previous branch
git pull origin main
```

### Step 2: Restart Services
```bash
# Restart with old code
docker-compose restart backend
# or your restart command
```

### Step 3: Remove Database Column (Optional)
**⚠️ Only if you need to fully rollback and the column is causing issues:**
```sql
ALTER TABLE scheduled_message_rules DROP COLUMN immediate_message;
```

**Note**: Since the column is nullable and the old code uses `getattr()`, the column can safely remain in the database even with old code.

## Post-Deployment Testing

### Test Case 1: Create Rule with Immediate Message
```json
POST /api/scheduled-messages/rules
{
  "name": "Welcome Message",
  "message_text": "",
  "status_ids": [1],
  "send_immediately_on_enter": true,
  "immediate_message": "Welcome! We'll contact you soon.",
  "delay_seconds": 0,
  "steps": [
    {
      "step_index": 1,
      "message_template": "Follow-up message after 1 hour",
      "delay_seconds": 3600,
      "enabled": true
    }
  ]
}
```

Expected: ✅ Rule created successfully, no errors

### Test Case 2: Update Rule with Immediate Message
```json
PATCH /api/scheduled-messages/rules/5
{
  "immediate_message": "Updated immediate message"
}
```

Expected: ✅ Rule updated successfully, no `TypeError`

### Test Case 3: Verify Backward Compatibility
```json
PATCH /api/scheduled-messages/rules/4
{
  "name": "Updated Name"
}
```

Expected: ✅ Old rules without immediate_message still work

## Monitoring
After deployment, monitor for:
- ✅ No `TypeError` about `immediate_message` in logs
- ✅ Scheduled messages API endpoints respond successfully
- ✅ Immediate messages are sent with correct content
- ✅ Step messages still work as expected

## Success Criteria
The deployment is successful when:
1. ✅ Migration completes without errors
2. ✅ Server starts and runs without errors
3. ✅ The original `TypeError` no longer appears in logs
4. ✅ Users can update rules with `immediate_message` parameter
5. ✅ Old rules continue to work without modification
6. ✅ New immediate messages are sent correctly

## Support
If you encounter issues:
1. Check the logs for error messages
2. Verify the migration ran successfully
3. Ensure the database column exists
4. Test with a simple API call
5. Review `FIX_SUMMARY_IMMEDIATE_MESSAGE.md` for technical details

---

**Estimated Deployment Time**: 5-10 minutes
**Downtime Required**: 30-60 seconds (for server restart)
**Risk Level**: Low (backward compatible changes)
