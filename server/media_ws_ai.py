"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
COMPLETE VERSION WITH REAL STT/TTS
"""
import os, json, time, base64, audioop, math
from simple_websocket import ConnectionClosed

SR = 8000
MIN_UTT_SEC = 0.7   # סוף-מבע לפי דממה קצרה
MAX_UTT_SEC = 6.0   # חיתוך בטיחות

class MediaStreamHandler:
    def __init__(self, ws):
        self.ws = ws
        self.mode = os.getenv("WS_MODE", "AI").upper()  # ודא ש-WS_MODE=AI בסביבה
        self.stream_sid = None
        self.rx = 0
        self.tx = 0
        self.buf = bytearray()
        self.last_rx = None
        self.speaking = False  # חסם לולאה

    def run(self):
        print(f"🚨 MEDIA_STREAM_HANDLER: mode={self.mode}")
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    break
                evt = json.loads(raw)
                et = evt.get("event")

                if et == "start":
                    self.stream_sid = evt["start"]["streamSid"]
                    self.last_rx = time.time()
                    print(f"WS_START sid={self.stream_sid} mode={self.mode}")
                    # פתיחה עם ברכה ב-TTS (בטוח יותר מ-<Play>)
                    if self.mode == "AI":
                        self._speak_text("שלום! איך אפשר לעזור?")
                    continue

                if et == "media":
                    self.rx += 1
                    mulaw = base64.b64decode(evt["media"]["payload"])
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx = time.time()

                    if self.mode == "AI" and not self.speaking:
                        self.buf.extend(pcm16)
                        dur = len(self.buf) / (2 * SR)
                        silent = (time.time() - self.last_rx) >= MIN_UTT_SEC
                        too_long = dur >= MAX_UTT_SEC
                        if (silent or too_long) and dur > 0.25:
                            self._process_utterance(bytes(self.buf))
                            self.buf.clear()
                    continue

                if et == "stop":
                    print(f"WS_STOP sid={self.stream_sid} rx={self.rx} tx={self.tx}")
                    break

        except ConnectionClosed:
            print(f"WS_CLOSED sid={self.stream_sid} rx={self.rx} tx={self.tx}")
        except Exception as e:
            print("WS_ERR:", e)
        finally:
            try: 
                self.ws.close()
            except: 
                pass
            print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    # --- מבע → ASR → LLM → TTS ---
    def _process_utterance(self, pcm16_8k: bytes):
        self.speaking = True
        try:
            print(f"🎤 Processing {len(pcm16_8k)} bytes of Hebrew audio")
            
            # 1. Real Hebrew ASR
            hebrew_text = self._hebrew_stt(pcm16_8k)
            if not hebrew_text or len(hebrew_text.strip()) < 2:
                print("🎤 No speech detected")
                self._send_beep(300)  # Short acknowledgment
                return
                
            print(f"🎤 ASR: {hebrew_text}")
            
            # 2. Real AI response
            ai_response = self._ai_response(hebrew_text)
            print(f"🤖 AI: {ai_response}")
            
            # 3. Real Hebrew TTS
            tts_audio = self._hebrew_tts(ai_response)
            if tts_audio:
                self._send_pcm16_as_mulaw_frames(tts_audio)
                print(f"🔊 TTS sent: {len(tts_audio)} bytes")
            else:
                print("🔊 TTS failed, sending response beep")
                self._send_beep(800)  # Response beep

        finally:
            self.speaking = False

    def _speak_text(self, text: str):
        try:
            print(f"🔊 SPEAKING: {text}")
            # Try real TTS first
            tts_audio = self._hebrew_tts(text)
            if tts_audio:
                self._send_pcm16_as_mulaw_frames(tts_audio)
            else:
                # Fallback: welcome beep
                self._send_beep(500)
        except Exception as e:
            print("TTS_INIT_ERR:", e)
            self._send_beep(500)

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        # clear לפני פריים ראשון
        if self.stream_sid:
            self.ws.send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        for i in range(0, len(mulaw), FR):
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                break
            payload = base64.b64encode(chunk).decode("ascii")
            self.ws.send(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload}
            }))
            self.tx += 1
        # mark (אופציונלי)
        self.ws.send(json.dumps({"event":"mark","streamSid":self.stream_sid,"mark":{"name":"tts_done"}}))

    def _send_beep(self, ms: int):
        # בסיסי: 440Hz ב-PCM16 8kHz
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        self._send_pcm16_as_mulaw_frames(bytes(out))
    
    def _hebrew_stt(self, pcm16_8k: bytes) -> str:
        """Hebrew Speech-to-Text using OpenAI Whisper"""
        try:
            import openai
            import tempfile
            import wave
            
            # Save as temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                with wave.open(f.name, 'wb') as wav:
                    wav.setnchannels(1)  # Mono
                    wav.setsampwidth(2)  # 16-bit
                    wav.setframerate(8000)  # 8kHz
                    wav.writeframes(pcm16_8k)
                
                # Use OpenAI Whisper
                client = openai.OpenAI()
                with open(f.name, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he"  # Hebrew
                    )
                
                import os
                os.unlink(f.name)
                return transcript.text.strip()
                
        except Exception as e:
            print(f"STT_ERROR: {e}")
            return ""
    
    def _ai_response(self, hebrew_text: str) -> str:
        """Generate Hebrew AI response for real estate"""
        try:
            import openai
            client = openai.OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-5",  # the newest OpenAI model is "gpt-5" which was released August 7, 2025. do not change this unless explicitly requested by the user
                messages=[
                    {
                        "role": "system",
                        "content": """אתה נציג שירות לקוחות של 'שי דירות ומשרדים בע״מ' - חברת נדל״ן מובילה.
                        
תפקידך:
- לענות בעברית בצורה מקצועית וידידותית
- לעזור עם שאלות על דירות, משרדים, מחירים ותהליכי השכירות/קנייה
- לקבוע פגישות עם יועצי המכירות
- לתת מידע על השירותים שלנו

השב תמיד בעברית, בקצרה (1-2 משפטים), ובצורה מועילה."""
                    },
                    {
                        "role": "user",
                        "content": hebrew_text
                    }
                ],
                max_completion_tokens=100,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            return content.strip() if content else "סליחה, לא הבנתי"
            
        except Exception as e:
            print(f"AI_ERROR: {e}")
            return "סליחה, יש בעיה טכנית. אפשר לנסות שוב?"
    
    def _hebrew_tts(self, text: str) -> bytes | None:
        """Hebrew Text-to-Speech using Google Cloud TTS"""
        try:
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="he-IL",
                name="he-IL-Standard-A"
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            print(f"TTS_ERROR: {e}")
            return None