from flask import Blueprint, request, Response, current_app
from twilio.twiml.voice_response import VoiceResponse
from whisper_handler import transcribe_hebrew
from ai_service import generate_reply_tts

twilio_bp = Blueprint("twilio", __name__)

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
    """Handle incoming calls with business-specific greeting"""
    host = current_app.config.get("HOST", request.host_url.rstrip("/"))
    called_number = request.form.get("Called", "")
    
    # Find business by phone number - שי דירות ומשרדים
    business_id = 13  # Default to our real estate business
    
    vr = VoiceResponse()
    
    # Use business-specific Hebrew greeting
    vr.say("שלום, הגעתם לשי דירות ומשרדים - המומחים שלכם בנדלן. אנא השאירו הודעה קצרה ונחזור אליכם בהקדם.", 
           language="he-IL", voice="alice")
    
    # Record with longer timeout to prevent disconnection
    vr.record(
        finish_on_key="*",
        timeout=8,
        max_length=45,
        play_beep=True,
        action=f"/webhook/handle_recording?business_id={business_id}",
        transcribe=False
    )
    return Response(str(vr), mimetype="text/xml")

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    """Handle recording with business context and continue conversation"""
    rec_url = request.form.get("RecordingUrl", "")
    business_id = request.args.get("business_id", 13, type=int)
    
    try:
        # Transcribe Hebrew audio
        text = transcribe_hebrew(rec_url)
        print(f"🎤 תמלול: {text}")
        
        # Generate business-specific AI response
        audio_url = generate_reply_tts(text, business_id)
        print(f"🔊 תשובה AI נוצרה: {audio_url}")
        
        vr = VoiceResponse()
        # Play AI response
        vr.play(f"http://localhost:5000{audio_url}")
        
        # Continue conversation - record again for follow-up
        vr.record(
            finish_on_key="*",
            timeout=8,
            max_length=45,
            play_beep=True,
            action=f"/webhook/handle_recording?business_id={business_id}",
            transcribe=False
        )
        
        return Response(str(vr), mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ שגיאה בטיפול בהקלטה: {e}")
        vr = VoiceResponse()
        vr.say("סליחה, הייתה תקלה רגעית. אנא נסו שוב או צרו קשר מאוחר יותר.", 
               language="he-IL", voice="alice")
        return Response(str(vr), mimetype="text/xml")

@twilio_bp.route("/call_status", methods=["POST"])
def call_status():
    return ("", 200)