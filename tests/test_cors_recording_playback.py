"""
Test CORS headers for recording playback endpoints
Verifies fix for OPTIONS preflight requests
"""
import pytest
from flask import Flask
from server.auth_api import require_api_auth


def test_options_request_returns_cors_headers():
    """
    Test that OPTIONS requests to API endpoints return proper CORS headers.
    This is critical for recording playback in the browser.
    """
    app = Flask(__name__)
    app.secret_key = 'test-secret-key'
    
    @app.route('/api/test', methods=['GET', 'HEAD', 'OPTIONS'])
    @require_api_auth
    def test_endpoint():
        return {'status': 'ok'}, 200
    
    with app.test_client() as client:
        # Simulate browser CORS preflight request with Origin header
        response = client.options(
            '/api/test',
            headers={'Origin': 'http://localhost:3000'}
        )
        
        # Verify status code
        assert response.status_code == 204, f"Expected 204, got {response.status_code}"
        
        # Verify CORS headers are present
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'
        
        assert 'Access-Control-Allow-Credentials' in response.headers
        assert response.headers['Access-Control-Allow-Credentials'] == 'true'
        
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'OPTIONS' in response.headers['Access-Control-Allow-Methods']
        assert 'GET' in response.headers['Access-Control-Allow-Methods']
        assert 'HEAD' in response.headers['Access-Control-Allow-Methods']
        
        assert 'Access-Control-Allow-Headers' in response.headers
        
        assert 'Vary' in response.headers
        assert response.headers['Vary'] == 'Origin'
        
        assert 'Access-Control-Max-Age' in response.headers


def test_options_request_without_origin():
    """
    Test that OPTIONS requests without Origin header still work
    but don't include CORS headers.
    """
    app = Flask(__name__)
    app.secret_key = 'test-secret-key'
    
    @app.route('/api/test', methods=['GET', 'HEAD', 'OPTIONS'])
    @require_api_auth
    def test_endpoint():
        return {'status': 'ok'}, 200
    
    with app.test_client() as client:
        # OPTIONS request without Origin header
        response = client.options('/api/test')
        
        # Verify status code
        assert response.status_code == 204
        
        # Should not have CORS headers without Origin
        assert 'Access-Control-Allow-Origin' not in response.headers


def test_decorator_with_parentheses():
    """
    Test that the decorator works correctly when used with parentheses.
    This tests the second code path in require_api_auth.
    """
    app = Flask(__name__)
    app.secret_key = 'test-secret-key'
    
    @app.route('/api/test2', methods=['GET', 'HEAD', 'OPTIONS'])
    @require_api_auth()  # Note: with parentheses
    def test_endpoint():
        return {'status': 'ok'}, 200
    
    with app.test_client() as client:
        # Simulate browser CORS preflight request
        response = client.options(
            '/api/test2',
            headers={'Origin': 'http://localhost:3000'}
        )
        
        # Verify status code
        assert response.status_code == 204
        
        # Verify CORS headers
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
