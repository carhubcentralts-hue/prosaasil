# server/routes_twilio.py
from flask import Blueprint, request, Response, current_app, jsonify
from twilio.twiml.voice_response import VoiceResponse
import os, requests, io
import openai
import tempfile

twilio_bp = Blueprint("twilio", __name__, url_prefix="/webhook")

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
    host = os.getenv("HOST", "https://ai-crmd.replit.app").rstrip("/")
    vr = VoiceResponse()

    # Play greeting if exists
    greeting_url = f"{host}/static/voice_responses/welcome.mp3"
    if greeting_url:
        vr.play(greeting_url)

    # Record according to requirements
    vr.record(
        max_length=30,
        timeout=5,
        finish_on_key="*",
        play_beep=True,
        action="/webhook/handle_recording",
        method="POST",
        trim="do-not-trim"
    )
    # Return TwiML
    return Response(str(vr), mimetype="text/xml", status=200)

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    """מקבל RecordingUrl, מוריד אודיו, מטמיע Whisper (עברית), GPT, TTS (fallback חד-פעמי)"""
    rec_url = request.form.get("RecordingUrl")
    if not rec_url and request.is_json and request.json:
        rec_url = request.json.get("RecordingUrl")
    if not rec_url:
        # אין הקלטה → Fallback חד-פעמי
        return _say_fallback("סליחה, לא קיבלתי הקלטה. כיצד אוכל לעזור?")

    # Twilio נותן URL ללא סיומת; מוסיפים .mp3 (או .wav) לפי קונפיג שלכם
    audio_url = f"{rec_url}.mp3"

    # הורדת האודיו
    try:
        r = requests.get(audio_url, timeout=20)
        r.raise_for_status()
        audio_bytes = io.BytesIO(r.content)
    except Exception:
        return _say_fallback("סליחה, הייתה תקלה זמנית בהורדת ההקלטה. איך אפשר לעזור?")

    # Whisper עברית
    try:
        text_he = transcribe_he(audio_bytes)
        if not text_he or len(text_he.strip()) < 3:
            return _say_fallback("לא הצלחתי להבין את ההקלטה. איך אוכל לעזור?")
    except Exception:
        return _say_fallback("לא הצלחתי להבין את ההקלטה. איך אוכל לעזור?")

    # GPT תשובה
    try:
        reply_he = generate_reply(text_he)
    except Exception:
        reply_he = "קיבלתי את הבקשה. מאשרת. האם תרצה שאחזור אליך?"

    # TTS (פעם אחת; אם נופל, מציגים הודעה קצרה)
    try:
        tts_url = synthesize_tts_he(reply_he)
        if tts_url:
            vr = VoiceResponse()
            vr.play(tts_url)
            return Response(str(vr), mimetype="text/xml", status=200)
    except Exception:
        pass

    return _say_fallback("אוקיי. רשמתי לפני. איך עוד לעזור?")

@twilio_bp.route("/call_status", methods=["POST"])
def call_status():
    """Always return 200 for call status"""
    return Response("OK", status=200)

def _say_fallback(text_he: str):
    vr = VoiceResponse()
    vr.say(text_he, language="he-IL", voice="alice")
    return Response(str(vr), mimetype="text/xml", status=200)

# ====== פונקציות גישור (להחליף בקריאות למודולים אצלכם) ======

def transcribe_he(audio_bytes_io):
    """
    Whisper Hebrew transcription
    """
    try:
        client = openai.OpenAI()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes_io.read())
            temp_path = temp_file.name
        
        # Transcribe with Whisper
        with open(temp_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he",
                response_format="text"
            )
        
        # Cleanup
        os.unlink(temp_path)
        
        result = str(transcript) if transcript else ""
        return result.strip()
        
    except Exception as e:
        print(f"Whisper transcription failed: {e}")
        return ""

def generate_reply(text_he: str) -> str:
    """GPT Hebrew real estate response"""
    try:
        client = openai.OpenAI()
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """אתה סוכן נדל"ן מקצועי בשי דירות ומשרדים בע"מ. 
                    תן תשובות קצרות, מקצועיות ומועילות בעברית.
                    שאל שאלות רלוונטיות כדי לעזור ללקוח.
                    הצע פגישה או יצירת קשר נוסף כשמתאים."""
                },
                {
                    "role": "user", 
                    "content": text_he
                }
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        return content.strip() if content else "תודה על הפנייה."
        
    except Exception as e:
        print(f"GPT response failed: {e}")
        return "תודה על הפנייה. נחזור אליך בהקדם."

def synthesize_tts_he(text_he: str) -> str | None:
    """
    Generate Hebrew TTS and return URL
    """
    try:
        from gtts import gTTS
        import hashlib
        
        # Create unique filename
        text_hash = hashlib.md5(text_he.encode()).hexdigest()[:8]
        filename = f"tts_response_{text_hash}.mp3"
        
        # Create TTS audio
        tts = gTTS(text=text_he, lang='iw', slow=False)
        
        # Save to static directory
        static_dir = "static/voice_responses"
        os.makedirs(static_dir, exist_ok=True)
        file_path = os.path.join(static_dir, filename)
        
        tts.save(file_path)
        
        # Return public URL
        host = os.getenv("HOST", "https://ai-crmd.replit.app").rstrip("/")
        return f"{host}/static/voice_responses/{filename}"
        
    except Exception as e:
        print(f"TTS generation failed: {e}")
        return None