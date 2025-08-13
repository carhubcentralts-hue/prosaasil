#!/usr/bin/env python3
"""
Server wrapper for main.py to fix deployment path issues.
This file redirects to the actual main.py in the root directory.
"""

import sys
import os

# Add the parent directory to the path to import the root main.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Change to the parent directory so relative imports work
os.chdir(parent_dir)

# Import and run the main application
if __name__ == "__main__":
    # Execute the root main.py
    exec(open(os.path.join(parent_dir, 'main.py')).read())