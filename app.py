import os
import logging
from flask import Flask
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
    
    # Blueprints registered in routes.py to avoid conflicts

    db.create_all()
    
    # הפעלת שירותי ניקוי אוטומטי
    try:
        from cleanup_service import start_audio_cleanup
        start_audio_cleanup()
        logging.info("🧹 Audio cleanup service started")
    except Exception as e:
        logging.warning(f"⚠️ Could not start cleanup service: {e}")
    
    # הפעלת שירות ניקוי ברקע מתקדם
    try:
        from auto_cleanup_background import background_cleanup
        background_cleanup.start_scheduler()
        logging.info("🧹 Background cleanup scheduler started")
    except Exception as e:
        logging.warning(f"⚠️ Could not start background cleanup: {e}")

# Media stream routes integrated into routes.py


