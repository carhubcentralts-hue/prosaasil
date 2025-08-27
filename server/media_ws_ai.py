"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random
from simple_websocket import ConnectionClosed

SR = 8000
# 🎯 פרמטרים מעודכנים לשיחה אנושית מושלמת!
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.55"))       # שקט לסוף-מבע (הואץ ל-0.55s)
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "6.0"))        # חיתוך בטיחות
VAD_RMS = int(os.getenv("VAD_RMS", "210"))                  # סף דיבור רגיש מעט
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "180"))  # Hangover אחרי שקט
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "280")) # "נשימה" לפני דיבור
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "420"))
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "850")) # קירור אחרי דיבור
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","10")) # יותר סבלני - 200ms
THINKING_HINT_MS = int(os.getenv("THINKING_HINT_MS", "2000"))     # רק אם LLM תקוע יותר מ-2s
THINKING_TEXT_HE = os.getenv("THINKING_TEXT_HE", "רגע...")         # קצר יותר
LLM_NATURAL_STYLE = True  # תגובות טבעיות לפי השיחה

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
        self.last_tts_end_ts = 0.0
        self.voice_in_row = 0
        self.greeting_sent = False
        self.state = STATE_LISTEN        # מצב נוכחי
        
        print("🎯 HUMAN-LIKE CONVERSATION: Natural timing, breathing, refractory period")

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
                    
                    # ברכה מיידית רק אם שקט
                    if not self.greeting_sent:
                        def _maybe_greet():
                            time.sleep(0.3)  # זמן מינימלי לזיהוי קול
                            # אם במשך 0.3s שקט מוחלט:
                            if (time.time() - self.last_rx_ts) >= 0.3 and not self.speaking:
                                greet = os.getenv("AI_GREETING_HE", "שלום! אני מתחה ממקסימוס נדלן. יש לי דירות מדהימות במרכז. איך אפשר לעזור?")
                                print(f"🔊 IMMEDIATE GREETING: {greet}")
                                self._speak_simple(greet)
                                self.greeting_sent = True
                        threading.Thread(target=_maybe_greet, daemon=True).start()
                    continue

                if et == "media":
                    self.rx += 1
                    b64 = evt["media"]["payload"]
                    mulaw = base64.b64decode(b64)
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx_ts = time.time()

                    # מדד דיבור/שקט (VAD) - זיהוי קול חזק בלבד
                    rms = audioop.rms(pcm16, 2)
                    # דרישה מחמירה פחות: קול חייב להיות חזק פי 1.3 מהרגיל (הקל!)
                    is_strong_voice = rms > (VAD_RMS * 1.3)  
                    
                    # ספירת פריימים רצופים של קול חזק בלבד
                    if is_strong_voice:
                        self.voice_in_row += 1
                    else:
                        self.voice_in_row = max(0, self.voice_in_row - 2)  # קיזוז מהיר לרעשים

                    # 🚨 BARGE-IN חכם: רק עם קול חזק ויציב 
                    if self.speaking and BARGE_IN and self.voice_in_row >= BARGE_IN_VOICE_FRAMES:
                        print(f"🚨 STRONG BARGE-IN! User speaking loudly (RMS={rms}) for {self.voice_in_row} frames!")
                        self._interrupt_bot_speech()
                        # נקה הכל ותן למשתמש לדבר
                        self.buf.clear()
                        self.processing = False  # עצור גם עיבוד
                        print("🎤 USER HAS THE FLOOR - Bot completely silent")
                        continue
                    
                    # אם המערכת מדברת ואין הפרעה - נקה קלט
                    if self.speaking:
                        self.buf.clear()
                        continue
                    
                    # 🎯 איסוף אודיו עם זיהוי דממה נכון + חלון רפרקטורי
                    if not self.processing:
                        # מתעלמים מנשימות/רחש מיד אחרי שהבוט דיבר (חלון קירור)
                        if (time.time() - self.last_tts_end_ts) < (REPLY_REFRACTORY_MS/1000.0):
                            continue
                            
                        self.buf.extend(pcm16)
                        dur = len(self.buf) / (2 * SR)
                        
                        # סוף-מבע אדפטיבי: מהיר למבעים קצרים
                        min_sil = MIN_UTT_SEC if dur > 1.2 else max(0.35, MIN_UTT_SEC - 0.12)
                        silent = ((time.time() - self.last_rx_ts) >= min_sil) and \
                                 ((time.time() - self.last_rx_ts) >= (VAD_HANGOVER_MS/1000.0))
                        too_long = dur >= MAX_UTT_SEC
                        
                        # 🎯 סוף מבע - רק אחרי דממה אמיתית או זמן יותר מדי
                        if (silent or too_long) and dur > 0.5:
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

    def _interrupt_bot_speech(self):
        """עצירה מיידית של דיבור הבוט (BARGE-IN)"""
        if not self.speaking:
            return
            
        print("🚨 INTERRUPTING BOT SPEECH - User wants to talk!")
        self.speaking = False
        
        # שלח CLEAR לטוויליו לעצור את האודיו מיד
        if self.stream_sid:
            try:
                self.ws.send(json.dumps({
                    "event": "clear", 
                    "streamSid": self.stream_sid
                }))
                print("🔇 CLEAR sent to Twilio - bot speech stopped")
            except Exception as e:
                print(f"Error sending CLEAR: {e}")
        
        print("✅ Bot is now silent - user can speak")

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
        self.state = STATE_THINK  # מעבר למצב חשיבה
        
        text = ""  # initialize to avoid unbound variable
        try:
            # 1. Hebrew ASR
            text = self._hebrew_stt(pcm16_8k)
            if not text or len(text.strip()) < 2:
                print("🎤 No speech detected")
                return
                
            print(f"🎤 ASR SUCCESS: '{text}' ({len(text)} chars)")
            
            # לוג חשוב - תמלול עבר!
            if not text or len(text) < 3:
                print("❌ STT returned empty or too short")
                return
            
            # 2. דה-דופליקציה חכמה
            if text.strip() == self.last_user_text:
                print("🚫 DEDUP: Same text as last input - SKIP")
                return
                
            self.last_user_text = text.strip()
            
            # 3. AI Response עם micro-ack אם נדרש
            started_at = time.time()
            
            def maybe_hint():
                time.sleep(THINKING_HINT_MS / 1000.0)  # חכה 2 שניות
                if hasattr(self, 'state') and self.state == STATE_THINK and not self.speaking:
                    print(f"🤔 MICRO-ACK: LLM really stuck after {THINKING_HINT_MS/1000}s, sending brief hint")
                    self._speak_simple(THINKING_TEXT_HE)
                    
            threading.Thread(target=maybe_hint, daemon=True).start()
            
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
            self.state = STATE_SPEAK  # מעבר למצב דיבור
            self._speak_simple(response)
            self.state = STATE_LISTEN  # חזרה להאזנה
            
        except Exception as e:
            print(f"❌ CRITICAL Processing error: {e}")
            print(f"   Text was: '{text}' ({len(text)} chars)")
            # תגובת חירום חזקה
            self.state = STATE_SPEAK
            self._speak_simple("מצטערת, לא הבנתי. אפשר לחזור?")
            self.state = STATE_LISTEN


    # 🎯 דיבור פשוט וישיר (ללא queue מורכב)
    def _speak_simple(self, text: str):
        """TTS פשוט עם הגנה מפני לולאות + נשימה אנושית"""
        if not text:
            return
            
        if self.speaking:
            print("🚫 Already speaking - cannot start new speech")
            return
            
        self.speaking = True
        print(f"🔊 SPEAKING: '{text}'")
        
        try:
            # "נשימה" אנושית לפני תחילת דיבור (נותן תחושת טבעיות)
            try:
                time.sleep(random.uniform(RESP_MIN_DELAY_MS/1000.0, RESP_MAX_DELAY_MS/1000.0))
            except Exception:
                pass
                
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
            self.last_tts_end_ts = time.time()
            print("✅ Speaking completed")

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        """שליחת אודיו עם יכולת עצירה באמצע (BARGE-IN)"""
        if not self.stream_sid or not pcm16_8k:
            return
            
        # CLEAR לפני שליחה
        self.ws.send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        total_frames = len(mulaw) // FR
        
        print(f"🔊 Starting audio transmission: {total_frames} frames ({total_frames * 20}ms)")
        
        for i in range(0, len(mulaw), FR):
            # 🚨 בדיקה קריטית: האם עדיין צריך לדבר?
            if not self.speaking:
                print(f"🚨 BARGE-IN detected! Stopped at frame {frames_sent}/{total_frames}")
                # שלח CLEAR נוסף למקרה הצורך
                self.ws.send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
                break
                
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                # הגענו לסוף - זה תקין
                break
                
            payload = base64.b64encode(chunk).decode("ascii")
            try:
                self.ws.send(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload}
                }))
                self.tx += 1
                frames_sent += 1
            except Exception as e:
                print(f"❌ Error sending frame {frames_sent}: {e}")
                break
        
        if self.speaking:
            print(f"✅ Complete audio sent: {frames_sent}/{total_frames} frames")
        else:
            print(f"⚠️ Audio interrupted: {frames_sent}/{total_frames} frames sent")

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
            print(f"❌ STT_CRITICAL_ERROR: {e}")
            print(f"   Audio size: {len(pcm16_8k)} bytes")
            print(f"   Duration: {len(pcm16_8k)/(2*8000):.1f}s")
            return ""
    
    def _ai_response(self, hebrew_text: str) -> str:
        """Generate NATURAL Hebrew AI response - exactly what the conversation needs!"""
        try:
            import openai
            client = openai.OpenAI()
            
            # 🎯 היסטוריה של שיחות למניעת חזרות
            if not hasattr(self, 'conversation_history'):
                self.conversation_history = []
            
            # 🚫 מנע לולאות - בדוק אם זה אותה שאלה בדיוק
            if len(self.conversation_history) > 0:
                last_turn = self.conversation_history[-1]
                if last_turn['user'].strip() == hebrew_text.strip():
                    print(f"🚫 LOOP DETECTED: Same input repeated - BLOCK!")
                    return "יש לך שאלה אחרת?"
                    
            # 📜 הקשר מהיסטוריה (להבנה טובה יותר)
            history_context = ""
            if self.conversation_history:
                recent = self.conversation_history[-2:]  # 2 אחרונים
                history_context = "הקשר שיחה: "
                for turn in recent:
                    history_context += f"לקוח אמר: '{turn['user'][:40]}' ענינו: '{turn['bot'][:40]}' | "
            
            # ✅ פרומפט מקצועי מלא עם מאגר דירות אמיתי
            smart_prompt = f"""את מתחה, נציגת מקסימוס נדל"ן המומחית. 

== המידע שלך ==
שם: מתחה ממקסימוס נדל"ן
תחום: נדלן מרכז הארץ (תל אביב, רמת גן, גבעתיים, חולון, בת ים)
ניסיון: 8 שנים בנדלן
מומחיות: דירות למכירה ולהשכרה, ייעוץ השקעות

== מאגר הדירות הזמינות במרכז ==
1. תל אביב, רחוב דיזנגוף 150 - 3 חדרים, 75 מ"ר, קומה 4, 7,500₪/חודש
2. רמת גן, שדרות ירושלים 45 - 4 חדרים, 90 מ"ר, קומה 2, 8,200₪/חודש  
3. תל אביב, אזור פלורנטין - 2 חדרים, 60 מ"ר, קומת קרקע, 6,800₪/חודש
4. גבעתיים, רחוב הרצל 12 - 3.5 חדרים, 85 מ"ר, קומה 3, 7,800₪/חודש
5. תל אביב, שכונת נווה צדק - 3 חדרים, 70 מ"ר, קומה 5, 8,500₪/חודש
6. חולון, שדרות וייצמן 88 - 4 חדרים, 95 מ"ר, קומה 1, 6,500₪/חודש
7. בת ים, רחוב הנשיא 25 - 3 חדרים, 80 מ"ר, קרוב לים, 6,200₪/חודש
8. רמת גן, אזור הבורסה - 2.5 חדרים, 65 מ"ר, קומה 6, 7,200₪/חודש
9. תל אביב, רחוב רוטשילד 88 - 3 חדרים, 78 מ"ר, משופץ, 9,200₪/חודש
10. גבעתיים, רחוב ויצמן 15 - 4 חדרים, 100 מ"ר, עם חנייה, 8,800₪/חודש

== איך לנהל שיחה מקצועית ==
1. זהי עצמך בהתחלה: "שלום, אני מתחה ממקסימוס נדלן"
2. זהי את הצורך: דירה/משרד, אזור, תקציב, חדרים
3. הציעי דירות מתאימות מהמאגר עם פרטים קונקרטיים
4. שאלי על פגישה לצפייה
5. קבעי זמן או קחי פרטים ליצירת קשר

== דוגמאות למענה מקצועי ==
"יש לי דירת 3 חדרים מדהימה בדיזנגוף 150, 75 מ"ר, 7,500 שקל. רוצה לשמוע פרטים?"
"מעולה! תראה, יש לי בדיוק מה שאתה מחפש ברמת גן, 4 חדרים, 8,200 שקל. אפשר לקבוע צפייה?"

{history_context}

עכשיו הלקוח אומר: "{hebrew_text}"
תני מענה מקצועי עם הצעות קונקרטיות:"""

            # שלח לAI עם הגדרות מותאמות לתגובות מלאות וחמות
            try:
                # נסה GPT-5 עם פרמטרים פשוטים
                response = client.chat.completions.create(
                    model="gpt-5",  # the newest OpenAI model is "gpt-5" which was released August 7, 2025. do not change this unless explicitly requested by the user
                    messages=[
                        {"role": "system", "content": smart_prompt},
                        {"role": "user", "content": hebrew_text}
                    ],
                    max_completion_tokens=150,  # מספיק לתשובה טבעית
                    temperature=1.0            # GPT-5 תומך רק בטמפרטורה 1.0
                )
            except Exception as gpt5_error:
                print(f"GPT-5 failed: {gpt5_error}, trying GPT-4...")
                # נסה GPT-4 כ-fallback
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": smart_prompt},
                        {"role": "user", "content": hebrew_text}
                    ],
                    max_tokens=100,           # קצר יותר אבל מספיק
                    temperature=0.7,          # יותר יציב
                    frequency_penalty=0.5     # פחות קיצוני
                )
            
            content = response.choices[0].message.content
            if content and content.strip():
                ai_answer = content.strip()
                
                print(f"🤖 AI SUCCESS: {ai_answer}")
                
                # 💾 הוסף לhיסטוריה למניעת חזרות
                self.conversation_history.append({
                    'user': hebrew_text.strip(),
                    'bot': ai_answer,
                    'time': time.time()
                })
                
                # 🧹 נקה היסטוריה ישנה (רק 10 אחרונים)
                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-10:]
                    
                return ai_answer
            else:
                print("AI returned empty response, using fallback")
                # אם LLM לא החזיר כלום - תגובות חירום
                if "תודה" in hebrew_text or "ביי" in hebrew_text:
                    return "בהצלחה!"
                elif "שלום" in hebrew_text:
                    return "שלום! אני מתחה ממקסימוס נדלן. מה אתה מחפש?"
                elif "דירה" in hebrew_text:
                    return "באיזה אזור?"
                elif "משרד" in hebrew_text:
                    return "איזה גודל?"
                elif any(word in hebrew_text for word in ["מחיר", "כמה", "עולה"]):
                    return "איזה נכס?"
                else:
                    return "מה אתה מחפש?"
            
        except Exception as e:
            print(f"AI_ERROR: {e} - Using emergency responses")
            # תגובות חירום מקצועיות עם הצעות קונקרטיות
            print(f"🚨 AI_ERROR fallback for: '{hebrew_text}'")
            
            if "תודה" in hebrew_text or "ביי" in hebrew_text:
                return "בהצלחה! תתקשר אליי בכל זמן - מתחה ממקסימוס נדלן"
            elif "שלום" in hebrew_text:
                return "שלום! אני מתחה ממקסימוס נדלן. יש לי דירות מדהימות במרכז. מה אתה מחפש?"
            elif "דירה" in hebrew_text:
                return "מעולה! יש לי 10 דירות זמינות במרכז. איזה אזור מעניין אותך - תל אביב, רמת גן או גבעתיים?"
            elif any(word in hebrew_text for word in ["תל אביב", "דיזנגוף", "פלורנטין", "נווה צדק"]):
                return "יש לי דירות מדהימות בתל אביב! דיזנגוף 150 - 3 חדרים 7,500 שקל, ופלורנטין - 2 חדרים 6,800 שקל. כמה חדרים אתה צריך?"
            elif any(word in hebrew_text for word in ["רמת גן", "גבעתיים"]):
                return "מושלם! ברמת גן יש לי 4 חדרים 8,200 שקל ובגבעתיים 3.5 חדרים 7,800 שקל. איזה תקציב מתאים לך?"
            elif any(word in hebrew_text for word in ["2", "3", "4", "חדרים", "חדר"]):
                return "יש לי בדיוק מה שאתה מחפש! דירה מדהימה במרכז. איזה תקציב יש לך - עד 7 אלף או יותר?"
            elif any(word in hebrew_text for word in ["שקל", "אלף", "תקציב", "מחיר", "7000", "8000"]):
                return "מצוין! יש לי כמה אפשרויות מושלמות. רוצה שאספר לך על הדירות? אפשר גם לקבוע צפייה היום"
            elif "משרד" in hebrew_text:
                return "יש לי גם משרדים מעולים במרכז. איזה אזור ואיזה גודל אתה מחפש?"
            elif any(word in hebrew_text for word in ["פגישה", "צפייה", "לראות", "ביקור"]):
                return "בטח! אני זמינה היום ומחר. מתי נוח לך? אני אכין לך את כל הפרטים"
            else:
                return "מצטערת, לא שמעתי טוב. יש לי דירות מדהימות במרכז - תל אביב, רמת גן וגבעתיים. מה אתה מחפש?"
    
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
                sample_rate_hertz=8000,
                speaking_rate=0.96,  # קצת יותר איטי מהרגיל
                pitch=0.0,           # טון טבעי
                effects_profile_id=["telephony-class-application"]  # אופטימיזציה לטלפון
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