# Quick Fix: Migrations 115-117 Not Running

## The Problem
```
ERROR: column appointments.calendar_id does not exist
```

The scheduled messages page ("דף תזמון הודעות") doesn't display anything.

## The Solution

**Run this one command:**

```bash
python migration_run_115_116_117.py
```

That's it! This will:
1. Check if migrations are needed
2. Run migrations 115, 116, 117
3. Verify everything worked
4. Report status

## Expected Output

```
🔧 ================================================================================
🔧 STANDALONE MIGRATION RUNNER: Migrations 115-117
🔧 ================================================================================
🔧 Database: postgresql://***@***
🔧 Found 50 existing tables
🔧 appointments table: ❌ MISSING calendar_id
🔧 Running apply_migrations()...
🔧 Migration 115: Adding business calendars and routing rules system
🔧   ✅ business_calendars table created
🔧   ✅ calendar_routing_rules table created
🔧   ✅ calendar_id column added to appointments
🔧 ✅ Migration 115 complete
🔧 Migration 116: Adding scheduled WhatsApp messages system
🔧   ✅ scheduled_message_rules table created
🔧   ✅ scheduled_rule_statuses table created
🔧   ✅ scheduled_messages_queue table created
🔧 ✅ Migration 116 complete
🔧 Migration 117: Enable 'scheduled_messages' page for businesses with WhatsApp
🔧   ✅ Migration 117 complete
🔧 ================================================================================
🔧 VERIFICATION
🔧 ================================================================================
🔧 Migration 115: Business Calendars System
🔧   ✅ business_calendars table exists
🔧   ✅ calendar_routing_rules table exists
🔧   ✅ appointments.calendar_id column exists
🔧 Migration 116: Scheduled Messages System
🔧   ✅ scheduled_message_rules table exists
🔧   ✅ scheduled_rule_statuses table exists
🔧   ✅ scheduled_messages_queue table exists
🔧 Migration 117: Scheduled Messages Page Enabled
🔧   ✅ 5 business(es) have scheduled_messages page enabled
🔧 ================================================================================
🔧 ✅ MIGRATION CHECK COMPLETE
🔧 ================================================================================
```

## Alternative Method

If above doesn't work, run the main migration system:

```bash
python -m server.db_migrate
```

## For Docker Deployments

If running in Docker container:

```bash
docker exec prosaasil-backend python migration_run_115_116_117.py
```

## After Running

1. **Restart your server** (if it's running)
2. **Refresh the scheduled messages page**
3. Everything should work now!

## Need Help?

Read the full documentation:
- **Hebrew**: `תיקון_מיגרציות_115_116_117.md`
- **English**: `FIX_MIGRATIONS_115_116_117.md`

## Files in This Fix

- `migration_run_115_116_117.py` - Main fix script ⭐
- `run_migrations_manual.py` - General migration runner
- `README_FIX_MIGRATIONS.md` - This file
- `תיקון_מיגרציות_115_116_117.md` - Hebrew docs
- `FIX_MIGRATIONS_115_116_117.md` - English docs

---

**Quick Start**: `python migration_run_115_116_117.py`
