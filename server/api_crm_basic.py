from flask import Blueprint, jsonify, request
from server.api_pagination import paginate_query, pagination_response
import logging

crm_basic_bp = Blueprint("crm_basic_bp", __name__, url_prefix="/api/crm")
log = logging.getLogger("api.crm.basic")

@crm_basic_bp.get("/customers")
def customers_list():
    """Basic customers endpoint for testing - PUBLIC ACCESS for development"""
    try:
        # Mock data for now - replace with real database queries
        mock_customers = [
            {"id": 1, "name": "משה כהן", "phone": "+972501234567", "email": "moshe@example.com", "status": "פעיל"},
            {"id": 2, "name": "שרה לוי", "phone": "+972502345678", "email": "sara@example.com", "status": "פעיל"},
            {"id": 3, "name": "דוד רוזן", "phone": "+972503456789", "email": "david@example.com", "status": "לא פעיל"},
        ]
        
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
        
        results, page, pages, total = paginate_query(mock_customers, page, limit)
        
        return jsonify(pagination_response(results, page, pages, total))
        
    except Exception as e:
        log.error(f"Error fetching customers: {e}")
        return jsonify({"error": "Failed to fetch customers"}), 500