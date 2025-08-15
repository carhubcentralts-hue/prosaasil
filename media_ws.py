# media_ws.py
import os, json, asyncio, logging, time, tempfile, numpy as np, soundfile as sf
from flask import current_app
from audio_utils import b64_to_mulaw, mulaw8k_to_pcm16k, pcm16k_float_to_mulaw8k_frames

# Logger
log = logging.getLogger("media_ws")

# Google TTS
try:
    from google.cloud import texttospeech as tts_module
    
    # הגדרת credentials מ-environment variable
    creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_json and creds_json.startswith("{"):
        # אם זה JSON string, כתוב לקובץ זמני
        with open("/tmp/tts_creds.json", "w") as f:
            f.write(creds_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/tts_creds.json"
    
    tts_client = tts_module.TextToSpeechClient()
    log.info("✅ Google TTS client initialized")
except Exception as e:
    log.error("❌ Google TTS failed: %s", e)
    tts_client = None
    tts_module = None

# OpenAI
try:
    from openai import OpenAI
    gpt = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    log.info("✅ OpenAI client initialized")
except Exception as e:
    log.error("❌ OpenAI failed: %s", e)
    gpt = None

# Simple VAD (Voice Activity Detection) 
def has_voice_energy(pcm16k: np.ndarray, threshold=0.01) -> bool:
    """בדיקה פשוטה - האם יש אנרגיה קולית מספיקה"""
    if len(pcm16k) == 0:
        return False
    rms = np.sqrt(np.mean(pcm16k ** 2))
    return rms > threshold

def tts_he_wavenet(text: str) -> np.ndarray:
    """TTS לעברית → PCM16@16k float32 [-1,1]"""
    if not tts_client or not tts_module:
        log.error("TTS client not available")
        return np.zeros(16000, dtype=np.float32)  # שקט של שנייה
        
    try:
        inp = tts_module.SynthesisInput(text=text)
        voice = tts_module.VoiceSelectionParams(
            language_code="he-IL", 
            name="he-IL-Wavenet-A"
        )
        cfg = tts_module.AudioConfig(
            audio_encoding=tts_module.AudioEncoding.LINEAR16, 
            sample_rate_hertz=16000
        )
        res = tts_client.synthesize_speech(input=inp, voice=voice, audio_config=cfg)
        
        # כתיבה זמנית וקריאה כ-numpy
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(res.audio_content)
            wav_path = f.name
        
        data, sr = sf.read(wav_path, dtype="float32")
        os.unlink(wav_path)  # ניקוי
        
        if sr != 16000:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=16000)
        
        return data.astype(np.float32)
    except Exception as e:
        log.error("TTS error: %s", e)
        return np.zeros(16000, dtype=np.float32)  # שקט של שנייה

def transcribe_chunk(pcm16k: np.ndarray) -> str:
    """תמלול אודיו עברי באמצעות OpenAI Whisper"""
    try:
        import io
        import soundfile as sf
        from openai import OpenAI
        
        # בדיקה שיש אודיו בכלל
        if len(pcm16k) == 0:
            return ""
            
        # יצירת client עם API key
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # המרה לפורמט WAV
        buf = io.BytesIO()
        sf.write(buf, pcm16k, 16000, subtype="PCM_16", format="WAV")
        buf.seek(0)
        
        # תמלול עם Whisper
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", buf, "audio/wav"),
            language="he"
        )
        
        result = response.text.strip() if response.text else ""
        log.info("✅ תמלול הושלם: %s", result[:50] + "..." if len(result) > 50 else result)
        return result
        
    except Exception as e:
        log.error(f"❌ שגיאה בתמלול: {e}")
        return ""

def llm_reply(user_text: str) -> str:
    """תגובת AI עבור הנדל"ן"""
    if not gpt:
        return "שלום, אני עוזר של שי דירות ומשרדים. איך אוכל לעזור?"
        
    try:
        from typing import List, Dict, Any
        msgs: List[Dict[str, Any]] = [
            {"role": "system", "content": "אתה סוכן נדל\"ן מקצועי עבור שי דירות ומשרדים בע\"מ. דבר בעברית, היה קצר ומועיל. אם מישהו שואל על נכס, הציע פגישה."},
            {"role": "user", "content": user_text}
        ]
        r = gpt.chat.completions.create(
            model="gpt-4o-mini", 
            messages=msgs,  # type: ignore
            temperature=0.3,
            max_tokens=100
        )
        response_content = r.choices[0].message.content
        return response_content.strip() if response_content else "שלום, איך אוכל לעזור לכם עם נדל\"ן?"
    except Exception as e:
        log.error("AI error: %s", e)
        return "שלום, איך אוכל לעזור לכם עם נדל\"ן?"

def is_goodbye(text: str) -> bool:
    """זיהוי סיום שיחה"""
    t = text.strip().lower()
    return any(w in t for w in ["ביי", "להתראות", "נתראה", "סגור", "bye", "goodbye", "תודה רבה"])

def handle_twilio_media(ws):
    """
    פרוטוקול Twilio Media Streams:
    - {"event":"start","start":{"streamSid":...,"callSid":...}}
    - {"event":"media","media":{"payload":"<b64 μ-law 8k>"}}   כל ~20ms
    - {"event":"stop",...}
    אנחנו מחזירים:
    - {"event":"media","streamSid":sid,"media":{"payload":"<b64 μ-law 8k>"}}
    """
    stream_sid = call_sid = None
    buf16k = np.zeros(0, dtype=np.float32)
    last_voice_ts = time.time()
    speaking = False  # האם אנחנו כרגע מנגנים TTS
    conversation_started = False
    
    try:
        while True:
            raw = ws.receive()
            if raw is None: 
                break
            evt = json.loads(raw)

            if evt.get("event") == "start":
                stream_sid = evt["start"]["streamSid"]
                call_sid = evt["start"]["callSid"]
                log.info("🔥 Stream started: %s call=%s", stream_sid, call_sid)
                
                # ברכה ראשונית
                greeting = "שלום! אתם מדברים עם שי דירות ומשרדים. איך אוכל לעזור לכם?"
                audio = tts_he_wavenet(greeting)
                speaking = True
                for frame in pcm16k_float_to_mulaw8k_frames(audio):
                    ws.send(json.dumps({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": frame}
                    }))
                    time.sleep(0.02)
                speaking = False
                conversation_started = True
                continue

            if evt.get("event") == "stop":
                log.info("🛑 Stream stop: %s", stream_sid)
                break

            if evt.get("event") == "media" and conversation_started:
                # 1) דגימה נכנסת → צבירה
                mulaw_b64 = evt["media"]["payload"]
                mulaw = b64_to_mulaw(mulaw_b64)
                pcm16k = mulaw8k_to_pcm16k(mulaw)
                buf16k = np.concatenate([buf16k, pcm16k])

                # 2) בדיקת אנרגיה קולית
                if len(buf16k) >= int(0.32 * 16000):  # 320ms
                    chunk = buf16k[-int(0.32 * 16000):]
                    if has_voice_energy(chunk):
                        last_voice_ts = time.time()
                    
                    # אם עברו >800ms בלי דיבור → סוף אמירה
                    if (time.time() - last_voice_ts) > 0.8 and not speaking and len(buf16k) > int(0.5 * 16000):
                        speaking = True
                        utter = buf16k.copy()
                        buf16k = np.zeros(0, dtype=np.float32)

                        # 3) תמלול
                        text = transcribe_chunk(utter)
                        log.info("👂 User said: %s", text)
                        
                        if not text or len(text.strip()) < 2:
                            speaking = False
                            continue

                        # 4) האם לסיים שיחה?
                        if is_goodbye(text):
                            reply = "תודה שפניתם לשי דירות ומשרדים! נשמח לעזור בעתיד. להתראות!"
                            audio = tts_he_wavenet(reply)
                            for frame in pcm16k_float_to_mulaw8k_frames(audio):
                                ws.send(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": frame}
                                }))
                                time.sleep(0.02)
                            
                            # ניתוק השיחה
                            try:
                                from twilio.rest import Client
                                client = Client(
                                    os.getenv("TWILIO_ACCOUNT_SID"), 
                                    os.getenv("TWILIO_AUTH_TOKEN")
                                )
                                if call_sid:
                                    client.calls(call_sid).update(status="completed")
                                    log.info("✅ Call terminated gracefully")
                                else:
                                    log.warning("⚠️ No call_sid to terminate")
                            except Exception as e:
                                log.error("❌ Failed to end call: %s", e)
                            break

                        # 5) תגובת AI
                        reply = llm_reply(text)
                        log.info("🤖 AI reply: %s", reply)

                        # 6) TTS → שליחה לטלפון
                        audio = tts_he_wavenet(reply)
                        for frame in pcm16k_float_to_mulaw8k_frames(audio):
                            ws.send(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": frame}
                            }))
                            time.sleep(0.02)

                        speaking = False
                        
    except Exception as e:
        log.exception("❌ WebSocket error: %s", e)
    finally:
        try: 
            ws.close()
        except: 
            pass
        log.info("🔚 WebSocket closed: %s", stream_sid)