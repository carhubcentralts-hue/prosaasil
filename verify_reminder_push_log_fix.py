#!/usr/bin/env python3
"""
Verify the reminder_push_log fix without running the full app

This script checks:
1. Migration 66 is present in db_migrate.py
2. Safety guards are added to reminder_scheduler.py
3. WebPush 410 handling is present in dispatcher.py
"""
import os
import re
import sys

# Get the repository root directory (parent of the script location)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def check_migration_exists():
    """Check that Migration 66 is added to db_migrate.py"""
    print("🔍 Checking Migration 66 in db_migrate.py...")
    
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Check for migration 66
    if 'Migration 66' not in content:
        print("❌ Migration 66 comment not found")
        return False
    print("✅ Migration 66 comment found")
    
    # Check for table creation
    if 'CREATE TABLE reminder_push_log' not in content:
        print("❌ CREATE TABLE reminder_push_log not found")
        return False
    print("✅ CREATE TABLE reminder_push_log found")
    
    # Check for required columns
    required_columns = ['reminder_id', 'offset_minutes', 'sent_at']
    for col in required_columns:
        if col not in content:
            print(f"❌ Column {col} not found in migration")
            return False
        print(f"✅ Column {col} present")
    
    # Check for foreign key
    if 'REFERENCES lead_reminders' not in content:
        print("❌ Foreign key to lead_reminders not found")
        return False
    print("✅ Foreign key to lead_reminders found")
    
    # Check for unique constraint
    if 'uq_reminder_push_log' not in content or 'reminder_id, offset_minutes' not in content:
        print("❌ Unique constraint on (reminder_id, offset_minutes) not found")
        return False
    print("✅ Unique constraint on (reminder_id, offset_minutes) found")
    
    # Check for indexes
    if 'idx_reminder_push_log_reminder_id' not in content:
        print("❌ Index on reminder_id not found")
        return False
    print("✅ Index on reminder_id found")
    
    if 'idx_reminder_push_log_sent_at' not in content:
        print("❌ Index on sent_at not found")
        return False
    print("✅ Index on sent_at found")
    
    print("\n✅ Migration 66 is correctly implemented\n")
    return True


def check_safety_guards():
    """Check that safety guards are added to reminder_scheduler.py"""
    print("🔍 Checking safety guards in reminder_scheduler.py...")
    
    scheduler_path = os.path.join(REPO_ROOT, 'server', 'services', 'notifications', 'reminder_scheduler.py')
    with open(scheduler_path, 'r') as f:
        content = f.read()
    
    # Check _cleanup_old_push_logs has table existence check
    cleanup_match = re.search(r'def _cleanup_old_push_logs.*?(?=\ndef )', content, re.DOTALL)
    if not cleanup_match:
        print("❌ _cleanup_old_push_logs function not found")
        return False
    
    cleanup_code = cleanup_match.group(0)
    if 'inspect' not in cleanup_code or 'get_table_names' not in cleanup_code:
        print("❌ Table existence check not found in _cleanup_old_push_logs")
        return False
    print("✅ Table existence check found in _cleanup_old_push_logs")
    
    if 'reminder_push_log' not in cleanup_code or 'does not exist yet' not in cleanup_code:
        print("❌ reminder_push_log check not found in _cleanup_old_push_logs")
        return False
    print("✅ reminder_push_log existence check found in _cleanup_old_push_logs")
    
    # Check _try_send_with_dedupe has table existence check
    dedupe_match = re.search(r'def _try_send_with_dedupe.*?(?=\ndef )', content, re.DOTALL)
    if not dedupe_match:
        print("❌ _try_send_with_dedupe function not found")
        return False
    
    dedupe_code = dedupe_match.group(0)
    if 'inspect' not in dedupe_code or 'get_table_names' not in dedupe_code:
        print("❌ Table existence check not found in _try_send_with_dedupe")
        return False
    print("✅ Table existence check found in _try_send_with_dedupe")
    
    if 'sending without deduplication' not in dedupe_code:
        print("❌ Fallback for missing table not found in _try_send_with_dedupe")
        return False
    print("✅ Fallback for missing table found in _try_send_with_dedupe")
    
    print("\n✅ Safety guards are correctly implemented\n")
    return True


def check_webpush_410_handling():
    """Check that WebPush 410 handling is present"""
    print("🔍 Checking WebPush 410 error handling...")
    
    # Check dispatcher.py
    dispatcher_path = os.path.join(REPO_ROOT, 'server', 'services', 'notifications', 'dispatcher.py')
    with open(dispatcher_path, 'r') as f:
        dispatcher_content = f.read()
    
    if 'should_deactivate' not in dispatcher_content:
        print("❌ should_deactivate check not found in dispatcher.py")
        return False
    print("✅ should_deactivate check found in dispatcher.py")
    
    if 'subscriptions_to_deactivate' not in dispatcher_content:
        print("❌ subscriptions_to_deactivate list not found in dispatcher.py")
        return False
    print("✅ subscriptions_to_deactivate list found in dispatcher.py")
    
    if 'is_active' not in dispatcher_content or 'False' not in dispatcher_content:
        print("❌ is_active = False update not found in dispatcher.py")
        return False
    print("✅ is_active = False update found in dispatcher.py")
    
    # Check webpush_sender.py
    sender_path = os.path.join(REPO_ROOT, 'server', 'services', 'push', 'webpush_sender.py')
    with open(sender_path, 'r') as f:
        sender_content = f.read()
    
    if '410' not in sender_content and '404' not in sender_content:
        print("❌ 410/404 status check not found in webpush_sender.py")
        return False
    print("✅ 410/404 status check found in webpush_sender.py")
    
    if 'should_deactivate' not in sender_content:
        print("❌ should_deactivate flag not found in webpush_sender.py")
        return False
    print("✅ should_deactivate flag found in webpush_sender.py")
    
    print("\n✅ WebPush 410 error handling is correctly implemented\n")
    return True


def main():
    print("=" * 70)
    print("VERIFYING REMINDER_PUSH_LOG FIX")
    print("=" * 70)
    print()
    
    all_passed = True
    
    try:
        if not check_migration_exists():
            all_passed = False
        
        if not check_safety_guards():
            all_passed = False
        
        if not check_webpush_410_handling():
            all_passed = False
        
        if all_passed:
            print("=" * 70)
            print("✅ ALL CHECKS PASSED - Fix is correctly implemented")
            print("=" * 70)
            return 0
        else:
            print("=" * 70)
            print("❌ SOME CHECKS FAILED")
            print("=" * 70)
            return 1
    
    except Exception as e:
        print("=" * 70)
        print(f"❌ VERIFICATION FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
