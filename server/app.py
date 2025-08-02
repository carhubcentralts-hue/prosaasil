import os
import logging
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

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
    
    # Register Blueprints
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
        
        logging.info("✅ All Blueprints registered successfully")
        
    except Exception as e:
        logging.warning(f"⚠️ Could not register some Blueprints: {e}")

    # Import systematic route modules (Hebrew CRM System)
    try:
        import routes_twilio      # AI Call handling routes
        import routes_whatsapp    # WhatsApp (Baileys + Twilio) routes  
        import routes_crm         # Advanced CRM routes
        import routes             # Legacy routes
        import api_routes         # New React API routes
        from admin_routes import admin_bp  # Admin routes for business management
        app.register_blueprint(admin_bp)
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
    return send_from_directory("../client/dist", "index.html")

@app.route("/<path:path>")
def serve_static_files(path):
    # Skip API routes - let Flask handle them
    if path.startswith('api/'):
        from flask import abort
        abort(404)
    
    file_path = os.path.join("../client/dist", path)
    if os.path.exists(file_path):
        return send_from_directory("../client/dist", path)
    else:
        return send_from_directory("../client/dist", "index.html")

# Media stream routes integrated into routes.py


