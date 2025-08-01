"""
Hebrew AI Call Center CRM - Production Entry Point
מערכת CRM מוקד שיחות AI בעברית - נקודת כניסה לייצור
"""
from app import app
# Routes are already imported in app.py
import os
import logging
from datetime import datetime

# Configure production logging
if not app.debug:
    log_file = os.environ.get('LOG_FILE_PATH', './app.log')
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure file logging
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(funcName)s(): %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('🚀 Hebrew AI Call Center CRM startup - production mode')

def run_initialization_check():
    """בדיקה אם המערכת מאותחלת עם נתונים בסיסיים"""
    try:
        from models import User, Business
        with app.app_context():
            admin_exists = User.query.filter_by(username='שי', role='admin').first()
            business_exists = Business.query.filter_by(is_active=True).first()
            
            if not admin_exists or not business_exists:
                app.logger.warning("⚠️  System not initialized with basic data")
                app.logger.info("💡 Run 'python init_database.py' to initialize with sample data")
                return False
            
            app.logger.info("✅ System initialization check passed")
            return True
    except Exception as e:
        app.logger.warning(f"⚠️  Could not check system initialization: {e}")
        return False

def main():
    """נקודת כניסה ראשית לאפליקציה"""
    # Production environment setup
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    # Log startup information
    app.logger.info(f"🌟 Starting Hebrew AI Call Center CRM")
    app.logger.info(f"📍 Host: {host}:{port}")
    app.logger.info(f"🔧 Debug mode: {debug_mode}")
    app.logger.info(f"🕐 Startup time: {datetime.utcnow().isoformat()}")
    
    # Run initialization check
    run_initialization_check()
    
    # Production-ready configuration
    extra_files = []
    if debug_mode:
        # In development, watch for template changes
        import glob
        extra_files.extend(glob.glob('templates/**/*.html', recursive=True))
        extra_files.extend(glob.glob('static/**/*', recursive=True))
    
    try:
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            threaded=True,
            extra_files=extra_files if debug_mode else None,
            use_reloader=debug_mode
        )
    except KeyboardInterrupt:
        app.logger.info("👋 Application stopped by user")
    except Exception as e:
        app.logger.error(f"❌ Application crashed: {e}")
        raise

if __name__ == "__main__":
    main()
