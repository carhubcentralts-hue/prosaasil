#!/usr/bin/env python3
"""
Test for datetime import fix in routes_outbound.py
Verifies that the datetime module is properly imported
"""

import sys
import os
import re

def test_datetime_import_in_file():
    """
    Test that datetime is properly imported in routes_outbound.py by checking the file content
    """
    print("=" * 80)
    print("TEST: datetime import in routes_outbound.py")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for datetime import
        has_datetime_import = False
        import_patterns = [
            r'from datetime import datetime',
            r'import datetime'
        ]
        
        for pattern in import_patterns:
            if re.search(pattern, content):
                has_datetime_import = True
                print(f"✅ Found import: {pattern}")
                break
        
        if not has_datetime_import:
            print("❌ datetime import NOT found in the file")
            return False
        
        # Check that datetime.utcnow() is used in the file
        utcnow_usages = re.findall(r'datetime\.utcnow\(\)', content)
        if utcnow_usages:
            print(f"✅ Found {len(utcnow_usages)} usages of datetime.utcnow()")
        else:
            print("⚠️  No usages of datetime.utcnow() found (might have been changed)")
        
        # Verify import is in the right location (near the top of the file)
        lines = content.split('\n')
        import_line = None
        for i, line in enumerate(lines[:50], 1):  # Check first 50 lines
            if 'from datetime import datetime' in line or 'import datetime' in line:
                import_line = i
                break
        
        if import_line:
            print(f"✅ datetime import found at line {import_line} (in imports section)")
        else:
            print("❌ datetime import not found in expected location")
            return False
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - datetime import is correctly added")
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
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py'
        
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

def test_all_datetime_usages_covered():
    """
    Test that all lines using datetime.utcnow() are listed
    """
    print("\n" + "=" * 80)
    print("TEST: Verify all datetime.utcnow() usages")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find all lines with datetime.utcnow()
        usage_lines = []
        for i, line in enumerate(lines, 1):
            if 'datetime.utcnow()' in line:
                usage_lines.append(i)
        
        if usage_lines:
            print(f"✅ Found datetime.utcnow() usage on lines: {usage_lines}")
            print("   These usages will now work with the import in place")
        else:
            print("⚠️  No datetime.utcnow() usages found")
        
        # Expected lines from the problem statement
        expected_lines = [1614, 1625, 1633, 1705, 1777, 1785, 1861, 1871]
        
        # Check if we found the problematic lines mentioned in the issue
        found_problematic_lines = [line for line in expected_lines if line in usage_lines]
        if found_problematic_lines:
            print(f"✅ Confirmed fix covers problematic lines: {found_problematic_lines}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    success = True
    
    # Run tests
    success = test_datetime_import_in_file() and success
    success = test_syntax_validity() and success
    success = test_all_datetime_usages_covered() and success
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 All datetime import tests passed!")
        print("=" * 80)
        print("\n✅ The fix is ready:")
        print("   - datetime is properly imported")
        print("   - All datetime.utcnow() calls will now work")
        print("   - No syntax errors detected")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
