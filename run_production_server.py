#!/usr/bin/env python3
"""
Production server for Replit - Designed to stay running
"""
import os
import sys
import time
import threading
import signal

# Ensure proper environment
os.environ.update({
    'PYTHONUNBUFFERED': '1',
    'PYTHONPATH': '.',
    'PORT': '5000',
    'FLASK_ENV': 'production'
})

def signal_handler(sig, frame):
    print(f"🛑 Received signal {sig}, shutting down...")
    sys.exit(0)

def main():
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🚀 Starting production server on port 5000...")
    
    try:
        # Import and create the Flask app
        from server.app_factory import create_app
        app = create_app()
        
        print("✅ Flask app created successfully")
        print("🌐 Server running on http://0.0.0.0:5000")
        print("📋 Health check: http://localhost:5000/healthz")
        print("🔍 Version info: http://localhost:5000/version")
        
        # Use Werkzeug server with proper threading
        from werkzeug.serving import run_simple
        
        run_simple(
            hostname='0.0.0.0',
            port=5000,
            application=app,
            use_reloader=False,
            use_debugger=False,
            threaded=True,
            use_evalex=False
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested")
        return 0
    except Exception as e:
        print(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())