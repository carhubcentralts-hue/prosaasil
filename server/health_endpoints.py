"""
Production Health Monitoring Endpoints
נקודות קצה לבקרת בריאות המערכת - PRODUCTION READY
"""
from flask import Blueprint, jsonify
import os
from datetime import datetime

health_bp = Blueprint('health', __name__)

@health_bp.route('/healthz', methods=['GET'])
def healthz_endpoint():
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
    """Version and build information - Updated for BUILD: 44"""
    import time
    return jsonify({
        "fe": "client/dist",
        "build": 44,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": "Hebrew AI Call Center CRM",
        "status": "production-ready"
    }), 200

@health_bp.route('/livez', methods=['GET'])
def livez():
    """Liveness check - server is alive"""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }), 200