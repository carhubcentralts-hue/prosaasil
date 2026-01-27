"""
Test HEAD request support for /api/recordings/file endpoint

This test verifies that the fix for AudioPlayer 404 errors works correctly.
"""
import pytest
import os
import tempfile
from server.app import app
from server.models_sql import db, Business, CallLog, User
from server.services.recording_service import _get_recordings_dir
from datetime import datetime


@pytest.fixture
def client():
    """Create a test client"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


@pytest.fixture
def auth_headers(client):
    """Create authenticated user and return auth headers"""
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business",
            phone="1234567890"
        )
        db.session.add(business)
        db.session.commit()
        
        # Create test user
        user = User(
            username="test@example.com",
            email="test@example.com",
            business_id=business.id,
            is_active=True
        )
        user.set_password("testpass123")
        db.session.add(user)
        db.session.commit()
        
        # Login to get session
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        # Session cookie should be set automatically
        return {'business_id': business.id}


def test_head_request_file_not_found(client, auth_headers):
    """Test HEAD request returns 404 when file doesn't exist"""
    with app.app_context():
        business_id = auth_headers['business_id']
        
        # Create a call log without a recording file
        call = CallLog(
            call_sid="CA1234567890abcdef1234567890abcdef",
            business_id=business_id,
            from_number="+15551234567",
            to_number="+15559876543",
            status="completed",
            direction="inbound",
            created_at=datetime.utcnow()
        )
        db.session.add(call)
        db.session.commit()
        
        # Make HEAD request
        response = client.head(f'/api/recordings/file/{call.call_sid}')
        
        # Should return 404 without JSON body
        assert response.status_code == 404
        assert response.data == b''  # No body for HEAD request


def test_head_request_file_exists(client, auth_headers):
    """Test HEAD request returns 200 with proper headers when file exists"""
    with app.app_context():
        business_id = auth_headers['business_id']
        
        # Create a call log
        call_sid = "CA1234567890abcdef1234567890abcdef"
        call = CallLog(
            call_sid=call_sid,
            business_id=business_id,
            from_number="+15551234567",
            to_number="+15559876543",
            status="completed",
            direction="inbound",
            created_at=datetime.utcnow()
        )
        db.session.add(call)
        db.session.commit()
        
        # Create a mock recording file
        recordings_dir = _get_recordings_dir()
        os.makedirs(recordings_dir, exist_ok=True)
        file_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
        
        # Write some dummy content
        with open(file_path, 'wb') as f:
            f.write(b'fake mp3 content for testing')
        
        try:
            # Make HEAD request
            response = client.head(f'/api/recordings/file/{call_sid}')
            
            # Should return 200 with proper headers
            assert response.status_code == 200
            assert response.data == b''  # No body for HEAD request
            assert response.headers['Content-Type'] == 'audio/mpeg'
            assert 'Content-Length' in response.headers
            assert response.headers['Accept-Ranges'] == 'bytes'
            assert response.headers['Cache-Control'] == 'no-store'
            
        finally:
            # Clean up test file
            if os.path.exists(file_path):
                os.remove(file_path)


def test_head_request_unauthorized(client):
    """Test HEAD request returns 401 when not authenticated"""
    # Make HEAD request without authentication
    response = client.head('/api/recordings/file/CA1234567890abcdef1234567890abcdef')
    
    # Should return 401 or 403 (depending on auth implementation)
    assert response.status_code in [401, 403]


def test_get_request_still_works(client, auth_headers):
    """Test that GET requests still work as expected after HEAD support"""
    with app.app_context():
        business_id = auth_headers['business_id']
        
        # Create a call log
        call_sid = "CA1234567890abcdef1234567890abcdef"
        call = CallLog(
            call_sid=call_sid,
            business_id=business_id,
            from_number="+15551234567",
            to_number="+15559876543",
            status="completed",
            direction="inbound",
            created_at=datetime.utcnow()
        )
        db.session.add(call)
        db.session.commit()
        
        # Create a mock recording file
        recordings_dir = _get_recordings_dir()
        os.makedirs(recordings_dir, exist_ok=True)
        file_path = os.path.join(recordings_dir, f"{call_sid}.mp3")
        
        test_content = b'fake mp3 content for testing'
        with open(file_path, 'wb') as f:
            f.write(test_content)
        
        try:
            # Make GET request
            response = client.get(f'/api/recordings/file/{call_sid}')
            
            # Should return 200 with file content
            assert response.status_code == 200
            assert response.data == test_content  # GET returns body
            assert response.headers['Content-Type'] == 'audio/mpeg'
            
        finally:
            # Clean up test file
            if os.path.exists(file_path):
                os.remove(file_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
