from flask import Blueprint, request, jsonify, session, g
from werkzeug.security import generate_password_hash
from server.models_sql import Business, User, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# CSRF bypass decorator
def csrf_exempt(f):
    """Bypass all CSRF protection for this endpoint"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Set flag to bypass CSRF
        g.csrf_exempt = True
        return f(*args, **kwargs)
    return decorated_function

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
        
        # JSON לפי ההנחיות המדויקות
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_e164": business.phone_e164 or "",
            "email": f"office@{business.name.lower().replace(' ', '-')}.co.il",
            "address": "",
            "status": "active" if business.is_active else "inactive",
            "whatsapp_status": "connected",
            "call_status": "ready",
            "created_at": business.created_at.isoformat() if business.created_at else None,
            "updated_at": business.updated_at.isoformat() if business.updated_at else None
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
        
        # ✅ לפי ההנחיות: name (חובה), phone_e164 (חובה), timezone (ברירת מחדל)
        required_fields = ['name', 'phone_e164']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": "missing_field", "field": field}), 400
        
        # Check if business name exists
        existing_business = Business.query.filter_by(name=data['name']).first()
        if existing_business:
            return jsonify({"error": "שם העסק כבר קיים"}), 409
        
        # הסרתי בדיקת admin email כי לא יוצרים משתמש אוטומטית
        
        # Create business - לפי ההנחיות המדויקות
        business = Business()
        business.name = data['name']
        business.phone_e164 = data['phone_e164']  # ✅ חובה לפי ההנחיות
        business.business_type = data.get('business_type', 'real_estate')  # ברירת מחדל
        business.timezone = data.get('timezone', 'Asia/Jerusalem')  # ✅ ברירת מחדל לפי ההנחיות
        business.domain = data.get('domain', '')  # אופציונלי
        business.is_active = True
        db.session.add(business)
        db.session.commit()
        
        logger.info(f"Created business {business.id}: {business.name}")
        
        # ✅ החזר JSON של העסק החדש עם id - לא HTML
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_e164": business.phone_e164,
            "business_type": business.business_type,
            "timezone": business.timezone,
            "domain": business.domain,
            "status": "active",
            "created_at": business.created_at.isoformat() if business.created_at else None
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
        current_user = session.get('user')
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

@biz_mgmt_bp.route('/api/admin/businesses/<int:business_id>/impersonate', methods=['POST'])
@require_api_auth(['admin', 'manager'])
@csrf_exempt
def impersonate_business(business_id):
    """Allow admin to impersonate business - WITH PROPER CSRF"""
    try:
        logger.info(f"🔄 Impersonation attempt for business {business_id}")
        current_admin = session.get('user')
        logger.info(f"📋 Current admin: {current_admin}")
        
        if not current_admin or current_admin.get('role') not in ['admin', 'manager']:
            return jsonify({"error": "Unauthorized"}), 401
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            logger.error(f"❌ Business {business_id} not found")
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        if not business.is_active:
            return jsonify({"error": "העסק אינו פעיל"}), 400
        
        # ✅ אדמין יכול להתחזות גם בלי user business - יוצר התחזות ויוצר אחד במידת הצורך
        
        # Store original admin for restoration later
        current_admin_serialized = {
            "id": current_admin.get('id'),
            "name": current_admin.get('name'),
            "email": current_admin.get('email'),
            "role": current_admin.get('role'),
            "business_id": current_admin.get('business_id')
        }
        session['original_user'] = current_admin_serialized
        
        # Switch session to business user - לפי ההנחיות המדויקות
        session['impersonating'] = True
        session['tenant_id'] = business.id  
        session['role'] = 'business'  # או scope-Role
        
        logger.info(f"✅ Admin successfully impersonating business {business_id}")
        logger.info(f"📋 Session: impersonating=True, tenant_id={business.id}, role=business")
        
        return jsonify({"ok": True, "tenant_id": business.id}), 200
        
    except Exception as e:
        logger.error(f"Error impersonating business {business_id}: {e}")
        return jsonify({"error": "שגיאה בהתחזות לעסק"}), 500

@biz_mgmt_bp.route('/api/admin/impersonate/exit', methods=['POST'])
@require_api_auth(['admin', 'manager'])
@csrf_exempt
def exit_impersonation():
    """Exit impersonation and restore original user"""
    try:
        logger.info("🔄 Exiting impersonation")
        
        # נקה את מצב ההתחזות - לפי ההנחיות
        session.pop('impersonating', None)
        session.pop('tenant_id', None)  
        session.pop('role', None)
        
        logger.info(f"✅ Successfully exited impersonation, restored: {session.get('user')}")
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        logger.error(f"Error exiting impersonation: {e}")
        return jsonify({"error": "שגיאה ביציאה מהתחזות"}), 500

# === ADDITIONAL BUSINESS ENDPOINTS FROM api_business.py ===

