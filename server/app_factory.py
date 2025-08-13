from flask import Flask
from flask_cors import CORS
from .error_handlers import register_error_handlers
from .logging_setup import setup_logging
from .routes import register_blueprints

def create_app(env: str = 'production') -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        PUBLIC_HOST = app.config.get("PUBLIC_HOST", ""),  # אפשר לדרוס דרך ENV
        CORS_ORIGINS = "*",
    )
    CORS(app, origins=app.config["CORS_ORIGINS"])
    register_blueprints(app)
    register_error_handlers(app)
    setup_logging(app)
    return app