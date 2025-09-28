"""API Guard utility for ensuring consistent JSON responses and database transactions"""

from functools import wraps
from flask import jsonify, request, current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
try:
    from server.extensions import db
except ImportError:
    from extensions import db

def api_handler(fn):
    """
    Decorator that ensures:
    1. Always returns JSON (never HTML error pages)
    2. Proper database commit/rollback
    3. Consistent error handling
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            rv = fn(*args, **kwargs)
            # Handle Flask Response objects (already processed)
            if hasattr(rv, 'status_code'):  # Flask Response
                return rv
            if isinstance(rv, tuple):
                return rv
            return jsonify(rv if rv is not None else {"ok": True}), 200
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.exception("IntegrityError in API")
            return jsonify({"ok": False, "error": "integrity_error", "message": "שגיאה בשלמות הנתונים"}), 400
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("Database error in API")
            return jsonify({"ok": False, "error": "db_error", "message": "שגיאה בבסיס הנתונים"}), 500
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Unexpected API error")
            return jsonify({"ok": False, "error": "server_error", "message": "שגיאת שרת"}), 500
    return wrapper