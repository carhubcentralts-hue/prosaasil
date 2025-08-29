# Clean UI Routes - Professional Hebrew CRM
# Based on exact specification from attached_assets
from flask import Blueprint, render_template, request, session, g, redirect, url_for, jsonify, render_template_string
from functools import wraps

ui_bp = Blueprint('ui', __name__)

def require_roles(*allowed_roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get('al_user') or session.get('user')
            if not user:
                return redirect(url_for('ui.login'))
            
            user_role = user.get('role', '')
            if user_role not in allowed_roles:
                # Smart role-based redirect
                if user_role in ("admin", "superadmin"):
                    return redirect(url_for("ui.admin_home"))
                return redirect(url_for("ui.biz_home"))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def effective_business_id():
    """Admin can choose ?business_id=; others locked to their business"""
    bid = request.args.get("business_id")
    user = session.get('al_user') or session.get('user')
    if user and user.get("role") not in ("admin","superadmin"):
        bid = user.get("business_id")
    return bid

def _load_counters_for_admin():
    """Load counters for admin dashboard"""
    try:
        from server.models_sql import Business, User
        tenants_active = Business.query.filter_by(is_active=True).count()
        users_pending = User.query.filter_by(enabled=False).count()
        return {
            'tenants_active': tenants_active,
            'users_pending': users_pending,
            'today_calls': 0,
            'whatsapp_unread': 0
        }
    except:
        return {
            'tenants_active': 0,
            'users_pending': 0,
            'today_calls': 0,
            'whatsapp_unread': 0
        }

def _load_counters_for_business(bid):
    """Load counters for business dashboard"""
    try:
        from server.models_sql import User
        biz_users_count = User.query.filter_by(business_id=bid).count() if bid else 0
        return {
            'biz_users_count': biz_users_count,
            'today_calls': 0,
            'whatsapp_unread': 0
        }
    except:
        return {
            'biz_users_count': 0,
            'today_calls': 0,
            'whatsapp_unread': 0
        }

# === MAIN ROUTES ===
@ui_bp.route('/')
def home():
    user = session.get('al_user') or session.get('user')
    if user:
        role = user.get('role')
        if role in ("admin", "superadmin"):
            return redirect(url_for("ui.admin_home"))
        else:
            return redirect(url_for("ui.biz_home"))
    return redirect(url_for('ui.login'))

@ui_bp.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@ui_bp.route('/app/admin')
@require_roles('admin', 'superadmin')
def admin_home():
    """Admin dashboard page"""
    user = session.get('al_user') or session.get('user')
    
    counters = _load_counters_for_admin()
    
    try:
        from server.models_sql import Business
        tenants = Business.query.filter_by(is_active=True).all()
    except:
        tenants = []
    
    return render_template('admin.html',
                         page_title="איזור מנהל",
                         role=user.get('role') if user else None,
                         current_user=user,
                         active="admin_home",
                         current_business_id=request.args.get("business_id"),
                         counters=counters,
                         tenants=tenants)

@ui_bp.route('/app/biz')
@require_roles('admin','superadmin','manager','agent')
def biz_home():
    """Business dashboard page"""
    user = session.get('al_user') or session.get('user')
    
    bid = effective_business_id()
    counters = _load_counters_for_business(bid)
    
    return render_template('business.html',
                         page_title="איזור עסק",
                         role=user.get('role') if user else None,
                         current_user=user,
                         active="biz_whatsapp",
                         current_business_id=bid,
                         counters=counters)

# === ADMIN HTMX ROUTES ===
@ui_bp.route("/ui/admin/switch_business")
@require_roles("admin","superadmin")
def ui_admin_switch_business():
    """Switch business for admin view"""
    bid = request.args.get("business_id","")
    return render_template_string('<div id="switchHook"></div><script>location = "/app/admin?business_id={{bid}}"</script>', bid=bid)

@ui_bp.route("/ui/admin/tenants/new")
@require_roles("admin","superadmin")
def ui_admin_tenants_new():
    """Modal for creating new tenant"""
    return "<div class='fixed inset-0 z-50 grid place-items-center bg-black/40'><div class='w-full max-w-lg bg-white rounded-2xl p-4'><h3 class='text-lg font-semibold mb-4'>עסק חדש</h3><p>טופס יתווסף בקרוב...</p><div class='flex gap-2 justify-end pt-4'><button onclick='closeModal()' class='btn'>בטל</button><button class='btn-primary'>שמור</button></div></div></div>"

@ui_bp.route("/ui/admin/users/new")
@require_roles("admin","superadmin")
def ui_admin_users_new():
    """Modal for creating new user"""
    return "<div class='fixed inset-0 z-50 grid place-items-center bg-black/40'><div class='w-full max-w-lg bg-white rounded-2xl p-4'><h3 class='text-lg font-semibold mb-4'>משתמש חדש</h3><p>טופס יתווסף בקרוב...</p><div class='flex gap-2 justify-end pt-4'><button onclick='closeModal()' class='btn'>בטל</button><button class='btn-primary'>שמור</button></div></div></div>"

@ui_bp.route("/ui/admin/tenants")
@require_roles("admin","superadmin")
def ui_admin_tenants():
    """Load tenants table via HTMX"""
    try:
        from server.models_sql import Business
        tenants = Business.query.filter_by(is_active=True).all()
        tenants_html = ""
        for t in tenants:
            tenants_html += f"<div class='flex items-center justify-between p-4 border-b border-gray-100 hover:bg-gray-50'><div><h4 class='font-medium text-gray-900'>{t.name}</h4><p class='text-sm text-gray-500'>נדלן ותיווך</p></div><div class='flex items-center space-x-2'><span class='px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800'>פעיל</span><button class='text-blue-600 hover:text-blue-800 text-sm mr-2'>עריכה</button></div></div>"
        return tenants_html
    except:
        return "<div class='p-4 text-center text-gray-500'>אין עסקים</div>"

@ui_bp.route("/ui/admin/users")
@require_roles("admin","superadmin")
def ui_admin_users():
    """Load users table via HTMX"""
    try:
        from server.models_sql import User
        users = User.query.limit(10).all()
        users_html = "<table class='w-full text-sm'><thead><tr class='border-b'><th class='p-2 text-right'>שם</th><th class='p-2 text-right'>אימייל</th><th class='p-2'>תפקיד</th><th class='p-2'></th></tr></thead><tbody>"
        for u in users:
            users_html += f"<tr class='border-b'><td class='p-2'>{getattr(u, 'name', getattr(u, 'email', 'משתמש'))}</td><td class='p-2'>{getattr(u, 'email', 'no-email')}</td><td class='p-2'>{getattr(u, 'role', 'agent')}</td><td class='p-2 text-left'><button class='btn'>ערוך</button></td></tr>"
        users_html += "</tbody></table>"
        return users_html
    except Exception as e:
        return f"<div class='p-4 text-center text-gray-500'>שגיאה: {e}</div>"

# === BUSINESS HTMX ROUTES ===
@ui_bp.route("/ui/biz/users/new")
@require_roles("admin","superadmin","manager")
def ui_biz_users_new():
    """Modal for creating new user in business"""
    return "<div class='fixed inset-0 z-50 grid place-items-center bg-black/40'><div class='w-full max-w-lg bg-white rounded-2xl p-4'><h3 class='text-lg font-semibold mb-4'>משתמש חדש בעסק</h3><p>טופס יתווסף בקרוב...</p><div class='flex gap-2 justify-end pt-4'><button onclick='closeModal()' class='btn'>בטל</button><button class='btn-primary'>שמור</button></div></div></div>"

@ui_bp.route("/ui/biz/users")
@require_roles("admin","superadmin","manager","agent")
def ui_biz_users():
    """Load business users table via HTMX"""
    try:
        from server.models_sql import User
        bid = effective_business_id()
        
        if bid:
            users = User.query.filter_by(business_id=bid).all()
        else:
            users = []
            
        users_html = "<table class='w-full text-sm'><thead><tr class='border-b'><th class='p-2 text-right'>שם</th><th class='p-2 text-right'>אימייל</th><th class='p-2'>תפקיד</th><th class='p-2'>סטטוס</th><th class='p-2'></th></tr></thead><tbody>"
        for u in users:
            status = 'פעיל' if getattr(u, 'enabled', True) else 'מושבת'
            users_html += f"<tr class='border-b'><td class='p-2'>{getattr(u, 'name', getattr(u, 'email', 'משתמש'))}</td><td class='p-2'>{getattr(u, 'email', 'no-email')}</td><td class='p-2'>{getattr(u, 'role', 'agent')}</td><td class='p-2'>{status}</td><td class='p-2 text-left'><button class='btn'>ערוך</button></td></tr>"
        users_html += "</tbody></table>"
        return users_html
    except Exception as e:
        return f"<div class='p-4 text-center text-gray-500'>שגיאה: {e}</div>"

# === AUTH API ROUTES ===
@ui_bp.route('/api/ui/login', methods=['POST'])
def api_login():
    """Handle login form submission"""
    try:
        data = request.get_json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        
        if not email or not password:
            return jsonify({"success": False, "error": "נדרשים אימייל וסיסמה"}), 400

        # Simple admin login for development
        if email == "admin@admin.com" and password == "admin123":
            session["al_user"] = {
                "id": "admin-1",
                "name": "מנהל מערכת",
                "email": "admin@admin.com",
                "role": "admin",
                "business_id": None,
            }
            return jsonify({
                "success": True,
                "user": session["al_user"]
            })
        elif email == "business@test.com" and password == "test123":
            session["al_user"] = {
                "id": "biz-1",
                "name": "מנהל עסק",
                "email": "business@test.com",
                "role": "manager",
                "business_id": "biz-1",
            }
            return jsonify({
                "success": True,
                "user": session["al_user"]
            })
        else:
            return jsonify({"success": False, "error": "פרטי התחברות שגויים"}), 401
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת התחברות: {str(e)}'}), 500

@ui_bp.route('/api/ui/logout', methods=['GET', 'POST'])
def api_logout():
    """Handle logout"""
    try:
        session.clear()
        if request.method == 'GET':
            return redirect(url_for('ui.login'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Alias for logout link in sidebar
@ui_bp.route('/logout')
def logout():
    """Direct logout route"""
    return api_logout()