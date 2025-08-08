from flask import Flask, request, Response

app = Flask(__name__)

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