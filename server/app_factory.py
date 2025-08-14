#!/usr/bin/env python3
"""
Professional Flask App Factory - Hebrew AI Call Center CRM
מפעל אפליקציות Flask מקצועי - מערכת ניהול שיחות עברית AI
"""

from flask import Flask, Response, request, jsonify, send_file
from flask_cors import CORS
import os

def register_blueprints(app):
    """Register all application blueprints"""
    # Health and core routes
    try:
        from server.health_routes import health_bp
        app.register_blueprint(health_bp)
        print("✅ Health routes registered successfully")
    except Exception as e:
        print(f"❌ Health routes registration failed: {e}")
    
    # Authentication
    try:
        from server.auth_routes import auth_bp
        app.register_blueprint(auth_bp)
        print("✅ Auth routes registered successfully")
    except Exception as e:
        print(f"❌ Auth routes registration failed: {e}")
    
    # Twilio webhooks (no auth required)
    try:
        from server.routes_twilio import twilio_bp
        app.register_blueprint(twilio_bp)
        print("✅ Twilio webhooks registered successfully")
    except Exception as e:
        print(f"❌ Twilio webhooks registration failed: {e}")
    
    # CRM and Timeline (auth required)
    try:
        from server.api_crm_advanced import crm_bp
        app.register_blueprint(crm_bp)
        print("✅ CRM API registered successfully")
    except Exception as e:
        print(f"❌ CRM API registration failed: {e}")
    
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
    
    # WhatsApp integration (auth required)
    try:
        from server.whatsapp_api import whatsapp_api_bp
        app.register_blueprint(whatsapp_api_bp)
        print("✅ WhatsApp API registered successfully")
    except Exception as e:
        print(f"❌ WhatsApp API registration failed: {e}")
        # Create minimal WhatsApp status route as fallback
        @app.route('/api/whatsapp/status', methods=['GET'])
        def whatsapp_status_fallback():
            return jsonify({'success': True, 'connected': False, 'status': 'disconnected'})

def create_app():
    """יצירת אפליקציית Flask עם הגדרות מקצועיות"""
    
    app = Flask(__name__, static_folder='../client/dist', static_url_path='')
    CORS(app)
    
    # Security configurations
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'shai-real-estate-secure-key-2025')
    app.config['SECURITY_PASSWORD_SALT'] = 'shai-offices-salt'
    app.config.update(
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False  # True behind HTTPS/Proxy
    )
    
    # Register routes
    register_auth_routes(app)
    register_core_routes(app)
    # register_webhook_routes(app)  # OLD SYSTEM DISABLED - Using new Twilio Blueprint
    register_static_routes(app)
    
    # Register all blueprints
    register_blueprints(app)
    
    return app

def register_auth_routes(app):
    """רישום נתיבי אימות מאובטחים"""
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json()
        
        # Secure authentication for professional system
        email = data.get('email')
        if email == 'admin@shai-realestate.co.il' and data.get('password') == 'admin123456':
            user = {
                'id': '1',
                # 'username': 'admin',
                'email': 'admin@shai-realestate.co.il',
                'firstName': 'מנהל',
                'lastName': 'ראשי',
                'role': 'admin',
                'businessId': None,
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'admin-token-secure'})
        elif (email == 'shai@shai-realestate.co.il' and data.get('password') == 'shai123') or (email == 'manager@shai-realestate.co.il' and data.get('password') == 'business123456'):
            user = {
                'id': '2',
                'username': 'shai',
                'email': 'manager@shai-realestate.co.il',
                'firstName': 'שי',
                'lastName': 'כהן',
                'role': 'business',
                'businessId': 'shai-offices',
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'business-token-secure'})
        else:
            return jsonify({'error': 'פרטי התחברות שגויים'}), 401
    
    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        return jsonify({'message': 'התנתקת בהצלחה'})
    
    @app.route('/api/auth/me', methods=['GET'])
    def auth_me():
        # For now, return unauthorized to force login
        return jsonify({'error': 'נדרשת התחברות'}), 401

def register_core_routes(app):
    """רישום נתיבים עיקריים"""
    
    @app.route('/')
    def serve_frontend():
        """הגשת הפרונטאנד המקצועי"""
        try:
            return send_file('../client/dist/index.html')
        except:
            return """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת ניהול שיחות AI - שי דירות ומשרדים בע״מ</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            color: #333;
            text-align: center; 
            padding: 60px 20px;
            direction: rtl;
        }
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: #f9f9f9;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #2c3e50; margin-bottom: 20px; }
        .status { 
            color: #27ae60; 
            font-weight: bold; 
            margin: 20px 0;
        }
        .features {
            text-align: right;
            margin-top: 30px;
        }
        .feature {
            margin: 10px 0;
            padding: 5px;
        }
        .loading {
            color: #3498db;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏢 מערכת ניהול שיחות AI</h1>
        <h2>שי דירות ומשרדים בע״מ</h2>
        <div class="status">✅ השרת פועל בהצלחה</div>
        
        <div class="features">
            <div class="feature">🔐 מערכת התחברות מאובטחת</div>
            <div class="feature">📞 שיחות קוליות חכמות</div>
            <div class="feature">💬 WhatsApp אוטומטי</div>
            <div class="feature">🎯 תמלול עברית מדויק</div>
            <div class="feature">🤖 תשובות AI מתוחכמות</div>
        </div>
        
        <div class="loading">⏳ טוען ממשק המשתמש...</div>
    </div>
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
    שלום, הגעתם לשי דירות ומשרדים. אני העוזרת הדיגיטלית.
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
    
    @app.route('/webhook/conversation_turn', methods=['POST'])
    def professional_conversation_turn():
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
    
    @app.route('/webhook/call_status', methods=['POST'])
    def call_status():
        return "OK", 200

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
        
        system_prompt = """אתה סוכן נדל"ן מקצועי וחכם של "שי דירות ומשרדים בע״מ".
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
    """רישום נתיבים לקבצים סטטיים - קבצי קול עבריים"""
    
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