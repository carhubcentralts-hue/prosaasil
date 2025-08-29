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
        logger.info(f"Looking for business with ID: {business_id}")
        business = Business.query.filter_by(id=business_id).first()
        logger.info(f"Found business: {business}")
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
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"שגיאה בטעינת נתוני העסק: {str(e)}"}), 500

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
        business = Business()
        business.name = data['name']
        business.business_type = data['business_type'] 
        business.is_active = True
        db.session.add(business)
        db.session.flush()  # Get business ID
        
        # Create admin user for the business
        admin_user = User()
        admin_user.email = data['admin_email']
        admin_user.name = data['name'] + ' - מנהל'
        admin_user.password_hash = generate_password_hash(data['admin_password'])
        admin_user.role = 'business'
        admin_user.business_id = business.id
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

# =============================================================================
# USER MANAGEMENT ENDPOINTS (Admin Only)
# =============================================================================

@biz_mgmt_bp.route('/api/admin/user', methods=['POST'])
@require_api_auth(['admin'])
def create_user():
    """Create new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"חסר שדה: {field}"}), 400
        
        # Check if email exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({"error": "כתובת האימייל כבר רשומה במערכת"}), 409
        
        # Create user
        user = User()
        user.email = data['email']
        user.name = data['name']
        user.password_hash = generate_password_hash(data['password'])
        user.role = data['role']
        user.business_id = data.get('business_id') if data['role'] == 'business' else None
        user.is_active = True
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"Created user {user.id} by admin")
        
        return jsonify({
            "success": True,
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {e}")
        return jsonify({"error": "שגיאה ביצירת המשתמש"}), 500

@biz_mgmt_bp.route('/api/admin/user/<int:user_id>', methods=['GET'])
@require_api_auth(['admin'])
def get_user(user_id):
    """Get user details"""
    try:
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        return jsonify({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "business_id": user.business_id,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None
        })
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({"error": "שגיאה בטעינת נתוני המשתמש"}), 500

@biz_mgmt_bp.route('/api/admin/user/<int:user_id>', methods=['PUT'])
@require_api_auth(['admin'])
def update_user(user_id):
    """Update user details"""
    try:
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            user.name = data['name']
        if 'email' in data:
            # Check if email is already taken by another user
            existing = User.query.filter_by(email=data['email']).filter(User.id != user_id).first()
            if existing:
                return jsonify({"error": "כתובת האימייל כבר רשומה למשתמש אחר"}), 409
            user.email = data['email']
        if 'role' in data:
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        db.session.commit()
        
        logger.info(f"Updated user {user_id} by admin")
        
        return jsonify({
            "success": True,
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating user {user_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון המשתמש"}), 500

@biz_mgmt_bp.route('/api/admin/user/<int:user_id>/change-password', methods=['POST'])
@require_api_auth(['admin'])
def change_user_password(user_id):
    """Change user password"""
    try:
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        data = request.get_json()
        new_password = data.get('password')
        
        if not new_password or len(new_password) < 6:
            return jsonify({"error": "הסיסמה חייבת להכיל לפחות 6 תווים"}), 400
        
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        logger.info(f"Changed password for user {user_id} by admin")
        
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error changing password for user {user_id}: {e}")
        return jsonify({"error": "שגיאה בשינוי הסיסמה"}), 500

@biz_mgmt_bp.route('/api/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@require_api_auth(['admin'])
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        # Don't allow disabling the current admin user
        current_user = session.get('al_user')
        if current_user and current_user.get('id') == user_id:
            return jsonify({"error": "לא ניתן להשהות את המשתמש הנוכחי"}), 400
        
        user.is_active = not user.is_active
        db.session.commit()
        
        status = "הופעל" if user.is_active else "הושהה"
        logger.info(f"User {user_id} {status} by admin")
        
        return jsonify({"success": True, "is_active": user.is_active})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling status for user {user_id}: {e}")
        return jsonify({"error": "שגיאה בשינוי סטטוס המשתמש"}), 500

@biz_mgmt_bp.route('/api/admin/login-as-business/<int:business_id>', methods=['POST'])
@require_api_auth(['admin'])
def login_as_business(business_id):
    """Allow admin to login as business"""
    try:
        business = Business.query.filter_by(id=business_id).first()
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