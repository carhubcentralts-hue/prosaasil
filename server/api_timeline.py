from flask import Blueprint, jsonify, request

timeline_bp = Blueprint("timeline_bp", __name__, url_prefix="/api")

@timeline_bp.get("/customers/<int:customer_id>/timeline")
def customer_timeline(customer_id):
    # בהמשך: למשוך אמיתי מה-DB. כרגע החזר מבנה תקין.
    return jsonify({"items": []})