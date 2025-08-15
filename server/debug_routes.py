"""
Debug routes לזיהוי כפילויות ובדיקת מסלולים
"""
from flask import Blueprint, jsonify, current_app

debug_bp = Blueprint("debug_bp", __name__)

@debug_bp.route("/__debug/routes", methods=["GET"])
def list_routes():
    """רשימת כל המסלולים הרשומים - לזיהוי כפילויות"""
    items = []
    for r in current_app.url_map.iter_rules():
        methods = [m for m in (r.methods or []) if m not in ("HEAD", "OPTIONS")]
        items.append({
            "rule": str(r), 
            "endpoint": r.endpoint or "",
            "methods": sorted(methods)
        })
    items.sort(key=lambda x: x["rule"])
    return jsonify(items)

@debug_bp.route("/__debug/webhooks", methods=["GET"])
def list_webhooks():
    """רק webhook routes - לבדיקה מהירה"""
    items = []
    for r in current_app.url_map.iter_rules():
        if "/webhook/" in str(r):
            methods = [m for m in (r.methods or []) if m not in ("HEAD", "OPTIONS")]
            items.append({
                "rule": str(r), 
                "endpoint": r.endpoint or "",
                "methods": sorted(methods)
            })
    return jsonify(items)