"""
Test recording enqueue fixes
Tests the critical fixes for:
1. RQ Retry parameter fix (int → Retry object)
2. Dedup flow fix (set only after successful enqueue)
3. API error handling (distinguish dedup from error)
4. Recording URL conversion (.json → .mp3)
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_retry_import():
    """Test 1: Verify Retry is imported from rq"""
    print("Test 1: Checking Retry import...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Check for Retry import
    assert 'from rq import Retry' in content, "❌ Retry not imported from rq"
    print("✅ Retry is imported from rq")
    
    # Check that Retry(max=...) is used instead of int
    assert 'retry=Retry(max=' in content, "❌ Retry(max=...) not used"
    assert 'retry=3  # RQ' not in content and 'retry=3,' not in content.replace('retry=Retry(max=3)', ''), \
        "❌ Still using retry=3 instead of Retry object"
    print("✅ Using Retry(max=N) instead of retry=N")

def test_dedup_flow():
    """Test 2: Verify dedup is set only after successful enqueue"""
    print("\nTest 2: Checking dedup flow...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find enqueue_recording_download_only function
    func_start = content.find('def enqueue_recording_download_only(')
    func_end = content.find('\ndef ', func_start + 10)
    func_body = content[func_start:func_end]
    
    # Check that we check for existing key with .get() before setting
    assert 'redis_conn.get(job_key)' in func_body, "❌ Not checking dedup key with .get()"
    print("✅ Checking dedup key with .get() before enqueue")
    
    # Check that we set key AFTER enqueue (not before)
    enqueue_pos = func_body.find('queue.enqueue(')
    set_pos = func_body.find('redis_conn.set(job_key, "enqueued"', enqueue_pos)
    
    assert set_pos > enqueue_pos, "❌ Setting dedup key before enqueue"
    print("✅ Setting dedup key AFTER successful enqueue")
    
    # Check for comment about this being critical fix
    assert 'CRITICAL FIX: Only set dedup key AFTER successful enqueue' in func_body, \
        "❌ Missing critical fix comment"
    print("✅ Critical fix documented in code")

def test_return_tuple():
    """Test 3: Verify return value is tuple (success, reason)"""
    print("\nTest 3: Checking return value format...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find enqueue_recording_download_only function
    func_start = content.find('def enqueue_recording_download_only(')
    func_end = content.find('\ndef ', func_start + 10)
    func_body = content[func_start:func_end]
    
    # Check docstring mentions tuple return
    assert 'tuple: (success: bool, reason: str)' in func_body, \
        "❌ Return type not documented as tuple"
    print("✅ Return type documented as tuple")
    
    # Check all return statements are tuples
    assert 'return (False, "cached")' in func_body, "❌ Missing cached return tuple"
    assert 'return (False, "error")' in func_body, "❌ Missing error return tuple"
    assert 'return (False, "duplicate")' in func_body, "❌ Missing duplicate return tuple"
    assert 'return (True, "enqueued")' in func_body, "❌ Missing enqueued return tuple"
    print("✅ All return statements use tuple format")
    
    # Check that there are no old-style boolean returns (return True/False alone)
    lines = func_body.split('\n')
    for i, line in enumerate(lines):
        if 'return True' in line or 'return False' in line:
            # Check if it's part of tuple
            if not ('return (True,' in line or 'return (False,' in line):
                raise AssertionError(f"❌ Line {i}: Old-style boolean return found: {line.strip()}")
    print("✅ No old-style boolean returns found")

def test_api_error_handling():
    """Test 4: Verify API distinguishes error from dedup"""
    print("\nTest 4: Checking API error handling...")
    
    with open('server/routes_calls.py', 'r') as f:
        content = f.read()
    
    # Check that API unpacks tuple
    assert 'job_success, reason = enqueue_recording_download_only(' in content, \
        "❌ API not unpacking tuple return value"
    print("✅ API unpacks tuple return value")
    
    # Check for error handling
    assert 'if reason == "error"' in content, "❌ API not checking for error reason"
    print("✅ API checks for error reason")
    
    # Check that error returns 500
    error_block_start = content.find('if reason == "error"')
    error_block_end = content.find('else:', error_block_start)
    error_block = content[error_block_start:error_block_end]
    
    assert '500' in error_block, "❌ Error case not returning HTTP 500"
    print("✅ Error case returns HTTP 500")
    
    # Check that success=False is set for error
    assert '"success": False' in error_block, "❌ Error case not setting success: False"
    print("✅ Error case sets success: False")

def test_recording_url_conversion():
    """Test 5: Verify .json URLs are converted to .mp3"""
    print("\nTest 5: Checking recording URL conversion...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Find recording callback function
    callback_start = content.find('def recording_status_callback')
    if callback_start == -1:
        callback_start = content.find('recording_url = request.form.get("RecordingUrl"')
    
    assert callback_start > 0, "❌ Could not find recording callback code"
    
    callback_end = content.find('\n@', callback_start + 100)  # Find next route
    if callback_end == -1:
        callback_end = len(content)
    callback_body = content[callback_start:callback_end]
    
    # Check for .json to .mp3 conversion
    assert '.endswith(".json")' in callback_body, "❌ Not checking for .json extension"
    print("✅ Checks for .json extension")
    
    # Check for conversion using .replace() method
    assert '.replace(".json", ".mp3")' in callback_body, \
        "❌ Not converting .json to .mp3 using .replace()"
    print("✅ Converts .json to .mp3 using .replace()")
    
    # Check that converted URL is saved
    assert 'media_url' in callback_body, "❌ Not using media_url variable"
    assert 'call_log.recording_url = media_url' in callback_body, \
        "❌ Not saving converted media_url"
    print("✅ Saves converted media URL to database")

def test_all():
    """Run all tests"""
    print("=" * 60)
    print("Recording Enqueue Fix - Test Suite")
    print("=" * 60)
    
    try:
        test_retry_import()
        test_dedup_flow()
        test_return_tuple()
        test_api_error_handling()
        test_recording_url_conversion()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
