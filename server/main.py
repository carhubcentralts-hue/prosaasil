#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Production Main Server
Hebrew AI Call Center with all features working
"""

import sys
import os

# Add current directory to path (we're in server/ now)
sys.path.append(os.path.dirname(__file__))

if __name__ == '__main__':
    print("🚀 AgentLocator CRM - Production System")
    print("📊 Hebrew Business Management Platform")
    print("🔐 Login: admin/admin, shai/shai123")
    print("🌐 Professional Interface Ready")
    print("📞 All Features Active: Calls, Transcription, Recordings, Responses, WhatsApp, Twilio")
    
    # Import and run the production server
    from app_simple import app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)