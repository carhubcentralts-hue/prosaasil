#!/usr/bin/env python3
"""
Test for datetime import fix in gmail_sync_service.py
Verifies that the datetime module is properly accessible throughout the function
"""

import sys
import os
import re

def test_no_local_datetime_import():
    """
    Test that there's no local import of datetime that shadows the module import
    """
    print("=" * 80)
    print("TEST: No local datetime import in sync_gmail_receipts function")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for module-level datetime import
        has_module_import = False
        if re.search(r'^from datetime import datetime.*timedelta.*timezone', content, re.MULTILINE):
            has_module_import = True
            print("✅ Found module-level import: from datetime import datetime, timedelta, timezone")
        
        if not has_module_import:
            print("❌ Module-level datetime import NOT found")
            return False
        
        # Find the sync_gmail_receipts function
        match = re.search(r'def sync_gmail_receipts.*?(?=\ndef [a-z_]+|\Z)', content, re.DOTALL)
        if not match:
            print("❌ Could not find sync_gmail_receipts function")
            return False
        
        function_body = match.group(0)
        
        # Check for local import of datetime within the function
        local_import_pattern = r'^\s+from datetime import'
        if re.search(local_import_pattern, function_body, re.MULTILINE):
            print("❌ Found local datetime import inside sync_gmail_receipts function")
            print("   This will shadow the module-level import and cause UnboundLocalError")
            return False
        else:
            print("✅ No local datetime import found in sync_gmail_receipts function")
        
        # Check that datetime is used in the function
        datetime_usages = re.findall(r'datetime\.now\(', function_body)
        if datetime_usages:
            print(f"✅ Found {len(datetime_usages)} usages of datetime.now() in the function")
        else:
            print("⚠️  No usages of datetime.now() found")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - datetime import fix is correct")
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
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
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
    success = test_no_local_datetime_import() and success
    success = test_syntax_validity() and success
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 All Gmail sync datetime import tests passed!")
        print("=" * 80)
        print("\n✅ The fix is ready:")
        print("   - datetime is properly imported at module level")
        print("   - No local import shadowing the module import")
        print("   - All datetime.now() calls will now work correctly")
        print("   - No syntax errors detected")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
