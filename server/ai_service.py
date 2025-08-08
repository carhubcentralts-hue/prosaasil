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

def generate_reply_tts(user_text: str) -> str:
    answer = _ask_llm_hebrew(user_text)
    try:
        return _tts_google_wavenet_he(answer)
    except Exception:
        # Fallback יחיד (אין לולאה)
        return _tts_google_wavenet_he("סליחה, הייתה תקלה רגעית. כיצד אוכל לעזור?")