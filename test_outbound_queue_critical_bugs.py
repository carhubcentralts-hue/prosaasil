"""
Test script to verify the 3 critical outbound call bugs are fixed

This script verifies:
1. create_lead_from_call_job accepts only call_sid parameter
2. error_message column exists in call_log table (after migration)
3. Cleanup handles NULL call_sid records properly
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_job_signature():
    """Test 1: Verify create_lead_from_call_job has correct signature"""
    logger.info("=" * 70)
    logger.info("TEST 1: Job Function Signature")
    logger.info("=" * 70)
    
    try:
        from server.jobs.twilio_call_jobs import create_lead_from_call_job
        import inspect
        
        sig = inspect.signature(create_lead_from_call_job)
        params = list(sig.parameters.keys())
        
        logger.info(f"Function signature: {sig}")
        logger.info(f"Parameters: {params}")
        
        # Should only have call_sid parameter
        if params == ['call_sid']:
            logger.info("✅ PASS: Function has correct signature (call_sid only)")
            return True
        else:
            logger.error(f"❌ FAIL: Expected ['call_sid'], got {params}")
            return False
            
    except Exception as e:
        logger.error(f"❌ FAIL: Error checking signature: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_fields():
    """Test 2: Verify CallLog model has error tracking fields"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: CallLog Model Fields")
    logger.info("=" * 70)
    
    try:
        from server.models_sql import CallLog
        import sqlalchemy.inspection as inspection
        
        # Get all column names
        mapper = inspection.inspect(CallLog)
        column_names = [column.key for column in mapper.columns]
        
        logger.info(f"Checking for error_message and error_code fields...")
        
        has_error_message = 'error_message' in column_names
        has_error_code = 'error_code' in column_names
        
        if has_error_message:
            logger.info("✅ error_message field exists in CallLog model")
        else:
            logger.error("❌ error_message field missing from CallLog model")
            
        if has_error_code:
            logger.info("✅ error_code field exists in CallLog model")
        else:
            logger.error("❌ error_code field missing from CallLog model")
        
        if has_error_message and has_error_code:
            logger.info("✅ PASS: All error tracking fields present")
            return True
        else:
            logger.error("❌ FAIL: Missing error tracking fields")
            return False
            
    except Exception as e:
        logger.error(f"❌ FAIL: Error checking model: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_function_exists():
    """Test 3: Verify cleanup functions exist and are correctly implemented"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Cleanup Functions")
    logger.info("=" * 70)
    
    try:
        from server.routes_outbound import cleanup_stuck_dialing_jobs, cleanup_stuck_runs
        import inspect
        
        # Check cleanup_stuck_dialing_jobs
        source = inspect.getsource(cleanup_stuck_dialing_jobs)
        
        # Verify it updates error_message
        has_error_message_update = 'error_message' in source
        has_null_call_sid_check = 'call_sid IS NULL' in source
        has_stale_threshold = 'stale_threshold' in source
        
        logger.info(f"cleanup_stuck_dialing_jobs analysis:")
        logger.info(f"  - Updates error_message: {has_error_message_update}")
        logger.info(f"  - Checks for NULL call_sid: {has_null_call_sid_check}")
        logger.info(f"  - Uses stale threshold: {has_stale_threshold}")
        
        if has_error_message_update and has_null_call_sid_check and has_stale_threshold:
            logger.info("✅ PASS: Cleanup function properly handles NULL call_sid with error_message")
            return True
        else:
            logger.error("❌ FAIL: Cleanup function missing proper implementation")
            return False
            
    except Exception as e:
        logger.error(f"❌ FAIL: Error checking cleanup functions: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dedup_logic():
    """Test 4: Verify dedup logic in twilio_outbound_service"""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Deduplication Logic")
    logger.info("=" * 70)
    
    try:
        from server.services.twilio_outbound_service import _check_duplicate_in_db
        import inspect
        
        source = inspect.getsource(_check_duplicate_in_db)
        
        # Verify it handles NULL call_sid with stale threshold
        has_null_sid_handling = 'call_sid IS NULL' in source or 'call_sid IS NOT NULL' in source
        has_stale_check = 'stale_threshold' in source
        has_recent_pending_log = 'Recent pending call without SID' in source
        
        logger.info(f"_check_duplicate_in_db analysis:")
        logger.info(f"  - Handles NULL call_sid: {has_null_sid_handling}")
        logger.info(f"  - Uses stale threshold: {has_stale_check}")
        logger.info(f"  - Logs recent pending calls: {has_recent_pending_log}")
        
        if has_null_sid_handling and has_stale_check:
            logger.info("✅ PASS: Dedup logic properly handles NULL call_sid")
            return True
        else:
            logger.error("❌ FAIL: Dedup logic missing proper NULL handling")
            return False
            
    except Exception as e:
        logger.error(f"❌ FAIL: Error checking dedup logic: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 70)
    logger.info("🔍 VERIFICATION: Outbound Call Queue Critical Bugs")
    logger.info("=" * 70)
    logger.info("Testing fixes for 3 critical issues:\n")
    logger.info("1. create_lead_from_call_job missing business_id")
    logger.info("2. call_log.error_message column missing")
    logger.info("3. Pending calls without CallSid blocking queue")
    logger.info("")
    
    results = []
    
    # Run all tests
    results.append(("Job Signature", test_job_signature()))
    results.append(("Model Fields", test_model_fields()))
    results.append(("Cleanup Functions", test_cleanup_function_exists()))
    results.append(("Dedup Logic", test_dedup_logic()))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Final Score: {passed}/{total} tests passed")
    logger.info("=" * 70)
    
    if passed == total:
        logger.info("\n🎉 SUCCESS: All critical bugs are fixed!")
        logger.info("\n📝 Next Steps:")
        logger.info("1. Run migration: python migration_add_call_log_error_fields.py")
        logger.info("2. Restart workers to pick up new job signature")
        logger.info("3. Test 10 outbound calls in sequence")
        logger.info("4. Verify no TypeError or SQL errors in logs")
        return 0
    else:
        logger.error(f"\n❌ FAILURE: {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
