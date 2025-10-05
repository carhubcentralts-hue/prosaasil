"""
Production Health Monitoring Endpoints
נקודות קצה לבקרת בריאות המערכת - PRODUCTION READY
"""
from flask import Blueprint, jsonify
import os
from datetime import datetime
import time

# Set app start time once when module is imported
APP_START_TIME = time.time()
os.environ['APP_START_TIME'] = str(int(APP_START_TIME))

health_bp = Blueprint('health', __name__)

@health_bp.route('/healthz', methods=['GET'])
def healthz_endpoint():
    """Basic health check"""
    return "ok", 200

@health_bp.route('/readyz', methods=['GET']) 
def readyz():
    """Readiness check with system status and dependencies"""
    try:
        # Check database connection
        from server.db import db
        from sqlalchemy import text
        try:
            db.session.execute(text('SELECT 1'))
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)[:50]}"
        
        # Check Baileys service connectivity  
        import requests
        baileys_status = "unknown"
        try:
            baileys_url = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
            response = requests.get(f"{baileys_url}/healthz", timeout=2)
            baileys_status = "healthy" if response.status_code == 200 else f"unhealthy: {response.status_code}"
        except Exception:
            baileys_status = "unreachable"
        
        overall_status = "ready" if db_status == "healthy" and baileys_status == "healthy" else "degraded"
        status_code = 200 if overall_status == "ready" else 503
        
        return jsonify({
            "status": overall_status,
            "dependencies": {
                "database": db_status,
                "baileys_service": baileys_status
            },
            "version": "1.2.0",
            "timestamp": datetime.now().isoformat()
        }), status_code
        
    except Exception as e:
        return jsonify({
            "status": "not_ready", 
            "error": str(e)[:100],
            "timestamp": datetime.now().isoformat()
        }), 503

@health_bp.route('/version', methods=['GET'])
def version():
    """Version and build information - BUILD 59: Prompt cache invalidation + QR persistence"""
    import time
    return jsonify({
        "status": "ok",
        "service": "agentlocator-whatsapp-crm",
        "version": "1.2.0",
        "build": 59,
        "phase": "ai_prompt_fixes",
        "features": [
            "prompt_cache_invalidation",
            "qr_code_persistence",
            "csrf_exempt_get_routes",
            "multi_tenant_baileys",
            "twilio_validation"
        ],
        "deploy_id": os.getenv("DEPLOY_ID", "development"),
        "sha": os.getenv("GIT_COMMIT", "dev"),
        "timestamp": int(time.time()),
        "uptime": int(time.time() - APP_START_TIME),
        "uptime_human": f"{int((time.time() - APP_START_TIME) // 3600)}h {int(((time.time() - APP_START_TIME) % 3600) // 60)}m {int((time.time() - APP_START_TIME) % 60)}s"
    }), 200

@health_bp.route('/livez', methods=['GET'])
def livez():
    """Liveness check - server is alive"""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }), 200