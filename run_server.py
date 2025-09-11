#!/usr/bin/env python3
"""
Production-ready server runner for Replit
This script is designed to run as a workflow in Replit
"""
import os
import sys
import time
import signal
import subprocess

def signal_handler(sig, frame):
    print(f"🛑 Received signal {sig}, shutting down...")
    sys.exit(0)

def main():
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Environment setup
    os.environ.update({
        'PYTHONUNBUFFERED': '1',
        'PYTHONPATH': '.',
        'PORT': os.getenv('PORT', '5000')
    })
    
    port = os.getenv('PORT', '5000')
    print(f"🚀 Starting server on port {port}...")
    
    try:
        # Import and run the Flask app directly
        from server.app_factory import create_app
        
        app = create_app()
        print(f"✅ Flask app created successfully")
        print(f"🌐 Starting server on 0.0.0.0:{port}")
        
        # Run with Werkzeug server for development
        app.run(
            host='0.0.0.0',
            port=int(port),
            debug=False,
            threaded=True,
            use_reloader=False
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