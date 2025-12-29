"""
Test Recording Download Deduplication Fix

This script verifies that:
1. Recording download status tracking works correctly
2. Duplicate enqueues are prevented
3. Status API returns correct information
4. Exponential backoff works for failed downloads
"""
import sys
import time
import requests
from datetime import datetime, timezone

# Test configuration
BASE_URL = "http://localhost:5000"
TEST_CALL_SID = "CA_test_recording_dedup_" + str(int(time.time()))

def test_migration():
    """Test that migration adds required columns"""
    print("🧪 Test 1: Check migration adds columns...")
    
    try:
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from sqlalchemy import inspect
        
        app = get_process_app()
        with app.app_context():
            inspector = inspect(CallLog.__table__.bind)
            columns = [col['name'] for col in inspector.get_columns('call_log')]
            
            required_columns = [
                'recording_download_status',
                'recording_last_enqueue_at',
                'recording_fail_count',
                'recording_next_retry_at'
            ]
            
            missing = [col for col in required_columns if col not in columns]
            
            if missing:
                print(f"   ❌ FAIL: Missing columns: {missing}")
                print(f"   💡 Run: python migration_add_recording_download_status.py")
                return False
            
            print(f"   ✅ PASS: All required columns exist")
            return True
            
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def test_deduplication():
    """Test that duplicate enqueues are prevented"""
    print("\n🧪 Test 2: Check deduplication prevents spam...")
    
    try:
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.db import db
        from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE
        
        app = get_process_app()
        with app.app_context():
            # Create a test call
            call = CallLog()
            call.call_sid = TEST_CALL_SID
            call.business_id = 1
            call.recording_url = "https://api.twilio.com/test/recording"
            call.from_number = "+972501234567"
            call.status = "completed"
            db.session.add(call)
            db.session.commit()
            
            # Get initial queue size
            initial_size = RECORDING_QUEUE.qsize()
            
            # Try to enqueue 5 times rapidly
            for i in range(5):
                enqueue_recording_download_only(
                    call_sid=TEST_CALL_SID,
                    recording_url=call.recording_url,
                    business_id=1,
                    from_number=call.from_number,
                    to_number="+972507654321"
                )
            
            # Check that only 1 job was enqueued
            final_size = RECORDING_QUEUE.qsize()
            enqueued_count = final_size - initial_size
            
            if enqueued_count == 1:
                print(f"   ✅ PASS: Only 1 job enqueued (prevented {4} duplicates)")
            else:
                print(f"   ❌ FAIL: {enqueued_count} jobs enqueued (expected 1)")
                return False
            
            # Check that status was set to 'queued'
            call = CallLog.query.filter_by(call_sid=TEST_CALL_SID).first()
            if call.recording_download_status == 'queued':
                print(f"   ✅ PASS: Status set to 'queued'")
            else:
                print(f"   ❌ FAIL: Status is '{call.recording_download_status}' (expected 'queued')")
                return False
            
            # Cleanup
            db.session.delete(call)
            db.session.commit()
            
            return True
            
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_status_api():
    """Test the new status API endpoint"""
    print("\n🧪 Test 3: Test /status API endpoint...")
    
    try:
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.db import db
        from server.services.recording_service import _get_recordings_dir
        import os
        
        app = get_process_app()
        with app.app_context():
            # Create a test call with ready status
            call = CallLog()
            call.call_sid = TEST_CALL_SID + "_ready"
            call.business_id = 1
            call.recording_url = "https://api.twilio.com/test/recording"
            call.from_number = "+972501234567"
            call.status = "completed"
            call.recording_download_status = 'ready'
            db.session.add(call)
            db.session.commit()
            
            # Create a dummy file to simulate cached recording
            recordings_dir = _get_recordings_dir()
            os.makedirs(recordings_dir, exist_ok=True)
            test_file = os.path.join(recordings_dir, f"{call.call_sid}.mp3")
            with open(test_file, 'wb') as f:
                f.write(b'test audio data')
            
            # Test with Flask test client
            with app.test_client() as client:
                # Mock authentication (would normally require session)
                with client.session_transaction() as sess:
                    sess['business_id'] = 1
                    sess['user_id'] = 1
                    sess['role'] = 'owner'
                
                # Test status endpoint
                response = client.get(f'/api/recordings/{call.call_sid}/status')
                
                if response.status_code == 200:
                    data = response.get_json()
                    if data.get('status') == 'ready':
                        print(f"   ✅ PASS: Status API returns 'ready'")
                    else:
                        print(f"   ❌ FAIL: Status is '{data.get('status')}' (expected 'ready')")
                        return False
                else:
                    print(f"   ❌ FAIL: Status API returned {response.status_code}")
                    return False
            
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            db.session.delete(call)
            db.session.commit()
            
            return True
            
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exponential_backoff():
    """Test that exponential backoff works for failures"""
    print("\n🧪 Test 4: Test exponential backoff for failures...")
    
    try:
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.db import db
        from server.tasks_recording import _update_download_status
        from datetime import timedelta
        
        app = get_process_app()
        with app.app_context():
            # Create a test call
            call = CallLog()
            call.call_sid = TEST_CALL_SID + "_backoff"
            call.business_id = 1
            call.recording_url = "https://api.twilio.com/test/recording"
            call.from_number = "+972501234567"
            call.status = "completed"
            db.session.add(call)
            db.session.commit()
            
            # Simulate failed download with retry time
            next_retry = datetime.now(timezone.utc) + timedelta(seconds=30)
            _update_download_status(
                call_sid=call.call_sid,
                status='failed',
                fail_count=2,
                next_retry_at=next_retry
            )
            
            # Reload from DB
            call = CallLog.query.filter_by(call_sid=call.call_sid).first()
            
            if call.recording_download_status == 'failed':
                print(f"   ✅ PASS: Status set to 'failed'")
            else:
                print(f"   ❌ FAIL: Status is '{call.recording_download_status}' (expected 'failed')")
                return False
            
            if call.recording_fail_count == 2:
                print(f"   ✅ PASS: Fail count is 2")
            else:
                print(f"   ❌ FAIL: Fail count is {call.recording_fail_count} (expected 2)")
                return False
            
            if call.recording_next_retry_at:
                wait_seconds = (call.recording_next_retry_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds()
                if 25 < wait_seconds < 35:  # Should be ~30 seconds
                    print(f"   ✅ PASS: Next retry in {int(wait_seconds)}s")
                else:
                    print(f"   ❌ FAIL: Next retry in {int(wait_seconds)}s (expected ~30s)")
                    return False
            else:
                print(f"   ❌ FAIL: next_retry_at not set")
                return False
            
            # Cleanup
            db.session.delete(call)
            db.session.commit()
            
            return True
            
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Recording Download Deduplication Fix - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Migration", test_migration),
        ("Deduplication", test_deduplication),
        ("Status API", test_status_api),
        ("Exponential Backoff", test_exponential_backoff),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
