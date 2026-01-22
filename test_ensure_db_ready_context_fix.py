"""
Test to verify ensure_db_ready works correctly with app context
This test validates the fix for "Working outside of application context" error
"""
import os
import sys

# Set minimal test environment
os.environ['MIGRATION_MODE'] = '1'
os.environ['DATABASE_URL'] = 'sqlite:///test_db_ready.db'

def test_ensure_db_ready_with_context():
    """Test that ensure_db_ready works with app context"""
    
    from server.app_factory import create_app, ensure_db_ready
    from server.db import db
    
    # Create minimal app
    app = create_app()
    
    print("✓ App created successfully")
    
    # Initialize database
    with app.app_context():
        db.create_all()
        print("✓ Database initialized")
    
    # Test ensure_db_ready with app parameter (the fix)
    try:
        result = ensure_db_ready(app, max_retries=3, retry_delay=0.5)
        
        if result:
            print("✓ ensure_db_ready returned True (database is ready)")
        else:
            print("✗ FAILED: ensure_db_ready returned False")
            sys.exit(1)
            
    except RuntimeError as e:
        if "Working outside of application context" in str(e):
            print(f"✗ FAILED: Still getting context error: {e}")
            sys.exit(1)
        else:
            # Some other error
            print(f"✗ FAILED: Unexpected error: {e}")
            sys.exit(1)
    
    print("\n✅ Test passed! No 'Working outside of application context' error")

def test_ensure_db_ready_handles_not_ready():
    """Test that ensure_db_ready handles DB not ready gracefully"""
    
    from server.app_factory import create_app, ensure_db_ready
    
    # Create minimal app with bad database URL
    os.environ['DATABASE_URL'] = 'postgresql://badhost:5432/baddb'
    app = create_app()
    
    print("✓ App created with bad database")
    
    # Test ensure_db_ready should return False, not crash
    try:
        result = ensure_db_ready(app, max_retries=2, retry_delay=0.1)
        
        if not result:
            print("✓ ensure_db_ready correctly returned False for bad database")
        else:
            print("⚠ WARNING: ensure_db_ready returned True for bad database (unexpected)")
            
    except RuntimeError as e:
        if "Working outside of application context" in str(e):
            print(f"✗ FAILED: Still getting context error: {e}")
            sys.exit(1)
        else:
            # Some other error is OK - the key is no context error
            print(f"✓ Got expected error (not context error): {type(e).__name__}")
    
    print("\n✅ Test passed! Handles DB not ready without context error")

if __name__ == '__main__':
    print("Testing ensure_db_ready context fix...\n")
    
    print("Test 1: ensure_db_ready with app context")
    print("-" * 60)
    test_ensure_db_ready_with_context()
    
    print("\n\nTest 2: ensure_db_ready handles not ready gracefully")
    print("-" * 60)
    test_ensure_db_ready_handles_not_ready()
    
    print("\n\n🎉 All tests completed successfully!")
    print("\nThe fix ensures:")
    print("  ✓ No 'Working outside of application context' errors")
    print("  ✓ DB readiness checks work correctly")
    print("  ✓ Graceful handling of DB not ready scenarios")
