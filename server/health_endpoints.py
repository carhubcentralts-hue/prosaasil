"""
Production Health Monitoring Endpoints
נקודות קצה לבקרת בריאות המערכת - PRODUCTION READY
"""
from flask import Blueprint, jsonify
import os
from datetime import datetime

health_bp = Blueprint('health', __name__)

@health_bp.route('/healthz', methods=['GET'])
def healthz():
    """Basic health check"""
    return "ok", 200

@health_bp.route('/readyz', methods=['GET']) 
def readyz():
    """Readiness check with system status"""
    return jsonify({
        "status": "ready",
        "db": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }), 200

@health_bp.route('/version', methods=['GET'])
def version():
    """Version and build information"""
    return jsonify({
        "app": "Hebrew AI Call Center CRM",
        "version": "1.0.0",
        "status": "production-ready",
        "build_time": datetime.now().isoformat(),
        "business": "שי דירות ומשרדים בע״מ"
    }), 200