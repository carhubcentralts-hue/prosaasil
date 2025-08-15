#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Professional Main Entry Point
נקודת כניסה עיקרית למערכת ניהול שיחות עברית AI - PRODUCTION READY
"""

import os
from server.bootstrap_secrets import ensure_env, ensure_google_creds_file
ensure_env()
ensure_google_creds_file()

from server.app_factory import create_app

# Create professional Flask app
app = create_app()

if __name__ == '__main__':
    print("🎯 Starting Professional Hebrew AI Call Center CRM")
    print("🔐 Secure Authentication System Active") 
    print("🏢 Business: שי דירות ומשרדים בע״מ")
    print("✅ שיחות רציפות עם זיכרון AI - CONTINUOUS CONVERSATIONS")
    print("=" * 50)
    
    # Production deployment configuration
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)