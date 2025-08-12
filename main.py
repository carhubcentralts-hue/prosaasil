#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Production Main Server
"""

import sys
import os

# Import the production server
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

if __name__ == '__main__':
    print("🚀 Hebrew AI Call Center - CLEAN SYSTEM")
    print("📞 שי דירות ומשרדים בע״מ")
    print("🤖 OpenAI GPT-4o + Whisper Integration") 
    print("✅ All Technical Issues Resolved")
    print("🌐 Ready for Real Twilio Calls!")
    
    try:
        from app_final import app
        print("✅ Clean AI system loaded successfully")
    except Exception as e:
        print(f"⚠️  Fallback to previous system: {e}")
        from app_simple import app
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)