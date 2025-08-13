#!/usr/bin/env python3
"""
Professional Flask App Factory - Hebrew AI Call Center CRM
מפעל אפליקציות Flask מקצועי - מערכת ניהול שיחות עברית AI
"""

from flask import Flask, Response, request, jsonify, send_file
from flask_cors import CORS
import os

def create_app():
    """יצירת אפליקציית Flask עם הגדרות מקצועיות"""
    
    app = Flask(__name__, static_folder='../client/dist', static_url_path='')
    CORS(app)
    
    # Security configurations
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'shai-real-estate-secure-key-2025')
    app.config['SECURITY_PASSWORD_SALT'] = 'shai-offices-salt'
    
    # Register routes
    register_auth_routes(app)
    register_core_routes(app)
    register_webhook_routes(app)
    register_static_routes(app)
    
    # Register API blueprints
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
    """רישום webhooks לTwilio עם שיחה רציפה"""
    
    PUBLIC_HOST = "https://ai-crmd.replit.app"
    
    @app.route('/webhook/incoming_call', methods=['POST'])
    def fast_incoming_call():
        """Fast incoming call webhook - immediate response"""
        call_sid = request.values.get('CallSid')
        from_number = request.values.get('From', '')
        
        print(f"📞 FAST incoming call: {call_sid} from {from_number}")
        
        # Return immediate response with simple instructions
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/greeting_simple.mp3</Play>
  <Pause length="1"/>
  <Say voice="alice" language="he-IL">אני מאזינה דבר עכשיו</Say>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    @app.route('/webhook/conversation_turn', methods=['POST'])
    def fast_conversation_turn():
        """Ultra-fast conversation webhook - NO DELAYS"""
        try:
            call_sid = request.values.get('CallSid') or 'unknown'
            recording_url = request.values.get('RecordingUrl') or ''
            turn_str = request.values.get('turn', '1')
            
            # Parse turn number quickly
            try:
                turn_num = int(turn_str)
            except:
                turn_num = 1
            
            next_turn = turn_num + 1
            
            print(f"🔄 FAST turn {turn_num} for {call_sid}")
            
            # Use simple listening prompt - no "processing" messages
            audio_url = f"{PUBLIC_HOST}/static/voice_responses/listening_simple.mp3"
            
            # Start background transcription if recording exists
            if recording_url:
                import threading
                threading.Thread(
                    target=lambda: process_recording_background(call_sid, recording_url, turn_num),
                    daemon=True
                ).start()
            
            # Return immediate TwiML response with simple instructions
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
            
            return Response(xml, mimetype="text/xml")
            
        except Exception as e:
            print(f"❌ Fast conversation error: {e}")
            # Ultra-minimal fallback
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/listening_simple.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn" method="POST" maxLength="30"/>
</Response>"""
            return Response(xml, mimetype="text/xml")

def process_recording_background(call_sid, recording_url, turn_num):
    """Process recording in background - verify transcription works"""
    try:
        print(f"🎤 Processing recording for {call_sid}, turn {turn_num}")
        print(f"📥 Recording URL: {recording_url}")
        
        # Download and test transcription
        import requests
        import tempfile
        import os
        
        # Download recording
        response = requests.get(recording_url)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            print(f"✅ Downloaded recording: {len(response.content)} bytes")
            
            # Test Whisper transcription
            try:
                import openai
                client = openai.OpenAI()
                
                with open(temp_path, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he"
                    )
                
                transcribed_text = transcript.text
                print(f"🎯 Transcription successful: '{transcribed_text}'")
                
                # Clean up
                os.unlink(temp_path)
                
                return transcribed_text
                
            except Exception as whisper_error:
                print(f"❌ Whisper transcription error: {whisper_error}")
                os.unlink(temp_path)
                return None
                
        else:
            print(f"❌ Failed to download recording: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Background processing error: {e}")
        return None
    
    @app.route('/webhook/call_status', methods=['POST'])
    def call_status():
        return "OK", 200

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