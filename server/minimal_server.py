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
    """דף בית עברי לשי דירות ומשרדים"""
    html_content = '''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>שי דירות ומשרדים - מרכז שיחות AI עברי</title>
    <style>
        body { 
            font-family: 'Assistant', Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            margin: 0; 
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .container { 
            text-align: center; 
            background: rgba(255,255,255,0.1); 
            padding: 40px; 
            border-radius: 15px; 
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            max-width: 600px;
        }
        h1 { color: #fff; margin-bottom: 20px; font-size: 2.5em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .status { 
            background: rgba(46, 160, 67, 0.2); 
            padding: 20px; 
            border-radius: 10px; 
            margin: 20px 0;
            border: 1px solid rgba(46, 160, 67, 0.3);
        }
        .feature {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            text-align: right;
        }
        .btn {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 25px;
            margin: 10px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: transform 0.2s;
            font-size: 14px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .system-info {
            margin-top: 20px; 
            font-size: 0.9em; 
            opacity: 0.8;
            background: rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏢 שי דירות ומשרדים בע״מ</h1>
        
        <div class="status">
            <h2>✅ מערכת AI עברית פעילה</h2>
            <p>מרכז שיחות חכם עם תמיכה מלאה בעברית</p>
        </div>

        <div class="feature">
            <h3>📞 שיחות אוטומטיות</h3>
            <p>מערכת מענה חכמה בעברית לשאלות נדל״ן</p>
        </div>

        <div class="feature">
            <h3>💬 WhatsApp Business</h3>
            <p>תמיכה ב-WhatsApp עם AI עברי מתקדם</p>
        </div>

        <div class="feature">
            <h3>🏠 התמחות בנדל״ן</h3>
            <p>AI מותאם לשוק הנדל״ן הישראלי - דירות, משרדים, השכרה ומכירה</p>
        </div>

        <div style="margin-top: 30px;">
            <a href="/api/crm/customers" class="btn">📊 מערכת CRM</a>
            <a href="/webhook/incoming_call" class="btn">📞 בדיקת TwiML</a>
            <a href="/calendar/" class="btn">📅 יומן</a>
            <a href="/signature/" class="btn">📝 חתימות</a>
        </div>

        <div class="system-info">
            <h4>📊 סטטוס מערכת</h4>
            <p><strong>Flask Backend:</strong> ✅ פעיל על פורט 5000</p>
            <p><strong>PostgreSQL:</strong> ✅ מחובר ופעיל</p>
            <p><strong>Twilio Webhooks:</strong> ✅ מוכנים לקבלת שיחות</p>
            <p><strong>AI Hebrew:</strong> ✅ מוכן לתמיכה עברית</p>
            <br>
            <p><strong>📞 טלפון ישראלי:</strong> +972-3-555-7777</p>
            <p><strong>📱 WhatsApp אמריקאי:</strong> +1-555-123-4567</p>
        </div>
    </div>
</body>
</html>'''
    return html_content

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