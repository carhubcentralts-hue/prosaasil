# PRE-MERGE VERIFICATION - 6 Critical Points

## Status: ⚠️ NEEDS FIXES BEFORE MERGE

Found **3 CRITICAL ISSUES** that must be fixed:

---

## ✅ Point 1: Backfills Don't Fail Deployment

**STATUS: PASS ✅**

**Evidence from `deploy_production.sh` lines 289-310:**
```bash
# Step 3.6: Run data backfill (separate from migrations)
log_header "Step 3.6: Running Data Backfill Operations"
log_info "Running backfill tool (non-blocking)..."

# Run backfill tool
# ⚠️ IMPORTANT: Backfill tool NEVER fails deployment
# It exits 0 even if incomplete, allowing deployment to continue
# Backfill is idempotent and will continue on next deployment if needed
log_info "Executing backfill tool..."
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm backfill

# Backfill tool always exits 0, so we don't check exit code
# Just log that it completed
log_success "Backfill tool completed (check logs above for any warnings)"
```

**Verification:**
- ✅ Migrations: `exit 1` on failure (lines 258-262)
- ✅ Indexer: No exit code check (line 287)
- ✅ Backfill: No exit code check (line 310)
- ✅ Backfill runner always exits 0 (in `db_run_backfills.py`)

---

## ❌ Point 2: SKIP LOCKED Implementation

**STATUS: FAIL ❌ - CRITICAL ISSUE**

**Problem:** The timeout policy is TOO SHORT for DML operations.

**Evidence from `db_backfills.py` lines 96-98:**
```python
with engine.begin() as conn:
    conn.execute(text("SET lock_timeout = '5s'"))      # ❌ TOO SHORT!
    conn.execute(text("SET statement_timeout = '30s'")) # ⚠️ Borderline
```

**Issue:**
- Using `lock_timeout = '5s'` is DDL timeout policy
- For DML with SKIP LOCKED, need **30-120s** lock_timeout
- Current 5s will cause false lock timeouts

**The SKIP LOCKED logic itself is CORRECT:**
```sql
WITH batch AS (
    SELECT id
    FROM leads
    WHERE tenant_id = :tenant_id 
      AND last_call_direction IS NULL
    ORDER BY id
    LIMIT :batch_size
    FOR UPDATE SKIP LOCKED    -- ✅ Correct pattern
),
first_calls AS (
    SELECT DISTINCT ON (cl.lead_id) 
        cl.lead_id,
        cl.direction
    FROM call_log cl
    JOIN batch b ON b.id = cl.lead_id
    WHERE cl.direction IN ('inbound', 'outbound')
    ORDER BY cl.lead_id, cl.created_at ASC
)
UPDATE leads l
SET last_call_direction = fc.direction
FROM first_calls fc
WHERE l.id = fc.lead_id
```

✅ Pattern is correct: SELECT IDs first with SKIP LOCKED, then UPDATE
✅ Uses CTE to select batch
✅ UPDATE only affects selected IDs

**FIX REQUIRED:**
```python
# WRONG (current):
conn.execute(text("SET lock_timeout = '5s'"))

# CORRECT (should be):
conn.execute(text("SET lock_timeout = '30s'"))  # Or 60s-120s
conn.execute(text("SET statement_timeout = '120s'"))  # Or 0 for unlimited
conn.execute(text("SET idle_in_transaction_session_timeout = '120s'"))
```

---

## ✅ Point 3: Idempotent and Resume-Safe

**STATUS: PASS ✅**

**Evidence:**
1. **Idempotent condition:** `WHERE last_call_direction IS NULL` (line 105)
2. **Resume-safe:** Only processes NULL values, safe to run multiple times
3. **Progress logging:** Logs progress every 10 batches (line 135-136)
4. **Completion tracking:** Tracks rows per business (line 132)

```python
# Query only processes NULL values
SELECT id
FROM leads
WHERE tenant_id = :tenant_id 
  AND last_call_direction IS NULL  # ✅ Idempotent condition
```

---

## ❌ Point 4: Small Batches with Commit Per Batch

**STATUS: PARTIAL ❌ - NEEDS IMPROVEMENT**

**Current Implementation:**
- ✅ Batch size: 100 (good, not too large)
- ✅ Commit per batch: `with engine.begin()` commits automatically
- ✅ Sleep between batches: `time.sleep(0.05)` (50ms)

**BUT:**
- ❌ Batch size is hardcoded at 100
- ⚠️ Should allow 200-1000 for better performance

**Evidence:**
```python
batch_size = 100,  # In registry definition

LIMIT :batch_size  # In SQL
```

**FIX RECOMMENDED:**
- Change default batch_size in registry from 100 to **200-500**
- 100 is very safe but might be too conservative
- 200-500 is a better balance for production

---

## ❌ Point 5: Timeout Policy for DML

**STATUS: FAIL ❌ - CRITICAL ISSUE** (Same as Point 2)

**Current timeouts:**
```python
conn.execute(text("SET lock_timeout = '5s'"))          # ❌ TOO SHORT
conn.execute(text("SET statement_timeout = '30s'"))     # ⚠️ Borderline
# Missing: idle_in_transaction_session_timeout
```

**Required for DML:**
```python
conn.execute(text("SET lock_timeout = '30s'"))         # Or 60-120s
conn.execute(text("SET statement_timeout = '120s'"))   # Or 0
conn.execute(text("SET idle_in_transaction_session_timeout = '120s'"))
```

**Rationale:**
- DDL (migrations) need **fail fast** → 5s lock_timeout ✅
- DML (backfills) need **patience** → 30-120s lock_timeout
- SKIP LOCKED helps but doesn't eliminate all locks
- 5s is way too aggressive for production workloads

---

## ✅ Point 6: Guard Test Catches All Violations

**STATUS: PASS ✅**

**Evidence from `test_guard_no_backfills_in_migrations.py`:**

```python
DML_PATTERNS = {
    'UPDATE': r'UPDATE\s+(\w+)\s+SET',           # ✅ Catches UPDATE
    'INSERT_SELECT': r'INSERT\s+INTO\s+\w+.*SELECT',  # ✅ Catches INSERT INTO ... SELECT
    'DELETE': r'DELETE\s+FROM\s+(\w+)',          # ✅ Catches DELETE
    'EXEC_DML': r'exec_dml\s*\(',                # ✅ Catches exec_dml()
    'BACKFILL_COMMENT': r'[Bb]ackfill',          # ✅ Catches backfill comments
}
```

**Verification:**
- ✅ Catches UPDATE statements with regex
- ✅ Catches INSERT INTO ... SELECT patterns
- ✅ Catches DELETE statements
- ✅ Catches exec_dml() function calls
- ✅ Extracts table names from UPDATE/DELETE
- ✅ Checks if table is "hot table" (leads, call_log, receipts, etc.)
- ✅ Reports severity (HIGH/MEDIUM/LOW)
- ✅ Grandfathers existing violations
- ✅ FAILS on new violations

**Test Results:** 0 new violations found ✅

---

## Summary: GO / NO-GO Decision

### ❌ **NO-GO** - Must fix 2 critical issues:

1. **CRITICAL:** Fix timeout policy in `server/db_backfills.py`
   - Change `lock_timeout` from 5s to 30-60s
   - Change `statement_timeout` to 120s or 0
   - Add `idle_in_transaction_session_timeout`

2. **RECOMMENDED:** Increase batch size from 100 to 200-500
   - Current 100 is too conservative
   - 200-500 is better for production performance

### After Fixes → GO ✅

Once these 2 issues are fixed:
- ✅ Backfills won't fail deployment
- ✅ SKIP LOCKED implemented correctly
- ✅ Everything is idempotent
- ✅ Small batches with commits
- ✅ Correct timeout policy (after fix)
- ✅ Guard test catches all violations

---

## Fixes Required

### File: `server/db_backfills.py` (Line 96-98)

**BEFORE:**
```python
with engine.begin() as conn:
    conn.execute(text("SET lock_timeout = '5s'"))
    conn.execute(text("SET statement_timeout = '30s'"))
```

**AFTER:**
```python
with engine.begin() as conn:
    # DML timeout policy (not DDL!)
    conn.execute(text("SET lock_timeout = '60s'"))  # Patient for busy tables
    conn.execute(text("SET statement_timeout = '120s'"))  # Allow time for batches
    conn.execute(text("SET idle_in_transaction_session_timeout = '120s'"))  # Prevent stuck transactions
```

### File: `server/db_backfills.py` (Registry definition)

**OPTIONAL but RECOMMENDED:**
```python
{
    'key': 'migration_36_last_call_direction',
    'migration_number': '36',
    'description': 'Populate last_call_direction on leads from first call in call_log',
    'tables': ['leads', 'call_log'],
    'batch_size': 200,  # Changed from 100 to 200
    'max_runtime_seconds': 600,
    'priority': 'HIGH',
    'safe_to_run_online': True,
    'function': backfill_last_call_direction,
    'status': 'active',
},
```

---

## Confidence Level After Fixes

With these 2 fixes applied:

- **Production Stability:** HIGH ✅
- **Lock Timeout Risk:** LOW ✅
- **Deployment Safety:** HIGH ✅
- **Idempotency:** HIGH ✅
- **Future Violations:** BLOCKED ✅

**Final Verdict:** This is the RIGHT architecture for production. Just fix the timeout policy and it's **GO** ✅
