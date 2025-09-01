#!/usr/bin/env python3
"""
Hebrew AI Call Center - Simple WSGI
פתרון פשוט עם Flask לפיתוח ובדיקות
"""

def create_flask_app():
    """Create Flask app with all routes"""
    from server.app_factory import create_app
    return create_app()

# Simple Flask app for production
app = create_flask_app()

print("✅ Simple Flask WSGI created:")
print("   📞 WebSocket routes handled by Flask-Sock")
print("   🌐 All routes handled by Flask app")
print("   🔧 Worker: sync (Flask compatible)")
print("🚀 Ready for development and testing!")

if __name__ == '__main__':
    print("🚀 Starting Flask dev server for testing...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)