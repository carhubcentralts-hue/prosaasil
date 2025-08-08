"""
AgentLocator v39 - Production Error Handlers
מטפלי שגיאות ברמה פרודקציונית עם לוגינג מלא
"""

from flask import jsonify, request
import traceback

def register_error_handlers(app):
    """Register production-grade error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        app.logger.warning(f"400 Bad Request: {request.url} - {error}")
        return jsonify({
            "error": "bad_request", 
            "message": "הבקשה שלך אינה תקינה"
        }), 400
    
    @app.errorhandler(401) 
    def unauthorized(error):
        app.logger.warning(f"401 Unauthorized: {request.url} - {error}")
        return jsonify({
            "error": "unauthorized",
            "message": "נדרשת התחברות"
        }), 401
        
    @app.errorhandler(403)
    def forbidden(error):
        app.logger.warning(f"403 Forbidden: {request.url} - {error}")
        return jsonify({
            "error": "forbidden",
            "message": "אין לך הרשאה לבצע פעולה זו"
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        app.logger.info(f"404 Not Found: {request.url}")
        return jsonify({
            "error": "not_found",
            "message": "המשאב המבוקש לא נמצא"
        }), 404
    
    @app.errorhandler(429)
    def too_many_requests(error):
        app.logger.warning(f"429 Rate Limited: {request.url} - {error}")
        return jsonify({
            "error": "rate_limited",
            "message": "יותר מדי בקשות - נסה שוב מאוחר יותר"
        }), 429
        
    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.exception("Unhandled server error")
        app.logger.error(f"500 Internal Error: {request.url}")
        app.logger.error(f"Error details: {str(error)}")
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            "error": "server_error",
            "message": "אירעה שגיאת שרת פנימית"
        }), 500
    
    @app.errorhandler(502)
    def bad_gateway(error):
        app.logger.error(f"502 Bad Gateway: {request.url} - {error}")
        return jsonify({
            "error": "bad_gateway", 
            "message": "שגיאה בתקשורת עם שירות חיצוני"
        }), 502
        
    @app.errorhandler(503)
    def service_unavailable(error):
        app.logger.error(f"503 Service Unavailable: {request.url} - {error}")
        return jsonify({
            "error": "service_unavailable",
            "message": "השירות אינו זמין כעת"
        }), 503
        
    # Handle database connection errors
    @app.errorhandler(Exception)
    def handle_database_errors(error):
        if "database" in str(error).lower() or "connection" in str(error).lower():
            app.logger.error(f"Database error: {str(error)}")
            return jsonify({
                "error": "database_error",
                "message": "שגיאה בחיבור למסד הנתונים"
            }), 503
        
        # Re-raise for other exception handlers
        raise error
    
    app.logger.info("✅ Production error handlers registered")