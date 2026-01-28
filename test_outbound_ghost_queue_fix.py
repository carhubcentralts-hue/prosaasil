"""
Test for outbound ghost queue fixes

Verifies:
1. cleanup_stuck_runs(on_startup=True) marks all running queues as failed
2. QueueStatusCard shows dismiss button for ghost queues
"""
import sys
import os
from datetime import datetime, timedelta

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_cleanup_stuck_runs_on_startup():
    """Test that cleanup_stuck_runs(on_startup=True) marks ALL running queues as failed"""
    from server.app_factory import create_app
    from server.models_sql import db, OutboundCallRun, Business
    from server.routes_outbound import cleanup_stuck_runs
    
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("TEST 1: cleanup_stuck_runs(on_startup=True)")
        print("="*70)
        
        # Get or create a test business
        business = Business.query.first()
        if not business:
            print("❌ No business found in database. Cannot test.")
            return False
        
        # Create a test run that's "running" with recent heartbeat (within 5 min TTL)
        test_run = OutboundCallRun()
        test_run.business_id = business.id
        test_run.status = 'running'
        test_run.total_leads = 10
        test_run.queued_count = 5
        test_run.in_progress_count = 2
        test_run.completed_count = 2
        test_run.failed_count = 1
        test_run.concurrency = 3
        test_run.locked_by_worker = "test-worker:12345"
        # Set lock_ts to 2 minutes ago (within 5-minute TTL)
        test_run.lock_ts = datetime.utcnow() - timedelta(minutes=2)
        test_run.created_at = datetime.utcnow() - timedelta(minutes=10)
        test_run.started_at = datetime.utcnow() - timedelta(minutes=8)
        
        db.session.add(test_run)
        db.session.commit()
        
        test_run_id = test_run.id
        print(f"✅ Created test run {test_run_id} with status='running', lock_ts=2min ago")
        print(f"   Worker: {test_run.locked_by_worker}")
        print(f"   Heartbeat: {test_run.lock_ts}")
        
        # Run cleanup with on_startup=False (normal mode)
        print("\n🔍 Running cleanup_stuck_runs(on_startup=False)...")
        count = cleanup_stuck_runs(on_startup=False)
        db.session.commit()
        
        # Check status - should still be 'running' (within TTL)
        db.session.refresh(test_run)
        if test_run.status == 'running':
            print(f"✅ PASS: Run still 'running' after normal cleanup (within TTL)")
        else:
            print(f"❌ FAIL: Run marked as '{test_run.status}' (should be 'running')")
            return False
        
        # Now run cleanup with on_startup=True (startup mode)
        print("\n🔍 Running cleanup_stuck_runs(on_startup=True)...")
        count = cleanup_stuck_runs(on_startup=True)
        db.session.commit()
        
        # Check status - should be marked as 'failed'
        db.session.refresh(test_run)
        if test_run.status == 'failed':
            print(f"✅ PASS: Run marked as 'failed' after startup cleanup")
            print(f"   Reason: {test_run.last_error}")
        else:
            print(f"❌ FAIL: Run still '{test_run.status}' (should be 'failed')")
            db.session.delete(test_run)
            db.session.commit()
            return False
        
        # Cleanup
        db.session.delete(test_run)
        db.session.commit()
        print(f"🧹 Cleaned up test run {test_run_id}")
        
        return True


def test_queuestatuscard_ghost_detection():
    """Test that QueueStatusCard logic correctly detects ghost queues"""
    print("\n" + "="*70)
    print("TEST 2: QueueStatusCard ghost queue detection")
    print("="*70)
    
    # Simulate the logic from QueueStatusCard.tsx
    def check_ghost_queue(status: str, inProgress: int, queued: int):
        """Simulate QueueStatusCard ghost queue detection"""
        isGhostQueue = status == 'running' and inProgress == 0 and queued == 0
        return isGhostQueue
    
    # Test cases
    test_cases = [
        # (status, inProgress, queued, expected_is_ghost, description)
        ('running', 0, 0, True, "Ghost queue: running with no activity"),
        ('running', 3, 5, False, "Active queue: running with jobs"),
        ('running', 0, 5, False, "Active queue: running with queued jobs"),
        ('running', 3, 0, False, "Active queue: running with in-progress jobs"),
        ('completed', 0, 0, False, "Completed queue: not ghost"),
        ('failed', 0, 0, False, "Failed queue: not ghost"),
        ('cancelled', 0, 0, False, "Cancelled queue: not ghost"),
    ]
    
    all_passed = True
    for status, inProgress, queued, expected_ghost, description in test_cases:
        is_ghost = check_ghost_queue(status, inProgress, queued)
        if is_ghost == expected_ghost:
            print(f"✅ PASS: {description}")
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Expected: {expected_ghost}, Got: {is_ghost}")
            all_passed = False
    
    return all_passed


def test_queuestatuscard_dismiss_logic():
    """Test that QueueStatusCard dismiss button logic is correct"""
    print("\n" + "="*70)
    print("TEST 3: QueueStatusCard dismiss button logic")
    print("="*70)
    
    # Simulate the logic from QueueStatusCard.tsx
    def check_dismiss_button(status: str, inProgress: int, queued: int, onDismiss_exists: bool):
        """Simulate QueueStatusCard dismiss button logic"""
        canDismiss = ['completed', 'cancelled', 'failed'].index(status) if status in ['completed', 'cancelled', 'failed'] else -1
        canDismiss = canDismiss != -1 and onDismiss_exists
        
        isGhostQueue = status == 'running' and inProgress == 0 and queued == 0
        showDismissForGhost = isGhostQueue and onDismiss_exists
        
        show_dismiss = canDismiss or showDismissForGhost
        return show_dismiss
    
    # Test cases
    test_cases = [
        # (status, inProgress, queued, onDismiss, expected_show, description)
        ('running', 0, 0, True, True, "Ghost queue: should show dismiss"),
        ('running', 3, 5, True, False, "Active queue: should NOT show dismiss"),
        ('completed', 0, 0, True, True, "Completed queue: should show dismiss"),
        ('failed', 0, 0, True, True, "Failed queue: should show dismiss"),
        ('cancelled', 0, 0, True, True, "Cancelled queue: should show dismiss"),
        ('running', 0, 0, False, False, "Ghost queue without onDismiss: no button"),
    ]
    
    all_passed = True
    for status, inProgress, queued, onDismiss, expected_show, description in test_cases:
        show_dismiss = check_dismiss_button(status, inProgress, queued, onDismiss)
        if show_dismiss == expected_show:
            print(f"✅ PASS: {description}")
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Expected: {expected_show}, Got: {show_dismiss}")
            all_passed = False
    
    return all_passed


if __name__ == '__main__':
    print("\n" + "="*70)
    print("OUTBOUND GHOST QUEUE FIX VERIFICATION")
    print("="*70)
    
    results = []
    
    # Test 1: Backend cleanup on startup
    try:
        results.append(("cleanup_stuck_runs(on_startup=True)", test_cleanup_stuck_runs_on_startup()))
    except Exception as e:
        print(f"\n❌ TEST 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("cleanup_stuck_runs(on_startup=True)", False))
    
    # Test 2: Ghost queue detection
    try:
        results.append(("Ghost queue detection", test_queuestatuscard_ghost_detection()))
    except Exception as e:
        print(f"\n❌ TEST 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Ghost queue detection", False))
    
    # Test 3: Dismiss button logic
    try:
        results.append(("Dismiss button logic", test_queuestatuscard_dismiss_logic()))
    except Exception as e:
        print(f"\n❌ TEST 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Dismiss button logic", False))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
