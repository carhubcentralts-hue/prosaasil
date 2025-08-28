# server/routes_auth.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, session, g, current_app
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import os, time, jwt
from server.models_sql import User, Business
from server.db import db

auth_bp = Blueprint("auth_bp", __name__)

# === קונפיג בסיסי ===
SECRET_KEY = os.getenv("SECRET_KEY", "please-change-me")
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
PASSWORD_RESET_SALT = os.getenv("PASSWORD_RESET_SALT", "al-reset-2025")
RESET_TOKEN_TTL_SEC = int(os.getenv("RESET_TOKEN_TTL_SEC", "1800"))  # 30 דקות

# itsdangerous serializer לאיפוס סיסמה
reset_serializer = URLSafeTimedSerializer(SECRET_KEY, salt=PASSWORD_RESET_SALT)

# ---- DAO implementation using SQLAlchemy models ----
class dao_users:
    @staticmethod
    def get_by_email(email: str):
        """Get user by email"""
        user = User.query.filter_by(email=email, is_active=True).first()
        if user:
            return {
                "id": user.id,
                "name": user.username or user.email,
                "role": user.role,
                "business_id": user.business_id,
                "password_hash": user.password_hash,
                "email": user.email
            }
        return None

    @staticmethod
    def get_by_id(user_id: str):
        """Get user by ID"""
        user = User.query.get(user_id)
        if user and user.is_active:
            return {
                "id": user.id,
                "name": user.username or user.email,
                "role": user.role,
                "business_id": user.business_id,
                "password_hash": user.password_hash,
                "email": user.email
            }
        return None

    @staticmethod
    def update_password_hash(user_id: str, pwhash: str):
        """Update user password hash"""
        try:
            user = User.query.get(user_id)
            if user:
                user.password_hash = pwhash
                db.session.commit()
                return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update password for user {user_id}: {e}")
        return False


# ---- טעינת משתמש פעיל לכל בקשה (Session/JWT) ----
def load_current_user():
    g.user = session.get("al_user")
    token = session.get("al_token")
    g.token = token
    # תמיכה גם ב-Bearer (אם בחרת לשים JWT בלוקאל):
    if not g.user:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            tok = authz.split(" ", 1)[1].strip()
            try:
                payload = jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
                g.user = {
                    "id": payload.get("uid"),
                    "name": payload.get("name"),
                    "role": payload.get("role"),
                    "business_id": payload.get("business_id"),
                }
            except Exception:
                g.user = None


def require_api_auth(roles: list[str] | None = None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(g, "user", None):
                return jsonify({"error": "unauthorized"}), 401
            if roles and g.user.get("role") not in roles:
                return jsonify({"error": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ---- LOGIN ----
@auth_bp.post("/api/auth/login")
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "missing fields"}), 400

    u = dao_users.get_by_email(email)
    if not u or not check_password_hash(u.get("password_hash", ""), password):
        # מסר ניטרלי – בלי לגלות אם האימייל קיים
        return jsonify({"error": "invalid credentials"}), 401

    # צור JWT (אופציונלי; אם עובדים עם session בלבד – אפשר לוותר)
    payload = {
        "uid": u["id"],
        "name": u.get("name", ""),
        "role": u.get("role", "agent"),
        "business_id": u.get("business_id"),
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 24 * 7,  # שבוע
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # שמור session (מאפשר HttpOnly cookie בצד השרת)
    session["al_user"] = {
        "id": u["id"],
        "name": u.get("name"),
        "role": u.get("role"),
        "business_id": u.get("business_id"),
    }
    session["al_token"] = token

    return jsonify({
        "user": session["al_user"],
        "token": token,  # אם בצד לקוח עובדים עם HttpOnly בלבד – אפשר לא לשלוח
        "success": True
    })


@auth_bp.post("/api/auth/logout")
def api_logout():
    session.pop("al_user", None)
    session.pop("al_token", None)
    # Clear old session keys too
    session.pop("user", None)
    session.pop("token", None)
    return jsonify({"ok": True})


@auth_bp.get("/api/auth/me")
@require_api_auth()
def api_me():
    return jsonify({"user": g.user})


# ---- FORGOT ----
@auth_bp.post("/api/auth/forgot")
def api_forgot():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"ok": True})  # תמיד ניטרלי

    u = dao_users.get_by_email(email)
    if u:
        token = reset_serializer.dumps({"uid": u["id"], "email": email})
        # שלח מייל / WhatsApp / SMS עם הקישור:
        reset_link = f'{request.host_url.rstrip("/")}/reset?token={token}'
        current_app.logger.info("PASSWORD_RESET for %s -> %s", email, reset_link)
        # TODO: חבר ל-mailer האמיתי; בזמן פיתוח – מספיקה הלוגה

    return jsonify({"ok": True})


# ---- RESET ----
@auth_bp.post("/api/auth/reset")
def api_reset():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("token") or ""
    new_password = data.get("password") or ""
    if not token or len(new_password) < 8:
        return jsonify({"error": "bad request"}), 400
    try:
        payload = reset_serializer.loads(token, max_age=RESET_TOKEN_TTL_SEC)
    except SignatureExpired:
        return jsonify({"error": "token expired"}), 400
    except BadSignature:
        return jsonify({"error": "invalid token"}), 400

    uid = payload.get("uid")
    if not uid:
        return jsonify({"error": "invalid token"}), 400

    pwhash = generate_password_hash(new_password)
    ok = dao_users.update_password_hash(uid, pwhash)
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "update failed"}), 500))