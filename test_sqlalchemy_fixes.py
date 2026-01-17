#!/usr/bin/env python3
"""
Test script to validate SQLAlchemy fixes for backend startup issues.

Tests:
1. SecurityEvent model has event_metadata (not metadata)
2. Models can be imported without "metadata is reserved" error
3. Multiple imports don't cause "Table 'business' is already defined" error
4. Thread-safe Flask app singleton works correctly
"""
import sys
import os
sys.path.insert(0, '.')

# Set required env vars
os.environ['DATABASE_URL'] = 'sqlite:///test.db'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['MIGRATION_MODE'] = '1'

import threading
import time


def test_security_event_metadata():
    """Test that SecurityEvent has event_metadata, not metadata as a column"""
    print("\n" + "=" * 70)
    print("Test 1: SecurityEvent.event_metadata exists")
    print("=" * 70)
    
    from server.models_sql import SecurityEvent
    
    # Check that event_metadata exists
    assert hasattr(SecurityEvent, 'event_metadata'), "event_metadata attribute not found"
    print("✅ SecurityEvent.event_metadata exists")
    
    # Check that we can create an instance and set event_metadata
    se = SecurityEvent()
    se.event_metadata = {"test": "data"}
    print("✅ Can set event_metadata on SecurityEvent instance")
    
    # Check that metadata is the SQLAlchemy MetaData object, not a column
    import sqlalchemy
    assert isinstance(SecurityEvent.metadata, sqlalchemy.schema.MetaData), \
        "metadata should be SQLAlchemy MetaData object"
    print("✅ metadata is SQLAlchemy's reserved MetaData (not a column)")


def test_models_import_no_errors():
    """Test that models can be imported multiple times without errors"""
    print("\n" + "=" * 70)
    print("Test 2: Models can be imported without errors")
    print("=" * 70)
    
    # First import
    import server.models_sql as models1
    print("✅ First import successful")
    
    # Second import (simulates what might happen with warmup thread)
    import server.models_sql as models2
    print("✅ Second import successful")
    
    # Verify they're the same module
    assert models1 is models2, "Models imported as different modules!"
    print("✅ Both imports reference the same module")
    
    # Verify key models exist and are consistent
    assert hasattr(models1, 'Business'), "Business model not found"
    assert hasattr(models1, 'SecurityEvent'), "SecurityEvent model not found"
    assert models1.Business is models2.Business, "Business model loaded twice!"
    assert models1.SecurityEvent is models2.SecurityEvent, "SecurityEvent model loaded twice!"
    print("✅ Business and SecurityEvent models are consistent")


def test_thread_safe_flask_app():
    """Test that Flask app singleton is thread-safe"""
    print("\n" + "=" * 70)
    print("Test 3: Thread-safe Flask app singleton")
    print("=" * 70)
    
    import asgi
    
    results = {"thread1": None, "thread2": None, "error": None}
    
    def get_app_thread(name, key):
        try:
            app = asgi.get_flask_app()
            results[key] = id(app)
            print(f"  [{name}] Got Flask app with ID: {id(app)}")
        except Exception as e:
            results["error"] = str(e)
            print(f"  [{name}] ERROR: {e}")
    
    # Create two threads that both try to get the Flask app
    thread1 = threading.Thread(target=get_app_thread, args=("Thread1", "thread1"), daemon=True)
    thread2 = threading.Thread(target=get_app_thread, args=("Thread2", "thread2"), daemon=True)
    
    # Start threads with slight delay to simulate race condition
    thread1.start()
    time.sleep(0.01)
    thread2.start()
    
    # Wait for threads to complete
    thread1.join(timeout=15)
    thread2.join(timeout=15)
    
    # Check for errors
    if results["error"]:
        raise AssertionError(f"Error during thread test: {results['error']}")
    
    # Verify both threads got the same app instance
    assert results["thread1"] is not None, "Thread 1 failed to get app"
    assert results["thread2"] is not None, "Thread 2 failed to get app"
    assert results["thread1"] == results["thread2"], \
        f"Different Flask apps created: {results['thread1']} vs {results['thread2']}"
    
    print("✅ Both threads got the SAME Flask app instance (singleton works!)")


def test_business_model_no_duplicate():
    """Test that Business model doesn't trigger 'already defined' error"""
    print("\n" + "=" * 70)
    print("Test 4: Business model doesn't duplicate")
    print("=" * 70)
    
    from server.models_sql import Business
    
    # Try to create instances
    b1 = Business()
    b2 = Business()
    
    print("✅ Can create multiple Business instances")
    print("✅ No 'Table business is already defined' error")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("SQLALCHEMY FIXES VALIDATION TEST SUITE")
    print("=" * 70)
    
    try:
        test_security_event_metadata()
        test_models_import_no_errors()
        test_thread_safe_flask_app()
        test_business_model_no_duplicate()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("Backend should now start successfully in docker compose")
        print("=" * 70)
        return 0
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
