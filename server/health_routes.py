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

@health_bp.route("/", methods=["GET"])
def root():
    """Root endpoint"""
    return jsonify({
        "service": "Hebrew AI Call Center CRM",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "twilio_webhooks": "/webhook/*",
            "api": "/api/*",
            "auth": "/api/auth/*"
        }
    }), 200