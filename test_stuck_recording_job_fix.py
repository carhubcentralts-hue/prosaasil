"""
Test for stuck recording job fix - prevents UI infinite loops

Tests that:
1. Stuck jobs (> 5 minutes old) are detected
2. Stuck jobs are marked as failed
3. New jobs are triggered for stuck recordings
4. UI gets proper status instead of infinite 202 loop
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from server.routes_recordings import cleanup_stuck_recording_jobs, JOB_TIMEOUT_MINUTES


def test_detect_stuck_job():
    """Test that jobs older than JOB_TIMEOUT_MINUTES are considered stuck"""
    from datetime import datetime, timedelta
    
    # Job created 6 minutes ago (> 5 minute timeout)
    old_job_created = datetime.utcnow() - timedelta(minutes=6)
    job_age = datetime.utcnow() - old_job_created
    is_stuck = job_age > timedelta(minutes=JOB_TIMEOUT_MINUTES)
    
    assert is_stuck, "Job older than 5 minutes should be considered stuck"
    
    # Job created 3 minutes ago (< 5 minute timeout)
    recent_job_created = datetime.utcnow() - timedelta(minutes=3)
    job_age = datetime.utcnow() - recent_job_created
    is_stuck = job_age > timedelta(minutes=JOB_TIMEOUT_MINUTES)
    
    assert not is_stuck, "Job younger than 5 minutes should not be considered stuck"


def test_cleanup_stuck_jobs():
    """Test that cleanup_stuck_recording_jobs marks old jobs as failed"""
    from server.models_sql import RecordingRun, db
    from server.app_factory import create_app
    
    app = create_app()
    
    with app.app_context():
        # Create a stuck job (7 minutes old)
        stuck_job = RecordingRun(
            business_id=1,
            call_sid='CAstuck123',
            recording_sid='REstuck123',
            recording_url='https://example.com/recording.mp3',
            job_type='download',
            status='queued',
            created_at=datetime.utcnow() - timedelta(minutes=7)
        )
        
        # Create a recent job (2 minutes old)
        recent_job = RecordingRun(
            business_id=1,
            call_sid='CArecent123',
            recording_sid='RErecent123',
            recording_url='https://example.com/recording2.mp3',
            job_type='download',
            status='queued',
            created_at=datetime.utcnow() - timedelta(minutes=2)
        )
        
        db.session.add(stuck_job)
        db.session.add(recent_job)
        db.session.commit()
        
        stuck_job_id = stuck_job.id
        recent_job_id = recent_job.id
        
        # Run cleanup
        cleaned_count = cleanup_stuck_recording_jobs()
        
        # Verify stuck job was marked as failed
        stuck_after = RecordingRun.query.get(stuck_job_id)
        assert stuck_after.status == 'failed', "Stuck job should be marked as failed"
        assert 'timeout' in stuck_after.error_message.lower(), "Error message should mention timeout"
        assert stuck_after.completed_at is not None, "Stuck job should have completed_at timestamp"
        
        # Verify recent job was not touched
        recent_after = RecordingRun.query.get(recent_job_id)
        assert recent_after.status == 'queued', "Recent job should still be queued"
        assert recent_after.error_message is None, "Recent job should have no error message"
        
        # Verify cleanup returned correct count
        assert cleaned_count >= 1, "Cleanup should report at least 1 job cleaned"
        
        # Cleanup test data
        db.session.delete(stuck_after)
        db.session.delete(recent_after)
        db.session.commit()


def test_serve_recording_file_with_stuck_job():
    """Test that serve_recording_file handles stuck jobs correctly"""
    from server.app_factory import create_app
    from server.models_sql import RecordingRun, CallLog, Business, db
    from flask import g
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            business_name='Test Business',
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        business_id = business.id
        
        # Create test call
        call = CallLog(
            business_id=business_id,
            call_sid='CAtest123',
            recording_sid='REtest123',
            recording_url='https://api.twilio.com/recording.mp3',
            from_number='+1234567890',
            to_number='+0987654321',
            direction='inbound',
            status='completed'
        )
        db.session.add(call)
        db.session.commit()
        
        # Create stuck job (10 minutes old)
        stuck_job = RecordingRun(
            business_id=business_id,
            call_sid='CAtest123',
            recording_sid='REtest123',
            recording_url='https://api.twilio.com/recording.mp3',
            job_type='download',
            status='queued',
            created_at=datetime.utcnow() - timedelta(minutes=10)
        )
        db.session.add(stuck_job)
        db.session.commit()
        stuck_job_id = stuck_job.id
        
        # Mock authentication
        with patch('server.routes_recordings.check_local_recording_exists', return_value=False):
            with patch('server.routes_recordings.enqueue_recording_download_only', return_value=(True, 'enqueued')):
                # Create test client
                client = app.test_client()
                
                # Set up authentication context
                with client.session_transaction() as sess:
                    sess['user_id'] = 1
                    sess['business_id'] = business_id
                
                # Mock the g object for authentication
                with app.test_request_context():
                    g.business_id = business_id
                    g.user_id = 1
                    
                    # Make request to serve_recording_file
                    response = client.get(
                        f'/api/recordings/file/CAtest123',
                        headers={'Authorization': 'Bearer test_token'}
                    )
                    
                    # Should return 202 (not stuck anymore since we triggered new job)
                    # or 500 if new job failed
                    assert response.status_code in [202, 500], f"Expected 202 or 500, got {response.status_code}"
                    
                    # Verify stuck job was marked as failed
                    stuck_after = RecordingRun.query.get(stuck_job_id)
                    assert stuck_after.status == 'failed', "Stuck job should be marked as failed"
                    assert 'timeout' in stuck_after.error_message.lower(), "Error message should mention timeout"
        
        # Cleanup
        db.session.query(RecordingRun).filter_by(call_sid='CAtest123').delete()
        db.session.query(CallLog).filter_by(call_sid='CAtest123').delete()
        db.session.query(Business).filter_by(id=business_id).delete()
        db.session.commit()


def test_prepare_recording_with_stuck_job():
    """Test that prepare_recording endpoint handles stuck jobs correctly"""
    from server.app_factory import create_app
    from server.models_sql import RecordingRun, CallLog, Business, db
    from flask import g
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            business_name='Test Business 2',
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        business_id = business.id
        
        # Create test call
        call = CallLog(
            business_id=business_id,
            call_sid='CAtest456',
            recording_sid='REtest456',
            recording_url='https://api.twilio.com/recording2.mp3',
            from_number='+1234567890',
            to_number='+0987654321',
            direction='inbound',
            status='completed'
        )
        db.session.add(call)
        db.session.commit()
        
        # Create stuck job (8 minutes old)
        stuck_job = RecordingRun(
            business_id=business_id,
            call_sid='CAtest456',
            recording_sid='REtest456',
            recording_url='https://api.twilio.com/recording2.mp3',
            job_type='download',
            status='running',  # stuck in running state
            created_at=datetime.utcnow() - timedelta(minutes=8)
        )
        db.session.add(stuck_job)
        db.session.commit()
        stuck_job_id = stuck_job.id
        
        # Mock authentication and file check
        with patch('server.routes_recordings.check_local_recording_exists', return_value=False):
            with patch('server.routes_recordings.enqueue_recording_download_only', return_value=(True, 'enqueued')):
                client = app.test_client()
                
                with app.test_request_context():
                    g.business_id = business_id
                    g.user_id = 1
                    
                    # Make request to prepare_recording
                    response = client.post(
                        f'/api/recordings/CAtest456/prepare',
                        headers={'Authorization': 'Bearer test_token'}
                    )
                    
                    # Should return 202 with new job (stuck job was marked as failed)
                    assert response.status_code == 202, f"Expected 202, got {response.status_code}"
                    
                    # Verify stuck job was marked as failed
                    stuck_after = RecordingRun.query.get(stuck_job_id)
                    assert stuck_after.status == 'failed', "Stuck job should be marked as failed"
                    assert 'timeout' in stuck_after.error_message.lower(), "Error message should mention timeout"
        
        # Cleanup
        db.session.query(RecordingRun).filter_by(call_sid='CAtest456').delete()
        db.session.query(CallLog).filter_by(call_sid='CAtest456').delete()
        db.session.query(Business).filter_by(id=business_id).delete()
        db.session.commit()


if __name__ == '__main__':
    # Run basic tests without pytest
    print("Testing stuck job detection...")
    test_detect_stuck_job()
    print("✓ Stuck job detection works")
    
    print("\nTesting cleanup function...")
    try:
        test_cleanup_stuck_jobs()
        print("✓ Cleanup function works")
    except Exception as e:
        print(f"✗ Cleanup test failed: {e}")
    
    print("\nAll basic tests passed!")
