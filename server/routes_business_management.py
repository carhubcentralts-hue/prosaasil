from flask import Blueprint, request, jsonify, session, g
from werkzeug.security import generate_password_hash
from server.models_sql import Business, User, BusinessSettings, FAQ, db
from datetime import datetime
from server.routes_admin import require_api_auth
from server.extensions import csrf
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# REMOVED custom csrf_exempt decorator - using proper @csrf.exempt from SeaSurf only where needed

def normalize_patterns(payload):
    """
    Normalize patterns_json to ensure it's always a List[str]
    
    Handles:
    - None/null → []
    - String (JSON or plain text) → parse and extract list
    - List → validate and clean
    - Empty strings/whitespace → []
    
    Returns: List[str] or raises ValueError
    """
    import json
    
    if payload is None or payload == "":
        return []
    
    if isinstance(payload, list):
        cleaned = [str(p).strip() for p in payload if p and str(p).strip()]
        return cleaned
    
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return []
        
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                cleaned = [str(p).strip() for p in parsed if p and str(p).strip()]
                return cleaned
            else:
                raise ValueError(f"patterns_json must be a list, got {type(parsed).__name__}")
        except json.JSONDecodeError as e:
            raise ValueError(f"patterns_json is not valid JSON: {e}")
    
    raise ValueError(f"patterns_json must be a list or JSON string, got {type(payload).__name__}")

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
        
        # JSON לפי ההנחיות המדויקות + ALL fields
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_e164": business.phone_e164 or "",
            "whatsapp_number": business.whatsapp_number or "",
            "greeting_message": business.greeting_message or "",
            "whatsapp_greeting": business.whatsapp_greeting or "",
            "system_prompt": business.system_prompt or "",
            "voice_message": business.voice_message or "",
            "working_hours": business.working_hours or "08:00-18:00",
            "phone_permissions": business.phone_permissions,
            "whatsapp_permissions": business.whatsapp_permissions,
            "calls_enabled": business.calls_enabled,
            "crm_enabled": business.crm_enabled,
            "whatsapp_enabled": business.whatsapp_enabled,
            "payments_enabled": business.payments_enabled,
            "default_provider": business.default_provider or "paypal",
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
@require_api_auth(['system_admin'])  # BUILD 138: Only system_admin can create businesses
def create_business():
    """Create new business with admin user"""
    try:
        data = request.get_json()
        
        # ✅ לפי ההנחיות: name (חובה), phone_e164 (חובה), timezone (ברירת מחדל)
        required_fields = ['name', 'phone_e164']  # השם שהפרונטאנד שולח
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": "missing_field", "field": field}), 400
        
        # Check if business name exists
        existing_business = Business.query.filter_by(name=data['name']).first()
        if existing_business:
            return jsonify({"error": "שם העסק כבר קיים"}), 409
        
        # ✅ Validate owner email and password (required for auto-create)
        owner_email = data.get('owner_email')
        owner_password = data.get('owner_password')
        owner_name = data.get('owner_name', data['name'] + ' - Owner')
        
        if not owner_email or not owner_password:
            return jsonify({"error": "owner_email וowner_password נדרשים ליצירת עסק"}), 400
        
        if len(owner_password) < 6:
            return jsonify({"error": "הסיסמה חייבת להכיל לפחות 6 תווים"}), 400
        
        # Check if owner email already exists
        existing_user = User.query.filter_by(email=owner_email).first()
        if existing_user:
            return jsonify({"error": "כתובת האימייל של הבעלים כבר רשומה במערכת"}), 409
        
        # ✅ ATOMIC TRANSACTION: Create business + owner together
        try:
            # Create business - לפי ההנחיות המדויקות + ALL required fields
            business = Business()
            business.name = data['name']
            business.phone_e164 = data['phone_e164']  # השם שהפרונטאנד שולח
            business.business_type = data.get('business_type', 'real_estate')  # ברירת מחדל
            business.is_active = True
            
            # Set ALL required fields to prevent NOT NULL constraint violations
            business.whatsapp_number = data.get('whatsapp_number', data['phone_e164'])  # Default to same phone
            business.greeting_message = data.get('greeting_message', "שלום! איך אפשר לעזור?")
            business.whatsapp_greeting = data.get('whatsapp_greeting', "שלום! איך אפשר לעזור?")
            business.system_prompt = data.get('system_prompt', f"אתה עוזר נדל\"ן מקצועי ב{{{{business_name}}}}. תפקידך לעזור ללקוחות למצוא נכסים.")  # ✅ עם placeholder!
            business.voice_message = data.get('voice_message', f"שלום מ{{{{business_name}}}}")
            business.working_hours = data.get('working_hours', "08:00-18:00")
            business.phone_permissions = True
            business.whatsapp_permissions = True
            business.calls_enabled = True
            business.crm_enabled = True
            business.whatsapp_enabled = True
            business.payments_enabled = False
            business.default_provider = "paypal"
            
            db.session.add(business)
            db.session.flush()  # Get business.id WITHOUT committing yet
            
            logger.info(f"Creating business {business.name} with owner {owner_email}")
            
            # AUTO-CREATE OWNER USER for new business (same transaction)
            owner_user = User(
                email=owner_email,
                password_hash=generate_password_hash(owner_password, method='scrypt'),
                name=owner_name,
                role='owner',
                business_id=business.id,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(owner_user)
            
            # ✅ SINGLE COMMIT: Both business + owner atomically
            db.session.commit()
            logger.info(f"✅ Created business {business.id}: {business.name} with owner {owner_email}")
        except Exception as error:
            # Rollback BOTH business and owner if anything fails
            db.session.rollback()
            logger.error(f"Failed to create business or owner, rolling back: {error}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify({"error": "שגיאה ביצירת עסק או משתמש הבעלים"}), 500
        
        # ✅ החזר JSON של העסק החדש עם id + ALL fields (consistent with DB)
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_e164": business.phone_e164,
            "whatsapp_number": business.whatsapp_number or "",
            "greeting_message": business.greeting_message or "",
            "whatsapp_greeting": business.whatsapp_greeting or "",
            "system_prompt": business.system_prompt or "",
            "voice_message": business.voice_message or "",
            "working_hours": business.working_hours or "08:00-18:00",
            "phone_permissions": business.phone_permissions,
            "whatsapp_permissions": business.whatsapp_permissions,
            "calls_enabled": business.calls_enabled,
            "crm_enabled": business.crm_enabled,
            "whatsapp_enabled": business.whatsapp_enabled,
            "payments_enabled": business.payments_enabled,
            "default_provider": business.default_provider or "paypal",
            "business_type": business.business_type,
            "is_active": business.is_active,
            "status": "active" if business.is_active else "inactive",
            "call_status": "ready",
            "whatsapp_status": "connected",
            "created_at": business.created_at.isoformat() if business.created_at else None,
            "updated_at": business.updated_at.isoformat() if business.updated_at else None
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating business: {e}")
        return jsonify({"error": "שגיאה ביצירת העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>', methods=['PUT'])
@require_api_auth(['system_admin'])  # BUILD 138: Only system_admin can update businesses
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
        
        # Update phone if provided
        if 'defaultPhoneE164' in data and data['defaultPhoneE164']:
            business.phone_e164 = data['defaultPhoneE164']
        
        # Update phone_e164 (alternative field name)
        if 'phone_e164' in data and data['phone_e164']:
            business.phone_e164 = data['phone_e164']
        
        # Update business type if provided
        if 'business_type' in data and data['business_type']:
            business.business_type = data['business_type']
        
        # Update status if provided
        if 'is_active' in data:
            business.is_active = bool(data['is_active'])
        
        # Update WhatsApp number if provided
        if 'whatsapp_number' in data:
            business.whatsapp_number = data['whatsapp_number']
        
        # Update greeting messages if provided
        if 'greeting_message' in data:
            business.greeting_message = data['greeting_message']
        
        if 'whatsapp_greeting' in data:
            business.whatsapp_greeting = data['whatsapp_greeting']
        
        # Update system prompt if provided
        if 'system_prompt' in data:
            business.system_prompt = data['system_prompt']
        
        # Update voice message if provided
        if 'voice_message' in data:
            business.voice_message = data['voice_message']
        
        # Update working hours if provided
        if 'working_hours' in data:
            business.working_hours = data['working_hours']
        
        # Update permissions if provided
        if 'phone_permissions' in data:
            business.phone_permissions = bool(data['phone_permissions'])
        
        if 'whatsapp_permissions' in data:
            business.whatsapp_permissions = bool(data['whatsapp_permissions'])
        
        # Update feature flags if provided
        if 'calls_enabled' in data:
            business.calls_enabled = bool(data['calls_enabled'])
        
        if 'crm_enabled' in data:
            business.crm_enabled = bool(data['crm_enabled'])
        
        if 'whatsapp_enabled' in data:
            business.whatsapp_enabled = bool(data['whatsapp_enabled'])
        
        if 'payments_enabled' in data:
            business.payments_enabled = bool(data['payments_enabled'])
        
        if 'default_provider' in data:
            business.default_provider = data['default_provider']
        
        business.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated business {business_id}")
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_e164": business.phone_e164,
            "whatsapp_number": business.whatsapp_number or "",
            "greeting_message": business.greeting_message or "",
            "whatsapp_greeting": business.whatsapp_greeting or "",
            "system_prompt": business.system_prompt or "",
            "voice_message": business.voice_message or "",
            "working_hours": business.working_hours or "08:00-18:00",
            "phone_permissions": business.phone_permissions,
            "whatsapp_permissions": business.whatsapp_permissions,
            "calls_enabled": business.calls_enabled,
            "crm_enabled": business.crm_enabled,
            "whatsapp_enabled": business.whatsapp_enabled,
            "payments_enabled": business.payments_enabled,
            "default_provider": business.default_provider or "paypal",
            "business_type": business.business_type,
            "is_active": business.is_active,
            "status": "active" if business.is_active else "inactive",
            "call_status": "ready",
            "whatsapp_status": "connected",
            "created_at": business.created_at.isoformat() if business.created_at else None,
            "updated_at": business.updated_at.isoformat() if business.updated_at else None
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating business {business_id}: {e}")
        return jsonify({"error": "שגיאה בעדכון העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>', methods=['DELETE'])
@require_api_auth(['admin'])
def delete_business(business_id):
    """Delete business with name confirmation"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        data = request.get_json()
        confirmation_name = data.get('confirmation_name', '').strip()
        
        # Check name confirmation
        if confirmation_name != business.name:
            return jsonify({
                "error": "שם העסק שהוזן אינו תואם. אנא הזן את השם המדויק לאישור המחיקה.",
                "expected": business.name,
                "received": confirmation_name
            }), 400
        
        business_name = business.name
        
        # Delete business (cascade will handle related records)
        db.session.delete(business)
        db.session.commit()
        
        logger.info(f"Deleted business {business_id}: {business_name}")
        
        return jsonify({
            "success": True,
            "message": f"העסק '{business_name}' נמחק בהצלחה"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting business {business_id}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "שגיאה במחיקת העסק"}), 500

@biz_mgmt_bp.route('/api/admin/business/<int:business_id>/change-password', methods=['POST'])
@require_api_auth(['admin', 'system_admin', 'owner'])
def change_business_password(business_id):
    """Change password for business owner (tenant-scoped)"""
    try:
        current_user = session.get('user')
        current_role = current_user.get('role') if current_user else None
        
        # ✅ SECURITY: Only system_admin can reset any business, owner only their own
        if current_role == 'system_admin' or current_role == 'admin':
            pass  # System admin can reset any business
        elif current_role == 'owner':
            # Owner can only reset password for their own business
            if current_user.get('business_id') != business_id:
                return jsonify({"error": "Forbidden: Can only reset password for your own business"}), 403
        else:
            return jsonify({"error": "Forbidden: Insufficient permissions"}), 403
        
        data = request.get_json()
        new_password = data.get('password')
        
        if not new_password or len(new_password) < 6:
            return jsonify({"error": "הסיסמה חייבת להכיל לפחות 6 תווים"}), 400
        
        # Find business owner user
        owner_user = User.query.filter_by(
            business_id=business_id,
            role='owner'
        ).first()
        
        if not owner_user:
            return jsonify({"error": "לא נמצא בעלים לעסק זה"}), 404
        
        # Update password
        owner_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        logger.info(f"Changed password for business {business_id} owner by {current_user.get('email') if current_user else 'unknown'}")
        
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
@require_api_auth(['admin', 'system_admin'])
def change_user_password(user_id):
    """Change user password - system admin only (no tenant scoping for security)"""
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

@biz_mgmt_bp.route('/api/admin/businesses/<int:business_id>/impersonate', methods=['POST', 'OPTIONS'])
@require_api_auth(['admin', 'manager'])
def impersonate_business(business_id):
    """Allow admin to impersonate business - WITH PROPER CSRF"""
    
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        logger.info(f"🔄 Impersonation attempt for business {business_id}")
        logger.info(f"📋 Session keys: {list(session.keys())}")
        current_admin = session.get('user') or session.get('al_user')  # Check both keys
        logger.info(f"📋 Current admin from session: {current_admin}")
        logger.info(f"📋 g.user from decorator: {getattr(g, 'user', None)}")
        
        if not current_admin or current_admin.get('role') not in ['admin', 'manager']:
            logger.error(f"❌ Authorization failed - current_admin: {current_admin}")
            return jsonify({"error": "Unauthorized"}), 401
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            logger.error(f"❌ Business {business_id} not found")
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        if not business.is_active:
            return jsonify({"error": "העסק אינו פעיל"}), 400
        
        # ✅ אדמין יכול להתחזות גם בלי user business - יוצר התחזות ויוצר אחד במידת הצורך
        
        # Store original admin for restoration later (per guidelines: use 'impersonator' key)
        current_admin_serialized = {
            "id": current_admin.get('id'),
            "name": current_admin.get('name'),
            "email": current_admin.get('email'),
            "role": current_admin.get('role'),
            "business_id": current_admin.get('business_id')
        }
        session['impersonator'] = current_admin_serialized  # Fixed key name per guidelines
        
        # Switch session to business user - לפי ההנחיות המדויקות
        session['impersonating'] = True
        session['impersonated_tenant_id'] = business.id  # Fixed key name per guidelines  
        # ✅ DON'T override session['role'] - keep original admin role for capabilities
        
        logger.info(f"✅ Admin successfully impersonating business {business_id}")
        logger.info(f"📋 Session: impersonating=True, impersonated_tenant_id={business.id}, admin_role_preserved")
        
        return jsonify({"ok": True, "impersonated_tenant_id": business.id}), 200
        
    except Exception as e:
        logger.error(f"Error impersonating business {business_id}: {e}")
        return jsonify({"error": "שגיאה בהתחזות לעסק"}), 500

@biz_mgmt_bp.route('/api/admin/impersonate/exit', methods=['POST', 'OPTIONS'])
@require_api_auth(['admin', 'manager'])
def exit_impersonation():
    """Exit impersonation and restore original user"""
    
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        logger.info("🔄 Exiting impersonation")
        
        # נקה את מצב ההתחזות ושחזר מצב מקורי - לפי ההנחיות המדויקות
        session.pop('impersonating', None)
        session.pop('impersonated_tenant_id', None)  # Fixed key name
        session.pop('impersonator', None)  # Clear impersonator key (DON'T restore to session['user'])
        
        # ✅ Per guidelines: DON'T modify session['user'] - it stays original throughout
        
        logger.info(f"✅ Successfully exited impersonation, restored: {session.get('user')}")
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        logger.error(f"Error exiting impersonation: {e}")
        return jsonify({"error": "שגיאה ביציאה מהתחזות"}), 500

# === ADDITIONAL BUSINESS ENDPOINTS FROM api_business.py ===

# Business current info route
@biz_mgmt_bp.route('/api/business/current', methods=['GET'])
@require_api_auth(['business', 'admin', 'manager'])
def get_current_business():
    """Get current business details for authenticated user"""
    try:
        from flask import request, g
        
        # Get business_id from context
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({"error": "No business context found"}), 400
            
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "Business not found"}), 404
            
        # Get settings if available
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "phone_number": settings.phone_number if settings and settings.phone_number else business.phone_e164,
            "email": settings.email if settings and settings.email else f"office@{business.name.lower().replace(' ', '-')}.co.il",
            "address": settings.address if settings else "",
            "working_hours": settings.working_hours if settings and settings.working_hours else business.working_hours,
            "timezone": settings.timezone if settings else "Asia/Jerusalem",
            # 🔥 BUILD 138: Appointment settings
            "slot_size_min": settings.slot_size_min if settings else 60,
            "allow_24_7": settings.allow_24_7 if settings else False,
            "booking_window_days": settings.booking_window_days if settings else 30,
            "min_notice_min": settings.min_notice_min if settings else 0,
            "opening_hours_json": settings.opening_hours_json if settings else None
        })
        
    except Exception as e:
        logger.error(f"Error getting current business: {e}")
        return jsonify({"error": "Internal server error"}), 500

@biz_mgmt_bp.route('/api/business/current/settings', methods=['PUT'])
@csrf.exempt  # ✅ Exempt from CSRF for authenticated API
@require_api_auth(['business', 'admin', 'manager'])
def update_current_business_settings():
    """Update current business settings"""
    try:
        from flask import request, session, g
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        # Get business_id from context
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({"error": "No business context found"}), 400
            
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "Business not found"}), 404
            
        # Update business name if provided
        if 'business_name' in data:
            business.name = data['business_name']
            
        # Get or create settings
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if not settings:
            settings = BusinessSettings()
            settings.tenant_id = business_id
            db.session.add(settings)
            
        # Update settings fields
        if 'phone_number' in data:
            settings.phone_number = data['phone_number']
            # Also update the main business table
            business.phone_e164 = data['phone_number']
        if 'email' in data:
            settings.email = data['email']
        if 'address' in data:
            settings.address = data['address']
        if 'working_hours' in data:
            settings.working_hours = data['working_hours']
            # Also update the main business table
            business.working_hours = data['working_hours']
        if 'timezone' in data:
            settings.timezone = data['timezone']
        
        # 🔥 BUILD 138: Appointment settings
        appointment_settings_changed = False
        
        if 'slot_size_min' in data:
            settings.slot_size_min = int(data['slot_size_min'])
            appointment_settings_changed = True
        if 'allow_24_7' in data:
            settings.allow_24_7 = bool(data['allow_24_7'])
            appointment_settings_changed = True
        if 'booking_window_days' in data:
            settings.booking_window_days = int(data['booking_window_days'])
            appointment_settings_changed = True
        if 'min_notice_min' in data:
            settings.min_notice_min = int(data['min_notice_min'])
            appointment_settings_changed = True
        if 'opening_hours_json' in data:
            settings.opening_hours_json = data['opening_hours_json']
            appointment_settings_changed = True
            
        # Track who updated
        user_email = session.get('al_user', {}).get('email', 'Unknown')
        settings.updated_by = user_email
        settings.updated_at = datetime.now()
        
        db.session.commit()
        
        # 🔄 Invalidate caches when appointment settings change
        if appointment_settings_changed:
            from server.policy.business_policy import invalidate_business_policy_cache
            invalidate_business_policy_cache(business_id)
            logger.info(f"🔄 Policy cache cleared for business {business_id} after settings update")
            
            # 🔥 ALSO invalidate agent cache (for AgentKit - WhatsApp)
            try:
                from server.agent_tools.agent_factory import invalidate_agent_cache
                invalidate_agent_cache(business_id)
                logger.info(f"🔄 Agent cache cleared for business {business_id} after settings update")
            except Exception as e:
                logger.warning(f"⚠️ Failed to invalidate agent cache: {e}")
        
        return jsonify({
            "success": True,
            "message": "הגדרות עסק עודכנו בהצלחה"
        })
        
    except Exception as e:
        logger.error(f"Error updating business settings: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


# ===== FAQ MANAGEMENT ROUTES =====

@biz_mgmt_bp.route('/api/business/faqs', methods=['GET'])
@csrf.exempt  # ✅ Exempt from CSRF for authenticated API
@require_api_auth(['business', 'admin', 'manager'])
def get_business_faqs():
    """Get all FAQs for current business"""
    try:
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'No business context found'}), 400
        
        faqs = FAQ.query.filter_by(business_id=business_id, is_active=True).order_by(FAQ.order_index, FAQ.id).all()
        
        return jsonify([{
            'id': faq.id,
            'question': faq.question,
            'answer': faq.answer,
            'intent_key': faq.intent_key,
            'patterns_json': faq.patterns_json,
            'channels': faq.channels,
            'priority': faq.priority,
            'lang': faq.lang,
            'order_index': faq.order_index,
            'created_at': faq.created_at.isoformat() if faq.created_at else None
        } for faq in faqs])
    except Exception as e:
        logger.error(f'Error getting FAQs: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@biz_mgmt_bp.route('/api/business/faqs', methods=['POST'])
@csrf.exempt  # ✅ Exempt from CSRF for authenticated API
@require_api_auth(['business', 'admin', 'manager'])
def create_faq():
    """Create new FAQ"""
    try:
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'No business context found'}), 400
        
        data = request.get_json()
        if not data or not data.get('question') or not data.get('answer'):
            return jsonify({'error': 'Question and answer are required'}), 400
        
        # Get max order_index
        max_order = db.session.query(db.func.max(FAQ.order_index)).filter_by(business_id=business_id).scalar() or 0
        
        try:
            normalized_patterns = normalize_patterns(data.get('patterns_json'))
        except ValueError as e:
            return jsonify({'error': f'Invalid patterns_json: {str(e)}'}), 400
        
        faq = FAQ(
            business_id=business_id,
            question=data['question'],
            answer=data['answer'],
            intent_key=data.get('intent_key'),
            patterns_json=normalized_patterns,
            channels=data.get('channels', 'voice'),
            priority=data.get('priority', 0),
            lang=data.get('lang', 'he-IL'),
            order_index=max_order + 1
        )
        db.session.add(faq)
        db.session.commit()
        
        # Invalidate FAQ cache after creation
        try:
            from server.services.faq_cache import faq_cache
            faq_cache.invalidate(business_id)
        except Exception as e:
            logger.warning(f"FAQ cache invalidation failed: {e}")
        
        return jsonify({
            'id': faq.id,
            'question': faq.question,
            'answer': faq.answer,
            'intent_key': faq.intent_key,
            'patterns_json': faq.patterns_json,
            'channels': faq.channels,
            'priority': faq.priority,
            'lang': faq.lang,
            'order_index': faq.order_index,
            'created_at': faq.created_at.isoformat() if faq.created_at else None
        }), 201
    except Exception as e:
        logger.error(f'Error creating FAQ: {e}')
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@biz_mgmt_bp.route('/api/business/faqs/<int:faq_id>', methods=['PUT'])
@csrf.exempt  # ✅ Exempt from CSRF for authenticated API
@require_api_auth(['business', 'admin', 'manager'])
def update_faq(faq_id):
    """Update FAQ"""
    try:
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'No business context found'}), 400
        
        faq = FAQ.query.filter_by(id=faq_id, business_id=business_id).first()
        if not faq:
            return jsonify({'error': 'FAQ not found'}), 404
        
        data = request.get_json()
        if 'question' in data:
            faq.question = data['question']
        if 'answer' in data:
            faq.answer = data['answer']
        if 'intent_key' in data:
            faq.intent_key = data['intent_key']
        if 'patterns_json' in data:
            try:
                faq.patterns_json = normalize_patterns(data['patterns_json'])
            except ValueError as e:
                return jsonify({'error': f'Invalid patterns_json: {str(e)}'}), 400
        if 'channels' in data:
            faq.channels = data['channels']
        if 'priority' in data:
            faq.priority = data['priority']
        if 'lang' in data:
            faq.lang = data['lang']
        if 'order_index' in data:
            faq.order_index = data['order_index']
        
        faq.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Invalidate FAQ cache after update
        try:
            from server.services.faq_cache import faq_cache
            faq_cache.invalidate(business_id)
        except Exception as e:
            logger.warning(f"FAQ cache invalidation failed: {e}")
        
        return jsonify({
            'id': faq.id,
            'question': faq.question,
            'answer': faq.answer,
            'intent_key': faq.intent_key,
            'patterns_json': faq.patterns_json,
            'channels': faq.channels,
            'priority': faq.priority,
            'lang': faq.lang,
            'order_index': faq.order_index,
            'updated_at': faq.updated_at.isoformat() if faq.updated_at else None
        })
    except Exception as e:
        logger.error(f'Error updating FAQ: {e}')
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@biz_mgmt_bp.route('/api/business/faqs/<int:faq_id>', methods=['DELETE'])
@csrf.exempt  # ✅ Exempt from CSRF for authenticated API
@require_api_auth(['business', 'admin', 'manager'])
def delete_faq(faq_id):
    """Delete FAQ (soft delete by marking inactive)"""
    try:
        business_id = getattr(g, 'business_id', None)
        if not business_id:
            return jsonify({'error': 'No business context found'}), 400
        
        faq = FAQ.query.filter_by(id=faq_id, business_id=business_id).first()
        if not faq:
            return jsonify({'error': 'FAQ not found'}), 404
        
        faq.is_active = False
        db.session.commit()
        
        # Invalidate FAQ cache after deletion
        try:
            from server.services.faq_cache import faq_cache
            faq_cache.invalidate(business_id)
        except Exception as e:
            logger.warning(f"FAQ cache invalidation failed: {e}")
        
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f'Error deleting FAQ: {e}')
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

