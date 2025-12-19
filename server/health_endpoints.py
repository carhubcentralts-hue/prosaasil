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

@health_bp.route('/api/health', methods=['GET'])
def api_health():
    """API health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "prosaasil-api",
        "timestamp": datetime.now().isoformat()
    }), 200

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

@health_bp.route('/warmup', methods=['GET', 'POST'])
def warmup():
    """
    ⚡ WARMUP endpoint - Preloads all services to avoid cold start
    Cloud Run calls this on instance startup
    """
    try:
        from server.services.lazy_services import get_openai_client, get_tts_client, get_stt_client
        
        start = time.time()
        results = {}
        
        # Warmup OpenAI
        client = get_openai_client()
        results['openai'] = 'ok' if client else 'unavailable'
        
        # ⚡ Phase 2: Warmup TTS with actual synthesis (prevents cold start!)
        try:
            from server.services.gcp_tts_live import maybe_warmup
            t_warmup = time.time()
            maybe_warmup()
            warmup_ms = int((time.time() - t_warmup) * 1000)
            results['tts_warmup'] = 'ok'
            results['tts_warmup_ms'] = warmup_ms
        except Exception as e:
            results['tts_warmup'] = f'error: {str(e)[:200]}'
        
        # Warmup TTS client
        client = get_tts_client()
        results['tts'] = 'ok' if client else 'unavailable'
        
        # Warmup STT
        client = get_stt_client()
        results['stt'] = 'ok' if client else 'unavailable'
        
        # Warmup DB
        from server.db import db
        from sqlalchemy import text
        try:
            db.session.execute(text('SELECT 1'))
            db.session.close()  # ✅ Clean up NullPool connection
            results['database'] = 'ok'
        except Exception as e:
            results['database'] = f'error: {str(e)[:30]}'
        
        duration = int((time.time() - start) * 1000)
        
        return jsonify({
            "status": "warmed",
            "services": results,
            "duration_ms": duration,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "warmup_failed",
            "error": str(e)[:100]
        }), 500

@health_bp.route('/db-check', methods=['GET'])
def db_check():
    """🔧 Database connection check - shows DB driver WITHOUT password"""
    db_url = os.getenv('DATABASE_URL', 'NOT_SET')
    
    # Extract driver without exposing password
    if db_url == 'NOT_SET':
        driver = 'NOT_SET'
        status = 'missing'
    else:
        driver = db_url.split(':')[0] if db_url else 'unknown'
        status = 'configured'
    
    # Try to connect
    connection_test = 'not_tested'
    try:
        from server.db import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        connection_test = 'success'
    except Exception as e:
        connection_test = f'failed: {str(e)[:50]}'
    
    return jsonify({
        "database_url_status": status,
        "driver": driver,
        "connection_test": connection_test,
        "is_production": os.getenv('REPLIT_DEPLOYMENT') == '1',
        "timestamp": datetime.now().isoformat()
    }), 200

@health_bp.route('/api/debug/routes', methods=['GET'])
def debug_routes():
    """
    🔧 Debug endpoint - Lists all registered Flask routes
    Useful for troubleshooting 404 issues in production
    
    Security: Only available in development or for system_admin
    """
    try:
        from flask import current_app
        from server.auth_api import require_api_auth
        
        # Check if in development mode or user is system_admin
        is_dev = os.getenv('FLASK_ENV') == 'development' or os.getenv('MIGRATION_MODE') == '1'
        
        if not is_dev:
            # In production, require system_admin role
            user = session.get('al_user') or session.get('user')
            if not user or user.get('role') != 'system_admin':
                return jsonify({
                    'error': 'forbidden',
                    'message': 'This endpoint is only available to system administrators'
                }), 403
        
        # Critical endpoints that MUST exist
        critical_endpoints = [
            '/api/health',
            '/api/dashboard/stats',
            '/api/dashboard/activity',
            '/api/business/current',
            '/api/notifications',
            '/api/admin/businesses',
            '/api/search',
            '/api/whatsapp/status',
            '/api/whatsapp/templates',
            '/api/whatsapp/broadcasts',
            '/api/crm/threads',
            '/api/statuses',
            '/api/leads',
        ]
        
        # Get all registered routes
        all_routes = []
        critical_status = {}
        
        for rule in current_app.url_map.iter_rules():
            route_path = str(rule)
            route_info = {
                'path': route_path,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'endpoint': rule.endpoint
            }
            all_routes.append(route_info)
            
            # Check if this is a critical endpoint (exact match only)
            for critical in critical_endpoints:
                # Exact match with or without trailing slash
                route_clean = route_path.rstrip('/')
                critical_clean = critical.rstrip('/')
                if route_clean == critical_clean:
                    critical_status[critical] = True
        
        # Mark missing critical endpoints
        for critical in critical_endpoints:
            if critical not in critical_status:
                critical_status[critical] = False
        
        # Filter to only show API routes
        api_routes = [r for r in all_routes if '/api/' in r['path']]
        api_routes.sort(key=lambda x: x['path'])
        
        # Count critical endpoints status
        critical_ok = sum(1 for v in critical_status.values() if v)
        critical_total = len(critical_endpoints)
        
        return jsonify({
            'status': 'ok' if critical_ok == critical_total else 'degraded',
            'total_routes': len(all_routes),
            'api_routes_count': len(api_routes),
            'critical_endpoints': {
                'total': critical_total,
                'registered': critical_ok,
                'missing': critical_total - critical_ok,
                'status': critical_status
            },
            'api_routes': api_routes[:50] if not is_dev else api_routes,  # Limit in production
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500