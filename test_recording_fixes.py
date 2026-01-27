#!/usr/bin/env python3
"""
Test script for recording fixes
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_service_worker_file():
    """Test that service worker file exists and has proper structure"""
    sw_path = os.path.join(os.path.dirname(__file__), 'client', 'public', 'sw.js')
    
    if not os.path.exists(sw_path):
        print("❌ Service worker file not found")
        return False
    
    with open(sw_path, 'r') as f:
        content = f.read()
    
    # Check for error handlers
    if "addEventListener('error'" not in content:
        print("❌ Service worker missing error handler")
        return False
    
    if "addEventListener('unhandledrejection'" not in content:
        print("❌ Service worker missing unhandledrejection handler")
        return False
    
    # Check for try-catch in handlers
    if "try {" not in content or "catch" not in content:
        print("❌ Service worker missing try-catch blocks")
        return False
    
    print("✅ Service worker has proper error handling")
    return True


def test_recordings_route():
    """Test that recordings route has auto-download logic"""
    route_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_recordings.py')
    
    if not os.path.exists(route_path):
        print("❌ Recordings route file not found")
        return False
    
    with open(route_path, 'r') as f:
        content = f.read()
    
    # Check for auto-download trigger
    if "enqueue_recording_download_only" not in content:
        print("❌ Recordings route missing auto-download logic")
        return False
    
    # Check for Hebrew error message
    if "בתהליך הורדה" not in content:
        print("❌ Recordings route missing Hebrew error message")
        return False
    
    # Check for RecordingRun status check
    if "existing_run = RecordingRun.query.filter" not in content:
        print("❌ Recordings route missing duplicate download check")
        return False
    
    print("✅ Recordings route has auto-download and proper error messages")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Recording and Service Worker Fixes")
    print("=" * 60)
    
    tests = [
        test_service_worker_file,
        test_recordings_route,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    print("=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
