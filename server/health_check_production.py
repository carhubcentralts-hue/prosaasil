"""
Production Health Check - Comprehensive System Status
בדיקת בריאות פרודקשן - סטטוס מערכת מקיף
"""
from flask import Blueprint, jsonify
from server.environment_validation import validate_production_environment
from server.whatsapp_provider import get_whatsapp_service
from server.models_sql import Business, Customer, CallLog, WhatsAppMessage
from server.db import db
import logging
import os
from datetime import datetime, timedelta

health_production_bp = Blueprint("health_production", __name__)
logger = logging.getLogger(__name__)

@health_production_bp.route("/api/health", methods=["GET"])
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Hebrew AI Call Center CRM",
        "timestamp": datetime.utcnow().isoformat(),
        "version": os.getenv("APP_VERSION", "1.0.0")
    })

@health_production_bp.route("/api/health/detailed", methods=["GET"])  
def detailed_health_check():
    """Comprehensive health check with all components"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # Environment validation
        try:
            env_validation = validate_production_environment()
            health_status["components"]["environment"] = {
                "status": "healthy" if env_validation["production_ready"] else "warning",
                "production_ready": env_validation["production_ready"],
                "provider": env_validation["whatsapp_provider"],
                "missing_critical": len(env_validation["missing"]["core"]) + len(env_validation["missing"]["whatsapp"])
            }
        except Exception as e:
            health_status["components"]["environment"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Database connectivity
        try:
            # Simple query to test database
            business_count = Business.query.count()
            customer_count = Customer.query.count()
            
            health_status["components"]["database"] = {
                "status": "healthy",
                "businesses": business_count,
                "customers": customer_count,
                "connected": True
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "error",
                "connected": False,
                "error": str(e)
            }
        
        # WhatsApp service
        try:
            service = get_whatsapp_service()
            wa_status = service.get_status()
            
            health_status["components"]["whatsapp"] = {
                "status": "healthy" if wa_status.get("ready") else "warning",
                "provider": wa_status.get("provider"),
                "ready": wa_status.get("ready"),
                "connected": wa_status.get("connected")
            }
        except Exception as e:
            health_status["components"]["whatsapp"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Recent activity check
        try:
            # Check for recent calls and messages
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            recent_calls = CallLog.query.filter(
                CallLog.created_at >= one_hour_ago
            ).count()
            
            recent_messages = WhatsAppMessage.query.filter(
                WhatsAppMessage.created_at >= one_hour_ago
            ).count()
            
            health_status["components"]["activity"] = {
                "status": "healthy",
                "recent_calls_1h": recent_calls,
                "recent_messages_1h": recent_messages
            }
        except Exception as e:
            health_status["components"]["activity"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Determine overall status
        component_statuses = [comp["status"] for comp in health_status["components"].values()]
        
        if "error" in component_statuses:
            health_status["status"] = "unhealthy"
        elif "warning" in component_statuses:
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "healthy"
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }), 500

@health_production_bp.route("/api/health/readiness", methods=["GET"])
def readiness_check():
    """Readiness probe for production deployment"""
    try:
        # Critical readiness checks
        checks = {
            "database": False,
            "environment": False,
            "whatsapp": False
        }
        
        errors = []
        
        # Database check
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            checks["database"] = True
        except Exception as e:
            errors.append(f"Database: {e}")
        
        # Environment check  
        try:
            env_validation = validate_production_environment()
            checks["environment"] = env_validation["production_ready"]
            if not checks["environment"]:
                missing = env_validation["missing"]["core"] + env_validation["missing"]["whatsapp"]
                errors.append(f"Environment: Missing {missing}")
        except Exception as e:
            errors.append(f"Environment: {e}")
        
        # WhatsApp service check
        try:
            service = get_whatsapp_service()
            wa_status = service.get_status()
            checks["whatsapp"] = wa_status.get("configured", False)
            if not checks["whatsapp"]:
                errors.append("WhatsApp: Service not configured")
        except Exception as e:
            errors.append(f"WhatsApp: {e}")
        
        # Overall readiness
        ready = all(checks.values())
        
        response = {
            "ready": ready,
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if errors:
            response["errors"] = errors
        
        status_code = 200 if ready else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            "ready": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503

@health_production_bp.route("/api/health/liveness", methods=["GET"])
def liveness_check():
    """Liveness probe - basic application functionality"""
    try:
        # Minimal check that the application is running
        return jsonify({
            "alive": True,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": None  # Could track actual uptime if needed
        })
        
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return jsonify({
            "alive": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500