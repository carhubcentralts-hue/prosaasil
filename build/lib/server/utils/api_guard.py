# server/utils/api_guard.py
from functools import wraps
from flask import jsonify, request, current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from server.db import db

def api_handler(fn):
    @wraps(fn)
    def w(*a, **kw):
        try:
            rv = fn(*a, **kw)
            if isinstance(rv, tuple): return rv
            return jsonify(rv if rv is not None else {"ok": True}), 200
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.exception("IntegrityError")
            return jsonify({"ok": False, "error": "integrity", "detail": str(e.orig)}), 400
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("DBError")
            return jsonify({"ok": False, "error": "db", "detail": str(e)}), 500
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"APIError in {fn.__name__}: {str(e)}")
            return jsonify({"ok": False, "error": "server", "detail": str(e)}), 500
    return w