#!/usr/bin/env python
"""
Test for _cancelled_response_ids AttributeError fix

This test verifies that:
1. _cancelled_response_ids is properly initialized in MediaStreamHandler.__init__
2. The attribute can be accessed without raising AttributeError
3. Basic set operations work correctly
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_cancelled_response_ids_initialization():
    """Test that _cancelled_response_ids is initialized in __init__"""
    # We need to mock the WebSocket object for initialization
    class MockWebSocket:
        def send(self, data):
            pass
    
    # Import the handler class
    from server.media_ws_ai import MediaStreamHandler
    
    # Create handler instance
    ws = MockWebSocket()
    handler = MediaStreamHandler(ws)
    
    # Test 1: Attribute exists
    assert hasattr(handler, '_cancelled_response_ids'), \
        "MediaStreamHandler should have _cancelled_response_ids attribute"
    
    # Test 2: Attribute is a set
    assert isinstance(handler._cancelled_response_ids, set), \
        "_cancelled_response_ids should be a set"
    
    # Test 3: Attribute is empty initially
    assert len(handler._cancelled_response_ids) == 0, \
        "_cancelled_response_ids should be empty initially"
    
    # Test 4: Can add items to the set
    test_id = "test_response_123"
    handler._cancelled_response_ids.add(test_id)
    assert test_id in handler._cancelled_response_ids, \
        "Should be able to add items to _cancelled_response_ids"
    
    # Test 5: Can check membership (the operation that was failing)
    test_id_2 = "test_response_456"
    assert test_id_2 not in handler._cancelled_response_ids, \
        "Should be able to check membership in _cancelled_response_ids"
    
    # Test 6: Can discard items
    handler._cancelled_response_ids.discard(test_id)
    assert test_id not in handler._cancelled_response_ids, \
        "Should be able to discard items from _cancelled_response_ids"
    
    print("✅ All tests passed!")
    print(f"   - _cancelled_response_ids is initialized as a set")
    print(f"   - Can add, check membership, and discard items")
    print(f"   - No AttributeError raised")
    
    return True

def test_related_attributes():
    """Test that related attributes are also initialized"""
    class MockWebSocket:
        def send(self, data):
            pass
    
    from server.media_ws_ai import MediaStreamHandler
    
    ws = MockWebSocket()
    handler = MediaStreamHandler(ws)
    
    # Test related attributes mentioned in the code
    assert hasattr(handler, '_cancelled_response_timestamps'), \
        "MediaStreamHandler should have _cancelled_response_timestamps"
    assert isinstance(handler._cancelled_response_timestamps, dict), \
        "_cancelled_response_timestamps should be a dict"
    
    assert hasattr(handler, '_cancelled_response_max_age_sec'), \
        "MediaStreamHandler should have _cancelled_response_max_age_sec"
    assert handler._cancelled_response_max_age_sec == 60, \
        "_cancelled_response_max_age_sec should be 60"
    
    assert hasattr(handler, '_cancelled_response_max_size'), \
        "MediaStreamHandler should have _cancelled_response_max_size"
    assert handler._cancelled_response_max_size == 100, \
        "_cancelled_response_max_size should be 100"
    
    print("✅ Related attributes test passed!")
    print(f"   - _cancelled_response_timestamps is a dict")
    print(f"   - _cancelled_response_max_age_sec = {handler._cancelled_response_max_age_sec}")
    print(f"   - _cancelled_response_max_size = {handler._cancelled_response_max_size}")
    
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Testing _cancelled_response_ids AttributeError Fix")
    print("=" * 70)
    print()
    
    try:
        # Run tests
        test_cancelled_response_ids_initialization()
        print()
        test_related_attributes()
        print()
        print("=" * 70)
        print("🎉 ALL TESTS PASSED - Fix is working correctly!")
        print("=" * 70)
        sys.exit(0)
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70)
        sys.exit(1)
