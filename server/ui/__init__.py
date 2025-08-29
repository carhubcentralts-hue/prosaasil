"""
UI Blueprint for Flask + Jinja + Tailwind + HTMX
Based on attached instructions
"""
from flask import Blueprint

ui_bp = Blueprint('ui', __name__)

# Import routes to register them with the blueprint  
from . import routes