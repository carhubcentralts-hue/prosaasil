"""
Test Recording 404 Fix with Twilio API Fallback

This test verifies that the recording endpoint can recover from missing
recording_url by fetching it from Twilio's API.
"""
import pytest
from unittest.mock import patch, MagicMock
from server.app_factory import create_app
from server.models_sql import db, CallLog, Business, User


@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_data(app):
    """Create test data"""
    with app.app_context():
        # Create business
        business = Business(
            name="Test Business",
            crm_type="custom"
        )
        db.session.add(business)
        db.session.flush()
        
        # Create user
        user = User(
            email="test@example.com",
            password_hash="dummy",
            business_id=business.id,
            role="owner"
        )
        db.session.add(user)
        db.session.flush()
        
        # Create call without recording_url (simulates webhook failure)
        call = CallLog(
            call_sid="CA1234567890abcdef1234567890abcdef",
            business_id=business.id,
            from_number="+1234567890",
            to_number="+0987654321",
            call_status="completed",
            recording_url=None,  # Missing!
            recording_sid=None
        )
        db.session.add(call)
        db.session.commit()
        
        return {
            'business_id': business.id,
            'user_id': user.id,
            'call_sid': call.call_sid,
            'call_id': call.id
        }


def test_recording_404_with_twilio_fallback(client, app, test_data):
    """Test that missing recording_url triggers Twilio API fetch"""
    
    with app.app_context():
        # Mock session to simulate logged-in user
        with client.session_transaction() as sess:
            sess['al_user'] = {
                'id': test_data['user_id'],
                'business_id': test_data['business_id'],
                'role': 'owner'
            }
        
        # Mock Twilio client
        mock_recording = MagicMock()
        mock_recording.uri = "/2010-04-01/Accounts/ACxxx/Recordings/RExxx.json"
        mock_recording.sid = "RExxx1234567890"
        
        with patch('server.routes_recordings.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.recordings.list.return_value = [mock_recording]
            mock_client_class.return_value = mock_client
            
            with patch('server.routes_recordings.check_local_recording_exists', return_value=False):
                with patch('server.routes_recordings.enqueue_recording_download_only') as mock_enqueue:
                    # Make HEAD request (AudioPlayer does this)
                    response = client.head(f"/api/recordings/file/{test_data['call_sid']}")
                    
                    # Should return 404 (file not ready yet)
                    assert response.status_code == 404
                    
                    # Verify Twilio API was called
                    mock_client.recordings.list.assert_called_once_with(
                        call_sid=test_data['call_sid'],
                        limit=1
                    )
                    
                    # Verify recording_url was saved to database
                    call = CallLog.query.get(test_data['call_id'])
                    assert call.recording_url is not None
                    assert call.recording_url == "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
                    assert call.recording_sid == "RExxx1234567890"
                    
                    # Verify download was enqueued
                    mock_enqueue.assert_called_once()
                    
                    print("✅ Test passed: Twilio API fallback working correctly")


def test_recording_404_no_twilio_recording(client, app, test_data):
    """Test error message when no recording exists in Twilio"""
    
    with app.app_context():
        # Mock session
        with client.session_transaction() as sess:
            sess['al_user'] = {
                'id': test_data['user_id'],
                'business_id': test_data['business_id'],
                'role': 'owner'
            }
        
        # Mock Twilio client - no recordings found
        with patch('server.routes_recordings.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.recordings.list.return_value = []  # No recordings
            mock_client_class.return_value = mock_client
            
            with patch('server.routes_recordings.check_local_recording_exists', return_value=False):
                # Make GET request to see error message
                response = client.get(f"/api/recordings/file/{test_data['call_sid']}")
                
                # Should return 404
                assert response.status_code == 404
                
                # Check error message
                data = response.get_json()
                assert "No recording found" in data.get('message_en', '')
                assert "לא נמצאה הקלטה" in data.get('message', '')
                
                print("✅ Test passed: Proper error message when no recording exists")


def test_recording_with_existing_url(client, app, test_data):
    """Test that existing recording_url works normally"""
    
    with app.app_context():
        # Update call with recording_url
        call = CallLog.query.get(test_data['call_id'])
        call.recording_url = "https://api.twilio.com/recordings/test.mp3"
        db.session.commit()
        
        # Mock session
        with client.session_transaction() as sess:
            sess['al_user'] = {
                'id': test_data['user_id'],
                'business_id': test_data['business_id'],
                'role': 'owner'
            }
        
        with patch('server.routes_recordings.check_local_recording_exists', return_value=False):
            with patch('server.routes_recordings.enqueue_recording_download_only') as mock_enqueue:
                # Make HEAD request
                response = client.head(f"/api/recordings/file/{test_data['call_sid']}")
                
                # Should return 404 (not downloaded yet)
                assert response.status_code == 404
                
                # Verify download was enqueued with existing URL
                mock_enqueue.assert_called_once()
                call_args = mock_enqueue.call_args
                assert call_args[1]['recording_url'] == "https://api.twilio.com/recordings/test.mp3"
                
                print("✅ Test passed: Existing recording_url used correctly")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
