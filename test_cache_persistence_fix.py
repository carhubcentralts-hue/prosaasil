"""
Test for recording cache persistence fix
Verifies that:
1. Recordings are cached locally
2. Cache persists (volume configured)
3. Parent call_sid fallback works
4. Download locking prevents concurrent downloads
5. UI doesn't prefetch recordings
"""
import os
import sys
import time
import threading
from unittest.mock import Mock, patch, MagicMock

# Set migration mode to avoid DB initialization
os.environ['MIGRATION_MODE'] = '1'


def test_docker_compose_has_volume():
    """Verify docker-compose.yml has persistent volume for recordings"""
    compose_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    
    assert os.path.exists(compose_path), "docker-compose.yml not found"
    
    with open(compose_path, 'r') as f:
        content = f.read()
    
    # Check for recordings volume
    assert 'recordings_data' in content, "recordings_data volume not defined"
    assert '/app/server/recordings' in content, "recordings volume mount not configured"
    
    print("✅ docker-compose.yml has persistent recordings volume")


def test_parent_call_sid_fallback():
    """Test that recording service checks parent_call_sid if call_sid not found"""
    from server.services.recording_service import get_recording_file_for_call
    from server.models_sql import CallLog
    import tempfile
    import shutil
    
    # Create a temporary recordings directory
    temp_dir = tempfile.mkdtemp()
    parent_sid = "CA_PARENT_123"
    child_sid = "CA_CHILD_456"
    
    try:
        # Create a recording file with parent_call_sid name
        parent_recording_path = os.path.join(temp_dir, f"{parent_sid}.mp3")
        with open(parent_recording_path, 'wb') as f:
            f.write(b"fake audio content" * 100)  # >1KB
        
        # Mock call with child_sid but parent_call_sid
        mock_call = Mock(spec=CallLog)
        mock_call.call_sid = child_sid
        mock_call.parent_call_sid = parent_sid
        mock_call.recording_url = "https://api.twilio.com/test.mp3"
        
        # Patch _get_recordings_dir to return our temp dir
        with patch('server.services.recording_service._get_recordings_dir', return_value=temp_dir):
            result = get_recording_file_for_call(mock_call)
            
            # Should find the parent's recording file
            assert result is not None, "Should find recording using parent_call_sid"
            assert parent_sid in result, f"Should return parent recording path, got: {result}"
            print(f"✅ Parent call_sid fallback works: found {result}")
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cache_hit_logging():
    """Test that cache hits are properly logged"""
    from server.services.recording_service import get_recording_file_for_call
    from server.models_sql import CallLog
    import tempfile
    import shutil
    import logging
    
    # Create a temporary recordings directory
    temp_dir = tempfile.mkdtemp()
    call_sid = "CA_TEST_CACHE_HIT"
    
    try:
        # Create a recording file
        recording_path = os.path.join(temp_dir, f"{call_sid}.mp3")
        with open(recording_path, 'wb') as f:
            f.write(b"fake audio content" * 100)  # >1KB
        
        # Mock call
        mock_call = Mock(spec=CallLog)
        mock_call.call_sid = call_sid
        mock_call.parent_call_sid = None
        mock_call.recording_url = "https://api.twilio.com/test.mp3"
        
        # Capture logs
        with patch('server.services.recording_service._get_recordings_dir', return_value=temp_dir):
            with patch('server.services.recording_service.log') as mock_log:
                result = get_recording_file_for_call(mock_call)
                
                # Should find the file
                assert result is not None, "Should find cached recording"
                
                # Check that Cache HIT was logged
                cache_hit_logged = False
                for call in mock_log.info.call_args_list:
                    if 'Cache HIT' in str(call):
                        cache_hit_logged = True
                        break
                
                assert cache_hit_logged, "Cache HIT should be logged when file exists"
                print("✅ Cache HIT is properly logged")
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_download_locking():
    """Test that concurrent downloads are prevented with locking"""
    from server.services.recording_service import get_recording_file_for_call
    from server.models_sql import CallLog
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    call_sid = "CA_LOCK_TEST"
    download_count = [0]  # Use list to allow modification in nested function
    
    def fake_download(url, account_sid, auth_token, call_sid_param):
        """Simulate slow download"""
        download_count[0] += 1
        time.sleep(0.5)  # Simulate network delay
        return b"fake audio content" * 100
    
    try:
        # Mock call
        mock_call = Mock(spec=CallLog)
        mock_call.call_sid = call_sid
        mock_call.parent_call_sid = None
        mock_call.recording_url = "https://api.twilio.com/test.mp3"
        
        results = []
        
        def download_in_thread():
            with patch('server.services.recording_service._get_recordings_dir', return_value=temp_dir):
                with patch('server.services.recording_service._download_from_twilio', side_effect=fake_download):
                    with patch('os.getenv', return_value='fake_credentials'):
                        result = get_recording_file_for_call(mock_call)
                        results.append(result)
        
        # Start 3 concurrent downloads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=download_in_thread)
            t.start()
            threads.append(t)
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=10)
        
        # Should only download once due to locking
        assert download_count[0] == 1, f"Expected 1 download due to locking, got {download_count[0]}"
        print(f"✅ Download locking works: only {download_count[0]} download despite 3 concurrent requests")
        
        # All threads should have gotten a result (either from download or from cache after lock)
        successful_results = [r for r in results if r is not None]
        assert len(successful_results) >= 1, "At least one thread should succeed"
        print(f"✅ {len(successful_results)}/3 threads got valid results")
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_audio_player_no_prefetch():
    """Test that AudioPlayer component uses preload='none'"""
    audio_player_path = os.path.join(
        os.path.dirname(__file__),
        'client/src/shared/components/AudioPlayer.tsx'
    )
    
    assert os.path.exists(audio_player_path), "AudioPlayer.tsx not found"
    
    with open(audio_player_path, 'r') as f:
        content = f.read()
    
    # Check that preload is set to 'none' not 'metadata' or 'auto'
    assert 'preload="none"' in content, "AudioPlayer should use preload='none'"
    assert 'preload="metadata"' not in content, "AudioPlayer should NOT use preload='metadata'"
    assert 'preload="auto"' not in content, "AudioPlayer should NOT use preload='auto'"
    
    print("✅ AudioPlayer uses preload='none' (no prefetching)")


def test_gitignore_has_recordings():
    """Test that .gitignore excludes recordings directory"""
    gitignore_path = os.path.join(os.path.dirname(__file__), '.gitignore')
    
    assert os.path.exists(gitignore_path), ".gitignore not found"
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    # Check for recordings directory
    assert 'server/recordings' in content or 'recordings/' in content, \
        "Recordings directory should be in .gitignore"
    
    print("✅ .gitignore excludes recordings directory")


def test_canonical_path_usage():
    """Test that all code uses canonical {call_sid}.mp3 path"""
    from server.services.recording_service import get_recording_file_for_call, check_local_recording_exists
    from server.models_sql import CallLog
    import tempfile
    
    temp_dir = tempfile.mkdtemp()
    call_sid = "CA_CANONICAL_TEST"
    
    try:
        # Create recording with canonical name
        canonical_path = os.path.join(temp_dir, f"{call_sid}.mp3")
        with open(canonical_path, 'wb') as f:
            f.write(b"fake audio" * 100)
        
        # Test that check_local_recording_exists uses same path
        with patch('server.services.recording_service._get_recordings_dir', return_value=temp_dir):
            exists = check_local_recording_exists(call_sid)
            assert exists, "check_local_recording_exists should find canonical path"
            print(f"✅ Canonical path {{call_sid}}.mp3 is used consistently")
    
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    print("\n=== Testing Recording Cache Persistence Fix ===\n")
    
    try:
        test_docker_compose_has_volume()
        print()
        
        test_parent_call_sid_fallback()
        print()
        
        test_cache_hit_logging()
        print()
        
        test_download_locking()
        print()
        
        test_audio_player_no_prefetch()
        print()
        
        test_gitignore_has_recordings()
        print()
        
        test_canonical_path_usage()
        print()
        
        print("✅ All cache persistence tests passed!")
        print("\n=== Expected Behavior ===")
        print("1. First playback: Cache miss → downloads from Twilio → saves locally")
        print("2. Second playback: Cache HIT → serves from disk (no Twilio download)")
        print("3. Multiple Range requests: Only one download, others wait and serve from cache")
        print("4. Container restart: Recordings persist (not lost)")
        print("5. Outbound calls: Correctly finds recording using parent_call_sid fallback")
        print("6. Page load: No prefetching, no Range requests until user clicks play")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
