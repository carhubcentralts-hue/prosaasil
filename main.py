#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Development Server
מערכת CRM עברית עם AI לקריאות טלפון
"""

import os
import sys

# For development only - production uses wsgi.py with eventlet
print("🔧 Development server - Use wsgi.py for production with WebSocket support")

# Create Flask app using app_factory
from server.app_factory import create_app
app = create_app()

print("✅ Flask app created with app_factory")
print("⚠️ WebSocket support requires production deployment with eventlet worker")
print("⚠️ For production: Use 'python -m gunicorn wsgi:app --worker-class eventlet'")

# Entry point for development only
if __name__ == '__main__':
    print("🚨 DEVELOPMENT MODE: WebSocket calls will NOT work!")
    print("🚨 Use deployment with eventlet worker for WebSocket support")
    app.run(host='0.0.0.0', port=5000, debug=False)