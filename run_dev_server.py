#!/usr/bin/env python3
"""
Simple Flask development server for Replit
More stable than eventlet in development environments
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set environment variables for stability
os.environ.update({
    'PYTHONUNBUFFERED': '1',
    'FLASK_ENV': 'development',
    'FLASK_DEBUG': 'false'  # Set to false for stability
})

def main():
    """Start Flask development server"""
    try:
        from server.app_factory import create_app
        
        print("🚀 Starting stable Flask development server...")
        
        # Create Flask app
        app = create_app()
        
        # Get port from environment or default to 5000
        port = int(os.getenv("PORT", "5000"))
        
        print(f"✅ Server starting on 0.0.0.0:{port}")
        print("🔧 Using Flask development server for stability")
        
        # Start the server with optimized settings for Replit
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=False,  # Disable debug for stability
            threaded=True,  # Enable threading for better performance
            use_reloader=False  # Disable reloader to prevent crashes
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