import io, requests, os
from pydub import AudioSegment

TW_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TW_TOKEN= os.getenv("TWILIO_AUTH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def _download_recording(url: str) -> bytes:
    # Twilio מוסיפה URL ללא סיומת — נסה .mp3 ואז .wav
    if not TW_SID or not TW_TOKEN:
        raise ValueError("Missing Twilio credentials")
    
    for ext in (".mp3", ".wav"):
        r = requests.get(url + ext, auth=(TW_SID, TW_TOKEN), timeout=30)
        if r.ok and r.content:
            return r.content
    # fallback: נסה כמו שהוא
    r = requests.get(url, auth=(TW_SID, TW_TOKEN), timeout=30)
    r.raise_for_status()
    return r.content

def transcribe_hebrew(recording_url: str) -> str:
    if not OPENAI_API_KEY:
        return "שגיאה: חסר מפתח OpenAI"
    
    try:
        raw = _download_recording(recording_url)
        # ייצוב לפורמט WAV 16k
        audio = AudioSegment.from_file(io.BytesIO(raw))
        wav_bytes = io.BytesIO()
        audio.set_channels(1).set_frame_rate(16000).export(wav_bytes, format="wav")
        wav_bytes.seek(0)

        # Whisper (OpenAI) – הגדר שפה לעברית להעדפה
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data  = {"model": "whisper-1", "language": "he"}
        resp = requests.post("https://api.openai.com/v1/audio/transcriptions",
                             headers=headers, files=files, data=data, timeout=120)
        resp.raise_for_status()
        text = resp.json().get("text","").strip()
        # סינון ג'יבריש קצר
        return text if len(text) >= 2 else "לא נשמע בבירור, נסה שוב."
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return "סליחה, לא הצלחתי לשמוע אותך. נסה שוב."