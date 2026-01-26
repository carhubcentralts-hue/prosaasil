# Long-Running Tasks Audit - ProSaaS System

**Date**: 2026-01-26  
**Purpose**: Comprehensive mapping of all background/long-running tasks before architectural unification

---

## Executive Summary

The system has **6 major domains** with **8 distinct long-running task types**. Currently using **mixed approach**:
- **BackgroundJob** table for 6 tasks (leads delete/update, receipts, broadcasts, outbound)
- **Dedicated models** for 2 tasks (ReceiptSyncRun, OutboundCallRun + items)
- **No tracking** for Recording downloads (thread-based, in-memory only)

---

## 1. OUTBOUND CALLS (Domain: Voice/Calls)

### 1.1 Bulk Call Queue
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Outbound Calls - Bulk dialing to lead lists |
| **Entry Point** | `POST /api/outbound/bulk-enqueue` (`routes_outbound.py:1862`) |
| **Execution Mode** | RQ Worker (queue: `default`) |
| **Queue Name** | `default` |
| **Existing DB Tracker** | `OutboundCallRun` + `OutboundCallJob` (NEW - added in this PR) + `BackgroundJob` |
| **Progress Support TODAY** | ✅ YES - Real-time via new API endpoints added in this PR |
| **Progress Source** | `OutboundCallRun` counters: total_leads, queued_count, in_progress_count, completed_count, failed_count |
| **Cancel Support TODAY** | ✅ YES - Added `cancel_requested` field in this PR |
| **Cancel Mechanism** | Worker checks `cancel_requested` each loop, marks remaining as cancelled |
| **Dedup/Idempotency TODAY** | ✅ YES - Lead IDs list in cursor, job_id tracking |
| **Dedup Key** | `run_id` + lead IDs list in BackgroundJob.cursor |
| **Concurrency Limit TODAY** | ✅ YES - Hard limit via Redis semaphore (NEW in this PR) |
| **Concurrency How Many** | **3 concurrent calls per business** (enforced by `outbound_semaphore.py`) |
| **Concurrency Where** | Redis SET-based semaphore with atomic Lua scripts |
| **Pain/Bugs Observed** | ✅ FIXED in this PR - was advisory only, now hard enforced |

**Status**: ✅ **Fully Implemented** in this PR as the reference pattern

---

## 2. RECORDINGS (Domain: Call Recordings)

### 2.1 Recording Download & Transcription
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Recording processing - Download from Twilio, transcribe, store |
| **Entry Point** | Multiple: Twilio webhooks, call completion events (`tasks_recording.py`) |
| **Execution Mode** | **Thread** (background threading with in-memory queue) |
| **Queue Name** | In-memory `queue.Queue()` (NOT RQ) |
| **Existing DB Tracker** | ❌ **NONE** - Only updates `CallLog` fields |
| **Progress Support TODAY** | ⚠️ **IMPLICIT ONLY** - Must query CallLog.transcript_source field |
| **Progress Source** | CallLog fields: `processed_at`, `transcript_source` (recording/realtime/failed) |
| **Cancel Support TODAY** | ❌ **NO** - Cannot cancel running downloads |
| **Dedup/Idempotency TODAY** | ⚠️ **PARTIAL** - In-memory dict + optional Redis |
| **Dedup Key** | `call_sid` + business_id with 600s cooldown |
| **Dedup Issue** | **🔴 P0 BROKEN** - In-memory dedup not cross-process safe (`tasks_recording.py:43-44`) |
| **Concurrency Limit TODAY** | ✅ YES - Semaphore limits `MAX_CONCURRENT_DOWNLOADS = 3` |
| **Concurrency How Many** | 3 downloads (but in-memory semaphore, not distributed) |
| **Concurrency Where** | `_download_semaphore` threading.Semaphore |
| **Pain/Bugs Observed** | 🔴 **CRITICAL**: `'int' object has no attribute 'max'` error (reported in logs), in-memory state lost on worker restart, no progress UI, excessive 10-min cooldown |

**Status**: 🔴 **P0 BROKEN** - Needs complete rewrite with proper job tracking

---

## 3. WHATSAPP BROADCASTS (Domain: Messaging)

### 3.1 Bulk WhatsApp Messages
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | WhatsApp - Send bulk messages to lead lists |
| **Entry Point** | `POST /api/whatsapp/broadcast` (`routes_whatsapp.py:3272`) |
| **Execution Mode** | RQ Worker (queue: `default`) |
| **Queue Name** | `default` |
| **Existing DB Tracker** | `WhatsAppBroadcast` + `WhatsAppBroadcastRecipient` + `BackgroundJob` |
| **Progress Support TODAY** | ✅ YES - sent_count, failed_count tracked |
| **Progress Source** | `WhatsAppBroadcast`: total_recipients, sent_count, failed_count + BackgroundJob counters |
| **Cancel Support TODAY** | ⚠️ **IMPLICIT** - Can set BackgroundJob.status='cancelled', worker checks |
| **Cancel Mechanism** | Worker checks BackgroundJob.status in loop |
| **Dedup/Idempotency TODAY** | ✅ YES - Recipient ID cursor + idempotency_key |
| **Dedup Key** | `WhatsAppBroadcast.idempotency_key` + cursor tracks `last_id` |
| **Concurrency Limit TODAY** | ✅ YES - BulkGate rate limiting |
| **Concurrency How Many** | BulkGate limits per business (not hard concurrent limit) |
| **Concurrency Where** | BulkGate Redis locks (`bulk_gate.py`) |
| **Pain/Bugs Observed** | 🟡 **MEDIUM**: Returns success even if RQ enqueue fails (`routes_whatsapp.py:3293`), has both WhatsAppBroadcast AND BackgroundJob (redundant) |

**Status**: ⚠️ **INCONSISTENT** - Dual tracking (WhatsAppBroadcast + BackgroundJob), enqueue not validated

---

## 4. RECEIPTS (Domain: Email/Document Management)

### 4.1 Delete All Receipts
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Gmail Receipts - Batch soft-delete with R2 cleanup |
| **Entry Point** | `DELETE /receipts/delete-all` (`routes_receipts.py:1307`) |
| **Execution Mode** | RQ Worker (queue: `maintenance`) |
| **Queue Name** | `maintenance` |
| **Existing DB Tracker** | `BackgroundJob` only |
| **Progress Support TODAY** | ✅ YES - Cursor-based with batch progress |
| **Progress Source** | BackgroundJob: total, processed, succeeded, failed_count |
| **Cancel Support TODAY** | ✅ YES - status='cancelled' checked each batch |
| **Cancel Mechanism** | Worker checks BackgroundJob.status before each batch |
| **Dedup/Idempotency TODAY** | ✅ YES - Cursor tracks `last_id` |
| **Dedup Key** | `last_id` in BackgroundJob.cursor JSON |
| **Concurrency Limit TODAY** | ✅ YES - BulkGate prevents concurrent deletes |
| **Concurrency How Many** | 1 delete job per business (BulkGate lock) |
| **Concurrency Where** | BulkGate Redis lock with TTL refresh |
| **Pain/Bugs Observed** | None major - works well |

**Status**: ✅ **GOOD** - BackgroundJob pattern works well here

---

### 4.2 Gmail Sync (Receipt Import)
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Gmail Integration - Fetch receipts from Gmail |
| **Entry Point** | `POST /receipts/sync` (`routes_receipts.py:2037`) |
| **Execution Mode** | RQ Worker (queue: `default`) OR Thread fallback |
| **Queue Name** | `default` OR Thread if RQ unavailable |
| **Existing DB Tracker** | `ReceiptSyncRun` (dedicated model) |
| **Progress Support TODAY** | ✅ YES - messages_scanned, saved_receipts tracked |
| **Progress Source** | ReceiptSyncRun: messages_scanned, saved_receipts, pages_scanned, errors_count |
| **Cancel Support TODAY** | ⚠️ **IMPLICIT ONLY** - Stale detection auto-fails hung runs |
| **Cancel Mechanism** | No explicit cancel - relies on heartbeat timeout (180s) |
| **Dedup/Idempotency TODAY** | ✅ YES - Redis lock prevents double-click |
| **Dedup Key** | Redis: `receipt_sync_lock:{business_id}` with 3600s TTL |
| **Concurrency Limit TODAY** | ✅ YES - Redis lock allows 1 sync per business |
| **Concurrency How Many** | 1 sync per business |
| **Concurrency Where** | Redis SET NX lock (`gmail_sync_job.py:134`) |
| **Pain/Bugs Observed** | ⚠️ Dedicated ReceiptSyncRun model (not BackgroundJob), no explicit cancel UI |

**Status**: ⚠️ **INCONSISTENT** - Uses dedicated model instead of BackgroundJob

---

## 5. LEADS BULK OPERATIONS (Domain: CRM)

### 5.1 Delete Leads (Bulk)
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Leads - Batch delete with cascade cleanup |
| **Entry Point** | `POST /api/leads/bulk/delete` (`routes_leads.py:1606`) |
| **Execution Mode** | RQ Worker (queue: `maintenance`) |
| **Queue Name** | `maintenance` |
| **Existing DB Tracker** | `BackgroundJob` only |
| **Progress Support TODAY** | ✅ YES - Cursor-based batch tracking |
| **Progress Source** | BackgroundJob: total, processed, succeeded, failed_count |
| **Cancel Support TODAY** | ✅ YES - status='cancelled' checked |
| **Cancel Mechanism** | Worker checks BackgroundJob.status before each batch |
| **Dedup/Idempotency TODAY** | ✅ YES - `processed_ids` array in cursor |
| **Dedup Key** | Lead IDs array in BackgroundJob.cursor |
| **Concurrency Limit TODAY** | ✅ YES - BulkGate prevents concurrent operations |
| **Concurrency How Many** | 1 delete job per business |
| **Concurrency Where** | BulkGate Redis lock |
| **Pain/Bugs Observed** | ⚠️ **CONSTRAINT ISSUE**: chk_job_type may reject if not migrated (`routes_leads.py:1720`) |

**Status**: ⚠️ **NEEDS FIX** - Database constraint migration missing

---

### 5.2 Update Leads (Bulk)
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Leads - Batch update status/owner/tags |
| **Entry Point** | `PATCH /api/leads/bulk` (`routes_leads.py:1762`) |
| **Execution Mode** | RQ Worker (queue: `maintenance`) |
| **Queue Name** | `maintenance` |
| **Existing DB Tracker** | `BackgroundJob` only |
| **Progress Support TODAY** | ✅ YES - Cursor-based batch tracking |
| **Progress Source** | BackgroundJob: total, processed, succeeded, failed_count |
| **Cancel Support TODAY** | ✅ YES |
| **Cancel Mechanism** | Worker checks BackgroundJob.status before each batch |
| **Dedup/Idempotency TODAY** | ✅ YES - `processed_ids` array in cursor |
| **Dedup Key** | Lead IDs array in BackgroundJob.cursor |
| **Concurrency Limit TODAY** | ✅ YES - BulkGate |
| **Concurrency How Many** | 1 update job per business |
| **Concurrency Where** | BulkGate Redis lock |
| **Pain/Bugs Observed** | Same constraint issue as delete |

**Status**: ⚠️ **NEEDS FIX** - Database constraint migration missing

---

### 5.3 Delete Imported Leads
| Attribute | Current State |
|-----------|---------------|
| **Feature/Domain** | Outbound Leads - Delete leads from imported_outbound source |
| **Entry Point** | `POST /api/outbound/delete-imported` (`routes_outbound.py:1620`) |
| **Execution Mode** | RQ Worker (queue: `maintenance`) |
| **Queue Name** | `maintenance` |
| **Existing DB Tracker** | `BackgroundJob` only |
| **Progress Support TODAY** | ✅ YES - Cursor-based ID pagination |
| **Progress Source** | BackgroundJob: total, processed, succeeded, failed_count |
| **Cancel Support TODAY** | ✅ YES |
| **Cancel Mechanism** | Worker checks BackgroundJob.status before each batch |
| **Dedup/Idempotency TODAY** | ✅ YES - `last_id` in cursor |
| **Dedup Key** | `last_id` in BackgroundJob.cursor |
| **Concurrency Limit TODAY** | ✅ YES - BulkGate |
| **Concurrency How Many** | 1 job per business |
| **Concurrency Where** | BulkGate Redis lock |
| **Pain/Bugs Observed** | None major |

**Status**: ✅ **GOOD** - Works well with BackgroundJob

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Domains** | 6 (Calls, Recordings, WhatsApp, Receipts, Leads, Gmail) |
| **Total Long-Running Tasks** | 8 distinct task types |
| **Using BackgroundJob** | 6 tasks (leads x3, receipts delete, broadcasts, outbound) |
| **Using Dedicated Models** | 3 tasks (OutboundCallRun+Job, WhatsAppBroadcast+Recipient, ReceiptSyncRun) |
| **No DB Tracking** | 1 task (Recording downloads - **BROKEN**) |
| **RQ Worker Tasks** | 7 tasks |
| **Thread-Based Tasks** | 1 task (recordings) |
| **With Progress Tracking** | 7 tasks (1 implicit only) |
| **With Cancel Support** | 6 explicit + 1 implicit |
| **With Concurrency Limits** | 7 tasks (6 BulkGate, 1 Redis semaphore) |
| **Critical Issues (P0)** | 1 (Recordings dedup broken) |
| **Medium Issues** | 3 (WhatsApp enqueue, constraint migration, ReceiptSync inconsistency) |

---

## Critical Issues Found

### 🔴 P0 - Production Blockers
1. **Recording Downloads Broken** (`tasks_recording.py`)
   - In-memory dedup not cross-process safe
   - Error: `'int' object has no attribute 'max'` 
   - No progress tracking in DB
   - No cancel support
   - **Impact**: Recording processing can fail silently or duplicate

### 🟡 P1 - High Priority
2. **Database Constraint Not Migrated** (`routes_leads.py:1720`)
   - `chk_job_type` constraint may reject new job types
   - Blocks leads bulk operations
   - **Impact**: 503 errors on bulk operations

3. **WhatsApp Broadcast Enqueue Not Validated** (`routes_whatsapp.py:3293`)
   - Returns success even if RQ job fails
   - UI shows "queued" but job doesn't exist
   - **Impact**: User confusion, lost broadcasts

4. **Dual Tracking Inconsistency**
   - WhatsAppBroadcast + BackgroundJob (redundant)
   - ReceiptSyncRun instead of BackgroundJob
   - OutboundCallRun + BackgroundJob (new in this PR)
   - **Impact**: Maintenance burden, query complexity

---

## Architectural Decision Matrix

### Option A: Unify on BackgroundJob
**Pros:**
- ✅ Already used by 6/8 tasks
- ✅ Has all needed fields (status, counters, cancel, pause/resume)
- ✅ Working well for leads/receipts operations
- ✅ Less migration work

**Cons:**
- ❌ `chk_job_type` constraint needs expansion for every new task type
- ❌ Cursor JSON is untyped (fragile for complex state)
- ❌ No explicit items table (items tracked in cursor JSON only)
- ❌ WhatsAppBroadcast/ReceiptSyncRun have UI-specific needs

**Verdict**: ⚠️ **Possible but constrained** - Would need job_type constraint updates for every new feature

---

### Option B: New Unified Job System
**Pros:**
- ✅ Clean slate design with lessons learned
- ✅ Explicit `job_items` table for granular tracking
- ✅ No constraint on job types (open-ended)
- ✅ Can coexist with old models during migration
- ✅ Better for complex workflows (recordings, multi-stage)

**Cons:**
- ❌ More migration work (create new tables)
- ❌ Need adapters for existing tasks
- ❌ Larger initial time investment

**Verdict**: ✅ **RECOMMENDED** - Better long-term architecture

---

## Recommended Decision: **OPTION B - New Unified System**

### Reasoning (5 key points):

1. **BackgroundJob constraint is a liability**: The `chk_job_type` constraint requires DB migration for every new feature. This blocks innovation and creates maintenance burden.

2. **Items table is essential**: Recordings, calls, and broadcasts all need per-item status tracking. Storing this in JSON cursor is fragile. A dedicated `job_items` table with typed status is more robust.

3. **Three models already exist** (OutboundCallRun, WhatsAppBroadcast, ReceiptSyncRun) with specialized fields. Forcing them into BackgroundJob loses information or requires massive JSON blobs.

4. **Recording system is broken** and needs rewrite anyway. This is the perfect opportunity to establish the new pattern correctly.

5. **Gradual migration is feasible**: New system can coexist with BackgroundJob. Migrate highest-pain tasks first (Recordings → WhatsApp → Receipts), leave stable ones (Leads bulk) for later.

---

## Migration Priority Order

### Phase 1 (Immediate - P0):
1. **Recordings** 🔴
   - **Why First**: Currently broken, no DB tracking, blocking production
   - **Complexity**: Medium (thread → RQ worker migration)
   - **Impact**: High (fixes critical bug)

### Phase 2 (High Priority - P1):
2. **WhatsApp Broadcasts** 🟡
   - **Why**: Dual tracking (WhatsAppBroadcast + BackgroundJob), enqueue not validated
   - **Complexity**: Medium (merge two models into one pattern)
   - **Impact**: High (user-facing feature, high usage)

### Phase 3 (Medium Priority):
3. **Receipt Sync (Gmail)** ⚠️
   - **Why**: Uses ReceiptSyncRun instead of unified system
   - **Complexity**: Medium (dedicated model to unified)
   - **Impact**: Medium (works okay now, but inconsistent)

### Phase 4 (Low Priority - Working Well):
4. **Leads Bulk Operations** ✅
   - **Why**: Already working well with BackgroundJob
   - **Complexity**: Low (already follows pattern)
   - **Impact**: Low (just constraint fix needed)
   - **Action**: Fix `chk_job_type` constraint in migration, leave architecture as-is

5. **Receipts Delete** ✅
   - **Why**: Already working perfectly with BackgroundJob
   - **Complexity**: N/A (no migration needed)
   - **Impact**: N/A (leave as-is)

### Phase 5 (Already Complete):
6. **Outbound Calls** ✅
   - **Status**: Just implemented in this PR with proper pattern
   - **Action**: Use as reference implementation for new system

---

## Required Migrations (Schema Only)

### Migration 106: Create Unified Job System Tables
```sql
-- Generic job runs table
CREATE TABLE job_runs (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
    job_type VARCHAR(64) NOT NULL,  -- NO CONSTRAINT - open-ended
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    success_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    cancel_requested BOOLEAN DEFAULT FALSE,
    last_error TEXT,
    metadata JSONB,  -- Typed JSON for job-specific data
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    heartbeat_at TIMESTAMP,
    INDEX idx_job_runs_business_status (business_id, status),
    INDEX idx_job_runs_type_status (job_type, status),
    CHECK (status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled'))
);

-- Generic job items table
CREATE TABLE job_items (
    id SERIAL PRIMARY KEY,
    job_run_id INTEGER NOT NULL REFERENCES job_runs(id) ON DELETE CASCADE,
    entity_type VARCHAR(64) NOT NULL,  -- 'lead', 'call', 'recording', 'message', etc.
    entity_id INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_job_items_run (job_run_id, status),
    INDEX idx_job_items_entity (entity_type, entity_id),
    CHECK (status IN ('queued', 'in_progress', 'success', 'failed', 'cancelled'))
);
```

### Migration 107: Fix BackgroundJob Constraint (Immediate)
```sql
-- Remove restrictive constraint, allow any job_type
ALTER TABLE background_jobs 
DROP CONSTRAINT IF EXISTS chk_job_type;

-- Add open-ended constraint (optional, for safety)
ALTER TABLE background_jobs 
ADD CONSTRAINT chk_job_type_format 
CHECK (job_type ~ '^[a-z_]+$' AND length(job_type) <= 64);
```

---

## Next Steps (DO NOT PROCEED WITHOUT APPROVAL)

1. ✅ **This audit document is complete**
2. ⏸️ **STOP and await approval on Option B decision**
3. ⏸️ **If approved**: Begin Phase 1 (Recordings migration)
4. ⏸️ **If not approved**: Provide alternative Option A implementation plan

---

**Document Status**: COMPLETE - Awaiting architectural decision approval before implementation
