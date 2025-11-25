# server/error_handlers.py
import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

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

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        log.exception("UNHANDLED %s %s", request.method, request.path)
        payload = {"error": "internal", "status": 500, "path": request.path}
        if request.path.startswith(("/api", "/webhook")):
            return jsonify(payload), 500
        return ("Internal Server Error", 500)