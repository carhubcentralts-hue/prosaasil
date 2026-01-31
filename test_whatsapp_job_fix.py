"""
Test that send_whatsapp_message_job receives all required arguments

This is a verification script that uses string-based testing to validate
the fix without requiring all dependencies to be installed. For production
testing, consider using proper unit tests with mocks.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_send_whatsapp_message_job_signature():
    """Test that send_whatsapp_message_job has the expected signature"""
    import inspect
    
    # Read the file directly to check signature without importing dependencies
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'jobs', 'send_whatsapp_message_job.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check that the function has the required parameters
    assert 'def send_whatsapp_message_job(' in content, "Function should be defined"
    assert 'business_id: int,' in content, "Function should have business_id parameter"
    assert 'tenant_id: str,' in content, "Function should have tenant_id parameter"
    assert 'remote_jid: str,' in content, "Function should have remote_jid parameter"
    assert 'response_text: str,' in content, "Function should have response_text parameter"
    
    print(f"✅ Test passed: send_whatsapp_message_job has correct signature")


def test_enqueue_fix():
    """Test that enqueue() fix correctly passes business_id and run_id"""
    
    # Read the enqueue function to verify the fix
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'services', 'jobs.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Verify the fix is present
    assert "job_func_kwargs = dict(kwargs)" in content, "Fix should create job_func_kwargs"
    assert "if business_id is not None:" in content, "Fix should check business_id"
    assert "job_func_kwargs['business_id'] = business_id" in content, "Fix should add business_id to kwargs"
    assert "if run_id is not None:" in content, "Fix should check run_id"
    assert "job_func_kwargs['run_id'] = run_id" in content, "Fix should add run_id to kwargs"
    assert "**job_func_kwargs," in content, "Fix should pass job_func_kwargs to queue.enqueue"
    
    print("✅ Test passed: enqueue() fix correctly passes business_id and run_id to job functions")


def test_routes_whatsapp_usage():
    """Test that routes_whatsapp.py correctly calls enqueue_job"""
    
    # Read the routes_whatsapp file
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_whatsapp.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check that enqueue_job is called with business_id
    assert 'enqueue_job(' in content or 'enqueue(' in content, "Should call enqueue_job"
    assert 'business_id=business_id' in content, "Should pass business_id parameter"
    assert 'tenant_id=tenant_id' in content, "Should pass tenant_id parameter"
    assert 'remote_jid=reply_jid' in content, "Should pass remote_jid parameter"
    assert 'response_text=response_text' in content, "Should pass response_text parameter"
    
    print("✅ Test passed: routes_whatsapp.py correctly calls enqueue with all parameters")


if __name__ == '__main__':
    print("Running tests for WhatsApp job fix...")
    print()
    
    test_send_whatsapp_message_job_signature()
    print()
    
    test_enqueue_fix()
    print()
    
    test_routes_whatsapp_usage()
    print()
    
    print("🎉 All tests passed!")
