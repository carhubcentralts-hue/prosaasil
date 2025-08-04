import os
import logging
from flask import Flask, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Production security settings
if os.environ.get("HTTPS_ONLY", "True").lower() == "true":
    app.config["PREFERRED_URL_SCHEME"] = "https"

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///call_center.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    
    # Register Admin Blueprint FIRST
    try:
        from admin_routes import admin_bp  # Admin routes for business management
        app.register_blueprint(admin_bp)
        logging.info("✅ Admin Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Admin Blueprint registration failed: {e}")

    # Register Business Blueprint
    try:
        from business_routes import business_bp  # Business routes
        app.register_blueprint(business_bp)
        logging.info("✅ Business Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Business Blueprint registration failed: {e}")
        
    # Register Status Blueprint
    try:
        from status_routes import status_bp  # Status routes
        app.register_blueprint(status_bp)
        logging.info("✅ Status Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Status Blueprint registration failed: {e}")

    # Register Login Blueprint
    try:
        from login_routes import login_bp  # Login and authentication routes
        app.register_blueprint(login_bp, url_prefix='/api')
        logging.info("✅ Login Blueprint registered successfully")
    except Exception as e:
        logging.error(f"❌ Login Blueprint registration failed: {e}")

    # Register other Blueprints
    try:
        from crm_bp import crm_bp
        from whatsapp_bp import whatsapp_bp
        from signature_bp import signature_bp
        from invoice_bp import invoice_bp
        from proposal_bp import proposal_bp
        
        app.register_blueprint(crm_bp)
        app.register_blueprint(whatsapp_bp)
        app.register_blueprint(signature_bp)
        app.register_blueprint(invoice_bp)
        app.register_blueprint(proposal_bp)
        
        logging.info("✅ All other Blueprints registered successfully")
        
    except Exception as e:
        logging.warning(f"⚠️ Could not register some Blueprints: {e}")

    # Import systematic route modules (Hebrew CRM System)
    try:
        import routes_twilio      # AI Call handling routes
        import routes_whatsapp    # WhatsApp (Baileys + Twilio) routes  
        import routes_crm         # Advanced CRM routes
        # import routes           # Legacy routes - DEPRECATED
        import api_routes         # New React API routes
        import api_crm_advanced   # Advanced CRM API routes
        import api_whatsapp_advanced # Advanced WhatsApp API routes
        import api_business_info  # Business info API routes
        
        # Register new advanced API blueprints
        from api_routes import api_bp
        app.register_blueprint(api_bp)
        logging.info("✅ API Routes Blueprint registered successfully")
        
        # Register newest advanced blueprints
        try:
            from api_phone_analysis import phone_analysis_bp
            app.register_blueprint(phone_analysis_bp)
            logging.info("✅ Phone Analysis Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Phone Analysis Blueprint not found")
        
        try:
            from api_admin_advanced import admin_advanced_bp
            app.register_blueprint(admin_advanced_bp)
            logging.info("✅ Admin Advanced Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Admin Advanced Blueprint not found")
        
        try:
            from api_business_leads import business_leads_bp
            app.register_blueprint(business_leads_bp)
            logging.info("✅ Business Leads Blueprint registered")
        except ImportError:
            logging.warning("⚠️ Business Leads Blueprint not found")
            
        logging.info("✅ All route modules loaded successfully")
    except Exception as e:
        logging.warning(f"⚠️ Route modules error: {e}")

    db.create_all()
    
    # הפעלת שירותי ניקוי אוטומטי הוסר - משתמש ב-background_cleanup
    
    # הפעלת שירות ניקוי ברקע מתקדם
    try:
        from auto_cleanup_background import background_cleanup
        background_cleanup.start_scheduler()
        logging.info("🧹 Background cleanup scheduler started")
    except Exception as e:
        logging.warning(f"⚠️ Could not start background cleanup: {e}")

# Emergency fix route for debugging stuck states
@app.route('/fix')
def fix_emergency():
    """עמוד תיקון חירום למצבים תקועים"""
    return """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔧 תיקון חירום</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; }
        .card { background: white; margin: 15px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .btn { background: #7c3aed; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; margin: 5px; font-size: 16px; }
        .btn.danger { background: #ef4444; }
        .btn.success { background: #10b981; }
        .log { background: #f8f9fa; padding: 15px; border-radius: 4px; font-family: monospace; margin: 10px 0; }
        .status { padding: 15px; border-radius: 4px; margin: 10px 0; font-weight: bold; }
        .status.good { background: #d1fae5; color: #065f46; }
        .status.bad { background: #fee2e2; color: #991b1b; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 תיקון חירום למערכת</h1>
        <p><strong>המערכת תקועה? השתמש בכלים הבאים:</strong></p>

        <div class="card">
            <h2>🔍 מצב נוכחי</h2>
            <div id="status" class="log">בודק...</div>
            <button class="btn" onclick="checkStatus()">בדוק מצב</button>
        </div>

        <div class="card">
            <h2>🚨 איפוס מהיר</h2>
            <button class="btn danger" onclick="resetToAdmin()">איפוס למנהל</button>
            <button class="btn" onclick="clearAndLogin()">נקה והתחבר</button>
            <div id="reset-result" class="log">לא בוצע</div>
        </div>

        <div class="card">
            <h2>🎯 מעבר ישיר</h2>
            <button class="btn" onclick="goTo('/admin/dashboard')">מנהל</button>
            <button class="btn success" onclick="goTo('/business/dashboard')">עסק</button>
            <button class="btn" onclick="goTo('/login')">התחברות</button>
        </div>

        <div class="card">
            <h2>🧪 בדיקת השתלטות</h2>
            <button class="btn success" onclick="testTakeover(1)">השתלטות על עסק #1</button>
            <button class="btn success" onclick="testTakeover(2)">השתלטות על עסק #2</button>
            <div id="takeover-result" class="log">לא בוצע</div>
        </div>
    </div>

    <script>
        function checkStatus() {
            const url = window.location.pathname;
            const token = localStorage.getItem('auth_token');
            const role = localStorage.getItem('user_role');
            const businessId = localStorage.getItem('business_id');
            const takeover = localStorage.getItem('admin_takeover_mode');
            
            let statusClass = 'good';
            let statusText = '✅ מצב תקין';
            
            if (role === 'business' && url.includes('/admin/')) {
                statusClass = 'bad';
                statusText = '❌ בעיה קריטית: role=business אבל בעמוד admin';
            } else if (takeover === 'true' && !url.includes('/business/')) {
                statusClass = 'bad';
                statusText = '❌ השתלטות פעילה אבל לא בעמוד עסק';
            }
            
            document.getElementById('status').innerHTML = 
                `<div class="status ${statusClass}">${statusText}</div>` +
                `URL: ${url}<br>` +
                `טוכן: ${token ? 'יש' : 'אין'}<br>` +
                `תפקיד: ${role || 'לא מוגדר'}<br>` +
                `עסק: ${businessId || 'לא מוגדר'}<br>` +
                `השתלטות: ${takeover || 'לא פעיל'}`;
        }

        function resetToAdmin() {
            console.log('🔄 Reset to admin');
            localStorage.clear();
            localStorage.setItem('auth_token', 'admin_token_' + Date.now());
            localStorage.setItem('user_role', 'admin');
            localStorage.setItem('user_name', 'מנהל');
            
            document.getElementById('reset-result').innerHTML = '✅ איפוס הושלם - עובר למנהל...';
            setTimeout(() => { window.location.href = '/admin/dashboard'; }, 1500);
        }

        function clearAndLogin() {
            localStorage.clear();
            document.getElementById('reset-result').innerHTML = '✅ נוקה - עובר להתחברות...';
            setTimeout(() => { window.location.href = '/login'; }, 1500);
        }

        function goTo(path) {
            window.location.href = path;
        }

        async function testTakeover(businessId) {
            try {
                document.getElementById('takeover-result').innerHTML = `🧪 בודק השתלטות על עסק #${businessId}...`;
                
                // איפוס למנהל
                localStorage.setItem('auth_token', 'admin_token_' + Date.now());
                localStorage.setItem('user_role', 'admin');
                localStorage.setItem('user_name', 'מנהל');
                localStorage.removeItem('admin_takeover_mode');
                localStorage.removeItem('business_id');
                
                const response = await fetch(`/api/admin/impersonate/${businessId}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer admin_token_' + Date.now(),
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    localStorage.setItem('admin_takeover_mode', 'true');
                    localStorage.setItem('original_admin_token', localStorage.getItem('auth_token'));
                    localStorage.setItem('business_id', businessId.toString());
                    localStorage.setItem('auth_token', data.token);
                    localStorage.setItem('user_role', 'business');
                    localStorage.setItem('user_name', `מנהל שולט ב-${data.business.name}`);
                    
                    document.getElementById('takeover-result').innerHTML = 
                        `✅ השתלטות על עסק #${businessId} הושלמה! עובר לדשבורד...`;
                    
                    setTimeout(() => { window.location.href = '/business/dashboard'; }, 2000);
                } else {
                    throw new Error(data.error || 'השתלטות נכשלה');
                }
            } catch (error) {
                document.getElementById('takeover-result').innerHTML = `❌ שגיאה: ${error.message}`;
            }
        }

        // הפעלה ראשונית
        checkStatus();
        setInterval(checkStatus, 5000);
    </script>
</body>
</html>
"""

# React Frontend Routes - Flask מגיש את React
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve React app with proper SPA routing support"""
    build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../client/dist"))
    requested_path = os.path.join(build_dir, path)

    if path != "" and os.path.exists(requested_path):
        return send_from_directory(build_dir, path)
    else:
        return send_from_directory(build_dir, "index.html")

# Media stream routes integrated into routes.py


