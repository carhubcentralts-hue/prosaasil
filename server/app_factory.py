"""
Flask Application Factory
מפעל יישומים Flask עם הגדרות סביבה
"""
from flask import Flask
from flask_cors import CORS
import logging
import os

def create_app(env: str = 'development') -> Flask:
    """Create Flask application with environment-specific configuration"""
    
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    
    # Load configuration
    CONFIG_MAP = {
        'development': 'config.DevConfig',
        'testing': 'config.TestConfig', 
        'production': 'config.ProdConfig',
    }
    
    config_class = CONFIG_MAP.get(env, 'config.DevConfig')
    app.config.from_object(config_class)
    
    # Initialize extensions
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['*']))
    
    # Initialize database from existing app setup
    # Note: Database is already initialized in app.py to avoid circular imports
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Setup logging
    setup_logging(app, env)
    
    app.logger.info(f"🚀 Hebrew AI Call Center CRM initialized - {env} mode")
    
    return app

def register_blueprints(app):
    """Register all application blueprints in organized manner"""
    
    def safe_register_blueprint(module_name, bp_name, description):
        """Safely register a blueprint with error handling"""
        try:
            module = __import__(module_name, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint)
            app.logger.info(f"✅ {description} registered")
            return True
        except ImportError as e:
            app.logger.warning(f"⚠️ {description} not found: {e}")
            return False
        except Exception as e:
            app.logger.error(f"❌ {description} failed: {e}")
            return False
    
    registered_count = 0
    
    # Core service blueprints
    core_blueprints = [
        ('routes_twilio', 'twilio_bp', 'Twilio Service Blueprint'),
        ('crm_bp', 'crm_bp', 'CRM Blueprint'),
        ('whatsapp_bp', 'whatsapp_bp', 'WhatsApp Blueprint'),
        ('signature_bp', 'signature_bp', 'Signature Blueprint'),
        ('invoice_bp', 'invoice_bp', 'Invoice Blueprint'),
        ('proposal_bp', 'proposal_bp', 'Proposal Blueprint'),
    ]
    
    for module, bp_name, desc in core_blueprints:
        if safe_register_blueprint(module, bp_name, desc):
            registered_count += 1
    
    # API blueprints
    api_blueprints = [
        ('whatsapp_api', 'whatsapp_api_bp', 'WhatsApp API Blueprint'),
        ('crm_api', 'crm_api_bp', 'CRM API Blueprint'),
        ('signature_api', 'signature_api_bp', 'Signature API Blueprint'),
        ('proposal_api', 'proposal_api_bp', 'Proposal API Blueprint'),
        ('invoice_api', 'invoice_api_bp', 'Invoice API Blueprint'),
        ('stats_api', 'stats_api_bp', 'Stats API Blueprint'),
    ]
    
    for module, bp_name, desc in api_blueprints:
        if safe_register_blueprint(module, bp_name, desc):
            registered_count += 1
    
    # Advanced API blueprints
    advanced_blueprints = [
        ('api_routes', 'api_bp', 'Main API Blueprint'),
        ('api_admin_advanced', 'admin_advanced_bp', 'Admin Advanced Blueprint'),
        ('api_business_leads', 'business_leads_bp', 'Business Leads Blueprint'),
        ('routes_call_analysis', 'call_analysis_bp', 'Call Analysis Blueprint'),
        ('api_phone_analysis', 'phone_analysis_bp', 'Phone Analysis Blueprint'),
        ('api_tasks', 'tasks_api_bp', 'Tasks API Blueprint'),
        ('api_notifications', 'notifications_api_bp', 'Notifications API Blueprint'),
    ]
    
    for module, bp_name, desc in advanced_blueprints:
        if safe_register_blueprint(module, bp_name, desc):
            registered_count += 1
    
    app.logger.info(f"🎯 Blueprint registration complete: {registered_count} blueprints loaded")

def register_error_handlers(app):
    """Register error handlers for common HTTP errors"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return {
            "error": "not_found",
            "message": "המשאב המבוקש לא נמצא",
            "detail": "Resource not found",
            "status_code": 404
        }, 404
    
    @app.errorhandler(500) 
    def internal_error(error):
        app.logger.exception("Unhandled server error")
        return {
            "error": "server_error",
            "message": "שגיאת שרת פנימית", 
            "detail": "Internal server error",
            "status_code": 500
        }, 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return {
            "error": "forbidden",
            "message": "אין הרשאה לגשת למשאב זה",
            "detail": "Access forbidden",
            "status_code": 403
        }, 403
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return {
            "error": "bad_request", 
            "message": "בקשה לא תקינה",
            "detail": "Bad request",
            "status_code": 400
        }, 400

def setup_logging(app, env):
    """Setup logging based on environment"""
    import json
    
    class JsonFormatter(logging.Formatter):
        """JSON log formatter for production"""
        def format(self, record):
            log_obj = {
                'timestamp': self.formatTime(record, self.datefmt),
                'level': record.levelname,
                'message': record.getMessage(),
                'logger': record.name,
                'module': record.module,
                'funcName': record.funcName,
                'lineno': record.lineno
            }
            
            if record.exc_info:
                log_obj['exception'] = self.formatException(record.exc_info)
                
            return json.dumps(log_obj, ensure_ascii=False)
    
    # Setup handler
    handler = logging.StreamHandler()
    
    if env == 'production':
        # JSON logging for production
        handler.setFormatter(JsonFormatter())
        app.logger.setLevel(logging.INFO)
        
        # Suppress debug logs from other libraries
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
    else:
        # Human-readable logging for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.setLevel(logging.DEBUG if app.config.get('ENABLE_DEBUG_LOGS') else logging.INFO)
    
    # Add handler to app logger
    app.logger.addHandler(handler)
    
    app.logger.info(f"📋 Logging setup complete for {env} environment")