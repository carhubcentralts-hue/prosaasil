#!/usr/bin/env python3
"""
Verification script to check Python compilation before deployment.
This script ensures no syntax errors exist in critical Python files.
"""

import sys
import py_compile
from pathlib import Path

def check_file(filepath):
    """Check if a Python file compiles without errors."""
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✓ {filepath} - OK")
        return True
    except py_compile.PyCompileError as e:
        print(f"✗ {filepath} - FAILED")
        print(f"  Error: {e}")
        return False

def main():
    """Main verification function."""
    print("=" * 70)
    print("Python Compilation Verification")
    print("=" * 70)
    
    # Critical files to check
    critical_files = [
        "server/media_ws_ai.py",
        "asgi.py",
        "server/routes_twilio.py",
        "server/app_factory.py",
    ]
    
    base_path = Path(__file__).parent
    all_ok = True
    
    for file in critical_files:
        filepath = base_path / file
        if not filepath.exists():
            print(f"⚠ {file} - NOT FOUND")
            all_ok = False
            continue
        
        if not check_file(str(filepath)):
            all_ok = False
    
    print("=" * 70)
    if all_ok:
        print("✅ All files compile successfully!")
        return 0
    else:
        print("❌ Some files failed to compile!")
        print("DO NOT DEPLOY - Fix syntax errors first!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
