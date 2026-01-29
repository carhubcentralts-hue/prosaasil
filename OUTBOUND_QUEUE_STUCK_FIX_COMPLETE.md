# Fix Stuck Outbound Calls Queue - Complete Implementation Summary

## Problem Statement (Hebrew Original)
כרגע יש "Active queue found on mount" שחוזר מהשרת ולכן ה־UI ממשיך להציג פרוגרס לנצח.

**Translation:** Currently there's "Active queue found on mount" returning from server, causing UI to show progress bar forever.

## Root Cause Analysis

The issue occurred because:
1. **Backend**: Returned queues as "active" even when they were stuck/stale/finished
2. **Frontend**: No TTL checks, no exit conditions, continued polling indefinitely
3. **Worker**: Jobs could fail silently leaving queues in stuck state

## Solution Implementation

### Backend Changes (Iron Rule: Make "active" impossible to get stuck)

#### 1. Strict Active Queue Definition (`get_active_outbound_job`)
**File:** `server/routes_outbound.py`

Changed from accepting `status IN ('running', 'queued')` to requiring ALL conditions:
- ✅ `status = 'running'` (ONLY running, not queued)
- ✅ `cancel_requested = False` (NOT cancelled)
- ✅ `completed_at = None` (NOT finished)
- ✅ `ended_at = None` (NOT finished)
- ✅ `last_heartbeat_at < 15 minutes` (NOT stale)

**Result:** Only truly active queues are returned. This is the primary fix for the 2 stuck businesses.

#### 2. Auto-Finalize on Stale Detection
**File:** `server/routes_outbound.py`

When a queue exceeds 15-minute TTL:
```python
# Auto-mark as failed
run.status = 'failed'
run.ended_at = now
run.completed_at = now
run.last_error = "Queue stale - no activity for X minutes"

# Clean up pending jobs
UPDATE outbound_call_jobs SET status='failed' WHERE ...

# Return 404 (no active queue)
```

**Result:** Stuck queues automatically become "failed" after 15 minutes, progress bar disappears.

#### 3. Complete Auto-Finalize (`release_lock`)
**File:** `server/services/outbound_queue.py`

Updated to set BOTH timestamps:
```python
ended_at = now
completed_at = now  # NEW - prevents API from returning completed queues
```

**Result:** When worker finishes, queue is properly marked as complete.

#### 4. Smart Cancel Endpoint
**File:** `server/routes_outbound.py`

Enhanced `cancel_outbound_job` to detect stale queues:
```python
if time_since_activity > 15 minutes:
    # Force cancel immediately
    run.status = 'cancelled'
    run.completed_at = now
    # Cancel all pending jobs
else:
    # Graceful cancel (worker will shut down)
    run.cancel_requested = True
```

**Result:** Cancel button works even for stuck queues.

### Frontend Changes (Don't lock UI forever)

#### 1. Client-Side TTL Check
**File:** `client/src/pages/calls/OutboundCallsPage.tsx`

Added 10-minute client-side fail-safe:
```typescript
// Check if queue is stale on client
const lastActivity = new Date(activeQueue.last_activity);
const minutesSinceActivity = (Date.now() - lastActivity.getTime()) / (1000 * 60);
const isStale = minutesSinceActivity > 10;

if (activeQueue.status !== 'running' || isStale) {
  // Don't show progress bar
  return;
}
```

**Result:** Even if server malfunctions, client won't show stale queues.

#### 2. Max Polling Duration
**File:** `client/src/pages/calls/OutboundCallsPage.tsx`

Added 20-minute max polling duration:
```typescript
const MAX_POLL_DURATION_MS = 20 * 60 * 1000;
if (Date.now() - pollStartTime > MAX_POLL_DURATION_MS) {
  // Stop polling
  clearInterval(pollIntervalRef.current);
  setActiveRunId(null);
}
```

**Result:** Prevents infinite polling loops.

#### 3. Enhanced Error Handling
**File:** `client/src/pages/calls/OutboundCallsPage.tsx`

Polling stops on ANY error:
```typescript
catch (error) {
  // Stop polling on error
  clearInterval(pollIntervalRef.current);
  setActiveRunId(null);
}
```

**Result:** Network errors won't cause stuck UI.

#### 4. Status Validation in Polling
**File:** `client/src/pages/calls/OutboundCallsPage.tsx`

Check status on every poll:
```typescript
if (status.status !== 'running') {
  // Stop polling immediately
  clearInterval(pollIntervalRef.current);
  setActiveRunId(null);
}
```

**Result:** Progress bar hides as soon as status changes.

### Worker Job Fixes (Bonus)

#### 1. WhatsApp Sessions Cleanup Job
**File:** `server/jobs/whatsapp_sessions_cleanup_job.py`

Already has graceful import handling:
```python
try:
    from server.models_sql import WhatsAppSession
except ImportError as import_err:
    return {'status': 'skipped', 'reason': 'model_not_found'}
```

**Result:** Job doesn't fail if model doesn't exist. ✅ Already fixed.

#### 2. Delete Leads Job
**File:** `server/jobs/delete_leads_job.py`

Already has FK constraint handling:
```python
# Delete OutboundCallJob records first (FK fix)
OutboundCallJob.query.filter(...).delete()

# Proper rollback on error
except Exception as e:
    db.session.rollback()
    db.session.refresh(job)
```

**Result:** FK constraints handled, rollback prevents stuck sessions. ✅ Already fixed.

## Definition of Done ✅

All requirements met:

1. ✅ **Progress bar disappears after refresh if no active queue**
   - Backend only returns truly active queues (status='running', TTL check)
   - Frontend validates status and staleness

2. ✅ **Stuck queue auto-fails after 15 minutes**
   - Backend auto-marks stale queues as 'failed'
   - All pending jobs marked as failed
   - Returns 404 (no active queue)

3. ✅ **Cancel button works and stops progress within seconds**
   - Smart cancel detects stale queues → force cancel
   - Active queues → graceful cancel (worker shuts down)
   - Sets completed_at to prevent re-display

4. ✅ **Polling has proper cleanup**
   - Max 20-minute polling duration
   - Stops on status change
   - Stops on errors
   - Cleanup on unmount already existed

5. ✅ **Worker jobs don't fail**
   - WhatsApp cleanup: graceful import handling
   - Delete leads: FK constraint handling + rollback

## Testing Performed

1. **TTL Logic Test** (`/tmp/test_queue_ttl_logic.py`)
   - ✅ Fresh queue (5 min) → NOT stale
   - ✅ Borderline (14.5 min) → NOT stale
   - ✅ Just stale (15.1 min) → IS stale
   - ✅ Very stale (60 min) → IS stale

2. **Cancel Scenarios Test** (`/tmp/test_cancel_scenarios.py`)
   - ✅ Active queue (30s heartbeat) → Graceful cancel
   - ✅ Stuck queue (20min heartbeat) → Force cancel
   - ✅ Recent pause (10min) → Graceful cancel
   - ✅ Old pause (60min) → Force cancel

3. **Python Syntax Check**
   - ✅ `routes_outbound.py` compiles
   - ✅ `outbound_queue.py` compiles

## Files Changed

1. **Backend:**
   - `server/routes_outbound.py` - Active queue detection + cancel logic
   - `server/services/outbound_queue.py` - Auto-finalize on release

2. **Frontend:**
   - `client/src/pages/calls/OutboundCallsPage.tsx` - TTL checks + polling limits
   - `client/src/services/calls.ts` - Type definition for last_activity

## How It Fixes the 2 Stuck Businesses

**Before:**
1. Queue gets stuck (worker crash, network issue, etc.)
2. Database has record: `status='running'`, `last_heartbeat_at=20 minutes ago`
3. API returns this as "active queue"
4. Frontend shows progress bar forever
5. User refreshes page → still shows progress bar (stuck!)

**After:**
1. Queue gets stuck (same scenario)
2. Database has record: `status='running'`, `last_heartbeat_at=20 minutes ago`
3. API detects: `last_heartbeat_at > 15 minutes` → STALE!
4. API auto-marks: `status='failed'`, `completed_at=now`
5. API returns: 404 "אין תור פעיל" (no active queue)
6. Frontend: No progress bar shown! ✅

**Plus client-side protection:**
- Even if API somehow returns stale queue, client checks TTL
- Even if polling continues, it auto-stops after 20 minutes

## Deployment Notes

No database migrations needed - all fields already exist:
- `status` (already has 'failed' option)
- `completed_at` (already exists, now used consistently)
- `ended_at` (already exists, now used consistently)
- `last_heartbeat_at` (already exists, used for TTL)

Just deploy the code and the stuck queues will auto-resolve.

## Security Summary

No new security vulnerabilities introduced:
- ✅ Business isolation maintained (all queries filter by business_id)
- ✅ Cancel endpoint already has business_id verification
- ✅ No new external dependencies
- ✅ No SQL injection (uses parameterized queries)
- ✅ No cross-business access possible

The fix actually IMPROVES security by preventing indefinite resource consumption from stuck queues.
