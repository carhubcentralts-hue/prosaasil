"""
Tests for Status Change Prompt API endpoints
Tests the fixed GET and POST endpoints with proper error handling
"""
import pytest
import json
from server.models_sql import Business, PromptRevisions, db
from datetime import datetime


class TestStatusChangePromptAPI:
    """Test suite for status change prompt endpoints"""
    
    def test_get_prompt_returns_default_when_none_exists(self, client, auth_headers):
        """
        Test GET endpoint returns stable default when no custom prompt exists
        ✅ FIX: Should never return 404/null, always return default
        """
        response = client.get(
            '/api/ai/status_change_prompt/get',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check new response format
        assert data.get('ok') == True or data.get('success') == True
        assert 'prompt' in data
        assert data['prompt'] != ''  # Should have default prompt
        assert data['version'] == 0
        assert data.get('exists') == False or data.get('has_custom_prompt') == False
    
    def test_get_prompt_returns_custom_when_exists(self, client, auth_headers, test_business):
        """
        Test GET endpoint returns custom prompt when it exists
        """
        # Create a custom prompt
        revision = PromptRevisions()
        revision.tenant_id = test_business.id
        revision.version = 1
        revision.status_change_prompt = "Test custom prompt"
        revision.changed_by = "test@example.com"
        revision.changed_at = datetime.utcnow()
        db.session.add(revision)
        db.session.commit()
        
        response = client.get(
            '/api/ai/status_change_prompt/get',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data.get('ok') == True or data.get('success') == True
        assert data['prompt'] == "Test custom prompt"
        assert data['version'] == 1
        assert data.get('exists') == True or data.get('has_custom_prompt') == True
        assert 'updated_at' in data
    
    def test_save_prompt_returns_full_object(self, client, auth_headers, test_business):
        """
        Test POST endpoint returns full updated object (not just {ok:true})
        ✅ FIX: Response should include prompt, version, updated_at
        """
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json={'prompt_text': 'New custom prompt for testing'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check new response format
        assert data.get('ok') == True or data.get('success') == True
        assert 'prompt' in data
        assert data['prompt'] == 'New custom prompt for testing'
        assert 'version' in data
        assert data['version'] >= 1
        assert 'updated_at' in data
        assert 'message' in data
    
    def test_save_prompt_with_version_conflict(self, client, auth_headers, test_business):
        """
        Test optimistic locking: 409 Conflict when version mismatch
        ✅ FIX: Should return 409 with latest data when version conflicts
        """
        # Create initial revision
        revision = PromptRevisions()
        revision.tenant_id = test_business.id
        revision.version = 5
        revision.status_change_prompt = "Current prompt v5"
        revision.changed_by = "user@example.com"
        revision.changed_at = datetime.utcnow()
        db.session.add(revision)
        db.session.commit()
        
        # Try to save with old version (simulating race condition)
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json={
                'prompt_text': 'Trying to save with old version',
                'version': 3  # Old version - should conflict
            }
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        
        assert data.get('ok') == False
        assert data.get('error') == 'VERSION_CONFLICT'
        assert 'latest_version' in data
        assert data['latest_version'] == 5
        assert 'latest_prompt' in data
        assert data['latest_prompt'] == "Current prompt v5"
    
    def test_save_empty_prompt_returns_error(self, client, auth_headers):
        """
        Test POST endpoint validates empty prompt
        """
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json={'prompt_text': ''}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data.get('ok') == False
        assert 'error' in data
        assert data['error'] == 'EMPTY_PROMPT'
    
    def test_save_too_long_prompt_returns_error(self, client, auth_headers):
        """
        Test POST endpoint validates prompt length
        """
        long_prompt = 'x' * 5001  # Exceeds 5000 char limit
        
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json={'prompt_text': long_prompt}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data.get('ok') == False
        assert 'error' in data
        assert data['error'] == 'PROMPT_TOO_LONG'
    
    def test_all_errors_return_consistent_json(self, client, auth_headers):
        """
        Test all error responses return consistent JSON format
        ✅ FIX: No HTML/unstructured errors, always {ok, error, details}
        """
        # Test empty prompt error
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json={'prompt_text': ''}
        )
        
        assert response.status_code == 400
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        assert 'ok' in data or 'success' in data
        assert 'error' in data
        assert 'details' in data
        
        # Test missing data error
        response = client.post(
            '/api/ai/status_change_prompt/save',
            headers=auth_headers,
            json=None
        )
        
        assert response.status_code == 400
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        assert 'ok' in data or 'success' in data
        assert 'error' in data


# Fixtures for testing
@pytest.fixture
def test_business():
    """Create a test business"""
    business = Business()
    business.name = "Test Business"
    business.email = "test@example.com"
    db.session.add(business)
    db.session.commit()
    yield business
    db.session.delete(business)
    db.session.commit()


@pytest.fixture
def auth_headers(test_business):
    """Create authentication headers for test business"""
    # This would normally set up proper auth headers
    # For now, return a basic structure
    return {
        'Authorization': 'Bearer test_token',
        'Content-Type': 'application/json'
    }
