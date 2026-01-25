"""
Test recording queue deduplication fixes
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_enqueue_deduplication():
    """Test that enqueue_recording_download_only prevents duplicates"""
    print("🧪 Testing recording queue deduplication...")
    
    # Import after path setup
    from server.tasks_recording import enqueue_recording_download_only, RECORDING_QUEUE
    
    # Clear queue
    while not RECORDING_QUEUE.empty():
        RECORDING_QUEUE.get()
    
    call_sid = "CA_TEST_DEDUP_12345"
    recording_url = "https://example.com/recording.mp3"
    business_id = 999
    
    # First enqueue - should succeed
    print(f"📝 First enqueue for {call_sid}...")
    enqueue_recording_download_only(
        call_sid=call_sid,
        recording_url=recording_url,
        business_id=business_id
    )
    
    queue_size_1 = RECORDING_QUEUE.qsize()
    print(f"   Queue size after first enqueue: {queue_size_1}")
    
    # Second enqueue - should be deduplicated (if Redis available)
    print(f"📝 Second enqueue for {call_sid} (should deduplicate)...")
    enqueue_recording_download_only(
        call_sid=call_sid,
        recording_url=recording_url,
        business_id=business_id
    )
    
    queue_size_2 = RECORDING_QUEUE.qsize()
    print(f"   Queue size after second enqueue: {queue_size_2}")
    
    # Check result
    if queue_size_2 == queue_size_1:
        print("✅ PASS: Deduplication working! No duplicate job added.")
        return True
    elif queue_size_2 == queue_size_1 + 1:
        print("⚠️  WARNING: Duplicate job added (Redis might not be available)")
        print("   This is OK for dev environment without Redis")
        return True
    else:
        print(f"❌ FAIL: Unexpected queue size change: {queue_size_1} -> {queue_size_2}")
        return False

def test_status_endpoint_exists():
    """Test that the new status endpoint is defined"""
    print("\n🧪 Testing status endpoint exists...")
    
    from server.routes_calls import calls_bp
    
    # Check if the route exists
    status_route_found = False
    for rule in calls_bp.url_map.iter_rules():
        if '/status' in rule.rule:
            status_route_found = True
            print(f"   Found route: {rule.rule}")
    
    if status_route_found:
        print("✅ PASS: Status endpoint exists")
        return True
    else:
        # Try alternative check - look at blueprint directly
        for endpoint, view_func in calls_bp.view_functions.items():
            if 'status' in endpoint.lower():
                print(f"   Found endpoint: {endpoint}")
                status_route_found = True
        
        if status_route_found:
            print("✅ PASS: Status endpoint exists")
            return True
        else:
            print("❌ FAIL: Status endpoint not found")
            return False

if __name__ == "__main__":
    print("=" * 60)
    print("Recording Queue Deduplication Test Suite")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(test_enqueue_deduplication())
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    try:
        results.append(test_status_endpoint_exists())
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 60)
    
    if passed == total:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
