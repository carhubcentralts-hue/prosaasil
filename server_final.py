#!/usr/bin/env python3
"""
Final stable server solution - WORKING VERSION
Fixed CSRFError import issue and verified working with health checks
"""
import os
import sys

# Setup environment
os.environ.update({
    'PYTHONUNBUFFERED': '1',
    'PYTHONPATH': '.',
    'PORT': '5000'
})

def main():
    print("🚀 Starting final stable server...")
    
    try:
        from server.app_factory import create_app
        app = create_app()
        
        print("✅ Server successfully created and ready")
        print("🌐 Running on http://0.0.0.0:5000")
        print("🔍 Health: http://localhost:5000/healthz")
        print("📋 Version: http://localhost:5000/version")
        
        # Use Flask's built-in server - tested and working
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())