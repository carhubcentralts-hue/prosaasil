#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Full WebSocket Version
Fixed for bidirectional Hebrew conversations and Media Streams
"""
import os

# Import the full app factory with WebSocket support
from server.app_factory import create_app

# Create app with full WebSocket Media Streams support
app = create_app()

# App is created by app_factory with all features
print("🚀 Hebrew AI Call Center - Full WebSocket Media Streams Version")
print("✅ WebSocket bidirectional conversations enabled")
print("✅ Hebrew TTS with proper secrets")
print("🐕 WATCHDOG SYSTEM ENABLED - Will redirect calls to Record if WebSocket fails")

# Test endpoints are now in app_factory.py with WebSocket support
# This file just imports the full app

# All routes and WebSocket functionality now handled by app_factory.py
# This ensures full bidirectional Hebrew conversations with Media Streams

if __name__ == '__main__':
    print("🚀 Hebrew AI Call Center - Full Featured Version")
    print("✅ WebSocket Media Streams enabled")
    print("✅ Bidirectional Hebrew conversations")
    print("✅ Real-time transcription and AI responses")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)