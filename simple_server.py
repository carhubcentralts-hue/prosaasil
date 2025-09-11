#!/usr/bin/env python3
"""
Simple working Flask server for Replit workflow
This minimal server will test if the workflow system works
"""
import os
from server.app_factory import create_app

def main():
    print("🚀 Simple Replit Server Starting...")
    
    # Create Flask app
    app = create_app()
    
    # Get port from environment
    port = int(os.getenv("PORT", "5000"))
    
    print(f"✅ Starting server on 0.0.0.0:{port}")
    print("🔥 Server will run until stopped")
    
    # Start the server
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )

if __name__ == '__main__':
    main()