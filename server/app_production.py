#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hebrew AI Call Center CRM - Production App Factory Implementation
מערכת CRM מוקד שיחות AI בעברית - יישום מפעל יישומים לייצור
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask
from flask_cors import CORS

# Production-ready application factory
def create_production_app():
    """Create production Flask application with optimized configuration"""
    
    # Import existing app configuration
    sys.path.append(os.path.dirname(__file__))
    from app import app
    
    # Enhance with production configuration
    env = os.getenv('FLASK_ENV', 'production')
    
    # Production security headers
    if env == 'production':
        app.config.update({
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'PERMANENT_SESSION_LIFETIME': 3600,  # 1 hour
        })
        
        # Add security response headers
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
    
    # Enhanced logging setup
    setup_production_logging(app, env)
    
    # Register new API endpoints
    register_production_apis(app)
    
    app.logger.info(f"🚀 Production Hebrew AI Call Center CRM initialized - {env} mode")
    
    return app

def register_production_apis(app):
    """Register production API endpoints"""
    
    def safe_register_api(module_name, bp_name, description):
        """Safely register API blueprint"""
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
    
    # Register new production APIs
    production_apis = [
        ('api_tasks', 'tasks_api_bp', 'Tasks Management API'),
        ('api_notifications', 'notifications_api_bp', 'Notifications API'),
    ]
    
    registered_count = 0
    for module, bp_name, desc in production_apis:
        if safe_register_api(module, bp_name, desc):
            registered_count += 1
    
    app.logger.info(f"🎯 Production APIs registered: {registered_count}/2")

def setup_production_logging(app, env):
    """Setup production-grade logging"""
    
    if env == 'production':
        # JSON logging for production
        import json
        
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    'timestamp': self.formatTime(record),
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'logger': record.name,
                    'module': record.module,
                }
                
                if record.exc_info:
                    log_obj['exception'] = self.formatException(record.exc_info)
                    
                return json.dumps(log_obj, ensure_ascii=False)
        
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        app.logger.setLevel(logging.INFO)
        
        # Suppress debug logs from libraries
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
    else:
        # Human-readable logging for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        app.logger.setLevel(logging.INFO)
    
    app.logger.addHandler(handler)
    app.logger.info(f"📋 Production logging setup complete for {env} environment")

def run_production_server():
    """Run production server with optimized configuration"""
    
    app = create_production_app()
    
    # Production server configuration
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0") 
    env = os.getenv('FLASK_ENV', 'production')
    debug_mode = (env == 'development')
    
    app.logger.info(f"🌟 Starting Hebrew AI Call Center CRM (Production Polish)")
    app.logger.info(f"📍 Host: {host}:{port}")
    app.logger.info(f"🔧 Debug mode: {debug_mode}")
    app.logger.info(f"🌍 Environment: {env}")
    app.logger.info(f"🕐 Startup time: {datetime.utcnow().isoformat()}")
    
    # Run initialization check
    run_initialization_check(app)
    
    try:
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            threaded=True,
            use_reloader=False,  # Disable reloader in production
        )
    except KeyboardInterrupt:
        app.logger.info("👋 Application stopped by user")
    except Exception as e:
        app.logger.error(f"❌ Application crashed: {e}")
        raise

def run_initialization_check(app):
    """Check if system is initialized with basic data"""
    try:
        from models import User, Business
        with app.app_context():
            admin_exists = User.query.filter_by(role='admin').first()
            business_exists = Business.query.filter_by(is_active=True).first()
            
            if not admin_exists or not business_exists:
                app.logger.warning("⚠️  System not initialized with basic data")
                app.logger.info("💡 Run 'python init_database.py' to initialize")
                return False
            
            app.logger.info("✅ System initialization check passed")
            return True
    except Exception as e:
        app.logger.warning(f"⚠️  Could not check system initialization: {e}")
        return False

if __name__ == "__main__":
    run_production_server()