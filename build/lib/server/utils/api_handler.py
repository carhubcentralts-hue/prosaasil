# server/utils/api_handler.py - שלב 3: JSON יציב ו-commit/rollback
from functools import wraps
from flask import jsonify
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from server.db import db

def api_handler(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        try:
            rv = fn(*a, **kw)
            if isinstance(rv, tuple): 
                return rv
            return jsonify(rv if rv is not None else {"ok": True}), 200
        except IntegrityError:
            db.session.rollback()
            return jsonify({"ok": False, "error": "integrity"}), 400
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({"ok": False, "error": "db"}), 500
        except Exception:
            db.session.rollback()
            return jsonify({"ok": False, "error": "server"}), 500
    return wrapper