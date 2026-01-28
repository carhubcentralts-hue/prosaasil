#!/usr/bin/env python3
"""
Test: Outbound Single Consumer Fix
Validates that:
1. Thread-based consumer is removed
2. Only RQ worker processes outbound calls
3. DB locking is in place
4. Reconcile endpoint exists
"""
import re


def test_no_thread_consumer():
    """Verify thread-based consumer is removed from _start_bulk_queue"""
    with open('server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    # Check that _start_bulk_queue doesn't start a thread
    start_bulk_queue_match = re.search(
        r'def _start_bulk_queue\(.*?\n(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    
    if not start_bulk_queue_match:
        print("❌ Could not find _start_bulk_queue function")
        return False
    
    func_body = start_bulk_queue_match.group(1)
    
    # Should NOT contain Thread(target=process_bulk_call_run
    if 'Thread(target=process_bulk_call_run' in func_body:
        print("❌ FAIL: Thread-based consumer still present in _start_bulk_queue")
        return False
    
    # Should contain enqueue to RQ
    if 'queue.enqueue' not in func_body or 'enqueue_outbound_calls_batch_job' not in func_body:
        print("❌ FAIL: RQ enqueue not found in _start_bulk_queue")
        return False
    
    print("✅ PASS: Thread-based consumer removed, RQ worker enqueue present")
    return True


def test_db_locking_present():
    """Verify SELECT FOR UPDATE SKIP LOCKED is used"""
    with open('server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    if 'FOR UPDATE SKIP LOCKED' not in content:
        print("❌ FAIL: SELECT FOR UPDATE SKIP LOCKED not found")
        return False
    
    print("✅ PASS: DB locking with FOR UPDATE SKIP LOCKED present")
    return True


def test_reconcile_endpoint_exists():
    """Verify reconcile endpoint is added"""
    with open('server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    if '/api/outbound/runs/reconcile' not in content:
        print("❌ FAIL: Reconcile endpoint not found")
        return False
    
    if 'def reconcile_stuck_runs' not in content:
        print("❌ FAIL: reconcile_stuck_runs function not found")
        return False
    
    print("✅ PASS: Reconcile endpoint present")
    return True


def test_enhanced_logging():
    """Verify enhanced logging for debugging duplicates"""
    with open('server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    required_logs = [
        'WORKER_ID',
        'consumer_source',
        'lock_acquired',
        'dedup_conflict'
    ]
    
    for log_item in required_logs:
        if log_item not in content:
            print(f"❌ FAIL: Enhanced logging missing: {log_item}")
            return False
    
    print("✅ PASS: Enhanced logging for debugging present")
    return True


def test_unique_constraint_documented():
    """Verify UNIQUE constraint is documented"""
    with open('server/models_sql.py', 'r') as f:
        content = f.read()
    
    # Check OutboundCallJob has unique constraint
    if "UniqueConstraint('run_id', 'lead_id'" not in content:
        print("❌ FAIL: UNIQUE constraint on (run_id, lead_id) not found")
        return False
    
    print("✅ PASS: UNIQUE constraint on (run_id, lead_id) present")
    return True


def main():
    print("=" * 70)
    print("Testing Outbound Single Consumer Fix")
    print("=" * 70)
    print()
    
    tests = [
        ("No Thread Consumer", test_no_thread_consumer),
        ("DB Locking Present", test_db_locking_present),
        ("Reconcile Endpoint", test_reconcile_endpoint_exists),
        ("Enhanced Logging", test_enhanced_logging),
        ("Unique Constraint", test_unique_constraint_documented),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        result = test_func()
        results.append((test_name, result))
        print()
    
    print("=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 70)
    
    return passed == total


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
