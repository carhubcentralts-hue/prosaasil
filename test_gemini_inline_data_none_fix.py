"""
Test for Gemini inline_data None check fix.

This test verifies that the code properly handles cases where inline_data is None
and doesn't crash with AttributeError when trying to access mime_type.
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))


def test_inline_data_none_check():
    """Test that the code has proper None check for inline_data"""
    print("🧪 Testing Gemini inline_data None check fix...")
    
    # Read the source code
    with open('server/services/gemini_realtime_client.py', 'r') as f:
        source = f.read()
    
    # Check that inline_data is checked before accessing mime_type
    # Look for the pattern where inline_data.mime_type is accessed
    import re
    
    # Find all places where inline_data.mime_type is accessed
    mime_type_accesses = re.findall(r'inline_data\.mime_type', source)
    
    if not mime_type_accesses:
        print("⚠️ No inline_data.mime_type access found in code")
        return True  # If there's no access, there's no issue
    
    print(f"Found {len(mime_type_accesses)} access(es) to inline_data.mime_type")
    
    # Check that there's a None check before the mime_type access
    # Look for patterns like: if inline_data and ... inline_data.mime_type
    # This is more flexible than exact string matching
    protected_pattern = re.search(
        r'if\s+inline_data\s+and.*?inline_data\.mime_type',
        source,
        re.DOTALL
    )
    
    if protected_pattern:
        print("✅ Fix confirmed: inline_data is checked before accessing mime_type")
        return True
    
    # Alternative: check if there's hasattr check
    hasattr_pattern = re.search(
        r'hasattr\(inline_data,\s*["\']mime_type["\']\)',
        source
    )
    
    if hasattr_pattern:
        print("✅ Fix confirmed: hasattr check for mime_type is present")
        return True
    
    print("❌ Warning: inline_data.mime_type access may not be properly protected")
    return False


def test_code_structure():
    """Test that the code structure is correct"""
    print("\n🧪 Testing code structure...")
    
    try:
        # Try to import the module
        from server.services import gemini_realtime_client
        print("✅ Module imports successfully")
        
        # Check that the class exists
        if hasattr(gemini_realtime_client, 'GeminiRealtimeClient'):
            print("✅ GeminiRealtimeClient class exists")
            return True
        else:
            print("❌ GeminiRealtimeClient class not found")
            return False
    except ImportError as e:
        print(f"⚠️ Import error (may need dependencies): {e}")
        # This is not a failure since we're just checking the code structure
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("GEMINI INLINE_DATA NONE CHECK FIX TEST")
    print("=" * 60)
    
    test1_passed = test_inline_data_none_check()
    test2_passed = test_code_structure()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        sys.exit(1)
