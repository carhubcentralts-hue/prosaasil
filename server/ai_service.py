import os, uuid
from google.cloud import texttospeech
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUDIO_DIR = "server/static/tts"

def _ensure_dir():
    os.makedirs(AUDIO_DIR, exist_ok=True)

def _ask_llm_hebrew(prompt: str) -> str:
    # החלף לקריאה למודל הטקסט שלך (GPT וכו')
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"}
    body = {"model":"gpt-4o-mini", "messages":[{"role":"user","content":prompt}]}
    r = requests.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def _tts_google_wavenet_he(text: str) -> str:
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="he-IL", name="he-IL-Wavenet-A")
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    _ensure_dir()
    fn = f"{uuid.uuid4().hex}.mp3"
    out_path = os.path.join(AUDIO_DIR, fn)
    resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    with open(out_path, "wb") as f:
        f.write(resp.audio_content)
    return f"/static/tts/{fn}"

def generate_reply_tts(user_text: str, business_id: int = 13) -> str:
    """Generate AI reply with TTS for specific business"""
    # Get business AI prompt from database using direct SQL
    import sqlite3
    import os
    
    try:
        # Try PostgreSQL first (production)
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            import psycopg2
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            cursor.execute("SELECT ai_prompt FROM businesses WHERE id = %s", (business_id,))
            result = cursor.fetchone()
            business_prompt = result[0] if result else None
            conn.close()
        else:
            business_prompt = None
    except Exception as e:
        print(f"Database error: {e}")
        business_prompt = None
    
    # Create a mock business object
    business = type('Business', (), {})()
    business.ai_prompt = business_prompt
    
    if business and business.ai_prompt:
        # Use business-specific AI prompt
        full_prompt = f"{business.ai_prompt}\n\nשאלת הלקוח: {user_text}\n\nענה בעברית בצורה מקצועית ונעימה:"
    else:
        # Fallback prompt
        full_prompt = f"אתה עוזר וירטואלי עבור עסק נדל״ן בישראל. ענה על השאלה הזו בעברית: {user_text}"
    
    answer = _ask_llm_hebrew(full_prompt)
    try:
        return _tts_google_wavenet_he(answer)
    except Exception:
        # Fallback יחיד (אין לולאה)
        return _tts_google_wavenet_he("סליחה, הייתה תקלה רגעית. כיצד אוכל לעזור?")