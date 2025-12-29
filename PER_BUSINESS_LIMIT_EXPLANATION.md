# BulkCall Concurrency - Per Business Limit

## ✅ CORRECT Behavior (What the code does)

```
System: Multiple businesses can use bulk queue simultaneously

Business A (ID=1):          Business B (ID=2):          Business C (ID=3):
├─ Call 1 ✅               ├─ Call 1 ✅               ├─ Call 1 ✅
├─ Call 2 ✅               ├─ Call 2 ✅               ├─ Call 2 ✅
├─ Call 3 ✅               ├─ Call 3 ✅               ├─ Call 3 ✅
└─ Call 4 ⏳ (waiting)     └─ Call 4 ⏳ (waiting)     └─ Call 4 ⏳ (waiting)

Total active: 9 calls ✅
Each business: max 3 calls ✅
```

## Code Implementation

```python
# In fill_queue_slots_for_job() and process_bulk_call_run():

# Line 1720 - Counts ONLY for THIS business
business_active_outbound = count_active_outbound_calls(run.business_id)
                                                       ^^^^^^^^^^^^^^
                                                       Specific business!

# Line 1723 - Checks THIS business limit
while ... and business_active_outbound < MAX_OUTBOUND_CALLS_PER_BUSINESS:
    # Start call for THIS business only
```

## In call_limiter.py

```python
# Line 55-56 - Filter by specific business_id
count = CallLog.query.filter(
    CallLog.business_id == business_id,  # ← Only THIS business!
    CallLog.direction == 'outbound',
    ...
).count()
```

## Example Scenario

**Setup:**
- Business A has 100 leads in queue
- Business B has 100 leads in queue
- Both start bulk calling at the same time

**What happens:**
```
Time 0s:
  Business A: Starts 3 calls → Total: 3 active
  Business B: Starts 3 calls → Total: 3 active
  System total: 6 calls ✅

Time 30s (some calls complete):
  Business A: 2 calls complete, starts 2 new → Total: 3 active
  Business B: 1 call completes, starts 1 new → Total: 3 active
  System total: 6 calls ✅

Time 60s:
  Business A: Still processing, 3 active
  Business B: Still processing, 3 active
  System total: 6 calls ✅

...continues until all 200 leads are called
```

## Database Query Verification

```sql
-- During multi-business bulk calling:
SELECT 
    business_id,
    COUNT(*) as active_calls
FROM outbound_call_jobs
WHERE status IN ('dialing', 'calling')
GROUP BY business_id;

-- Expected output (multiple businesses calling):
-- business_id | active_calls
-- ------------|-------------
--      1      |      3       ✅
--      2      |      3       ✅
--      5      |      2       ✅ (2 is < 3, so OK)
--     12      |      3       ✅
-- 
-- Each business ≤ 3 calls ✅
-- System total: 11 calls ✅ (perfectly fine!)
```

## Key Points

1. **Per-Business Limit**: `count_active_outbound_calls(business_id)` filters by business
2. **Independent Queues**: Each business's queue runs independently
3. **No Global Limit**: System can handle many businesses × 3 calls each
4. **SSOT**: All limiting logic in `call_limiter.py` with `business_id` parameter

## ❌ What Would Be WRONG (Not implemented)

```python
# WRONG - Global limit across all businesses:
global_active = CallLog.query.filter(
    CallLog.direction == 'outbound',
    # NO business_id filter!  ❌
).count()

if global_active >= 3:  # ❌ Wrong! Would limit entire system to 3
    return "Cannot start call"
```

**This is NOT what we implemented.** ✅ We correctly use per-business filtering.
