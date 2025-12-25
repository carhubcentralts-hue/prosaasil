"""
Test for recording download deduplication
Verifies that duplicate enqueue requests are properly handled
"""
import os
import sys
import time
from unittest.mock import Mock, patch, MagicMock

# Set migration mode to avoid DB initialization
os.environ['MIGRATION_MODE'] = '1'


def test_deduplication_prevents_duplicate_enqueue():
    """Test that deduplication prevents duplicate job enqueues"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE, _last_enqueue_time
    
    # Clear queue and tracking
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    _last_enqueue_time.clear()
    
    # Mock the recording service functions
    with patch('server.services.recording_service.check_local_recording_exists', return_value=False):
        with patch('server.services.recording_service.is_download_in_progress', return_value=False):
            
            # First enqueue should succeed
            enqueue_recording_download_only(
                call_sid="TEST_CALL_1",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should have 1 item
            assert RECORDING_QUEUE.qsize() == 1, "First enqueue should add to queue"
            
            # Second enqueue (immediate) should be blocked by cooldown
            enqueue_recording_download_only(
                call_sid="TEST_CALL_1",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should still have only 1 item (duplicate blocked)
            assert RECORDING_QUEUE.qsize() == 1, "Duplicate enqueue should be blocked by cooldown"
            
            print("✅ Deduplication prevents duplicate enqueue")


def test_deduplication_respects_cached_files():
    """Test that deduplication skips enqueue if file is already cached"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE, _last_enqueue_time
    
    # Clear queue and tracking
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    _last_enqueue_time.clear()
    
    # Mock the recording service to say file is cached
    with patch('server.services.recording_service.check_local_recording_exists', return_value=True):
        with patch('server.services.recording_service.is_download_in_progress', return_value=False):
            
            # Enqueue should be skipped
            enqueue_recording_download_only(
                call_sid="TEST_CALL_CACHED",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should be empty (enqueue skipped)
            assert RECORDING_QUEUE.qsize() == 0, "Enqueue should be skipped for cached files"
            
            print("✅ Deduplication respects cached files")


def test_deduplication_respects_in_progress():
    """Test that deduplication skips enqueue if download is in progress"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE, _last_enqueue_time
    
    # Clear queue and tracking
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    _last_enqueue_time.clear()
    
    # Mock the recording service to say download is in progress
    with patch('server.services.recording_service.check_local_recording_exists', return_value=False):
        with patch('server.services.recording_service.is_download_in_progress', return_value=True):
            
            # Enqueue should be skipped
            enqueue_recording_download_only(
                call_sid="TEST_CALL_IN_PROGRESS",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should be empty (enqueue skipped)
            assert RECORDING_QUEUE.qsize() == 0, "Enqueue should be skipped for in-progress downloads"
            
            print("✅ Deduplication respects in-progress downloads")


def test_cooldown_expires_after_timeout():
    """Test that cooldown expires after the configured timeout"""
    from server.tasks_recording import (
        enqueue_recording_download_only, 
        RECORDING_QUEUE, 
        _last_enqueue_time,
        ENQUEUE_COOLDOWN_SECONDS
    )
    
    # Clear queue and tracking
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    _last_enqueue_time.clear()
    
    # Mock the recording service functions
    with patch('server.services.recording_service.check_local_recording_exists', return_value=False):
        with patch('server.services.recording_service.is_download_in_progress', return_value=False):
            
            # First enqueue
            enqueue_recording_download_only(
                call_sid="TEST_CALL_COOLDOWN",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should have 1 item
            assert RECORDING_QUEUE.qsize() == 1, "First enqueue should add to queue"
            
            # Manually expire the cooldown by setting timestamp to past
            _last_enqueue_time["TEST_CALL_COOLDOWN"] = time.time() - ENQUEUE_COOLDOWN_SECONDS - 1
            
            # Second enqueue should now succeed (cooldown expired)
            enqueue_recording_download_only(
                call_sid="TEST_CALL_COOLDOWN",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should have 2 items now
            assert RECORDING_QUEUE.qsize() == 2, "Second enqueue should succeed after cooldown expires"
            
            print("✅ Cooldown expires after timeout")


def test_different_call_sids_not_blocked():
    """Test that different call_sids are not blocked by each other"""
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE, _last_enqueue_time
    
    # Clear queue and tracking
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    _last_enqueue_time.clear()
    
    # Mock the recording service functions
    with patch('server.services.recording_service.check_local_recording_exists', return_value=False):
        with patch('server.services.recording_service.is_download_in_progress', return_value=False):
            
            # Enqueue first call
            enqueue_recording_download_only(
                call_sid="TEST_CALL_A",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Enqueue second call (different SID)
            enqueue_recording_download_only(
                call_sid="TEST_CALL_B",
                recording_url="https://test.com/recording.mp3",
                business_id=1,
                from_number="+1234567890",
                to_number="+0987654321"
            )
            
            # Queue should have 2 items (different call_sids not blocked)
            assert RECORDING_QUEUE.qsize() == 2, "Different call_sids should not block each other"
            
            print("✅ Different call_sids are not blocked by each other")


def test_recording_service_stale_cleanup():
    """Test that recording service cleans up stale download markers"""
    from server.services.recording_service import (
        mark_download_started,
        is_download_in_progress,
        _download_in_progress,
        _download_start_time,
        DOWNLOAD_STALE_TIMEOUT
    )
    
    # Clear state
    _download_in_progress.clear()
    _download_start_time.clear()
    
    # Mark a download as started
    assert mark_download_started("TEST_STALE"), "Should mark download as started"
    assert is_download_in_progress("TEST_STALE"), "Download should be in progress"
    
    # Manually set start time to past (simulate stale download)
    _download_start_time["TEST_STALE"] = time.time() - DOWNLOAD_STALE_TIMEOUT - 1
    
    # Check should clean up stale entry
    assert not is_download_in_progress("TEST_STALE"), "Stale download should be cleaned up"
    
    print("✅ Recording service cleans up stale download markers")


if __name__ == '__main__':
    print("\n=== Testing Recording Download Deduplication ===\n")
    
    try:
        test_deduplication_prevents_duplicate_enqueue()
        print()
        test_deduplication_respects_cached_files()
        print()
        test_deduplication_respects_in_progress()
        print()
        test_cooldown_expires_after_timeout()
        print()
        test_different_call_sids_not_blocked()
        print()
        test_recording_service_stale_cleanup()
        print()
        print("✅ All deduplication tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
