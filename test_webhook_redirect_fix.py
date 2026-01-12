#!/usr/bin/env python3
"""
Test for webhook redirect handling fix
Tests that POST redirects are properly followed without consuming retry attempts
"""
import sys
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Add project root to path (parent directory of this script)
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class MockResponse:
    """Mock HTTP response"""
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


def test_webhook_follows_redirect_preserves_post():
    """Test that webhook follows redirects while preserving POST method"""
    print("🧪 Test 1: Webhook Follows Redirect and Preserves POST")
    
    from server.services.generic_webhook_service import send_generic_webhook
    
    # Provide webhook_url directly to bypass database
    with patch('server.services.generic_webhook_service.requests.post') as mock_post:
        # First call returns redirect, second call succeeds
        mock_post.side_effect = [
            MockResponse(302, headers={'Location': 'https://example.com/webhook'}),
            MockResponse(200, text='OK')
        ]
        
        # Mock threading to run synchronously
        with patch('server.services.generic_webhook_service.threading.Thread') as mock_thread:
            def run_sync(*args, **kwargs):
                # Call the target function directly
                kwargs['target']()
            mock_thread.return_value.start = lambda: run_sync(target=mock_thread.call_args[1]['target'])
            
            result = send_generic_webhook(
                business_id=1,
                event_type="test.event",
                data={"test": "data"},
                webhook_url="http://example.com/webhook"  # Provide URL directly
            )
        
        # Verify POST was called twice (once for original, once for redirect)
        assert mock_post.call_count == 2, f"Expected 2 POST calls, got {mock_post.call_count}"
        
        # Verify first call was to original URL
        first_call_url = mock_post.call_args_list[0][0][0]
        assert first_call_url == 'http://example.com/webhook', f"First call should be to original URL, got {first_call_url}"
        
        # Verify second call was to redirect URL
        second_call_url = mock_post.call_args_list[1][0][0]
        assert second_call_url == 'https://example.com/webhook', f"Second call should be to redirect URL, got {second_call_url}"
        
        print("  ✅ PASS - Webhook correctly follows redirect with POST method")
        return True


def test_webhook_multiple_redirects():
    """Test that webhook can follow multiple redirects"""
    print("\n🧪 Test 2: Webhook Follows Multiple Redirects")
    
    from server.services.generic_webhook_service import send_generic_webhook
    
    with patch('server.services.generic_webhook_service.requests.post') as mock_post:
        # Multiple redirects before success
        mock_post.side_effect = [
            MockResponse(301, headers={'Location': 'http://example.com/v2/webhook'}),
            MockResponse(302, headers={'Location': 'https://example.com/v2/webhook'}),
            MockResponse(200, text='OK')
        ]
        
        with patch('server.services.generic_webhook_service.threading.Thread') as mock_thread:
            def run_sync(*args, **kwargs):
                kwargs['target']()
            mock_thread.return_value.start = lambda: run_sync(target=mock_thread.call_args[1]['target'])
            
            result = send_generic_webhook(
                business_id=1,
                event_type="test.event",
                data={"test": "data"},
                webhook_url="http://example.com/webhook"
            )
        
        # Should have made 3 calls (2 redirects + final success)
        assert mock_post.call_count == 3, f"Expected 3 POST calls (2 redirects + success), got {mock_post.call_count}"
        
        print("  ✅ PASS - Webhook correctly follows multiple redirects")
        return True


def test_webhook_too_many_redirects():
    """Test that webhook stops after too many redirects"""
    print("\n🧪 Test 3: Webhook Stops After Too Many Redirects")
    
    from server.services.generic_webhook_service import send_generic_webhook, MAX_REDIRECTS, MAX_RETRIES
    
    with patch('server.services.generic_webhook_service.requests.post') as mock_post:
        # Return infinite redirects
        mock_post.return_value = MockResponse(
            301, 
            headers={'Location': 'http://example.com/webhook'}
        )
        
        with patch('server.services.generic_webhook_service.threading.Thread') as mock_thread:
            def run_sync(*args, **kwargs):
                kwargs['target']()
            mock_thread.return_value.start = lambda: run_sync(target=mock_thread.call_args[1]['target'])
            
            result = send_generic_webhook(
                business_id=1,
                event_type="test.event",
                data={"test": "data"},
                webhook_url="http://example.com/webhook"
            )
        
        # Calculate expected calls:
        # Each retry attempt makes: 1 initial request + MAX_REDIRECTS follow-up requests
        # With MAX_RETRIES attempts: (1 + MAX_REDIRECTS) * MAX_RETRIES
        # Example: MAX_REDIRECTS=5, MAX_RETRIES=3: (1+5)*3 = 18 calls
        expected_calls = (1 + MAX_REDIRECTS) * MAX_RETRIES
        
        # Should stop after hitting redirect limit, not make infinite calls
        assert mock_post.call_count > 0, "Should have made at least one call"
        assert mock_post.call_count <= expected_calls, f"Should make at most {expected_calls} calls (got {mock_post.call_count})"
        assert mock_post.call_count < 50, f"Should not make infinite calls, got {mock_post.call_count}"
        
        print(f"  ✅ PASS - Webhook stopped after {mock_post.call_count} calls (expected max: {expected_calls})")
        return True


def test_webhook_redirect_then_error_retries():
    """Test that errors after redirects still retry properly"""
    print("\n🧪 Test 4: Errors After Redirects Retry Correctly")
    
    from server.services.generic_webhook_service import send_generic_webhook
    
    with patch('server.services.generic_webhook_service.requests.post') as mock_post, \
         patch('server.services.generic_webhook_service.time.sleep'):  # Mock sleep to speed up test
        # First attempt: redirect then 500 error
        # Second attempt: redirect then success
        mock_post.side_effect = [
            MockResponse(302, headers={'Location': 'https://example.com/webhook'}),
            MockResponse(500, text='Server Error'),  # First attempt fails after redirect
            MockResponse(302, headers={'Location': 'https://example.com/webhook'}),
            MockResponse(200, text='OK')  # Second attempt succeeds after redirect
        ]
        
        with patch('server.services.generic_webhook_service.threading.Thread') as mock_thread:
            def run_sync(*args, **kwargs):
                kwargs['target']()
            mock_thread.return_value.start = lambda: run_sync(target=mock_thread.call_args[1]['target'])
            
            result = send_generic_webhook(
                business_id=1,
                event_type="test.event",
                data={"test": "data"},
                webhook_url="http://example.com/webhook"
            )
        
        # Should have made 4 calls total:
        # Attempt 1: original -> redirect -> error (2 calls)
        # Attempt 2: original -> redirect -> success (2 calls)
        assert mock_post.call_count == 4, f"Expected 4 POST calls, got {mock_post.call_count}"
        
        print("  ✅ PASS - Redirects don't consume retry attempts")
        return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Webhook Redirect Fix")
    print("=" * 60)
    
    tests = [
        test_webhook_follows_redirect_preserves_post,
        test_webhook_multiple_redirects,
        test_webhook_too_many_redirects,
        test_webhook_redirect_then_error_retries,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ FAIL - {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

