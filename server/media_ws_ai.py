"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib
# Using Flask-Sock for WebSocket handling  
from simple_websocket import ConnectionClosed
from server.stream_state import stream_registry

SR = 8000
# 🎯 פרמטרים אופטימליים לשיחה טבעיית (מחקר 2025)!
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.3"))        # מהיר יותר כמו בן אדם
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "4.0"))        # קצר יותר למניעת monologues
VAD_RMS = int(os.getenv("VAD_RMS", "70"))                   # רגיש אבל לא יותר מדי
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "150"))  # מהיר יותר - כמו שיחה אמיתית
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "150")) # "נשימה" קצרה יותר
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "250")) # תגובה מהירה יותר
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "750")) # קירור אחרי דיבור
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","8"))  # איזון: 160ms לinterruption טבעיות
THINKING_HINT_MS = int(os.getenv("THINKING_HINT_MS", "800"))       # מהיר יותר
THINKING_TEXT_HE = os.getenv("THINKING_TEXT_HE", "שנייה… בודקת")   # מקצועי יותר
DEDUP_WINDOW_SEC = int(os.getenv("DEDUP_WINDOW_SEC", "14"))        # חלון דה-דופליקציה
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
        self.call_sid = None  # PATCH 3: For watchdog connection
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
        
        # דה-דופליקציה מתקדמת עם hash
        self.last_user_hash = None
        self.last_user_hash_ts = 0.0
        self.last_reply_hash = None
        self.introduced = False
        self.response_history = []       # היסטוריית תגובות
        self.last_tts_end_ts = 0.0
        self.voice_in_row = 0
        self.greeting_sent = False
        self.state = STATE_LISTEN        # מצב נוכחי
        
        # TX Queue for smooth audio transmission
        self.tx_q = queue.Queue(maxsize=4096)
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        
        print("🎯 HUMAN-LIKE CONVERSATION: Natural timing, breathing, refractory period")

    def run(self):
        print(f"🚨 MEDIA_STREAM_HANDLER: mode={self.mode}")
        
        # CRITICAL FIX: Ensure json import is available
        import json
        
        # Write debug to MULTIPLE LOCATIONS for guaranteed persistence
        timestamp = int(time.time())
        debug_files = [
            f"/tmp/ws_handler_debug_{timestamp}.txt",
            f"/tmp/websocket_debug.txt",
            f"/tmp/handler_called.txt",
            f"/home/runner/workspace/handler_debug.txt",
            f"/tmp/HANDLER_WORKS_{timestamp}.txt"
        ]
        
        success_count = 0
        for debug_file in debug_files:
            try:
                with open(debug_file, "w") as f:
                    f.write(f"HANDLER_START: {self.stream_sid} at {time.time()}\n")
                    f.write(f"WEBSOCKET_HANDLER_DEFINITELY_WORKS!\n")
                    f.write(f"CONNECTION_SUCCESSFUL: {timestamp}\n")
                    f.flush()
                success_count += 1
                print(f"✅ Debug written to {debug_file}", flush=True)
            except Exception as e:
                print(f"❌ Failed to write {debug_file}: {e}", flush=True)
        
        print(f"✅ Debug files written: {success_count}/{len(debug_files)}", flush=True)
        
        # PATCH 4: Advanced logging counters
        self.rx_frames = 0
        self.tx_frames = 0
        
        print(f"WS_START sid={self.stream_sid} mode=AI call_sid={self.call_sid}")
        print(f"🎯 CONVERSATION_START: state={self.state} barge_in={BARGE_IN} VAD_RMS={VAD_RMS}")
        
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    break
                evt = json.loads(raw)
                et = evt.get("event")

                if et == "start":
                    # תמיכה בשני פורמטים: Twilio אמיתי ובדיקות
                    if "start" in evt:
                        # Twilio format: {"event": "start", "start": {"streamSid": "...", "callSid": "..."}}
                        self.stream_sid = evt["start"]["streamSid"]
                        self.call_sid = (
                            evt["start"].get("callSid")
                            or (evt["start"].get("customParameters") or {}).get("call_sid")
                        )
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                    self.last_rx_ts = time.time()
                    print(f"WS_START sid={self.stream_sid} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                    
                    # ✅ ברכה חכמה: רק אם אין קול ב-0.8s הראשונות
                    if not self.tx_running:
                        self.tx_running = True
                        self.tx_thread.start()
                    
                    if not self.greeting_sent:
                        def _smart_greet():
                            time.sleep(0.8)  # חכה לראות אם יש קול
                            if ((time.time() - self.last_rx_ts) >= 0.8 and 
                                self.state == STATE_LISTEN and not self.speaking):
                                greet = os.getenv("AI_GREETING_HE", "שלום! מתמחה ממקסימוס נדלן - איך אני יכולה לעזור?")
                                if greet.strip():
                                    print(f"🔊 SMART_GREETING: '{greet}' delay=0.8s")
                                    self._speak_with_breath(greet)
                                    self.greeting_sent = True
                        threading.Thread(target=_smart_greet, daemon=True).start()
                    continue

                if et == "media":
                    self.rx += 1
                    b64 = evt["media"]["payload"]
                    mulaw = base64.b64decode(b64)
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx_ts = time.time()
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    
                    # מדד דיבור/שקט (VAD) - זיהוי קול חזק בלבד
                    rms = audioop.rms(pcm16, 2)
                    
                    # לוגים מתקדמים כל 50 פריימים + PATCH 10
                    if self.rx % 50 == 0:
                        print(f"WS_MEDIA sid={self.stream_sid} rx={self.rx} state={self.state} VAD={rms}/{VAD_RMS}")

                    # דרישה רגישה יותר: קול רגיל מספיק (כמו שיחה טבעיית!)
                    is_strong_voice = rms > (VAD_RMS * 0.5)  # רגיש אבל יציב
                    
                    # 🔍 DEBUG: לוג כל 25 frames עם RMS ומצב מערכת
                    if self.rx % 25 == 0:
                        print(f"📊 AUDIO_DEBUG: Frame #{self.rx}, RMS={rms}, VAD_threshold={VAD_RMS * 0.5}, Voice={is_strong_voice}, State={self.state}, Speaking={self.speaking}, Processing={self.processing}, Buffer_size={len(self.buf)}")
                        # תדפיס גם כמה אודיו נאסף
                        if len(self.buf) > 0:
                            print(f"   📊 AUDIO_ACCUMULATED: {len(self.buf)/(2*SR):.1f}s duration")
                        # זמן שקט
                        silence_time = (time.time() - self.last_rx_ts) if hasattr(self, 'last_rx_ts') else 0
                        print(f"   🔇 SILENCE_TIME: {silence_time:.2f}s")  
                    
                    # ספירת פריימים רצופים של קול חזק בלבד
                    if is_strong_voice:
                        self.voice_in_row += 1
                    else:
                        self.voice_in_row = max(0, self.voice_in_row - 2)  # קיזוז מהיר לרעשים

                    # 🚨 BARGE-IN מתקדם: עצור מיד כשמדברים מעל הבוט (מחקר 2025)
                    if self.speaking and BARGE_IN and self.voice_in_row >= BARGE_IN_VOICE_FRAMES:
                        print(f"🚨 NATURAL BARGE-IN! User interrupting (RMS={rms}) after {self.voice_in_row} frames (160ms)")
                        self._interrupt_speaking()
                        # נקה הכל ותן למשתמש לדבר
                        self.buf.clear()
                        self.processing = False  # עצור גם עיבוד
                        self.state = STATE_LISTEN
                        print("🎤 USER TURN - Bot listening naturally")
                        # הוסף הודעה קצרה באודיו שהבוט הפסיק לדבר
                        try:
                            self.tx_q.put_nowait({"type": "clear"})
                        except:
                            pass
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
                        
                        # סוף-מבע אדפטיבי: מהיר למבעים קצרים (כמו שיחה אמיתית)
                        min_sil = MIN_UTT_SEC if dur > 1.0 else max(0.25, MIN_UTT_SEC - 0.08)
                        silent = ((time.time() - self.last_rx_ts) >= min_sil) and \
                                 ((time.time() - self.last_rx_ts) >= (VAD_HANGOVER_MS/1000.0))
                        too_long = dur >= MAX_UTT_SEC
                        
                        # 🎯 סוף מבע - רק אחרי דממה אמיתית או זמן יותר מדי
                        if (silent or too_long) and dur > 0.28:
                            print(f"🎤 PROCESSING: {dur:.1f}s audio (conversation #{self.conversation_id})")
                            print(f"🔍 AUDIO_INFO: Buffer={len(self.buf)} bytes, Duration={dur:.1f}s, Silent={silent}, TooLong={too_long}")
                            
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
            # סגירת TX thread
        self.tx_running = False
        try:
            self.tx_q.put_nowait({"type": "end"})
        except:
            pass
        print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    def _interrupt_speaking(self):
        """עצירה מיידית של דיבור הבוט (BARGE-IN משופר)"""
        if not self.speaking:
            return
            
        print("🚨 BARGE-IN: interrupt")
        self.speaking = False
        
        # נקה את תור השידור
        try:
            while not self.tx_q.empty():
                self.tx_q.get_nowait()
        except:
            pass
            
        # שלח CLEAR לטוויליו
        try:
            self.tx_q.put_nowait({"type": "clear"})
        except:
            pass
        
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
            # PATCH 6: Safe ASR - never leaves empty
            try:
                text = self._hebrew_stt(pcm16_8k) or ""
                print(f"ASR_TEXT: {text}")
            except Exception as e:
                print("ASR_ERR:", e)
                text = ""
            
            if not text.strip():
                text = "אפשר לחזור על זה במשפט קצר?"
            print("ASR_TEXT:", text)
            
            # PATCH 6: Anti-duplication on user text (14s window)
            uh = zlib.crc32(text.strip().encode("utf-8"))
            if (self.last_user_hash == uh and 
                (time.time() - self.last_user_hash_ts) <= DEDUP_WINDOW_SEC):
                print("DEDUP user → ignore")
                self.processing = False
                self.state = STATE_LISTEN
                return
            self.last_user_hash, self.last_user_hash_ts = uh, time.time()
            
            # 3. AI Response - БЕЗ micro-ack! תן לה לחשוב בשקט
            started_at = time.time()
            
            # ✅ השתמש בפונקציה המתקדמת עם מתמחה והמאגר הכולל!
            reply = self._ai_response(text)
            
            # PATCH 6: Anti-duplication bot reply
            rh = zlib.crc32(reply.strip().encode("utf-8"))
            if self.last_reply_hash == rh:
                reply = "הבנתי. תרצה שאפרט או להתקדם?"
                rh = zlib.crc32(reply.encode("utf-8"))
            self.last_reply_hash = rh
            
            # 5. הוסף להיסטוריה
            self.response_history.append({
                'id': conversation_id,
                'user': text,
                'bot': reply,
                'time': time.time()
            })
            
            # PATCH 6: Always speak something
            self._speak_simple(reply)
            
        except Exception as e:
            print(f"❌ CRITICAL Processing error: {e}")
            print(f"   Text was: '{text}' ({len(text)} chars)")
            # ✅ תגובת חירום מפורטת ומועילה
            self.state = STATE_SPEAK
            emergency_response = "מצטערת, לא שמעתי טוב בגלל החיבור. אני מתמחה ממקסימוס נדל\"ן ויש לי דירות מדהימות במרכז. בואו נתחיל מחדש - איזה סוג נכס אתה מחפש ובאיזה אזור?"
            self._speak_with_breath(emergency_response)
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
                
            # נסה TTS אמיתי עם גיבוי חכם
            if len(text) > 150:  # אם הטקסט ארוך מדי - קצר אותו
                text = text[:150].rsplit(' ', 1)[0] + '.'
                print(f"🔪 TTS_SHORTENED: {text}")
            
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
                
                # לוגים מתקדמים כל 50 פריימי שידור + PATCH 10
                if self.tx % 50 == 0:
                    elapsed = time.time() - self.last_tts_end_ts
                    print(f"WS_TX sid={self.stream_sid} tx={self.tx} frames_sent={frames_sent}/{total_frames} elapsed={elapsed:.1f}s")
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
    
    def _beep_pcm16_8k(self, ms: int) -> bytes:
        """יצירת צפצוף PCM16 8kHz"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        return bytes(out)
    
    def _hebrew_stt(self, pcm16_8k: bytes) -> str:
        """Hebrew Speech-to-Text using OpenAI Whisper"""
        try:
            from server.services.lazy_services import get_openai_client
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
                client = get_openai_client()
                if not client:
                    print("❌ OpenAI client not available for STT")
                    return ""
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
            from server.services.lazy_services import get_openai_client
            client = get_openai_client()
            if not client:
                print("❌ OpenAI client not available for AI response")
                return "מצטער, יש בעיה טכנית."
            
            # 🎯 היסטוריה של שיחות למניעת חזרות
            if not hasattr(self, 'conversation_history'):
                self.conversation_history = []
            
            # 🚫 מנע לולאות - בדוק אם זה אותה שאלה או תגובה זהה מאוחרת
            if len(self.conversation_history) >= 2:
                last_two = self.conversation_history[-2:]
                # בדוק אם 2 התגובות האחרונות שלנו זהות
                if (last_two[0]['bot'] == last_two[1]['bot'] and 
                    last_two[0]['bot'].count("דיזנגוף") > 0):
                    print(f"🚫 BOT LOOP DETECTED - same response repeated!")
                    return "איזה אזור מעניין אותך יותר?"
                    
                # בדוק אם המשתמש חוזר על אותה שאלה
                if last_two[-1]['user'].strip() == hebrew_text.strip():
                    print(f"🚫 USER LOOP DETECTED: Same input repeated")
                    return "בואי ננסה משהו אחר - איזה תקציב יש לך?"
                    
            # 📜 הקשר מהיסטוריה (להבנה טובה יותר)
            history_context = ""
            if self.conversation_history:
                recent = self.conversation_history[-2:]  # 2 אחרונים
                history_context = "הקשר שיחה: "
                for turn in recent:
                    history_context += f"לקוח אמר: '{turn['user'][:40]}' ענינו: '{turn['bot'][:40]}' | "
            
            # ✅ פרומפט מאוזן לשיחה מציאותית (לא קצר מדי!)
            smart_prompt = f"""את מתמחה ממקסימוס נדלן עם 8 שנות ניסיון במרכז הארץ.

דירות זמינות עכשיו:
• תל אביב דיזנגוף 150 - 3 חדרים, 85 מ"ר, 7,500₪/חודש
• רמת גן הבורסה - 4 חדרים, 95 מ"ר, 8,200₪/חודש  
• פלורנטין - 2 חדרים, 65 מ"ר, 6,800₪/חודש
• גבעתיים הרצל - 3.5 חדרים, 90 מ"ר, 7,800₪/חודש

כללי שיחה מציאותית:
- תני תגובות של 30-50 מילים (לא קצר מדי!)
- עני ישירות על השאלה שנשאלת
- תהיי מעניינת ומקצועית
- הציעי דירות ספציפיות עם פרטים
- שאלי שאלות ממוקדות לקידום הלקוח
- אל תחזרי על "תודה" או "שמחתי לעזור"

{history_context}

הלקוח אומר: "{hebrew_text}"
תגובה מקצועית ומעניינת:"""

            # ✅ GPT-4 יציב ומהיר עם timeout לשיחה חיה!
            import asyncio
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": smart_prompt},
                        {"role": "user", "content": hebrew_text}
                    ],
                    max_tokens=150,           # ✅ תשובות מאוזנות (30-50 מילים)  
                    temperature=0.7,          # טבעי אבל עקבי
                    frequency_penalty=0.5,    # מנע חזרות חזקות
                    presence_penalty=0.3,     # מגוון בביטויים
                    timeout=3.0               # מקס 3 שניות לתגובה מהירה
                )
            except Exception as e:
                print(f"⏰ AI timeout/error ({e}) - using quick fallback")
                return "רגע, אני בודקת... איזה אזור מעניין אותך?"
            
            content = response.choices[0].message.content
            if content and content.strip():
                ai_answer = content.strip()
                
                # ✅ הגבלת אורך תגובה מאוזנת (לא קצר מדי!)
                if len(ai_answer) > 200:  # מקס 200 תווים = ~40 מילים בעברית
                    # קצר לתחילת משפט שלם
                    sentences = ai_answer.split('.')
                    if len(sentences) > 1:
                        ai_answer = sentences[0] + '.'
                    else:
                        ai_answer = ai_answer[:200].rsplit(' ', 1)[0]
                    print(f"🔪 SHORTENED: {len(content)} → {len(ai_answer)} chars")
                
                # ✅ מנע תגובות עם חזרות או "דיזנגוף" קבועה
                if (ai_answer.count("תודה") > 0 or "שמחתי לעזור" in ai_answer or 
                    "דיזנגוף" in ai_answer.lower() or "תמיד פה לעזור" in ai_answer):
                    # תחליף בשאלה מעניינת
                    ai_answer = "איזה סוג דירה אתה מחפש?"
                    print(f"🚫 BLOCKED REPETITIVE/GENERIC: Using fresh question instead")
                
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
                # ✅ תגובות חירום מאוזנות ומועילות
                if "תודה" in hebrew_text or "ביי" in hebrew_text:
                    return "תודה רבה! אני כאן לכל שאלה - מתמחה ממקסימוס נדלן"
                elif "שלום" in hebrew_text:
                    return "שלום וברוכים הבאים! מתמחה ממקסימוס נדלן. יש לי דירות מעולות במרכז הארץ - איך אני יכולה לעזור?"
                elif "דירה" in hebrew_text:
                    return "מעולה! יש לי מבחר גדול במרכז. איזה אזור מעניין אותך - תל אביב, רמת גן או גבעתיים? וכמה חדרים אתה צריך?"
                elif "משרד" in hebrew_text:
                    return "יש לי משרדים נהדרים במרכז! איזה גודל משרד אתה מחפש ובאיזה אזור - תל אביב או רמת גן?"
                elif any(word in hebrew_text for word in ["מחיר", "כמה", "עולה"]):
                    return "המחירים שלי נעים בין 6,800 ל-8,200 שקל לחודש. איזה אזור מעניין אותך ומה התקציב שלך?"
                elif any(word in hebrew_text for word in ["תל אביב", "דיזנגוף"]):
                    return "בדיזנגוף 150 יש לי דירת 3 חדרים מושלמת, 85 מ״ר, 7,500 שקל. רוצה לשמוע פרטים?"
                else:
                    return "לא הבנתי לגמרי - תוכל לחזור על השאלה? אני כאן לעזור עם דירות במרכז הארץ"
            
        except Exception as e:
            print(f"AI_ERROR: {e} - Using emergency responses")
            # תגובות חירום מקצועיות עם הצעות קונקרטיות
            print(f"🚨 AI_ERROR fallback for: '{hebrew_text}'")
            
            if "תודה" in hebrew_text or "ביי" in hebrew_text:
                return "להתראות!"
            elif "שלום" in hebrew_text:
                return "שלום! איך אני יכולה לעזור?"
            elif "דירה" in hebrew_text:
                return "איזה אזור מעניין אותך?"
            elif any(word in hebrew_text for word in ["תל אביב", "דיזנגוף", "פלורנטין", "נווה צדק"]):
                return "כמה חדרים אתה צריך בתל אביב?"
            elif any(word in hebrew_text for word in ["רמת גן", "גבעתיים"]):
                return "איזה תקציב מתאים לך?"
            elif any(word in hebrew_text for word in ["2", "3", "4", "חדרים", "חדר"]):
                return "איזה תקציב יש לך?"
            elif any(word in hebrew_text for word in ["שקל", "אלף", "תקציב", "מחיר", "7000", "8000"]):
                return "רוצה לשמוע על הדירות?"
            elif "משרד" in hebrew_text:
                return "איזה גודל משרד אתה מחפש?"
            elif any(word in hebrew_text for word in ["פגישה", "צפייה", "לראות", "ביקור"]):
                return "מתי נוח לך?"
            else:
                return "לא הבנתי - תוכל לחזור?"
    
    def _hebrew_tts(self, text: str) -> bytes | None:
        """Hebrew Text-to-Speech using Google Cloud TTS"""
        try:
            print(f"🔊 TTS_START: Generating Hebrew TTS for '{text[:50]}...' (length: {len(text)} chars)")
            from server.services.lazy_services import get_tts_client
            from google.cloud import texttospeech
            
            client = get_tts_client()
            if not client:
                print("❌ TTS client not available")
                return None
            
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
            
            print(f"✅ TTS_SUCCESS: Generated {len(response.audio_content)} bytes of audio ({len(response.audio_content)/16000:.1f}s estimated)")
            return response.audio_content
            
        except Exception as e:
            print(f"❌ TTS_CRITICAL_ERROR: {e}")
            print(f"   Text was: '{text}'")
            print(f"   Check Google Cloud credentials!")
            return None
    
    def _tx_loop(self):
        """TX Queue loop for smooth audio transmission"""
        while self.tx_running:
            try:
                item = self.tx_q.get(timeout=0.5)
            except queue.Empty:
                continue
            
            if item.get("type") == "end":
                break
            if item.get("type") == "clear" and self.stream_sid:
                self.ws.send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
                continue
            if item.get("type") == "media":
                self.ws.send(json.dumps({
                    "event": "media", 
                    "streamSid": self.stream_sid,
                    "media": {"payload": item["payload"]}
                }))
                continue
            if item.get("type") == "mark":
                self.ws.send(json.dumps({
                    "event": "mark", 
                    "streamSid": self.stream_sid,
                    "mark": {"name": item.get("name", "mark")}
                }))
    
    def _speak_with_breath(self, text: str):
        """דיבור עם נשימה אנושית ו-TX Queue - תמיד משדר משהו"""
        if not text:
            return
            
        self.speaking = True
        self.state = STATE_SPEAK
        
        try:
            # נשימה אנושית (220-360ms)
            breath_delay = random.uniform(RESP_MIN_DELAY_MS/1000.0, RESP_MAX_DELAY_MS/1000.0)
            time.sleep(breath_delay)
            
            # clear + שידור
            if self.stream_sid:
                self.tx_q.put_nowait({"type": "clear"})
            
            # נסה TTS אמיתי
            pcm = None
            try:
                pcm = self._hebrew_tts(text)
            except Exception as e:
                print("TTS_ERR:", e)
                
            if not pcm or len(pcm) < 400:
                print("🔊 TTS FAILED - sending beep")
                pcm = self._beep_pcm16_8k(300)  # צפצוף 300ms
            else:
                print(f"🔊 TTS SUCCESS: {len(pcm)} bytes")
            
            # שלח את האודיו
            if pcm:
                self._send_pcm16_as_mulaw_frames(pcm)
            time.sleep(breath_delay)
            print(f"💨 HUMAN BREATH: {breath_delay*1000:.0f}ms")
            
            # TTS
            pcm = None
            try:
                pcm = self._hebrew_tts(text)
            except Exception as e:
                print(f"TTS_ERR: {e}")
            
            if not pcm or len(pcm) < 400:
                # אודיו חירום - צפצוף
                pcm = self._beep_pcm16_8k_v2(300)
            
            # שלח דרך TX Queue
            if self.stream_sid:
                self.tx_q.put_nowait({"type": "clear"})
            
            # המר ל-µ-law ושלח ב-20ms chunks
            mulaw = audioop.lin2ulaw(pcm, 2)
            FR = 160  # 20ms @ 8kHz
            
            for i in range(0, len(mulaw), FR):
                if not self.speaking:  # אם נפסק באמצע
                    break
                    
                chunk = mulaw[i:i+FR]
                if len(chunk) < FR:
                    break
                    
                b64 = base64.b64encode(chunk).decode("ascii")
                self.tx_q.put_nowait({"type": "media", "payload": b64})
                self.tx += 1
            
            # סיום
            self.tx_q.put_nowait({"type": "mark", "name": "tts_done"})
            
        finally:
            self.speaking = False
            self.last_tts_end_ts = time.time()
            self.state = STATE_LISTEN
    
    def _beep_pcm16_8k_v2(self, ms: int) -> bytes:
        """יצירת צפצוף PCM16 8kHz"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        
        for n in range(samples):
            val = int(amp * math.sin(2 * math.pi * 440 * n / SR))
            out.extend(val.to_bytes(2, "little", signed=True))
            
        return bytes(out)