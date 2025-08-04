"""
Business Information API for React Frontend
פרטי עסק ונתונים בסיסיים
"""

from flask import request, jsonify
from app import app
from models import Business
import logging

logger = logging.getLogger(__name__)

@app.route("/api/business/info", methods=["GET"])
def api_get_business_info():
    """
    Get business information
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        business_info = {
            'id': business.id,
            'name': business.name,
            'business_type': business.business_type,
            'phone_number': business.phone_number,
            'whatsapp_number': business.whatsapp_number,
            'calls_enabled': business.calls_enabled,
            'whatsapp_enabled': business.whatsapp_enabled,
            'crm_enabled': business.crm_enabled,
            'is_active': business.is_active,
            'created_at': business.created_at.isoformat() if business.created_at else None,
            'updated_at': business.updated_at.isoformat() if business.updated_at else None,
            'users_count': 1,  # Simplified for now
            'plan_expires': '31/12/2024'  # Mock data for now
        }
        
        return jsonify(business_info)
        
    except Exception as e:
        logger.error(f"Error getting business info: {e}")
        return jsonify({"error": "Failed to get business info"}), 500

if __name__ == '__main__':
    print("✅ Business Info API routes loaded successfully")