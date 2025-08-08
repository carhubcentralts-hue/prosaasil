"""
נתיבי תיקון למצבים תקועים
"""
from flask import Blueprint, render_template_string, request, jsonify, make_response

fix_bp = Blueprint('fix', __name__)

@fix_bp.route('/fix')
def fix_status():
    """עמוד תיקון מצב המערכת"""
    html = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔧 תיקון מצב המערכת</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { 
            background: white; 
            margin: 15px 0; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .btn { 
            background: #7c3aed; 
            color: white; 
            border: none; 
            padding: 12px 24px; 
            border-radius: 6px; 
            cursor: pointer; 
            margin: 5px;
            font-size: 16px;
        }
        .btn.danger { background: #ef4444; }
        .btn.success { background: #10b981; }
        .btn.warning { background: #f59e0b; }
        .log { 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 4px; 
            font-family: monospace; 
            margin: 10px 0;
            border-left: 4px solid #6b7280;
        }
        .status { padding: 15px; border-radius: 4px; margin: 10px 0; font-weight: bold; }
        .status.good { background: #d1fae5; color: #065f46; }
        .status.bad { background: #fee2e2; color: #991b1b; }
        .status.warning { background: #fef3c7; color: #92400e; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 תיקון מצב המערכת</h1>
        <p>כלי לפתרון בעיות השתלטות וניווט</p>

        <div class="card">
            <h2>🔍 מצב נוכחי</h2>
            <div id="status" class="log">בודק...</div>
            <button class="btn" onclick="checkStatus()">בדוק מצב</button>
        </div>

        <div class="card">
            <h2>🚨 פעולות חירום</h2>
            <button class="btn danger" onclick="resetToAdmin()">איפוס מלא למנהל</button>
            <button class="btn warning" onclick="clearAll()">נקה הכל</button>
            <div id="emergency-result" class="log">לא בוצע</div>
        </div>

        <div class="card">
            <h2>🎯 ניווט ישיר</h2>
            <button class="btn" onclick="goToAdmin()">עבור למנהל</button>
            <button class="btn success" onclick="goToBusiness()">עבור לעסק</button>
            <button class="btn" onclick="goToLogin()">עבור להתחברות</button>
            <div id="navigation-result" class="log">לא בוצע</div>
        </div>

        <div class="card">
            <h2>🧪 בדיקת השתלטות</h2>
            <button class="btn success" onclick="testTakeover(1)">השתלט על עסק #1</button>
            <button class="btn success" onclick="testTakeover(2)">השתלט על עסק #2</button>
            <div id="takeover-result" class="log">לא בוצע</div>
        </div>

        <div class="card">
            <h2>📊 פרטי localStorage</h2>
            <div id="localStorage-details" class="log">לא נטען</div>
            <button class="btn" onclick="showLocalStorage()">הצג פרטים</button>
        </div>
    </div>

    <script>
        function checkStatus() {
            const currentUrl = window.location.pathname;
            const token = localStorage.getItem('auth_token');
            const role = localStorage.getItem('user_role');
            const businessId = localStorage.getItem('business_id');
            const takeover = localStorage.getItem('admin_takeover_mode');
            
            let statusClass = 'good';
            let statusText = '✅ מצב תקין';
            
            // זיהוי בעיות
            if (role === 'business' && currentUrl.includes('/admin/')) {
                statusClass = 'bad';
                statusText = '❌ בעיה קריטית: role=business אבל בעמוד admin';
            } else if (role === 'admin' && currentUrl.includes('/business/')) {
                statusClass = 'bad';
                statusText = '❌ בעיה: role=admin אבל בעמוד business';
            } else if (takeover === 'true' && !currentUrl.includes('/business/')) {
                statusClass = 'warning';
                statusText = '⚠️ השתלטות פעילה אבל לא בעמוד עסק';
            }
            
            document.getElementById('status').innerHTML = 
                `<div class="status ${statusClass}">${statusText}</div>` +
                `URL: ${currentUrl}<br>` +
                `טוכן: ${token ? 'יש' : 'אין'}<br>` +
                `תפקיד: ${role || 'לא מוגדר'}<br>` +
                `עסק: ${businessId || 'לא מוגדר'}<br>` +
                `השתלטות: ${takeover || 'לא פעיל'}`;
        }

        function resetToAdmin() {
            ;
            
            // ניקוי מלא
            localStorage.clear();
            
            // הגדרת מנהל
            localStorage.setItem('auth_token', 'admin_token_' + Date.now());
            localStorage.setItem('user_role', 'admin');
            localStorage.setItem('user_name', 'מנהל');
            
            document.getElementById('emergency-result').innerHTML = 
                '✅ איפוס הושלם. עובר למנהל...';
            
            setTimeout(() => {
                window.location.href = '/admin/dashboard';
            }, 1500);
        }

        function clearAll() {
            localStorage.clear();
            document.getElementById('emergency-result').innerHTML = 
                '✅ כל הנתונים נוקו. עובר להתחברות...';
            
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        }

        function goToAdmin() {
            document.getElementById('navigation-result').innerHTML = '🔄 עובר למנהל...';
            window.location.href = '/admin/dashboard';
        }

        function goToBusiness() {
            document.getElementById('navigation-result').innerHTML = '🔄 עובר לעסק...';
            window.location.href = '/business/dashboard';
        }

        function goToLogin() {
            document.getElementById('navigation-result').innerHTML = '🔄 עובר להתחברות...';
            window.location.href = '/login';
        }

        async function testTakeover(businessId) {
            try {
                document.getElementById('takeover-result').innerHTML = 
                    `🧪 בודק השתלטות על עסק #${businessId}...`;
                
                // קודם איפוס למנהל
                localStorage.setItem('auth_token', 'admin_token_' + Date.now());
                localStorage.setItem('user_role', 'admin');
                localStorage.setItem('user_name', 'מנהל');
                localStorage.removeItem('admin_takeover_mode');
                localStorage.removeItem('business_id');
                
                // השתלטות
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
                        `✅ השתלטות על עסק #${businessId} הושלמה!<br>` +
                        `עסק: ${data.business.name}<br>` +
                        `עובר לדשבורד העסק...`;
                    
                    setTimeout(() => {
                        window.location.href = '/business/dashboard';
                    }, 2000);
                } else {
                    throw new Error(data.error || 'השתלטות נכשלה');
                }
            } catch (error) {
                document.getElementById('takeover-result').innerHTML = 
                    `❌ שגיאה: ${error.message}`;
            }
        }

        function showLocalStorage() {
            const storage = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                storage[key] = localStorage.getItem(key);
            }
            
            document.getElementById('localStorage-details').innerHTML = 
                '<strong>localStorage content:</strong><br>' + 
                JSON.stringify(storage, null, 2).replace(/\\n/g, '<br>').replace(/ /g, '&nbsp;');
        }

        // בדיקה ראשונית
        checkStatus();
        showLocalStorage();
        
        // רענון אוטומטי כל 5 שניות
        setInterval(() => {
            checkStatus();
        }, 5000);
    </script>
</body>
</html>
    """
    return html

@fix_bp.route('/api/reset-to-admin', methods=['POST'])
def reset_to_admin():
    """API לאיפוס למצב מנהל"""
    response = make_response(jsonify({
        'success': True,
        'message': 'Reset to admin mode',
        'redirect': '/admin/dashboard'
    }))
    
    # Clear cookies if any
    response.set_cookie('auth_token', '', expires=0)
    response.set_cookie('user_role', '', expires=0)
    
    return response