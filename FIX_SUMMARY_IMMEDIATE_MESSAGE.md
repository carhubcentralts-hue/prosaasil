# Fix Summary: immediate_message Parameter Error

## Problem
The error occurred when updating a scheduled message rule:
```
TypeError: update_rule() got an unexpected keyword argument 'immediate_message'
```

The frontend was sending an `immediate_message` parameter when updating rules, but the backend didn't accept this parameter.

## Root Cause
The frontend UI (ScheduledMessagesPage.tsx) was designed to support separate messages:
1. An immediate message sent when a lead enters a status (`immediate_message`)
2. Delayed messages sent later (`message_text` or step messages)

However, the backend service (`scheduled_messages_service.py`) only accepted and used `message_text` for both immediate and delayed sends.

## Solution
Added full support for the `immediate_message` parameter throughout the backend:

### 1. Database Model (`server/models_sql.py`)
- Added `immediate_message` column to `ScheduledMessageRule` model
- Type: `Text`, nullable (for backward compatibility)
- Positioned after `send_immediately_on_enter` for logical grouping

### 2. Service Layer (`server/services/scheduled_messages_service.py`)
- Added `immediate_message` parameter to `create_rule()` function
- Added `immediate_message` parameter to `update_rule()` function
- Updated `create_scheduled_tasks_for_lead()` to use `immediate_message` when available
- Falls back to `message_text` if `immediate_message` is not set (backward compatibility)

### 3. API Routes (`server/routes_scheduled_messages.py`)
- Updated `create_rule()` endpoint to accept and pass `immediate_message`
- Updated `update_rule()` endpoint to accept and pass `immediate_message` (via `**data`)
- Added `immediate_message` to all API response objects
- Used `getattr()` for safe attribute access during migration period

### 4. Database Migration (`migration_add_immediate_message.py`)
- Created migration script to add `immediate_message` column
- Migration is idempotent (checks if column exists before adding)
- Column is nullable for backward compatibility

## Backward Compatibility
The fix maintains full backward compatibility:
- Existing rules without `immediate_message` continue to work
- When `immediate_message` is null, the system falls back to `message_text`
- All existing API calls continue to work without changes
- Uses `getattr()` for safe attribute access during migration

## Testing
Created comprehensive test suite (`test_immediate_message_fix.py`) that verifies:
1. ✅ Service functions accept `immediate_message` parameter
2. ✅ Model has `immediate_message` column defined
3. ✅ API routes handle `immediate_message` parameter correctly
4. ✅ Service logic uses `immediate_message` with proper fallback
5. ✅ Database migration file exists and is correct

## Files Changed
1. `server/models_sql.py` - Added column definition
2. `server/services/scheduled_messages_service.py` - Added parameter support and logic
3. `server/routes_scheduled_messages.py` - Updated API endpoints
4. `migration_add_immediate_message.py` - New migration script

## Deployment Instructions
1. Apply the code changes (already committed)
2. Run the migration: `python migration_add_immediate_message.py`
3. Restart the backend server
4. No frontend changes needed (frontend already supports this)

## Result
After this fix:
- ✅ Frontend can send `immediate_message` parameter
- ✅ Backend accepts and stores the parameter
- ✅ System uses `immediate_message` for immediate sends when available
- ✅ Falls back to `message_text` for backward compatibility
- ✅ No breaking changes to existing functionality
- ✅ Error is resolved
