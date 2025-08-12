from flask import Blueprint, request, Response, current_app

twilio_bp = Blueprint("twilio_bp", __name__, url_prefix="")

@twilio_bp.post("/webhook/incoming_call")
def incoming_call():
    # ברכה עברית מובנית עם הוראות ברורות
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום וברכה! הגעתם לשי דירות ומשרדים בעמ. אנחנו כאן לעזור לכם למצוא את הנכס המושלם. אנא דברו אחרי הצפצוף ולחצו כוכבית כשסיימתם.</Say>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30"
          timeout="8"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@twilio_bp.post("/webhook/handle_recording")
def handle_recording():
    from flask import request
    import requests
    
    # קבלת הקלטה מTwilio
    recording_url = request.form.get('RecordingUrl')
    caller = request.form.get('From', 'לא ידוע')
    
    print(f"🎙️ התקבלה הקלטה מ-{caller}: {recording_url}")
    
    if recording_url:
        try:
            # כאן יבוא התמלול עם Whisper בעתיד
            # כרגע נחזיר תודה ומספר ליצירת קשר
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה רבה על פנייתכם. קיבלנו את הודעתכם ונחזור אליכם בהקדם. למידע נוסף חייגו אפס שלוש חמש חמש חמש שבעת אלפים שבע מאות שבעים ושבע. שיהיה לכם יום נעים!</Say>
  <Hangup/>
</Response>"""
            return Response(xml, mimetype="text/xml")
            
        except Exception as e:
            print(f"❌ שגיאה בטיפול בהקלטה: {e}")
    
    # ברירת מחדל אם אין הקלטה
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">לא הצלחנו לקבל את הודעתכם. אנא חייגו שוב מאוחר יותר. תודה רבה!</Say>
  <Hangup/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@twilio_bp.post("/webhook/call_status")
def call_status():
    # Always return 200 for Twilio status updates
    return "OK", 200