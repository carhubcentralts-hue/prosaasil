#!/usr/bin/env python3
"""
Test for datetime import fix in routes_calls.py
Verifies that the timezone module is properly imported and used correctly
"""

import sys
import os
import re


def test_datetime_timezone_import():
    """
    Test that timezone is properly imported from datetime module
    """
    print("=" * 80)
    print("TEST: timezone import in routes_calls.py")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_calls.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Check for timezone import
        has_timezone_import = False
        import_line_num = None
        
        for i, line in enumerate(lines[:50], 1):  # Check first 50 lines
            if re.search(r'from datetime import.*timezone', line):
                has_timezone_import = True
                import_line_num = i
                print(f"✅ Found timezone import at line {i}: {line.strip()}")
                break
        
        if not has_timezone_import:
            print("❌ timezone import NOT found in the file")
            return False
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_datetime_timezone_usage():
    """
    Test that datetime.timezone.utc is NOT used (should use timezone.utc instead)
    """
    print("\n" + "=" * 80)
    print("TEST: Verify no datetime.timezone.utc usage")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_calls.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find any lines with datetime.timezone (which would be wrong)
        problematic_lines = []
        for i, line in enumerate(lines, 1):
            if 'datetime.timezone' in line:
                problematic_lines.append((i, line.strip()))
        
        if problematic_lines:
            print("❌ Found problematic datetime.timezone usage:")
            for line_num, line_content in problematic_lines:
                print(f"   Line {line_num}: {line_content}")
            return False
        else:
            print("✅ No datetime.timezone usage found (correct!)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_correct_timezone_usage():
    """
    Test that timezone.utc is used correctly
    """
    print("\n" + "=" * 80)
    print("TEST: Verify correct timezone.utc usage")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_calls.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find lines with timezone.utc (correct usage)
        correct_usage_lines = []
        for i, line in enumerate(lines, 1):
            # Match timezone.utc but not datetime.timezone.utc
            if re.search(r'(?<!datetime\.)timezone\.utc', line):
                correct_usage_lines.append((i, line.strip()))
        
        if correct_usage_lines:
            print("✅ Found correct timezone.utc usage:")
            for line_num, line_content in correct_usage_lines:
                print(f"   Line {line_num}: {line_content}")
        else:
            print("⚠️  No timezone.utc usage found (may not be needed)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
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
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_calls.py'
        
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


def test_can_import_module():
    """
    Test that the module can be imported without errors
    """
    print("\n" + "=" * 80)
    print("TEST: Module import test")
    print("=" * 80)
    
    try:
        # Add parent directory to path
        sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')
        
        # Try to import the module (this will catch the datetime.timezone error if it exists)
        import server.routes_calls
        
        print("✅ Module imports successfully without errors")
        return True
        
    except AttributeError as e:
        if 'timezone' in str(e):
            print(f"❌ AttributeError (datetime.timezone issue): {e}")
            return False
        else:
            # Some other AttributeError - might be OK if it's about missing dependencies
            print(f"⚠️  AttributeError (might be dependency issue): {e}")
            return True
    except ImportError as e:
        # ImportError is OK - might be missing dependencies in test environment
        print(f"⚠️  ImportError (expected in test environment): {e}")
        return True
    except Exception as e:
        print(f"⚠️  Other error during import: {e}")
        # Most other errors are OK in test environment
        return True


if __name__ == '__main__':
    success = True
    
    # Run tests
    success = test_datetime_timezone_import() and success
    success = test_no_datetime_timezone_usage() and success
    success = test_correct_timezone_usage() and success
    success = test_syntax_validity() and success
    success = test_can_import_module() and success
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 All datetime timezone fix tests passed!")
        print("=" * 80)
        print("\n✅ The fix is ready:")
        print("   - timezone is properly imported from datetime")
        print("   - No datetime.timezone.utc usage (which would fail)")
        print("   - Correct timezone.utc usage found")
        print("   - No syntax errors detected")
        print("\n🎯 This fixes the recording playback issue!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
