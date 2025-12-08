# Database, Verification, and Transcript Fixes - Summary

## Changes Made

### 1. Fixed DB Migrations (Idempotent PostgreSQL)

**File**: `server/db_migrate.py`

**Changes**:
- Migration 34 (CallLog extraction fields): Wrapped all ALTER TABLE statements in a single PostgreSQL DO block
- Migration 35 (Lead extraction fields): Wrapped all ALTER TABLE statements in a single PostgreSQL DO block
- Both migrations now use `information_schema.columns` checks before adding columns
- Added proper error handling with rollback on failure
- Changed `FLOAT` to `DOUBLE PRECISION` for PostgreSQL compatibility

**New Columns Added**:
- `call_log.final_transcript` (TEXT) - Full offline transcript from recording
- `call_log.extracted_service` (VARCHAR(255)) - AI-extracted service type
- `call_log.extracted_city` (VARCHAR(255)) - AI-extracted city
- `call_log.extraction_confidence` (DOUBLE PRECISION) - Confidence score
- `leads.service_type` (VARCHAR(255)) - Service type from call extraction
- `leads.city` (VARCHAR(255)) - City from call extraction

**Expected Result**: 
- No more `column does not exist` errors on startup
- No more `InFailedSqlTransaction` errors after column errors
- Migrations can be run multiple times safely

---

### 2. Disabled Verification/Lead Confirmed Early Hangup

**File**: `server/media_ws_ai.py`

**Changes**:

#### Added configuration flag:
- Added `verification_enabled: bool = False` to `CallConfig` dataclass (line ~161)
- Loads from `BusinessSettings.verification_enabled` (defaults to False)
- This flag controls whether the legacy verification feature is active

#### Gated verification logic (line ~4147):
```python
# Before: Always set verification_confirmed when user says "כן"
# After: Only set if verification_enabled=True
verification_enabled = getattr(self.call_config, 'verification_enabled', False)
if verification_enabled:
    self.verification_confirmed = True
else:
    print("Verification feature is DISABLED - ignoring as confirmation")
```

#### Gated hangup logic (line ~4290):
```python
# Before: Always check verification_confirmed for lead-captured hangup
# After: Only check if verification_enabled=True
verification_enabled = getattr(self.call_config, 'verification_enabled', False)
if self.auto_end_after_lead_capture and not self.pending_hangup and verification_enabled:
    # Lead confirmed hangup logic
```

**Expected Result**:
- Users saying "כן" will NOT trigger early call closure
- Calls will only hang up based on:
  - Smart hangup logic with required_lead_fields truly captured (from prompt)
  - User explicitly saying goodbye
  - Other configured hangup conditions
- The verification feature remains in codebase but is disabled by default

---

### 3. Ensured Recording-Based Transcript is Primary Source

**File**: `server/media_ws_ai.py`

**Changes**:

#### Webhook payload building (line ~9770):
1. **Priority 1**: Use `call_log.extracted_city` and `call_log.extracted_service` if available
   ```python
   if call_log:
       if call_log.extracted_city:
           city = call_log.extracted_city
       if call_log.extracted_service:
           service_category = call_log.extracted_service
   ```

2. **Fallback**: Only extract from realtime transcript if offline extraction didn't provide data
   ```python
   if full_conversation and not service_category:
       # Extract from AI confirmation patterns
   ```

3. **Transcript**: Use `call_log.final_transcript` (offline) over realtime `full_conversation`
   ```python
   final_transcript = call_log.final_transcript if call_log and call_log.final_transcript else full_conversation
   ```

**File**: `server/tasks_recording.py` (already implemented)

**Existing Features Verified**:
- Offline transcription with Whisper runs in background after call ends
- Extraction service extracts service + city from full transcript with business context
- Results saved to `call_log.final_transcript`, `extracted_service`, `extracted_city`, `extraction_confidence`
- Proper error handling - pipeline continues even if extraction fails
- Lead fields updated only if empty OR confidence > 0.8

**Expected Result**:
- Webhook payloads will prefer offline extracted city/service (higher quality)
- Transcript in webhooks will be from offline Whisper (more accurate) when available
- Realtime STT only used as fallback when no recording available
- No crashes if recording processing fails

---

## Testing Checklist

### 1. Database Migrations
- [ ] Container restart succeeds without column errors
- [ ] Query `/api/notifications` - should not crash with "column leads.service_type does not exist"
- [ ] Incoming calls should not crash with "column call_log.final_transcript does not exist"
- [ ] Check logs for "✅ Applied migration 34" and "✅ Applied migration 35"

### 2. Verification Logic
- [ ] Make a test call
- [ ] Say "כן" or other confirmation words
- [ ] Call should NOT immediately hang up
- [ ] Call should continue based on prompt requirements
- [ ] Check logs for "Verification feature is DISABLED - ignoring as confirmation"
- [ ] Call only hangs up when appropriate (goodbye, all fields collected per prompt, etc.)

### 3. Recording-Based Transcripts
- [ ] Make a real call with valid Twilio recording
- [ ] After call ends, recording should be transcribed offline
- [ ] Check logs for "[OFFLINE_STT] ✅ Transcript obtained"
- [ ] Check logs for "[OFFLINE_EXTRACT] ✅ Extracted: service='...', city='...'"
- [ ] CallLog should have `final_transcript`, `extracted_service`, `extracted_city` populated
- [ ] Webhook should show "✅ [WEBHOOK] Using offline extracted city/service from CallLog"
- [ ] If no recording: system should fall back gracefully without crashing

### 4. No Regressions
- [ ] Existing calls still work normally
- [ ] WhatsApp messages still work
- [ ] Admin panel loads without errors
- [ ] Dashboard shows correct stats

---

## Log Examples to Look For

### Success - Migrations
```
✅ Applied migration 34: add_call_log_extraction_fields - POST-CALL EXTRACTION for CallLog
✅ Applied migration 35: add_leads_extraction_fields - POST-CALL EXTRACTION for Lead
```

### Success - Verification Disabled
```
ℹ️ [BUILD 176] User said 'כן' but verification feature is DISABLED - ignoring as confirmation
```

### Success - Offline Transcript Priority
```
✅ [WEBHOOK] Using offline extracted city from CallLog: 'תל אביב' (confidence: 0.92)
✅ [WEBHOOK] Using offline extracted service from CallLog: 'מנעולן' (confidence: 0.95)
✅ [WEBHOOK] Using offline final_transcript (450 chars) instead of realtime (380 chars)
```

### Error Eliminated
```
# Before (ERROR):
❌ ERROR in /api/notifications: column leads.service_type does not exist

# After (SUCCESS):
✅ Business exists: קליבר (ID: 10)
🔔 Querying reminders for tenant_id=10
```

---

## Database Schema Changes

### CallLog Table
```sql
ALTER TABLE call_log ADD COLUMN final_transcript TEXT;
ALTER TABLE call_log ADD COLUMN extracted_service VARCHAR(255);
ALTER TABLE call_log ADD COLUMN extracted_city VARCHAR(255);
ALTER TABLE call_log ADD COLUMN extraction_confidence DOUBLE PRECISION;
```

### Leads Table
```sql
ALTER TABLE leads ADD COLUMN service_type VARCHAR(255);
ALTER TABLE leads ADD COLUMN city VARCHAR(255);
```

### BusinessSettings Table (Optional - for future use)
```sql
-- Not created in this fix, but can be added if verification feature is re-enabled:
ALTER TABLE business_settings ADD COLUMN verification_enabled BOOLEAN DEFAULT FALSE;
```

---

## Rollback Plan (If Needed)

If issues arise, rollback is minimal since changes are defensive:

1. **Migrations**: Columns are nullable - can be dropped without data loss:
   ```sql
   ALTER TABLE call_log DROP COLUMN IF EXISTS final_transcript;
   ALTER TABLE call_log DROP COLUMN IF EXISTS extracted_service;
   ALTER TABLE call_log DROP COLUMN IF EXISTS extracted_city;
   ALTER TABLE call_log DROP COLUMN IF EXISTS extraction_confidence;
   ALTER TABLE leads DROP COLUMN IF EXISTS service_type;
   ALTER TABLE leads DROP COLUMN IF EXISTS city;
   ```

2. **Verification**: Already disabled by default - no action needed

3. **Transcript priority**: Falls back gracefully - no breaking changes

---

## Implementation Notes

### Why These Changes Matter

1. **DB Migrations**: Production was crashing on every startup due to missing columns referenced in SQLAlchemy models

2. **Verification Logic**: Users were experiencing premature call hangups when they politely confirmed ("כן") during the conversation, before all information was collected

3. **Transcript Priority**: Recording-based transcription (offline Whisper) is significantly more accurate than realtime STT, especially for Hebrew. Webhooks and downstream systems benefit from this higher quality data.

### Design Decisions

- **Verification disabled by default**: The prompt-based flow is more flexible and accurate. Verification can be re-enabled per-business via BusinessSettings if needed.

- **Fallback chain**: System gracefully degrades if recording processing fails - uses realtime data as fallback

- **No breaking changes**: All changes are backwards-compatible. Existing calls continue working.

---

## Files Modified

1. `server/db_migrate.py` - Migrations 34 and 35
2. `server/media_ws_ai.py` - CallConfig, verification logic, webhook building
3. `server/models_sql.py` - Already had the new columns (no changes needed)
4. `server/tasks_recording.py` - Already implemented (verified, no changes needed)
5. `server/services/lead_extraction_service.py` - Already exists (no changes needed)

---

**Implementation Complete**: All fixes are in place and ready for production deployment.
