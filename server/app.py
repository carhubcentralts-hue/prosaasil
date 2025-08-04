import os
import logging
from flask import Flask, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Production security settings
if os.environ.get("HTTPS_ONLY", "True").lower() == "true":
    app.config["PREFERRED_URL_SCHEME"] = "https"

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///call_center.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    
    # Register Admin Blueprint FIRST
    try:
        from admin_routes import admin_bp  # Admin routes for business management
        app.register_blueprint(admin_bp)
        logging.info("✅ Admin Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Admin Blueprint registration failed: {e}")

    # Register Business Blueprint
    try:
        from business_routes import business_bp  # Business routes
        app.register_blueprint(business_bp)
        logging.info("✅ Business Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Business Blueprint registration failed: {e}")
        
    # Register Status Blueprint
    try:
        from status_routes import status_bp  # Status routes
        app.register_blueprint(status_bp)
        logging.info("✅ Status Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Status Blueprint registration failed: {e}")

    # Register Login Blueprint
    try:
        from login_routes import login_bp  # Login and authentication routes
        app.register_blueprint(login_bp, url_prefix='/api')
        logging.info("✅ Login Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Login Blueprint registration failed: {e}")

    # Register other Blueprints
    try:
        from crm_bp import crm_bp
        from whatsapp_bp import whatsapp_bp
        from signature_bp import signature_bp
        from invoice_bp import invoice_bp
        from proposal_bp import proposal_bp
        
        app.register_blueprint(crm_bp)
        app.register_blueprint(whatsapp_bp)
        app.register_blueprint(signature_bp)
        app.register_blueprint(invoice_bp)
        app.register_blueprint(proposal_bp)
        
        logging.info("✅ All other Blueprints registered successfully")
        
    except Exception as e:
        logging.warning(f"⚠️ Could not register some Blueprints: {e}")

    # Import systematic route modules (Hebrew CRM System)
    try:
        import routes_twilio      # AI Call handling routes
        import routes_whatsapp    # WhatsApp (Baileys + Twilio) routes  
        import routes_crm         # Advanced CRM routes
        # import routes           # Legacy routes - DEPRECATED
        import api_routes         # New React API routes
        import api_crm_advanced   # Advanced CRM API routes
        import api_whatsapp_advanced # Advanced WhatsApp API routes
        import api_business_info  # Business info API routes
        logging.info("✅ All route modules loaded successfully")
    except Exception as e:
        logging.warning(f"⚠️ Route modules error: {e}")

    db.create_all()
    
    # הפעלת שירותי ניקוי אוטומטי הוסר - משתמש ב-background_cleanup
    
    # הפעלת שירות ניקוי ברקע מתקדם
    try:
        from auto_cleanup_background import background_cleanup
        background_cleanup.start_scheduler()
        logging.info("🧹 Background cleanup scheduler started")
    except Exception as e:
        logging.warning(f"⚠️ Could not start background cleanup: {e}")

# React Frontend Routes - Flask מגיש את React
@app.route("/")
def serve_index():
    """Serve React app at root"""
    try:
        return send_from_directory("../client/dist", "index.html")
    except FileNotFoundError:
        return "<h1>React Build Not Found</h1><p>Run 'npm run build' in client directory</p>", 404

@app.route("/<path:path>")
def serve_static_files(path):
    """Serve static files or React app for SPA routing"""
    try:
        # Static files from React build
        file_path = os.path.join("../client/dist", path) 
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory("../client/dist", path)
        else:
            # For all other routes (SPA routing), serve React app
            return send_from_directory("../client/dist", "index.html")
    except FileNotFoundError:
        return "<h1>React Build Not Found</h1><p>Run 'npm run build' in client directory</p>", 404

# Media stream routes integrated into routes.py


