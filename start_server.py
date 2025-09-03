#!/usr/bin/env python3
"""
Simple server starter for debugging
"""

print("🚀 Starting Hebrew AI Call Center Server...")

from server.app_factory import create_app

print("✅ Creating Flask app...")
app = create_app()

print("✅ App created successfully!")

if __name__ == '__main__':
    print("🌐 Starting Flask development server on 0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)