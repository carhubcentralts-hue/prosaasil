#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
FORCE clean eventlet environment
"""

import os
import sys

# CRITICAL FIX: Force eventlet to use working hub for NixOS
os.environ['EVENTLET_HUB'] = 'epolls'

# Set ONLY safe eventlet variables
os.environ['EVENTLET_NO_GREENDNS'] = '1'

print(f"🔧 Eventlet hub forced to: {os.environ.get('EVENTLET_HUB')}")

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