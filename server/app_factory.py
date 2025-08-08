from flask import Flask
from routes import register_blueprints
from error_handlers import register_error_handlers  
from logging_setup import setup_logging

def create_app(config_object="config.ProdConfig"):
    app = Flask(__name__)
    app.config.from_object(config_object)
    setup_logging(app)
    register_blueprints(app)
    register_error_handlers(app)
    return app