#!/usr/bin/env python3
"""
Test for Worker Availability Check
Verifies that the worker availability check function works correctly
"""

import sys
import os

def test_worker_check_function_exists():
    """
    Test that the _has_active_workers function exists in routes_receipts.py
    """
    print("=" * 80)
    print("TEST: Worker availability check function exists")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for function definition
        if 'def _has_active_workers' in content:
            print("✅ PASS: _has_active_workers function found in routes_receipts.py")
            
            # Check it uses Worker.all()
            if 'Worker.all(connection=' in content:
                print("✅ PASS: Function uses Worker.all() to check for active workers")
            else:
                print("❌ FAIL: Function doesn't use Worker.all() properly")
                return False
                
            # Check it returns boolean
            if 'return len(workers) > 0' in content:
                print("✅ PASS: Function returns boolean based on worker count")
            else:
                print("❌ FAIL: Function doesn't return proper boolean")
                return False
                
            return True
        else:
            print("❌ FAIL: _has_active_workers function not found")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        return False


def test_worker_check_in_sync_endpoint():
    """
    Test that the worker check is called in sync_receipts endpoint
    """
    print("\n" + "=" * 80)
    print("TEST: Worker check is called before enqueuing jobs")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find the sync_receipts function
        in_function = False
        found_worker_check = False
        found_503_response = False
        worker_check_line = 0
        
        for i, line in enumerate(lines, start=1):
            if 'def sync_receipts():' in line:
                in_function = True
                print(f"✅ Found sync_receipts function at line {i}")
                continue
            
            if in_function:
                # Look for next function definition to know when to stop
                if line.startswith('def ') and 'sync_receipts' not in line and not line.startswith('    def '):
                    break
                
                # Check for worker availability check
                if '_has_active_workers' in line:
                    found_worker_check = True
                    worker_check_line = i
                    print(f"✅ PASS: Worker availability check found at line {i}")
                
                # Check for 503 error response when no workers
                if found_worker_check and ', 503' in line:
                    # Look for "Worker not running" in nearby lines
                    nearby_lines = ''.join(lines[max(0, i-10):min(len(lines), i+5)])
                    if 'Worker not running' in nearby_lines:
                        found_503_response = True
                        print(f"✅ PASS: 503 error response found when no workers detected")
        
        if not found_worker_check:
            print("❌ FAIL: Worker availability check not found in sync_receipts")
            return False
        
        if not found_503_response:
            print("❌ FAIL: 503 error response not found for missing workers")
            return False
        
        return True
            
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        return False


def test_rq_job_status_endpoint():
    """
    Test that the sync status endpoint supports job_id parameter
    """
    print("\n" + "=" * 80)
    print("TEST: Sync status endpoint supports RQ job_id parameter")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for job_id parameter handling
        if "job_id = request.args.get('job_id'" in content:
            print("✅ PASS: job_id parameter extraction found")
            
            # Check for RQ Job.fetch
            if 'Job.fetch(job_id, connection=redis_conn)' in content:
                print("✅ PASS: RQ Job.fetch() used to get job status")
            else:
                print("❌ FAIL: Job.fetch() not found for job status")
                return False
                
            # Check for job status return
            if 'job.get_status()' in content:
                print("✅ PASS: Job status retrieval found")
            else:
                print("❌ FAIL: Job status not retrieved properly")
                return False
                
            return True
        else:
            print("❌ FAIL: job_id parameter handling not found")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        return False


def test_date_range_handling():
    """
    Test that date range handling uses months_back when only to_date is specified
    """
    print("\n" + "=" * 80)
    print("TEST: Date range uses months_back parameter properly")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for months_back usage when only to_date
        if 'months_to_go_back = months_back if months_back else 12' in content:
            print("✅ PASS: months_back parameter properly used when only to_date specified")
            
            # Check for relativedelta with months_to_go_back
            if 'relativedelta(months=months_to_go_back)' in content:
                print("✅ PASS: relativedelta uses months_to_go_back variable")
            else:
                print("❌ FAIL: relativedelta doesn't use months_to_go_back")
                return False
                
            return True
        else:
            print("❌ FAIL: months_back parameter not properly used")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        return False


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("WORKER AVAILABILITY CHECK - TEST SUITE")
    print("=" * 80 + "\n")
    
    all_passed = True
    
    # Run tests
    all_passed = test_worker_check_function_exists() and all_passed
    all_passed = test_worker_check_in_sync_endpoint() and all_passed
    all_passed = test_rq_job_status_endpoint() and all_passed
    all_passed = test_date_range_handling() and all_passed
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        sys.exit(1)
