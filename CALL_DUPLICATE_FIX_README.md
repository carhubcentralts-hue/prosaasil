# Call Log Duplicate Fix and Direction Classification

## Quick Summary

This PR fixes critical issues with call logging:
1. **Duplicate call logs** - Twilio creates parent + child call legs, both were saved
2. **Incorrect direction** - outbound-api/outbound-dial not mapped correctly
3. **No UI filter** - Missing filter for inbound/outbound calls
4. **Webhook data loss** - Direction and ParentCallSid not captured

## Changes Made

### Database (Migration 41)
- Added `parent_call_sid` VARCHAR(64) to track parent/child relationships
- Added `twilio_direction` VARCHAR(32) to store original Twilio direction values
- Created indexes on both fields for performance

### Backend
- **New function**: `normalize_call_direction()` - Maps Twilio directions to inbound/outbound/unknown
- **Updated**: `save_call_status_async()` - UPSERT logic to prevent duplicates
- **Updated**: All webhooks capture Direction and ParentCallSid:
  - `/webhook/incoming_call`
  - `/webhook/call_status`
  - `/webhook/handle_recording`
  - `/webhook/stream_status`
- **Updated**: `/api/calls` - Filters out parent calls by default

### Frontend
- **Added**: Direction filter dropdown (All/Inbound/Outbound) in CallsTab
- **Updated**: Empty state messages based on filter
- **Updated**: Filter calls by direction

## Running the Migration

### Option 1: Dedicated Script
```bash
python3 run_call_fix_migration.py
```

### Option 2: Standard Migration
```bash
python3 -m server.db_migrate
```

### Option 3: Automatic
Migration runs automatically when server starts.

## Verification

### 1. Check database columns added
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'call_log' 
  AND column_name IN ('parent_call_sid', 'twilio_direction');
```

### 2. Test a call
- Make an inbound call
- Check UI shows single call (no duplicate)
- Verify direction is correct ("שיחה נכנסת")
- Test direction filter works

### 3. Check in database
```sql
-- Calls with parent (child legs)
SELECT call_sid, parent_call_sid, direction, twilio_direction
FROM call_log
WHERE parent_call_sid IS NOT NULL
ORDER BY created_at DESC LIMIT 10;

-- Direction distribution
SELECT direction, COUNT(*) FROM call_log GROUP BY direction;
```

## What's Fixed

✅ Duplicate calls - **FIXED** (filters out parent calls)  
✅ Direction mapping - **FIXED** (outbound-* → outbound, inbound-* → inbound)  
✅ UI filter - **ADDED** (dropdown to filter by direction)  
✅ Webhook data - **FIXED** (captures Direction and ParentCallSid)  
✅ Migrations - **READY** (Migration 41a & 41b)

## Technical Details

### Direction Normalization
```python
"outbound-api" → "outbound"    # Parent call
"outbound-dial" → "outbound"   # Actual outbound call
"inbound" → "inbound"          # Inbound call
None/empty → "unknown"         # Unknown
```

### Parent Call Filtering
By default, `/api/calls` filters out:
- Parent calls with duration ≤ 1 second
- Calls that have corresponding child legs

Use `?show_all=true` to see all calls including parents (for debugging).

### Backward Compatibility
- New fields are nullable
- Old calls without these fields still work
- Only new calls will have direction/parent data

## Files Changed

### Backend
- `server/models_sql.py` - Added fields to CallLog model
- `server/tasks_recording.py` - Added normalize_call_direction(), updated save_call_status
- `server/routes_twilio.py` - Updated all webhooks to capture new fields
- `server/routes_calls.py` - Updated /api/calls with smart filtering
- `server/db_migrate.py` - Added Migration 41a & 41b

### Frontend
- `client/src/pages/Leads/LeadDetailPage.tsx` - Added direction filter UI

### Scripts & Docs
- `server/scripts/add_call_parent_and_twilio_direction.sql` - Manual migration SQL
- `run_call_fix_migration.py` - Dedicated migration runner
- `תיקון_כפילות_שיחות.md` - Hebrew documentation

## Testing Checklist

- [ ] Run migration successfully
- [ ] Make test inbound call → verify single entry, correct direction
- [ ] Make test outbound call → verify single entry, correct direction
- [ ] Test direction filter in UI (All/Inbound/Outbound)
- [ ] Check recordings still work
- [ ] Verify no duplicate calls appear
- [ ] Check database fields populated for new calls

## Notes

- Existing calls won't have new fields (NULL values)
- Only affects new calls from this point forward
- Minimal changes - surgical fixes only
- No breaking changes to existing functionality
