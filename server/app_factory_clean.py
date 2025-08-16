"""
Hebrew AI Call Center CRM - App Factory (Production Ready - CLEAN)
מפעל אפליקציות Flask נקי ומוכן לפרודקשן
"""
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sock import Sock

def create_app():
    """Create Flask application with Hebrew AI Call Center configuration"""
    app = Flask(__name__)
    
    # CORS configuration
    CORS(app, origins=["*"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    # App configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'PUBLIC_HOST': os.getenv('PUBLIC_HOST', ''),
        'JSONIFY_PRETTYPRINT_REGULAR': True
    })
    
    # Initialize extensions
    try:
        from server.db import db
        db.init_app(app)
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
    
    # Setup production logging
    try:
        from server.logging_setup import setup_logging
        setup_logging()
        print("✅ Production logging setup complete")
    except Exception as e:
        print(f"❌ Logging setup failed: {e}")
        
    # Bootstrap secrets
    try:
        from server.bootstrap_secrets import check_secrets, ensure_google_creds_file
        ensure_google_creds_file()
        secrets = check_secrets()
        print(f"✅ Secrets checked: {secrets}")
    except Exception as e:
        print(f"❌ Secrets bootstrap failed: {e}")
        
    # Apply database migrations
    try:
        from server.db_migrate import apply_migrations
        with app.app_context():
            migrations = apply_migrations()
            if migrations:
                print(f"✅ Applied migrations: {', '.join(migrations)}")
            else:
                print("✅ Database up to date")
    except Exception as e:
        print(f"❌ Database migrations failed: {e}")
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize WebSocket
    setup_websocket(app)
    
    return app

def register_blueprints(app):
    """Register all application blueprints"""
    blueprints = [
        ('server.health_endpoints', 'health_bp'),
        ('server.routes_twilio', 'twilio_bp'),
        ('server.auth_routes', 'auth_bp'),
        ('server.api_crm_unified', 'crm_unified_bp'),
        ('server.providers.payments', 'payments_bp'),
    ]
    
    for module_name, blueprint_name in blueprints:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint)
            print(f"✅ {blueprint_name} registered")
        except Exception as e:
            print(f"❌ {blueprint_name} registration failed: {e}")

def setup_websocket(app):
    """Setup WebSocket for Twilio Media Streams"""
    try:
        sock = Sock(app)
        
        # Try to use production media handler
        try:
            from server.media_ws import handle_media_stream
            sock.route('/ws/twilio-media')(handle_media_stream)
            print("✅ Production WebSocket handler registered")
        except ImportError:
            # Fallback minimal handler
            @sock.route("/ws/twilio-media")
            def media_fallback(ws):
                import json
                logging.info("WebSocket connected (fallback)")
                try:
                    while True:
                        message = ws.receive()
                        if not message:
                            break
                        data = json.loads(message)
                        event = data.get('event')
                        if event == 'stop':
                            break
                except Exception as e:
                    logging.error(f"WebSocket error: {e}")
                finally:
                    logging.info("WebSocket disconnected")
            
            print("✅ Fallback WebSocket handler registered")
            
    except Exception as e:
        print(f"❌ WebSocket setup failed: {e}")

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)