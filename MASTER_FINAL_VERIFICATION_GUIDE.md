# MASTER FINAL VERIFICATION – Auto-Status + Outbound

## הנחיית שימוש (Hebrew Instructions Summary)

זהו סקריפט אימות מקיף שבודק שהפיצ'רים הבאים עובדים בפועל בפרודקשן:

1. ✅ **Auto-Status** - עדכון סטטוס אוטומטי אחרי כל שיחה
2. ✅ **Bulk Calling** - שיחות יוצאות מרובות עם הגבלת קונקרנטיות
3. ✅ **Status Source of Truth** - כל הסטטוסים מגיעים אך ורק מהטבלה lead_statuses
4. ✅ **Both Flows** - גם שיחות נכנסות וגם יוצאות מפעילות את Auto-Status

## Usage

### Prerequisites

```bash
# Run from backend container with DATABASE_URL set
export DATABASE_URL="postgresql://user:pass@host/dbname"

# OR run inside Docker container:
docker exec -it prosaasil-backend-1 python verify_master_final_production.py
```

### Running the Verification

```bash
cd /opt/prosaasil  # or your project directory
python verify_master_final_production.py
```

## What This Script Does

### 0) Verify Deploy Running New Code

Checks that the new backend code is deployed:
- ✅ Auto-status service exists
- ✅ `save_call_to_db` has auto-status integration
- ✅ Bulk calling routes exist
- ✅ Required models exist

### 1) Verify Auto-Status Runs in Real Life

Checks the database for evidence of auto-status working:
- Looks for recent calls with summaries
- Checks if leads have updated statuses
- Verifies activity logs show `auto_inbound` or `auto_outbound` source
- Confirms fields are updated: `summary`, `last_contact_at`

**What to look for:**
```sql
SELECT l.id, l.status, l.summary, l.last_contact_at,
       la.type, la.payload->>'source' as source
FROM leads l
JOIN lead_activities la ON la.lead_id = l.id
WHERE la.type = 'status_change'
  AND la.payload->>'source' LIKE 'auto_%'
ORDER BY la.at DESC
LIMIT 10;
```

### 2) Verify Status Source of Truth (NO DRIFT)

**Critical Check:** Ensures NO lead has a status that doesn't exist in `lead_statuses`

```sql
-- This query MUST return empty results
SELECT DISTINCT l.status
FROM leads l
WHERE l.status IS NOT NULL
  AND l.status NOT IN (
    SELECT name FROM lead_statuses 
    WHERE business_id = l.tenant_id 
    AND is_active = true
  );
```

If this returns results → **BUG!** Status drift detected.

### 3) Verify Auto-Status Doesn't Guess Unknown Statuses

Tests that the auto-status service ONLY suggests statuses that exist for the business.

Example:
- Business has statuses: `new`, `interested`, `not_relevant`
- Summary: "לא מעוניין"
- Auto-status suggests: `not_relevant` ✅
- Auto-status NEVER suggests: `HOT_INTERESTED` ❌ (doesn't exist for this business)

### 4) Verify Both Flows: Inbound + Outbound

Confirms that `save_call_to_db` calls auto-status for BOTH:
- ✅ Inbound calls
- ✅ Outbound calls

**No conditional blocking** - both flows use the same logic.

### 5) Verify Bulk Call Concurrency

Checks that bulk calling respects the concurrency limit:

```sql
SELECT run_id,
       COUNT(*) FILTER (WHERE status='calling') AS active,
       concurrency
FROM outbound_call_jobs
JOIN outbound_call_runs ON outbound_call_runs.id = run_id
GROUP BY run_id, concurrency;
```

**Critical:** `active` must NEVER exceed `concurrency`

Default concurrency: **3**

### 6) Verify Nothing Depends on Frontend

Confirms that:
- Auto-status works via `save_call_to_db` (pure backend)
- Bulk calling triggered via API (pure backend)
- Database updates happen server-side
- No UI imports in backend services

### 7) Final Acceptance Statement

The script confirms:

✅ Auto-status runs in production  
✅ Status selected ONLY from lead_statuses  
✅ Both inbound and outbound trigger auto-status  
✅ Bulk calls limited to N concurrent  
✅ No dependency on UI/permissions for logic  

## Expected Output

### ✅ All Passing

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              MASTER FINAL VERIFICATION – Auto-Status + Outbound              ║
║                        (IGNORE UI/Console NOISE)                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

IMPORTANT:
  ❌ Ignoring Console errors / 403 / Admin UI / Roles
  ❌ NOT changing permissions
  ❌ NOT touching admin routes
  ✅ Focusing ONLY on backend code connection and production logic

================================================================================
0) VERIFY DEPLOY REALLY RUNNING NEW BACKEND CODE
================================================================================

✅ Auto-status service exists and can be imported
   - Service class: LeadAutoStatusService
✅ save_call_to_db has auto-status integration
✅ Bulk calling routes exist (process_bulk_call_run)
✅ Required models exist (OutboundCallRun, OutboundCallJob, LeadStatus)

Code Verification: 4/4 checks passed

... (rest of verification output)

================================================================================
7) FINAL ACCEPTANCE STATEMENT
================================================================================

✅ Auto-status runs in production
✅ Status selected ONLY from lead_statuses
✅ Both inbound and outbound trigger auto-status
✅ Bulk calls limited to N concurrent
✅ No dependency on UI/permissions for logic

================================================================================
✅✅✅ ALL ACCEPTANCE CRITERIA MET ✅✅✅

The feature is WORKING IN PRODUCTION
Auto-status and bulk calling are operational
Ready for production use
================================================================================
```

## Manual Testing (If Needed)

If the script shows "⚠️ NOT VERIFIED" for inbound or outbound calls, perform manual tests:

### Test 1: Inbound Call → Not Interested

1. Call business number
2. Say: **"לא מעוניין, תפסיקו להתקשר"**
3. Hang up
4. Wait 30 seconds
5. Check DB:

```sql
SELECT status, summary, last_contact_at
FROM leads
ORDER BY last_contact_at DESC
LIMIT 1;
```

**Expected:**
- `status` = `not_relevant` (or business's equivalent)
- `summary` updated
- `last_contact_at` updated

### Test 2: Outbound Call → Interested

1. Make outbound call
2. Lead says: **"יכול להיות מעניין, תשלחו פרטים"**
3. Hang up
4. Check DB:

```sql
SELECT status
FROM leads
ORDER BY last_contact_at DESC
LIMIT 1;
```

**Expected:**
- `status` = `interested` (or business's equivalent)
- **NOT** `HOT_INTERESTED` or any group name
- Only actual status from `lead_statuses` table

### Test 3: Bulk Call Concurrency

1. Select 50 leads
2. POST to `/api/outbound/bulk-enqueue` with `concurrency=3`
3. Monitor:

```sql
-- Run this repeatedly during the bulk run
SELECT 
  r.id,
  r.concurrency,
  r.in_progress_count,
  (SELECT COUNT(*) FROM outbound_call_jobs 
   WHERE run_id = r.id AND status = 'calling') as actual_calling
FROM outbound_call_runs r
WHERE r.status = 'running';
```

**Expected:**
- `actual_calling` NEVER exceeds `concurrency` (3)

## What NOT to Do

⛔️ **DO NOT:**
- ❌ Touch permissions
- ❌ Touch admin routes
- ❌ "Fix" console errors
- ❌ Change status mapping without real status in database
- ❌ Add new statuses without business context

## Troubleshooting

### "No recent calls found"

**Solution:** Make a test call (inbound or outbound) and run the script again.

### "Status drift detected"

**Solution:** This is a bug. Check logs for:
```
[AutoStatus] ⚠️ Suggested status 'X' not valid for business Y - skipping status change
```

The status validation is working, but some old data might have invalid statuses.

### "Concurrency violation"

**Solution:** Check the `process_bulk_call_run` function in `routes_outbound.py`:
- Line 1047-1053: Active jobs count check
- Line 1053: `if active_jobs < run.concurrency`

Also check `save_call_status_async` in `tasks_recording.py`:
- Line 702: `run.in_progress_count = max(0, run.in_progress_count - 1)`

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Call Completed                          │
│                  (Inbound or Outbound)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Recording Processed → Summary Generated        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  save_call_to_db()                          │
│           (tasks_recording.py, line 425)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          suggest_lead_status_from_call()                    │
│       (lead_auto_status_service.py, line 256)               │
│                                                             │
│  1. Get valid statuses for business (from lead_statuses)   │
│  2. Analyze summary with keyword scoring                   │
│  3. Return status OR None if no match                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Validate Status Exists                         │
│         (tasks_recording.py, line 570-574)                  │
│                                                             │
│  LeadStatus.query.filter_by(                               │
│    business_id=X,                                          │
│    name=suggested_status,                                  │
│    is_active=True                                          │
│  ).first()                                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Update Lead + Create Activity                  │
│         (tasks_recording.py, line 577-591)                  │
│                                                             │
│  - lead.status = suggested_status                          │
│  - lead.summary = summary                                  │
│  - lead.last_contact_at = now()                            │
│  - Create LeadActivity with source='auto_inbound/outbound' │
└─────────────────────────────────────────────────────────────┘
```

## Bulk Calling Flow

```
┌─────────────────────────────────────────────────────────────┐
│     POST /api/outbound/bulk-enqueue                         │
│     {lead_ids: [...], concurrency: 3}                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          Create OutboundCallRun + Jobs                      │
│          Start process_bulk_call_run thread                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            While there are queued jobs:                     │
│                                                             │
│  1. Count active jobs (status='calling')                   │
│  2. If active < concurrency:                               │
│     - Get next queued job                                  │
│     - Update job.status = 'calling'                        │
│     - Increment run.in_progress_count                      │
│     - Start Twilio call                                    │
│  3. Else: wait 2 seconds                                   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Call completes                                 │
│          save_call_status_async()                           │
│                                                             │
│  - Update job.status = 'completed' or 'failed'             │
│  - Decrement run.in_progress_count                         │
│  - Increment run.completed_count or failed_count           │
└─────────────────────────────────────────────────────────────┘
```

## Files Modified

### Backend Services
1. `server/services/lead_auto_status_service.py` - Auto-status service
2. `server/tasks_recording.py` - Integration point (save_call_to_db)
3. `server/routes_outbound.py` - Bulk calling endpoints
4. `server/models_sql.py` - Database models

### Verification Scripts
5. `verify_master_final_production.py` - **NEW** comprehensive verification
6. `verify_auto_status_production.py` - Original verification (still useful)

### Documentation
7. `AUTO_STATUS_VERIFICATION.md` - Feature verification checklist
8. `AUTO_STATUS_HOW_IT_WORKS.md` - User guide
9. `MASTER_FINAL_VERIFICATION_GUIDE.md` - **THIS FILE**

## Summary

This verification script provides a comprehensive, production-ready check of the auto-status and bulk calling features. It:

- ✅ Checks that code is deployed
- ✅ Verifies features work with real data
- ✅ Ensures data integrity (no status drift)
- ✅ Confirms concurrency limits are respected
- ✅ Validates backend-only operation (no UI dependency)

**Run this script after deployment to confirm everything is working correctly in production.**

---

**Last Updated:** 2025-12-14  
**Version:** 1.0  
**Status:** Production-Ready ✅
