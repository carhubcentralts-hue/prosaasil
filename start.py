#!/usr/bin/env python3
"""
Universal startup script that works from any directory.
This script ensures the application can start regardless of the working directory.
"""

import os
import sys

# Get the directory where this script is located (project root)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Change to the project root directory
os.chdir(script_dir)

# Add the project root to Python path
sys.path.insert(0, script_dir)

# Verify main.py exists
main_py_path = os.path.join(script_dir, 'main.py')
if not os.path.exists(main_py_path):
    print(f"❌ Error: main.py not found at {main_py_path}")
    print(f"📁 Script directory: {script_dir}")
    print(f"📁 Current directory: {os.getcwd()}")
    print(f"📁 Available files: {os.listdir(script_dir)}")
    sys.exit(1)

# Execute the main application
if __name__ == "__main__":
    print(f"🚀 Universal startup script executing from: {os.getcwd()}")
    exec(open(main_py_path).read())