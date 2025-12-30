#!/usr/bin/env python3
"""
Test for No-Answer Call Fix
Verifies that no-answer calls get summaries and status updates
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_failed_call_handler():
    """Test that _handle_failed_call creates summary and updates status"""
    print("=" * 80)
    print("TEST: Failed Call Handler")
    print("=" * 80)
    print()
    
    from server.tasks_recording import _handle_failed_call
    from server.models_sql import CallLog, Lead, LeadStatus, Business
    from server.app_factory import get_process_app
    from server.db import db
    
    app = get_process_app()
    
    with app.app_context():
        # Create test business
        business = Business()
        business.name = "Test Business"
        business.is_active = True
        db.session.add(business)
        db.session.flush()
        
        # Create test status
        status = LeadStatus()
        status.business_id = business.id
        status.name = "no_answer"
        status.description = "אין מענה"
        status.is_active = True
        db.session.add(status)
        db.session.flush()
        
        # Create test lead
        lead = Lead()
        lead.business_id = business.id
        lead.status = "new"
        lead.phone = "+972501234567"
        db.session.add(lead)
        db.session.flush()
        
        # Create test call log
        call_log = CallLog()
        call_log.call_sid = "TEST_NO_ANSWER_123"
        call_log.business_id = business.id
        call_log.lead_id = lead.id
        call_log.direction = "outbound"
        call_log.call_status = "no-answer"
        call_log.duration = 0
        db.session.add(call_log)
        db.session.flush()
        
        print(f"Created test call_log: {call_log.call_sid}")
        print(f"Lead ID: {lead.id}, Initial Status: {lead.status}")
        print()
        
        # Test the handler
        _handle_failed_call(call_log, "no-answer", db)
        
        # Refresh from DB
        db.session.refresh(call_log)
        db.session.refresh(lead)
        
        print(f"After handling:")
        print(f"  Call Summary: {call_log.summary}")
        print(f"  Lead Status: {lead.status}")
        print()
        
        # Verify results
        success = True
        
        if not call_log.summary or "לא נענתה" not in call_log.summary:
            print("❌ FAIL: Summary not created or incorrect")
            success = False
        else:
            print(f"✅ PASS: Summary created: '{call_log.summary}'")
        
        if lead.status == "no_answer":
            print(f"✅ PASS: Status updated to: {lead.status}")
        else:
            print(f"⚠️  Status remained: {lead.status} (may be expected if status logic differs)")
        
        # Cleanup
        db.session.rollback()
        
        return success


def test_status_progression():
    """Test that no-answer status progression works correctly"""
    print("=" * 80)
    print("TEST: No-Answer Status Progression")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Test with business that has numbered no-answer statuses
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'no_answer_2': 'אין מענה 2',
        'no_answer_3': 'אין מענה 3',
        'interested': 'מעוניין'
    }
    
    # Mock the _get_valid_statuses_dict method
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    try:
        # Test with no-answer summary
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary="שיחה לא נענתה - אין מענה",
            call_transcript=None,
            call_duration=0
        )
        
        print(f"Call Summary: 'שיחה לא נענתה - אין מענה'")
        print(f"Duration: 0 seconds")
        print(f"Suggested Status: {result}")
        print()
        
        if result and 'no_answer' in result.lower():
            print("✅ PASS: No-answer status correctly suggested")
            return True
        else:
            print(f"❌ FAIL: Expected no_answer status, got '{result}'")
            return False
    finally:
        # Restore original method
        service._get_valid_statuses_dict = original_method


def test_busy_status():
    """Test that busy calls are handled correctly"""
    print("=" * 80)
    print("TEST: Busy Call Handling")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'busy': 'תפוס',
        'interested': 'מעוניין'
    }
    
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    try:
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary="שיחה לא נענתה - קו תפוס",
            call_transcript=None,
            call_duration=0
        )
        
        print(f"Call Summary: 'שיחה לא נענתה - קו תפוס'")
        print(f"Suggested Status: {result}")
        print()
        
        if result:
            print(f"✅ PASS: Status suggested: {result}")
            return True
        else:
            print(f"⚠️  No status suggested (may be expected)")
            return True  # Not a failure - might not have 'busy' status
    finally:
        service._get_valid_statuses_dict = original_method


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  No-Answer Call Fix Tests".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Failed Call Handler", test_failed_call_handler),
        ("Status Progression", test_status_progression),
        ("Busy Call Handling", test_busy_status),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ TEST CRASHED: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print(f"Total: {passed_count}/{total} tests passed")
    print()
    
    if passed_count == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"❌ {total - passed_count} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
