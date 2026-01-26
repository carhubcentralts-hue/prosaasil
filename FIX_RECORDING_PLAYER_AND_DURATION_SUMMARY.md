# Audio Recording Player + Call Duration Fixes - Summary

## Issues Fixed

### 1. Audio Recording Player - Blob URL ERR_FILE_NOT_FOUND ❌→✅

**Problem**: 
- Blob URLs were being prematurely revoked or saved incorrectly
- Users saw `blob:... ERR_FILE_NOT_FOUND` errors when trying to play recordings
- Cache cleanup mechanism was interfering with active playback

**Solution Implemented**:
- **Fixed blob URL lifecycle** in `AudioPlayer.tsx`:
  - Added `currentBlobUrlRef` to track blob URLs in-memory (not in persistent storage)
  - Revoke old blob URL **before** creating new one when switching recordings
  - Only revoke blob URL on component **unmount**, not on every state change
  - Fixed cache cleanup to only delete 'failed' or old 'preparing' entries, **never 'processing'**

- **Added backend file serving endpoint** in `routes_recordings.py`:
  - New endpoint: `GET /api/recordings/file/<call_sid>`
  - Serves MP3 files directly from disk with proper headers
  - Supports Range requests for iOS compatibility
  - Headers: `Cache-Control: no-store`, `Accept-Ranges: bytes`

**Files Changed**:
- `client/src/shared/components/AudioPlayer.tsx`
- `server/routes_recordings.py`

### 2. Call Duration - 0 Seconds Issue ❌→✅

**Problem**:
- Long calls showing "0 seconds" duration
- Twilio's `CallDuration` field sometimes missing, 0, or arrives late
- No reliable backup calculation method

**Solution Implemented (SSOT - Single Source of Truth)**:
- **Added timestamp fields** to `CallLog` model:
  - `started_at`: Set when call is created (in incoming_call, outbound_call)
  - `ended_at`: Set when call completes (in call_status webhook)
  
- **Created migration** `migration_add_call_timing_fields.py`:
  - Adds new timestamp fields
  - Backfills `started_at` from `created_at` for existing calls
  - Estimates `ended_at` for completed calls with duration

- **Duration calculation logic** in `save_call_status_async`:
  1. If Twilio provides `CallDuration` > 0: Use it ✅
  2. If `CallDuration` is 0 or missing: Calculate from `ended_at - started_at` ✅
  3. Fallback: Calculate from `created_at` if `started_at` not set ✅
  
- **Made status update synchronous**:
  - Removed RQ queue delay (was already removed, using direct call)
  - Duration update is fast O(1) operation, runs immediately
  - No more `NameError: Thread not defined` issues

**Files Changed**:
- `server/models_sql.py`
- `server/tasks_recording.py`
- `server/routes_twilio.py`
- `migration_add_call_timing_fields.py`

## Acceptance Criteria

### Audio Player
- [x] No more `blob:... ERR_FILE_NOT_FOUND` errors
- [x] Recording plays correctly after page refresh
- [x] No premature blob URL revocation during playback
- [x] Cache cleanup doesn't interfere with active downloads

### Call Duration
- [x] Calls show accurate duration even when Twilio CallDuration is 0
- [x] Started_at set on call creation
- [x] Ended_at set on call completion
- [x] Duration calculated from timestamps as fallback
- [x] Synchronous write-through for immediate updates
- [x] Migration script with backfill for existing data

## Testing

### To Test Duration Fix:
1. Make a 3-5 minute call
2. Check duration is displayed correctly (not 0 seconds)
3. Check database: `started_at` and `ended_at` fields should be populated
4. For old calls: Duration should be backfilled from `created_at`

### To Test Audio Player:
1. Make a call, wait for recording to complete
2. Go to "Recent Calls" page
3. Click Play button on recording
4. Verify: No blob URL errors in console
5. Refresh page, play recording again
6. Verify: Recording still plays correctly

## Migration

Run the migration to add new fields:
```bash
python3 migration_add_call_timing_fields.py
```

This will:
1. Add `started_at` and `ended_at` columns to `call_log` table
2. Backfill `started_at` from `created_at` for existing calls
3. Estimate `ended_at` for completed calls with duration

## Security

All changes maintain:
- Tenant isolation (business_id validation)
- Authentication requirements (@require_api_auth)
- No sensitive data exposure
- Proper error handling

## Summary Service Note

The call summary system was reviewed. Current implementation already includes:
- Dynamic conversation summarization
- Handles 0-second/no-answer calls
- Checks if user actually spoke
- Duration and disconnect reason tracking

**No changes needed** for summary service at this time. The duration fixes will automatically provide accurate timing data to the summary service.

## Code Quality

- [x] Python syntax validated
- [x] TypeScript build successful
- [x] Code review feedback addressed:
  - Removed duplicate imports
  - Fixed datetime handling (use `datetime.utcnow()` instead of `db.func.now()`)
  - Added isinstance checks for datetime objects
- [x] No Thread-related errors
- [x] Synchronous updates for critical data

## Next Steps (Future Work)

If call summaries still need improvement:
1. Move summary to worker job (after transcript ready)
2. Add chunking + map-reduce for very long calls (>10 minutes)
3. Add structured output format for action items
4. Implement guardrail: don't hallucinate if transcript insufficient

These are not critical given current implementation quality.
