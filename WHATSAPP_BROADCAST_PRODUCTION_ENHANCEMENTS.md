# WhatsApp Broadcast Production Enhancements

## Overview
This document describes the 8 production-grade enhancements implemented for the WhatsApp broadcast system to ensure stability, reliability, and proper error handling.

## Enhancements Implemented

### 1. ✅ Separate Clear Statuses
**Status Progression:**
- `accepted` - API received and validated the broadcast request
- `queued` - Broadcast entered the processing queue  
- `running` - Worker is actively sending messages
- `sent` - Message successfully sent to WhatsApp provider
- `delivered` - Message delivered to recipient (when available from provider)
- `failed` - Message failed to send (with error reason)
- `partial` - Some messages sent, some failed
- `completed` - All messages processed successfully

**Implementation:**
- Updated `WhatsAppBroadcast` model with clear status field
- Updated `WhatsAppBroadcastRecipient` model with status progression
- Added `delivered_at` timestamp for delivery tracking
- Broadcast starts with `accepted` status
- Worker progresses through `queued` → `running` → `completed/failed/partial`

### 2. ✅ Real Proof = queued_count + broadcast_id + items[]
**Response includes:**
```json
{
  "success": true,
  "broadcast_id": 123,
  "queued_count": 50,
  "total_recipients": 50,
  "sent_count": 0,
  "job_id": "broadcast_123",
  "items": [
    {"phone": "+972...", "lead_id": 1, "status": "queued"},
    ...
  ],
  "invalid_recipients_count": 2
}
```

**Implementation:**
- Return items[] array with up to 100 recipient details
- Never return success without queued_count > 0
- UI checks items.length to verify actual queuing
- Include invalid_recipients_count for transparency

### 3. ✅ Idempotency to Prevent "Sent Twice"
**How it works:**
- Generate `idempotency_key` from: message + recipients + tenant_id + time_bucket(5min)
- Hash with SHA256, store in database
- Check for existing broadcast with same key within 10 minutes
- If exists, return existing broadcast_id instead of creating duplicate

**Implementation:**
- Added `idempotency_key` field to `WhatsAppBroadcast` model
- Check before creating new broadcast
- Return existing broadcast with `idempotent: true` flag
- Prevents duplicate sends from double-clicks or page refreshes

### 4. ✅ Baileys Not Connected Blocks Sending
**Connection Check:**
- Before creating broadcast, check Baileys status
- If `connected: false`, return 503 Service Unavailable
- Error code: `WHATSAPP_NOT_CONNECTED`
- Message: "WhatsApp לא מחובר. יש להתחבר תחילה"

**Implementation:**
- Call `/whatsapp/business_{id}/status` before broadcast creation
- Timeout: 5 seconds
- If not connected, reject with clear error
- If check fails (timeout), continue anyway (fail-open for reliability)

### 5. ✅ Phone Normalization + Validation
**Validation Process:**
1. Remove all non-digits
2. Check minimum length (9 digits)
3. Add country code if missing (+972 for Israeli numbers)
4. Validate E.164 format: `^\+\d{10,15}$`
5. Track invalid phones with reasons

**Invalid Reasons:**
- `too_short` - Less than 9 digits
- `invalid_format` - Doesn't match E.164

**Implementation:**
- Normalize all phones to E.164 before storing
- Return `invalid_recipients_count` in response
- Log first 5 invalid phones for debugging
- If all phones invalid, return 400 with detailed error

### 6. 🔧 Worker Locks + Concurrency (TO BE IMPLEMENTED)
**Requirements:**
- Lock per WhatsApp session (tenant_id/session_id)
- Prevent multiple workers sending to same session
- Max 1-2 concurrent threads per session
- Use Redis locks or database row locks

**Planned Implementation:**
```python
# Pseudo-code
with session_lock(f"wa_session_{tenant_id}"):
    # Process broadcast for this session
    # Only one worker can enter at a time
```

### 7. 🔧 Observability Dashboard (TO BE IMPLEMENTED)
**Metrics to Track:**
- `pending_count` - Messages waiting to send
- `sent_last_5m` - Messages sent in last 5 minutes
- `failed_last_5m` - Messages failed in last 5 minutes
- `active_broadcasts` - Currently running broadcasts

**Planned Implementation:**
- Add endpoint: `GET /api/whatsapp/metrics`
- Return real-time metrics from database
- Cache for 10 seconds to reduce DB load
- Display in UI dashboard

### 8. 🔧 Acceptance Test - Partial Failure (TO BE IMPLEMENTED)
**Test Scenario:**
- Broadcast to 3 recipients
- 2 succeed, 1 fails
- UI must show:
  - Status: `partial`
  - Sent: 2
  - Failed: 1
  - Per-recipient status with failure reason

**Test Implementation:**
```python
def test_partial_broadcast_failure():
    # Create broadcast with 3 recipients
    # Mock: 2 succeed, 1 fails
    # Verify UI shows partial status
    # Verify per-recipient status visible
```

## Database Schema Changes

### WhatsAppBroadcast Table
```sql
ALTER TABLE whatsapp_broadcasts
ADD COLUMN idempotency_key VARCHAR(64);

CREATE INDEX idx_wa_broadcast_idempotency 
ON whatsapp_broadcasts(idempotency_key);
```

### WhatsAppBroadcastRecipient Table
```sql
ALTER TABLE whatsapp_broadcast_recipients
ADD COLUMN delivered_at TIMESTAMP;
```

## Migration Script
Run: `python migration_add_broadcast_enhancements.py`

## Testing Checklist

### Basic Functionality
- [ ] Single message send succeeds
- [ ] Broadcast to 3 recipients - all receive
- [ ] Disconnected Baileys blocks send with clear error
- [ ] Invalid phone numbers rejected with reason
- [ ] Duplicate broadcast prevented (idempotency)

### Status Tracking
- [ ] Broadcast status progresses: accepted → running → completed
- [ ] Recipient status shows: queued → sent → delivered/failed
- [ ] Failed recipients show error reason
- [ ] Partial failure shows correctly (some sent, some failed)

### Error Handling
- [ ] No recipients error shows detailed diagnostics
- [ ] Invalid phones error shows count and examples
- [ ] Connection error shows "WhatsApp not connected"
- [ ] Idempotent request returns existing broadcast

### Logging
- [ ] All logs include broadcast_id
- [ ] Logs show [WA_BROADCAST] and [WA_SEND] tags
- [ ] Logs show queued_count, sent_count, failed_count
- [ ] Invalid phones logged (first 5)

## Next Steps
1. Complete worker locks implementation (#6)
2. Add observability dashboard (#7)
3. Write comprehensive acceptance tests (#8)
4. Load test with 1000+ recipients
5. Monitor production metrics

## References
- Problem Statement: [Hebrew issue description]
- Original Implementation: routes_whatsapp.py lines 1673-2050
- Worker Implementation: services/broadcast_worker.py
- Models: models_sql.py lines 886-947
