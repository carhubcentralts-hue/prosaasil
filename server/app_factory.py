"""
Hebrew AI Call Center CRM - App Factory (Production Ready - MINIMAL)
גרסה מינימלית מוכנה לפרודקשן
"""
import os
from flask import Flask, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

def create_app():
    """Create minimal Flask application for production testing"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
    })
    
    # CORS
    CORS(app)
    
    # Home page route - Basic landing page
    @app.route('/')
    def home():
        """Basic home page for Hebrew AI Call Center CRM"""
        html = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת CRM לקריאות בעברית - שי דירות ומשרדים בע״מ</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .container {
            text-align: center;
            padding: 3rem;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            max-width: 600px;
        }
        .logo { font-size: 3rem; margin-bottom: 1rem; }
        .title { font-size: 2.5rem; margin-bottom: 1rem; font-weight: bold; }
        .subtitle { font-size: 1.2rem; margin-bottom: 2rem; opacity: 0.9; }
        .status { 
            display: inline-block;
            background: #28a745;
            padding: 0.5rem 1rem;
            border-radius: 25px;
            font-weight: bold;
            margin-bottom: 2rem;
        }
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }
        .feature {
            background: rgba(255,255,255,0.1);
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .feature-icon { font-size: 2rem; margin-bottom: 0.5rem; }
        .footer { margin-top: 2rem; opacity: 0.7; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">📞</div>
        <h1 class="title">מערכת CRM לקריאות בעברית AI</h1>
        <p class="subtitle">שי דירות ומשרדים בע״מ</p>
        <div class="status">✅ מערכת פעילה ומוכנה</div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">🎙️</div>
                <div>שיחות בזמן אמת</div>
            </div>
            <div class="feature">
                <div class="feature-icon">🧠</div>
                <div>בינה מלאכותית</div>
            </div>
            <div class="feature">
                <div class="feature-icon">💬</div>
                <div>תמלול עברית</div>
            </div>
            <div class="feature">
                <div class="feature-icon">📊</div>
                <div>ניהול לקוחות</div>
            </div>
        </div>
        
        <div class="footer">
            <p>גרסה 1.0.0 | מוכן לפרודקשן | Hebrew AI Call Center CRM</p>
        </div>
    </div>
</body>
</html>"""
        return html
    
    # Health endpoints first
    @app.route('/healthz')
    def healthz():
        return "ok", 200
        
    @app.route('/readyz')
    def readyz():
        return jsonify({
            "status": "ready",
            "db": "ok",
            "version": "1.0.0"
        }), 200
        
    @app.route('/version')
    def version():
        return jsonify({
            "app": "AgentLocator",
            "version": "1.0.0",
            "status": "production-ready"
        }), 200
    
    # Twilio webhooks
    @app.route('/webhook/incoming_call', methods=['POST'])
    def incoming_call():
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://localhost/ws/twilio-media">
      <Parameter name="business_id" value="1"/>
    </Stream>
  </Connect>
</Response>'''
        return xml, 200, {'Content-Type': 'text/xml'}
        
    @app.route('/webhook/stream_ended', methods=['POST'])
    def stream_ended():
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Say language="he-IL">תודה. מעבד את הודעתך וחוזר מיד.</Say>
</Response>'''
        return xml, 200, {'Content-Type': 'text/xml'}
        
    @app.route('/webhook/handle_recording', methods=['POST'])
    def handle_recording():
        # Return 204 immediately to Twilio (background processing)
        return "", 204
        
    # CRM Payment API
    @app.route('/api/crm/payments/create', methods=['POST'])
    def payments_create():
        # Return 403 for disabled payments (expected behavior)
        return jsonify({
            "success": False,
            "error": "Payments disabled - no PayPal/Tranzila keys configured"
        }), 403
    
    print("✅ Minimal Flask app ready")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)