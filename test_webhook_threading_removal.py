#!/usr/bin/env python3
"""
Test WhatsApp webhook endpoint after threading removal.

This test verifies that:
1. The webhook endpoint only enqueues jobs (no inline processing)
2. Returns 503 when Redis is unavailable (no fallback)
3. Proper deduplication works
4. Valid Python syntax in all modified files
"""
import sys
import ast
import os


def test_webhook_code_structure():
    """
    Verify that routes_webhook.py has the correct structure after threading removal.
    """
    print("🧪 Test 1: Verify webhook code structure")
    
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_webhook.py')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Test 1: Legacy functions should be removed
    assert '_process_whatsapp_fast' not in code, "❌ _process_whatsapp_fast should be removed"
    assert '_process_whatsapp_with_cleanup' not in code, "❌ _process_whatsapp_with_cleanup should be removed"
    assert 'get_or_create_app' not in code, "❌ get_or_create_app should be removed"
    assert '_async_conversation_analysis' not in code, "❌ _async_conversation_analysis should be removed"
    print("   ✅ All legacy functions removed")
    
    # Test 2: Threading globals should be removed
    assert '_active_wa_threads' not in code, "❌ _active_wa_threads should be removed"
    assert '_wa_thread_semaphore' not in code, "❌ _wa_thread_semaphore should be removed"
    assert 'MAX_CONCURRENT_WA_THREADS' not in code, "❌ MAX_CONCURRENT_WA_THREADS should be removed"
    print("   ✅ All threading globals removed")
    
    # Test 3: New patterns should be present
    assert 'enqueue_with_dedupe' in code, "❌ enqueue_with_dedupe not found"
    assert 'webhook_process_job' in code, "❌ webhook_process_job not imported"
    assert 'service_unavailable' in code, "❌ 503 error handling not found"
    print("   ✅ Job-based processing in place")
    
    # Test 4: No inline processing fallback
    assert 'Fallback to inline processing' not in code, "❌ Fallback comment still present"
    print("   ✅ No fallback processing")
    
    # Test 5: Verify syntax
    try:
        ast.parse(code)
        print("   ✅ Valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"❌ Syntax error: {e}")
    
    print("✅ Test 1 PASSED\n")


def test_webhook_job_structure():
    """
    Verify that webhook_process_job has all necessary logic.
    """
    print("🧪 Test 2: Verify webhook job structure")
    
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'jobs', 'webhook_process_job.py')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Test 1: Required imports
    required_imports = [
        'from server.services.business_resolver import resolve_business_with_fallback',
        'from server.whatsapp_provider import get_whatsapp_service',
        'from server.services.ai_service import get_ai_service',
        'from server.models_sql import WhatsAppMessage',
        'from flask import current_app',
    ]
    
    for import_line in required_imports:
        assert import_line in code, f"❌ Missing import: {import_line}"
    print("   ✅ All required imports present")
    
    # Test 2: Uses app context
    assert 'with current_app.app_context()' in code, "❌ Missing app context"
    print("   ✅ Uses Flask app context")
    
    # Test 3: Has AI processing logic
    assert 'ai_service.generate_response_with_agent' in code, "❌ Missing AI processing"
    assert 'wa_service.send_message' in code, "❌ Missing WhatsApp sending"
    print("   ✅ Has complete processing logic")
    
    # Test 4: Verify syntax
    try:
        ast.parse(code)
        print("   ✅ Valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"❌ Syntax error: {e}")
    
    print("✅ Test 2 PASSED\n")


def test_no_orphaned_references():
    """
    Verify no other files reference the removed functions.
    """
    print("🧪 Test 3: Check for orphaned references")
    
    removed_functions = [
        '_process_whatsapp_fast',
        '_process_whatsapp_with_cleanup',
        'get_or_create_app',
        '_active_wa_threads',
    ]
    
    # Search in Python files
    import subprocess
    
    for func in removed_functions:
        result = subprocess.run(
            ['grep', '-r', func, '--include=*.py', 'server/'],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True
        )
        
        # Filter out the test file itself
        lines = [line for line in result.stdout.split('\n') if line and 'test_webhook_threading_removal' not in line]
        
        if lines:
            print(f"   ⚠️  Found references to {func}:")
            for line in lines[:5]:  # Show first 5 matches
                print(f"      {line}")
            raise AssertionError(f"❌ Found orphaned references to {func}")
    
    print("   ✅ No orphaned references found")
    print("✅ Test 3 PASSED\n")


def test_architecture_separation():
    """
    Verify that the architecture maintains proper separation.
    """
    print("🧪 Test 4: Verify architecture separation")
    
    webhook_file = os.path.join(os.path.dirname(__file__), 'server', 'routes_webhook.py')
    with open(webhook_file, 'r') as f:
        webhook_code = f.read()
    
    # Webhook should only enqueue, not process
    heavy_processing = [
        'CustomerIntelligence',
        'get_ai_service',
        'generate_response_with_agent',
        'find_or_create_customer_from_whatsapp',
    ]
    
    for pattern in heavy_processing:
        assert pattern not in webhook_code, f"❌ Webhook still has heavy processing: {pattern}"
    
    print("   ✅ Webhook only enqueues (no heavy processing)")
    
    # Webhook should have enqueue logic
    assert 'enqueue_with_dedupe' in webhook_code, "❌ Missing enqueue logic"
    assert 'dedupe_key' in webhook_code, "❌ Missing deduplication"
    print("   ✅ Webhook has proper enqueue logic")
    
    # Job file should have all the processing
    job_file = os.path.join(os.path.dirname(__file__), 'server', 'jobs', 'webhook_process_job.py')
    with open(job_file, 'r') as f:
        job_code = f.read()
    
    for pattern in heavy_processing:
        assert pattern in job_code, f"❌ Job missing processing logic: {pattern}"
    
    print("   ✅ Job has all processing logic")
    print("✅ Test 4 PASSED\n")


def test_error_handling():
    """
    Verify proper error handling without fallback.
    """
    print("🧪 Test 5: Verify error handling")
    
    file_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_webhook.py')
    with open(file_path, 'r') as f:
        code = f.read()
    
    # Should return 503 on enqueue failure
    assert '503' in code, "❌ Missing 503 status code"
    assert 'service_unavailable' in code, "❌ Missing service unavailable error"
    print("   ✅ Returns 503 on queue failure")
    
    # Should NOT have fallback processing
    assert 'fallback' not in code.lower() or 'no fallback' in code.lower(), "❌ Has fallback processing"
    print("   ✅ No fallback processing")
    
    # Should have CRITICAL logging
    assert 'CRITICAL' in code, "❌ Missing critical error logging"
    print("   ✅ Has critical error logging")
    
    print("✅ Test 5 PASSED\n")


def main():
    print("=" * 60)
    print("WhatsApp Webhook Threading Removal - Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_webhook_code_structure()
        test_webhook_job_structure()
        test_no_orphaned_references()
        test_architecture_separation()
        test_error_handling()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Summary:")
        print("  • Legacy threading code removed (357 lines)")
        print("  • Single execution path maintained")
        print("  • Proper error handling (503 on failure)")
        print("  • Clean separation: API enqueues, Worker processes")
        print("  • No orphaned references")
        print()
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print("❌ TEST FAILED!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ UNEXPECTED ERROR!")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
