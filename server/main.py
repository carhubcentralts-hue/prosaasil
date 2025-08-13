#!/usr/bin/env python3
"""
Server wrapper for main.py to fix deployment path issues.
This file redirects to the actual main.py in the root directory.
"""

import sys
import os

# Get the absolute path to the parent directory (project root)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Change to the parent directory so relative imports work correctly
os.chdir(parent_dir)

# Verify the main.py file exists
main_py_path = os.path.join(parent_dir, 'main.py')
if not os.path.exists(main_py_path):
    print(f"❌ Error: main.py not found at {main_py_path}")
    print(f"📁 Current directory: {os.getcwd()}")
    print(f"📁 Parent directory: {parent_dir}")
    print(f"📁 Available files: {os.listdir(parent_dir) if os.path.exists(parent_dir) else 'Directory not found'}")
    sys.exit(1)

# Import and run the main application
if __name__ == "__main__":
    try:
        print(f"🔧 Server wrapper starting from: {os.getcwd()}")
        print(f"🎯 Executing main application: {main_py_path}")
        
        # Execute the root main.py with proper error handling
        with open(main_py_path, 'r') as f:
            exec(f.read())
            
    except Exception as e:
        print(f"❌ Failed to execute main application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)