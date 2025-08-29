"""
UI Routes for Flask + Jinja + Tailwind + HTMX
Based on attached instructions - EXACT IMPLEMENTATION
"""
from flask import render_template, request, redirect, url_for, session, jsonify, flash, g, render_template_string
from server.ui import ui_bp
from server.routes_auth import require_roles, effective_business_id
import requests
import os

# Base URL for API calls
API_BASE = os.getenv('PUBLIC_BASE_URL', 'http://localhost:5000')

def _load_counters_for_admin():
    """Load counters for admin dashboard"""
    try:
        from server.models_sql import User, Business, CallLog
        from server.db import db
        
        tenants_active = db.session.query(Business).filter_by(is_active=True).count()
        users_pending = db.session.query(User).filter_by(is_active=False).count()
        today_calls = db.session.query(CallLog).filter(
            CallLog.created_at >= db.func.current_date()
        ).count() if hasattr(CallLog, 'created_at') else 0
        
        return {
            'tenants_active': tenants_active,
            'users_pending': users_pending,
            'today_calls': today_calls,
            'whatsapp_unread': 0  # TODO: implement when WhatsApp tables exist
        }
    except Exception as e:
        return {
            'tenants_active': 0,
            'users_pending': 0,
            'today_calls': 0,
            'whatsapp_unread': 0
        }

def _load_counters_for_business(business_id):
    """Load counters for business dashboard"""
    try:
        from server.models_sql import User, CallLog
        from server.db import db
        
        if not business_id:
            return {'today_calls': 0, 'whatsapp_unread': 0}
            
        today_calls = db.session.query(CallLog).filter(
            CallLog.business_id == business_id,
            CallLog.created_at >= db.func.current_date()
        ).count() if hasattr(CallLog, 'business_id') and hasattr(CallLog, 'created_at') else 0
        
        return {
            'today_calls': today_calls,
            'whatsapp_unread': 0  # TODO: implement when WhatsApp tables exist
        }
    except Exception as e:
        return {'today_calls': 0, 'whatsapp_unread': 0}

@ui_bp.get("/")
def home():
    if getattr(g, "user", None):
        return redirect(url_for("ui.admin_home") if g.user["role"] in ("admin","superadmin") else url_for("ui.biz_home"))
    return redirect(url_for("ui.login"))

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

@ui_bp.get("/app/admin")
@require_roles("admin","superadmin")
def admin_home():
    # active מגדיר פריט פעיל בסיידבר
    try:
        from server.models_sql import Business
        tenants = Business.query.filter_by(is_active=True).all()
    except:
        tenants = []
        
    return render_template("admin.html",
        page_title="איזור מנהל",
        role=g.user["role"], current_user=g.user,
        active="admin_home",
        current_business_id=request.args.get("business_id"),
        counters=_load_counters_for_admin(),
        tenants=tenants
    )

@ui_bp.get("/app/biz")
@require_roles("admin","superadmin","manager","agent")
def biz_home():
    bid = effective_business_id()
    return render_template("business.html",
        page_title="איזור עסק",
        role=g.user["role"], current_user=g.user,
        active="biz_whatsapp",
        current_business_id=bid,
        counters=_load_counters_for_business(bid)
    )

# Admin: החלפת עסק פעיל (לסנן דפים וקישורים)
@ui_bp.get("/ui/admin/switch_business")
@require_roles("admin","superadmin")
def ui_admin_switch_business():
    bid = request.args.get("business_id","")
    # אפשר לשמור cookie קצר לצרכי UI, או פשוט לעשות redirect:
    return render_template_string('<div id="switchHook"></div><script>location = "/app/admin?business_id={{bid}}"</script>', bid=bid)

# HTMX Partials for Modals
@ui_bp.get("/ui/admin/tenants/new")
@require_roles("admin","superadmin")
def ui_admin_tenants_new():
    """Modal for adding new business"""
    return render_template_string('''
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick="closeModal()">
      <div class="bg-white rounded-xl p-6 w-full max-w-md mx-4" onclick="event.stopPropagation()">
        <h3 class="text-lg font-semibold mb-4">הוסף עסק חדש</h3>
        <form hx-post="/api/admin/business" hx-target="#modal" hx-swap="outerHTML">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-1">שם העסק</label>
              <input name="name" type="text" required class="w-full px-3 py-2 border rounded-xl" placeholder="שם העסק"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">תחום</label>
              <input name="industry" type="text" class="w-full px-3 py-2 border rounded-xl" placeholder="נדלן, שירותים וכו'"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">אימייל ליצירת משתמש ראשי</label>
              <input name="admin_email" type="email" required class="w-full px-3 py-2 border rounded-xl" placeholder="admin@business.com"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">סיסמה</label>
              <input name="password" type="password" required class="w-full px-3 py-2 border rounded-xl" placeholder="סיסמה חזקה"/>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button type="submit" class="btn-primary flex-1">צור עסק</button>
            <button type="button" onclick="closeModal()" class="btn flex-1">ביטול</button>
          </div>
        </form>
      </div>
    </div>
    ''')

@ui_bp.get("/ui/admin/users/new")
@require_roles("admin","superadmin")
def ui_admin_users_new():
    """Modal for adding new user"""
    try:
        from server.models_sql import Business
        businesses = Business.query.filter_by(is_active=True).all()
    except:
        businesses = []
        
    business_options = ""
    for b in businesses:
        business_options += f'<option value="{b.id}">{b.name}</option>'
    
    return render_template_string(f'''
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick="closeModal()">
      <div class="bg-white rounded-xl p-6 w-full max-w-md mx-4" onclick="event.stopPropagation()">
        <h3 class="text-lg font-semibold mb-4">הוסף משתמש חדש</h3>
        <form hx-post="/api/admin/user" hx-target="#modal" hx-swap="outerHTML">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-1">שם מלא</label>
              <input name="name" type="text" required class="w-full px-3 py-2 border rounded-xl" placeholder="שם המשתמש"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">אימייל</label>
              <input name="email" type="email" required class="w-full px-3 py-2 border rounded-xl" placeholder="user@example.com"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">סיסמה</label>
              <input name="password" type="password" required class="w-full px-3 py-2 border rounded-xl" placeholder="סיסמה חזקה"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">תפקיד</label>
              <select name="role" required class="w-full px-3 py-2 border rounded-xl">
                <option value="">בחר תפקיד</option>
                <option value="admin">מנהל מערכת</option>
                <option value="manager">מנהל עסק</option>
                <option value="agent">נציג</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">עסק</label>
              <select name="business_id" class="w-full px-3 py-2 border rounded-xl">
                <option value="">ללא עסק (מנהל מערכת)</option>
                {business_options}
              </select>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button type="submit" class="btn-primary flex-1">צור משתמש</button>
            <button type="button" onclick="closeModal()" class="btn flex-1">ביטול</button>
          </div>
        </form>
      </div>
    </div>
    ''')

# HTMX Tables
@ui_bp.get("/ui/admin/users")
@require_roles("admin","superadmin")
def ui_admin_users_table():
    """Users table for admin"""
    try:
        from server.models_sql import User, Business
        from server.db import db
        
        q = request.args.get('q', '').strip()
        business_id = request.args.get('business_id', '')
        
        query = db.session.query(User).filter_by(is_active=True)
        
        if q:
            query = query.filter(User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
        if business_id:
            query = query.filter_by(business_id=business_id)
            
        users = query.all()
        
    except Exception as e:
        users = []
    
    table_html = '''
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">משתמש</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">תפקיד</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">עסק</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">פעולות</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
    '''
    
    for user in users:
        role_color = "bg-red-100 text-red-800" if user.role == "admin" else "bg-blue-100 text-blue-800"
        business_name = "מנהל מערכת" if not user.business_id else f"עסק {user.business_id}"
        
        table_html += f'''
          <tr class="hover:bg-gray-50">
            <td class="px-4 py-3">
              <div class="flex items-center">
                <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {user.name[0] if user.name else user.email[0]}
                </div>
                <div class="mr-3">
                  <p class="text-sm font-medium text-gray-900">{user.name or user.email}</p>
                  <p class="text-sm text-gray-500">{user.email}</p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3">
              <span class="inline-flex px-2 py-1 text-xs font-medium rounded-full {role_color}">
                {user.role}
              </span>
            </td>
            <td class="px-4 py-3 text-sm text-gray-900">{business_name}</td>
            <td class="px-4 py-3">
              <div class="flex space-x-2">
                <button onclick="editUser({user.id})" class="text-blue-600 hover:text-blue-800 text-sm">עריכה</button>
                <button onclick="changeUserPassword({user.id})" class="text-purple-600 hover:text-purple-800 text-sm">סיסמה</button>
              </div>
            </td>
          </tr>
        '''
    
    table_html += '''
        </tbody>
      </table>
    </div>
    '''
    
    return table_html

# Admin Tenants Table - FIX 404 ERROR
@ui_bp.get("/ui/admin/tenants")
@require_roles("admin","superadmin")
def ui_admin_tenants_table():
    """Tenants table for admin"""
    try:
        from server.models_sql import Business
        from server.db import db
        
        q = request.args.get('q', '').strip()
        business_id = request.args.get('business_id', '')
        
        query = db.session.query(Business).filter_by(is_active=True)
        
        if q:
            query = query.filter(Business.name.ilike(f'%{q}%'))
            
        businesses = query.all()
        
    except Exception as e:
        businesses = []
    
    table_html = '''
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">עסק</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">תחום</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">סטטוס</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">פעולות</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
    '''
    
    for business in businesses:
        status_color = "bg-green-100 text-green-800" if business.is_active else "bg-red-100 text-red-800"
        status_text = "פעיל" if business.is_active else "לא פעיל"
        
        table_html += f'''
          <tr class="hover:bg-gray-50">
            <td class="px-4 py-3">
              <div class="flex items-center">
                <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {business.name[0] if business.name else 'B'}
                </div>
                <div class="mr-3">
                  <p class="text-sm font-medium text-gray-900">{business.name}</p>
                  <p class="text-sm text-gray-500">ID: {business.id}</p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3 text-sm text-gray-900">{getattr(business, 'industry', 'לא מוגדר')}</td>
            <td class="px-4 py-3">
              <span class="inline-flex px-2 py-1 text-xs font-medium rounded-full {status_color}">
                {status_text}
              </span>
            </td>
            <td class="px-4 py-3">
              <div class="flex space-x-2">
                <button onclick="editBusiness({business.id})" class="text-blue-600 hover:text-blue-800 text-sm">עריכה</button>
                <button onclick="loginAsBusiness({business.id})" class="text-green-600 hover:text-green-800 text-sm">התחבר כעסק</button>
                <button onclick="changeBusinessPassword({business.id})" class="text-purple-600 hover:text-purple-800 text-sm">סיסמה</button>
              </div>
            </td>
          </tr>
        '''
    
    table_html += '''
        </tbody>
      </table>
    </div>
    '''
    
    return table_html

# Business User Management Partials
@ui_bp.get("/ui/business/users/new")
@require_roles("admin","superadmin","manager")
def ui_business_users_new():
    """Modal for adding new user to business"""
    business_id = effective_business_id()
    if not business_id:
        return render_template_string('<div class="p-4 text-red-500">שגיאה: לא נמצא עסק פעיל</div>')
    
    return render_template_string(f'''
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick="closeModal()">
      <div class="bg-white rounded-xl p-6 w-full max-w-md mx-4" onclick="event.stopPropagation()">
        <h3 class="text-lg font-semibold mb-4">הוסף משתמש לעסק</h3>
        <form hx-post="/api/business/users" hx-target="#modal" hx-swap="outerHTML">
          <input type="hidden" name="business_id" value="{business_id}"/>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium mb-1">שם מלא</label>
              <input name="name" type="text" required class="w-full px-3 py-2 border rounded-xl" placeholder="שם המשתמש"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">אימייל</label>
              <input name="email" type="email" required class="w-full px-3 py-2 border rounded-xl" placeholder="user@example.com"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">סיסמה</label>
              <input name="password" type="password" required class="w-full px-3 py-2 border rounded-xl" placeholder="סיסמה חזקה"/>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">תפקיד</label>
              <select name="role" required class="w-full px-3 py-2 border rounded-xl">
                <option value="">בחר תפקיד</option>
                <option value="manager">מנהל עסק</option>
                <option value="agent">נציג</option>
              </select>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button type="submit" class="btn-primary flex-1">הוסף משתמש</button>
            <button type="button" onclick="closeModal()" class="btn flex-1">ביטול</button>
          </div>
        </form>
      </div>
    </div>
    ''')

@ui_bp.get("/ui/business/users")
@require_roles("admin","superadmin","manager","agent")
def ui_business_users_table():
    """Users table for business (limited to business users only)"""
    try:
        from server.models_sql import User, Business
        from server.db import db
        
        business_id = effective_business_id()
        if not business_id:
            return '<div class="p-4 text-red-500">שגיאה: לא נמצא עסק פעיל</div>'
        
        q = request.args.get('q', '').strip()
        
        query = db.session.query(User).filter_by(is_active=True, business_id=business_id)
        
        if q:
            query = query.filter(User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
            
        users = query.all()
        
    except Exception as e:
        users = []
    
    table_html = '''
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">משתמש</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">תפקיד</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">סטטוס</th>
            <th class="px-4 py-3 text-right text-sm font-medium text-gray-500">פעולות</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
    '''
    
    for user in users:
        role_color = "bg-blue-100 text-blue-800" if user.role == "manager" else "bg-green-100 text-green-800"
        role_text = "מנהל עסק" if user.role == "manager" else "נציג"
        status_color = "bg-green-100 text-green-800" if user.is_active else "bg-red-100 text-red-800"
        status_text = "פעיל" if user.is_active else "לא פעיל"
        
        table_html += f'''
          <tr class="hover:bg-gray-50">
            <td class="px-4 py-3">
              <div class="flex items-center">
                <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {user.name[0] if user.name else user.email[0]}
                </div>
                <div class="mr-3">
                  <p class="text-sm font-medium text-gray-900">{user.name or user.email}</p>
                  <p class="text-sm text-gray-500">{user.email}</p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3">
              <span class="inline-flex px-2 py-1 text-xs font-medium rounded-full {role_color}">
                {role_text}
              </span>
            </td>
            <td class="px-4 py-3">
              <span class="inline-flex px-2 py-1 text-xs font-medium rounded-full {status_color}">
                {status_text}
              </span>
            </td>
            <td class="px-4 py-3">
              <div class="flex space-x-2">
                <button onclick="editBusinessUser({user.id})" class="text-blue-600 hover:text-blue-800 text-sm">עריכה</button>
                <button onclick="changeBusinessUserPassword({user.id})" class="text-purple-600 hover:text-purple-800 text-sm">סיסמה</button>
              </div>
            </td>
          </tr>
        '''
    
    table_html += '''
        </tbody>
      </table>
    </div>
    '''
    
    return table_html

# Additional route for logout (to complete the logout link in sidebar)
@ui_bp.get("/logout")
def logout():
    """Handle logout via GET and redirect to login"""
    session.pop('al_user', None)
    session.pop('al_token', None)
    session.pop('user', None)
    session.pop('token', None)
    session.clear()
    return redirect(url_for('ui.login'))

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
    """Handle logout - clear all session data"""
    try:
        # Clear all session data
        session.pop('al_user', None)
        session.pop('al_token', None)
        session.pop('user', None)
        session.pop('token', None)
        session.clear()  # Clear everything
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500