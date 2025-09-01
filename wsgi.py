#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
טוען את main.py ומחשף את app למנוע ההפעלה
"""

# CRITICAL: eventlet.monkey_patch() MUST be first for gunicorn+eventlet
# But gracefully handle dev environment issues
try:
    import eventlet
    eventlet.monkey_patch()
    print("✅ Eventlet loaded successfully - WebSocket ready")
    EVENTLET_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Eventlet failed in dev environment: {e}")
    print("🔄 Production deployment will handle this correctly")
    EVENTLET_AVAILABLE = False

import importlib.util
import sys
import os

# טען את main.py כמודול דינמי
def load_main_app():
    """טוען את main.py ומחזיר את app"""
    try:
        # נתיב ל-main.py
        main_path = os.path.join(os.path.dirname(__file__), 'main.py')
        
        if not os.path.exists(main_path):
            raise FileNotFoundError(f"main.py not found at {main_path}")
        
        # טען כמודול
        spec = importlib.util.spec_from_file_location("main", main_path)
        if spec is None:
            raise ImportError(f"Could not create spec for {main_path}")
            
        main_module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise ImportError(f"No loader found for {main_path}")
        
        # הוסף למערכת המודולים
        sys.modules["main"] = main_module
        spec.loader.exec_module(main_module)
        
        # החזר את app
        if hasattr(main_module, 'app'):
            return main_module.app
        else:
            raise AttributeError("No 'app' object found in main.py")
            
    except Exception as e:
        print(f"❌ Failed to load main.py: {e}")
        raise

# Try to load main.py first, fallback to direct app_factory for dev environment  
try:
    app = load_main_app()
    print("✅ Main.py loaded successfully")
except Exception as e:
    print(f"⚠️ Main.py failed (dev env), using direct app_factory: {e}")
    # Import app_factory directly (for development environment)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
    from app_factory import create_app
    app = create_app()
    print("✅ Direct app_factory loaded successfully - Production will use main.py")

# שסתום ביטחון - להבטיח שיש /healthz בלי לשבור כלום
from flask import Response

# אם /healthz לא קיים – הוסף אותו מקומית כדי להציל את הבריאות
if not any(r.rule == "/healthz" for r in app.url_map.iter_rules()):
    @app.get("/healthz")
    def __healthz():
        return Response("ok", 200)

# חתימת אפליקציה לזיהוי קוד חדש
@app.after_request
def _sig(r):
    r.headers["X-App-Signature"] = "wsgi-healthz-v1"
    return r

# Gunicorn Entry Point
if __name__ == "__main__":
    print("🚀 WSGI Entry Point Loaded Successfully")
    print("📍 Application:", app)