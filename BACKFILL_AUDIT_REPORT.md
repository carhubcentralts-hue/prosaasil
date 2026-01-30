# Backfill Audit Report

Generated: 2026-01-30T10:41:57.998079

## Summary

- Total migrations with DML: 25
- HIGH priority: 11
- MEDIUM priority: 9
- LOW priority: 5

## Priority Definitions

- **HIGH**: Operations on hot tables (leads, call_log, receipts, messages, appointments)
- **MEDIUM**: UPDATE/INSERT operations on other tables
- **LOW**: Metadata or small table operations


## HIGH Priority Backfills

| Migration | Description | Tables | DML Types |
|-----------|-------------|--------|----------|
| 90 | No description | many, pg_stat_activity, sqlalchemy (+15 more) | exec_dml, backfill_comment |
| 11 | No description | sqlalchemy, leads | UPDATE |
| 81 | No description | business | UPDATE |
| 84 | No description | if, sqlalchemy, receipts (+5 more) | UPDATE, backfill_comment |
| 91 | No description | receipts | UPDATE, backfill_comment |
| 92 | No description | low, reports, receipts | UPDATE, backfill_comment |
| 96 | No description | leads | UPDATE |
| 97 | No description | same, pg_indexes, receipts | UPDATE |
| 110 | No description | call_log, sqlalchemy | UPDATE |
| 112 | No description | any, existing, sqlalchemy (+1 more) | UPDATE |
| 117 | No description | faqs, sqlalchemy, leads (+3 more) | UPDATE |

## MEDIUM Priority Backfills

| Migration | Description | Tables | DML Types |
|-----------|-------------|--------|----------|
| 61 | No description | invalid, businesses | UPDATE |
| 71 | No description | only, server, sqlalchemy (+1 more) | UPDATE |
| 75 | No description | Free, sqlalchemy, note_type (+2 more) | UPDATE |
| 86 | No description | receipt_sync_runs, crashed, sqlalchemy (+1 more) | UPDATE |
| 89 | No description | status, receipt_sync_runs, affecting | UPDATE |
| 102 | No description | tts_provider, business | UPDATE |
| 103 | No description | background_jobs, crashed, sqlalchemy (+1 more) | UPDATE |
| 113 | No description | sqlalchemy, parent, jobs (+2 more) | UPDATE, DELETE |
| 114 | No description | lock_ts, outbound_call_runs, sqlalchemy | UPDATE |

## LOW Priority Backfills

| Migration | Description | Tables | DML Types |
|-----------|-------------|--------|----------|
| 6 | No description | messages, sqlalchemy | DELETE |
| 15 | No description | call_log, sqlalchemy | DELETE |
| 36 | No description | data | backfill_comment |
| 85 | No description | sqlalchemy, DB | backfill_comment |
| 87 | No description | whatsapp_message, webhook | DELETE |

## Next Steps

1. Review HIGH priority migrations first
2. Move each backfill to db_backfills.py registry
3. Test each backfill independently
4. Update migrations to be schema-only
5. Add guard test to prevent future backfills in migrations
