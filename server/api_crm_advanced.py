# server/api_crm_advanced.py (or your CRM file)
from flask import Blueprint, request, jsonify
from server.authz import auth_required, roles_required
try:
    from server.models import db, Customer  # adapt names
except ImportError:
    # Fallback if models not available
    db = None
    Customer = None

crm_bp = Blueprint("crm", __name__, url_prefix="/api/crm")

@crm_bp.get("/customers")
@auth_required
def list_customers():
    try:
        page  = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 25)), 1), 100)
    except ValueError:
        return jsonify({"error":"invalid paging"}), 400

    q = (request.args.get("q") or "").strip()
    
    # For now, return empty if no Customer model
    if not Customer:
        return jsonify({
            "page": page,
            "limit": limit,
            "total": 0,
            "items": []
        }), 200
    
    # When you have a real Customer model, use this pattern:
    # query = Customer.query
    # if q:
    #     like = f"%{q}%"
    #     query = query.filter(
    #         (Customer.name.ilike(like)) |
    #         (Customer.phone.ilike(like)) |
    #         (Customer.email.ilike(like))
    #     )
    #
    # total = query.count()
    # items = (query.order_by(Customer.created_at.desc())
    #               .offset((page-1)*limit)
    #               .limit(limit)
    #               .all())
    # return jsonify({
    #     "page": page,
    #     "limit": limit,
    #     "total": total,
    #     "items": [c.to_dict() for c in items]
    # }), 200
    
    # Placeholder response
    return jsonify({
        "page": page,
        "limit": limit,
        "total": 0,
        "items": []
    }), 200