# server/health_routes.py
from flask import Blueprint, jsonify
import datetime

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "Hebrew AI Call Center CRM",
        "version": "1.0.0"
    }), 200

# Root endpoint moved to app_factory.py to serve the frontend