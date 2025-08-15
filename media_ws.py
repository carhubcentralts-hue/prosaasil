# media_ws.py - Hebrew Real-time Voice Processing for Twilio Media Streams
import os, json, time, tempfile, logging
import numpy as np
import soundfile as sf
from audio_utils import b64_to_mulaw, mulaw8k_to_pcm16k, pcm16k_float_to_mulaw8k_frames

log = logging.getLogger("media_ws")

# Initialize Google TTS - ensure credentials are bootstrapped first
tts_client = None
tts_module = None

def init_tts_client():
    """Initialize TTS client with proper credentials"""
    global tts_client, tts_module
    if tts_client is not None:
        return tts_client
        
    try:
        # Bootstrap credentials first
        from server.bootstrap_secrets import ensure_google_creds_file
        creds_result = ensure_google_creds_file()
        if not creds_result:
            log.warning("Google credentials not available for TTS")
            return None
            
        from google.cloud import texttospeech as tts_mod
        tts_module = tts_mod
        tts_client = tts_mod.TextToSpeechClient()
        log.info("✅ Google TTS client initialized with credentials")
        return tts_client
    except Exception as e:
        log.error(f"❌ Google TTS failed: {e}")
        return None

# Try to initialize on import
try:
    init_tts_client()
except:
    pass  # Will retry when needed

# Initialize OpenAI
try:
    from openai import OpenAI
    gpt = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    log.info("✅ OpenAI client initialized")
except Exception as e:
    log.error(f"❌ OpenAI failed: {e}")
    gpt = None

def has_voice_energy(pcm16k: np.ndarray, threshold=0.01) -> bool:
    """Simple voice activity detection"""
    if len(pcm16k) == 0:
        return False
    rms = np.sqrt(np.mean(pcm16k ** 2))
    return rms > threshold

def tts_he_wavenet_safe(text: str) -> np.ndarray:
    """Hebrew TTS using Google Cloud with fallback → PCM16@16k float32 [-1,1]"""
    # Try to ensure TTS client is available
    client = init_tts_client()
    if not client or not tts_module:
        log.error("TTS client not available - returning silence")
        return np.zeros(16000, dtype=np.float32)  # 1 second of silence
        
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
        res = client.synthesize_speech(input=inp, voice=voice, audio_config=cfg)
        
        # Write to temp file and read as numpy
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(res.audio_content)
            wav_path = f.name
        
        data, sr = sf.read(wav_path, dtype="float32")
        os.unlink(wav_path)  # cleanup
        
        if sr != 16000:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=16000)
        
        log.info(f"✅ TTS generated {len(data)} samples for: {text[:30]}...")
        return data.astype(np.float32)
        
    except Exception as e:
        log.error(f"TTS error: {e}")
        return np.zeros(16000, dtype=np.float32)  # fallback silence

# Backward compatibility alias
def tts_he_wavenet(text: str) -> np.ndarray:
    return tts_he_wavenet_safe(text)

def transcribe_he_whisper(pcm16k: np.ndarray) -> str:
    """Hebrew transcription using OpenAI Whisper"""
    if not gpt or len(pcm16k) == 0:
        return ""
        
    try:
        # Save to temporary wav file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, pcm16k, 16000, format='WAV')
            wav_path = f.name
        
        # Send to Whisper API
        with open(wav_path, "rb") as audio_file:
            transcript = gpt.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he"
            )
        
        os.unlink(wav_path)  # cleanup
        return transcript.text.strip() if transcript.text else ""
        
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return ""

def gpt_response_he(user_input: str) -> str:
    """Smart Hebrew response using GPT-4o"""
    if not gpt or not user_input.strip():
        return "שלום מ שי דירות ומשרדים בע״מ"
        
    try:
        response = gpt.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": """אתה נציג מכירות מקצועי של "שי דירות ומשרדים בע״מ" - חברת נדל״ן מובילה בישראל.

תפקידך:
- ענה בעברית בלבד
- היה מקצועי, חברותי ועוזר
- קדם דירות ומשרדים למכירה ולהשכרה
- אמור "מה אוכל לעזור לכם?" בסוף
- השאר פרטים (שם, טלפון) לחזרה מהצוות
- תשובות קצרות עד 20 מילים"""
                },
                {"role": "user", "content": user_input}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        return answer.strip() if answer else "שלום מ שי דירות ומשרדים. מה אוכל לעזור לכם?"
        
    except Exception as e:
        log.error(f"GPT error: {e}")
        return "שלום מ שי דירות ומשרדים. השאירו הודעה ונחזור אליכם."

def handle_twilio_media(ws):
    """
    Handle Twilio Media Streams WebSocket - Hebrew real-time bidirectional calls
    טיפול בWebSocket של Twilio Media Streams - שיחות דו-כיווניות בזמן אמת בעברית
    """
    log.info("🌐 WebSocket connection established for Hebrew call")
    
    # Buffer for accumulating audio
    audio_buffer = np.array([], dtype=np.float32)
    silence_counter = 0
    conversation_memory = []
    stream_sid = None
    
    try:
        while True:
            message = ws.receive()
            if not message:
                break
                
            try:
                data = json.loads(message)
                event = data.get("event")
                
                if event == "start":
                    stream_sid = data.get("start", {}).get("streamSid", "")
                    log.info("🔄 Media stream started")
                    
                    # Send initial Hebrew greeting
                    try:
                        greeting = "שלום! הגעתם ל שי דירות ומשרדים בע״מ. איך אוכל לעזור לכם?"
                        greeting_audio = tts_he_wavenet_safe(greeting)
                        if greeting_audio is not None and len(greeting_audio) > 0:
                            greeting_frames = pcm16k_float_to_mulaw8k_frames(greeting_audio)
                            
                            for frame in greeting_frames:
                                media_msg = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": frame}
                                }
                                ws.send(json.dumps(media_msg))
                                time.sleep(0.02)  # 20ms between frames
                            
                            log.info("✅ Hebrew greeting sent successfully")
                        else:
                            log.warning("⚠️ TTS failed, skipping greeting")
                        
                    except Exception as e:
                        log.error(f"❌ Failed to send greeting: {e}")
                
                elif event == "media":
                    # Receive audio from user
                    payload = data.get("media", {}).get("payload", "")
                    if payload:
                        # Convert to PCM
                        mulaw_data = b64_to_mulaw(payload)
                        pcm_chunk = mulaw8k_to_pcm16k(mulaw_data)
                        
                        if len(pcm_chunk) > 0:
                            audio_buffer = np.concatenate([audio_buffer, pcm_chunk])
                            
                            # Check for voice activity
                            if has_voice_energy(pcm_chunk):
                                silence_counter = 0
                            else:
                                silence_counter += 1
                            
                            # Process if we have enough audio and silence detected
                            if len(audio_buffer) > 16000 and silence_counter > 10:  # ~1 sec audio + silence
                                transcript = transcribe_he_whisper(audio_buffer)
                                log.info(f"🎤 Transcribed: {transcript}")
                                
                                if transcript and len(transcript.strip()) > 2:
                                    # Generate AI response
                                    ai_response = gpt_response_he(transcript)
                                    log.info(f"🤖 AI Response: {ai_response}")
                                    
                                    # Convert to speech and send
                                    response_audio = tts_he_wavenet_safe(ai_response)
                                    if response_audio is not None and len(response_audio) > 0:
                                        response_frames = pcm16k_float_to_mulaw8k_frames(response_audio)
                                        
                                        for frame in response_frames:
                                            media_msg = {
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {"payload": frame}
                                            }
                                            ws.send(json.dumps(media_msg))
                                            time.sleep(0.02)
                                    else:
                                        log.warning("⚠️ TTS failed for response, skipping audio")
                                    
                                    # Save to conversation memory
                                    conversation_memory.append({
                                        "user": transcript,
                                        "ai": ai_response,
                                        "timestamp": time.time()
                                    })
                                
                                # Reset buffer
                                audio_buffer = np.array([], dtype=np.float32)
                                silence_counter = 0
                
                elif event == "stop":
                    log.info("🔚 Media stream stopped")
                    break
                    
            except json.JSONDecodeError:
                log.warning("Invalid JSON received")
            except Exception as e:
                log.error(f"Error processing message: {e}")
                
    except Exception as e:
        log.error(f"❌ WebSocket handler error: {e}")
        import traceback
        traceback.print_exc()
    
    log.info(f"🏁 Call ended. Conversation turns: {len(conversation_memory)}")