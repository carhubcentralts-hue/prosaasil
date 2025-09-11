#!/usr/bin/env python3
"""
Stable server startup script for Replit
Designed to run the server reliably with proper error handling
"""
import os
import sys
import time

def main():
    # Set environment variables
    os.environ.update({
        'PYTHONUNBUFFERED': '1',
        'PYTHONPATH': '.',
        'PORT': '5000'
    })
    
    print("🚀 Starting stable server on port 5000...")
    
    try:
        # Import and create the Flask app
        from server.app_factory import create_app
        app = create_app()
        
        print("✅ Flask app created successfully")
        print("🌐 Server starting on 0.0.0.0:5000")
        
        # Run with Flask's built-in server (stable for development)
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,
            use_reloader=False
        )
        
    except Exception as e:
        print(f"❌ Server startup error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())