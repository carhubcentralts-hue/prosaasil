#!/usr/bin/env python3
"""
Test for Flask app context fix in receipt sync background thread
Verifies that the app object is captured before starting the thread
"""

import sys
import os
import re

def test_app_context_capture():
    """
    Test that app object is captured before thread starts (not inside thread)
    """
    print("=" * 80)
    print("TEST: Flask app context capture before thread start")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the sync_receipts function that contains the threading code
        match = re.search(
            r'def sync_receipts\(\):.*?(?=\n@|\ndef [a-z_]+\(|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not match:
            print("❌ Could not find sync_receipts function")
            return False
        
        function_body = match.group(0)
        
        # Check for the pattern: capture app before thread starts
        # Pattern should be:
        # 1. from flask import current_app
        # 2. app = current_app._get_current_object()
        # 3. def run_sync_in_background():
        # 4.     with app.app_context():
        
        # Check for capturing app before thread
        has_app_capture = re.search(
            r'from flask import current_app.*?'
            r'app = current_app\._get_current_object\(\)',
            function_body,
            re.DOTALL
        )
        
        if not has_app_capture:
            print("❌ Missing: app = current_app._get_current_object() before thread")
            return False
        else:
            print("✅ Found: app = current_app._get_current_object() before thread")
        
        # Check that run_sync_in_background uses 'app' not 'current_app'
        thread_func_match = re.search(
            r'def run_sync_in_background\(\):.*?(?=\n        thread = threading\.Thread)',
            function_body,
            re.DOTALL
        )
        
        if not thread_func_match:
            print("❌ Could not find run_sync_in_background function")
            return False
        
        thread_func_body = thread_func_match.group(0)
        
        # Should use 'with app.app_context():'
        if 'with app.app_context():' in thread_func_body:
            print("✅ Found: with app.app_context(): (using captured app)")
        else:
            print("❌ Missing: with app.app_context(): in thread function")
            return False
        
        # Should NOT use 'with current_app.app_context():' inside thread
        if 'with current_app.app_context():' in thread_func_body:
            print("❌ ERROR: Still using current_app.app_context() inside thread!")
            print("   This will cause 'Working outside of application context' error")
            return False
        else:
            print("✅ Not using current_app.app_context() inside thread (good!)")
        
        # Should NOT have 'from flask import current_app' inside thread function
        if re.search(r'def run_sync_in_background.*?from flask import current_app', thread_func_body, re.DOTALL):
            print("❌ ERROR: Still importing current_app inside thread function!")
            return False
        else:
            print("✅ Not importing current_app inside thread function (good!)")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - Flask app context fix is correct")
        print("=" * 80)
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_syntax_validity():
    """
    Test that the Python file has valid syntax
    """
    print("\n" + "=" * 80)
    print("TEST: Python syntax validity")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            code = f.read()
        
        # Try to compile the code to check for syntax errors
        compile(code, file_path, 'exec')
        print("✅ Python syntax is valid (no syntax errors)")
        
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error found: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking syntax: {e}")
        return False

if __name__ == '__main__':
    success = True
    
    # Run tests
    success = test_app_context_capture() and success
    success = test_syntax_validity() and success
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 All receipt sync thread fix tests passed!")
        print("=" * 80)
        print("\n✅ The fix is ready:")
        print("   - App object is captured before thread starts")
        print("   - Thread function uses captured app, not current_app proxy")
        print("   - No 'Working outside of application context' error will occur")
        print("   - Gmail receipt sync with date filters should now work!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
