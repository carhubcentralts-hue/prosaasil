"""
Test for recording download endpoint fix (502 Bad Gateway)
Verifies that the endpoint returns proper errors instead of crashing
"""
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Set migration mode to avoid DB initialization
os.environ['MIGRATION_MODE'] = '1'


def test_download_endpoint_exists():
    """Verify the download endpoint is registered"""
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all registered routes
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    
    # Check that download endpoint exists
    download_route = '/api/calls/<call_sid>/download'
    
    # Find matching route (may have different format in Flask)
    matching_routes = [r for r in routes if 'download' in r and '/api/calls/' in r]
    
    assert len(matching_routes) > 0, f"Download endpoint not found. Available routes with 'calls': {[r for r in routes if 'calls' in r]}"
    print(f"✅ Download endpoint found: {matching_routes}")


def test_download_endpoint_error_handling():
    """Test that download endpoint handles errors gracefully without crashing"""
    from server.app_factory import create_app
    from server.models_sql import CallLog
    
    app = create_app()
    
    with app.test_client() as client:
        # Test 1: Invalid call_sid should return 404, not 502
        with app.app_context():
            # Mock authentication
            with patch('server.auth_api.require_api_auth', return_value=lambda f: f):
                with patch('server.routes_crm.get_business_id', return_value=1):
                    response = client.get('/api/calls/INVALID_SID/download')
                    
                    # Should not be 502 (Bad Gateway)
                    assert response.status_code != 502, "Endpoint crashed with 502"
                    # Should be 404 (Not Found) or 400 (Bad Request)
                    assert response.status_code in [404, 400, 401], f"Expected 404/400/401, got {response.status_code}"
                    print(f"✅ Invalid call_sid returns proper error: {response.status_code}")


def test_recording_service_error_handling():
    """Test that recording service handles Twilio failures gracefully"""
    from server.services.recording_service import get_recording_file_for_call, _download_from_twilio
    from server.models_sql import CallLog
    
    # Test 1: None input should not crash
    result = get_recording_file_for_call(None)
    assert result is None, "Should return None for invalid input"
    print("✅ recording_service handles None input")
    
    # Test 2: CallLog without recording_url should not crash
    mock_call = Mock(spec=CallLog)
    mock_call.call_sid = "TEST123"
    mock_call.recording_url = None
    
    result = get_recording_file_for_call(mock_call)
    assert result is None, "Should return None when no recording_url"
    print("✅ recording_service handles missing recording_url")
    
    # Test 3: Twilio download failure should not crash
    with patch('server.services.recording_service.requests.get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        result = _download_from_twilio(
            "https://api.twilio.com/test.mp3",
            "test_sid",
            "test_token",
            "TEST123"
        )
        assert result is None, "Should return None on Twilio failure"
        print("✅ recording_service handles Twilio failure")


def test_nginx_config_has_streaming_support():
    """Verify nginx.conf has proper audio streaming configuration"""
    nginx_conf_path = os.path.join(os.path.dirname(__file__), 'docker', 'nginx.conf')
    
    assert os.path.exists(nginx_conf_path), "nginx.conf not found"
    
    with open(nginx_conf_path, 'r') as f:
        content = f.read()
    
    # Check for required streaming settings
    required_settings = [
        'proxy_buffering off',
        'proxy_request_buffering off',
        'proxy_read_timeout',
        'proxy_send_timeout',
        'Range $http_range'
    ]
    
    missing = []
    for setting in required_settings:
        if setting not in content:
            missing.append(setting)
    
    assert len(missing) == 0, f"nginx.conf missing required streaming settings: {missing}"
    print("✅ nginx.conf has all required streaming settings")


if __name__ == '__main__':
    print("\n=== Testing Recording Download Fix ===\n")
    
    try:
        test_download_endpoint_exists()
        print()
        test_download_endpoint_error_handling()
        print()
        test_recording_service_error_handling()
        print()
        test_nginx_config_has_streaming_support()
        print()
        print("✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
