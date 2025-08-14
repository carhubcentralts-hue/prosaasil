# server/routes_twilio_improved.py - Enhanced Twilio Webhooks
from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse
import os, requests, io, logging

twilio_bp = Blueprint("twilio", __name__, url_prefix="/webhook")
log = logging.getLogger("twilio.voice")

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
    """Professional incoming call handler with immediate recording"""
    call_sid = request.form.get('CallSid', 'unknown')
    from_number = request.form.get('From', '')
    to_number = request.form.get('To', '')
    
    log.info("📞 Professional call started: %s from %s to %s", call_sid, from_number, to_number)
    
    host = os.getenv("HOST", "").rstrip("/")
    vr = VoiceResponse()
    
    # Optional welcome message
    if host and os.path.exists("static/voice_responses/welcome.mp3"):
        vr.play(f"{host}/static/voice_responses/welcome.mp3")
    else:
        # Professional Hebrew greeting
        vr.say("שלום, הגעתם לשי דירות ומשרדים. אני העוזרת הדיגיטלית. אשמח לעזור לכם עם כל שאלה בנושא נדלן. דברו אחרי הצפצוף.", 
               voice="alice", language="he-IL", rate="0.9")
    
    # Immediate recording with optimal settings
    vr.record(
        max_length=30,
        timeout=5,
        finish_on_key="*", 
        play_beep=True,
        action="/webhook/handle_recording",
        method="POST",
        trim="do-not-trim"
    )
    
    response = Response(str(vr), mimetype="text/xml", status=200)
    response.headers['Content-Type'] = 'text/xml; charset=utf-8'
    return response

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    """Professional recording handler with full AI pipeline"""
    call_sid = request.form.get('CallSid', 'unknown')
    recording_url = request.form.get('RecordingUrl', '')
    turn_str = request.form.get('turn', '1')
    
    try:
        turn_num = int(turn_str)
    except ValueError:
        turn_num = 1
    
    log.info("🎤 Processing turn %d for call %s", turn_num, call_sid)
    log.info("📥 Recording URL: %s", recording_url)
    
    if not recording_url:
        log.warning("No recording URL provided")
        return _say("סליחה, לא קיבלתי הקלטה. איך אפשר לעזור?")
    
    # Download recording
    audio_url = f"{recording_url}.mp3"
    try:
        r = requests.get(audio_url, timeout=20)
        r.raise_for_status()
        audio_bytes = io.BytesIO(r.content)
        log.info("✅ Successfully downloaded recording: %d bytes", len(audio_bytes.getvalue()))
    except Exception as e:
        log.error("❌ Failed to download recording: %s", e)
        return _say("תקלה זמנית בהורדת ההקלטה. כיצד לעזור?")

    # Hebrew transcription using Whisper
    try:
        from server.whisper_handler import transcribe_he
        transcription = transcribe_he(audio_bytes)
        log.info("🎯 Transcription: %s", transcription)
    except Exception as e:
        log.error("❌ Transcription failed: %s", e)
        return _say("לא הצלחתי להבין את ההקלטה. איך לעזור?")

    # Generate AI response
    try:
        from server.ai_conversation import generate_response
        ai_response = generate_response(transcription, call_sid)
        log.info("🤖 AI Response: %s", ai_response[:100] + "..." if len(ai_response) > 100 else ai_response)
    except Exception as e:
        log.error("❌ AI response generation failed: %s", e)
        ai_response = "קיבלתי את הבקשה שלך. איך אוכל לעזור לך היום?"

    # Try Hebrew TTS synthesis
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        tts_file_path = create_hebrew_audio(ai_response, call_sid)
        
        if tts_file_path and os.path.exists(tts_file_path):
            host = os.getenv("HOST", "").rstrip("/")
            if host:
                tts_url = f"{host}/{tts_file_path}"
                log.info("🔊 TTS file created: %s", tts_url)
                
                vr = VoiceResponse()
                vr.play(tts_url)
                
                # Continue conversation for next turn
                next_turn = turn_num + 1
                vr.record(
                    max_length=30,
                    timeout=5,
                    finish_on_key="*",
                    play_beep=False,  # No beep for continuation
                    action=f"/webhook/handle_recording?turn={next_turn}",
                    method="POST",
                    trim="do-not-trim"
                )
                
                response = Response(str(vr), mimetype="text/xml", status=200)
                response.headers['Content-Type'] = 'text/xml; charset=utf-8'
                return response
    except Exception as e:
        log.error("❌ TTS synthesis failed: %s", e)

    # Fallback: Use Twilio's built-in Hebrew voice
    return _say_and_continue(ai_response, turn_num + 1)

@twilio_bp.route("/call_status", methods=["POST", "GET"])  
def call_status():
    """Handle call status updates"""
    call_sid = request.form.get('CallSid', 'unknown')
    call_status = request.form.get('CallStatus', 'unknown')
    
    log.info("📊 Call status update: %s - %s", call_sid, call_status)
    
    # Log call completion
    if call_status in ['completed', 'failed', 'busy', 'no-answer']:
        duration = request.form.get('CallDuration', '0')
        log.info("📞 Call %s ended: status=%s duration=%ss", call_sid, call_status, duration)
    
    return Response("", status=200)

def _say(text_he: str):
    """Helper: Create TwiML response with Hebrew text-to-speech"""
    vr = VoiceResponse()
    vr.say(text_he, voice="alice", language="he-IL", rate="0.9")
    
    response = Response(str(vr), mimetype="text/xml", status=200)
    response.headers['Content-Type'] = 'text/xml; charset=utf-8'
    return response

def _say_and_continue(text_he: str, next_turn: int):
    """Helper: Say text and continue conversation"""
    vr = VoiceResponse()
    vr.say(text_he, voice="alice", language="he-IL", rate="0.9")
    
    # Continue conversation
    vr.record(
        max_length=30,
        timeout=5, 
        finish_on_key="*",
        play_beep=False,
        action=f"/webhook/handle_recording?turn={next_turn}",
        method="POST",
        trim="do-not-trim"
    )
    
    response = Response(str(vr), mimetype="text/xml", status=200)
    response.headers['Content-Type'] = 'text/xml; charset=utf-8'
    return response