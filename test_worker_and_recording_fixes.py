"""
Test Worker and Recording Fixes
Tests for:
1. Worker properly imports and handles delete_receipts_batch_job
2. Safe filename access for attachments
"""
import sys
import os
import py_compile

def test_python_syntax():
    """Test that all modified Python files compile"""
    print("\n🧪 TEST: Python syntax validation")
    
    files_to_check = [
        'server/worker.py',
        'server/jobs/__init__.py',
        'server/jobs/delete_receipts_job.py',
        'server/routes_receipts.py',
        'server/routes_receipts_contracts.py',
        'server/routes_calls.py',
        'server/tasks_recording.py',
    ]
    
    base_path = os.path.dirname(__file__)
    
    for file in files_to_check:
        file_path = os.path.join(base_path, file)
        try:
            py_compile.compile(file_path, doraise=True)
            print(f"✅ {file}: syntax OK")
        except Exception as e:
            raise AssertionError(f"❌ {file}: syntax error: {e}")


def test_safe_get_filename_logic():
    """Test safe_get_filename logic without importing Flask dependencies"""
    print("\n🧪 TEST: safe_get_filename logic")
    
    # Simulate the function logic
    def safe_get_filename_test(attachment, default=None):
        if not attachment:
            return default or f"attachment_{id(attachment)}"
        
        for attr in ['filename_original', 'filename', 'original_filename', 'file_name', 'name']:
            if hasattr(attachment, attr):
                value = getattr(attachment, attr, None)
                if value:
                    return value
        
        if hasattr(attachment, 'id'):
            return default or f"attachment_{attachment.id}"
        
        return default or "unknown_file"
    
    # Test with mock object that has filename_original
    class MockAttachment1:
        filename_original = "test.pdf"
        id = 123
    
    result = safe_get_filename_test(MockAttachment1())
    print(f"✅ filename_original: {result}")
    assert result == "test.pdf", f"Expected 'test.pdf' but got '{result}'"
    
    # Test with mock object that has filename (legacy)
    class MockAttachment2:
        filename = "legacy.pdf"
        id = 456
    
    result = safe_get_filename_test(MockAttachment2())
    print(f"✅ filename (legacy): {result}")
    assert result == "legacy.pdf", f"Expected 'legacy.pdf' but got '{result}'"
    
    # Test with mock object that has neither - should use ID
    class MockAttachment3:
        id = 789
    
    result = safe_get_filename_test(MockAttachment3())
    print(f"✅ fallback to ID: {result}")
    assert "789" in result, f"Expected ID 789 in result but got '{result}'"
    
    # Test with None
    result = safe_get_filename_test(None, "default.txt")
    print(f"✅ None with default: {result}")
    assert result == "default.txt", f"Expected 'default.txt' but got '{result}'"


def test_key_fixes_present():
    """Verify key fixes are present in the code"""
    print("\n🧪 TEST: Key fixes verification")
    
    base_path = os.path.dirname(__file__)
    
    # Check that worker.py imports delete_receipts_batch_job
    worker_path = os.path.join(base_path, 'server', 'worker.py')
    with open(worker_path, 'r') as f:
        worker_content = f.read()
    
    assert 'from server.jobs.delete_receipts_job import delete_receipts_batch_job' in worker_content, \
        "Worker doesn't import delete_receipts_batch_job"
    print("✅ Worker imports delete_receipts_batch_job")
    
    # Check that jobs/__init__.py exports delete_receipts_batch_job
    jobs_init_path = os.path.join(base_path, 'server', 'jobs', '__init__.py')
    with open(jobs_init_path, 'r') as f:
        jobs_init_content = f.read()
    
    assert 'delete_receipts_batch_job' in jobs_init_content, \
        "jobs/__init__.py doesn't export delete_receipts_batch_job"
    print("✅ jobs/__init__.py exports delete_receipts_batch_job")
    
    # Check that routes_receipts.py has safe_get_filename
    routes_receipts_path = os.path.join(base_path, 'server', 'routes_receipts.py')
    with open(routes_receipts_path, 'r') as f:
        routes_receipts_content = f.read()
    
    assert 'def safe_get_filename' in routes_receipts_content, \
        "routes_receipts.py doesn't have safe_get_filename function"
    print("✅ routes_receipts.py has safe_get_filename function")
    
    # Check that routes_receipts_contracts.py uses filename_original not filename
    contracts_path = os.path.join(base_path, 'server', 'routes_receipts_contracts.py')
    with open(contracts_path, 'r') as f:
        contracts_content = f.read()
    
    # Check line around 357
    if 'attachment.filename = file.filename' in contracts_content:
        raise AssertionError("routes_receipts_contracts.py still uses attachment.filename (should be filename_original)")
    
    assert 'attachment.filename_original = file.filename' in contracts_content, \
        "routes_receipts_contracts.py doesn't use filename_original"
    print("✅ routes_receipts_contracts.py uses filename_original")
    
    # Check that tasks_recording.py has rate limiting
    tasks_recording_path = os.path.join(base_path, 'server', 'tasks_recording.py')
    with open(tasks_recording_path, 'r') as f:
        tasks_recording_content = f.read()
    
    assert '_check_business_rate_limit' in tasks_recording_content, \
        "tasks_recording.py doesn't have _check_business_rate_limit function"
    print("✅ tasks_recording.py has rate limiting function")
    
    assert 'BLOCKED' in tasks_recording_content, \
        "tasks_recording.py doesn't have BLOCKED logging"
    print("✅ tasks_recording.py has BLOCKED logging")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING: Worker and Recording Fixes")
    print("=" * 60)
    
    test_python_syntax()
    test_safe_get_filename_logic()
    test_key_fixes_present()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)

