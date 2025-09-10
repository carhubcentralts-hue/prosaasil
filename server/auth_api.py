"""
Authentication API endpoints
Based on attached instructions - creates missing auth endpoints
"""
from flask import Blueprint, request, jsonify, session, g
from werkzeug.security import check_password_hash, generate_password_hash
from server.models_sql import User, Business, db
from server.extensions import csrf
from datetime import datetime, timedelta
from functools import wraps
import secrets
import os

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')

@auth_api.get("/csrf")
def get_csrf():
    """מחזיר טוקן CSRF "קריא ל־JS" עם דגלים מתאימים לפי ההנחיות המדויקות"""
    import os
    
    IS_PREVIEW = (
        'picard.replit.dev' in os.getenv('REPLIT_URL', '') or
        os.getenv('PREVIEW_MODE') == '1'
    )
    
    token = request.cookies.get('XSRF-TOKEN') or csrf._get_token()
    if not token:
        token = secrets.token_urlsafe(32)
    
    resp = jsonify({"csrfToken": token})
    
    if IS_PREVIEW:
        resp.set_cookie('XSRF-TOKEN', token, httponly=False, samesite='None', secure=True, path='/')
    else:
        resp.set_cookie('XSRF-TOKEN', token, httponly=False, samesite='Lax',  secure=True, path='/')
    return resp

@csrf.exempt  # Proper SeaSurf exemption
@auth_api.route('/login', methods=['POST', 'OPTIONS'])
def login():
    """Login endpoint with CSRF bypass"""
    """
    POST /api/auth/login
    Expected response: {user:{id,name,role,business_id}, token?}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Missing email or password'}), 400
        
        # Find user by email (fix field names to match DB schema)
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Get business info if exists
        business = None
        if user.business_id:
            business = Business.query.get(user.business_id)
        
        # Prepare user response
        user_data = {
            'id': user.id,
            'name': user.name or user.email,
            'role': user.role,
            'business_id': user.business_id,
            'email': user.email
        }
        
        # Prepare tenant response (required by frontend)
        tenant_data = {
            'id': business.id if business else user.business_id or 1,
            'name': business.name if business else 'Default Tenant'
        }
        
        # Store in session - both keys for compatibility
        session['al_user'] = user_data  # Use al_user key for consistency
        session['user'] = user_data     # Also store as 'user' for decorators
        session['tenant_id'] = user.business_id
        session['token'] = f"session_{user.id}"  # Simple session token
        
        # Return format that matches frontend AuthResponse type
        return jsonify({
            'user': user_data,
            'tenant': tenant_data,
            'impersonating': False
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@csrf.exempt  # Forgot password also exempt from CSRF
@auth_api.route('/forgot', methods=['POST'])
def forgot_password():
    """
    POST /api/auth/forgot
    Send password reset email
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        email = data.get('email')
        if not email:
            return jsonify({'success': False, 'error': 'Missing email'}), 400
        
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            user.resetToken = reset_token
            user.resetTokenExpiry = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            db.session.commit()
            
            # TODO: Send actual email here
            # For now, just log the reset link
            reset_url = f"{os.getenv('PUBLIC_BASE_URL', 'http://localhost:5000')}/reset?token={reset_token}"
            print(f"🔐 Password reset for {email}: {reset_url}")
        
        # Always return success for security (don't reveal if email exists)
        return jsonify({'success': True, 'message': 'If the email exists, a reset link has been sent'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@csrf.exempt  # Reset password also exempt from CSRF  
@auth_api.route('/reset', methods=['POST'])
def reset_password():
    """
    POST /api/auth/reset
    Reset password with token
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        token = data.get('token')
        new_password = data.get('password')
        
        if not token or not new_password:
            return jsonify({'success': False, 'error': 'Missing token or password'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        # Find user by reset token
        user = User.query.filter_by(resetToken=token, isActive=True).first()
        
        if not user:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 400
        
        # Check token expiry
        if user.resetTokenExpiry < datetime.utcnow():
            return jsonify({'success': False, 'error': 'Token has expired'}), 400
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Password updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@csrf.exempt  # Logout also exempt from CSRF
@auth_api.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True})

@auth_api.route('/me', methods=['GET'])
def get_current_user():
    """
    GET /api/auth/me
    Returns current user data from session - single source of truth
    """
    try:
        u = session.get('al_user')  # Use al_user key for consistency
        if not u:
            return jsonify({"error":"Not authenticated"}), 401
        
        # Get tenant info from business
        business = None
        tenant_id = session.get('tenant_id') or u.get('business_id')
        if tenant_id:
            business = Business.query.get(tenant_id)
        
        # Prepare tenant response (required by frontend)
        tenant_data = {
            'id': business.id if business else tenant_id or 1,
            'name': business.name if business else 'Default Tenant'
        }
        
        # ✅ חישוב נכון של impersonating לפי ההנחיות
        impersonating = bool(session.get('impersonating') and session.get('tenant_id'))
        
        return jsonify({
            "user": u,
            "tenant": tenant_data,
            "impersonating": impersonating
        }), 200
    
    except Exception as e:
        print(f"Error in /api/auth/me: {e}")
        return jsonify({'error': str(e)}), 500

@auth_api.route('/current', methods=['GET'])
def get_current_user_legacy():
    """Get current logged in user data"""
    try:
        user = session.get('al_user')  # Use al_user key for consistency
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Get business info if exists
        business = None
        if user.get('business_id'):
            from server.models_sql import Business
            business_obj = Business.query.get(user['business_id'])
            if business_obj:
                business = {
                    'id': business_obj.id,
                    'name': business_obj.name,
                    'phone_e164': business_obj.phone_e164
                }
        
        # Basic permissions based on role
        permissions = {
            'view_calls': True,
            'view_whatsapp': True,
            'view_customers': True,
            'manage_users': user.get('role') == 'manager',
            'manage_business': user.get('role') == 'manager'
        }
        
        return jsonify({
            'user': user,
            'business': business,
            'permissions': permissions
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Auth decorator for API routes
def require_api_auth(roles=None):
    """Decorator for API routes that require authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in (session-based)
            user = session.get('user') or session.get('al_user')
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Check role if specified - ✅ אדמין יכול לגשת לכל התוחמים
            if roles and user.get('role') not in roles:
                # אדמין יכול לגשת גם ל-business endpoints כשהוא מתחזה
                if user.get('role') != 'admin':
                    return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Store user in g for use in route
            g.user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper function to create default admin user (for development)
def create_default_admin():
    """Create default admin user if none exists"""
    try:
        if not User.query.filter_by(role='admin').first():
            admin = User()
            admin.email = 'admin@maximus.co.il'
            admin.password_hash = generate_password_hash('admin123')
            admin.name = 'מנהל מערכת'
            admin.role = 'admin'
            admin.business_id = None
            db.session.add(admin)
            db.session.commit()
            print("✅ Created default admin user: admin@maximus.co.il / admin123")
    except Exception as e:
        print(f"⚠️ Error creating admin user: {e}")