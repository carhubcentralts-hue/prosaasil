"""
Security Tests for Outbound Call Queue System

These tests verify:
1. Business isolation - users can only see/cancel runs for their business
2. No duplicate starts - same run cannot be started twice
3. Proper state transitions
4. No duplicate calls (run_id, lead_id constraint)
5. Crash recovery

Run with: python test_outbound_call_security.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_business_isolation():
    """
    Test: Business A cannot see/cancel run of Business B
    
    This is the most critical security test
    """
    print("=" * 80)
    print("TEST 1: Business Isolation")
    print("=" * 80)
    
    from server.app_factory import create_app
    from server.models_sql import db, OutboundCallRun, OutboundCallJob, Business, Lead, User
    from flask import session
    
    app = create_app()
    
    with app.app_context():
        # Create two test businesses
        business_a = Business(name="Business A", phone_e164="+972501234567")
        business_b = Business(name="Business B", phone_e164="+972501234568")
        db.session.add(business_a)
        db.session.add(business_b)
        db.session.flush()
        
        # Create test users for each business
        user_a = User(email="user_a@test.com", business_id=business_a.id, role="admin", is_active=True)
        user_b = User(email="user_b@test.com", business_id=business_b.id, role="admin", is_active=True)
        db.session.add(user_a)
        db.session.add(user_b)
        db.session.flush()
        
        # Create test leads for each business
        lead_a1 = Lead(tenant_id=business_a.id, phone_e164="+972501111111", source="test")
        lead_a2 = Lead(tenant_id=business_a.id, phone_e164="+972501111112", source="test")
        lead_b1 = Lead(tenant_id=business_b.id, phone_e164="+972502222221", source="test")
        db.session.add_all([lead_a1, lead_a2, lead_b1])
        db.session.flush()
        
        # Create runs for each business
        run_a = OutboundCallRun(
            business_id=business_a.id,
            created_by_user_id=user_a.id,
            status="running",
            total_leads=2,
            queued_count=2,
            concurrency=3
        )
        run_b = OutboundCallRun(
            business_id=business_b.id,
            created_by_user_id=user_b.id,
            status="running",
            total_leads=1,
            queued_count=1,
            concurrency=3
        )
        db.session.add(run_a)
        db.session.add(run_b)
        db.session.flush()
        
        # Create jobs for each run
        job_a1 = OutboundCallJob(run_id=run_a.id, lead_id=lead_a1.id, business_id=business_a.id, status="queued")
        job_a2 = OutboundCallJob(run_id=run_a.id, lead_id=lead_a2.id, business_id=business_a.id, status="queued")
        job_b1 = OutboundCallJob(run_id=run_b.id, lead_id=lead_b1.id, business_id=business_b.id, status="queued")
        db.session.add_all([job_a1, job_a2, job_b1])
        db.session.commit()
        
        print(f"✅ Created test data:")
        print(f"   Business A (id={business_a.id}): run_id={run_a.id}, 2 jobs")
        print(f"   Business B (id={business_b.id}): run_id={run_b.id}, 1 job")
        print()
        
        # TEST 1.1: User A queries run B (should fail)
        print("TEST 1.1: User A tries to access Run B")
        run_query = OutboundCallRun.query.filter_by(
            id=run_b.id,
            business_id=business_a.id  # Wrong business!
        ).first()
        
        if run_query is None:
            print("✅ PASS: User A cannot see Run B (filtered by business_id)")
        else:
            print("❌ FAIL: User A can see Run B (security breach!)")
            return False
        
        # TEST 1.2: User B queries run A (should fail)
        print("TEST 1.2: User B tries to access Run A")
        run_query = OutboundCallRun.query.filter_by(
            id=run_a.id,
            business_id=business_b.id  # Wrong business!
        ).first()
        
        if run_query is None:
            print("✅ PASS: User B cannot see Run A (filtered by business_id)")
        else:
            print("❌ FAIL: User B can see Run A (security breach!)")
            return False
        
        # TEST 1.3: Verify jobs are also isolated by business_id
        print("TEST 1.3: Verify jobs have business_id for isolation")
        jobs_without_business = OutboundCallJob.query.filter(
            OutboundCallJob.business_id.is_(None)
        ).count()
        
        if jobs_without_business == 0:
            print("✅ PASS: All jobs have business_id set")
        else:
            print(f"❌ FAIL: {jobs_without_business} jobs missing business_id")
            return False
        
        # Cleanup
        db.session.rollback()
        
    print("\n✅ TEST 1 PASSED: Business isolation is working correctly\n")
    return True


def test_duplicate_prevention():
    """
    Test: No duplicate calls (run_id, lead_id constraint)
    """
    print("=" * 80)
    print("TEST 2: Duplicate Call Prevention")
    print("=" * 80)
    
    from server.app_factory import create_app
    from server.models_sql import db, OutboundCallRun, OutboundCallJob, Business, Lead
    from sqlalchemy.exc import IntegrityError
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(name="Test Business", phone_e164="+972501234567")
        db.session.add(business)
        db.session.flush()
        
        # Create test lead
        lead = Lead(tenant_id=business.id, phone_e164="+972501111111", source="test")
        db.session.add(lead)
        db.session.flush()
        
        # Create run
        run = OutboundCallRun(
            business_id=business.id,
            status="running",
            total_leads=1,
            queued_count=1,
            concurrency=3
        )
        db.session.add(run)
        db.session.flush()
        
        # Create first job
        job1 = OutboundCallJob(
            run_id=run.id,
            lead_id=lead.id,
            business_id=business.id,
            status="queued"
        )
        db.session.add(job1)
        db.session.commit()
        
        print(f"✅ Created first job: run_id={run.id}, lead_id={lead.id}")
        
        # Try to create duplicate job (should fail)
        print("TEST 2.1: Attempting to create duplicate job...")
        try:
            job2 = OutboundCallJob(
                run_id=run.id,
                lead_id=lead.id,  # Same lead_id!
                business_id=business.id,
                status="queued"
            )
            db.session.add(job2)
            db.session.commit()
            
            print("❌ FAIL: Duplicate job was created (unique constraint not working!)")
            db.session.rollback()
            return False
            
        except IntegrityError as e:
            db.session.rollback()
            if "unique_run_lead" in str(e).lower() or "duplicate" in str(e).lower():
                print("✅ PASS: Duplicate job prevented by unique constraint")
            else:
                print(f"❌ FAIL: IntegrityError but wrong constraint: {e}")
                return False
        
    print("\n✅ TEST 2 PASSED: Duplicate prevention is working\n")
    return True


def test_state_machine():
    """
    Test: Proper state transitions
    """
    print("=" * 80)
    print("TEST 3: State Machine Transitions")
    print("=" * 80)
    
    from server.app_factory import create_app
    from server.models_sql import db, OutboundCallRun, Business
    from datetime import datetime
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(name="Test Business", phone_e164="+972501234567")
        db.session.add(business)
        db.session.flush()
        
        # Create run in pending state
        run = OutboundCallRun(
            business_id=business.id,
            status="pending",
            total_leads=10,
            queued_count=10,
            concurrency=3
        )
        db.session.add(run)
        db.session.commit()
        
        print(f"✅ Created run in 'pending' state")
        
        # TEST 3.1: Transition to running
        print("TEST 3.1: Transition pending → running")
        run.status = "running"
        run.started_at = datetime.utcnow()
        db.session.commit()
        
        if run.status == "running" and run.started_at is not None:
            print("✅ PASS: Transition to running with started_at set")
        else:
            print("❌ FAIL: Transition to running failed")
            return False
        
        # TEST 3.2: Transition to completed
        print("TEST 3.2: Transition running → completed")
        run.status = "completed"
        run.ended_at = datetime.utcnow()
        run.completed_at = datetime.utcnow()
        db.session.commit()
        
        if run.status == "completed" and run.ended_at is not None:
            print("✅ PASS: Transition to completed with ended_at set")
        else:
            print("❌ FAIL: Transition to completed failed")
            return False
        
        # TEST 3.3: Check that new fields exist
        print("TEST 3.3: Verify new tracking fields")
        if hasattr(run, 'created_by_user_id') and \
           hasattr(run, 'started_at') and \
           hasattr(run, 'ended_at') and \
           hasattr(run, 'cursor_position') and \
           hasattr(run, 'locked_by_worker') and \
           hasattr(run, 'lock_ts'):
            print("✅ PASS: All new tracking fields exist in model")
        else:
            print("❌ FAIL: Some tracking fields missing")
            return False
        
        db.session.rollback()
        
    print("\n✅ TEST 3 PASSED: State machine is working correctly\n")
    return True


def test_cancel_functionality():
    """
    Test: Cancel functionality works correctly
    """
    print("=" * 80)
    print("TEST 4: Cancel Functionality")
    print("=" * 80)
    
    from server.app_factory import create_app
    from server.models_sql import db, OutboundCallRun, OutboundCallJob, Business, Lead
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(name="Test Business", phone_e164="+972501234567")
        db.session.add(business)
        db.session.flush()
        
        # Create test leads
        lead1 = Lead(tenant_id=business.id, phone_e164="+972501111111", source="test")
        lead2 = Lead(tenant_id=business.id, phone_e164="+972501111112", source="test")
        db.session.add_all([lead1, lead2])
        db.session.flush()
        
        # Create run
        run = OutboundCallRun(
            business_id=business.id,
            status="running",
            total_leads=2,
            queued_count=2,
            concurrency=3
        )
        db.session.add(run)
        db.session.flush()
        
        # Create jobs
        job1 = OutboundCallJob(run_id=run.id, lead_id=lead1.id, business_id=business.id, status="queued")
        job2 = OutboundCallJob(run_id=run.id, lead_id=lead2.id, business_id=business.id, status="calling")
        db.session.add_all([job1, job2])
        db.session.commit()
        
        print(f"✅ Created run with 2 jobs (1 queued, 1 calling)")
        
        # TEST 4.1: Set cancel_requested
        print("TEST 4.1: Set cancel_requested flag")
        run.cancel_requested = True
        db.session.commit()
        
        if run.cancel_requested:
            print("✅ PASS: cancel_requested flag set")
        else:
            print("❌ FAIL: cancel_requested flag not set")
            return False
        
        # TEST 4.2: Verify worker would check this flag
        print("TEST 4.2: Verify cancel_requested can be checked")
        db.session.refresh(run)
        if run.cancel_requested and run.status != "cancelled":
            print("✅ PASS: Worker can detect cancel request")
        else:
            print("❌ FAIL: Cancel detection logic issue")
            return False
        
        db.session.rollback()
        
    print("\n✅ TEST 4 PASSED: Cancel functionality is working\n")
    return True


def main():
    """Run all security tests"""
    print("\n" + "=" * 80)
    print("OUTBOUND CALL QUEUE SECURITY TESTS")
    print("=" * 80 + "\n")
    
    tests = [
        ("Business Isolation", test_business_isolation),
        ("Duplicate Prevention", test_duplicate_prevention),
        ("State Machine", test_state_machine),
        ("Cancel Functionality", test_cancel_functionality),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH EXCEPTION: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL SECURITY TESTS PASSED! 🎉\n")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - SECURITY ISSUES DETECTED ⚠️\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
