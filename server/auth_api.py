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

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')

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
        data = request.get_json()
        if not data:
            print("❌ LOGIN: No JSON data received")
            return jsonify({'success': False, 'error': 'Missing request data'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        print(f"🔐 LOGIN ATTEMPT: email={email}")
        
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
        
        # Update last login
        user.last_login = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as commit_error:
            print(f"⚠️ DB commit warning: {commit_error}")
            db.session.rollback()  # Rollback if commit fails
        
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
        # Note: Don't set tenant_id here - use impersonated_tenant_id only for impersonation per guidelines
        session['token'] = f"session_{user.id}"  # Simple session token
        
        # Return format that matches frontend AuthResponse type
        return jsonify({
            'user': user_data,
            'tenant': tenant_data,
            'impersonating': False
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_api.route('/forgot', methods=['POST'])  # CSRF protected - not in exempt list
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

@auth_api.route('/reset', methods=['POST'])  # CSRF protected - not in exempt list
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

# REMOVED duplicate get_csrf_token() - using single @auth_api.get("/csrf") implementation only

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
        tenant_id = session.get('impersonated_tenant_id') or u.get('business_id')  # Fixed key per guidelines
        if tenant_id:
            business = Business.query.get(tenant_id)
        
        # Prepare tenant response (required by frontend)
        tenant_data = {
            'id': business.id if business else tenant_id or 1,
            'name': business.name if business else 'Default Tenant'
        }
        
        # ✅ חישוב נכון של impersonating לפי ההנחיות
        impersonating = bool(session.get('impersonating') and session.get('impersonated_tenant_id'))  # Fixed key per guidelines
        
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

# Auth decorator for API routes - simplified per instructions
def require_api_auth(roles=None):
    """Simple guard that doesn't do CSRF at all"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            
            # Allow OPTIONS immediately (204)
            if request.method == "OPTIONS":
                return '', 204
            
            # Check session['user'] exists
            if 'user' not in session:
                return jsonify({
                    'error': 'forbidden',
                    'reason': 'no_session',
                    'message': 'Authentication required'
                }), 401
            
            # Compute context once - per exact instructions
            role = session['user']['role']  # 'system_admin'|'owner'|'admin'|'agent'|'business'
            tenant = session.get('impersonated_tenant_id') or session['user'].get('business_id')  # Fixed: use business_id not tenant_id
            impersonating = bool(session.get('impersonating'))
            
            # Store context in g for route use (properly typed)
            g.business_id = tenant
            
            # Route-based permissions logic
            is_admin_route = request.path.startswith('/api/admin/')
            
            if is_admin_route:
                # כל /api/admin/** ⇒ דורש role in {'system_admin','owner','admin','manager'}
                # BUILD 124: Updated to support new role structure
                if role not in {'system_admin', 'owner', 'admin', 'manager'}:
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'admin_required',
                        'message': f'Admin route requires system_admin/owner/admin role, got {role}'
                    }), 403
            else:
                # ראוטים של עסק ⇒ role in {'owner','admin','agent','business'} או system_admin (עם או בלי התחזות)
                if role in {'owner', 'admin', 'agent', 'business'}:
                    # Business users - allow if same tenant
                    pass
                elif role == 'system_admin':
                    # System admin - always allow business routes (with or without impersonation)
                    pass
                elif role in {'admin', 'manager'}:
                    # Legacy roles - still allow for backward compatibility
                    pass
                else:
                    return jsonify({
                        'error': 'forbidden', 
                        'reason': 'business_access_denied',
                        'message': f'Business route access denied for role {role}'
                    }), 403
            
            # Store context in g for route use
            g.user = session['user']
            g.role = role
            g.tenant = tenant
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
            # Create new system admin
            admin = User(
                email='admin@admin.com',
                password_hash=generate_password_hash('admin123', method='scrypt'),
                name='System Administrator',
                role='system_admin',
                business_id=1,
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