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
        if session.get('user'):
            user_role = session['user'].get('role')
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
    return render_template('admin.html', user=session['user'])

@ui_bp.route('/app/biz')
@require_roles('business', 'admin')
def business_dashboard():
    """Business dashboard page"""
    return render_template('business.html', user=session['user'])

# API Auth endpoints for JS calls
@ui_bp.route('/api/ui/login', methods=['POST'])
def api_login():
    """Handle login form submission"""
    try:
        data = request.get_json()
        # Call existing auth API
        response = requests.post(f'{API_BASE}/api/auth/login', json=data)
        
        if response.status_code == 200:
            result = response.json()
            # Store in session
            session['user'] = result.get('user')
            session['token'] = result.get('token')
            return jsonify({'success': True, 'user': result.get('user')})
        else:
            return jsonify({'success': False, 'error': 'Login failed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@ui_bp.route('/api/ui/logout', methods=['POST'])
def api_logout():
    """Handle logout"""
    session.clear()
    return jsonify({'success': True})