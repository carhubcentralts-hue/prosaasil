# Fix Migrations 115-117: Calendar and Scheduled Messages

## Problem Identified

Server reports error:
```
column appointments.calendar_id does not exist
LINE 2: ...ated, appointments.source AS appointments_source, appointmen...
```

**Root Cause**: Migrations 115, 116, 117 have not been executed on the production database.

## What These Migrations Do

### Migration 115: Business Calendars System
Creates a multi-calendar system for businesses:
- ✅ Creates `business_calendars` table - manage multiple calendars per business
- ✅ Creates `calendar_routing_rules` table - AI-powered smart routing
- ✅ Adds `calendar_id` column to `appointments` table
- ✅ Creates default calendar for each existing business
- ✅ Links existing appointments to default calendar

### Migration 116: Scheduled WhatsApp Messages System
Creates infrastructure for timed WhatsApp messages:
- ✅ Creates `scheduled_message_rules` table - scheduling rules
- ✅ Creates `scheduled_rule_statuses` table - status associations
- ✅ Creates `scheduled_messages_queue` table - message queue

### Migration 117: Enable Scheduled Messages Page
- ✅ Adds `scheduled_messages` to `enabled_pages` for WhatsApp businesses

## Why Migrations Didn't Run

Possible reasons:
1. **Server configured as worker** - Workers don't run migrations
2. **Migrations disabled** - `RUN_MIGRATIONS` env var not set to 1
3. **Migration lock held** - Another process held the lock
4. **Database connection issue** - Communication problem with PostgreSQL

## Solution - 3 Ways

### Method 1: Run Dedicated Migration Script (Recommended)

Script created specifically for migrations 115-117:

```bash
cd /home/runner/work/prosaasil/prosaasil
python migration_run_115_116_117.py
```

This script:
- ✅ Checks if migrations already ran
- ✅ Forces migrations to run (bypasses blockers)
- ✅ Reports real-time progress
- ✅ Verifies everything worked after completion

### Method 2: Run All Migrations via db_migrate.py

```bash
cd /home/runner/work/prosaasil/prosaasil
python -m server.db_migrate
```

This runs **all** pending migrations (not just 115-117).

### Method 3: Run from Docker (if running in container)

```bash
docker exec prosaasil-backend python migration_run_115_116_117.py
```

Or:

```bash
docker exec prosaasil-backend python -m server.db_migrate
```

## Verify Migrations Ran

After running migrations, verify:

### 1. Check Logs
Look for these messages:
```
✅ Migration 115 complete: Business calendars and routing rules system added
✅ Migration 116 complete: Scheduled WhatsApp messages system added
✅ Migration 117 complete: 'scheduled_messages' page enabled for WhatsApp businesses
```

### 2. Check Database
Connect to PostgreSQL and verify:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('business_calendars', 'calendar_routing_rules', 
                     'scheduled_message_rules', 'scheduled_rule_statuses', 
                     'scheduled_messages_queue');

-- Check calendar_id column exists
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'appointments' AND column_name = 'calendar_id';

-- Check default calendars created
SELECT business_id, name, type_key FROM business_calendars;

-- Check businesses got scheduled_messages page
SELECT id, name, enabled_pages::text 
FROM business 
WHERE enabled_pages::text LIKE '%scheduled_messages%';
```

### 3. Check UI
1. Login to system
2. Navigate to "תזמון הודעות WhatsApp" (WhatsApp Message Scheduling)
3. Page should load without errors
4. Should see list of scheduling rules

## What Happens After Migrations?

### Calendar System
1. Each business gets a **default calendar** automatically
2. All existing appointments linked to this calendar
3. Can create additional calendars via management interface
4. AI can route appointments to different calendars based on rules

### Scheduled Messages
1. "תזמון הודעות WhatsApp" page appears in menu
2. Can create rules for automatic message sending
3. Rules trigger based on lead status changes
4. Messages sent within defined time windows

## Troubleshooting

### Error: "DATABASE_URL not set"
```bash
export DATABASE_URL="postgresql://user:password@host:5432/database"
```

### Error: "Could not acquire lock"
Another process is running migrations. Wait 30 seconds and try again.

### Error: "ModuleNotFoundError"
Ensure you're running from correct Python environment:
```bash
source .venv/bin/activate  # if using venv
```

### Migrations ran but still getting errors
1. **Restart server** - Server needs to reload models
2. **Clear cache** - If using Redis/cache, clear it
3. **Check logs** - Look for additional errors

## Automatic Execution in Future

Migrations should run **automatically** when server starts.

To ensure this works:
1. Set `RUN_MIGRATIONS=1` in `.env` file
2. Ensure `SERVICE_ROLE` is not set to `worker` on main server
3. Check logs during server startup

## Files Created

1. **migration_run_115_116_117.py** - Dedicated script for these migrations
2. **run_migrations_manual.py** - General migration runner script  
3. **תיקון_מיגרציות_115_116_117.md** - Hebrew documentation
4. **FIX_MIGRATIONS_115_116_117.md** - This English documentation

## Summary

**Problem**: appointments.calendar_id does not exist  
**Solution**: Run migrations 115-117  
**Easy Way**: `python migration_run_115_116_117.py`

After running:
- ✅ Scheduled messages page will work
- ✅ Calendar system will be active
- ✅ All errors will disappear

---

**Last Updated**: 2026-01-29  
**Migration Version**: 115-117  
**Status**: ✅ Ready to use
