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

        # Rx / Tx counters
        self.rx_frames = 0
        self.tx_frames = 0

        # מצב שיחה - מכונת מצבים מתקדמת
        self.state = STATE_LISTEN
        self.speaking = False
        self.processing = False            # מונע _process_utterance כפול
        self.last_rx_ts = None
        self.buf_pcm16 = bytearray()       # באפר מבע הנוכחי
        self.last_reply_text = None        # מניעת לופים של אותה תשובה
        self.last_user_text = None         # מניעת עיבוד כפול של אותו מבע

        # תור שידור אסינכרוני (אפשר לעצור מיד - BARGE-IN)
        self.tx_q: queue.Queue = queue.Queue(maxsize=4096)
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self.tx_running = False

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
                    print(f"WS_START sid={self.stream_sid} mode={self.mode} state={self.state}")
                    
                    # מפעיל משדר אסינכרוני
                    if not self.tx_running:
                        self.tx_running = True
                        self.tx_thread.start()
                    
                    # ברכה פעם אחת
                    self._speak_text("שלום! אני העוזרת החכמה של שי דירות ומשרדים. איך אני יכולה לעזור לך היום?")
                    continue

                if et == "media":
                    self.rx_frames += 1
                    b64 = evt["media"]["payload"]
                    mulaw = base64.b64decode(b64)
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx_ts = time.time()

                    # מדד דיבור/שקט (VAD)
                    rms = audioop.rms(pcm16, 2)
                    is_voice = rms > VAD_RMS

                    # 🚨 Barge-in: אם הבוט מדבר והאדם התחיל לדבר → לעצור מיד
                    if BARGE_IN and self.state == STATE_SPEAK and is_voice:
                        print(f"🚨 BARGE_IN: User speaking (RMS={rms}) while bot talking - interrupting!")
                        self._interrupt_speaking()
                        self.state = STATE_LISTEN

                    # איסוף מבע רק כשאנחנו במצב האזנה
                    if self.state == STATE_LISTEN and not self.speaking:
                        self.buf_pcm16.extend(pcm16)

                        dur = len(self.buf_pcm16) / (2 * SR)
                        silent_enough = (time.time() - self.last_rx_ts) >= MIN_UTT_SEC
                        too_long = dur >= MAX_UTT_SEC

                        # סוף-מבע: פעם אחת בלבד (processing guard)
                        if (silent_enough or too_long) and dur > 0.3 and not self.processing:
                            print(f"🎤 END-OF-UTTERANCE: {dur:.1f}s audio, state={self.state}")
                            self.processing = True
                            self.state = STATE_THINK
                            utt_pcm = bytes(self.buf_pcm16)
                            self.buf_pcm16.clear()
                            try:
                                self._process_utterance(utt_pcm)
                            finally:
                                self.processing = False
                                # חוזרים להאזנה רק אם לא התחיל דיבור
                                if not self.speaking:
                                    self.state = STATE_LISTEN
                    continue

                if et == "stop":
                    print(f"WS_STOP sid={self.stream_sid} rx={self.rx_frames} tx={self.tx_frames}")
                    break

        except ConnectionClosed:
            print(f"WS_CLOSED sid={self.stream_sid} rx={self.rx_frames} tx={self.tx_frames}")
        except Exception as e:
            print("WS_ERR:", e)
        finally:
            try: 
                self.ws.close()
            except: 
                pass
            # סיום תור השידור
            self.tx_running = False
            try: 
                self.tx_q.put_nowait({"type": "end"})
            except: 
                pass
            print(f"WS_DONE sid={self.stream_sid} rx={self.rx_frames} tx={self.tx_frames}")

    # תור השידור (TX) – 20ms µ-law, עם CLEAR/STOP מיידי
    def _tx_loop(self):
        """מריץ ברקע; כל פריים יוצא בנפרד – מאפשר ברג'-אין מיידי"""
        while self.tx_running:
            try:
                item = self.tx_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if item.get("type") == "end":
                break
            if item.get("type") == "clear":
                # לרוקן באפר נגן אצל Twilio
                if self.stream_sid:
                    self.ws.send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
                continue
            if item.get("type") == "media":
                payload = item["payload"]
                self.ws.send(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload}
                }))
                self.tx_frames += 1
                continue
            if item.get("type") == "mark":
                self.ws.send(json.dumps({"event": "mark", "streamSid": self.stream_sid,
                                         "mark": {"name": item.get("name", "mark")}}))

    # עצירת דיבור (Barge-in) + ניקוי תור
    def _interrupt_speaking(self):
        if not self.speaking:
            return
        print("🚨 BARGE_IN: interrupt speaking")
        self.speaking = False
        self.state = STATE_LISTEN
        # ריקון מיידי של התור
        while not self.tx_q.empty():
            try: 
                self.tx_q.get_nowait()
            except: 
                break
        # CLEAR לנגן
        try: 
            self.tx_q.put_nowait({"type":"clear"})
        except: 
            pass

    # --- מבע → ASR → LLM → TTS ---
    def _process_utterance(self, pcm16_8k: bytes):
        """טיפול במבע - פעם אחת בלבד, בלי דופליקטים"""
        # לא מאפשרים Re-entry
        if self.speaking:
            return
        
        try:
            # 1. Hebrew ASR
            text = self._hebrew_stt(pcm16_8k)
        except Exception as e:
            print("ASR_ERR:", e)
            text = ""

        print(f"ASR_TEXT: '{text}'")
        if not text.strip():
            # תגובה מינימלית או לא להגיב כלל
            return

        # מניעת לופים: אם זהה למבע הקודם בטווח קצר, דלג
        if text.strip() == getattr(self, "last_user_text", None):
            print("DEDUP: same utterance ignored")
            return
        self.last_user_text = text.strip()

        self.state = STATE_THINK

        # תשובה מהמודל
        try:
            reply = self._ai_response(text)
        except Exception as e:
            print("LLM_ERR:", e)
            reply = ""

        if not reply.strip():
            reply = "בסדר, איך אפשר לעזור?"

        # אם זהה לתשובה הקודמת → עדכן קצת כדי לא להישמע תקוע
        if reply.strip() == (self.last_reply_text or ""):
            reply = reply + " תרצה לפרט?"

        self.last_reply_text = reply.strip()
        print(f"LLM_REPLY: '{reply}'")

        # TTS ושידור
        self._speak_text(reply)

    # TTS ושידור 20ms דרך התור החדש
    def _speak_text(self, text: str):
        """TTS ושידור אסינכרוני עם תמיכה ב-Barge-in"""
        if not text:
            return
        
        print(f"🔊 SPEAKING: '{text}'")
        
        # נסה TTS אמיתי
        pcm = None
        try:
            pcm = self._hebrew_tts(text)
        except Exception as e:
            print("TTS_ERR:", e)

        if not pcm or len(pcm) < 1000:
            # Fallback לצפצוף
            pcm = self._beep_pcm16_8k(800)
            print("🔊 Using fallback beep")

        self.speaking = True
        self.state = STATE_SPEAK

        # CLEAR לפני הפריים הראשון
        try: 
            self.tx_q.put_nowait({"type":"clear"})
        except: 
            pass

        # המרה ל-µlaw ושידור פריימים של 20ms
        mulaw = audioop.lin2ulaw(pcm, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        
        for i in range(0, len(mulaw), FR):
            if not self.speaking:  # הופסק בבארג'-אין
                print("🚨 Speaking interrupted by barge-in")
                break
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                break
            b64 = base64.b64encode(chunk).decode("ascii")
            try: 
                self.tx_q.put_nowait({"type":"media", "payload": b64})
                frames_sent += 1
            except queue.Full:
                print("⚠️ TX queue full - breaking")
                break

        # MARK לסיום
        try: 
            self.tx_q.put_nowait({"type":"mark", "name":"tts_done"})
        except: 
            pass

        print(f"🔊 TTS complete: {frames_sent} frames sent")
        self.speaking = False
        self.state = STATE_LISTEN

    # צפצוף פולבאק (אם TTS נפל)
    def _beep_pcm16_8k(self, ms: int) -> bytes:
        """יוצר צפצוף של 440Hz באורך נתון"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        return bytes(out)

    # Legacy function - מוחלף בשידור דרך התור
    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        """Legacy - עכשיו משתמשים ב-_speak_text עם התור החדש"""
        print("⚠️ Using legacy send function - consider updating to new TX queue")
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
            self.tx_frames += 1

    def _send_beep(self, ms: int):
        """Legacy beep - משתמש בשידור דרך התור"""
        beep_audio = self._beep_pcm16_8k(ms)
        self._speak_text("")  # Will use the beep as fallback
    
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