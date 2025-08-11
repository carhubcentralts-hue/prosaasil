#!/usr/bin/env python3
# Main Flask Server for Hebrew AI Call Center CRM
import os
import sys

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Import and run the Flask app
from app import app

if __name__ == '__main__':
    print("🚀 Starting Hebrew AI Call Center CRM on port 5000...")
    print("🌐 Server will be available at http://0.0.0.0:5000")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )