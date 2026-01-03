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
import hashlib
import binascii
import logging

# 🔥 AUTH DEBUG flag - only enabled in development
DEBUG_AUTH = os.getenv("DEBUG_AUTH", "0") == "1"

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')
logger = logging.getLogger(__name__)

def get_session_user():
    """
    Helper function to get current user from session.
    Returns dict with user data or None if not authenticated.
    Unlike get_current_user() route handler, this returns a plain dict.
    """
    from flask import session
    u = session.get('al_user') or session.get('user')
    if not u:
        return None
    return u

def verify_password(stored_hash, password):
    """
    Verify password against stored hash - werkzeug handles all formats
    
    Args:
        stored_hash: The stored password hash from database
        password: The plaintext password to verify
        
    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        # ✅ FIX: werkzeug handles scrypt, pbkdf2, and all other formats natively
        return check_password_hash(stored_hash, password)
    except Exception as e:
        print(f"⚠️ Password verification error: {e}")
        return False

@auth_api.get("/csrf")
def get_csrf():
    """✅ תיקון לפי architect: מחזיר את token של SeaSurf (מסונכרן עם cookie)"""
    from flask import current_app
    from server.extensions import csrf
    
    # ✅ CRITICAL FIX: קבל את ה-token הקיים של SeaSurf (לא ליצור חדש!)
    # כך ה-header וה-cookie יהיו מסונכרנים
    token = csrf._get_token()
    
    resp = jsonify({"csrfToken": token})
    
    # SeaSurf כבר מגדיר את ה-cookie ב-response middleware
    # לכן אנחנו רק מחזירים את אותו token ב-JSON
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
        from server.services.auth_service import AuthService, get_request_user_agent
        
        data = request.get_json()
        if not data:
            print("❌ LOGIN: No JSON data received")
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        email = data.get('email')
        password = data.get('password')
        remember_me = data.get('remember_me', False)  # Remember me checkbox
        
        print(f"🔐 LOGIN ATTEMPT: email={email}, remember_me={remember_me}")
        
        if not email or not password:
            print("❌ LOGIN: Missing email or password")
            return jsonify({'success': False, 'error': 'Missing email or password'}), 400
        
        # Find user by email (fix field names to match DB schema)
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if not user:
            print(f"❌ LOGIN: User not found for email={email}")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        print(f"✓ Found user: id={user.id}, email={user.email}, role={user.role}")
        print(f"✓ Password hash: {user.password_hash[:50]}...")
        
        password_valid = verify_password(user.password_hash, password)
        print(f"✓ Password verification result: {password_valid}")
        
        if not password_valid:
            print(f"❌ LOGIN: Invalid password for email={email}")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Update last login and last activity
        user.last_login = datetime.utcnow()
        user.last_activity_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as commit_error:
            print(f"⚠️ DB commit warning: {commit_error}")
            db.session.rollback()  # Rollback if commit fails
        
        # Generate refresh token
        user_agent = get_request_user_agent()
        plain_refresh_token, refresh_token_obj = AuthService.generate_refresh_token(
            user_id=user.id,
            tenant_id=user.business_id,
            remember_me=remember_me,
            user_agent=user_agent
        )
        
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
        # ✅ BUILD 139: Don't fallback to 1 for system_admin - let it be None
        tenant_data = {
            'id': business.id if business else user.business_id,  # None for system_admin
            'name': business.name if business else ('System Admin' if user.role == 'system_admin' else 'No Business')
        }
        
        # Store in session - both keys for compatibility
        session['al_user'] = user_data  # Use al_user key for consistency
        session['user'] = user_data     # Also store as 'user' for decorators
        # Note: Don't set tenant_id here - use impersonated_tenant_id only for impersonation per guidelines
        session['token'] = f"session_{user.id}"  # Simple session token
        session['refresh_token'] = plain_refresh_token  # Store refresh token in session
        
        # BUILD 144: Critical session persistence settings for production!
        session.permanent = True  # Use PERMANENT_SESSION_LIFETIME
        session.modified = True   # Force cookie to be sent
        session['_last_activity'] = datetime.now().isoformat()
        session['_session_start'] = datetime.now().isoformat()
        
        # 🔍 BUILD 138 DEBUG: Log what we stored in session
        logger.info(f"[AUTH] login_success user_id={user.id} email={user.email} role={user.role} business_id={user.business_id} remember_me={remember_me}")
        
        # Return format that matches frontend AuthResponse type
        return jsonify({
            'user': user_data,
            'tenant': tenant_data,
            'impersonating': False
        })
        
    except Exception as e:
        logger.error(f"[AUTH] Login error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_api.route('/forgot', methods=['POST'])  # CSRF protected - not in exempt list
def forgot_password():
    """
    POST /api/auth/forgot
    Send password reset email
    """
    try:
        from server.services.auth_service import AuthService
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        email = data.get('email')
        if not email:
            return jsonify({'success': False, 'error': 'Missing email'}), 400
        
        # Generate and send reset token (always returns True)
        AuthService.generate_password_reset_token(email)
        
        # Always return success for security (don't reveal if email exists)
        return jsonify({'success': True, 'message': 'If the email exists, a reset link has been sent'})
        
    except Exception as e:
        logger.error(f"[AUTH] Forgot password error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_api.route('/reset', methods=['POST'])  # CSRF protected - not in exempt list
def reset_password():
    """
    POST /api/auth/reset
    Reset password with token
    """
    try:
        from server.services.auth_service import AuthService
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        token = data.get('token')
        new_password = data.get('password')
        
        if not token or not new_password:
            return jsonify({'success': False, 'error': 'Missing token or password'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        # Hash the new password
        new_password_hash = generate_password_hash(new_password)
        
        # Complete password reset
        success = AuthService.complete_password_reset(token, new_password_hash)
        
        if not success:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 400
        
        return jsonify({'success': True, 'message': 'Password updated successfully'})
        
    except Exception as e:
        logger.error(f"[AUTH] Reset password error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@csrf.exempt  # Logout also exempt from CSRF
@auth_api.route('/logout', methods=['POST'])
def logout():
    """Logout user and invalidate all sessions"""
    try:
        from server.services.auth_service import AuthService
        
        # Get user from session
        user = session.get('al_user') or session.get('user')
        
        if user and user.get('id'):
            # Invalidate all refresh tokens for this user
            AuthService.invalidate_all_user_tokens(user['id'])
        
        # Clear session
        session.clear()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"[AUTH] Logout error: {e}")
        # Clear session even on error
        session.clear()
        return jsonify({'success': True})

# REMOVED duplicate get_csrf_token() - using single @auth_api.get("/csrf") implementation only

@auth_api.route('/me', methods=['GET'])
def get_current_user():
    """
    GET /api/auth/me
    Returns current user data from session - single source of truth
    """
    try:
        # BUILD 142 FINAL: Check al_user first, then user (priority order)
        u = session.get('al_user') or session.get('user')
        if not u:
            return jsonify({"error":"Not authenticated"}), 401
        
        # BUILD 142 FINAL: Compute tenant - impersonation overrides business_id
        if session.get("impersonated_tenant_id"):
            tenant_id = session.get("impersonated_tenant_id")
            impersonating = True
        else:
            tenant_id = u.get('business_id')
            impersonating = False
        
        # Get tenant info from business
        business = None
        if tenant_id:
            business = Business.query.get(tenant_id)
        
        # Prepare tenant response (required by frontend)
        # 🔥 HARDENING: No fallback to 1 - tenant_id can be None for system_admin
        tenant_data = {
            'id': business.id if business else tenant_id,
            'name': business.name if business else ('System Admin' if u.get('role') == 'system_admin' else 'No Tenant')
        }
        
        # Include original user data during impersonation for frontend banner
        response_data = {
            "user": u,
            "tenant": tenant_data,
            "impersonating": impersonating
        }
        
        # Add original_user during impersonation so frontend can display proper banner
        if impersonating and session.get('impersonator'):
            response_data["original_user"] = session.get('impersonator')
        
        return jsonify(response_data), 200
    
    except Exception as e:
        print(f"Error in /api/auth/me: {e}")
        return jsonify({'error': str(e)}), 500

@auth_api.route('/current', methods=['GET'])
def get_current_user_legacy():
    """Get current logged in user data"""
    try:
        # BUILD 142 FINAL: Check al_user first, then user (priority order)
        user = session.get('al_user') or session.get('user')
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

# Auth decorator for API routes - BUILD 124: Enhanced with role-based access control
def require_api_auth(allowed_roles=None):
    """
    Auth decorator with role-based access control and idle timeout checking
    
    Args:
        allowed_roles: List of allowed roles for this route (e.g., ['system_admin', 'owner'])
                      If None, allows all authenticated users
                      
    Role hierarchy (BUILD 124):
        - system_admin: Global administrator (full access)
        - owner: Business owner (full business access)
        - admin: Business administrator (limited business access)
        - agent: Business agent (limited CRM/calls access)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from server.services.auth_service import AuthService
            
            # Allow OPTIONS immediately (204)
            if request.method == "OPTIONS":
                return '', 204
            
            # BUILD 142 FINAL: Check session keys in priority order (al_user first, then user)
            user = session.get("al_user") or session.get("user")
            if not user:
                return jsonify({
                    'error': 'forbidden',
                    'reason': 'no_session',
                    'message': 'Authentication required'
                }), 401
            
            # Check idle timeout
            user_id = user.get('id')
            if user_id:
                user_obj = User.query.get(user_id)
                if user_obj and AuthService.check_idle_timeout(user_obj):
                    # User has been idle too long - invalidate all tokens and logout
                    AuthService.invalidate_all_user_tokens(user_id)
                    session.clear()
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'idle_timeout',
                        'message': 'Session expired due to inactivity'
                    }), 401
                
                # Update activity timestamp
                AuthService.update_user_activity(user_id)
            
            # BUILD 142 FINAL: Compute tenant - impersonation overrides business_id
            if session.get("impersonated_tenant_id"):
                tenant = session.get("impersonated_tenant_id")
            else:
                tenant = user.get('business_id')  # Can be None for system_admin - THIS IS OK!
            
            # Compute role and impersonation status
            user_role = user['role']
            impersonating = bool(session.get("impersonated_tenant_id"))
            
            # 🔍 BUILD 142 AUTH DEBUG: Only log in development mode
            if DEBUG_AUTH:
                logger.debug(f"[AUTH] user_id={user.get('id')}, role={user_role}, business_id={user.get('business_id')}, computed_tenant={tenant}, impersonating={impersonating}")
            
            # BUILD 138: FIXED legacy role mapping - only map ACTUAL legacy roles, not new ones!
            # Legacy roles (old): manager, business, superadmin
            # Current roles (new): system_admin, owner, admin, agent
            legacy_to_new = {
                'manager': 'owner',          # Old manager → new owner
                'business': 'admin',         # Old business → new admin (business-level access)
                'superadmin': 'system_admin' # Old superadmin → new system_admin
            }
            
            # Map user's role only if it's legacy
            effective_user_role = legacy_to_new.get(user_role, user_role)
            
            # ✅ BUILD 140: system_admin bypasses role checks (global access)
            is_system_admin = effective_user_role == 'system_admin'
            
            # Check role-based access if roles are specified (unless system_admin)
            if allowed_roles and not is_system_admin:
                # Build allowed set: support BOTH legacy names in decorator AND user roles
                allowed_set = set()
                for role in allowed_roles:
                    allowed_set.add(role)  # Add original
                    # If this is a legacy role name, add its new equivalent
                    if role in legacy_to_new:
                        allowed_set.add(legacy_to_new[role])
                
                # Check if user's role (mapped if legacy) is allowed
                if effective_user_role not in allowed_set:
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'insufficient_permissions',
                        'message': f'This route requires one of {allowed_roles}, got {user_role} (mapped to {effective_user_role})'
                    }), 403
            
            # BUILD 142 FINAL: Store context in g for route use
            g.user = user
            g.role = effective_user_role  # Use mapped role
            g.tenant = tenant  # Can be None for system_admin - THIS IS OK!
            g.business_id = tenant  # Backward compatibility
            g.impersonating = impersonating
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Helper function to create default admin user (for development)
def create_default_admin():
    """Create default admin user if none exists"""
    try:
        # Check for admin@admin.com first
        admin = User.query.filter_by(email='admin@admin.com').first()
        if admin:
            # Reset password for existing admin
            print(f"👤 Admin exists (ID={admin.id}), resetting password to 'admin123'")
            admin.password_hash = generate_password_hash('admin123', method='scrypt')
            db.session.commit()
            print(f"✅ Admin password reset: admin@admin.com / admin123")
        elif not User.query.filter_by(role='system_admin').first():
            # ✅ BUILD 140: Create system_admin with business_id=None (global entity)
            admin = User(
                email='admin@admin.com',
                password_hash=generate_password_hash('admin123', method='scrypt'),
                name='System Administrator',
                role='system_admin',
                business_id=None,  # Global entity - not tied to any business
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Created default admin user: admin@admin.com / admin123")
    except Exception as e:
        print(f"⚠️ Error creating admin user: {e}")

@csrf.exempt
@auth_api.route('/init-admin', methods=['POST'])
def init_admin():
    """Emergency endpoint to initialize admin user"""
    try:
        create_default_admin()
        return jsonify({'success': True, 'message': 'Admin initialized'}), 200
    except Exception as e:
        print(f"❌ Admin init failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500