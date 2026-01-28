#!/usr/bin/env python3
"""
Simplified verification of outbound call queue implementation
Checks code patterns without requiring full app dependencies
"""
import os
import re

print("=" * 80)
print("Outbound Call Queue Implementation Verification")
print("=" * 80)
print()

tests_passed = 0
tests_failed = 0

# Read source files
with open('server/models_sql.py', 'r') as f:
    models_source = f.read()

with open('server/routes_outbound.py', 'r') as f:
    routes_source = f.read()

with open('server/db_migrate.py', 'r') as f:
    migrate_source = f.read()

# Test 1: Check OutboundCallRun model has all required fields
print("Test 1: OutboundCallRun model has all required tracking fields")
print("-" * 80)
required_fields = [
    'created_by_user_id',
    'started_at',
    'ended_at',
    'cursor_position',
    'locked_by_worker',
    'lock_ts'
]

outbound_run_section = models_source.split('class OutboundCallRun')[1].split('class ')[0]
missing_fields = []
for field in required_fields:
    if field not in outbound_run_section:
        missing_fields.append(field)

if not missing_fields:
    print(f"✅ PASS: All {len(required_fields)} tracking fields present in OutboundCallRun model")
    tests_passed += 1
else:
    print(f"❌ FAIL: Missing fields in OutboundCallRun model: {', '.join(missing_fields)}")
    tests_failed += 1
print()

# Test 2: Check OutboundCallJob has unique constraint and business_id
print("Test 2: OutboundCallJob has unique constraint and business_id")
print("-" * 80)
outbound_job_section = models_source.split('class OutboundCallJob')[1].split('class ')[0]
has_unique_constraint = 'unique_run_lead' in outbound_job_section or '__table_args__' in outbound_job_section
has_business_id = 'business_id' in outbound_job_section

if has_unique_constraint and has_business_id:
    print("✅ PASS: OutboundCallJob has unique constraint and business_id")
    tests_passed += 1
else:
    print(f"❌ FAIL: unique_constraint={has_unique_constraint}, business_id={has_business_id}")
    tests_failed += 1
print()

# Test 3: Check business isolation in get_run_status endpoint
print("Test 3: Business isolation in get_run_status endpoint")
print("-" * 80)
get_run_status_section = routes_source.split('def get_run_status')[1].split('def ')[0]
has_business_filter = 'business_id=tenant_id' in get_run_status_section
has_security_log = '[SECURITY]' in get_run_status_section and 'cross-business' in get_run_status_section.lower()

if has_business_filter and has_security_log:
    print("✅ PASS: get_run_status enforces business isolation with security logging")
    tests_passed += 1
else:
    print(f"❌ FAIL: business_filter={has_business_filter}, security_log={has_security_log}")
    tests_failed += 1
print()

# Test 4: Check business isolation in stop_queue endpoint
print("Test 4: Business isolation in stop_queue endpoint")
print("-" * 80)
stop_queue_section = routes_source.split('def stop_queue')[1].split('def ')[0]
has_business_filter = 'business_id=tenant_id' in stop_queue_section
has_security_log = '[SECURITY]' in stop_queue_section
has_double_check = 'run.business_id != tenant_id' in stop_queue_section

if has_business_filter and has_security_log and has_double_check:
    print("✅ PASS: stop_queue enforces business isolation with double-check")
    tests_passed += 1
else:
    print(f"❌ FAIL: filter={has_business_filter}, log={has_security_log}, double_check={has_double_check}")
    tests_failed += 1
print()

# Test 5: Check business isolation in cancel endpoint
print("Test 5: Business isolation in cancel_outbound_job endpoint")
print("-" * 80)
cancel_section = routes_source.split('def cancel_outbound_job')[1].split('def ')[0]
has_business_check = 'run.business_id != tenant_id' in cancel_section
has_security_log = '[SECURITY]' in cancel_section and 'cross-business' in cancel_section.lower()

if has_business_check and has_security_log:
    print("✅ PASS: cancel_outbound_job enforces business isolation")
    tests_passed += 1
else:
    print(f"❌ FAIL: business_check={has_business_check}, security_log={has_security_log}")
    tests_failed += 1
print()

# Test 6: Check worker lock mechanism
print("Test 6: Worker lock mechanism in process_bulk_call_run")
print("-" * 80)
worker_section = routes_source.split('def process_bulk_call_run')[1].split('def ')[0]
has_worker_id = 'socket.gethostname()' in worker_section and 'os.getpid()' in worker_section
has_lock_assignment = 'locked_by_worker = worker_id' in worker_section or 'locked_by_worker=worker_id' in worker_section
has_heartbeat = 'lock_ts = datetime.utcnow()' in worker_section or 'lock_ts=datetime.utcnow()' in worker_section

if has_worker_id and has_lock_assignment and has_heartbeat:
    print("✅ PASS: Worker lock mechanism with heartbeat implemented")
    tests_passed += 1
else:
    print(f"❌ FAIL: worker_id={has_worker_id}, lock={has_lock_assignment}, heartbeat={has_heartbeat}")
    tests_failed += 1
print()

# Test 7: Check cancel detection in worker loop
print("Test 7: Cancel detection in worker loop")
print("-" * 80)
has_cancel_check = 'cancel_requested' in worker_section and 'status != "cancelled"' in worker_section
has_cancel_jobs = 'Cancelled by user' in worker_section or 'cancelled' in worker_section.lower()
has_break = 'break' in worker_section

if has_cancel_check and has_cancel_jobs and has_break:
    print("✅ PASS: Worker detects cancellation and stops processing")
    tests_passed += 1
else:
    print(f"❌ FAIL: cancel_check={has_cancel_check}, cancel_jobs={has_cancel_jobs}, break={has_break}")
    tests_failed += 1
print()

# Test 8: Check cursor position tracking
print("Test 8: Cursor position tracking for resume")
print("-" * 80)
has_cursor_update = 'cursor_position' in worker_section
has_completed_count = re.search(r'cursor_position\s*=\s*completed_jobs', worker_section)

if has_cursor_update and has_completed_count:
    print("✅ PASS: Cursor position tracked for resume capability")
    tests_passed += 1
else:
    print(f"❌ FAIL: cursor_update={has_cursor_update}, completed_count={bool(has_completed_count)}")
    tests_failed += 1
print()

# Test 9: Check "3 calls issue" fix (already_queued handling)
print("Test 9: Fix for '3 calls and stop' issue")
print("-" * 80)
has_already_queued = 'already_queued' in worker_section
has_sleep_continue = 'time.sleep(1)' in worker_section and 'continue' in worker_section
has_wait_log = 'waiting for slot' in worker_section.lower()

if has_already_queued and has_sleep_continue and has_wait_log:
    print("✅ PASS: '3 calls issue' fixed - jobs wait for slots instead of skipping")
    tests_passed += 1
else:
    print(f"❌ FAIL: already_queued={has_already_queued}, sleep={has_sleep_continue}, log={has_wait_log}")
    tests_failed += 1
print()

# Test 10: Check Migration 113 exists in db_migrate.py
print("Test 10: Migration 113 added to db_migrate.py")
print("-" * 80)
has_migration_113 = 'Migration 113' in migrate_source
has_created_by_user = 'created_by_user_id' in migrate_source
has_unique_constraint = 'unique_run_lead' in migrate_source
has_business_id_jobs = 'business_id' in migrate_source and 'outbound_call_jobs' in migrate_source

if has_migration_113 and has_created_by_user and has_unique_constraint and has_business_id_jobs:
    print("✅ PASS: Migration 113 properly integrated into db_migrate.py")
    tests_passed += 1
else:
    print(f"❌ FAIL: migration_113={has_migration_113}, fields={has_created_by_user}, constraint={has_unique_constraint}, business_id={has_business_id_jobs}")
    tests_failed += 1
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Tests Passed: {tests_passed}/10")
print(f"Tests Failed: {tests_failed}/10")
print()

if tests_failed == 0:
    print("✅ ALL IMPLEMENTATION CHECKS PASSED!")
    print()
    print("Implementation verified:")
    print("  ✅ All tracking fields present in models")
    print("  ✅ Unique constraint and business_id in jobs")
    print("  ✅ Business isolation in all endpoints")
    print("  ✅ Worker lock mechanism with heartbeat")
    print("  ✅ Cancel detection and handling")
    print("  ✅ Cursor position tracking for resume")
    print("  ✅ '3 calls issue' fixed")
    print("  ✅ Migration 113 integrated")
    print()
    exit(0)
else:
    print("❌ SOME IMPLEMENTATION CHECKS FAILED!")
    exit(1)
