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
        
    # Register Twilio Blueprint  
    try:
        from routes_twilio import twilio_bp  # Twilio webhook routes
        app.register_blueprint(twilio_bp)
        logging.info("✅ Twilio Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Twilio Blueprint registration failed: {e}")

    # Register other Blueprints
    try:
        from crm_bp import crm_bp
        from whatsapp_bp import whatsapp_bp
        from signature_bp import signature_bp
        from invoice_bp import invoice_bp
        from proposal_bp import proposal_bp
        from whatsapp_api import whatsapp_api_bp
        from crm_api import crm_api_bp
        from signature_api import signature_api_bp
        from proposal_api import proposal_api_bp
        from invoice_api import invoice_api_bp
        from stats_api import stats_api_bp
        
        # Register template blueprints
        app.register_blueprint(crm_bp)
        app.register_blueprint(whatsapp_bp)
        app.register_blueprint(signature_bp)
        app.register_blueprint(invoice_bp)
        app.register_blueprint(proposal_bp)
        
        # Register API blueprints for React consumption (AgentLocator)
        try:
            from crm_api import crm_api_bp
            app.register_blueprint(crm_api_bp)
            logging.info("✅ CRM API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ CRM API Blueprint failed: {e}")
        
        try:
            from whatsapp_api import whatsapp_api_bp
            app.register_blueprint(whatsapp_api_bp)
            logging.info("✅ WhatsApp API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ WhatsApp API Blueprint failed: {e}")
        
        try:
            from signature_api import signature_api_bp
            app.register_blueprint(signature_api_bp)
            logging.info("✅ Signature API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ Signature API Blueprint failed: {e}")
        
        try:
            from proposal_api import proposal_api_bp
            app.register_blueprint(proposal_api_bp)
            logging.info("✅ Proposal API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ Proposal API Blueprint failed: {e}")
        
        try:
            from invoice_api import invoice_api_bp
            app.register_blueprint(invoice_api_bp)
            logging.info("✅ Invoice API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ Invoice API Blueprint failed: {e}")
        
        try:
            from stats_api import stats_api_bp
            app.register_blueprint(stats_api_bp)
            logging.info("✅ Stats API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ Stats API Blueprint failed: {e}")
        
        try:
            from routes_call_analysis import call_analysis_bp
            app.register_blueprint(call_analysis_bp)
            logging.info("✅ Call Analysis API Blueprint registered")
        except Exception as e:
            logging.warning(f"⚠️ Call Analysis API Blueprint failed: {e}")
        
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
        
        # Register new advanced API blueprints
        from api_routes import api_bp
        app.register_blueprint(api_bp)
        logging.info("✅ API Routes Blueprint registered successfully")
        
        # Register newest advanced blueprints
        try:
            from api_phone_analysis import phone_analysis_bp
            app.register_blueprint(phone_analysis_bp)
            logging.info("✅ Phone Analysis Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Phone Analysis Blueprint not found")
        
        try:
            from api_admin_advanced import admin_advanced_bp
            app.register_blueprint(admin_advanced_bp)
            logging.info("✅ Admin Advanced Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Admin Advanced Blueprint not found")
        
        try:
            from api_business_leads import business_leads_bp
            app.register_blueprint(business_leads_bp)
            logging.info("✅ Business Leads Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Business Leads Blueprint not found")
            
        try:
            from routes_crm_integration import crm_integration
            app.register_blueprint(crm_integration)
            logging.info("✅ CRM Integration Blueprint registered")
        except ImportError:
            logging.warning("⚠️ CRM Integration Blueprint not found")
            
        # AGENTLOCATOR API BLUEPRINTS - SIMPLE CONNECTION  
        from crm_api import crm_api_bp
        from whatsapp_api import whatsapp_api_bp
        from signature_api import signature_api_bp
        from invoice_api import invoice_api_bp
        from proposal_api import proposal_api_bp
        from stats_api import stats_api_bp

        app.register_blueprint(crm_api_bp)
        app.register_blueprint(whatsapp_api_bp)
        app.register_blueprint(signature_api_bp)
        app.register_blueprint(invoice_api_bp)
        app.register_blueprint(proposal_api_bp)
        app.register_blueprint(stats_api_bp)
        
        logging.info("✅ AgentLocator API Blueprints registered successfully")
        
        logging.info("✅ All route modules loaded successfully")
    except Exception as e:
        logging.warning(f"⚠️ Route modules error: {e}")

    db.create_all()
    
    # הפעלת שירותי ניקוי אוטומטי הוסר - משתמש ב-background_cleanup
    
    # הפעלת שירות ניקוי ברקע מתקדם
    try:
        from auto_cleanup_background import start_background_scheduler
        import threading
        cleanup_thread = threading.Thread(target=start_background_scheduler, daemon=True)
        cleanup_thread.start()
        logging.info("🧹 Background cleanup scheduler started")
    except Exception as e:
        logging.warning(f"⚠️ Could not start background cleanup: {e}")

# TTS Static File Route - HIGHEST PRIORITY - MUST BE FIRST
@app.route("/server/static/voice_responses/<filename>", methods=['GET', 'HEAD'])
def serve_tts_files(filename):
    """Serve TTS audio files with correct MIME type - FIXED VERSION"""
    import os
    from flask import send_file
    
    logging.info(f"🎵 TTS Route Called: {filename}")
    
    try:
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "voice_responses"))
        file_path = os.path.join(static_dir, filename)
        
        logging.info(f"🎵 TTS Full Path: {file_path}")
        logging.info(f"🎵 Directory exists: {os.path.exists(static_dir)}")
        logging.info(f"🎵 File exists: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logging.info(f"🎵 SUCCESS - Serving TTS file: {filename} ({file_size} bytes)")
            
            # Force the correct headers
            response = send_file(file_path, mimetype='audio/mpeg', as_attachment=False)
            response.headers['Content-Type'] = 'audio/mpeg'
            response.headers['Cache-Control'] = 'no-cache'
            return response
        else:
            logging.error(f"❌ TTS file not found: {filename} at {file_path}")
            return "TTS File not found", 404
            
    except Exception as e:
        logging.error(f"❌ Error serving TTS file {filename}: {e}")
        import traceback
        logging.error(f"❌ Full traceback: {traceback.format_exc()}")
        return f"Server error: {e}", 500

# React Assets Route - CRITICAL: Handle both /assets/ and /*/assets/ paths
@app.route("/assets/<path:filename>")
@app.route("/<path:route>/assets/<path:filename>")
def serve_assets(filename, route=None):
    """Serve React assets with correct MIME types from any route"""
    from flask import Response
    
    build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../client/dist"))
    assets_dir = os.path.join(build_dir, "assets")
    
    try:
        response = send_from_directory(assets_dir, filename)
        
        # Set correct MIME types for JavaScript modules
        if filename.endswith('.js'):
            response.mimetype = 'application/javascript'
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        elif filename.endswith('.css'):
            response.mimetype = 'text/css'
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
            
        logging.info(f"✅ Serving asset: {filename} from route: {route} with MIME: {response.mimetype}")
        return response
    except Exception as e:
        logging.error(f"❌ Error serving asset {filename}: {e}")
        return "Asset not found", 404

# React Frontend Routes - Flask מגיש את React
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve React app with proper SPA routing support"""       
    build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../client/dist"))
    
    # CRITICAL: Skip any requests that contain /assets/ - let asset routes handle them
    if "/assets/" in path or path.startswith("assets/"):
        logging.info(f"🔄 Skipping asset path in serve_react: {path}")
        # Don't handle assets - this should never be reached
        from flask import abort
        return abort(404)
    
    requested_path = os.path.join(build_dir, path)

    if path != "" and os.path.exists(requested_path):
        return send_from_directory(build_dir, path)
    else:
        # Serve index.html for SPA routing
        logging.info(f"📄 Serving index.html for SPA path: {path}")
        return send_from_directory(build_dir, "index.html")

# Media stream routes integrated into routes.py


