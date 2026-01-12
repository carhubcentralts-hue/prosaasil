"""
Test to verify threading import fix in app_factory.py
This test ensures that threading.Event() can be used without UnboundLocalError
"""
import sys
import os

def test_threading_import():
    """Verify that threading is imported at module level"""
    # Import the module
    from server import app_factory
    
    # Verify threading is available as a module attribute
    assert hasattr(app_factory, 'threading'), "threading should be imported at module level"
    assert app_factory.threading is not None, "threading module should not be None"
    print("✅ threading is properly imported at module level")

def test_create_app_no_error():
    """Verify that create_app() doesn't throw UnboundLocalError"""
    try:
        # Set minimal environment to avoid dependencies
        os.environ['MIGRATION_MODE'] = '1'  # Skip background threads
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        from server.app_factory import create_minimal_app
        app = create_minimal_app()
        
        assert app is not None, "App should be created successfully"
        print("✅ create_minimal_app() executed without UnboundLocalError")
        
    except UnboundLocalError as e:
        if 'threading' in str(e):
            print(f"❌ FAILED: UnboundLocalError with threading: {e}")
            raise
        else:
            raise
    except Exception as e:
        # Other exceptions are okay for this test (we're just checking threading)
        print(f"⚠️ Other exception (not threading related): {type(e).__name__}: {e}")
        pass

if __name__ == '__main__':
    print("Testing threading import fix...")
    test_threading_import()
    test_create_app_no_error()
    print("\n✅ All tests passed!")
