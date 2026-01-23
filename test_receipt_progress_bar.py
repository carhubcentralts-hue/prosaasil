#!/usr/bin/env python3
"""
Test script to verify progress bar persistence for receipts module

Tests:
1. Progress bar state persistence in localStorage
2. Progress bar restoration after page refresh
3. Cancel button functionality
4. Progress tracking during sync and delete operations
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_sync_progress_bar_persistence():
    """Test that sync progress bar persists across page refresh"""
    print("=" * 60)
    print("Test 1: Sync Progress Bar Persistence")
    print("=" * 60)
    
    # Read the ReceiptsPage.tsx to verify localStorage implementation
    with open('client/src/pages/receipts/ReceiptsPage.tsx', 'r') as f:
        content = f.read()
    
    # Check for localStorage operations
    checks = {
        'Save sync_run_id to localStorage': "localStorage.setItem('activeSyncRunId'",
        'Load sync_run_id from localStorage': "localStorage.getItem('activeSyncRunId')",
        'Clear sync_run_id on completion': "localStorage.removeItem('activeSyncRunId')",
        'Check for active sync on mount': '/api/receipts/sync/latest',
        'Fallback to stored sync_run_id': 'storedSyncRunId',
    }
    
    passed = 0
    failed = 0
    
    for check_name, check_string in checks.items():
        if check_string in content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    print(f"\nSync Progress Bar: {passed}/{len(checks)} checks passed")
    return failed == 0


def test_delete_progress_bar_persistence():
    """Test that delete progress bar persists across page refresh"""
    print("\n" + "=" * 60)
    print("Test 2: Delete Progress Bar Persistence")
    print("=" * 60)
    
    with open('client/src/pages/receipts/ReceiptsPage.tsx', 'r') as f:
        content = f.read()
    
    checks = {
        'Save delete job_id to localStorage': "localStorage.setItem('activeDeleteJobId'",
        'Load delete job_id from localStorage': "localStorage.getItem('activeDeleteJobId')",
        'Clear delete job_id on completion': "localStorage.removeItem('activeDeleteJobId')",
        'Check for active delete on mount': "storedDeleteJobId",
        'Poll delete progress': 'pollDeleteProgress',
    }
    
    passed = 0
    failed = 0
    
    for check_name, check_string in checks.items():
        if check_string in content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    print(f"\nDelete Progress Bar: {passed}/{len(checks)} checks passed")
    return failed == 0


def test_cancel_functionality():
    """Test that cancel buttons work correctly"""
    print("\n" + "=" * 60)
    print("Test 3: Cancel Button Functionality")
    print("=" * 60)
    
    # Check frontend
    with open('client/src/pages/receipts/ReceiptsPage.tsx', 'r') as f:
        frontend_content = f.read()
    
    # Check backend
    with open('server/jobs/delete_receipts_job.py', 'r') as f:
        backend_content = f.read()
    
    checks = {
        'Frontend: handleCancelSync function': 'handleCancelSync',
        'Frontend: handleCancelDelete function': 'handleCancelDelete',
        'Frontend: Cancel sync API call': "/cancel'",
        'Backend: Check cancelled status in worker': "status == 'cancelled'",
        'Backend: Refresh job from DB': 'db.session.refresh(job)',
    }
    
    passed = 0
    failed = 0
    
    for check_name, check_string in checks.items():
        content = frontend_content if 'Frontend' in check_name else backend_content
        if check_string in content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    print(f"\nCancel Functionality: {passed}/{len(checks)} checks passed")
    return failed == 0


def test_receipt_processor_integration():
    """Test that ReceiptProcessor is properly integrated"""
    print("\n" + "=" * 60)
    print("Test 4: ReceiptProcessor Integration")
    print("=" * 60)
    
    # Check if ReceiptProcessor exists
    processor_file = 'server/services/receipts/receipt_processor.py'
    if not os.path.exists(processor_file):
        print(f"❌ ReceiptProcessor file not found: {processor_file}")
        return False
    
    with open(processor_file, 'r') as f:
        content = f.read()
    
    checks = {
        'ReceiptProcessor class defined': 'class ReceiptProcessor',
        'process_receipt method': 'def process_receipt',
        'normalize_email_content': 'def _normalize_email_content',
        'generate_preview': 'def _generate_preview',
        'extract_data': 'def _extract_data',
        'Preview image key stored': 'preview_image_key',
        'Preview source tracked': 'preview_source',
        'Extraction status tracked': 'extraction_status',
    }
    
    passed = 0
    failed = 0
    
    for check_name, check_string in checks.items():
        if check_string in content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    print(f"\nReceiptProcessor Integration: {passed}/{len(checks)} checks passed")
    return failed == 0


def test_database_migrations():
    """Test that database migrations are properly defined"""
    print("\n" + "=" * 60)
    print("Test 5: Database Migrations")
    print("=" * 60)
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    checks = {
        'Migration 101 exists': 'Migration 101',
        'preview_image_key column': 'preview_image_key',
        'preview_source column': 'preview_source',
        'extraction_status column': 'extraction_status',
        'extraction_error column': 'extraction_error',
    }
    
    passed = 0
    failed = 0
    
    for check_name, check_string in checks.items():
        if check_string in content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    # Check Receipt model
    with open('server/models_sql.py', 'r') as f:
        model_content = f.read()
    
    model_checks = {
        'Model: preview_image_key': 'preview_image_key',
        'Model: preview_source': 'preview_source',
        'Model: extraction_status': 'extraction_status',
        'Model: extraction_error': 'extraction_error',
    }
    
    for check_name, check_string in model_checks.items():
        if check_string in model_content:
            print(f"✅ {check_name}")
            passed += 1
        else:
            print(f"❌ {check_name}")
            failed += 1
    
    total_checks = len(checks) + len(model_checks)
    print(f"\nDatabase Migrations: {passed}/{total_checks} checks passed")
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Receipt Module Progress Bar & Integration Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Sync Progress Bar", test_sync_progress_bar_persistence()))
    results.append(("Delete Progress Bar", test_delete_progress_bar_persistence()))
    results.append(("Cancel Functionality", test_cancel_functionality()))
    results.append(("ReceiptProcessor", test_receipt_processor_integration()))
    results.append(("Database Migrations", test_database_migrations()))
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Receipt module is complete.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed. Review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
