#!/usr/bin/env python3
"""
Professional Flask App Factory - Hebrew AI Call Center CRM
מפעל אפליקציות Flask מקצועי - מערכת ניהול שיחות עברית AI
"""

from flask import Flask, Response, request, jsonify, send_file
from flask_cors import CORS
import os
from server.logging_setup import init_logging, install_request_hooks, install_sqlalchemy_slow_query_logging
from server.error_handlers import register_error_handlers

# Database imports
from server.db import db
from server.models_sql import *  # noqa

def register_blueprints(app):
    """Register all application blueprints"""
    # Health and core routes
    try:
        from server.health_routes import health_bp
        app.register_blueprint(health_bp)
        print("✅ Health routes registered successfully")
    except Exception as e:
        print(f"❌ Health routes registration failed: {e}")
    
    # Debug routes (development only)
    try:
        from server.debug_routes import debug_bp
        app.register_blueprint(debug_bp)
        print("✅ Debug routes registered successfully")
    except Exception as e:
        print(f"❌ Debug routes registration failed: {e}")
    
    # Authentication
    try:
        from server.auth_routes import auth_bp
        app.register_blueprint(auth_bp)
        print("✅ Auth routes registered successfully")
    except Exception as e:
        print(f"❌ Auth routes registration failed: {e}")
    
    # Password management (auth required)
    try:
        from server.password_routes import password_bp
        app.register_blueprint(password_bp)
        print("✅ Password routes registered successfully")
    except Exception as e:
        print(f"❌ Password routes registration failed: {e}")
    
    # Twilio webhooks (no auth required)
    try:
        print("🔧 STARTING Twilio webhooks registration...")
        from server.routes_twilio import twilio_bp
        print(f"✅ twilio_bp imported: {twilio_bp}")
        app.register_blueprint(twilio_bp)
        print("✅ Twilio webhooks registered successfully")
    except Exception as e:
        print(f"❌ Twilio webhooks registration failed: {e}")
    
    # WhatsApp Twilio webhooks (no auth required)
    try:
        from server.routes_whatsapp_twilio import whatsapp_twilio_bp
        app.register_blueprint(whatsapp_twilio_bp)
        print("✅ WhatsApp Twilio webhooks registered successfully")
        
        # DEBUG: Show registered routes
        print("🔍 DEBUG: Current Flask routes:")
        for rule in app.url_map.iter_rules():
            if 'webhook' in rule.rule or 'handle_recording' in rule.rule:
                print(f"   {rule.rule} -> {rule.methods} -> {rule.endpoint}")
        
    except Exception as e:
        print(f"❌ Twilio webhooks registration failed: {e}")
        print(f"🔍 Error details: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # CRM and Timeline (auth required)
    # Timeline API  
    try:
        from server.api_timeline import timeline_bp
        app.register_blueprint(timeline_bp)
        print("✅ Timeline API registered successfully")
    except Exception as e:
        print(f"❌ Timeline API registration failed: {e}")
    
    # Business management (auth required)
    try:
        from server.api_business import biz_bp
        app.register_blueprint(biz_bp)
        print("✅ Business API registered successfully")
    except Exception as e:
        print(f"❌ Business API registration failed: {e}")
    
    # CRM Basic API for testing (public for development)
    try:
        from server.api_crm_basic import crm_basic_bp
        app.register_blueprint(crm_basic_bp)
        print("✅ CRM Basic API registered successfully")
    except Exception as e:
        print(f"❌ CRM Basic API registration failed: {e}")
    
    # CRM Unified API (לפי המפרט המקצועי)
    try:
        from server.api_crm_unified import crm_unified_bp
        app.register_blueprint(crm_unified_bp)
        print("✅ CRM Unified API registered successfully")
    except Exception as e:
        print(f"❌ CRM Unified API registration failed: {e}")
    
    # WhatsApp integration (auth required)
    try:
        from server.whatsapp_api import whatsapp_api_bp
        app.register_blueprint(whatsapp_api_bp)
        print("✅ WhatsApp API registered successfully")
    except Exception as e:
        print(f"❌ WhatsApp API registration failed: {e}")
        # Create minimal WhatsApp status route as last resort
        @app.route('/api/whatsapp/status', methods=['GET'])
        def whatsapp_status_fallback():
            return jsonify({'success': True, 'connected': False, 'status': 'disconnected'})

def create_app():
    """Production-ready app factory with comprehensive setup"""
    """יצירת אפליקציית Flask עם הגדרות מקצועיות"""
    app = Flask(__name__)
    
    # Setup critical environment variables for voice system - FAIL FAST if missing
    PH = os.getenv("PUBLIC_HOST", "").rstrip("/")
    if not PH:
        raise RuntimeError("PUBLIC_HOST not set – configure in Replit Secrets (Workspace + Deploy)")
    app.config["PUBLIC_HOST"] = PH
    print(f"✅ PUBLIC_HOST set to: {PH}")
    
    # Load configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    
    # Security improvements
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    
    # CORS - only your domain
    cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ['http://localhost:3000', 'http://localhost:5000', 'https://*.replit.app']
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # Initialize professional logging first
    init_logging(app)
    install_request_hooks(app)
    
    # Initialize rate limiting for security (after blueprints)
    # Note: Moved to after blueprint registration for proper function access
    
    # Health endpoint
    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "Hebrew AI Call Center CRM"}
    
    # Add revision header to all responses
    @app.after_request
    def add_revision_header(response):
        response.headers["X-Revision"] = os.getenv("APP_REV", "dev")
        return response
    
    # Initialize database if available
    try:
        # Try new SQLAlchemy models first
        if db is not None:
            app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///./agentlocator.db")
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            
            db.init_app(app)
            with app.app_context():
                try:
                    db.create_all()
                    print("✅ Production database initialized with SQLAlchemy models")
                except Exception as e:
                    print(f"⚠️ Database initialization warning: {e}")
                try:
                    install_sqlalchemy_slow_query_logging(app, db)
                    print("✅ DB slow query logging installed")
                except Exception as e:
                    app.logger.warning("DB slow query logging not installed: %s", e)
        else:
            print("ℹ️ Database object is None")
    except ImportError as e:
        print(f"ℹ️ No database models found: {e}")
        
        # Fallback to legacy models
        try:
            from server.models import db as legacy_db
            if legacy_db is not None:
                legacy_db.init_app(app)
                print("✅ Legacy database models loaded")
        except ImportError:
            print("ℹ️ No legacy database models found")
    
    # Register all blueprints
    register_blueprints(app)
    
    # Register error handlers last
    register_error_handlers(app)
    print("✅ Error handlers registered")
    
    # Initialize rate limiting after blueprints are registered
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"]
        )
        print("✅ Rate limiting initialized")
    except ImportError:
        print("❌ Rate limiting not available")
    
    # Health endpoint already registered above as /api/health
    
    # Register additional core routes
    register_core_routes(app)
    register_static_routes(app)
    
    # DISABLE OLD WEBHOOK ROUTES - they conflict with new ones!
    # register_webhook_routes(app)  # COMMENTED OUT - using new twilio_bp instead
    
    return app

def register_core_routes(app):
    """רישום נתיבים עיקריים"""
    
    @app.route('/')
    def serve_frontend():
        """הגשת הפרונטאנד המקצועי"""
        import os
        client_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client', 'dist', 'index.html')
        print(f"🔍 Looking for client at: {client_dist}")
        try:
            if os.path.exists(client_dist):
                print("✅ Client dist found, serving React app")
                with open(client_dist, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Fix asset paths for production
                    content = content.replace('"/assets/', '"/static/assets/')
                    content = content.replace('"/vite.svg', '"/static/vite.svg')
                    return content
            else:
                print(f"❌ Client dist not found at {client_dist}")
        except Exception as e:
            print(f"Error serving frontend: {e}")
        
        # Professional fallback login page if client dist not found
        return """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת CRM</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', 'Assistant', sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
            color: #334155;
        }
        
        .login-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 3rem;
            width: 100%;
            max-width: 440px;
            box-shadow: 
                0 20px 25px -5px rgba(0, 0, 0, 0.1),
                0 10px 10px -5px rgba(0, 0, 0, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .brand-header {
            text-align: center;
            margin-bottom: 2.5rem;
        }
        
        .brand-logo {
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1rem;
            color: white;
            font-size: 24px;
            font-weight: 600;
        }
        
        .brand-title {
            font-size: 28px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        
        .brand-subtitle {
            font-size: 16px;
            color: #64748b;
            font-weight: 400;
        }
        .header {
            text-align: center;
            margin-bottom: 3rem;
        }
        .logo {
            font-size: 3rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #1e3a8a, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        h1 {
            font-size: 1.75rem;
            font-weight: 700;
            color: #1e293b;
            margin: 0 0 0.5rem 0;
        }
        .subtitle {
            color: #64748b;
            font-size: 1rem;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            font-size: 0.95rem;
            font-weight: 600;
            color: #374151;
            margin-bottom: 0.75rem;
        }
        input {
            width: 100%;
            padding: 1rem;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 1rem;
            background: #f9fafb;
            transition: all 0.2s ease;
        }
        input:focus {
            outline: none;
            border-color: #3b82f6;
            background: white;
        }
        .btn {
            width: 100%;
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 1rem;
            border: none;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.39);
            margin-bottom: 2rem;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px 0 rgba(59, 130, 246, 0.5);
        }
        .credentials {
            padding: 1.5rem;
            background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
            border: 1px solid #7dd3fc;
            border-radius: 16px;
            font-size: 0.85rem;
            color: #0c4a6e;
        }
        .credentials h3 {
            margin-bottom: 1rem;
            font-weight: 600;
        }
        .credentials div {
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }
        .error {
            background: linear-gradient(135deg, #fef2f2, #fee2e2);
            border: 1px solid #fca5a5;
            color: #dc2626;
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            text-align: center;
            font-weight: 500;
        }
        #loading {
            background: #9ca3af;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🏢</div>
            <h1>מערכת ניהול שיחות AI</h1>
            <p class="subtitle">מערכת CRM מתקדמת</p>
        </div>

        <form id="loginForm">
            <div class="form-group">
                <label>דואר אלקטרוני</label>
                <input type="email" id="email" placeholder="הזן דואר אלקטרוני" required>
            </div>

            <div class="form-group">
                <label>סיסמה</label>
                <input type="password" id="password" placeholder="הזן סיסמה" required>
            </div>

            <div id="errorDiv" class="error" style="display: none;"></div>

            <button type="submit" class="btn" id="loginBtn">כניסה למערכת</button>
        </form>

        <div class="credentials">
            <h3>🔐 פרטי התחברות למערכת:</h3>
            <div><strong>מנהל:</strong> admin@shai.com / admin123</div>
            <div><strong>מנהל ראשי:</strong> admin@shai-realestate.co.il / admin123456</div>
            <div><strong>משתמש עסק:</strong> shai@shai-realestate.co.il / shai123</div>
        </div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('errorDiv');
            const loginBtn = document.getElementById('loginBtn');
            
            // Show loading state
            loginBtn.textContent = 'מתחבר...';
            loginBtn.id = 'loading';
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email, password })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Success - redirect or show dashboard
                    document.body.innerHTML = `
                        <div class="container">
                            <div class="header">
                                <div class="logo">✅</div>
                                <h1>התחברת בהצלחה!</h1>
                                <p class="subtitle">משתמש: ${data.user.firstName || data.user.name} (${data.user.role})</p>
                            </div>
                            <div class="credentials">
                                <h3>🎯 מערכת פעילה ומוכנה:</h3>
                                <div>✅ מערכת שיחות AI פעילה</div>
                                <div>✅ Twilio webhooks מחוברים</div>
                                <div>✅ לוגים מקצועיים פועלים</div>
                                <div>✅ מוכן לקבלת שיחות!</div>
                            </div>
                        </div>
                    `;
                } else {
                    errorDiv.textContent = data.error || 'שגיאה בהתחברות';
                    errorDiv.style.display = 'block';
                }
            } catch (err) {
                errorDiv.textContent = 'שגיאת תקשורת. נסה שוב.';
                errorDiv.style.display = 'block';
            }
            
            // Reset button
            loginBtn.textContent = 'כניסה למערכת';
            loginBtn.id = 'loginBtn';
        });
    </script>
</body>
</html>"""

def register_webhook_routes(app):
    """רישום webhooks מקצועיים עם זרימת שיחה חכמה - LEGACY BACKUP"""
    
    PUBLIC_HOST = "https://ai-crmd.replit.app"
    
    @app.route('/webhook/incoming_call_backup', methods=['POST'])
    def professional_incoming_call_backup():
        """Professional incoming call - immediate professional response"""
        call_sid = request.values.get('CallSid', 'unknown')
        from_number = request.values.get('From', '')
        
        print(f"📞 Professional call started: {call_sid} from {from_number}")
        
        # Direct professional greeting + immediate recording
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    שלום, הגעתם למערכת CRM המתקדמת. אני העוזרת הדיגיטלית.
    אשמח לעזור לכם עם כל שאלה בנושא נדלן. דברו אחרי הצפצוף.
  </Say>
  <Record action="/webhook/conversation_turn?turn=1"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
        
        response = Response(xml, mimetype="text/xml")
        response.headers['Content-Type'] = 'text/xml; charset=utf-8'
        return response
    
    @app.route('/webhook/conversation_turn_backup', methods=['POST'])
    def professional_conversation_turn_backup():
        """Professional conversation handling with AI responses"""
        try:
            call_sid = request.values.get('CallSid', 'unknown')
            recording_url = request.values.get('RecordingUrl', '')
            turn_str = request.values.get('turn', '1')
            
            # Parse turn number
            try:
                turn_num = int(turn_str)
            except:
                turn_num = 1
            
            next_turn = turn_num + 1
            
            print(f"🎤 Processing turn {turn_num} for call {call_sid}")
            print(f"📥 Recording URL: {recording_url}")
            
            # Generate AI response and continue conversation
            if recording_url and recording_url != '':
                # Process recording and get AI response
                ai_response = process_real_conversation_sync(call_sid, recording_url, turn_num)
                
                if ai_response and len(ai_response.strip()) > 5:
                    # AI response + continue conversation
                    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">{ai_response}</Say>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
                else:
                    # No valid transcription - ask again
                    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    לא שמעתי אתכם בבירור. בבקשה דברו שוב אחרי הצפצוף.
  </Say>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
            else:
                # No recording - ask to speak
                xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    לא שמעתי אתכם. בבקשה דברו אחרי הצפצוף.
  </Say>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
            
            response = Response(xml, mimetype="text/xml")
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response
            
        except Exception as e:
            print(f"❌ Conversation error: {e}")
            # Professional error handling
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    סליחה, יש לי בעיה טכנית. אנא התקשרו שוב מאוחר יותר.
  </Say>
  <Hangup/>
</Response>"""
            return Response(xml, mimetype="text/xml")
    
    # REMOVED OLD @app.route('/webhook/call_status') - using twilio_bp instead!

def process_real_conversation_sync(call_sid: str, recording_url: str, turn_num: int) -> str:
    """Process real conversation synchronously and return AI response"""
    try:
        print(f"🎙️ Processing call {call_sid}, turn {turn_num}")
        
        # Download and transcribe
        import requests
        import tempfile
        import openai
        import os
        
        # Download recording
        response = requests.get(recording_url)
        if response.status_code != 200:
            print(f"❌ Failed to download recording: {response.status_code}")
            return ""
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        print(f"✅ Downloaded {len(response.content)} bytes")
        
        # Transcribe with Whisper
        client = openai.OpenAI()
        
        with open(temp_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he",
                response_format="text"
            )
        
        user_input = str(transcript).strip()
        print(f"🎤 Transcription: '{user_input}'")
        
        # Generate AI response
        ai_response = ""
        if len(user_input) > 3:  # Valid input
            ai_response = generate_professional_response(user_input, turn_num)
            print(f"🤖 AI Response: '{ai_response}'")
            
            # Store in database (if available)
            try:
                store_conversation_turn(call_sid, turn_num, user_input, ai_response)
            except Exception as e:
                print(f"⚠️ Could not store in DB: {e}")
        
        # Cleanup
        os.unlink(temp_path)
        return ai_response
        
    except Exception as e:
        print(f"❌ Real conversation processing failed: {e}")
        return ""

def generate_professional_response(user_input: str, turn_num: int) -> str:
    """Generate professional AI response for real estate"""
    try:
        import openai
        
        client = openai.OpenAI()
        
        system_prompt = """אתה סוכן נדל"ן מקצועי וחכם של מערכת CRM מתקדמת.
אתה מומחה בשוק הנדל"ן הישראלי ונותן שירות מעולה ללקוחות.

הנחיות חשובות:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 40 מילים)
3. שאל שאלה רלוונטית אחת
4. אל תמציא מחירים או נכסים ספציפיים
5. הפנה לפגישה או לקבלת פרטים נוספים
6. התנהג בצורה מקצועית וחמה

אם הלקוח רוצה לסיים ("תודה", "ביי", "זה הכל") - סיים בנימוס."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        ai_content = response.choices[0].message.content
        return ai_content.strip() if ai_content else "אשמח לעזור לכם. אפשר לחזור על השאלה?"
        
    except Exception as e:
        print(f"❌ AI response generation failed: {e}")
        return "אשמח לעזור לכם. אפשר לחזור על השאלה?"

def store_conversation_turn(call_sid: str, turn_num: int, user_input: str, ai_response: str):
    """Store conversation turn in database (if available)"""
    try:
        # This would use the database if models are available
        print(f"💾 Would store: {call_sid} turn {turn_num}")
        print(f"    User: {user_input}")
        print(f"    AI: {ai_response}")
    except Exception as e:
        print(f"⚠️ Storage not available: {e}")

def register_static_routes(app):
    """רישום נתיבים לקבצים סטטיים - קבצי קול עבריים ו-client assets"""
    from flask import send_from_directory
    
    # Serve client assets from React build
    @app.route('/static/assets/<path:filename>')
    def serve_client_assets(filename):
        """Serve client assets from client/dist/assets"""
        import os
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client', 'dist', 'assets')
        return send_from_directory(assets_dir, filename)
    
    @app.route('/static/voice_responses/<filename>')
    def serve_voice_files(filename):
        """הגשת קבצי קול עבריים"""
        try:
            import os
            from pathlib import Path
            # Get absolute path 
            base_path = Path(__file__).parent
            filepath = base_path / 'static' / 'voice_responses' / filename
            if filepath.exists():
                return send_file(str(filepath), mimetype='audio/mpeg')
            else:
                return f"File not found: {filepath}", 404
        except Exception as e:
            return f"Error serving {filename}: {e}", 500

if __name__ == '__main__':
    app = create_app()
    print("🎯 Starting Professional Hebrew AI Call Center CRM")
    print("🔐 מנהל: admin / admin123")
    print("🏢 שי: shai / shai123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)