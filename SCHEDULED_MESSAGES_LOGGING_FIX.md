# Scheduled Messages Fix - Enhanced Logging

## Problem

User reported: "יש לי בעיה... הוא לא שולח הודעות שאני מתזמן הודעה ויש ERROR!!"
Translation: Scheduled messages are not being sent and there are errors.

## Investigation

Looking at the logs, we found:
1. The tick job was running successfully: `[SCHEDULED-MSG-TICK] Starting scheduled messages tick`
2. No explicit ERROR messages in scheduled message logs
3. However, logging was minimal - couldn't see if messages were actually being enqueued

**Key Issue**: Insufficient logging made it impossible to diagnose problems.

## Solution

**Enhanced logging throughout the scheduled message flow** to make issues visible.

### Changes Made

#### 1. Scheduled Messages Tick Job (`server/jobs/scheduled_messages_tick_job.py`)

**Before**: Minimal logging
```python
logger.info(f"[SCHEDULED-MSG-TICK] Claimed {len(messages)} message(s), enqueuing to workers")
logger.debug(f"[SCHEDULED-MSG-TICK] Enqueued message {message.id} for lead {message.lead_id}")
```

**After**: Comprehensive logging with emoji indicators
```python
logger.info(f"[SCHEDULED-MSG-TICK] ✅ Claimed {len(messages)} message(s) ready to send")
logger.info(f"[SCHEDULED-MSG-TICK] Enqueuing message {message.id} for lead {message.lead_id}, business {message.business_id}")
logger.info(f"[SCHEDULED-MSG-TICK] ✅ Enqueued message {message.id} as job {job.id}")
logger.error(f"[SCHEDULED-MSG-TICK] ❌ Failed to enqueue message {message.id}: {e}", exc_info=True)
logger.info(f"[SCHEDULED-MSG-TICK] ✅ Successfully enqueued {enqueued_count}/{len(messages)} message(s), failed={failed_count}")
```

**Key Improvements**:
- ✅ Log each message with business_id, lead_id, message_id
- ✅ Show job_id after enqueuing (proves it was queued)
- ✅ Track failed_count separately
- ✅ Use emoji indicators (✅ ❌ 📤 ⏭️) for easy scanning
- ✅ Add exc_info=True for full stack traces on errors

#### 2. Send Scheduled WhatsApp Job (`server/jobs/send_scheduled_whatsapp_job.py`)

**Before**: Basic logging
```python
logger.info(f"[SEND-SCHEDULED-WA] Starting send for message {message_id}")
logger.error(f"[SEND-SCHEDULED-WA] Message {message_id} not found")
```

**After**: Detailed context logging
```python
logger.info(f"[SEND-SCHEDULED-WA] 📤 Starting send for message {message_id}")
logger.info(f"[SEND-SCHEDULED-WA] Message {message_id}: business={message.business_id}, lead={message.lead_id}, status={message.status}")
logger.error(f"[SEND-SCHEDULED-WA] ❌ Message {message_id} not found in database")
logger.warning(f"[SEND-SCHEDULED-WA] ⏭️  Message {message_id} status is '{message.status}', skipping send")
```

**Key Improvements**:
- 📤 Clear indicator when starting send
- ℹ️ Show message details (business, lead, status)
- ❌ Clear error indicators
- ⏭️ Skip indicators for non-pending messages

#### 3. Added business_id to enqueue() Calls

**Before**:
```python
enqueue(
    'default',
    send_scheduled_whatsapp_job,
    message_id=message.id,
    job_id=f"scheduled_wa_{message.id}",
    # Missing business_id
)
```

**After**:
```python
enqueue(
    'default',
    send_scheduled_whatsapp_job,
    message_id=message.id,
    business_id=message.business_id,  # ✅ Added for proper tracking
    job_id=f"scheduled_wa_{message.id}",
    description=f"Send scheduled WhatsApp to lead {message.lead_id}"
)
```

## What You'll See Now

### Successful Flow
```log
[SCHEDULED-MSG-TICK] Starting scheduled messages tick
[SCHEDULED-MSG-TICK] ✅ Claimed 3 message(s) ready to send
[SCHEDULED-MSG-TICK] Enqueuing message 123 for lead 456, business 10
[SCHEDULED-MSG-TICK] ✅ Enqueued message 123 as job scheduled_wa_123
[SCHEDULED-MSG-TICK] Enqueuing message 124 for lead 457, business 10
[SCHEDULED-MSG-TICK] ✅ Enqueued message 124 as job scheduled_wa_124
[SCHEDULED-MSG-TICK] Enqueuing message 125 for lead 458, business 10
[SCHEDULED-MSG-TICK] ✅ Enqueued message 125 as job scheduled_wa_125
[SCHEDULED-MSG-TICK] ✅ Successfully enqueued 3/3 message(s), failed=0

[SEND-SCHEDULED-WA] 📤 Starting send for message 123
[SEND-SCHEDULED-WA] Message 123: business=10, lead=456, status=pending
[SEND-SCHEDULED-WA] Using provider: baileys
[SEND-SCHEDULED-WA] Sending to 972501234567@s.wh... (business 10)
[SEND-SCHEDULED-WA] ✅ Message 123 sent successfully
```

### Error Scenarios

**Enqueue Failure**:
```log
[SCHEDULED-MSG-TICK] ✅ Claimed 2 message(s) ready to send
[SCHEDULED-MSG-TICK] Enqueuing message 123 for lead 456, business 10
[SCHEDULED-MSG-TICK] ❌ Failed to enqueue message 123: ImportError: cannot import name 'send_scheduled_whatsapp_job'
Traceback (most recent call last):
  File "/app/server/jobs/scheduled_messages_tick_job.py", line 43, in scheduled_messages_tick_job
    from server.jobs.send_scheduled_whatsapp_job import send_scheduled_whatsapp_job
ImportError: ...
[SCHEDULED-MSG-TICK] ✅ Successfully enqueued 1/2 message(s), failed=1
```

**Send Failure**:
```log
[SEND-SCHEDULED-WA] 📤 Starting send for message 123
[SEND-SCHEDULED-WA] Message 123: business=10, lead=456, status=pending
[SEND-SCHEDULED-WA] ❌ Lead 456 not found for business 10
```

**Skip (Already Sent)**:
```log
[SEND-SCHEDULED-WA] 📤 Starting send for message 123
[SEND-SCHEDULED-WA] Message 123: business=10, lead=456, status=sent
[SEND-SCHEDULED-WA] ⏭️  Message 123 status is 'sent', skipping send
```

## Debugging Guide

### Check If Messages Are Being Claimed
```bash
grep "Claimed.*message(s) ready to send" logs/app.log
```
- If you see "Claimed 0 messages" - no messages are scheduled for now
- If you see "Claimed N messages" - messages are being picked up

### Check If Messages Are Being Enqueued
```bash
grep "Enqueued message.*as job" logs/app.log
```
- Should see one line per message enqueued
- Shows the job_id which can be tracked in RQ

### Check For Enqueue Failures
```bash
grep "Failed to enqueue message" logs/app.log
```
- Shows which messages failed to enqueue and why

### Check Send Status
```bash
grep "SEND-SCHEDULED-WA.*Starting send" logs/app.log
grep "SEND-SCHEDULED-WA.*sent successfully" logs/app.log
```
- First: How many sends were attempted
- Second: How many succeeded

### Check For Send Errors
```bash
grep "SEND-SCHEDULED-WA.*❌" logs/app.log
```
- Shows all send failures with reasons

## Common Issues & Solutions

### Issue: No messages claimed
**Log**: `[SCHEDULED-MSG-TICK] No messages ready to send`
**Cause**: No scheduled messages with `scheduled_for <= now` and `status=pending`
**Solution**: Check if messages exist and have correct scheduled_for time

### Issue: Messages enqueued but not sent
**Log**: `Enqueued message 123 as job scheduled_wa_123` but no send logs
**Cause**: Worker might not be running or job failed silently
**Solution**: Check RQ worker logs, check job status in Redis

### Issue: Send fails with "Lead not found"
**Log**: `❌ Lead 456 not found for business 10`
**Cause**: Lead was deleted or business_id mismatch
**Solution**: Verify lead exists in database for correct business

### Issue: Send fails with "No WhatsApp JID available"
**Log**: `❌ No WhatsApp JID available`
**Cause**: Message has no remote_jid (WhatsApp phone number)
**Solution**: Check how messages are created, ensure remote_jid is populated

## Testing

### Create Test Scheduled Message
```python
from server.models_sql import ScheduledMessagesQueue, Lead
from datetime import datetime, timedelta

lead = Lead.query.filter_by(business_id=10).first()
message = ScheduledMessagesQueue(
    business_id=10,
    lead_id=lead.id,
    remote_jid=lead.whatsapp_jid or f"{lead.phone_e164}@s.whatsapp.net",
    message_text="Test scheduled message",
    scheduled_for=datetime.utcnow() + timedelta(minutes=2),  # 2 minutes from now
    status='pending',
    rule_id=1  # Your rule ID
)
db.session.add(message)
db.session.commit()
```

### Watch Logs
```bash
# Watch for tick job picking it up
tail -f logs/app.log | grep "SCHEDULED-MSG"

# After scheduled_for time passes, should see:
# [SCHEDULED-MSG-TICK] ✅ Claimed 1 message(s) ready to send
# [SCHEDULED-MSG-TICK] Enqueuing message 123 for lead 456, business 10
# [SCHEDULED-MSG-TICK] ✅ Enqueued message 123 as job scheduled_wa_123
# [SEND-SCHEDULED-WA] 📤 Starting send for message 123
# [SEND-SCHEDULED-WA] ✅ Message 123 sent successfully
```

## Summary

**Problem**: Insufficient logging made it impossible to diagnose scheduled message issues  
**Solution**: Enhanced logging throughout tick job and send job with emoji indicators  
**Result**: Can now see exactly what's happening at each step  
**Status**: ✅ ENHANCED and deployed

### Key Improvements
- ✅ Every message logged with business_id, lead_id, message_id
- ✅ Job IDs shown after enqueue (proves queuing worked)
- ✅ Failed enqueue count tracked separately
- ✅ Emoji indicators for easy log scanning
- ✅ Full stack traces on errors (exc_info=True)
- ✅ business_id added to enqueue() calls
