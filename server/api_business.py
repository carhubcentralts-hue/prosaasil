from flask import Blueprint, request, jsonify, session
from server.authz import auth_required, roles_required
import logging, datetime

biz_bp = Blueprint("business", __name__, url_prefix="/api/businesses")
audit = logging.getLogger("audit.business")

# Mock database for businesses - replace with real database later
MOCK_BUSINESSES = [
    {
        "id": 1, 
        "name": "שי דירות ומשרדים בע״מ", 
        "domain": "shai-realestate.co.il", 
        "active": True,
        "created_at": "2024-01-01T10:00:00Z"
    },
    {
        "id": 2, 
        "name": "נדל״ן יוקרה בע״מ", 
        "domain": "luxury-realestate.co.il", 
        "active": True,
        "created_at": "2024-01-05T14:30:00Z"
    }
]

@biz_bp.get("")
@auth_required
def list_businesses():
    """List all businesses"""
    # Sort by creation date (newest first)
    sorted_businesses = sorted(MOCK_BUSINESSES, key=lambda x: x["created_at"], reverse=True)
    return jsonify(sorted_businesses), 200

@biz_bp.post("")
@roles_required("admin")
def create_business():
    """Create new business"""
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    
    if not name:
        return jsonify({"error": "name required"}), 400
    
    # Check for duplicate names
    if any(b["name"] == name for b in MOCK_BUSINESSES):
        return jsonify({"error": "name exists"}), 409
    
    domain = (data.get("domain") or "").strip() or None
    new_id = max(b["id"] for b in MOCK_BUSINESSES) + 1 if MOCK_BUSINESSES else 1
    
    new_business = {
        "id": new_id,
        "name": name,
        "domain": domain,
        "active": True,
        "created_at": datetime.datetime.now().isoformat() + "Z"
    }
    
    MOCK_BUSINESSES.append(new_business)
    
    user_email = session.get("user", {}).get("email", "unknown")
    audit.info("BUSINESS_CREATE id=%s name=%s by=%s", new_id, name, user_email)
    
    return jsonify(new_business), 201

@biz_bp.put("/<int:bid>")
@roles_required("admin")
def update_business(bid):
    """Update business"""
    # Find business
    business = next((b for b in MOCK_BUSINESSES if b["id"] == bid), None)
    if not business:
        return jsonify({"error": "business not found"}), 404
    
    data = request.get_json(force=True)
    
    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name:
            return jsonify({"error": "invalid name"}), 400
        
        # Check for duplicate names
        if new_name != business["name"] and any(b["name"] == new_name for b in MOCK_BUSINESSES):
            return jsonify({"error": "name exists"}), 409
        
        business["name"] = new_name
    
    if "domain" in data:
        business["domain"] = (data["domain"] or "").strip() or None
    
    user_email = session.get("user", {}).get("email", "unknown")
    audit.info("BUSINESS_UPDATE id=%s fields=%s by=%s", bid, list(data.keys()), user_email)
    
    return jsonify(business), 200

@biz_bp.post("/<int:bid>/deactivate")
@roles_required("admin")
def deactivate_business(bid):
    """Deactivate business"""
    business = next((b for b in MOCK_BUSINESSES if b["id"] == bid), None)
    if not business:
        return jsonify({"error": "business not found"}), 404
    
    business["active"] = False
    
    user_email = session.get("user", {}).get("email", "unknown")
    audit.info("BUSINESS_DEACTIVATE id=%s by=%s", bid, user_email)
    
    return jsonify(business), 200

@biz_bp.post("/<int:bid>/reactivate")
@roles_required("admin")
def reactivate_business(bid):
    """Reactivate business"""
    business = next((b for b in MOCK_BUSINESSES if b["id"] == bid), None)
    if not business:
        return jsonify({"error": "business not found"}), 404
    
    business["active"] = True
    
    user_email = session.get("user", {}).get("email", "unknown")
    audit.info("BUSINESS_REACTIVATE id=%s by=%s", bid, user_email)
    
    return jsonify(business), 200

@biz_bp.delete("/<int:bid>")
@roles_required("admin")
def delete_business(bid):
    """Delete business"""
    business = next((b for b in MOCK_BUSINESSES if b["id"] == bid), None)
    if not business:
        return jsonify({"error": "business not found"}), 404
    
    business["active"] = False  # Soft delete
    
    user_email = session.get("user", {}).get("email", "unknown")
    audit.info("BUSINESS_DELETE id=%s by=%s", bid, user_email)
    
    return jsonify({"ok": True}), 200