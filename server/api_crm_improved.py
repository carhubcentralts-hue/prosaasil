# server/api_crm_improved.py
from flask import Blueprint, request, jsonify
from server.authz import auth_required
import logging

crm_bp = Blueprint("crm", __name__, url_prefix="/api/crm")
log = logging.getLogger(__name__)

@crm_bp.get("/customers")
@auth_required
def list_customers():
    """Enhanced customer listing with search and pagination"""
    try:
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(max(int(request.args.get("limit", 25)), 1), 100)
    except ValueError:
        return jsonify({"error": "invalid paging"}), 400
    
    q = (request.args.get("q") or "").strip()
    
    # Mock data for now - replace with actual database queries
    mock_customers = [
        {
            "id": 1, 
            "name": "יוסי כהן", 
            "phone": "+972-50-123-4567",
            "email": "yossi@example.com",
            "status": "active",
            "created_at": "2024-01-15T10:00:00Z"
        },
        {
            "id": 2,
            "name": "שרה לוי",
            "phone": "+972-52-987-6543", 
            "email": "sarah@example.com",
            "status": "lead",
            "created_at": "2024-01-14T15:30:00Z"
        }
    ]
    
    # Apply search filter
    if q:
        filtered = [c for c in mock_customers 
                   if q.lower() in c["name"].lower() 
                   or q in c["phone"] 
                   or q.lower() in c["email"].lower()]
    else:
        filtered = mock_customers
    
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    items = filtered[start:end]
    
    return jsonify({
        "page": page,
        "limit": limit, 
        "total": total,
        "items": items
    }), 200

@crm_bp.post("/customers")
@auth_required  
def create_customer():
    """Create new customer"""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    
    # Mock customer creation
    new_customer = {
        "id": 999,  # Mock ID
        "name": data["name"],
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "status": "lead",
        "created_at": "2024-01-16T12:00:00Z"
    }
    
    log.info("Created customer: %s", new_customer["name"])
    return jsonify(new_customer), 201

@crm_bp.get("/customers/<int:customer_id>")
@auth_required
def get_customer(customer_id):
    """Get single customer details"""
    # Mock customer data
    if customer_id == 1:
        customer = {
            "id": 1,
            "name": "יוסי כהן",
            "phone": "+972-50-123-4567",
            "email": "yossi@example.com", 
            "status": "active",
            "created_at": "2024-01-15T10:00:00Z",
            "notes": "לקוח מעולה, מתעניין בדירות 4 חדרים"
        }
        return jsonify(customer), 200
    
    return jsonify({"error": "customer not found"}), 404

@crm_bp.put("/customers/<int:customer_id>")
@auth_required
def update_customer(customer_id):
    """Update customer information"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data provided"}), 400
    
    # Mock update
    updated_customer = {
        "id": customer_id,
        "name": data.get("name", "יוסי כהן"),
        "phone": data.get("phone", "+972-50-123-4567"),
        "email": data.get("email", "yossi@example.com"),
        "status": data.get("status", "active"),
        "updated_at": "2024-01-16T14:00:00Z"
    }
    
    log.info("Updated customer %d", customer_id)
    return jsonify(updated_customer), 200