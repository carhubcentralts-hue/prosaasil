# DML Operations in Migrations - Safety Analysis

## Overview

This document analyzes all DML (UPDATE/INSERT/DELETE) operations found in migrations
to determine if they are safe or should be moved to backfills.

## Safety Criteria

**SAFE DML in migrations:**
- Deduplication before creating UNIQUE index (required for index creation)
- Small INSERT for initial setup/seed data (< 100 rows)
- One-time UPDATE to set defaults on existing rows

**UNSAFE DML (should be in backfills):**
- Large UPDATE/DELETE on tables with many rows
- Data transformations that could take minutes
- Any operation that could timeout

## Found Operations

### 1. Line 1607: DELETE FROM messages (Deduplication)
**Status: SAFE ✅**
**Reason:** Required before creating UNIQUE index. Removes duplicates based on provider_msg_id.
**Type:** Deduplication for constraint enforcement

```python
DELETE FROM messages 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM messages 
    WHERE provider_msg_id IS NOT NULL AND provider_msg_id != ''
    GROUP BY provider_msg_id
)
AND provider_msg_id IS NOT NULL AND provider_msg_id != ''
```

**Action:** Keep in migration. Add comment clarifying it's required for UNIQUE index.

---

### 2. Line 1718: UPDATE leads SET order_index = id
**Status: POTENTIALLY UNSAFE ⚠️**
**Reason:** Updates ALL existing leads. Could be slow on large tables.
**Type:** Backfill of default values

```python
UPDATE leads SET order_index = id WHERE order_index = 0
```

**Action:** Should move to db_backfills.py OR add LIMIT if table is small.

---

### 3. Line 1739: DELETE FROM call_log (Deduplication)
**Status: SAFE ✅**
**Reason:** Required before creating UNIQUE index. Removes duplicates based on call_sid.
**Type:** Deduplication for constraint enforcement

```python
DELETE FROM call_log 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM call_log 
    WHERE call_sid IS NOT NULL AND call_sid != ''
    GROUP BY call_sid
)
AND call_sid IS NOT NULL AND call_sid != ''
```

**Action:** Keep in migration. Add comment clarifying it's required for UNIQUE index.

---

### 4. Lines 1818, 1831: INSERT INTO business_contact_channels
**Status: SAFE ✅**
**Reason:** Small INSERT for initial setup. Likely one row per business.
**Type:** Setup/seed data

**Action:** Keep in migration. These are schema-related setup.

---

### 5. Lines 3460, 3474, 3488: INSERT INTO email_templates
**Status: SAFE ✅**
**Reason:** Small INSERT for seed data. Creating default email templates (< 10 rows).
**Type:** Setup/seed data

**Action:** Keep in migration. This is initial data setup.

---

### 6. Line 4945: DELETE FROM whatsapp_message (Deduplication)
**Status: SAFE ✅**
**Reason:** Required before creating UNIQUE index. Removes duplicates.
**Type:** Deduplication for constraint enforcement

```python
DELETE FROM whatsapp_message
WHERE id NOT IN (
    SELECT MIN(id)
    FROM whatsapp_message
    WHERE provider_message_id IS NOT NULL
    GROUP BY business_id, provider_message_id
)
AND provider_message_id IS NOT NULL
```

**Action:** Keep in migration. Add comment clarifying it's required for UNIQUE index.

---

### 7. Lines 6684, 6754: DELETE FROM outbound_call_jobs
**Status: SAFE ✅**
**Reason:** Cleanup of orphaned/duplicate records before adding constraints.
**Type:** Deduplication/cleanup for constraint enforcement

**Action:** Keep in migration. Add comment clarifying it's required for constraints.

---

### 8. Line 7033: INSERT INTO business_calendars
**Status: SAFE ✅**
**Reason:** Small INSERT for initial setup. Creating default calendar per business.
**Type:** Setup/seed data

**Action:** Keep in migration. This is schema-related setup.

---

## Summary

**Safe Operations (can stay in migrations):** 10/12
- Deduplication before UNIQUE index: 4 operations
- Small INSERT for seed data: 4 operations  
- Cleanup for constraints: 2 operations

**Potentially Unsafe Operations (consider moving):** 1/12
- Line 1718: UPDATE leads SET order_index = id
  - Could be slow on large tables
  - Should check if leads table is typically small or move to backfill

**Action Items:**
1. ✅ Verify Point 1: execute_with_retry creates new connections - VERIFIED
2. ✅ Verify Point 2: No external engine.begin() - VERIFIED  
3. ⚠️ Verify Point 3: Review UPDATE leads operation
   - Add LIMIT if table is small
   - OR move to db_backfills.py if table can be large
4. Add comments to all DML operations explaining why they're safe

## Recommendation

The DML operations are mostly safe because they are:
1. Required for creating UNIQUE indexes (deduplication)
2. Small seed data inserts
3. One-time setup operations

Only the UPDATE leads operation needs review/optimization.
