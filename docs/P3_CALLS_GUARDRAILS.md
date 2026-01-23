# P3 Calls Guardrails - MAX_ACTIVE_CALLS Configuration

## Overview

The P3 Calls Guardrails system provides production-grade capacity management for real-time phone calls. It uses a Redis-based counter to track active calls and reject new calls when the system reaches capacity, preventing overload and ensuring service stability.

## How It Works

### Architecture

1. **Redis-based Counter**: Uses Redis Set to track active call IDs
2. **TTL Safety Net**: Each call has a 2-hour TTL to prevent stuck slots
3. **Fail-Safe Behavior**: If Redis is unavailable, calls are allowed (fail-open)
4. **Graceful Rejection**: Capacity-exceeded calls receive a polite Hebrew message

### Call Flow

```
1. Incoming Call → Twilio Webhook
2. Check Capacity: try_acquire_call_slot(call_id)
   ├─ At Capacity (≥15) → Reject with TwiML message
   └─ Under Capacity → Proceed normally
3. Call Processing...
4. Call Ends → release_call_slot(call_id) in finally block
```

### Entry Points

The capacity check is integrated at two critical points:

1. **Twilio Webhook** (`/webhook/incoming_call`): Before creating CallLog
2. **WebSocket Handler** (`MediaStreamHandler.run()`): In finally block for release

### Rejection Behavior

When capacity is reached, callers hear:
> "המערכת עמוסה כרגע. אנא נסו שוב בעוד מספר דקות או שלחו לנו הודעה בוואטסאפ."
> 
> Translation: "The system is currently busy. Please try again in a few minutes or send us a WhatsApp message."

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Maximum concurrent active calls (default: 15 in production, 50 in dev)
MAX_ACTIVE_CALLS=15

# Behavior when capacity reached (default: reject)
# Future options: voicemail, whatsapp
CALLS_OVER_CAPACITY_BEHAVIOR=reject

# Log level for capacity events (default: WARNING)
CALLS_CAPACITY_LOG_LEVEL=WARNING
```

### Increasing Capacity

To handle more concurrent calls, simply update the environment variable:

```bash
# For 25 concurrent calls
MAX_ACTIVE_CALLS=25

# For 40 concurrent calls
MAX_ACTIVE_CALLS=40

# For 80 concurrent calls
MAX_ACTIVE_CALLS=80
```

**No code changes required!** Just restart the calls service.

### Production Defaults

If `MAX_ACTIVE_CALLS` is not set:
- **Production** (`PRODUCTION=1`): Defaults to 15
- **Development** (`PRODUCTION=0`): Defaults to 50

## Monitoring

### Health Endpoint

Check current capacity status:

```bash
curl http://localhost:5050/health/details
```

Response:
```json
{
  "status": "ok",
  "active_calls": 8,
  "max_calls": 15,
  "capacity_available": 7,
  "at_capacity": false
}
```

### Logs

Capacity events are logged at the configured level:

```
[CAPACITY] ACQUIRED call_id=CA1234 active_calls=8/15
[CAPACITY] REJECTED call_id=CA5678 active_calls=15 max=15
[CAPACITY] RELEASED call_id=CA1234 active_calls=7/15
```

## Safety Features

### 1. TTL Safety Net

Each call slot has a 2-hour TTL. If a call crashes without releasing its slot, Redis automatically cleans it up after 2 hours.

### 2. Fail-Open Behavior

If Redis is unavailable, the system allows calls to proceed rather than rejecting them. This prevents cascading failures.

### 3. Idempotent Release

`release_call_slot()` can be called multiple times safely. It's always called in a `finally` block to ensure cleanup.

### 4. Database Logging

Rejected calls are logged to the database with status `rejected_capacity` for analysis and monitoring.

## Cleanup Maintenance (Optional)

While TTL handles automatic cleanup, you can manually trigger cleanup:

```python
from server.services.calls_capacity import cleanup_expired_slots

# Remove expired slots that somehow remained in the active set
cleaned_count = cleanup_expired_slots()
print(f"Cleaned up {cleaned_count} expired slots")
```

## Scaling Strategy

### Short-term (ENV-only)

1. Monitor `/health/details` to see capacity usage
2. If frequently at capacity, increase `MAX_ACTIVE_CALLS`
3. Restart calls service

### Long-term (Code changes)

For larger scale (100+ concurrent calls):
1. Consider splitting calls service across multiple instances
2. Implement load balancing
3. Add more sophisticated queueing/voicemail

## Troubleshooting

### Slots Not Released

**Symptom**: Active calls count stays high after calls end

**Fix**: Check that:
1. `call_status` webhook is configured in Twilio
2. WebSocket finally blocks are executing
3. Redis is accessible

### False Rejections

**Symptom**: Calls rejected even when under capacity

**Check**:
```bash
# Get active calls count
redis-cli SCARD calls:active

# List active call IDs
redis-cli SMEMBERS calls:active

# Check TTL of a specific call
redis-cli TTL calls:active:CAxxxxxxxxxxxxxxxxxxxxxx
```

### Redis Connection Issues

**Symptom**: Logs show Redis errors

**Expected Behavior**: System fails open - calls proceed despite errors

**Fix**: Check `REDIS_URL` environment variable and Redis service status

## Implementation Files

- **Module**: `server/services/calls_capacity.py`
- **Integration**: `server/routes_twilio.py` (acquire)
- **Release**: `server/media_ws_ai.py` (finally block)
- **Config**: `.env.example` (documentation)
- **Health**: `/health/details` endpoint

## Future Enhancements

### Voicemail Mode (Future)

```bash
CALLS_OVER_CAPACITY_BEHAVIOR=voicemail
```

Redirect to voicemail recording instead of rejecting.

### WhatsApp Redirect (Future)

```bash
CALLS_OVER_CAPACITY_BEHAVIOR=whatsapp
```

Send WhatsApp invitation link instead of rejecting.

### Per-Business Limits (Future)

Allow different limits per business/tenant.

## Summary

The P3 Calls Guardrails system provides:

✅ **Predictable capacity**: Max 15 concurrent calls (configurable)
✅ **Graceful degradation**: Polite rejection message
✅ **Safety nets**: TTL cleanup, fail-open behavior  
✅ **Easy scaling**: Single ENV variable change
✅ **Production-ready**: Comprehensive logging and monitoring

**Remember**: Increasing capacity is just one ENV change + restart!
