"""
BulkGate Integration Guide
==========================

This document shows how to integrate BulkGate into bulk operation endpoints.

## Pattern to Follow

For EVERY bulk operation endpoint, add this code at the START of the function:

```python
def bulk_operation_endpoint():
    # Get business_id and user_id
    business_id = get_current_business_id()  # or get_current_tenant()
    user_id = get_current_user_id()  # or user.get('id')
    
    # 🔥 USE BULK GATE: Check if enqueue is allowed
    try:
        import redis
        from rq import Queue
        REDIS_URL = os.getenv('REDIS_URL')
        redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
        
        if redis_conn:
            from server.services.bulk_gate import get_bulk_gate
            bulk_gate = get_bulk_gate(redis_conn)
            
            if bulk_gate:
                # Check if enqueue is allowed
                allowed, reason = bulk_gate.can_enqueue(
                    business_id=business_id,
                    operation_type='YOUR_OPERATION_TYPE',  # e.g., 'delete_leads_bulk'
                    user_id=user_id
                )
                
                if not allowed:
                    return jsonify({"error": reason}), 429
    except Exception as e:
        logger.warning(f"BulkGate check failed (proceeding anyway): {e}")
    
    # ... rest of endpoint code ...
    
    # After creating BackgroundJob and before enqueuing:
    if redis_conn and bulk_gate:
        # Acquire lock for this operation
        lock_acquired = bulk_gate.acquire_lock(
            business_id=business_id,
            operation_type='YOUR_OPERATION_TYPE',
            job_id=job.id
        )
        
        # Record the enqueue
        bulk_gate.record_enqueue(
            business_id=business_id,
            operation_type='YOUR_OPERATION_TYPE'
        )
    
    # Enqueue to RQ
    queue.enqueue(job_function, job.id, ...)
    
    return jsonify({"job_id": job.id}), 202
```

## Operation Types

Use these consistent operation_type values:

- `delete_leads_bulk` - Bulk delete leads
- `update_leads_bulk` - Bulk update leads
- `delete_receipts_all` - Delete all receipts
- `delete_imported_leads` - Delete imported leads
- `broadcast_whatsapp` - WhatsApp broadcast
- `export_receipts` - Export receipts
- `enqueue_outbound_calls` - Bulk outbound calls
- `recording_download` - Recording download

## Endpoints That Need Integration

1. ✅ `server/routes_receipts.py:delete_all_receipts()` - DONE
2. ❌ `server/routes_leads.py:bulk_delete_leads()` - TODO
3. ❌ `server/routes_leads.py:bulk_update_leads()` - TODO
4. ❌ `server/routes_outbound.py:bulk_delete_imported_leads()` - TODO
5. ❌ `server/routes_outbound.py:bulk_enqueue_outbound_calls()` - TODO
6. ❌ `server/routes_whatsapp.py:create_broadcast()` - TODO (if migrated)
7. ❌ `server/routes_calls.py:stream_recording()` - TODO (recording downloads)

## Recording Downloads - Special Case

For recording downloads (called frequently from UI), use stricter limits:

```python
if bulk_gate:
    allowed, reason = bulk_gate.can_enqueue(
        business_id=business_id,
        operation_type='recording_download',
        user_id=user_id,
        params_hash=call_sid  # Use call_sid as dedup key
    )
```

This prevents the same recording from being enqueued multiple times.

## Job Completion - Release Lock

When a job completes, release the lock:

```python
# In the job function (e.g., delete_leads_batch_job)
try:
    # ... process batches ...
    
    job.status = 'completed'
    db.session.commit()
    
finally:
    # Release BulkGate lock
    try:
        import redis
        from server.services.bulk_gate import get_bulk_gate
        REDIS_URL = os.getenv('REDIS_URL')
        redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
        
        if redis_conn:
            bulk_gate = get_bulk_gate(redis_conn)
            if bulk_gate:
                bulk_gate.release_lock(
                    business_id=job.business_id,
                    operation_type='YOUR_OPERATION_TYPE'
                )
    except Exception as e:
        logger.warning(f"Failed to release BulkGate lock: {e}")
```

## Testing

After integration, test:

1. **Rate limiting**: Try to enqueue >N operations per minute
   - Should get 429 with error message
   
2. **Active job lock**: Try to start same operation twice
   - Second attempt should get 429 with "פעולה פעילה כבר רצה"
   
3. **Deduplication**: Try to enqueue same params twice quickly
   - Should get 429 with "פעולה זהה כבר בוצעה"
   
4. **Lock release**: After job completes, should be able to start new job
   - Verify lock is released properly

## Configuration

Rate limits are configured in `BulkGate.RATE_LIMITS`:

```python
RATE_LIMITS = {
    'delete_leads_bulk': 2,           # Max 2 per minute
    'broadcast_whatsapp': 3,          # Max 3 per minute
    'recording_download': 10,         # Max 10 per minute
    # ... etc
}
```

Adjust these values based on production load patterns.
