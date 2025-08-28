"""
UI Routes for Flask + Jinja + Tailwind + HTMX
Based on attached instructions
"""
from flask import render_template, request, redirect, url_for, session, jsonify, flash
from server.ui import ui_bp
from server.ui.auth import require_roles, require_login
import requests
import os

# Base URL for API calls
API_BASE = os.getenv('PUBLIC_BASE_URL', 'http://localhost:5000')

@ui_bp.route('/')
def index():
    """Root redirect to login or dashboard"""
    try:
        # Check new auth system first
        user = session.get('al_user') or session.get('user')
        if user:
            user_role = user.get('role')
            if user_role == 'admin':
                return redirect(url_for('ui.admin_dashboard'))
            else:
                return redirect(url_for('ui.business_dashboard'))
        return redirect(url_for('ui.login'))
    except Exception as e:
        return f"<h1>🚧 System Loading...</h1><p>Error: {e}</p><p><a href='/login'>Go to Login</a></p>"

@ui_bp.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@ui_bp.route('/forgot')
def forgot():
    """Forgot password page"""
    return render_template('forgot.html')

@ui_bp.route('/reset')
def reset():
    """Reset password page"""
    token = request.args.get('token')
    return render_template('reset.html', token=token)

@ui_bp.route('/app/admin')
@require_roles('admin')
def admin_dashboard():
    """Admin dashboard page"""
    user = session.get('al_user') or session.get('user')
    return render_template('admin.html', user=user)

@ui_bp.route('/app/biz')
@require_roles('business', 'admin')
def business_dashboard():
    """Business dashboard page"""
    user = session.get('al_user') or session.get('user')
    return render_template('business.html', user=user)

# API Auth endpoints for JS calls
@ui_bp.route('/api/ui/login', methods=['POST'])
def api_login():
    """Handle login form submission - call auth system directly"""
    try:
        data = request.get_json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        
        if not email or not password:
            return jsonify({"success": False, "error": "נדרשים אימייל וסיסמה"}), 400

        # Import dao and check user
        from server.routes_auth import dao_users
        from werkzeug.security import check_password_hash
        
        u = dao_users.get_by_email(email)
        if not u or not check_password_hash(u.get("password_hash", ""), password):
            return jsonify({"success": False, "error": "פרטי התחברות שגויים"}), 401

        # Set session
        session["al_user"] = {
            "id": u["id"],
            "name": u.get("name"),
            "role": u.get("role"),
            "business_id": u.get("business_id"),
        }
        
        return jsonify({
            "success": True,
            "user": session["al_user"]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת התחברות: {str(e)}'}), 500

@ui_bp.route('/api/ui/logout', methods=['POST'])
def api_logout():
    """Handle logout - use new auth system"""
    try:
        from server.routes_auth import api_logout as auth_logout
        from flask import current_app
        
        with current_app.test_request_context('/api/auth/logout', method='POST'):
            result = auth_logout()
            return result
    except Exception as e:
        session.clear()  # Fallback
        return jsonify({'success': True})