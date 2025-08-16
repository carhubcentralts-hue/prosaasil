#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Production Main Entry Point
נקודת כניסה עיקרית למערכת ניהול שיחות עברית AI - PRODUCTION READY
"""
import os

# Production-ready app creation
from server.app_factory import create_app
app = create_app()

if __name__ == '__main__':
    print("🚀 Hebrew AI Call Center CRM - Production Ready")
    print("✅ All production components loaded")
    print("=" * 50)
    
    # Production configuration
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)