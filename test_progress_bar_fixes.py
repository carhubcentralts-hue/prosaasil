#!/usr/bin/env python3
"""
Test suite for progress bar fixes
Verifies that stuck progress bars are properly handled

Run with: python test_progress_bar_fixes.py
"""
import os
import sys


def test_localStorage_caching_removed():
    """Test that localStorage no longer caches progress/status"""
    print("\n🧪 TEST: localStorage caching removed from useLongTaskPersistence")
    
    hook_path = os.path.join(
        os.path.dirname(__file__),
        'client',
        'src',
        'hooks',
        'useLongTaskPersistence.ts'
    )
    
    with open(hook_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify status field is NOT in TaskState interface
    if 'status: string' in content and 'TaskState' in content:
        # Check if it's in a comment
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'status: string' in line and 'TaskState' in '\n'.join(lines[max(0,i-5):i+1]):
                if not line.strip().startswith('//') and not line.strip().startswith('*'):
                    raise AssertionError("TaskState interface should NOT have 'status' field - only taskId and taskType")
    
    # Verify the fix comment exists
    if '✅ CRITICAL FIX' not in content or 'Progress bars must ALWAYS fetch state from server' not in content:
        raise AssertionError("Missing critical fix comment explaining the change")
    
    # Verify saveTask only saves taskId/taskType, not status
    if 'saveTask' in content:
        save_task_start = content.find('const saveTask')
        save_task_end = content.find('};', save_task_start) + 2
        save_task_section = content[save_task_start:save_task_end]
        
        if 'status' in save_task_section and 'taskId' in save_task_section:
            raise AssertionError("saveTask should NOT save status to localStorage")
    
    print("✅ localStorage only stores taskId reference, not progress/status")


def test_stale_detection_added_to_status_card():
    """Test that LongTaskStatusCard has heartbeat staleness detection"""
    print("\n🧪 TEST: Stale detection added to LongTaskStatusCard")
    
    card_path = os.path.join(
        os.path.dirname(__file__),
        'client',
        'src',
        'shared',
        'components',
        'ui',
        'LongTaskStatusCard.tsx'
    )
    
    with open(card_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for heartbeat props
    if 'heartbeatAt?' not in content:
        raise AssertionError("Missing heartbeatAt prop in LongTaskStatusCard")
    
    # Check for stale detection logic
    if 'isStale' not in content and 'STALE_THRESHOLD' not in content:
        raise AssertionError("Missing stale detection logic")
    
    # Check for stale warning display
    if 'תקוע' not in content or 'אין עדכון' not in content:
        raise AssertionError("Missing stale warning display in Hebrew")
    
    print("✅ LongTaskStatusCard has heartbeat staleness detection")


def test_stale_run_detection_in_receipt_routes():
    """Test that receipt sync routes auto-mark stale runs as failed"""
    print("\n🧪 TEST: Stale run detection in receipt routes")
    
    routes_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_receipts.py'
    )
    
    with open(routes_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the sync status endpoint
    if 'def get_sync_status' not in content:
        raise AssertionError("get_sync_status endpoint not found")
    
    # Find the function
    func_start = content.find('def get_sync_status')
    func_end = content.find('\n@receipts_bp.route', func_start + 1)
    if func_end == -1:
        func_end = content.find('\ndef ', func_start + 1)
    
    func_section = content[func_start:func_end]
    
    # Check for stale detection logic
    if 'STALE_THRESHOLD_SECONDS' not in func_section:
        raise AssertionError("Missing STALE_THRESHOLD_SECONDS constant")
    
    if '5 * 60' not in func_section:  # 5 minutes
        raise AssertionError("Stale threshold should be 5 minutes")
    
    if 'is_stale' not in func_section:
        raise AssertionError("Missing is_stale variable")
    
    # Check for auto-mark as failed
    if "sync_run.status = 'failed'" not in func_section:
        raise AssertionError("Missing auto-mark as failed logic")
    
    if 'no heartbeat' not in func_section.lower():
        raise AssertionError("Missing heartbeat explanation in error message")
    
    print("✅ Receipt sync routes auto-mark stale runs as failed")


def test_stale_broadcast_detection():
    """Test that broadcast routes auto-mark stale broadcasts as failed"""
    print("\n🧪 TEST: Stale broadcast detection")
    
    routes_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_whatsapp.py'
    )
    
    with open(routes_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the broadcast status endpoint
    if 'def get_broadcast_status' not in content:
        raise AssertionError("get_broadcast_status endpoint not found")
    
    # Find the function
    func_start = content.find('def get_broadcast_status')
    func_end = content.find('\n@whatsapp_bp.route', func_start + 1)
    if func_end == -1:
        func_end = content.find('\ndef ', func_start + 1)
    
    func_section = content[func_start:func_end]
    
    # Check for stale detection
    if 'STALE_THRESHOLD_SECONDS' not in func_section:
        raise AssertionError("Missing STALE_THRESHOLD_SECONDS constant")
    
    if 'is_stale' not in func_section:
        raise AssertionError("Missing is_stale variable")
    
    # Check for auto-mark as failed
    if "broadcast.status = 'failed'" not in func_section:
        raise AssertionError("Missing auto-mark as failed logic for broadcasts")
    
    if 'STALE BROADCAST DETECTED' not in func_section:
        raise AssertionError("Missing stale broadcast warning log")
    
    print("✅ Broadcast routes auto-mark stale broadcasts as failed")


def test_admin_reset_endpoint():
    """Test that admin reset endpoint exists"""
    print("\n🧪 TEST: Admin reset endpoint")
    
    routes_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'routes_admin.py'
    )
    
    with open(routes_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for reset endpoint
    if '/api/admin/business/<int:business_id>/reset-progress' not in content:
        raise AssertionError("Admin reset endpoint not found")
    
    if 'def reset_business_progress' not in content:
        raise AssertionError("reset_business_progress function not found")
    
    # Find the function
    func_start = content.find('def reset_business_progress')
    func_end = content.find('\n\n@admin_bp.route', func_start + 1)
    if func_end == -1:
        func_end = len(content)
    
    func_section = content[func_start:func_end]
    
    # Check it resets all three types
    checks = [
        ('ReceiptSyncRun', 'receipt sync runs'),
        ('WhatsAppBroadcast', 'broadcasts'),
        ('RecordingRun', 'recording runs')
    ]
    
    for model, name in checks:
        if model not in func_section:
            raise AssertionError(f"Admin reset should handle {name} ({model})")
    
    # Check for proper status updates
    if "status = 'failed'" not in func_section:
        raise AssertionError("Admin reset should mark runs as failed")
    
    print("✅ Admin reset endpoint exists and handles all run types")


def test_cache_headers_verified():
    """Test that nginx cache headers are properly configured"""
    print("\n🧪 TEST: Nginx cache headers")
    
    nginx_path = os.path.join(
        os.path.dirname(__file__),
        'docker',
        'nginx',
        'frontend-static.conf'
    )
    
    with open(nginx_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for assets caching
    if 'location /assets' not in content:
        raise AssertionError("Missing /assets location block")
    
    if 'expires 1y' not in content:
        raise AssertionError("Assets should have 1 year expiry")
    
    if 'immutable' not in content:
        raise AssertionError("Assets should be marked as immutable")
    
    # Check for index.html no-cache
    if 'location = /index.html' not in content:
        raise AssertionError("Missing /index.html location block")
    
    if 'no-cache' not in content or 'no-store' not in content:
        raise AssertionError("index.html should have no-cache headers")
    
    print("✅ Nginx cache headers properly configured")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Progress Bar Fixes - Test Suite")
    print("=" * 60)
    
    tests = [
        test_localStorage_caching_removed,
        test_stale_detection_added_to_status_card,
        test_stale_run_detection_in_receipt_routes,
        test_stale_broadcast_detection,
        test_admin_reset_endpoint,
        test_cache_headers_verified
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()

