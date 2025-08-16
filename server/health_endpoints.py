"""
Health check endpoints for production monitoring
"""
import os
import json
from flask import Blueprint, jsonify
from server.bootstrap_secrets import check_secrets
from server.db import db
import logging

health_bp = Blueprint("health", __name__)
log = logging.getLogger(__name__)

@health_bp.get("/healthz")
def healthz():
    """Basic health check - always returns ok"""
    return "ok", 200

@health_bp.get("/readyz") 
def readyz():
    """Readiness check with service status"""
    status = {
        "db": "ok",
        "openai": "disabled", 
        "tts": "disabled",
        "payments": {
            "paypal": "disabled",
            "tranzila": "disabled"
        }
    }
    
    # Check database
    try:
        db.session.execute("SELECT 1")
        status["db"] = "ok"
    except Exception as e:
        log.error(f"Database check failed: {e}")
        status["db"] = "fail"
    
    # Check secrets
    try:
        secrets = check_secrets()
        status["openai"] = "ok" if secrets["openai"] else "disabled"
        status["tts"] = "ok" if secrets["tts"] else "disabled"  
        status["payments"]["paypal"] = "enabled" if secrets["paypal"] else "disabled"
        status["payments"]["tranzila"] = "enabled" if secrets["tranzila"] else "disabled"
    except Exception as e:
        log.error(f"Secrets check failed: {e}")
        
    return jsonify(status), 200

@health_bp.get("/version")
def version():
    """Version info"""
    return jsonify({
        "app": "AgentLocator",
        "commit": os.getenv("GIT_COMMIT", "dev"),
        "build_time": os.getenv("BUILD_TIME", "dev")
    }), 200