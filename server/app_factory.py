from flask import Flask
from flask_cors import CORS
from .config import DevConfig, ProdConfig, TestConfig
from .routes import register_blueprints
from .models import db
from .error_handlers import register_error_handlers
from .logging_setup import setup_logging

CONFIG_MAP = {
    'development': DevConfig,
    'testing': TestConfig,
    'production': ProdConfig,
}

def create_app(env: str = 'development') -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIG_MAP.get(env, DevConfig))

    # extensions
    db.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', '*'))

    # blueprints
    register_blueprints(app)

    # error handlers
    register_error_handlers(app)

    # logging
    setup_logging(app)
    
    # Create tables and demo data
    with app.app_context():
        db.create_all()
        from .demo_data import create_demo_data
        create_demo_data()
    
    return app