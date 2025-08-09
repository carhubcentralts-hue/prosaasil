from flask import Flask, request, Response, send_from_directory
import os

app = Flask(__name__, static_folder='static')

# Static file serving for voice responses
@app.route('/static/<path:filename>')
def serve_static(filename):
    """שרת קבצים סטטיים - קבצי אודיו"""
    static_dir = app.static_folder or 'static'
    return send_from_directory(static_dir, filename)

@app.route('/voice_responses/<path:filename>')
def serve_voice_responses(filename):
    """שרת קבצי תגובות קוליות"""
    static_dir = app.static_folder or 'static'
    voice_dir = os.path.join(static_dir, 'voice_responses')
    return send_from_directory(voice_dir, filename)

@app.route("/")
def home():
    """דף התחברות פשוט"""
    from flask import send_file
    
    # Try to serve React built files first
    dist_path = os.path.join(os.path.dirname(__file__), '..', 'client', 'dist', 'index.html')
    if os.path.exists(dist_path):
        return send_file(dist_path)
    
    # Simple login page fallback
    return '''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>התחברות - AgentLocator CRM</title>
    <style>
        body { 
            font-family: "Assistant", Arial, sans-serif; 
            margin: 0;
            direction: rtl;
            background: white;
            min-height: 100vh;
            display: grid;
            place-items: center;
        }
        .login-form {
            width: 100%;
            max-width: 380px;
            padding: 24px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            border: 1px solid #ddd;
        }
        h1 { margin-bottom: 16px; font-weight: 700; color: #333; }
        label { display: block; margin-bottom: 8px; color: #333; }
        input { 
            width: 100%; 
            padding: 12px; 
            margin-bottom: 12px; 
            border-radius: 10px; 
            border: 1px solid #ddd;
            box-sizing: border-box;
        }
        button { 
            width: 100%; 
            padding: 12px; 
            border-radius: 10px; 
            border: none; 
            background: #007bff;
            color: white;
            font-weight: 700; 
            cursor: pointer;
        }
        .demo { margin-top: 16px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <form class="login-form">
        <h1>התחברות</h1>
        <label>אימייל</label>
        <input type="email" required>
        <label>סיסמה</label>
        <input type="password" required>
        <button type="submit">כניסה</button>
        <div class="demo">דמו: admin@example.com / demo123</div>
    </form>
</body>
</html>'''


@app.route("/webhook/incoming_call", methods=["POST"])
def incoming_call():
    """טיפול בשיחות נכנסות - מחזיר TwiML תקין"""
    twiml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>http://localhost:5000/static/greeting.mp3</Play>
    <Record finishOnKey="*" timeout="5" maxLength="30" playBeep="true" action="/webhook/handle_recording"/>
</Response>'''
    return Response(twiml_response, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=["POST"])
def handle_recording():
    """טיפול בהקלטות - מחזיר TwiML בסיסי"""
    # בגרסה מלאה: transcribe_hebrew + generate_reply_tts 
    twiml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>http://localhost:5000/static/reply.mp3</Play>
</Response>'''
    return Response(twiml_response, mimetype="text/xml")

@app.route("/webhook/call_status", methods=["POST"])
def call_status():
    """מעקב סטטוס שיחות"""
    return ("", 200)

@app.route("/api/crm/customers", methods=["GET"])
def customers():
    """נתיב CRM בסיסי"""
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 25)), 100)
    return {
        "page": page,
        "limit": limit, 
        "total": 0,
        "items": []
    }

@app.route("/signature/", methods=["GET"])
def signature_home():
    return {"message": "Signature route placeholder"}, 200

@app.route("/calendar/", methods=["GET"])  
def calendar_home():
    return {"message": "Calendar route placeholder"}, 200

@app.route("/proposal/", methods=["GET"])
def proposal_home():
    return {"message": "Proposal route placeholder"}, 200

@app.route("/reports/", methods=["GET"])
def reports_home():
    return {"message": "Reports route placeholder"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)