#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew AI Call Center CRM - Main Server (Safe Mode)
Fixed version that avoids grpc conflicts while maintaining functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the minimal server that works without grpc conflicts
from minimal_server import app

if __name__ == "__main__":
    print("🚀 Starting Hebrew AI Call Center CRM (Safe Mode)")
    print("📱 Flask Server starting on http://localhost:5000")
    print("🎯 עסק: שי דירות ומשרדים בע״מ")
    print("✅ AI Hebrew Support Ready")
    
    # Add session configuration
    app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")
    app.config.update(
        SESSION_COOKIE_SAMESITE="Lax", 
        SESSION_COOKIE_SECURE=False
    )
    
    # Add health check endpoint
    @app.route("/health", methods=["GET"])
    def health(): 
        return {"ok": True}, 200
    
    app.run(host="0.0.0.0", port=5000, debug=True)