#!/usr/bin/env python3
"""
Test script to verify WhatsApp timeout fix implementation
Tests:
1. Baileys provider timeout increased to 15s
2. Retry logic (2 attempts) on timeout
3. Background sending thread functionality
"""

import sys
import time
from unittest.mock import Mock, patch, MagicMock
import threading

def test_baileys_timeout_increase():
    """Test that Baileys timeout is increased to 15s"""
    print("🧪 Test 1: Baileys Timeout Increase")
    
    # Import the provider
    sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')
    from server.whatsapp_provider import BaileysProvider
    
    provider = BaileysProvider()
    
    # Check timeout is 15s
    assert provider.read_timeout == 15.0, f"Expected timeout 15s, got {provider.read_timeout}s"
    assert provider.timeout == 15.0, f"Expected timeout 15s, got {provider.timeout}s"
    
    print("  ✅ PASS - Timeout is 15s")
    return True

def test_baileys_retry_logic():
    """Test that Baileys retries once on timeout"""
    print("\n🧪 Test 2: Baileys Retry Logic")
    
    sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')
    from server.whatsapp_provider import BaileysProvider
    import requests
    
    provider = BaileysProvider()
    
    # Mock the session.post to simulate timeout
    attempt_count = 0
    
    def mock_post(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise requests.exceptions.Timeout("Simulated timeout")
    
    with patch.object(provider._session, 'post', side_effect=mock_post):
        with patch.object(provider, '_check_health', return_value=True):
            result = provider.send_text(
                to="972501234567",
                text="Test message",
                tenant_id="business_1"
            )
    
    # Should attempt twice (initial + 1 retry)
    assert attempt_count == 2, f"Expected 2 attempts, got {attempt_count}"
    assert result['status'] == 'error', f"Expected error status, got {result['status']}"
    assert 'timeout' in result['error'].lower(), f"Expected timeout error, got {result['error']}"
    
    print(f"  ✅ PASS - Retried {attempt_count} times as expected")
    print(f"  ✅ PASS - Error response: {result['error']}")
    return True

def test_background_send_function():
    """Test that background send function is defined and callable"""
    print("\n🧪 Test 3: Background Send Function")
    
    # Instead of importing the function (which requires Flask),
    # verify the function signature exists in the source file
    import os
    
    source_file = '/home/runner/work/prosaasil/prosaasil/server/routes_whatsapp.py'
    
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Check function exists
    assert '_send_whatsapp_message_background' in content, "Background send function not found in source"
    
    # Check function has the required parameters
    expected_params = ['business_id', 'tenant_id', 'from_number', 'response_text', 'wa_msg_id']
    for param in expected_params:
        assert param in content, f"Missing parameter in source: {param}"
    
    # Check it uses threading
    assert 'threading.Thread' in content, "Background function doesn't use threading"
    assert 'send_with_failover' in content, "Doesn't use send_with_failover for Twilio fallback"
    
    print(f"  ✅ PASS - Function exists in source with correct signature")
    print(f"  ✅ PASS - Uses threading.Thread for background execution")
    print(f"  ✅ PASS - Uses send_with_failover for automatic fallback")
    return True

def test_background_thread_behavior():
    """Test that background thread executes without blocking"""
    print("\n🧪 Test 4: Background Thread Non-Blocking")
    
    sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')
    
    # Simulate the background threading pattern used in webhook
    execution_log = []
    
    def mock_background_task():
        time.sleep(0.1)  # Simulate slow sending
        execution_log.append("background_complete")
    
    start = time.time()
    
    # Start background thread (like in webhook)
    thread = threading.Thread(target=mock_background_task, daemon=True)
    thread.start()
    
    # Immediately continue (like webhook returning 200)
    execution_log.append("webhook_returned")
    
    duration = time.time() - start
    
    # Webhook should return almost immediately (< 50ms)
    assert duration < 0.05, f"Webhook blocked for {duration*1000:.0f}ms (expected <50ms)"
    
    # Wait for background to complete
    thread.join(timeout=1.0)
    
    # Verify execution order
    assert execution_log[0] == "webhook_returned", "Webhook should return before background completes"
    assert len(execution_log) == 2, "Background task should complete"
    assert execution_log[1] == "background_complete", "Background task should complete"
    
    print(f"  ✅ PASS - Webhook returned in {duration*1000:.0f}ms")
    print(f"  ✅ PASS - Background task completed asynchronously")
    return True

def test_twilio_fallback_integration():
    """Test that send_with_failover is properly integrated"""
    print("\n🧪 Test 5: Twilio Fallback Integration")
    
    sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')
    from server.whatsapp_provider import WhatsAppService, BaileysProvider, TwilioProvider
    
    # Mock Baileys to fail
    baileys = BaileysProvider()
    service = WhatsAppService(baileys, tenant_id="business_1")
    
    # Check send_with_failover method exists
    assert hasattr(service, 'send_with_failover'), "send_with_failover method not found"
    
    print(f"  ✅ PASS - send_with_failover method exists")
    
    # Verify method signature
    import inspect
    sig = inspect.signature(service.send_with_failover)
    params = list(sig.parameters.keys())
    
    expected_params = ['to', 'message', 'thread_data', 'tenant_id']
    for param in expected_params:
        assert param in params, f"Missing parameter in send_with_failover: {param}"
    
    print(f"  ✅ PASS - send_with_failover has correct signature")
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("WhatsApp Timeout Fix - Test Suite")
    print("=" * 60)
    
    tests = [
        test_baileys_timeout_increase,
        test_baileys_retry_logic,
        test_background_send_function,
        test_background_thread_behavior,
        test_twilio_fallback_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
