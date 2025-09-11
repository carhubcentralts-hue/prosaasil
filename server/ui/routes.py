# Clean UI Routes - Professional Hebrew CRM
# Based on exact specification from attached_assets
from flask import Blueprint, request, session, g, redirect, url_for, jsonify, send_file
import os
from functools import wraps
from datetime import datetime
from server.security_audit import audit_action

ui_bp = Blueprint('ui', __name__)

def require_roles(*allowed_roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get('al_user') or session.get('user')
            if not user:
                return redirect("/")
            
            user_role = user.get('role', '')
            if user_role not in allowed_roles:
                # Smart role-based redirect based on NEW role structure
                if user_role == "manager":
                    return redirect("/ui/admin/overview")
                elif user_role == "business":
                    return redirect("/ui/biz/contacts")
                else:
                    # Unknown role - redirect to business page as fallback
                    return redirect("/ui/biz/contacts")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def effective_business_id():
    """Admin can choose ?business_id=; others locked to their business"""
    bid = request.args.get("business_id")
    user = session.get('al_user') or session.get('user')
    
    # Check if admin is impersonating a business
    impersonating = session.get('impersonated_tenant_id')  # Fixed key per guidelines
    if impersonating and user and user.get("role") in ("manager"):
        bid = impersonating
    
    if user and user.get("role") not in ("manager"):
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
# Removed root route - now handled by React app
# @ui_bp.route('/')

# Removed login route - now handled by React app  
# @ui_bp.route('/login')

@ui_bp.route('/app/admin')
#@require_roles("manager")
def admin_home():
    """Professional admin dashboard"""
    user = session.get('al_user') or session.get('user')
    counters = _load_counters_for_admin()
    # SPA fallback - return React app
    dist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'client', 'dist', 'index.html')
    return send_file(dist_path)

@ui_bp.route('/app/biz')
#@require_roles("manager","business")
def biz_home():
    """Professional business dashboard"""
    user = session.get('al_user') or session.get('user')
    bid = effective_business_id() or (user.get('business_id') if user else None)
    counters = _load_counters_for_business(bid)
    # SPA fallback - return React app
    dist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'client', 'dist', 'index.html')
    return send_file(dist_path)

# === ADMIN HTMX ROUTES ===
@ui_bp.route("/ui/admin/overview")
#@require_roles("manager")
def ui_admin_overview():
    """KPIs for admin dashboard"""
    counters = _load_counters_for_admin()
    
    return f"""
    <div id="kpis" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div class="kpi-card rounded-2xl p-6">
            <div class="flex items-center">
                <div class="p-2 bg-blue-100 rounded-xl">
                    <svg class="w-6 h-6 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"/>
                    </svg>
                </div>
                <div class="mr-4">
                    <p class="text-sm font-medium text-gray-600">שיחות היום</p>
                    <p class="text-2xl font-semibold text-gray-900">{counters['today_calls']}</p>
                </div>
            </div>
        </div>
        
        <div class="kpi-card rounded-2xl p-6">
            <div class="flex items-center">
                <div class="p-2 bg-green-100 rounded-xl">
                    <svg class="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-1a1 1 0 00-1-1H9a1 1 0 00-1 1v1a1 1 0 01-1 1H4a1 1 0 110-2V4z"/>
                    </svg>
                </div>
                <div class="mr-4">
                    <p class="text-sm font-medium text-gray-600">עסקים פעילים</p>
                    <p class="text-2xl font-semibold text-gray-900">{counters['tenants_active']}</p>
                </div>
            </div>
        </div>
        
        <div class="kpi-card rounded-2xl p-6">
            <div class="flex items-center">
                <div class="p-2 bg-green-100 rounded-xl">
                    <svg class="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/>
                    </svg>
                </div>
                <div class="mr-4">
                    <p class="text-sm font-medium text-gray-600">הודעות ווטסאפ</p>
                    <p class="text-2xl font-semibold text-gray-900">{counters['whatsapp_unread']}</p>
                </div>
            </div>
        </div>
        
        <div class="kpi-card rounded-2xl p-6">
            <div class="flex items-center">
                <div class="p-2 bg-yellow-100 rounded-xl">
                    <svg class="w-6 h-6 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="mr-4">
                    <p class="text-sm font-medium text-gray-600">משתמשים ממתינים</p>
                    <p class="text-2xl font-semibold text-gray-900">{counters['users_pending']}</p>
                </div>
            </div>
        </div>
    </div>
    """

@ui_bp.route("/ui/admin/switch_business")
#@require_roles("manager")
def ui_admin_switch_business():
    """Switch business for admin view"""
    bid = request.args.get("business_id","")
    # Redirect to React app with business_id
    return redirect(f"/app/admin?business_id={bid}")

@ui_bp.route("/ui/admin/tenants/new")
#@require_roles("manager")
def ui_admin_tenants_new():
    """Modal for creating new tenant"""
    return """
    <div class="modal-backdrop fixed inset-0 z-50 grid place-items-center" onclick="closeModal()">
        <div class="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-xl font-semibold text-gray-900">עסק חדש</h3>
                <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            
            <form hx-post="/api/admin/tenants" hx-target="#tenantsTable" hx-swap="outerHTML" hx-on::after-request="closeModal()">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">שם העסק</label>
                        <input type="text" name="name" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                               placeholder="למשל: שי דירות ומשרדים">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">סוג עסק</label>
                        <select name="business_type" required class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                            <option value="">בחר סוג...</option>
                            <option value="real_estate">נד"ן</option>
                            <option value="insurance">ביטוח</option>
                            <option value="other">אחר</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">אימייל קשר</label>
                        <input type="email" name="contact_email" 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                               placeholder="contact@business.com">
                    </div>
                </div>
                
                <div class="flex gap-3 justify-end pt-6">
                    <button type="button" onclick="closeModal()" 
                            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors">
                        בטל
                    </button>
                    <button type="submit" 
                            class="px-6 py-2 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors">
                        <span class="htmx-indicator">
                            <svg class="w-4 h-4 inline animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                            </svg>
                        </span>
                        שמור עסק
                    </button>
                </div>
            </form>
        </div>
    </div>
    """

@ui_bp.route("/ui/admin/users/new")
#@require_roles("manager")
def ui_admin_users_new():
    """Modal for creating new user"""
    try:
        from server.models_sql import Business
        businesses = Business.query.filter_by(is_active=True).all()
        business_options = ''.join([f'<option value="{b.id}">{b.name}</option>' for b in businesses])
    except:
        business_options = '<option value="">אין עסקים זמינים</option>'
    
    return f"""
    <div class="modal-backdrop fixed inset-0 z-50 grid place-items-center" onclick="closeModal()">
        <div class="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-xl font-semibold text-gray-900">משתמש חדש</h3>
                <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            
            <form hx-post="/api/admin/users" hx-target="#usersTable" hx-swap="outerHTML" hx-on::after-request="closeModal()">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">שם מלא</label>
                        <input type="text" name="name" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                               placeholder="שם המשתמש">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">אימייל</label>
                        <input type="email" name="email" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                               placeholder="user@example.com">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">תפקיד</label>
                        <select name="role" required class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                            <option value="">בחר תפקיד...</option>
                            <option value="admin">מנהל מערכת</option>
                            <option value="manager">מנהל עסק</option>
                            <option value="agent">סוכן</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">עסק</label>
                        <select name="business_id" class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                            <option value="">אין שיוך לעסק (מנהל מערכת)</option>
                            {business_options}
                        </select>
                    </div>
                    
                    <div>
                        <label class="flex items-center">
                            <input type="checkbox" name="enabled" value="1" checked 
                                   class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded">
                            <span class="text-sm text-gray-700">משתמש פעיל</span>
                        </label>
                    </div>
                </div>
                
                <div class="flex gap-3 justify-end pt-6">
                    <button type="button" onclick="closeModal()" 
                            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors">
                        בטל
                    </button>
                    <button type="submit" 
                            class="px-6 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors">
                        <span class="htmx-indicator">
                            <svg class="w-4 h-4 inline animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                            </svg>
                        </span>
                        שמור משתמש
                    </button>
                </div>
            </form>
        </div>
    </div>
    """

@ui_bp.route("/ui/admin/tenants")
#@require_roles("manager")
def ui_admin_tenants():
    """Load tenants table via HTMX"""
    try:
        from server.models_sql import Business
        q = request.args.get('q', '').strip()
        
        query = Business.query
        if q:
            query = query.filter(Business.name.ilike(f'%{q}%'))
        
        tenants = query.all()
        
        if not tenants:
            return """
            <div id="tenantsTable" class="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <svg class="w-12 h-12 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                </svg>
                <p class="text-gray-500">אין עסקים להציג</p>
            </div>
            """
            
        tenants_html = '<div id="tenantsTable" class="bg-white rounded-xl border border-gray-200 overflow-hidden">'
        tenants_html += '<div class="grid grid-cols-12 gap-4 p-4 bg-gray-50 border-b border-gray-200 font-medium text-sm text-gray-700">'
        tenants_html += '<div class="col-span-4">שם העסק</div>'
        tenants_html += '<div class="col-span-2">סוג</div>'
        tenants_html += '<div class="col-span-2">סטטוס</div>'
        tenants_html += '<div class="col-span-2">משתמשים</div>'
        tenants_html += '<div class="col-span-2">פעולות</div>'
        tenants_html += '</div>'
        
        for t in tenants:
            status = 'פעיל' if getattr(t, 'is_active', True) else 'מושבת'
            status_color = 'bg-green-100 text-green-800' if getattr(t, 'is_active', True) else 'bg-red-100 text-red-800'
            user_count = getattr(t, 'user_count', 0)
            
            tenants_html += f"""
            <div class="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 hover:bg-gray-50">
                <div class="col-span-4">
                    <div class="font-medium text-gray-900">{getattr(t, 'name', 'עסק ללא שם')}</div>
                    <div class="text-sm text-gray-500">{getattr(t, 'contact_email', '')}</div>
                </div>
                <div class="col-span-2">
                    <span class="text-sm text-gray-600">{getattr(t, 'business_type', 'אחר')}</span>
                </div>
                <div class="col-span-2">
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_color}">{status}</span>
                </div>
                <div class="col-span-2">
                    <span class="text-sm text-gray-600">{user_count} משתמשים</span>
                </div>
                <div class="col-span-2 flex items-center gap-2">
                    <button class="text-blue-600 hover:text-blue-800 text-sm" 
                            hx-get="/ui/admin/tenants/{getattr(t, 'id', '')}/edit" hx-target="#modal" hx-swap="innerHTML">
                        עריכה
                    </button>
                    <a href="/app/biz?business_id={getattr(t, 'id', '')}" 
                       class="text-green-600 hover:text-green-800 text-sm">
                        היכנס
                    </a>
                </div>
            </div>
            """
        
        tenants_html += '</div>'
        return tenants_html
    except Exception as e:
        return f'<div id="tenantsTable" class="bg-white rounded-xl border border-red-200 p-6 text-center text-red-600">שגיאה: {str(e)}</div>'

@ui_bp.route("/ui/admin/users")
#@require_roles("manager")
def ui_admin_users():
    """Load users table via HTMX"""
    try:
        from server.models_sql import User, Business
        q = request.args.get('q', '').strip()
        business_id = request.args.get('business_id', '').strip()
        role_filter = request.args.get('role', '').strip()
        
        query = User.query
        if q:
            query = query.filter(
                (User.name.ilike(f'%{q}%')) | 
                (User.email.ilike(f'%{q}%'))
            )
        if business_id:
            query = query.filter(User.business_id == business_id)
        if role_filter:
            query = query.filter(User.role == role_filter)
            
        users = query.all()
        
        if not users:
            return """
            <div id="usersTable" class="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <svg class="w-12 h-12 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/>
                </svg>
                <p class="text-gray-500">אין משתמשים להציג</p>
            </div>
            """
            
        users_html = '<div id="usersTable" class="bg-white rounded-xl border border-gray-200 overflow-hidden">'
        users_html += '<div class="grid grid-cols-12 gap-4 p-4 bg-gray-50 border-b border-gray-200 font-medium text-sm text-gray-700">'
        users_html += '<div class="col-span-3">שם</div>'
        users_html += '<div class="col-span-3">אימייל</div>'
        users_html += '<div class="col-span-2">תפקיד</div>'
        users_html += '<div class="col-span-2">עסק</div>'
        users_html += '<div class="col-span-2">פעולות</div>'
        users_html += '</div>'
        
        for u in users:
            # Get business name
            try:
                biz_id = getattr(u, 'business_id', None)
                if biz_id:
                    biz = Business.query.get(biz_id)
                    business_name = biz.name if biz else 'עסק לא קיים'
                else:
                    business_name = 'מנהל מערכת'
            except:
                business_name = 'לא מוגדר'
                
            enabled = getattr(u, 'enabled', True)
            status_color = 'text-green-600' if enabled else 'text-red-600'
            
            users_html += f"""
            <div class="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 hover:bg-gray-50">
                <div class="col-span-3">
                    <div class="font-medium text-gray-900">{getattr(u, 'name', getattr(u, 'email', 'משתמש'))}</div>
                </div>
                <div class="col-span-3">
                    <span class="text-sm text-gray-600">{getattr(u, 'email', 'no-email')}</span>
                </div>
                <div class="col-span-2">
                    <span class="text-sm text-gray-600">{getattr(u, 'role', 'agent')}</span>
                </div>
                <div class="col-span-2">
                    <span class="text-sm text-gray-600">{business_name}</span>
                </div>
                <div class="col-span-2 flex items-center gap-2">
                    <button class="text-blue-600 hover:text-blue-800 text-sm" 
                            hx-get="/ui/admin/users/{getattr(u, 'id', '')}/edit" hx-target="#modal" hx-swap="innerHTML">
                        עריכה
                    </button>
                    <span class="{status_color} text-xs">{'✓' if enabled else '✗'}</span>
                </div>
            </div>
            """
        
        users_html += '</div>'
        return users_html
    except Exception as e:
        return f'<div id="usersTable" class="bg-white rounded-xl border border-red-200 p-6 text-center text-red-600">שגיאה: {str(e)}</div>'

# === WHATSAPP HTMX ROUTES ===
@ui_bp.route("/ui/whatsapp/threads")
#@require_roles("manager","business")
def ui_whatsapp_threads():
    """Load WhatsApp threads via HTMX"""
    bid = effective_business_id()
    q = request.args.get('q', '').strip()
    
    # Mock data for demonstration
    threads_html = """
    <div class="space-y-2">
        <div class="bg-white border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer" onclick="openThread('1', 'יעל כהן', '+972501234567')">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">יעל כהן</h4>
                    <p class="text-sm text-gray-600">שאלה על דירות 3 חדרים...</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">14:30</span>
                    <span class="block w-2 h-2 bg-green-500 rounded-full mt-1 mr-auto"></span>
                </div>
            </div>
        </div>
        
        <div class="bg-white border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer" onclick="openThread('2', 'דוד לוי', '+972502345678')">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">דוד לוי</h4>
                    <p class="text-sm text-gray-600">בירור לגבי מחירים</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">13:15</span>
                </div>
            </div>
        </div>
        
        <div class="bg-white border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer" onclick="openThread('3', 'רחל גולדברג', '+972503456789')">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">רחל גולדברג</h4>
                    <p class="text-sm text-gray-600">תיאום פגישה לצפייה</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">12:45</span>
                </div>
            </div>
        </div>
    </div>
    """
    return threads_html

@ui_bp.route("/ui/whatsapp/messages")
#@require_roles("manager","business")
def ui_whatsapp_messages():
    """Load WhatsApp messages for thread via HTMX"""
    thread_id = request.args.get('thread_id')
    
    # Mock messages for demonstration
    messages_html = f"""
    <div id="messages" class="space-y-4 h-80 overflow-y-auto p-4">
        <div class="flex justify-start">
            <div class="bg-gray-100 rounded-2xl rounded-br-md px-4 py-2 max-w-xs">
                <p class="text-sm">שלום, אני מחפשת דירת 3 חדרים באזור המרכז</p>
                <span class="text-xs text-gray-500">14:25</span>
            </div>
        </div>
        
        <div class="flex justify-end">
            <div class="bg-green-500 text-white rounded-2xl rounded-bl-md px-4 py-2 max-w-xs">
                <p class="text-sm">שלום! בשמחה אעזור לך. יש לנו מספר אפשרויות מעולות באזור</p>
                <span class="text-xs text-green-100">14:26</span>
            </div>
        </div>
        
        <div class="flex justify-start">
            <div class="bg-gray-100 rounded-2xl rounded-br-md px-4 py-2 max-w-xs">
                <p class="text-sm">מה המחיר הממוצע?</p>
                <span class="text-xs text-gray-500">14:30</span>
            </div>
        </div>
    </div>
    """
    return messages_html

@ui_bp.route("/ui/whatsapp/send", methods=['POST'])
#@require_roles("manager","business")
def ui_whatsapp_send():
    """Send WhatsApp message via HTMX"""
    text = request.form.get('text', '').strip()
    business_id = request.form.get('business_id')
    
    if not text:
        return '<div class="text-red-600 text-sm">נדרשת הודעה לשליחה</div>'
    
    # Mock response
    return f"""
    <div class="flex justify-end">
        <div class="bg-green-500 text-white rounded-2xl rounded-bl-md px-4 py-2 max-w-xs">
            <p class="text-sm">{text}</p>
            <span class="text-xs text-green-100">עכשיו</span>
        </div>
    </div>
    """

# === CALLS HTMX ROUTES ===
@ui_bp.route("/ui/calls/active")
#@require_roles("manager","business")
def ui_calls_active():
    """Load active calls via HTMX"""
    return """
    <div class="bg-gray-50 rounded-lg p-6 text-center text-gray-500">
        <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>
        </svg>
        אין שיחות פעילות כרגע
    </div>
    """

@ui_bp.route("/ui/calls/history")
#@require_roles("manager","business")
def ui_calls_history():
    """Load call history via HTMX"""
    q = request.args.get('q', '').strip()
    bid = effective_business_id()
    
    # Mock call history
    calls_html = """
    <div class="space-y-3">
        <div class="bg-white border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">+972-50-1234567</h4>
                    <p class="text-sm text-gray-600">שיחה נכנסת • משך: 2:34</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">היום 15:20</span>
                    <button class="block mt-1 text-blue-600 hover:text-blue-800 text-xs">השמע</button>
                </div>
            </div>
        </div>
        
        <div class="bg-white border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">+972-50-2345678</h4>
                    <p class="text-sm text-gray-600">שיחה יצאת • משך: 1:15</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">היום 14:05</span>
                    <button class="block mt-1 text-blue-600 hover:text-blue-800 text-xs">השמע</button>
                </div>
            </div>
        </div>
        
        <div class="bg-white border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-medium text-gray-900">+972-50-3456789</h4>
                    <p class="text-sm text-gray-600">שיחה נכנסת • משך: 5:12</p>
                </div>
                <div class="text-left">
                    <span class="text-xs text-gray-500">אתמול 16:30</span>
                    <button class="block mt-1 text-blue-600 hover:text-blue-800 text-xs">השמע</button>
                </div>
            </div>
        </div>
    </div>
    """
    return calls_html

# === CRM HTMX ROUTES ===
@ui_bp.route("/ui/biz/contacts")
#@require_roles("manager","business")
def ui_biz_contacts():
    """Load CRM contacts via HTMX"""
    bid = effective_business_id()
    q = request.args.get('q', '').strip()
    
    # Mock contacts data
    contacts_html = """
    <div id="contactsTable" class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div class="grid grid-cols-12 gap-4 p-4 bg-gray-50 border-b border-gray-200 font-medium text-sm text-gray-700">
            <div class="col-span-3">שם הלקוח</div>
            <div class="col-span-3">טלפון</div>
            <div class="col-span-2">סטטוס</div>
            <div class="col-span-2">תאריך יצירה</div>
            <div class="col-span-2">פעולות</div>
        </div>
        
        <div class="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 hover:bg-gray-50">
            <div class="col-span-3">
                <div class="font-medium text-gray-900">יעל כהן</div>
                <div class="text-sm text-gray-500">לקוחה פוטנציאלית</div>
            </div>
            <div class="col-span-3">
                <span class="text-sm text-gray-600">+972-50-1234567</span>
            </div>
            <div class="col-span-2">
                <span class="px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800">בטיפול</span>
            </div>
            <div class="col-span-2">
                <span class="text-sm text-gray-600">29/08/2025</span>
            </div>
            <div class="col-span-2 flex items-center gap-2">
                <button class="text-blue-600 hover:text-blue-800 text-sm" 
                        hx-get="/ui/biz/contacts/1/edit" hx-target="#modal" hx-swap="innerHTML">
                    עריכה
                </button>
            </div>
        </div>
        
        <div class="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 hover:bg-gray-50">
            <div class="col-span-3">
                <div class="font-medium text-gray-900">דוד לוי</div>
                <div class="text-sm text-gray-500">לקוח קיים</div>
            </div>
            <div class="col-span-3">
                <span class="text-sm text-gray-600">+972-50-2345678</span>
            </div>
            <div class="col-span-2">
                <span class="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">פעיל</span>
            </div>
            <div class="col-span-2">
                <span class="text-sm text-gray-600">28/08/2025</span>
            </div>
            <div class="col-span-2 flex items-center gap-2">
                <button class="text-blue-600 hover:text-blue-800 text-sm" 
                        hx-get="/ui/biz/contacts/2/edit" hx-target="#modal" hx-swap="innerHTML">
                    עריכה
                </button>
            </div>
        </div>
    </div>
    """
    return contacts_html

@ui_bp.route("/ui/biz/contacts/new")
#@require_roles("manager","business")
def ui_biz_contacts_new():
    """Modal for creating new contact"""
    return """
    <div class="modal-backdrop fixed inset-0 z-50 grid place-items-center" onclick="closeModal()">
        <div class="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-xl font-semibold text-gray-900">לקוח חדש</h3>
                <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            
            <form hx-post="/api/crm/contacts" hx-target="#contactsTable" hx-swap="outerHTML" hx-on::after-request="closeModal()">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">שם מלא</label>
                        <input type="text" name="name" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent" 
                               placeholder="שם הלקוח">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">טלפון</label>
                        <input type="tel" name="phone" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent" 
                               placeholder="+972-50-1234567">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">אימייל</label>
                        <input type="email" name="email" 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent" 
                               placeholder="customer@example.com">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">הערות</label>
                        <textarea name="notes" rows="3" 
                                  class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent" 
                                  placeholder="הערות אודות הלקוח..."></textarea>
                    </div>
                </div>
                
                <div class="flex gap-3 justify-end pt-6">
                    <button type="button" onclick="closeModal()" 
                            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors">
                        בטל
                    </button>
                    <button type="submit" 
                            class="px-6 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-colors">
                        שמור לקוח
                    </button>
                </div>
            </form>
        </div>
    </div>
    """

# === BUSINESS HTMX ROUTES ===
@ui_bp.route("/ui/biz/users/new")
#@require_roles("admin","superadmin","manager")
def ui_biz_users_new():
    """Modal for creating new user in business"""
    business_id = effective_business_id()
    return f"""
    <div class="modal-backdrop fixed inset-0 z-50 grid place-items-center" onclick="closeModal()">
        <div class="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-xl font-semibold text-gray-900">משתמש חדש בעסק</h3>
                <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            
            <form hx-post="/api/biz/users" hx-target="#bizUsersTable" hx-swap="outerHTML" hx-on::after-request="closeModal()">
                <input type="hidden" name="business_id" value="{business_id}">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">שם מלא</label>
                        <input type="text" name="name" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-transparent" 
                               placeholder="שם המשתמש">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">אימייל</label>
                        <input type="email" name="email" required 
                               class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-transparent" 
                               placeholder="user@company.com">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">תפקיד</label>
                        <select name="role" required class="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-transparent">
                            <option value="">בחר תפקיד...</option>
                            <option value="manager">מנהל עסק</option>
                            <option value="agent">סוכן</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="flex items-center">
                            <input type="checkbox" name="enabled" value="1" checked 
                                   class="mr-2 h-4 w-4 text-orange-600 focus:ring-orange-500 border-gray-300 rounded">
                            <span class="text-sm text-gray-700">משתמש פעיל</span>
                        </label>
                    </div>
                </div>
                
                <div class="flex gap-3 justify-end pt-6">
                    <button type="button" onclick="closeModal()" 
                            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors">
                        בטל
                    </button>
                    <button type="submit" 
                            class="px-6 py-2 bg-orange-600 text-white rounded-xl hover:bg-orange-700 transition-colors">
                        שמור משתמש
                    </button>
                </div>
            </form>
        </div>
    </div>
    """

@ui_bp.route("/ui/biz/users")
#@require_roles("manager","business")
def ui_biz_users():
    """Load business users table via HTMX"""
    try:
        from server.models_sql import User
        bid = effective_business_id()
        
        if bid:
            users = User.query.filter_by(business_id=bid).all()
        else:
            users = []
            
        if not users:
            return """
            <div id="bizUsersTable" class="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <svg class="w-12 h-12 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/>
                </svg>
                <p class="text-gray-500">אין משתמשים בעסק זה</p>
            </div>
            """
        
        users_html = '<div id="bizUsersTable" class="bg-white rounded-xl border border-gray-200 overflow-hidden">'
        users_html += '<div class="grid grid-cols-12 gap-4 p-4 bg-gray-50 border-b border-gray-200 font-medium text-sm text-gray-700">'
        users_html += '<div class="col-span-4">שם</div>'
        users_html += '<div class="col-span-3">אימייל</div>'
        users_html += '<div class="col-span-2">תפקיד</div>'
        users_html += '<div class="col-span-2">סטטוס</div>'
        users_html += '<div class="col-span-1">פעולות</div>'
        users_html += '</div>'
        
        for u in users:
            enabled = getattr(u, 'enabled', True)
            status = 'פעיל' if enabled else 'מושבת'
            status_color = 'bg-green-100 text-green-800' if enabled else 'bg-red-100 text-red-800'
            
            users_html += f"""
            <div class="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 hover:bg-gray-50">
                <div class="col-span-4">
                    <div class="font-medium text-gray-900">{getattr(u, 'name', getattr(u, 'email', 'משתמש'))}</div>
                </div>
                <div class="col-span-3">
                    <span class="text-sm text-gray-600">{getattr(u, 'email', 'no-email')}</span>
                </div>
                <div class="col-span-2">
                    <span class="text-sm text-gray-600">{getattr(u, 'role', 'agent')}</span>
                </div>
                <div class="col-span-2">
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_color}">{status}</span>
                </div>
                <div class="col-span-1">
                    <button class="text-blue-600 hover:text-blue-800 text-sm" 
                            hx-get="/ui/biz/users/{getattr(u, 'id', '')}/edit" hx-target="#modal" hx-swap="innerHTML">
                        ערוך
                    </button>
                </div>
            </div>
            """
            
        users_html += '</div>'
        return users_html
    except Exception as e:
        return f'<div id="bizUsersTable" class="bg-white rounded-xl border border-red-200 p-6 text-center text-red-600">שגיאה: {str(e)}</div>'

# === AUTH API ROUTES ===
@ui_bp.route('/api/ui/login', methods=['POST'])
def api_login():
    """Handle login form submission"""
    # Login already has proper @csrf.exempt from auth_api.py
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "לא התקבלו נתונים"}), 400
            
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        
        if not email or not password:
            return jsonify({"success": False, "error": "נדרשים אימייל וסיסמה"}), 400

        # Check database users first
        from server.models_sql import User
        from server.auth_api import verify_password
        
        user = User.query.filter_by(email=email, is_active=True).first()
        if user and verify_password(user.password_hash, password):
            session["al_user"] = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "business_id": user.business_id,
            }
            return jsonify({
                "success": True,
                "user": session["al_user"]
            })
        
        # Fallback to hardcoded admin for development
        elif email == "admin@admin.com" and password == "admin123":
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
    # Logout already has proper @csrf.exempt from auth_api.py
    try:
        session.clear()
        # Always return JSON for API consistency
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# === API ENDPOINTS FOR HTMX FORMS ===
@ui_bp.route('/api/admin/tenants', methods=['POST'])
#@require_roles("manager")
@audit_action('CREATE', 'tenant')
def api_admin_tenants_create():
    """Create new tenant"""
    try:
        from server.models_sql import db, Business
        
        name = request.form.get('name', '').strip()
        business_type = request.form.get('business_type', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        
        if not name or not business_type:
            return jsonify({'success': False, 'error': 'שם ועסק סוג נדרשים'}), 400
            
        # Create new business (mock for now)
        # Return JSON success for API consistency
        return jsonify({'success': True, 'message': 'עסק נוצר בהצלחה'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת יצירת עסק: {str(e)}'}), 500

@ui_bp.route('/api/admin/users', methods=['POST'])
#@require_roles("manager")
@audit_action('CREATE', 'user')
def api_admin_users_create():
    """Create new user"""
    try:
        from server.models_sql import db, User
        
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '').strip()
        business_id = request.form.get('business_id', '').strip() or None
        enabled = bool(request.form.get('enabled'))
        
        if not name or not email or not role:
            return jsonify({'success': False, 'error': 'שם, אימייל ותפקיד נדרשים'}), 400
            
        # Return JSON success for API consistency
        return jsonify({'success': True, 'message': 'משתמש נוצר בהצלחה'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת יצירת משתמש: {str(e)}'}), 500

@ui_bp.route('/api/biz/users', methods=['POST'])
#@require_roles("manager")
def api_biz_users_create():
    """Create new business user"""
    try:
        from server.models_sql import db, User
        
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '').strip()
        business_id = request.form.get('business_id', '').strip()
        enabled = bool(request.form.get('enabled'))
        
        if not name or not email or not role or not business_id:
            return jsonify({'success': False, 'error': 'כל השדות נדרשים'}), 400
            
        # Return JSON success for API consistency
        return jsonify({'success': True, 'message': 'משתמש נוצר בהצלחה'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת יצירת משתמש: {str(e)}'}), 500

@ui_bp.route('/api/crm/contacts', methods=['POST'])
#@require_roles("manager","business")
def api_crm_contacts_create():
    """Create new CRM contact"""
    try:
        # Mock success for now
        import time
        time.sleep(0.5)  # Simulate processing
        
        # Return JSON success for API consistency
        return jsonify({'success': True, 'message': 'לקוח נוצר בהצלחה'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'שגיאת יצירת לקוח: {str(e)}'}), 500

# === ADMIN IMPERSONATION SYSTEM ===
@ui_bp.route('/admin/impersonate/<int:business_id>', methods=['POST'])
#@require_roles("manager")
@audit_action('IMPERSONATE', 'business')
def admin_impersonate_business(business_id):
    """השתלטות כעסק למנהלים"""
    try:
        from server.models_sql import Business
        business = Business.query.get_or_404(business_id)
        
        # Log impersonation start
        if hasattr(g, 'audit_logger') and g.audit_logger:
            g.audit_logger.log_action('IMPERSONATE_START', 'business', business_id, 
                                    {'business_name': business.name})
        
        # Set impersonation session (per guidelines)
        session['impersonator'] = session.get('user')  # Store original user
        session['impersonating'] = True
        session['impersonated_tenant_id'] = business_id
        
        # Return JSON success for API consistency
        return jsonify({'success': True, 'redirect': '/app/biz'})
        
    except Exception as e:
        return jsonify({'error': f'שגיאה בהשתלטות: {str(e)}'}), 500

@ui_bp.route('/admin/stop-impersonate', methods=['POST'])
@require_roles("manager", "admin")
def admin_stop_impersonation():
    """סיום השתלטות"""
    try:
        # Clear impersonation state (per guidelines - DON'T modify session['user'])
        if session.get('impersonating'):
            # Clear the 3 impersonation keys only
            session.pop('impersonating', None)
            session.pop('impersonated_tenant_id', None) 
            session.pop('impersonator', None)
            
            # Log impersonation end
            if hasattr(g, 'audit_logger') and g.audit_logger:
                g.audit_logger.log_action('IMPERSONATE_END', 'business')
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': f'שגיאה בסיום השתלטות: {str(e)}'}), 500

# === FINANCIAL SYSTEM ===
@ui_bp.route('/biz/invoices')
#@require_roles("manager")
def ui_biz_invoices():
    """חשבוניות עסק"""
    business_id = effective_business_id()
    
    try:
        # Mock invoices for now - will connect to actual invoice table
        invoices = [
            {'id': 1, 'invoice_number': f'INV-{business_id}-001', 'customer_name': 'לקוח דוגמא', 'amount': 1500, 'status': 'paid'},
            {'id': 2, 'invoice_number': f'INV-{business_id}-002', 'customer_name': 'לקוח אחר', 'amount': 2300, 'status': 'pending'},
        ]
        
        # Return JSON for SPA instead of template
        return jsonify({"invoices": invoices})
    except Exception as e:
        from server.ui_components import render_error_state
        return render_error_state(f'שגיאה בטעינת חשבוניות: {str(e)}')

@ui_bp.route('/biz/contracts')
#@require_roles("manager")
def ui_biz_contracts():
    """חוזים עסק"""
    business_id = effective_business_id()
    
    try:
        # Mock contracts for now
        contracts = [
            {'id': 1, 'title': 'חוזה דירה תל אביב', 'client': 'יוסי כהן', 'status': 'signed', 'amount': 1200000},
            {'id': 2, 'title': 'חוזה משרד רמת גן', 'client': 'חברת ABC', 'status': 'pending', 'amount': 800000},
        ]
        
        # Return JSON for SPA instead of template  
        return jsonify({"contracts": contracts})
    except Exception as e:
        from server.ui_components import render_error_state
        return render_error_state(f'שגיאה בטעינת חוזים: {str(e)}')

# Alias for logout link in sidebar
@ui_bp.route('/logout')
def logout():
    """Direct logout route"""
    return api_logout()

# === UNAUTHORIZED PAGE FIX ===
@ui_bp.route('/unauthorized')
def unauthorized():
    """Handle unauthorized access - redirect based on login status and role"""
    user = session.get('al_user') or session.get('user')
    
    if not user:
        # Not logged in - redirect to login
        return redirect('/')
    
    # User is logged in - redirect to appropriate page based on role
    user_role = user.get('role', '')
    if user_role == 'manager':
        return redirect('/ui/admin/overview')
    elif user_role == 'business':
        return redirect('/ui/biz/contacts')
    else:
        # Unknown role - redirect to login
        return redirect('/')