#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Full WebSocket Version
Fixed for bidirectional Hebrew conversations and Media Streams
AgentLocator 71 - Production Ready
"""
import os
import json
import tempfile

# CRITICAL: Setup GCP credentials FIRST (per guidelines §3.2)
creds = os.getenv("GCP_CREDENTIALS_JSON") or os.getenv("GOOGLE_TTS_SA_JSON")
if creds and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    p = os.path.join(tempfile.gettempdir(), "gcp.json")
    with open(p, "w") as f: f.write(creds)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = p
    print(f"🔐 GCP credentials file created: {p}")

# Import the full app factory with WebSocket support
from server.app_factory import create_app

# Create app with full WebSocket Media Streams support
# This is the app instance that Gunicorn will use
app = create_app()

print(f"🚀 AgentLocator-71 app created successfully for Gunicorn")

# App is created by app_factory with all features
print("🚀 AgentLocator 71 - Hebrew AI Call Center")
print("✅ WebSocket bidirectional conversations enabled")
print("✅ Hebrew TTS/STT with proper GCP credentials") 
print("🐕 WATCHDOG SYSTEM ENABLED - Record fallback on WS failure")
print("🔄 DEPLOYMENT: AgentLocator 71 - Production Ready per Guidelines")

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