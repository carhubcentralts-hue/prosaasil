#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Professional Main Entry Point
נקודת כניסה עיקרית למערכת ניהול שיחות עברית AI
"""

from server.app_factory import create_app

# Create professional Flask app
app = create_app()

if __name__ == '__main__':
    print("🎯 Starting Professional Hebrew AI Call Center CRM")
    print("🔐 Secure Authentication System Active") 
    print("🏢 Business: שי דירות ומשרדים בע״מ")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)