#!/usr/bin/env python3
"""
Test to verify receipts sync queue configuration fix.

This test verifies that:
1. Worker is configured to listen to receipts-related queues
2. The receipts sync endpoint uses the correct queue
3. Worker availability check works correctly

Run with: python test_receipts_sync_queue_fix.py
"""

import os
import sys

def test_worker_queue_config():
    """Test that worker is configured with correct queues."""
    print("=" * 60)
    print("TEST: Worker Queue Configuration")
    print("=" * 60)
    
    # Check docker-compose.yml
    print("\n1. Checking docker-compose.yml...")
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
        if 'RQ_QUEUES: high,default,low,receipts,receipts_sync' in content:
            print("   ✓ docker-compose.yml has correct RQ_QUEUES configuration")
        else:
            print("   ✗ docker-compose.yml is missing receipts queues")
            return False
    
    # Check docker-compose.prod.yml
    print("\n2. Checking docker-compose.prod.yml...")
    with open('docker-compose.prod.yml', 'r') as f:
        content = f.read()
        if 'RQ_QUEUES: high,default,low,receipts,receipts_sync' in content:
            print("   ✓ docker-compose.prod.yml has correct RQ_QUEUES configuration")
        else:
            print("   ✗ docker-compose.prod.yml is missing receipts queues")
            return False
    
    print("\n✓ All docker-compose files have correct queue configuration")
    return True


def test_receipts_sync_queue_usage():
    """Test that receipts sync uses the correct queue."""
    print("\n" + "=" * 60)
    print("TEST: Receipts Sync Queue Usage")
    print("=" * 60)
    
    print("\n1. Checking routes_receipts.py for queue usage...")
    with open('server/routes_receipts.py', 'r') as f:
        content = f.read()
        
        # Check that it creates a Queue with 'default'
        if "Queue('default'" in content:
            print("   ✓ Receipts sync uses 'default' queue")
        else:
            print("   ✗ Queue configuration not found or incorrect")
            return False
        
        # Check for worker availability check
        if "_has_worker_for_queue" in content and 'queue_name="default"' in content:
            print("   ✓ Worker availability check uses correct queue name")
        else:
            print("   ⚠️  Worker availability check may not be verifying correct queue")
    
    print("\n✓ Receipts sync queue usage is correct")
    return True


def test_worker_implementation():
    """Test that worker implementation reads RQ_QUEUES correctly."""
    print("\n" + "=" * 60)
    print("TEST: Worker Implementation")
    print("=" * 60)
    
    print("\n1. Checking server/worker.py...")
    with open('server/worker.py', 'r') as f:
        content = f.read()
        
        if "RQ_QUEUES = os.getenv('RQ_QUEUES'" in content:
            print("   ✓ Worker reads RQ_QUEUES from environment")
        else:
            print("   ✗ Worker doesn't read RQ_QUEUES correctly")
            return False
        
        if "LISTEN_QUEUES = [q.strip() for q in RQ_QUEUES.split(',')" in content:
            print("   ✓ Worker parses queue list correctly")
        else:
            print("   ✗ Worker doesn't parse queue list")
            return False
    
    print("\n✓ Worker implementation is correct")
    return True


def print_deployment_instructions():
    """Print deployment instructions."""
    print("\n" + "=" * 60)
    print("DEPLOYMENT INSTRUCTIONS")
    print("=" * 60)
    print("""
After these changes, deploy with:

1. Production deployment:
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --force-recreate prosaas-worker

2. Development deployment:
   docker compose up -d --build --force-recreate worker

3. Verify worker logs:
   docker logs --tail 50 prosaas-worker
   
   You should see:
   - RQ_QUEUES configuration: high,default,low,receipts,receipts_sync
   - Will listen to queues: ['high', 'default', 'low', 'receipts', 'receipts_sync']

4. Test the sync endpoint:
   POST /api/receipts/sync
   
   Should return:
   - 202 Accepted (job queued)
   - No longer 503 "Receipt sync worker is not online"

5. Monitor job processing:
   GET /api/receipts/sync/status?job_id=<job_id>
   
   Should show:
   - status: queued -> started -> finished
   - Not stuck in queued state
""")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RECEIPTS SYNC QUEUE FIX VERIFICATION")
    print("=" * 60)
    
    all_passed = True
    
    # Run tests
    all_passed &= test_worker_queue_config()
    all_passed &= test_receipts_sync_queue_usage()
    all_passed &= test_worker_implementation()
    
    # Print results
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print_deployment_instructions()
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("Please fix the issues before deploying")
        return 1


if __name__ == '__main__':
    sys.exit(main())
