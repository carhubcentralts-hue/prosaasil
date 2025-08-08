"""
AgentLocator v39 - App Factory Pattern
מפעל אפליקציה למחזור הפיתוח הפרודקציוני
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from datetime import datetime

# Import core modules
from .models import db, init_db
from .routes import register_blueprints
from .error_handlers import register_error_handlers
from .logging_setup import setup_logging

def create_app(config_name='development'):
    """
    Application factory pattern for creating Flask app instances
    יצירת מופע אפליקציה עם דפוס Factory
    """
    app = Flask(__name__)
    
    # Environment-based configuration
    if config_name == 'production':
        app.config.update({
            'DEBUG': False,
            'TESTING': False,
            'SECRET_KEY': os.environ.get('SECRET_KEY', os.urandom(32)),
            'DATABASE_URL': os.environ.get('DATABASE_URL'),
            'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'pool_pre_ping': True,
                'pool_recycle': 300,
                'connect_args': {"connect_timeout": 10}
            }
        })
    elif config_name == 'testing':
        app.config.update({
            'DEBUG': False,
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'DATABASE_URL': 'sqlite:///:memory:',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        })
    else:  # development
        app.config.update({
            'DEBUG': True,
            'TESTING': False,
            'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key'),
            'DATABASE_URL': os.environ.get('DATABASE_URL', 'sqlite:///development.db'),
            'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///development.db'),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        })
    
    # Initialize extensions
    init_extensions(app)
    
    # Setup logging first
    setup_logging(app)
    app.logger.info(f"🏭 App Factory: Creating {config_name} application")
    
    # Register components
    register_blueprints(app)
    register_error_handlers(app)
    
    # Initialize database
    with app.app_context():
        try:
            init_db(app)
            app.logger.info("✅ App Factory: Database initialized")
        except Exception as e:
            app.logger.error(f"❌ App Factory: Database initialization failed: {e}")
    
    # Feature flags
    setup_feature_flags(app)
    
    app.logger.info(f"🚀 App Factory: {config_name.title()} application created successfully")
    return app

def init_extensions(app):
    """Initialize Flask extensions"""
    
    # Database
    db.init_app(app)
    
    # CORS configuration
    cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # Add health check endpoint
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': 'v39',
            'environment': app.config.get('ENV', 'unknown')
        }

def setup_feature_flags(app):
    """Setup feature flags based on environment"""
    
    feature_flags = {
        'advanced_crm': True,
        'whatsapp_integration': True,
        'voice_calls': True,
        'digital_signatures': True,
        'invoicing': True,
        'task_management': True,
        'real_time_notifications': True,
        'timeline_api': True,
        'analytics': True,
        'ai_insights': os.environ.get('OPENAI_API_KEY') is not None
    }
    
    app.config['FEATURE_FLAGS'] = feature_flags
    app.logger.info(f"🚩 Feature flags configured: {sum(feature_flags.values())}/{len(feature_flags)} enabled")