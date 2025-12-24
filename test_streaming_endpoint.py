"""
Test for new recording streaming endpoint with 202 handling
"""
import os
import sys

# Set migration mode to avoid DB initialization
os.environ['MIGRATION_MODE'] = '1'


def test_streaming_endpoint_exists():
    """Verify the streaming endpoint is registered"""
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all registered routes
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    
    # Check that streaming endpoint exists
    stream_route = '/api/recordings/<call_sid>/stream'
    
    # Find matching route
    matching_routes = [r for r in routes if 'stream' in r and '/api/recordings/' in r]
    
    assert len(matching_routes) > 0, f"Streaming endpoint not found. Available routes: {[r for r in routes if 'recordings' in r or 'calls' in r]}"
    print(f"✅ Streaming endpoint found: {matching_routes}")


def test_check_local_recording_function():
    """Verify check_local_recording_exists function works"""
    from server.services.recording_service import check_local_recording_exists
    
    # Should return False for non-existent recording
    result = check_local_recording_exists("NONEXISTENT_CALL_SID")
    assert result == False, "Should return False for non-existent recording"
    print("✅ check_local_recording_exists works correctly")


def test_recording_service_imports():
    """Verify recording service can be imported in routes"""
    try:
        from server.services.recording_service import check_local_recording_exists, _get_recordings_dir
        print("✅ Recording service functions can be imported")
        
        # Test that _get_recordings_dir returns a valid path
        recordings_dir = _get_recordings_dir()
        assert isinstance(recordings_dir, str), "recordings_dir should be a string"
        assert len(recordings_dir) > 0, "recordings_dir should not be empty"
        print(f"✅ _get_recordings_dir returns: {recordings_dir}")
        
    except ImportError as e:
        raise AssertionError(f"Failed to import recording service functions: {e}")


def test_enqueue_recording_job_function():
    """Verify enqueue_recording_job can be imported and called"""
    from server.tasks_recording import enqueue_recording_job, RECORDING_QUEUE
    
    # Queue should be empty initially
    initial_size = RECORDING_QUEUE.qsize()
    
    # Enqueue a test job
    enqueue_recording_job(
        call_sid="TEST_SID",
        recording_url="https://api.twilio.com/test.mp3",
        business_id=1,
        from_number="+1234567890",
        to_number="+0987654321",
        retry_count=0
    )
    
    # Queue should have one more item
    final_size = RECORDING_QUEUE.qsize()
    assert final_size == initial_size + 1, f"Queue should have {initial_size + 1} items, has {final_size}"
    
    # Clean up by removing the test job
    RECORDING_QUEUE.get()
    RECORDING_QUEUE.task_done()
    
    print("✅ enqueue_recording_job works correctly")


if __name__ == '__main__':
    print("\n=== Testing Recording Streaming Endpoint ===\n")
    
    try:
        test_streaming_endpoint_exists()
        print()
        test_check_local_recording_function()
        print()
        test_recording_service_imports()
        print()
        test_enqueue_recording_job_function()
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
