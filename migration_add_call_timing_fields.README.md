# Migration 109 - Call Timing Fields (OBSOLETE)

## ⚠️ DO NOT RUN THIS MIGRATION

The file `migration_add_call_timing_fields.py` has been renamed to `.OBSOLETE` because **Migration 109 is intentionally a NO-OP**.

## Why is this migration obsolete?

According to `server/db_migrate.py`, Migration 109 is in "backward compatibility mode" and does NOT create the following columns:
- `call_log.started_at`
- `call_log.ended_at`  
- `call_log.duration_sec`

Instead, the system uses **Migration 51 columns** (which are the correct columns to use):
- `call_log.stream_started_at` ✅
- `call_log.stream_ended_at` ✅
- `call_log.stream_duration_sec` ✅

## What does the code say?

From `server/db_migrate.py` lines 5530-5541:

```python
# Migration 109: NO-OP (Backward Compatibility Mode)
# ...
# to work without started_at/ended_at/duration_sec columns.
checkpoint("Migration 109: NO-OP (skipped - uses Migration 51 columns)")
checkpoint("  ℹ️ System uses stream_started_at/stream_ended_at from Migration 51")
checkpoint("  ℹ️ Columns started_at/ended_at/duration_sec are NOT created")
checkpoint("✅ Migration 109 complete: Skipped (backward compatibility mode)")
```

## If you see errors about call_log.started_at

If you encounter errors like:
```
psycopg2.errors.UndefinedColumn: column call_log.started_at does not exist
```

This means there's code trying to query `call_log.started_at` directly. The fix is to:
1. Replace `started_at` with `stream_started_at`
2. Replace `ended_at` with `stream_ended_at`
3. Replace `duration_sec` with `stream_duration_sec`

## Model Definition

From `server/models_sql.py`, the `CallLog` model uses:

```python
# 🔥 DURATION TRACKING: Use these columns for call timing (Migration 51)
# Stream metrics - PRIMARY source for call timing
stream_started_at = db.Column(db.DateTime, nullable=True)  # When WebSocket stream started
stream_ended_at = db.Column(db.DateTime, nullable=True)  # When WebSocket stream ended
stream_duration_sec = db.Column(db.Float, nullable=True)  # Stream duration in seconds
```

## Tests

See `test_migration_109_backward_compat.py` for verification that the system works correctly without the `started_at`/`ended_at`/`duration_sec` columns.
