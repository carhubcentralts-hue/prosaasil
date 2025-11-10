# server/spa_static.py
from flask import Blueprint, send_from_directory, request, make_response, abort
from pathlib import Path

spa_bp = Blueprint("spa", __name__)
DIST = Path(__file__).resolve().parents[1] / "dist"

@spa_bp.get("/assets/<path:filename>")
def assets(filename):
    resp = make_response(send_from_directory(DIST / "assets", filename))
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # Ensure correct MIME types
    if filename.endswith('.js'):
        resp.headers['Content-Type'] = 'application/javascript'
    elif filename.endswith('.css'):
        resp.headers['Content-Type'] = 'text/css'
    return resp

@spa_bp.get("/")
@spa_bp.get("/<path:path>")
def spa(path=""):
    # אל תתפוס API/סטטי/ווב-הוקים
    blocked = ("api/", "assets/", "static/", "webhook/", "favicon", "robots")
    if path.startswith(blocked):
        abort(404)
    resp = make_response(send_from_directory(DIST, "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp