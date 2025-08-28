from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from server.models_sql import Business, User, db
from server.routes_admin import require_api_auth
import logging

logger = logging.getLogger(__name__)

# Business Management Blueprint
biz_mgmt_bp = Blueprint('business_management', __name__)

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>', methods=['GET'])
@require_api_auth(['admin'])
def get_business(business_id):
    """Get business details"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "business_type": business.business_type,
            "is_active": business.is_active,
            "created_at": business.created_at.isoformat() if business.created_at else None
        })
    except Exception as e:
        logger.error(f"Error getting business {business_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת נתוני העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business', methods=['POST'])
@require_api_auth(['admin'])
def create_business():
    """Create new business with admin user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'business_type', 'admin_email', 'admin_password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"חסר שדה: {field}"}), 400
        
        # Check if business name exists
        existing_business = Business.query.filter_by(name=data['name']).first()
        if existing_business:
            return jsonify({"error": "שם העסק כבר קיים"}), 409
        
        # Check if admin email exists
        existing_user = User.query.filter_by(email=data['admin_email']).first()
        if existing_user:
            return jsonify({"error": "כתובת האימייל כבר רשומה במערכת"}), 409
        
        # Create business
        business = Business(
            name=data['name'],
            business_type=data['business_type'],
            is_active=True
        )
        db.session.add(business)
        db.session.flush()  # Get business ID
        
        # Create admin user for the business
        admin_user = User(
            email=data['admin_email'],
            name=data['name'] + ' - מנהל',
            password_hash=generate_password_hash(data['admin_password']),
            role='business',
            business_id=business.id
        )
        db.session.add(admin_user)
        db.session.commit()
        
        logger.info(f"Created business {business.id} with admin user {admin_user.id}")
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "business_type": business.business_type,
            "is_active": business.is_active
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating business: {e}")
        return jsonify({"error": "שגיאה ביצירת העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>', methods=['PUT'])
@require_api_auth(['admin'])
def update_business(business_id):
    """Update business details"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        data = request.get_json()
        
        # Update name if provided
        if 'name' in data and data['name']:
            # Check for duplicate names (excluding current business)
            existing = Business.query.filter(
                Business.name == data['name'],
                Business.id != business_id
            ).first()
            if existing:
                return jsonify({"error": "שם העסק כבר קיים"}), 409
            business.name = data['name']
        
        # Update business type if provided
        if 'business_type' in data and data['business_type']:
            business.business_type = data['business_type']
        
        # Update status if provided
        if 'is_active' in data:
            business.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        logger.info(f"Updated business {business_id}")
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "business_type": business.business_type,
            "is_active": business.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating business {business_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>/change-password', methods=['POST'])
@require_api_auth(['admin'])
def change_business_password(business_id):
    """Change password for business admin"""
    try:
        data = request.get_json()
        new_password = data.get('password')
        
        if not new_password or len(new_password) < 6:
            return jsonify({"error": "הסיסמה חייבת להכיל לפחות 6 תווים"}), 400
        
        # Find business admin user
        admin_user = User.query.filter_by(
            business_id=business_id,
            role='business'
        ).first()
        
        if not admin_user:
            return jsonify({"error": "לא נמצא מנהל לעסק זה"}), 404
        
        # Update password
        admin_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        logger.info(f"Changed password for business {business_id} admin")
        
        return jsonify({"success": True, "message": "סיסמה שונתה בהצלחה"})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error changing password for business {business_id}: {e}")
        return jsonify({"error": "שגיאה בשינוי הסיסמה"}), 500

@biz_mgmt_bp.route('/api/admin/login-as-business/<int:business_id>', methods=['POST'])
@require_api_auth(['admin'])
def login_as_business(business_id):
    """Allow admin to login as business"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        if not business.is_active:
            return jsonify({"error": "העסק אינו פעיל"}), 400
        
        # Find business admin user
        admin_user = User.query.filter_by(
            business_id=business_id,
            role='business'
        ).first()
        
        if not admin_user:
            return jsonify({"error": "לא נמצא מנהל לעסק זה"}), 404
        
        # Update session to login as business
        session["al_user"] = {
            "id": admin_user.id,
            "name": admin_user.name,
            "role": admin_user.role,
            "business_id": admin_user.business_id,
            "is_admin_login": True  # Mark this as admin login
        }
        
        logger.info(f"Admin logged in as business {business_id}")
        
        return jsonify({
            "success": True,
            "business": {
                "id": business.id,
                "name": business.name
            }
        })
        
    except Exception as e:
        logger.error(f"Error logging in as business {business_id}: {e}")
        return jsonify({"error": "שגיאה בהתחברות לעסק"}), 500