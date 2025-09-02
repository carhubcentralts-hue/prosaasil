#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Development Server
מערכת CRM עברית עם AI לקריאות טלפון
"""

import os
import sys

# Import wsgi app with full WebSocket support
from wsgi import app

print("✅ WSGI app loaded with EventLet WebSocket support")
print("📞 Hebrew AI Call Center ready")
print("🤖 Leah: Hebrew real estate AI agent")

# Entry point - works with WebSocket!
if __name__ == '__main__':
    print("🚀 Starting Hebrew AI server with full WebSocket support...")
    port = int(os.environ.get('PORT', 5000))
    
    import eventlet.wsgi
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app)