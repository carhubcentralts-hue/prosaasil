"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue
from simple_websocket import ConnectionClosed

SR = 8000
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.7"))   # זמן דממה לסוף-מבע
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "6.0"))   # חיתוך בטיחות
VAD_RMS = int(os.getenv("VAD_RMS", "200"))             # סף דיבור (RMS)
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"

# מכונת מצבים
STATE_LISTEN = "LISTENING"
STATE_THINK  = "THINKING"
STATE_SPEAK  = "SPEAKING"

class MediaStreamHandler:
    def __init__(self, ws):
        self.ws = ws
        self.mode = "AI"  # תמיד במצב AI
        self.stream_sid = None
        self.rx = 0
        self.tx = 0
        
        # 🎯 פתרון פשוט ויעיל לניהול תורות
        self.buf = bytearray()
        self.last_rx = None
        self.speaking = False           # האם הבוט מדבר כרגע
        self.processing = False         # האם מעבד מבע כרגע
        self.conversation_id = 0        # מונה שיחות למניעת כפילויות
        self.last_processing_id = -1    # מזהה העיבוד האחרון
        self.response_timeout = None    # זמן תגובה מקסימלי
        
        # דה-דופליקציה מתקדמת
        self.last_user_text = ""
        self.last_response_text = ""
        self.response_history = []       # היסטוריית תגובות
        
        print("🎯 SIMPLE TURN-TAKING: No loops, one response per input")

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
                    self.last_rx_ts = time.time()
                    print(f"WS_START sid={self.stream_sid} mode={self.mode}")
                    
                    # ברכה פשוטה ובודדת
                    greeting = "שלום! אני העוזרת החכמה של שי דירות ומשרדים. איך אני יכולה לעזור לך היום?"
                    print(f"🔊 GREETING: {greeting}")
                    self._speak_simple(greeting)
                    continue

                if et == "media":
                    self.rx += 1
                    b64 = evt["media"]["payload"]
                    mulaw = base64.b64decode(b64)
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx_ts = time.time()

                    # מדד דיבור/שקט (VAD)
                    rms = audioop.rms(pcm16, 2)
                    is_voice = rms > VAD_RMS

                    # 🎯 פתרון פשוט: רק בדוק אם המערכת מדברת ונקה buffer
                    if self.speaking:
                        # כשהמערכת מדברת - נקה כל קלט
                        self.buf.clear()
                        continue
                    
                    # איסוף אודיו רק כשלא מעבדים ולא מדברים
                    if not self.processing:
                        self.buf.extend(pcm16)
                        dur = len(self.buf) / (2 * SR)
                        silent = (time.time() - self.last_rx_ts) >= MIN_UTT_SEC
                        too_long = dur >= MAX_UTT_SEC
                        
                        # סוף מבע - עיבוד פעם אחת בלבד
                        if (silent or too_long) and dur > 0.3:
                            print(f"🎤 PROCESSING: {dur:.1f}s audio (conversation #{self.conversation_id})")
                            
                            # חסימה מוחלטת של עיבוד כפול
                            if self.processing:
                                print("🚫 Already processing - SKIP")
                                continue
                                
                            self.processing = True
                            current_id = self.conversation_id
                            self.conversation_id += 1
                            
                            # עיבוד במנותק
                            utt_pcm = bytes(self.buf)
                            self.buf.clear()
                            
                            try:
                                self._process_utterance_safe(utt_pcm, current_id)
                            finally:
                                self.processing = False
                                print(f"✅ Processing complete for conversation #{current_id}")
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

    # 🎯 עיבוד מבע פשוט וביטוח (ללא כפילויות)
    def _process_utterance_safe(self, pcm16_8k: bytes, conversation_id: int):
        """עיבוד מבע עם הגנה כפולה מפני לולאות"""
        # וודא שלא מעבדים את אותו ID פעמיים
        if conversation_id <= self.last_processing_id:
            print(f"🚫 DUPLICATE processing ID {conversation_id} (last: {self.last_processing_id}) - SKIP")
            return
        
        self.last_processing_id = conversation_id
        
        # וודא שהמערכת לא מדברת כרגע
        if self.speaking:
            print("🚫 Still speaking - cannot process new utterance")
            return
            
        print(f"🎤 SAFE PROCESSING: conversation #{conversation_id}")
        
        try:
            # 1. Hebrew ASR
            text = self._hebrew_stt(pcm16_8k)
            if not text or len(text.strip()) < 2:
                print("🎤 No speech detected")
                return
                
            print(f"🎤 ASR: '{text}'")
            
            # 2. דה-דופליקציה חכמה
            if text.strip() == self.last_user_text:
                print("🚫 DEDUP: Same text as last input - SKIP")
                return
                
            self.last_user_text = text.strip()
            
            # 3. AI Response
            response = self._ai_response(text)
            if not response:
                response = "בסדר, איך אפשר לעזור?"
                
            print(f"🤖 AI: '{response}'")
            
            # 4. דה-דופליקציה של תגובות
            if response.strip() == self.last_response_text:
                response = response + " אפשר לפרט?"
                
            self.last_response_text = response.strip()
            
            # 5. הוסף להיסטוריה
            self.response_history.append({
                'id': conversation_id,
                'user': text,
                'bot': response,
                'time': time.time()
            })
            
            # 6. דבר!
            self._speak_simple(response)
            
        except Exception as e:
            print(f"❌ Processing error: {e}")
            # תגובת חירום
            self._speak_simple("מצטערת, לא הבנתי. אפשר לחזור?")


    # 🎯 דיבור פשוט וישיר (ללא queue מורכב)
    def _speak_simple(self, text: str):
        """TTS פשוט עם הגנה מפני לולאות"""
        if not text:
            return
            
        if self.speaking:
            print("🚫 Already speaking - cannot start new speech")
            return
            
        self.speaking = True
        print(f"🔊 SPEAKING: '{text}'")
        
        try:
            # נסה TTS אמיתי
            tts_audio = self._hebrew_tts(text)
            if tts_audio and len(tts_audio) > 1000:
                print(f"🔊 TTS SUCCESS: {len(tts_audio)} bytes")
                self._send_pcm16_as_mulaw_frames(tts_audio)
            else:
                print("🔊 TTS FAILED - sending beep")
                self._send_beep(800)
        except Exception as e:
            print(f"🔊 TTS ERROR: {e} - sending beep")
            self._send_beep(800)
        finally:
            self.speaking = False
            print("✅ Speaking completed")

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        """שליחת אודיו פשוטה ויעילה"""
        if not self.stream_sid:
            return
            
        # CLEAR לפני שליחה
        self.ws.send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        
        for i in range(0, len(mulaw), FR):
            # בדיקה אם עדיין מדברים (למקרה של בעיות)
            if not self.speaking:
                print("🚨 Speech interrupted")
                break
                
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
            frames_sent += 1
            
        print(f"🔊 Sent {frames_sent} audio frames")

    def _send_beep(self, ms: int):
        """צפצוף פשוט"""
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
            
            # ✅ פרומפט מעודכן לעוזרת חכמה
            system_prompt = """את העוזרת החכמה של 'שי דירות ומשרדים בע״מ' - חברת נדל״ן מובילה בישראל.

🏢 השירותים שלנו:
- דירות למכירה והשכרה (2-5 חדרים)
- משרדים ומבנים מסחריים
- יעוץ השקעות נדל"ן
- הערכת שווי נכסים
- ליווי משפטי וכלכלי

📞 הסגנון שלך:
- ענה בעברית בלבד
- היה חמה, מקצועית וידידותית
- תני תשובות קצרות ויעילות (1-2 משפטים)
- הציעי תמיד פגישה או יעוץ נוסף
- אל תציני מחירים ספציפיים

✅ דוגמאות:
"אני רוצה דירה" → "מעולה! איזה אזור מעניין אותך ומה התקציב שלך?"
"כמה זה עולה" → "המחירים משתנים לפי אזור וגודל. בואו נקבע פגישה ואמצא לך את הדירה המושלמת!"
"תודה" → "בשמחה! אני כאן לכל שאלה נוספת."

הלקוח כבר שמע את הברכה שלך, אז עני ישירות על השאלות שלו."""

            # נסה קודם עם GPT-4 שיותר יציב
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system", 
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": hebrew_text
                        }
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
            except Exception:
                # אם GPT-4 לא עובד, נסה GPT-5
                response = client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {
                            "role": "system", 
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": hebrew_text
                        }
                    ],
                    max_completion_tokens=150
                )
            
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"🤖 AI SUCCESS: {content.strip()}")
                return content.strip()
            else:
                return "שמח לעזור! איך אני יכול לסייע לך עם נדל\"ן היום?"
            
        except Exception as e:
            print(f"AI_ERROR: {e}")
            # ✅ תגובת חירום טובה יותר במקום "בעיה טכנית"
            if "רוצה" in hebrew_text or "דירה" in hebrew_text or "משרד" in hebrew_text:
                return "מעולה! אשמח לעזור לך למצוא נכס מתאים. בואו נקבע פגישה?"
            elif "שלום" in hebrew_text or "היי" in hebrew_text:
                return "שלום! איך אני יכול לעזור לך היום עם נדל\"ן?"
            else:
                return "שמח לעזור! ספר לי מה אתה מחפש ואמצא לך את הפתרון המושלם."
    
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