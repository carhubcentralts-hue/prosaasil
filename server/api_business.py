from flask import Blueprint, request, jsonify
from server.authz import auth_required, roles_required
try:
    from server.models import db, Business
except ImportError:
    # Fallback if models not available
    db = None
    Business = None

biz_bp = Blueprint("business", __name__, url_prefix="/api/businesses")

@biz_bp.get("")
@auth_required
def list_businesses():
    if not Business:
        return jsonify([]), 200
    items = Business.query.order_by(Business.created_at.desc()).all()
    return jsonify([b.to_dict() for b in items]), 200

@biz_bp.post("")
@roles_required("admin")
def create_business():
    if not Business:
        return jsonify({"error": "Business model not available"}), 501
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error":"name required"}), 400
    if Business.query.filter_by(name=name).first():
        return jsonify({"error":"name exists"}), 409
    b = Business(name=name, domain=(data.get("domain") or "").strip() or None)
    db.session.add(b); db.session.commit()
    return jsonify(b.to_dict()), 201

@biz_bp.put("/<int:bid>")
@roles_required("admin")
def update_business(bid):
    if not Business:
        return jsonify({"error": "Business model not available"}), 501
    b = Business.query.get_or_404(bid)
    data = request.get_json(force=True)
    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name: return jsonify({"error":"invalid name"}), 400
        if new_name != b.name and Business.query.filter_by(name=new_name).first():
            return jsonify({"error":"name exists"}), 409
        b.name = new_name
    if "domain" in data:
        b.domain = (data["domain"] or "").strip() or None
    db.session.commit()
    return jsonify(b.to_dict()), 200

@biz_bp.post("/<int:bid>/deactivate")
@roles_required("admin")
def deactivate_business(bid):
    if not Business:
        return jsonify({"error": "Business model not available"}), 501
    b = Business.query.get_or_404(bid); b.active = False; db.session.commit()
    return jsonify(b.to_dict()), 200

@biz_bp.post("/<int:bid>/reactivate")
@roles_required("admin")
def reactivate_business(bid):
    if not Business:
        return jsonify({"error": "Business model not available"}), 501
    b = Business.query.get_or_404(bid); b.active = True; db.session.commit()
    return jsonify(b.to_dict()), 200

@biz_bp.delete("/<int:bid>")
@roles_required("admin")
def delete_business(bid):
    if not Business:
        return jsonify({"error": "Business model not available"}), 501
    # Soft delete preferred; if you really need hard delete, ensure FK handling first.
    b = Business.query.get_or_404(bid)
    b.active = False
    db.session.commit()
    return jsonify({"ok": True}), 200