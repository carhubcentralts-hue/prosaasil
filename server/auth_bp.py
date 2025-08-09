# server/auth_bp.py
from flask import Blueprint, request, jsonify, session
import os, hmac, hashlib

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "")  # sha256 של הסיסמה

def _ok(p: str):
    h = hashlib.sha256(p.encode()).hexdigest()
    return hmac.compare_digest(h, ADMIN_PASS_HASH)

@auth_bp.post("/login")
def login():
    data = request.get_json(force=True)
    if data.get("email")==ADMIN_EMAIL and _ok(data.get("password","")):
        session["user"] = {"email": ADMIN_EMAIL}
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error":"invalid"}), 401

@auth_bp.get("/me")
def me(): return jsonify(session.get("user") or {}), 200

@auth_bp.post("/logout")
def logout():
    session.clear(); return jsonify({"ok": True})