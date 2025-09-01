#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
Clean eventlet setup without forced configuration
"""

import os
import sys

# Clean environment - remove any cached EVENTLET_HUB settings
os.environ.pop('EVENTLET_HUB', None)
os.environ.setdefault('EVENTLET_NO_GREENDNS', '1')

# Don't force monkey_patch - let gunicorn eventlet worker handle it
try:
    import eventlet  # Just import, no patching
except ImportError:
    pass

# Load app from main.py
try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Import main module
    import main
    app = main.app
    print("✅ App loaded from main.py")
except Exception as e:
    print(f"❌ Failed to load main.py: {e}")
    # Fallback
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
    from app_factory import create_app
    app = create_app()
    print("✅ Fallback app loaded")

# Simple health check
@app.route('/healthz')
def health():
    return "ok", 200

if __name__ == "__main__":
    print("🚀 WSGI loaded successfully")