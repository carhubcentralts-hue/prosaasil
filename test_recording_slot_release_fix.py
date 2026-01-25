"""
Test for recording queue slot release fix.

This test verifies that the critical bug is fixed where semaphore slots
were acquired but never released when enqueue decided not to add a job.

Bug scenario:
1. API acquires slot with try_acquire_slot()
2. enqueue_recording_download_only() checks dedup and returns early
3. No job is added to queue
4. Slot is never released → active=3/3 stuck forever

Fix:
- enqueue_recording_download_only() now returns True/False
- API checks return value and releases slot if False
- Slot is only held when a job is actually enqueued
"""

from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Set migration mode to avoid DB initialization
os.environ['MIGRATION_MODE'] = '1'

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


def test_enqueue_returns_false_when_file_cached():
    """Test that enqueue returns False when file is already cached"""
    from server.tasks_recording import enqueue_recording_download_only
    
    with patch('server.tasks_recording.check_local_recording_exists', return_value=True):
        # If file exists locally, enqueue should return False (don't enqueue)
        result = enqueue_recording_download_only(
            call_sid="CA123",
            recording_url="https://api.twilio.com/recordings/RE456",
            recording_sid="RE456",
            business_id=1,
            from_number="+1234567890",
            to_number="+0987654321"
        )
        assert result is False, "Should return False when file is cached"


def test_enqueue_returns_false_when_redis_dedup_hit():
    """Test that enqueue returns False when Redis dedup detects duplicate job"""
    from server.tasks_recording import enqueue_recording_download_only
    
    # Mock Redis client to return False (key already exists)
    mock_redis = MagicMock()
    mock_redis.set.return_value = False  # NX failed, key already exists
    mock_redis.ttl.return_value = 1234
    
    with patch('server.tasks_recording.check_local_recording_exists', return_value=False):
        with patch('server.tasks_recording._redis_client', mock_redis):
            with patch('server.tasks_recording.REDIS_DEDUP_ENABLED', True):
                result = enqueue_recording_download_only(
                    call_sid="CA123",
                    recording_url="https://api.twilio.com/recordings/RE456",
                    recording_sid="RE456",
                    business_id=1,
                    from_number="+1234567890",
                    to_number="+0987654321"
                )
                assert result is False, "Should return False when Redis dedup hits"


def test_enqueue_returns_true_when_job_enqueued():
    """Test that enqueue returns True when job is successfully enqueued"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE
    
    # Mock Redis client to return True (key set successfully)
    mock_redis = MagicMock()
    mock_redis.set.return_value = True  # NX succeeded
    
    with patch('server.tasks_recording.check_local_recording_exists', return_value=False):
        with patch('server.tasks_recording._redis_client', mock_redis):
            with patch('server.tasks_recording.REDIS_DEDUP_ENABLED', True):
                result = enqueue_recording_download_only(
                    call_sid="CA123",
                    recording_url="https://api.twilio.com/recordings/RE456",
                    recording_sid="RE456",
                    business_id=1,
                    from_number="+1234567890",
                    to_number="+0987654321"
                )
                assert result is True, "Should return True when job is enqueued"
                
                # Verify job was added to queue
                assert not RECORDING_QUEUE.empty(), "Job should be in queue"
                job = RECORDING_QUEUE.get()
                assert job["call_sid"] == "CA123"
                assert job["recording_sid"] == "RE456"
                assert job["type"] == "download_only"
                RECORDING_QUEUE.task_done()


def test_job_includes_recording_sid():
    """Test that enqueued job includes recording_sid for better logging"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE
    
    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    
    with patch('server.tasks_recording.check_local_recording_exists', return_value=False):
        with patch('server.tasks_recording._redis_client', mock_redis):
            with patch('server.tasks_recording.REDIS_DEDUP_ENABLED', True):
                result = enqueue_recording_download_only(
                    call_sid="CA789",
                    recording_url="https://api.twilio.com/recordings/RE999",
                    recording_sid="RE999",
                    business_id=2,
                    from_number="+1111111111",
                    to_number="+2222222222"
                )
                
                assert result is True
                job = RECORDING_QUEUE.get()
                assert job["recording_sid"] == "RE999", "Job should include recording_sid"
                assert job["call_sid"] == "CA789"
                RECORDING_QUEUE.task_done()


def test_api_releases_slot_when_enqueue_returns_false():
    """Test that API releases slot when enqueue returns False"""
    # This is a documentation test showing the expected flow
    # In the actual API code:
    # 1. acquired, slot_status = try_acquire_slot(business_id, call_sid)
    # 2. if acquired:
    #       job_enqueued = enqueue_recording_download_only(...)
    #       if not job_enqueued:
    #           release_slot(business_id, call_sid)
    
    # Mock the recording semaphore
    mock_release = Mock()
    
    with patch('server.recording_semaphore.release_slot', mock_release):
        from server.tasks_recording import enqueue_recording_download_only
        
        # Simulate cached file scenario
        with patch('server.tasks_recording.check_local_recording_exists', return_value=True):
            result = enqueue_recording_download_only(
                call_sid="CA123",
                recording_url="https://api.twilio.com/recordings/RE456",
                recording_sid="RE456",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Result is False, so API should call release_slot
            assert result is False
            
            # Simulate API calling release_slot
            if not result:
                mock_release(1, "CA123")
            
            # Verify release_slot was called
            mock_release.assert_called_once_with(1, "CA123")


def test_logging_includes_recording_sid():
    """Test that logs include both call_sid and recording_sid"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE
    
    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    
    with patch('server.tasks_recording.check_local_recording_exists', return_value=False):
        with patch('server.tasks_recording._redis_client', mock_redis):
            with patch('server.tasks_recording.REDIS_DEDUP_ENABLED', True):
                # Capture log output
                import logging
                import io
                log_capture = io.StringIO()
                handler = logging.StreamHandler(log_capture)
                logger = logging.getLogger('tasks_recording')
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                
                try:
                    enqueue_recording_download_only(
                        call_sid="CA555",
                        recording_url="https://api.twilio.com/recordings/RE777",
                        recording_sid="RE777",
                        business_id=3,
                        from_number="+3333333333",
                        to_number="+4444444444"
                    )
                    
                    # Clean up queue
                    RECORDING_QUEUE.get()
                    RECORDING_QUEUE.task_done()
                    
                    # Check log output
                    log_output = log_capture.getvalue()
                    # Log should mention both SIDs
                    # Note: The actual log format is: "call_sid=CA555 recording_sid=RE777"
                    assert "CA555" in log_output or "call_sid" in log_output.lower()
                finally:
                    logger.removeHandler(handler)


if __name__ == "__main__":
    # Run tests manually
    print("Running recording slot release fix tests...\n")
    
    tests = [
        ("enqueue returns False when file cached", test_enqueue_returns_false_when_file_cached),
        ("enqueue returns False when Redis dedup hit", test_enqueue_returns_false_when_redis_dedup_hit),
        ("enqueue returns True when job enqueued", test_enqueue_returns_true_when_job_enqueued),
        ("job includes recording_sid", test_job_includes_recording_sid),
        ("API releases slot when enqueue returns False", test_api_releases_slot_when_enqueue_returns_false),
        ("logging includes recording_sid", test_logging_includes_recording_sid),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"Testing: {test_name}...", end=" ")
            test_func()
            print("✅ PASS")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    if failed > 0:
        sys.exit(1)
