#!/usr/bin/env python3
"""
Simple dev server starter for debugging
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, '.')

print("🚀 Starting Hebrew AI Call Center CRM...")
print("📁 Working directory:", os.getcwd())
print("🐍 Python version:", sys.version)

try:
    # Test Flask import
    from flask import Flask
    print("✅ Flask import successful")
    
    # Test our app import
    from main import app
    print("✅ Main app import successful")
    
    # Start server
    port = int(os.getenv('PORT', 5000))
    print(f"🌐 Starting server on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        threaded=True,
        use_reloader=False  # Prevent double startup
    )
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()