# Database Schema Management

## ⚠️ IMPORTANT: This is a Flask/Python Project

This project uses **Flask + SQLAlchemy** (Python) for database management, NOT Drizzle (TypeScript).

### Schema Location

The database schema is defined in: `server/models_sql.py`

### Migration Management

**DO NOT use Drizzle migrations!**

This project was created from a `fullstack_js` template, but the backend is Python.

If Replit shows migration warnings about:
- `business_contact_channels` table
- `business_settings` columns (slot_size_min, allow_24_7, etc.)
- `call_log.direction` column

**IGNORE THESE WARNINGS!** These are all correctly defined in `server/models_sql.py` and exist in the production database.

### Why the Warnings?

Replit's auto-migration detection looks for `shared/schema.ts` (Drizzle schema for TypeScript).
Since this file doesn't exist (because we use Python SQLAlchemy), Replit gets confused.

### Correct Migration Process

For this Python/Flask project, use:

1. **Manual SQL** (for production):
   ```bash
   psql $DATABASE_URL -c "ALTER TABLE ..."
   ```

2. **Flask-Migrate** (future enhancement):
   ```bash
   flask db migrate -m "description"
   flask db upgrade
   ```

3. **Direct SQLAlchemy** (development):
   ```python
   db.create_all()  # Creates tables based on models_sql.py
   ```

### Current Schema Status

✅ All tables and columns in production database match `server/models_sql.py`
✅ No migrations needed
✅ System is working correctly

**If you see migration warnings in Replit UI: CANCEL/IGNORE them!**
