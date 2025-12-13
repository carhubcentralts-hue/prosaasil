# server/error_handlers.py
import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import OperationalError, DisconnectionError
import psycopg2

from server.utils.db_health import is_neon_error, log_db_error

log = logging.getLogger("errors")

def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http(e: HTTPException):
        # JSON for API/Webhooks; allow SPA to handle others
        payload = {"error": e.name, "status": e.code, "path": request.path}
        log.warning("HTTP %s %s -> %s", request.method, request.path, e.code)
        if request.path.startswith(("/api", "/webhook")):
            return jsonify(payload), e.code
        return (f"{e.code} {e.name}", e.code)

    @app.errorhandler(OperationalError)
    def handle_db_operational_error(e: OperationalError):
        """Handle DB connectivity errors - return 503 Service Unavailable"""
        
        log_db_error(e, context=f"{request.method} {request.path}")
        
        if is_neon_error(e):
            log.error(f"[DB_DOWN] Neon endpoint disabled during {request.method} {request.path}")
            detail = "Database temporarily unavailable (endpoint disabled)"
        else:
            log.error(f"[DB_DOWN] Database operational error during {request.method} {request.path}")
            detail = "Database temporarily unavailable"
        
        payload = {
            "error": "SERVICE_UNAVAILABLE",
            "detail": detail,
            "status": 503,
            "path": request.path
        }
        
        # Try to rollback to clean up session
        try:
            from server.db import db
            db.session.rollback()
        except:
            pass
        
        if request.path.startswith(("/api", "/webhook")):
            return jsonify(payload), 503
        return ("Service Unavailable - Database temporarily offline", 503)

    @app.errorhandler(DisconnectionError)
    def handle_db_disconnection_error(e: DisconnectionError):
        """Handle DB disconnection errors - return 503 Service Unavailable"""
        log.error(f"[DB_DOWN] Database disconnection during {request.method} {request.path}: {e}")
        
        payload = {
            "error": "SERVICE_UNAVAILABLE",
            "detail": "Database connection lost",
            "status": 503,
            "path": request.path
        }
        
        # Try to rollback to clean up session
        try:
            from server.db import db
            db.session.rollback()
        except:
            pass
        
        if request.path.startswith(("/api", "/webhook")):
            return jsonify(payload), 503
        return ("Service Unavailable - Database connection lost", 503)

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        # Check if it's a psycopg2 OperationalError (lower level than SQLAlchemy)
        if isinstance(e, psycopg2.OperationalError):
            log_db_error(e, context=f"{request.method} {request.path}")
            
            payload = {
                "error": "SERVICE_UNAVAILABLE",
                "detail": "Database temporarily unavailable",
                "status": 503,
                "path": request.path
            }
            
            # Try to rollback
            try:
                from server.db import db
                db.session.rollback()
            except:
                pass
            
            if request.path.startswith(("/api", "/webhook")):
                return jsonify(payload), 503
            return ("Service Unavailable - Database temporarily offline", 503)
        
        log.exception("UNHANDLED %s %s", request.method, request.path)
        payload = {"error": "internal", "status": 500, "path": request.path}
        if request.path.startswith(("/api", "/webhook")):
            return jsonify(payload), 500
        return ("Internal Server Error", 500)