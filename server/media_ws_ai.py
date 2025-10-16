"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib
import builtins

# Override print to always flush (CRITICAL for logs visibility)
_original_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _original_print(*args, **kwargs)
builtins.print = print

# WebSocket ConnectionClosed exception (works with both Flask-Sock and Starlette)
class ConnectionClosed(Exception):
    """WebSocket connection closed"""
    pass

from server.stream_state import stream_registry

SR = 8000
# ✅ FIXED: פרמטרים לפי ההנחיות המקצועיות
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "1.2"))        # ⚡ SPEED: 1.2s במקום 1.5s - תמלול מהיר יותר
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "8.0"))        # ✅ 8.0s - זמן מספיק לתיאור נכסים מפורט
VAD_RMS = int(os.getenv("VAD_RMS", "65"))                   # ✅ פחות רגיש לרעשים - מפחית קטיעות שגויות
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "300"))  # ⚡ SPEED: 300ms במקום 400ms - תגובה מהירה יותר
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "50")) # ⚡ SPEED: 50ms במקום 80ms - תגובה מהירה
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "120")) # ⚡ SPEED: 120ms במקום 200ms - פחות המתנה
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "1500")) # ✅ 1500ms - יותר "קירור" אחרי תגובה
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","40"))  # ✅ 40 frames = ≈800ms קול רציף נדרש לקטיעה
THINKING_HINT_MS = int(os.getenv("THINKING_HINT_MS", "0"))       # בלי "בודקת" - ישירות לעבודה!
THINKING_TEXT_HE = os.getenv("THINKING_TEXT_HE", "")   # אין הודעת חשיבה
DEDUP_WINDOW_SEC = int(os.getenv("DEDUP_WINDOW_SEC", "8"))        # חלון קצר יותר
LLM_NATURAL_STYLE = True  # תגובות טבעיות לפי השיחה

# מכונת מצבים
STATE_LISTEN = "LISTENING"
STATE_THINK  = "THINKING"
STATE_SPEAK  = "SPEAKING"

class MediaStreamHandler:
    def __init__(self, ws):
        self.ws = ws
        self.mode = "AI"  # תמיד במצב AI
        
        # 🔧 תאימות WebSocket - EventLet vs RFC6455 עם טיפול שגיאות
        if hasattr(ws, 'send'):
            self._ws_send_method = ws.send
        else:
            # אם אין send, נסה send_text או כל שיטה אחרת
            self._ws_send_method = getattr(ws, 'send_text', lambda x: print(f"❌ No send method: {x}"))
        
        # 🛡️ Safe WebSocket send wrapper with connection health
        self.ws_connection_failed = False
        self.failed_send_count = 0
        
        def _safe_ws_send(data):
            if self.ws_connection_failed:
                return False  # Don't spam when connection is dead
                
            try:
                self._ws_send_method(data)
                self.failed_send_count = 0  # Reset on success
                return True
            except Exception as e:
                self.failed_send_count += 1
                if self.failed_send_count <= 3:  # Only log first 3 errors
                    print(f"❌ WebSocket send error #{self.failed_send_count}: {e}")
                
                if self.failed_send_count >= 10:  # Increased threshold - After 10 failures, mark as dead
                    self.ws_connection_failed = True
                    print(f"🚨 WebSocket connection marked as FAILED after {self.failed_send_count} attempts")
                
                return False
        
        self._ws_send = _safe_ws_send
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
        
        # ✅ תיקון קריטי: מעקב נפרד אחר קול ושקט
        self.last_voice_ts = 0.0         # זמן הקול האחרון - לחישוב דממה אמיתי
        self.noise_floor = 35.0          # רמת רעש בסיסית
        self.vad_threshold = 35.0        # סף VAD דינמי
        self.is_calibrated = False       # האם כוילרנו את רמת הרעש
        self.calibration_frames = 0      # מונה פריימים לכיול
        self.mark_pending = False        # האם ממתינים לסימון TTS
        self.mark_sent_ts = 0.0          # זמן שליחת סימון
        
        # הגנות Watchdog
        self.processing_start_ts = 0.0   # תחילת עיבוד
        self.speaking_start_ts = 0.0     # תחילת דיבור
        
        # ✅ WebSocket Keepalive למניעת נפילות אחרי 5 דקות
        self.last_keepalive_ts = 0.0     # זמן keepalive אחרון
        self.keepalive_interval = 18.0   # שלח כל 18 שניות
        self.heartbeat_counter = 0       # מונה heartbeat
        
        # TX Queue for smooth audio transmission
        self.tx_q = queue.Queue(maxsize=4096)
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        
        print("🎯 AI CONVERSATION STARTED")
        
        # מאפיינים לזיהוי עסק
        self.business_id = None  # ✅ יזוהה דינמית לפי to_number
        self.phone_number = None
        
        # היסטוריית שיחה למעקב אחר הקשר
        self.conversation_history = []  # רשימה של הודעות {'user': str, 'bot': str}
        
        # ✅ CRITICAL: Track background threads for proper cleanup
        self.background_threads = []

    def run(self):
        # Media stream handler initialized")
        
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
        print(f"🎯 CONVERSATION READY (VAD threshold: {VAD_RMS})")
        
        try:
            while True:
                # COMPATIBILITY: Handle both EventLet and Flask-Sock WebSocket APIs
                raw = None
                try:
                    # Simplified WebSocket handling - no spam logs
                    ws_type = str(type(self.ws))
                    
                    # RFC6455WebSocket-specific handling (EventLet)
                    if 'RFC6455WebSocket' in ws_type:
                        # EventLet RFC6455WebSocket uses wait() method
                        raw = self.ws.wait()
                        # רק ספירה בלי spam
                        self.rx_frames += 1
                    else:
                        # Standard WebSocket APIs
                        if hasattr(self.ws, 'receive'):
                            raw = self.ws.receive()
                        elif hasattr(self.ws, 'recv'):
                            raw = self.ws.recv()
                        elif hasattr(self.ws, 'read_message'):
                            raw = self.ws.read_message()
                        elif hasattr(self.ws, 'receive_data'):
                            raw = self.ws.receive_data()
                        elif hasattr(self.ws, 'read'):
                            raw = self.ws.read()
                        else:
                            print(f"⚠️ Unknown WebSocket type: {type(self.ws)}, available methods: {[m for m in dir(self.ws) if not m.startswith('_')]}", flush=True)
                            raise Exception(f"No compatible receive method found for {type(self.ws)}")
                        
                    if raw is None or raw == '':
                        print("📞 WebSocket connection closed normally", flush=True)
                        break
                        
                    # Handle both string and bytes
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8')
                        
                    evt = json.loads(raw)
                    et = evt.get("event")
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid JSON received: {str(raw)[:100] if raw else 'None'}... Error: {e}", flush=True)
                    continue
                except Exception as e:
                    print(f"⚠️ WebSocket receive error: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Try to continue, might be temporary - don't crash the connection
                    continue

                if et == "start":
                    # תמיכה בשני פורמטים: Twilio אמיתי ובדיקות
                    if "start" in evt:
                        # Twilio format: {"event": "start", "start": {"streamSid": "...", "callSid": "..."}}
                        self.stream_sid = evt["start"]["streamSid"]
                        self.call_sid = (
                            evt["start"].get("callSid")
                            or (evt["start"].get("customParameters") or {}).get("CallSid")
                            or (evt["start"].get("customParameters") or {}).get("call_sid")
                        )
                        
                        # ✅ זיהוי מספרי טלפון מ-customParameters
                        custom_params = evt["start"].get("customParameters", {})
                        self.phone_number = (
                            custom_params.get("From") or
                            custom_params.get("CallFrom") or  
                            custom_params.get("from") or
                            custom_params.get("phone_number")
                        )
                        # ✅ CRITICAL FIX: שמירת to_number למזהה עסק
                        self.to_number = (
                            evt["start"].get("to") or  # ✅ Twilio sends 'to' at start level
                            custom_params.get("To") or
                            custom_params.get("Called") or
                            custom_params.get("to") or
                            custom_params.get("called")
                        )
                        
                        # ✅ DEBUG: הדפסת המידע שמגיע מ-Twilio
                        print(f"🔍 DEBUG TO_NUMBER: evt[start].get('to')={evt['start'].get('to')}, customParams={custom_params}, final to_number={self.to_number}")
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                        self.phone_number = evt.get("from") or evt.get("phone_number")
                        self.to_number = evt.get("to") or evt.get("called")
                        
                    self.last_rx_ts = time.time()
                    self.last_keepalive_ts = time.time()  # ✅ התחל keepalive
                    print(f"🎯 WS_START sid={self.stream_sid} call_sid={self.call_sid} from={self.phone_number} to={getattr(self, 'to_number', 'N/A')} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                    
                    # ✅ CRITICAL: זיהוי עסק וברכה - במקביל לחיסכון זמן!
                    try:
                        from server.app_factory import create_app
                        app = create_app()
                        with app.app_context():
                            self._identify_business_from_phone()
                            # ✅ טעינת ברכה בו-זמנית - חוסך שאילתת DB נוספת!
                            greet = self._get_business_greeting_cached()
                        print(f"✅ עסק וברכה זוהו: business_id={getattr(self, 'business_id', 'NOT SET')}")
                    except Exception as e:
                        print(f"❌ CRITICAL ERROR in business identification: {e}")
                        import traceback
                        traceback.print_exc()
                        self.business_id = 1  # fallback
                        greet = "שלום! איך אפשר לעזור?"
                    
                    # ✅ יצירת call_log מיד בהתחלת שיחה (אחרי זיהוי עסק!)
                    try:
                        if self.call_sid and not hasattr(self, '_call_log_created'):
                            self._create_call_log_on_start()
                            self._call_log_created = True
                    except Exception as e:
                        print(f"⚠️ Call log creation failed (non-critical): {e}")
                    
                    # ✅ ברכה מיידית - בלי השהיה!
                    if not self.tx_running:
                        self.tx_running = True
                        self.tx_thread.start()
                    
                    if not self.greeting_sent:
                        print("🎯 SENDING IMMEDIATE GREETING!")
                        try:
                            self._speak_greeting(greet)  # ✅ פונקציה מיוחדת לברכה ללא sleep!
                            self.greeting_sent = True
                        except Exception as e:
                            print(f"❌ CRITICAL ERROR sending greeting: {e}")
                            import traceback
                            traceback.print_exc()
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
                    
                    # 📊 VAD דינמי משופר עם קליברציה ארוכה יותר והיסטרזיס
                    if not self.is_calibrated and self.calibration_frames < 40:
                        # קליברציה ארוכה יותר: 300-500ms = 15-25 frames, נשתמש ב-40 להיות בטוחים
                        self.noise_floor = (self.noise_floor * self.calibration_frames + rms) / (self.calibration_frames + 1)
                        self.calibration_frames += 1
                        if self.calibration_frames >= 60:
                            # ✅ HEBREW-OPTIMIZED: Balanced threshold for Hebrew speech
                            self.vad_threshold = max(150, self.noise_floor * 5.0 + 100)  # מותאם לעברית - מאזין עד הסוף
                            self.is_calibrated = True
                            print(f"🎛️ VAD CALIBRATED for HEBREW (threshold: {self.vad_threshold:.1f})")
                            
                            # היסטרזיס למניעת ריצוד
                            if not hasattr(self, 'vad_hysteresis_count'):
                                self.vad_hysteresis_count = 0
                            if not hasattr(self, 'last_vad_state'):
                                self.last_vad_state = False
                    
                    # 📊 זיהוי קול משופר עם היסטרזיס ו-Zero-Crossing Rate
                    if self.is_calibrated:
                        # חישוב Zero-Crossing Rate למדידת דיבור רך
                        zero_crossings = 0
                        try:
                            import numpy as np
                            pcm_np = np.frombuffer(pcm16, dtype=np.int16)
                            zero_crossings = np.sum(np.diff(np.sign(pcm_np)) != 0) / len(pcm_np) if len(pcm_np) > 0 else 0
                        except ImportError:
                            # numpy לא מותקן - נשתמש בVAD בסיסי בלבד
                            zero_crossings = 0
                        except:
                            zero_crossings = 0
                        
                        # VAD בסיסי
                        basic_voice = rms > self.vad_threshold
                        
                        # VAD משופר עם Zero-Crossing Rate
                        zcr_voice = zero_crossings > 0.05  # דיבור רך עם הרבה מעברי אפס
                        enhanced_voice = basic_voice or (zcr_voice and rms > self.vad_threshold * 0.6)
                        
                        # היסטרזיס: 100ms = 5 frames למניעת ריצוד
                        if enhanced_voice != self.last_vad_state:
                            self.vad_hysteresis_count += 1
                            if self.vad_hysteresis_count >= 5:  # 100ms היסטרזיס חזק יותר
                                is_strong_voice = enhanced_voice
                                self.last_vad_state = enhanced_voice
                                self.vad_hysteresis_count = 0
                            else:
                                is_strong_voice = self.last_vad_state  # השאר מצב קודם
                        else:
                            is_strong_voice = enhanced_voice
                            self.vad_hysteresis_count = 0
                    else:
                        # לפני קליברציה - VAD חזק יותר לעברית
                        is_strong_voice = rms > 300  # Even higher for Hebrew speech
                    
                    # ✅ FIXED: Update last_voice_ts only with VERY strong voice
                    current_time = time.time()
                    # ✅ EXTRA CHECK: Only if RMS is significantly above threshold
                    if is_strong_voice and rms > (getattr(self, 'vad_threshold', 200) * 1.2):
                        self.last_voice_ts = current_time
                        # Debug only strong voice detection (max once per 3 seconds)
                        if not hasattr(self, 'last_debug_ts') or (current_time - self.last_debug_ts) > 3.0:
                            print(f"🎙️ REAL_VOICE: rms={rms}, threshold={getattr(self, 'vad_threshold', 'uncalibrated')}")
                            self.last_debug_ts = current_time
                    
                    # חישוב דממה אמיתי - מאז הקול האחרון! 
                    # אם אין קול בכלל, דממה = 0 (כדי שלא נתקע)
                    silence_time = (current_time - self.last_voice_ts) if self.last_voice_ts > 0 else 0
                    
                    # ✅ לוגים נקיים - רק אירועים חשובים (לא כל frame)  
                    
                    # ספירת פריימים רצופים של קול חזק בלבד
                    if is_strong_voice:
                        self.voice_in_row += 1
                    else:
                        self.voice_in_row = max(0, self.voice_in_row - 2)  # קיזוז מהיר לרעשים

                    # ⚡ FIXED BARGE-IN: Prevent false interruptions - EXTRA LONG GRACE PERIOD
                    if self.speaking and BARGE_IN:
                        # ✅ CRITICAL: Grace period מאוד ארוך - 4 שניות! היא חייבת לסיים משפטים!
                        grace_period = 4.0  # 4.0 שניות - כמעט כל המשפטים נגמרים תוך 4 שניות
                        time_since_tts_start = current_time - self.speaking_start_ts
                        
                        if time_since_tts_start < grace_period:
                            # Inside grace period - NO barge-in allowed AT ALL
                            continue
                        
                        # ✅ HEBREW BARGE-IN: Very high threshold + longer duration required
                        barge_in_threshold = max(1200, self.noise_floor * 15.0 + 500) if self.is_calibrated else 1500
                        is_barge_in_voice = rms > barge_in_threshold
                        
                        if is_barge_in_voice:
                            self.voice_in_row += 1
                            # ✅ HEBREW SPEECH: Require 1500ms continuous LOUD voice to prevent false interrupts  
                            if self.voice_in_row >= 75:  # 1500ms קול רציף חזק - ממש בטוח שזה הפרעה מכוונת
                                print(f"⚡ BARGE-IN DETECTED (after {time_since_tts_start*1000:.0f}ms)")
                                
                                # ✅ מדידת Interrupt Halt Time
                                interrupt_start = time.time()
                                
                                # ✅ FIXED: רק בצע interrupt, הוא יטפל בכל המצבים
                                self._interrupt_speaking()
                                
                                # ✅ מדידת זמן עצירה
                                halt_time = (time.time() - interrupt_start) * 1000
                                print(f"📊 INTERRUPT_HALT: {halt_time:.1f}ms (target: ≤200ms)")
                                
                                # ✅ מעבר מיידי ל-LISTENING
                                self.state = STATE_LISTEN
                                self.processing = False
                                
                                # ✅ ניקוי באפר ופתיחה חדשה לתמלול
                                self.buf.clear()
                                self.last_voice_ts = current_time  # התחל מדידת שקט מחדש
                                self.voice_in_row = 0
                                
                                print("🎤 BARGE-IN -> LISTENING (user can speak now)")
                                
                                # שלח clear לטוויליו כדי לנקות אודיו תקוע (אם החיבור תקין)
                                if not self.ws_connection_failed:
                                    try:
                                        self.tx_q.put_nowait({"type": "clear"})
                                    except:
                                        pass
                                else:
                                    print("💔 SKIPPING barge-in clear - WebSocket connection failed")
                                continue
                        else:
                            # אם אין קול חזק מספיק - קזז את הספירה
                            self.voice_in_row = max(0, self.voice_in_row - 1)
                    else:
                        self.voice_in_row = 0  # אפס ספירה אם לא במצב speaking
                    
                    # אם המערכת מדברת ואין הפרעה - נקה קלט
                    if self.speaking:
                        self.buf.clear()
                        continue
                    
                    # ✅ איסוף אודיו עם זיהוי דממה תקין
                    if not self.processing and self.state == STATE_LISTEN:
                        # חלון רפרקטורי אחרי TTS
                        if (current_time - self.last_tts_end_ts) < (REPLY_REFRACTORY_MS/1000.0):
                            continue
                        
                        # אסוף אודיו רק כשיש קול או כשיש כבר דבר מה בבאפר
                        if is_strong_voice or len(self.buf) > 0:
                            self.buf.extend(pcm16)
                            dur = len(self.buf) / (2 * SR)
                            
                            # ✅ זיהוי סוף מבע לפי ההנחיות - 350-500ms שקט
                            min_silence = 1.0  # 1 שנייה שקט לפני עיבוד - נותן זמן לחשוב
                            silent = silence_time >= min_silence  
                            too_long = dur >= MAX_UTT_SEC
                            min_duration = 0.8  # מינימום לתמלול איכותי
                            
                            # ✅ EOU איכותי: באפר מספיק גדול לתמלול משמעותי
                            buffer_big_enough = len(self.buf) > 12800  # לפחות 0.8s של אודיו איכותי
                            
                            # סוף מבע: דממה מספקת OR זמן יותר מדי OR באפר גדול עם שקט
                            if ((silent and buffer_big_enough) or too_long) and dur >= min_duration:
                                print(f"🎤 END OF UTTERANCE: {dur:.1f}s audio, conversation #{self.conversation_id}")
                                
                                # ✅ מדידת Turn Latency - התחלת מדידה
                                self.eou_timestamp = time.time()
                                
                                # מעבר לעיבוד
                                self.processing = True
                                self.processing_start_ts = current_time
                                self.state = STATE_THINK
                                current_id = self.conversation_id
                                self.conversation_id += 1
                                
                                # עיבוד במנותק
                                utt_pcm = bytes(self.buf)
                                self.buf.clear()
                                self.last_voice_ts = 0  # אפס לסיבוב הבא
                                
                                print(f"🧠 STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                                
                                try:
                                    self._process_utterance_safe(utt_pcm, current_id)
                                except Exception as proc_err:
                                    print(f"❌ Audio processing failed for conversation #{current_id}: {proc_err}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continue without crashing WebSocket
                                finally:
                                    self.processing = False
                                    if self.state == STATE_THINK:
                                        self.state = STATE_LISTEN
                                    print(f"✅ Processing complete for conversation #{current_id}")
                    
                    # ✅ WebSocket Keepalive - מונע נפילות אחרי 5 דקות
                    if current_time - self.last_keepalive_ts > self.keepalive_interval:
                        self.last_keepalive_ts = current_time
                        self.heartbeat_counter += 1
                        
                        # שלח heartbeat mark event אם החיבור תקין
                        if not self.ws_connection_failed:
                            try:
                                heartbeat_msg = {
                                    "event": "mark",
                                    "streamSid": self.stream_sid,
                                    "mark": {"name": f"heartbeat_{self.heartbeat_counter}"}
                                }
                                success = self._ws_send(json.dumps(heartbeat_msg))
                                if success:
                                    print(f"💓 WS_KEEPALIVE #{self.heartbeat_counter} (prevents 5min timeout)")
                            except Exception as e:
                                print(f"⚠️ Keepalive failed: {e}")
                        else:
                            print(f"💔 SKIPPING keepalive - WebSocket connection failed")
                    
                    # ✅ Watchdog: וודא שלא תקועים במצב + EOU כפויה
                    if self.processing and (current_time - self.processing_start_ts) > 2.5:
                        print("⚠️ PROCESSING TIMEOUT - forcing reset")
                        self.processing = False
                        self.state = STATE_LISTEN
                        self.buf.clear()
                    
                    # ✅ LONGER speaking timeout to prevent cutoff mid-sentence
                    if self.speaking and (current_time - self.speaking_start_ts) > 15.0:
                        print("⚠️ SPEAKING TIMEOUT - forcing reset after 15s")  
                        self.speaking = False
                        self.state = STATE_LISTEN
                    
                    # ✅ EOU חירום: מכריח עיבוד אם הבאפר גדול מדי
                    if (not self.processing and self.state == STATE_LISTEN and 
                        len(self.buf) > 32000 and  # 2.0s של אודיו (סביר!)
                        silence_time > 0.2):      # 200ms שקט (סביר!)
                        print(f"🚨 EMERGENCY EOU: {len(self.buf)/(2*SR):.1f}s audio, silence={silence_time:.2f}s")
                        # כפה EOU
                        self.processing = True
                        self.processing_start_ts = current_time
                        self.state = STATE_THINK
                        current_id = self.conversation_id
                        self.conversation_id += 1
                        
                        utt_pcm = bytes(self.buf)
                        self.buf.clear()
                        self.last_voice_ts = 0
                        
                        print(f"🧠 EMERGENCY STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                        
                        try:
                            self._process_utterance_safe(utt_pcm, current_id)
                        except Exception as proc_err:
                            print(f"❌ Emergency audio processing failed for conversation #{current_id}: {proc_err}")
                            import traceback
                            traceback.print_exc()
                            # Continue without crashing WebSocket
                        finally:
                            self.processing = False
                            if self.state == STATE_THINK:
                                self.state = STATE_LISTEN
                            print(f"✅ Emergency processing complete for conversation #{current_id}")
                    
                    continue

                if et == "mark":
                    # ✅ סימון TTS הושלם - חזור להאזנה
                    mark_name = evt.get("mark", {}).get("name", "")
                    if mark_name == "assistant_tts_end":
                        print("🎯 TTS_MARK_ACK: assistant_tts_end -> LISTENING")
                        self.speaking = False
                        self.state = STATE_LISTEN
                        self.mark_pending = False
                        self.last_tts_end_ts = time.time()
                        # איפוס חשוב למערכת VAD
                        self.last_voice_ts = 0
                        self.voice_in_row = 0
                        print("🎤 STATE -> LISTENING | buffer_reset")
                    elif mark_name.startswith("heartbeat_"):
                        # אישור keepalive - התעלם
                        pass
                    continue

                if et == "stop":
                    print(f"WS_STOP sid={self.stream_sid} rx={self.rx} tx={self.tx}")
                    # ✅ CRITICAL: סיכום שיחה בסיום
                    self._finalize_call_on_stop()
                    # Send close frame properly
                    try:
                        if hasattr(self.ws, 'close'):
                            self.ws.close()
                    except:
                        pass
                    break

        except ConnectionClosed as e:
            print(f"📞 WS_CLOSED sid={self.stream_sid} rx={self.rx} tx={self.tx} reason=ConnectionClosed")
            # ✅ ניסיון התאוששות אם השיחה עדיין פעילה
            if self.call_sid:
                print(f"🔄 WS connection lost for active call {self.call_sid} - recovery might be possible via Twilio REST API")
        except Exception as e:
            print(f"❌ WS_ERROR sid={self.stream_sid}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up TX thread
            if hasattr(self, 'tx_thread') and self.tx_thread.is_alive():
                self.tx_running = False
                try:
                    self.tx_thread.join(timeout=1.0)
                except:
                    pass
            
            # ✅ CRITICAL: Wait for all background threads to complete
            # This prevents crashes when threads access DB after WebSocket closes
            if hasattr(self, 'background_threads') and self.background_threads:
                print(f"🧹 Waiting for {len(self.background_threads)} background threads...")
                for i, thread in enumerate(self.background_threads):
                    if thread.is_alive():
                        try:
                            thread.join(timeout=3.0)  # Max 3 seconds per thread
                            if thread.is_alive():
                                print(f"⚠️ Background thread {i} still running after timeout")
                            else:
                                print(f"✅ Background thread {i} completed")
                        except Exception as e:
                            print(f"❌ Error joining thread {i}: {e}")
                print(f"✅ All background threads cleanup complete")
            
            try: 
                self.ws.close()
            except: 
                pass
            # Mark as ended
            if hasattr(self, 'call_sid') and self.call_sid:
                stream_registry.clear(self.call_sid)
        
        # Final cleanup
        print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    def _interrupt_speaking(self):
        """✅ FIXED: עצירה מיידית של דיבור הבוט - סדר פעולות נכון"""
        print("🚨 INTERRUPT_START: Beginning full interrupt sequence")
        
        # ✅ STEP 1: שלח clear לטוויליו ראשון
        if not self.ws_connection_failed:
            try:
                self.tx_q.put_nowait({"type": "clear"})
                print("✅ CLEAR_SENT: Twilio clear command sent")
            except Exception as e:
                print(f"⚠️ CLEAR_FAILED: {e}")
        
        # ✅ STEP 2: נקה את תור השידור אחר clear
        try:
            cleared_count = 0
            while not self.tx_q.empty():
                self.tx_q.get_nowait()
                cleared_count += 1
            if cleared_count > 0:
                print(f"✅ TX_QUEUE_CLEARED: Removed {cleared_count} pending audio frames")
        except Exception as e:
            print(f"⚠️ TX_CLEAR_FAILED: {e}")
        
        # ✅ STEP 3: עדכן מצבים
        self.state = STATE_LISTEN
        self.mark_pending = False
        self.last_voice_ts = 0
        self.voice_in_row = 0
        self.processing = False
        
        # ✅ STEP 4: רק בסוף - עדכן speaking=False
        self.speaking = False
        
        print("✅ INTERRUPT_COMPLETE: Full interrupt sequence finished - ready to listen")

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
                print(f"🎤 USER: {text}")
                
                # ✅ מדידת ASR Latency
                if hasattr(self, 'eou_timestamp'):
                    asr_latency = time.time() - self.eou_timestamp
                    print(f"📊 ASR_LATENCY: {asr_latency:.3f}s (target: <0.7s)")
                    
            except Exception as e:
                print(f"❌ STT ERROR: {e}")
                text = ""
            
            # ✅ SMART HANDLING: כשלא מבין - בשקט או "לא הבנתי" אחרי כמה ניסיונות
            if not text.strip():
                # ספירת כישלונות רצופים
                if not hasattr(self, 'consecutive_empty_stt'):
                    self.consecutive_empty_stt = 0
                self.consecutive_empty_stt += 1
                
                # אם 2 כישלונות ברצף - תגיד "לא הבנתי"
                if self.consecutive_empty_stt >= 2:
                    print("🚫 MULTIPLE_EMPTY_STT: Saying 'didn't understand'")
                    self.consecutive_empty_stt = 0  # איפוס
                    try:
                        self._speak_simple("לא הבנתי, אפשר לחזור?")
                    except:
                        pass
                else:
                    print("🚫 NO_SPEECH_DETECTED: Staying silent (attempt 1)")
                
                self.state = STATE_LISTEN
                self.processing = False
                return
            # ✅ איפוס מונה כישלונות - STT הצליח!
            if hasattr(self, 'consecutive_empty_stt'):
                self.consecutive_empty_stt = 0
            # STT result processed")
            
            # PATCH 6: Anti-duplication on user text (14s window) - WITH DEBUG
            uh = zlib.crc32(text.strip().encode("utf-8"))
            if (self.last_user_hash == uh and 
                (time.time() - self.last_user_hash_ts) <= DEDUP_WINDOW_SEC):
                print("🚫 DUPLICATE USER INPUT (ignored)")
                self.processing = False
                self.state = STATE_LISTEN
                return
            self.last_user_hash, self.last_user_hash_ts = uh, time.time()
            # Processing new user input")
            
            # 3. AI Response - БЕЗ micro-ack! תן לה לחשוב בשקט
            ai_processing_start = time.time()
            
            # ✅ השתמש בפונקציה המתקדמת עם מתמחה והמאגר הכולל!
            reply = self._ai_response(text)
            
            # ✅ FIXED: אם AI החזיר None (אין טקסט אמיתי) - אל תגיב!
            if reply is None:
                print("🚫 AI_RETURNED_NONE: No response needed - returning to listen mode")
                self.processing = False
                self.state = STATE_LISTEN
                return
            
            # ✅ מניעת כפילויות משופרת - בדיקת 8 תשובות אחרונות (פחות רגיש)
            if not hasattr(self, 'recent_replies'):
                self.recent_replies = []
            
            # ✅ FIXED: מניעת כפילויות חכמה - רק כפילויות מרובות ממש
            reply_trimmed = reply.strip() if reply else ""
            exact_duplicates = [r for r in self.recent_replies if r == reply_trimmed]
            if len(exact_duplicates) >= 3:  # ✅ FIXED: רק אחרי 3 כפילויות מדויקות
                print("🚫 EXACT DUPLICATE detected (3+ times) - adding variation")
                if "תודה" in text.lower():
                    reply = "בשמחה! יש לי עוד אפשרויות אם אתה מעוניין."
                else:
                    reply = reply + " או אפשר עוד פרטים?"
                reply_trimmed = reply.strip()
                
            # עדכן היסטוריה - שמור רק 8 אחרונות
            if reply_trimmed:  # ✅ רק אם יש תשובה אמיתית
                self.recent_replies.append(reply_trimmed)
            if len(self.recent_replies) > 8:
                self.recent_replies = self.recent_replies[-8:]
            
            # ✅ FIXED: רק אם יש תשובה אמיתית - דפס, שמור ודבר
            if reply and reply.strip():
                print(f"🤖 BOT: {reply}")
                
                # ✅ מדידת AI Processing Time
                ai_processing_time = time.time() - ai_processing_start
                print(f"📊 AI_PROCESSING: {ai_processing_time:.3f}s")
                
                # 5. הוסף להיסטוריה (שני מבנים - סנכרון)
                self.response_history.append({
                    'id': conversation_id,
                    'user': text,
                    'bot': reply,
                    'time': time.time()
                })
                
                # ✅ CRITICAL FIX: סנכרון conversation_history לזיכרון AI
                self.conversation_history.append({
                    'user': text,
                    'bot': reply
                })
                
                # ✅ שמירת תור שיחה במסד נתונים לזיכרון קבוע
                self._save_conversation_turn(text, reply)
                
                # ✨ 6. Customer Intelligence - זיהוי/יצירת לקוח וליד חכם
                self._process_customer_intelligence(text, reply)
                
                # 6. דבר רק אם יש מה לומר
                self._speak_simple(reply)
            else:
                print("🚫 NO_VALID_RESPONSE: AI returned empty/None - staying silent")
                # לא דופסים, לא שומרים בהיסטוריה, לא מדברים
            
            # ✅ CRITICAL: חזור למצב האזנה אחרי כל תגובה!
            self.state = STATE_LISTEN
            print(f"✅ RETURNED TO LISTEN STATE after conversation #{conversation_id}")
            
        except Exception as e:
            print(f"❌ CRITICAL Processing error: {e}")
            print(f"   Text was: '{text}' ({len(text)} chars)")
            # ✅ תיקון קריטי: דבק לטראסבק ואל תקריס
            import traceback
            traceback.print_exc()
            # ✅ תגובת חירום מפורטת ומועילה
            try:
                self.state = STATE_SPEAK
                emergency_response = "מצטערת, לא שמעתי טוב בגלל החיבור. בואו נתחיל מחדש - איזה סוג נכס אתה מחפש ובאיזה אזור?"
                self._speak_with_breath(emergency_response)
                self.state = STATE_LISTEN
                print(f"✅ RETURNED TO LISTEN STATE after error in conversation #{conversation_id}")
            except Exception as emergency_err:
                print(f"❌ EMERGENCY RESPONSE FAILED: {emergency_err}")
                self.state = STATE_LISTEN
                # ✅ חזור למצב האזנה בכל מקרה


    # ✅ דיבור מתקדם עם סימונים לטוויליו
    def _speak_greeting(self, text: str):
        """⚡ TTS מהיר לברכה - ללא sleep!"""
        if not text:
            return
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        print(f"🔊 GREETING_TTS_START: '{text}'")
        
        try:
            # ⚡ בלי sleep - ברכה מיידית!
            tts_audio = self._hebrew_tts(text)
            if tts_audio and len(tts_audio) > 1000:
                print(f"✅ GREETING_TTS_SUCCESS: {len(tts_audio)} bytes")
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
            else:
                print("❌ GREETING_TTS_FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            print(f"❌ GREETING_TTS_ERROR: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._send_beep(800)
            except:
                pass
            self._finalize_speaking()
    
    def _speak_simple(self, text: str):
        """TTS עם מעקב מצבים וסימונים"""
        if not text:
            return
            
        if self.speaking:
            print("🚫 Already speaking - stopping current and starting new")
            try:
                # ✅ FIXED: בצע interrupt מלא לפני התחלת TTS חדש
                self._interrupt_speaking()
                time.sleep(0.05)  # המתנה קצרה
            except Exception as e:
                print(f"⚠️ Interrupt error (non-critical): {e}")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        print(f"🔊 TTS_START: '{text}'")
        
        # ✅ מדידת Turn Latency (מ-EOU עד TTS)
        if hasattr(self, 'eou_timestamp'):
            turn_latency = time.time() - self.eou_timestamp
            print(f"📊 TURN_LATENCY: {turn_latency:.3f}s (target: <1.2s)")
            delattr(self, 'eou_timestamp')  # נקה למדידה הבאה
        
        try:
            # ⚡ SPEED BOOST: המתנה קצרה יותר (100ms במקום 200-400ms)
            time.sleep(0.1)
                
            # קיצור טקסט ארוך
            if len(text) > 150:
                text = text[:150].rsplit(' ', 1)[0] + '.'
                print(f"🔪 TTS_SHORTENED: {text}")
            
            tts_audio = self._hebrew_tts(text)
            if tts_audio and len(tts_audio) > 1000:
                print(f"🔊 TTS SUCCESS: {len(tts_audio)} bytes")
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
            else:
                print("🔊 TTS FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            print(f"❌ TTS_ERROR: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._send_beep(800)
            except:
                pass
            self._finalize_speaking()
    
    def _finalize_speaking(self):
        """סיום דיבור עם חזרה להאזנה"""
        self.speaking = False
        self.last_tts_end_ts = time.time()
        self.state = STATE_LISTEN
        self.last_voice_ts = 0  # איפוס למערכת VAD
        self.voice_in_row = 0
        print("🎤 SPEAKING_END -> LISTEN STATE | buffer_reset")

    def _send_pcm16_as_mulaw_frames_with_mark(self, pcm16_8k: bytes):
        """שליחת אודיו עם סימון לטוויליו וברג-אין"""
        if not self.stream_sid or not pcm16_8k:
            self._finalize_speaking()
            return
            
        # CLEAR לפני שליחה
        self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        total_frames = len(mulaw) // FR
        
        print(f"🔊 TTS_FRAMES: {total_frames} frames ({total_frames * 20}ms)")
        
        for i in range(0, len(mulaw), FR):
            # בדיקת ברג-אין
            if not self.speaking:
                print(f"🚨 BARGE-IN! Stopped at frame {frames_sent}/{total_frames}")
                self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
                self._finalize_speaking()
                return
                
            # שלח פריים
            frame = mulaw[i:i+FR].ljust(FR, b'\x00')
            payload = base64.b64encode(frame).decode()
            media_msg = json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload}
            })
            self._ws_send(media_msg)
            frames_sent += 1
            
            # Yield לeventlet
            if frames_sent % 5 == 0:  # כל 100ms
                time.sleep(0)  # yield
        
        # הוסף 200ms שקט בסוף
        silence_frames = 10  # 200ms @ 20ms per frame  
        silence_mulaw = b'\x00' * FR
        for _ in range(silence_frames):
            if not self.speaking:
                break
            payload = base64.b64encode(silence_mulaw).decode()
            media_msg = json.dumps({
                "event": "media", 
                "streamSid": self.stream_sid,
                "media": {"payload": payload}
            })
            self._ws_send(media_msg)
            time.sleep(0)  # yield
        
        # שלח סימון לטוויליו
        self.mark_pending = True
        self.mark_sent_ts = time.time()
        mark_msg = json.dumps({
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {"name": "assistant_tts_end"}
        })
        self._ws_send(mark_msg)
        print("🎯 TTS_MARK_SENT: assistant_tts_end")
        
        # ✅ BUILD 100.4 FIX: סיים דיבור מיד וחזור להאזנה!
        # הבעיה: המערכת נשארה ב-STATE_SPEAK אחרי ברכה ולא חזרה להאזנה
        self._finalize_speaking()
        print("✅ GREETING_COMPLETE -> LISTEN STATE")

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        """שליחת אודיו עם יכולת עצירה באמצע (BARGE-IN) - גרסה ישנה"""
        if not self.stream_sid or not pcm16_8k:
            return
            
        # CLEAR לפני שליחה
        self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        
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
                self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
                break
                
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                # הגענו לסוף - זה תקין
                break
                
            payload = base64.b64encode(chunk).decode("ascii")
            try:
                self._ws_send(json.dumps({
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
    
    def _process_audio_for_stt(self, pcm16_8k: bytes) -> bytes:
        """🎵 עיבוד אודיו איכותי לפני STT: AGC, פילטרים, resample ל-16kHz"""
        try:
            import numpy as np
            from scipy import signal
        except ImportError:
            # numpy/scipy לא מותקנים - החזר כמו שזה
            print("⚠️ numpy/scipy not available - using raw audio")
            return pcm16_8k
        
        try:
            
            # המר ל-numpy array
            audio_int16 = np.frombuffer(pcm16_8k, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0  # normalize to [-1, 1]
            
            # ✅ 1. DC-offset removal
            audio_float = audio_float - float(np.mean(audio_float))
            
            # ✅ 2. High-pass filter (100Hz) - מטאטא זמזום
            sos_hp = signal.butter(4, 100, btype='high', fs=8000, output='sos')
            audio_float = np.array(signal.sosfilt(sos_hp, audio_float), dtype=np.float32)
            
            # ✅ 3. Low-pass filter (3.6kHz) - טלפוני רגיל  
            sos_lp = signal.butter(4, 3600, btype='low', fs=8000, output='sos')
            audio_float = np.array(signal.sosfilt(sos_lp, audio_float), dtype=np.float32)
            
            # ✅ 4. AGC עדין - נרמול לטווח מטרה (-20dBFS ≈ 0.1)
            rms_squared = np.mean(audio_float * audio_float)
            rms = float(np.sqrt(rms_squared))
            if rms > 0.001:  # אם יש אודיו אמיתי
                target_rms = 0.1  # -20dBFS
                gain = min(target_rms / rms, 3.0)  # מגביל גיין ל-3x
                audio_float = np.array(audio_float * gain, dtype=np.float32)
            
            # ✅ 5. Clipping protection
            audio_float = np.clip(audio_float, -0.95, 0.95)
            
            # ✅ 6. Resample 8kHz → 16kHz (Whisper עובד טוב יותר ב-16k)
            audio_16k = signal.resample(audio_float, len(audio_float) * 2)
            
            # המר חזרה ל-int16
            audio_16k_int16 = np.array(audio_16k * 32767, dtype=np.int16)
            
            return audio_16k_int16.tobytes()
            
        except ImportError:
            print(f"⚠️ numpy/scipy not available - using raw audio")
            return pcm16_8k
        except Exception as e:
            print(f"⚠️ Audio processing failed, using raw audio: {e}")
            # Fallback: החזר אודיו כמו שזה
            try:
                import numpy as np
                from scipy import signal
                audio_int16 = np.frombuffer(pcm16_8k, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_16k = signal.resample(audio_float, len(audio_float) * 2)
                audio_16k_int16 = np.array(audio_16k * 32767, dtype=np.int16)
                return audio_16k_int16.tobytes()
            except Exception as e2:
                print(f"⚠️ Even simple resample failed: {e2}")
                # Ultimate fallback: duplicate samples (crude but works)
                return pcm16_8k + pcm16_8k  # Double the data for "16kHz"

    def _hebrew_stt(self, pcm16_8k: bytes) -> str:
        """Hebrew STT using Google STT Streaming with speech contexts (לפי ההנחיות)"""
        try:
            print(f"🎵 STT_PROCEED: Processing {len(pcm16_8k)} bytes with Google STT (audio validated)")
            
            # ✅ FIXED: בדיקת איכות אודיו מתקדמת - מניעת עיבוד של רעש/שקט
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            print(f"📊 AUDIO_QUALITY_CHECK: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # ✅ בדיקות מרובות לזיהוי דיבור אמיתי
            
            # 1. בדיקת עוצמה בסיסית
            if max_amplitude < 100:  # ✅ חמור יותר מ-50
                print("🚫 STT_BLOCKED: Audio too quiet (max_amplitude < 100)")
                return ""
            
            # 2. בדיקת RMS לזיהוי אנרגיה שמעותית
            if rms < 80:  # ✅ בדיקת אנרגיה מינימלית
                print("🚫 STT_BLOCKED: Audio energy too low (rms < 80)")
                return ""
            
            # 3. בדיקת אורך מינימלי
            if duration < 0.2:  # פחות מ-200ms
                print("🚫 STT_BLOCKED: Audio too short (< 200ms)")
                return ""
            
            # 4. ✅ בדיקת שינוי אנרגיה - האם יש דיבור אמיתי? (numpy אופציונלי)
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                
                if energy_variance < 500000:  # אנרגיה מונוטונית = רעש
                    print(f"🚫 STT_BLOCKED: Monotonic audio (variance={energy_variance}) - likely noise")
                    return ""
                
                # 5. בדיקת Zero Crossing Rate - דיבור יש לו מעברי אפס
                zero_crossings = np.sum(np.diff(np.sign(pcm_array)) != 0) / len(pcm_array)
                if zero_crossings < 0.01:  # שיעור נמוך מאוד = לא דיבור
                    print(f"🚫 STT_BLOCKED: Low ZCR ({zero_crossings:.3f}) - not speech")
                    return ""
                
                print(f"✅ AUDIO_VALIDATED: variance={energy_variance}, zcr={zero_crossings:.3f} - proceeding to STT")
                
            except ImportError:
                print("⚠️ numpy not available - skipping advanced audio validation")
            except Exception as numpy_error:
                print(f"⚠️ Advanced audio analysis failed: {numpy_error} - using basic validation")
                # אם נכשלנו בבדיקות מתקדמות - המשך עם בסיסיות
            
            try:
                from server.services.lazy_services import get_stt_client
                from google.cloud import speech
            except ImportError as import_error:
                print(f"⚠️ Google Speech library not available: {import_error} - using Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            client = get_stt_client()
            if not client:
                print("❌ Google STT client not available - fallback to Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            # ⚡ SPEED BOOST: Google STT עם timeout אגרסיבי ל-enhanced model
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,  
                language_code="he-IL",   # עברית ישראל
                use_enhanced=True,       # Enhanced model לאיכות טובה יותר
                enable_automatic_punctuation=False,  # מניעת הפרעות
                # קונטקסט קל - רק לרמז
                speech_contexts=[
                    speech.SpeechContext(phrases=[
                        "שלום", "תודה", "כן", "לא", "בסדר", "נהדר", "ביי",
                        "דירה", "בית", "נדלן", "משרד", "חדרים", "שכירות", "קניה",
                        "תל אביב", "רמת גן", "רמלה", "לוד", "מודיעין",
                        "אלף", "מיליון", "שקל", "תקציב", "מחיר"
                    ], boost=2.0)
                ]
            )
            
            # Single request recognition (לא streaming למבע קצר)
            audio = speech.RecognitionAudio(content=pcm16_8k)
            
            # ⚡ RELIABLE STT: Timeout מספיק לעברית - 3s
            try:
                response = client.recognize(
                    config=recognition_config,
                    audio=audio,
                    timeout=3.0  # ✅ 3s timeout - מספיק לעברית
                )
            except Exception as timeout_error:
                # אם timeout - נסה basic model מיידית
                print(f"⚠️ ENHANCED_MODEL_TIMEOUT ({timeout_error}) - switching to basic")
                return self._google_stt_basic_fallback(pcm16_8k)
            
            print(f"📊 GOOGLE_STT_ENHANCED: Processed {len(pcm16_8k)} bytes")
            
            if response.results and response.results[0].alternatives:
                hebrew_text = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                print(f"📊 GOOGLE_STT_RESULT: '{hebrew_text}' (confidence: {confidence:.2f})")
                
                # ✅ CRITICAL: בדיקת confidence - לא לקבל תוצאות אקראיות!
                if confidence < 0.5:  # confidence נמוך = לא אמין
                    print(f"🚫 LOW_CONFIDENCE: {confidence:.2f} < 0.5 - rejecting result")
                    return ""  # ✅ החזר ריק במקום nonsense!
                
                print(f"✅ GOOGLE_STT_SUCCESS: '{hebrew_text}' (confidence: {confidence:.2f})")
                return hebrew_text
            else:
                print("⚠️ ENHANCED_MODEL_FAILED - trying BASIC model")
                # ✅ FIXED: נסה basic model לפני Whisper!
                return self._google_stt_basic_fallback(pcm16_8k)
                
        except Exception as e:
            print(f"❌ GOOGLE_STT_ERROR: {e} - trying basic model")
            return self._google_stt_basic_fallback(pcm16_8k)
    
    def _google_stt_basic_fallback(self, pcm16_8k: bytes) -> str:
        """✅ FIXED: Google STT basic model כ-fallback לפני Whisper"""
        try:
            print(f"🔄 GOOGLE_STT_BASIC: Trying basic model as fallback")
            try:
                from server.services.lazy_services import get_stt_client
                from google.cloud import speech
            except ImportError as import_error:
                print(f"⚠️ Google Speech library not available: {import_error} - using Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            client = get_stt_client()
            if not client:
                print("❌ Google STT client not available - fallback to Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            # ✅ Basic model עם אפס speech contexts - מאוד גמיש!
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                language_code="he-IL",
                use_enhanced=False,      # Basic model
                enable_automatic_punctuation=False,
                # ✅ אפס speech contexts - מקבל כל עברית!
            )
            
            audio = speech.RecognitionAudio(content=pcm16_8k)
            response = client.recognize(
                config=recognition_config,
                audio=audio,
                timeout=3.0  # ✅ 3s timeout - מספיק לעברית
            )
            
            print(f"📊 GOOGLE_STT_BASIC: Processed {len(pcm16_8k)} bytes")
            
            if response.results and response.results[0].alternatives:
                hebrew_text = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                print(f"📊 GOOGLE_STT_BASIC_RESULT: '{hebrew_text}' (confidence: {confidence:.2f})")
                
                # ✅ CRITICAL: בדיקת confidence - לא לקבל תוצאות אקראיות!
                if confidence < 0.5:  # confidence נמוך = לא אמין
                    print(f"🚫 LOW_CONFIDENCE: {confidence:.2f} < 0.5 - rejecting result")
                    return ""  # ✅ החזר ריק במקום nonsense!
                
                print(f"✅ GOOGLE_STT_BASIC_SUCCESS: '{hebrew_text}' (confidence: {confidence:.2f})")
                return hebrew_text
            else:
                print("❌ Both Google STT models failed - fallback to Whisper with validation")
                return self._whisper_fallback_validated(pcm16_8k)
                
        except Exception as e:
            print(f"❌ GOOGLE_STT_BASIC_ERROR: {e} - fallback to Whisper with validation")
            return self._whisper_fallback_validated(pcm16_8k)
    
    def _whisper_fallback_validated(self, pcm16_8k: bytes) -> str:
        """✅ FIXED: Whisper fallback with smart validation - לא ימציא מילים!"""
        try:
            print(f"🔄 WHISPER_VALIDATED: Processing {len(pcm16_8k)} bytes with fabrication prevention")
            
            # ✅ בדיקת איכות אודיו חמורה יותר
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            print(f"📊 AUDIO_VALIDATION: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # ✅ STRICT validation - אסור ל-Whisper להמציא דברים!
            if max_amplitude < 200 or rms < 120:  # הרבה יותר חמור!
                print("🚫 WHISPER_BLOCKED: Audio too weak - preventing fabrication")
                return ""  # פשוט אל תתן ל-Whisper להמציא!
            
            if duration < 0.3:  # פחות מ-300ms
                print("🚫 WHISPER_BLOCKED: Audio too short - likely noise")
                return ""
            
            # ✅ בדיקת שיווי אנרגיה - האם יש דיבור אמיתי?
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                if energy_variance < 1000000:  # אנרגיה מונוטונית = רעש
                    print(f"🚫 WHISPER_BLOCKED: Low energy variance ({energy_variance}) - likely background noise")
                    return ""
            except:
                pass  # אם נכשל בבדיקה - המשך
            
            from server.services.lazy_services import get_openai_client
            client = get_openai_client()
            if not client:
                print("❌ OpenAI client not available")
                return ""
            
            # Resample to 16kHz for Whisper
            pcm16_16k = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)[0]
            print(f"🔄 RESAMPLED: {len(pcm16_8k)} bytes @ 8kHz → {len(pcm16_16k)} bytes @ 16kHz")
            
            # ✅ Whisper עם פרמטרים חמורים נגד המצאות
            import tempfile
            import wave
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    wav_file.writeframes(pcm16_16k)
                
                with open(temp_wav.name, 'rb') as audio_file:
                    # ✅ FIXED: פרמטרים חמורים נגד המצאה
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he",  # חייב עברית
                        prompt="זוהי שיחת טלפון בעברית על נדלן. אם אין דיבור ברור - אל תנסה לנחש.",  # הנחיה חמורה!
                        temperature=0.1  # נמוך מאוד - פחות יצירתיות
                    )
            
            import os
            os.unlink(temp_wav.name)
            
            result = transcript.text.strip()
            
            # ✅ FINAL validation - בדיקת תוצאה חשודה
            if not result or len(result) < 2:
                print("✅ WHISPER_VALIDATED: Empty/minimal result - good!")
                return ""
            
            # ✅ בדיקת מילים חשודות ש-Whisper אוהב להמציא
            suspicious_words = ["תודה", "נהדר", "נהדרת", "מעולה", "בראבו"] 
            if len(result.split()) == 1 and any(word in result for word in suspicious_words):
                print(f"🚫 WHISPER_FABRICATION_DETECTED: Suspicious single word '{result}' - blocking")
                return ""
            
            print(f"✅ WHISPER_VALIDATED_SUCCESS: '{result}'")
            return result
            
        except Exception as e:
            print(f"❌ WHISPER_VALIDATED_ERROR: {e}")
            return ""
    
    def _whisper_fallback(self, pcm16_8k: bytes) -> str:
        """⚠️ DEPRECATED: Old Whisper fallback - עכשיו שימוש ב-validated version"""
        try:
            print(f"🔄 WHISPER_FALLBACK: Processing {len(pcm16_8k)} bytes")
            
            # Check if audio has actual content
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            print(f"📊 AUDIO_ANALYSIS: max_amplitude={max_amplitude}, rms={rms}")
            
            if max_amplitude < 100 or rms < 80:  # ✅ תיקון לעברית - thresholds נמוכים יותר
                print("🔇 WHISPER_SKIP: Audio too quiet or likely noise (Hebrew optimized)")
                return ""
            
            from server.services.lazy_services import get_openai_client
            client = get_openai_client()
            if not client:
                print("❌ OpenAI client not available")
                return ""
            
            # Resample to 16kHz for Whisper
            pcm16_16k = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)[0]
            print(f"🔄 RESAMPLED: {len(pcm16_8k)} bytes @ 8kHz → {len(pcm16_16k)} bytes @ 16kHz")
            
            # Save as temporary WAV file
            import tempfile, wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    wav_file.writeframes(pcm16_16k)
                
                with open(temp_wav.name, 'rb') as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he",
                        response_format="text", 
                        temperature=0.2
                    )
                
                hebrew_text = str(transcription).strip() if transcription else ""
                print(f"✅ WHISPER_FALLBACK_SUCCESS: '{hebrew_text}'")
                
                # Clean up
                import os
                os.unlink(temp_wav.name)
                return hebrew_text
                
        except Exception as e:
            print(f"❌ WHISPER_FALLBACK_ERROR: {e}")
            return ""
    
    def _load_business_prompts(self, channel: str = 'calls') -> str:
        """טוען פרומפטים מהדאטאבייס לפי עסק - לפי ההנחיות המדויקות"""
        try:
            # ✅ CRITICAL: All DB queries need app_context in Cloud Run/ASGI!
            from server.app_factory import create_app
            from server.models_sql import Business, BusinessSettings
            
            app = create_app()
            with app.app_context():
                # ✅ BUILD 100 FIX: זיהוי business_id לפי מספר טלפון - שימוש ב-phone_e164
                if not self.business_id and self.phone_number:
                    # חפש עסק לפי מספר הטלפון (phone_e164 = העמודה האמיתית)
                    business = Business.query.filter(
                        Business.phone_e164 == self.phone_number
                    ).first()
                    if business:
                        self.business_id = business.id
                        print(f"✅ זיהוי עסק לפי טלפון {self.phone_number}: {business.name}")
                
                # אם אין עדיין business_id, השתמש בfallback
                if not self.business_id:
                    from server.services.business_resolver import resolve_business_with_fallback
                    self.business_id, status = resolve_business_with_fallback('twilio_voice', '+97233763805')
                    print(f"✅ שימוש בעסק fallback: business_id={self.business_id} ({status})")
                
                if not self.business_id:
                    print("❌ לא נמצא עסק - שימוש בפרומפט ברירת מחדל")
                    return "את עוזרת נדלן מקצועית. עזרי ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם hardcoded
                
                # טען פרומפט מ-BusinessSettings
                settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
                business = Business.query.get(self.business_id)
            
            if settings and settings.ai_prompt:
                try:
                    # נסה לפרסר JSON (פורמט חדש עם calls/whatsapp)
                    import json
                    if settings.ai_prompt.startswith('{'):
                        prompt_data = json.loads(settings.ai_prompt)
                        prompt_text = prompt_data.get(channel, prompt_data.get('calls', ''))
                        if prompt_text:
                            print(f"AI_PROMPT loaded tenant={self.business_id} channel={channel}")
                            return prompt_text
                    else:
                        # פרומפט יחיד (legacy)
                        print(f"✅ טען פרומפט legacy מדאטאבייס לעסק {self.business_id}")
                        return settings.ai_prompt
                except Exception as e:
                    print(f"⚠️ שגיאה בפרסור פרומפט JSON: {e}")
                    # fallback לפרומפט כטקסט רגיל
                    return settings.ai_prompt
            
            # אם אין ב-BusinessSettings, בדוק את business.system_prompt
            if business and business.system_prompt:
                print(f"✅ טען פרומפט מטבלת businesses לעסק {self.business_id}")
                return business.system_prompt
                
            print(f"⚠️ לא נמצא פרומפט לעסק {self.business_id} - שימוש בברירת מחדל")
            return "את עוזרת נדלן מקצועית. עזרי ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם/עסק hardcoded
            
        except Exception as e:
            print(f"❌ שגיאה בטעינת פרומפט מדאטאבייס: {e}")
            return "את עוזרת נדלן מקצועית. עזרי ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם hardcoded

    def _identify_business_from_phone(self):
        """זיהוי business_id לפי to_number (המספר שאליו התקשרו) אם חסר"""
        try:
            # ✅ CRITICAL: All DB queries need app_context in Cloud Run/ASGI!
            from server.app_factory import create_app
            from server.models_sql import Business
            from sqlalchemy import or_
            
            to_number = getattr(self, 'to_number', None)
            
            print(f"🔍 _identify_business_from_phone: to_number={to_number}")
            
            app = create_app()
            with app.app_context():
                if to_number:
                    # נרמל מספר טלפון (הסר רווחים, מקפים)
                    normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
                    
                    print(f"🔍 מחפש עסק: to_number={to_number}, normalized={normalized_phone}")
                    
                    # ✅ BUILD 100 FIX: חפש business לפי phone_e164 (העמודה האמיתית ב-DB, לא property!)
                    business = Business.query.filter(
                        or_(
                            Business.phone_e164 == to_number,
                            Business.phone_e164 == normalized_phone
                        )
                    ).first()
                    
                    if business:
                        self.business_id = business.id
                        print(f"✅ זיהוי עסק לפי to_number {to_number}: business_id={self.business_id} (מצא: {business.name})")
                        return
                    else:
                        # Debug: הדפס את כל העסקים כדי לראות מה יש
                        all_businesses = Business.query.filter_by(is_active=True).all()
                        print(f"⚠️ לא נמצא עסק עם מספר {to_number}")
                        print(f"📋 עסקים פעילים: {[(b.id, b.name, b.phone_e164) for b in all_businesses]}")
                
                # Fallback: עסק פעיל ראשון
                business = Business.query.filter_by(is_active=True).first()
                if business:
                    self.business_id = business.id
                    print(f"✅ שימוש בעסק fallback: business_id={self.business_id} ({business.name})")
                else:
                    # Ultimate fallback
                    business = Business.query.first()
                    self.business_id = business.id if business else 1
                    print(f"⚠️ שימוש בעסק ראשון: business_id={self.business_id}")
        
        except Exception as e:
            # ✅ CRITICAL: Never crash - always set fallback business_id
            print(f"❌ Business identification failed: {e}")
            import traceback
            traceback.print_exc()
            self.business_id = 1  # Ultimate fallback
            print(f"✅ Using fallback business_id=1")

    def _get_business_greeting_cached(self) -> str:
        """⚡ טעינת ברכה עם cache - במיוחד מהיר לברכה הראשונה!"""
        # קודם כל - בדוק אם יש business_id
        if not hasattr(self, 'business_id') or not self.business_id:
            print(f"⚠️ business_id חסר בקריאה ל-_get_business_greeting_cached!")
            return "שלום! איך אפשר לעזור?"
        
        try:
            # ✅ CRITICAL FIX: Must have app_context for DB query in Cloud Run/ASGI!
            from server.app_factory import create_app
            from server.models_sql import Business
            
            app = create_app()
            with app.app_context():
                # ⚡ שאילתה בודדת - קל ומהיר
                business = Business.query.get(self.business_id)
                
                if business:
                    # קבלת הברכה המותאמת
                    greeting = business.greeting_message or "שלום! איך אפשר לעזור?"
                    business_name = business.name or "העסק שלנו"
                    
                    # החלפת placeholder בשם האמיתי
                    greeting = greeting.replace("{{business_name}}", business_name)
                    greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                    
                    print(f"✅ ברכה נטענה במהירות: business_id={self.business_id}, name={business_name}")
                    return greeting
                else:
                    print(f"⚠️ Business {self.business_id} לא נמצא - ברכה ברירת מחדל")
                    return "שלום! איך אפשר לעזור?"
        except Exception as e:
            print(f"❌ שגיאה בטעינת ברכה: {e}")
            import traceback
            traceback.print_exc()
            return "שלום! איך אפשר לעזור?"
    
    def _get_business_greeting(self) -> str:
        """טעינת ברכה מותאמת אישית מהעסק עם {{business_name}} placeholder"""
        print(f"🔍 _get_business_greeting CALLED! business_id={getattr(self, 'business_id', 'NOT SET')}")
        
        try:
            from server.app_factory import create_app
            from server.models_sql import Business
            
            # זיהוי עסק אם עדיין לא זוהה
            if not hasattr(self, 'business_id') or not self.business_id:
                print(f"⚠️ business_id לא מוגדר - מזהה עסק עכשיו...")
                app = create_app()
                with app.app_context():
                    self._identify_business_from_phone()
                print(f"🔍 אחרי זיהוי: business_id={getattr(self, 'business_id', 'STILL NOT SET')}")
            
            # טעינת ברכה מה-DB
            app = create_app()
            with app.app_context():
                business = Business.query.get(self.business_id)
                print(f"🔍 שאילתת business: id={self.business_id}, נמצא: {business is not None}")
                
                if business:
                    # קבלת הברכה המותאמת
                    greeting = business.greeting_message or "שלום! איך אפשר לעזור?"
                    business_name = business.name or "העסק שלנו"
                    
                    print(f"🔍 פרטי עסק: name={business_name}, greeting_message={business.greeting_message}")
                    
                    # החלפת placeholder בשם האמיתי
                    greeting = greeting.replace("{{business_name}}", business_name)
                    greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                    
                    print(f"✅ Loaded custom greeting for business {self.business_id} ({business_name}): '{greeting}'")
                    return greeting
                else:
                    print(f"⚠️ Business {self.business_id} not found - using default greeting")
                    return "שלום! איך אפשר לעזור?"
        except Exception as e:
            import traceback
            print(f"❌ Error loading business greeting: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return "שלום! איך אפשר לעזור?"

    def _ai_response(self, hebrew_text: str) -> str:
        """Generate NATURAL Hebrew AI response using unified AIService - UPDATED for prompt auto-sync"""
        try:
            # ✅ UNIFIED: Use AIService for ALL prompt management (auto-updates!)
            from server.services.ai_service import generate_ai_response
            from server.app_factory import create_app
            
            # וידוא שיש business_id
            if not hasattr(self, 'business_id') or not self.business_id:
                # זיהוי business_id אם חסר - WITH APP CONTEXT
                app = create_app()
                with app.app_context():
                    self._identify_business_from_phone()
            
            # Build context for the AI
            context = {
                "phone_number": getattr(self, 'phone_number', ''),
                "channel": "voice_call",
                "previous_messages": []
            }
            
            # Add conversation history for context - ✅ FIXED FORMAT
            if hasattr(self, 'conversation_history') and self.conversation_history:
                context["previous_messages"] = [
                    f"לקוח: {item['user']}\nעוזרת: {item['bot']}"  # ✅ "עוזרת" במקום "לאה" - כללי!
                    for item in self.conversation_history[-6:]  # עד 6 תורות אחרונים לזיכרון מלא
                ]
            
            # ✅ CRITICAL FIX: Generate AI response WITH APP CONTEXT (for DB access)
            business_id = getattr(self, 'business_id', None)
            if not business_id:
                # ✅ זיהוי business_id אם חסר
                app = create_app()
                with app.app_context():
                    self._identify_business_from_phone()
                business_id = self.business_id or 11  # Fallback to business 11
            
            app = create_app()
            with app.app_context():
                ai_response = generate_ai_response(
                    message=hebrew_text,
                    business_id=int(business_id),  # Ensure it's an int
                    context=context,
                    channel='calls'  # ✅ Use 'calls' prompt for phone calls
                )
            
            print(f"✅ AI_SERVICE_RESPONSE: Generated {len(ai_response)} chars for business {business_id}")
            return ai_response
            
        except Exception as e:
            print(f"❌ AI_SERVICE_ERROR: {e} - using fallback logic")
            return self._fallback_response(hebrew_text)
    
    def _fallback_response(self, hebrew_text: str) -> str:
        """Simple fallback response when AI service fails"""
        if "שלום" in hebrew_text or "היי" in hebrew_text:
            return "שלום! איך אני יכולה לעזור?"  # ✅ כללי - לא חושף שם עסק
        elif "תודה" in hebrew_text or "ביי" in hebrew_text:
            return "תודה רבה! אני כאן לכל שאלה."
        else:
            return "איזה אזור מעניין אותך?"  # ✅ כללי - לא מדבר על דירות
    
    
    def _hebrew_tts(self, text: str) -> bytes | None:
        """
        ✅ UPGRADED Hebrew TTS with natural voice, SSML, and smart pronunciation
        Uses gcp_tts_live.py with all professional enhancements
        """
        try:
            print(f"🔊 TTS_START: Generating Natural Hebrew TTS for '{text[:50]}...' ({len(text)} chars)")
            
            # ✅ OPTION 1: Use punctuation polish if enabled
            try:
                from server.services.punctuation_polish import polish_hebrew_text
                text = polish_hebrew_text(text)
                print(f"✅ Punctuation polished: '{text[:40]}...'")
            except Exception as e:
                print(f"⚠️ Punctuation polish unavailable: {e}")
            
            # ✅ OPTION 2: Use upgraded TTS with SSML, natural voice, telephony profile
            try:
                from server.services.gcp_tts_live import get_hebrew_tts
                tts_service = get_hebrew_tts()
                audio_bytes = tts_service.synthesize_hebrew_pcm16_8k(text)
                
                if audio_bytes and len(audio_bytes) > 1000:
                    duration_seconds = len(audio_bytes) / (8000 * 2)
                    print(f"✅ TTS_SUCCESS: {len(audio_bytes)} bytes Natural Wavenet ({duration_seconds:.1f}s)")
                    return audio_bytes
                else:
                    print("⚠️ TTS returned empty or too short")
                    return None
                    
            except ImportError as ie:
                print(f"⚠️ Upgraded TTS unavailable ({ie}), using fallback...")
                
                # ✅ FALLBACK: Basic Google TTS (if upgraded version fails)
                from server.services.lazy_services import get_tts_client
                from google.cloud import texttospeech
                
                client = get_tts_client()
                if not client:
                    print("❌ Google TTS client not available")
                    return None
                
                # ✅ קבלת הגדרות מ-ENV - לא מקודד!
                voice_name = os.getenv("TTS_VOICE", "he-IL-Wavenet-D")
                speaking_rate = float(os.getenv("TTS_RATE", "0.96"))
                pitch = float(os.getenv("TTS_PITCH", "-2.0"))
                
                synthesis_input = texttospeech.SynthesisInput(text=text)
                voice = texttospeech.VoiceSelectionParams(language_code="he-IL", name=voice_name)
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=8000,
                    speaking_rate=speaking_rate,
                    pitch=pitch,
                    effects_profile_id=["telephony-class-application"]
                )
                
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                duration_seconds = len(response.audio_content) / (8000 * 2)
                print(f"✅ TTS_FALLBACK_SUCCESS: {len(response.audio_content)} bytes (voice={voice_name}, rate={speaking_rate}, pitch={pitch}, {duration_seconds:.1f}s)")
                return response.audio_content
            
        except Exception as e:
            print(f"❌ TTS_CRITICAL_ERROR: {e}")
            print(f"   Text was: '{text}'")
            import traceback
            traceback.print_exc()
            return None
    
    def _tx_loop(self):
        """TX Queue loop for smooth audio transmission"""
        print("🔊 TX_LOOP_START: Audio transmission thread started")
        tx_count = 0
        while self.tx_running:
            try:
                item = self.tx_q.get(timeout=0.5)
            except queue.Empty:
                continue
            
            if item.get("type") == "end":
                print("🔚 TX_LOOP_END: End signal received")
                break
            if item.get("type") == "clear" and self.stream_sid:
                success = self._ws_send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
                print(f"🧹 TX_CLEAR: {'SUCCESS' if success else 'FAILED'}")
                continue
            if item.get("type") == "media":
                success = self._ws_send(json.dumps({
                    "event": "media", 
                    "streamSid": self.stream_sid,
                    "media": {"payload": item["payload"]}
                }))
                tx_count += 1
                if tx_count % 50 == 0:  # Log every 50 frames (1 second)
                    print(f"🎵 TX_MEDIA: Frame {tx_count} {'SUCCESS' if success else 'FAILED'}")
                continue
            if item.get("type") == "mark":
                success = self._ws_send(json.dumps({
                    "event": "mark", 
                    "streamSid": self.stream_sid,
                    "mark": {"name": item.get("name", "mark")}
                }))
                print(f"📍 TX_MARK: {item.get('name', 'mark')} {'SUCCESS' if success else 'FAILED'}")
        print(f"🔊 TX_LOOP_DONE: Transmitted {tx_count} frames total")
    
    def _speak_with_breath(self, text: str):
        """דיבור עם נשימה אנושית ו-TX Queue - תמיד משדר משהו"""
        if not text:
            return
            
        self.speaking = True
        self.state = STATE_SPEAK
        self.speaking_start_ts = time.time()  # ✅ חלון חסד - זמן תחילת TTS
        
        try:
            # נשימה אנושית (220-360ms)
            breath_delay = random.uniform(RESP_MIN_DELAY_MS/1000.0, RESP_MAX_DELAY_MS/1000.0)
            time.sleep(breath_delay)
            
            # clear + שידור אם החיבור תקין
            if self.stream_sid and not self.ws_connection_failed:
                self.tx_q.put_nowait({"type": "clear"})
            elif self.ws_connection_failed:
                print("💔 SKIPPING TTS clear - WebSocket connection failed")
                return None
            
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
            
            # ✅ שלח את האודיו דרך TX Queue (אם החיבור תקין)
            if pcm and self.stream_sid and not self.ws_connection_failed:
                self._send_pcm16_as_mulaw_frames(pcm)
            elif self.ws_connection_failed:
                print("💔 SKIPPING audio clear - WebSocket connection failed")
                return
            
            # ✅ Audio already sent by _send_pcm16_as_mulaw_frames() above
            
        finally:
            # ✅ Clean finalization
            self._finalize_speaking()
    
    def _beep_pcm16_8k_v2(self, ms: int) -> bytes:
        """יצירת צפצוף PCM16 8kHz"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        
        for n in range(samples):
            val = int(amp * math.sin(2 * math.pi * 440 * n / SR))
            out.extend(val.to_bytes(2, "little", signed=True))
            
        return bytes(out)
    
    def _detect_area(self, text: str) -> str:
        """זיהוי אזור מהטקסט של הלקוח"""
        text = text.lower()
        
        # מרכז הארץ
        if any(word in text for word in ["תל אביב", "דיזנגוף", "פלורנטין", "נווה צדק"]):
            return "תל אביב"
        elif any(word in text for word in ["רמת גן", "גבעתיים", "הבורסה"]):
            return "רמת גן/גבעתיים"
        elif any(word in text for word in ["הרצליה", "פיתוח"]):
            return "הרצליה"
            
        # מרכז ודרום
        elif any(word in text for word in ["רמלה"]):
            return "רמלה"
        elif any(word in text for word in ["לוד"]):
            return "לוד"
        elif any(word in text for word in ["פתח תקווה", "פתח תקוה"]):
            return "פתח תקווה"
        elif any(word in text for word in ["מודיעין"]):
            return "מודיעין"
        elif any(word in text for word in ["רחובות"]):
            return "רחובות"
            
        # אזור ירושלים
        elif any(word in text for word in ["בית שמש"]):
            return "בית שמש"
        elif any(word in text for word in ["מעלה אדומים"]):
            return "מעלה אדומים"
        elif any(word in text for word in ["ירושלים"]):
            return "ירושלים"
            
        return ""  # Return empty string instead of None
    
    def _analyze_lead_completeness(self) -> dict:
        """✅ ניתוח השלמת מידע ליד לתיאום פגישה"""
        collected_info = {
            'area': False,
            'property_type': False, 
            'budget': False,
            'timing': False,
            'contact': False
        }
        
        meeting_ready = False
        
        # בדוק היסטוריה לאיסוף מידע
        if hasattr(self, 'conversation_history') and self.conversation_history:
            full_conversation = ' '.join([turn['user'] + ' ' + turn['bot'] for turn in self.conversation_history])
            
            # זיהוי אזור
            if any(area in full_conversation for area in ['תל אביב', 'רמת גן', 'רמלה', 'לוד', 'בית שמש', 'מודיעין', 'פתח תקווה', 'רחובות', 'הרצליה', 'ירושלים']):
                collected_info['area'] = True
            
            # זיהוי סוג נכס
            if any(prop_type in full_conversation for prop_type in ['דירה', 'חדרים', '2 חדרים', '3 חדרים', '4 חדרים', 'משרד', 'דופלקס']):
                collected_info['property_type'] = True
            
            # זיהוי תקציב
            if any(budget_word in full_conversation for budget_word in ['שקל', 'אלף', 'תקציב', '₪', 'אלפים', 'מיליון']):
                collected_info['budget'] = True
            
            # זיהוי זמן כניסה
            if any(timing in full_conversation for timing in ['מיידי', 'דחוף', 'חודש', 'שבועיים', 'בקרוב', 'עכשיו']):
                collected_info['timing'] = True
            
            # זיהוי פרטי קשר
            if any(contact in full_conversation for contact in ['טלפון', 'וואטסאפ', 'נייד', 'מספר', 'פרטים']):
                collected_info['contact'] = True
        
        # ספירת מידע שנאסף
        completed_fields = sum(collected_info.values())
        
        # תיאום פגישה אם יש לפחות 4 שדות (יותר מידע לשיחה טבעית)
        meeting_ready = completed_fields >= 4
        
        # יצירת סיכום
        summary_parts = []
        if collected_info['area']: summary_parts.append('אזור')
        if collected_info['property_type']: summary_parts.append('סוג נכס')
        if collected_info['budget']: summary_parts.append('תקציב')
        if collected_info['timing']: summary_parts.append('זמן')
        if collected_info['contact']: summary_parts.append('קשר')
        
        summary = f"{len(summary_parts)}/5 שדות: {', '.join(summary_parts) if summary_parts else 'אין'}"
        
        # הודעה לתיאום פגישה או הצגת אופציות
        meeting_prompt = ""
        if meeting_ready:
            import datetime
            now = datetime.datetime.now()
            today_evening = f"היום {now.hour + 2}:00"
            tomorrow_morning = f"מחר {9 + (now.hour % 3)}:30"
            
            meeting_prompt = f"""
זמן לתיאום פגישה! יש מספיק מידע ({completed_fields}/5 שדות).
הצע 2-3 חלונות זמן: {today_evening}, {tomorrow_morning}, או עוד אפשרות קצרה.
בקש אישור ושלח סיכום קצר."""
        elif completed_fields == 3:
            meeting_prompt = """
יש מידע בסיסי טוב! עכשיו תני דוגמה אחת ספציפית מתאימה ושאלי שאלה ממוקדת לפני קביעת פגישה."""
        else:
            missing = 4 - completed_fields
            meeting_prompt = f"צריך עוד {missing} שדות מידע לפני הצגת אופציות. המשיכי שיחה טבעית ותני פרטים נוספים על השוק והאזור."
        
        return {
            'collected': collected_info,
            'completed_count': completed_fields,
            'meeting_ready': meeting_ready,
            'summary': summary,
            'meeting_prompt': meeting_prompt
        }
    
    def _finalize_call_on_stop(self):
        """✅ סיכום מלא של השיחה בסיום - עדכון call_log וליד"""
        try:
            from server.models_sql import CallLog
            from server.services.customer_intelligence import CustomerIntelligence
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def finalize_in_background():
                try:
                    app = create_app()
                    with app.app_context():
                        # מצא call_log
                        call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if not call_log:
                            print(f"⚠️ No call_log found for final summary: {self.call_sid}")
                            return
                        
                        # בנה סיכום מלא
                        full_conversation = ""
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            full_conversation = "\n".join([
                                f"לקוח: {turn['user']}\nעוזרת: {turn['bot']}"  # ✅ כללי - לא hardcoded!
                                for turn in self.conversation_history
                            ])
                        
                        # צור סיכום AI
                        business_id = getattr(self, 'business_id', 1)
                        ci = CustomerIntelligence(business_id)
                        summary_data = ci.generate_conversation_summary(
                            full_conversation,
                            {'conversation_history': self.conversation_history}
                        )
                        
                        # עדכן call_log
                        call_log.status = "completed"
                        call_log.transcription = full_conversation  # ✅ FIX: transcription not transcript!
                        call_log.summary = summary_data.get('summary', '')
                        call_log.ai_summary = summary_data.get('detailed_summary', '')
                        
                        db.session.commit()
                        
                        print(f"✅ CALL FINALIZED: {self.call_sid}")
                        print(f"📝 Summary: {summary_data.get('summary', 'N/A')}")
                        print(f"🎯 Intent: {summary_data.get('intent', 'N/A')}")
                        print(f"📊 Next Action: {summary_data.get('next_action', 'N/A')}")
                        
                except Exception as e:
                    print(f"❌ Failed to finalize call: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע
            thread = threading.Thread(target=finalize_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Call finalization setup failed: {e}")
    
    def _create_call_log_on_start(self):
        """✅ יצירת call_log מיד בהתחלת שיחה - למניעת 'Call SID not found' errors"""
        try:
            from server.models_sql import CallLog
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def create_in_background():
                try:
                    app = create_app()
                    with app.app_context():
                        # ✅ LOG DATABASE CONNECTION (per הנחיות)
                        db_url = os.getenv('DATABASE_URL', 'NOT_SET')
                        db_driver = db_url.split(':')[0] if db_url else 'none'
                        print(f"🔧 DB_URL_AT_WRITE: driver={db_driver}, BIZ={getattr(self, 'business_id', 1)}, SID={self.call_sid}", flush=True)
                        
                        # בדוק אם כבר קיים
                        existing = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if existing:
                            print(f"✅ Call log already exists for {self.call_sid}")
                            return
                        
                        # צור call_log חדש
                        call_log = CallLog(
                            business_id=getattr(self, 'business_id', 1),
                            call_sid=self.call_sid,
                            from_number=str(self.phone_number or ""),
                            to_number=str(getattr(self, 'to_number', '') or ''),  # ✅ המספר שאליו התקשרו
                            call_status="in_progress"  # ✅ תוקן: call_status במקום status
                        )
                        db.session.add(call_log)
                        
                        try:
                            db.session.commit()
                            print(f"✅ Created call_log on start: call_sid={self.call_sid}, phone={self.phone_number}")
                        except Exception as commit_error:
                            # Handle duplicate key error (race condition)
                            db.session.rollback()
                            error_msg = str(commit_error).lower()
                            if 'unique' in error_msg or 'duplicate' in error_msg:
                                print(f"⚠️ Call log already exists (race condition): {self.call_sid}")
                            else:
                                raise
                        
                except Exception as e:
                    print(f"❌ Failed to create call_log on start: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע
            thread = threading.Thread(target=create_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Call log creation setup failed: {e}")
    
    def _save_conversation_turn(self, user_text: str, bot_reply: str):
        """✅ שמירת תור שיחה במסד נתונים לזיכרון קבוע"""
        try:
            from server.models_sql import ConversationTurn, CallLog
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def save_in_background():
                try:
                    app = create_app()
                    with app.app_context():
                        # מצא call_log קיים (אמור להיות כבר נוצר ב-_create_call_log_on_start)
                        call_log = None
                        if hasattr(self, 'call_sid') and self.call_sid:
                            call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        
                        if not call_log:
                            print(f"⚠️ Call log not found for {self.call_sid} - conversation turn not saved")
                            return
                        
                        # שמור תור משתמש
                        user_turn = ConversationTurn(
                            call_log_id=call_log.id,
                            call_sid=self.call_sid or f"live_{int(time.time())}",
                            speaker='user',
                            message=user_text,
                            confidence_score=1.0
                        )
                        db.session.add(user_turn)
                        
                        # שמור תור AI
                        bot_turn = ConversationTurn(
                            call_log_id=call_log.id,
                            call_sid=self.call_sid or f"live_{int(time.time())}",
                            speaker='assistant',
                            message=bot_reply,
                            confidence_score=1.0
                        )
                        db.session.add(bot_turn)
                        
                        db.session.commit()
                        print(f"✅ Saved conversation turn to DB: call_log_id={call_log.id}")
                        
                except Exception as e:
                    print(f"❌ Failed to save conversation turn: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע כדי לא לחסום
            thread = threading.Thread(target=save_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Conversation turn save setup failed: {e}")
    
    def _process_customer_intelligence(self, user_text: str, bot_reply: str):
        """
        ✨ עיבוד חכם של השיחה עם זיהוי/יצירת לקוח וליד אוטומטית
        """
        try:
            # וודא שיש מספר טלפון ו-business_id
            if not self.phone_number or not hasattr(self, 'business_id'):
                print("⚠️ Missing phone_number or business_id for customer intelligence")
                return
            
            # Import only when needed to avoid circular imports
            from server.services.customer_intelligence import CustomerIntelligence
            from server.app_factory import create_app
            from server.db import db
            
            # הרצה אסינכרונית כדי לא לחסום את השיחה
            import threading
            
            def process_in_background():
                try:
                    app = create_app()
                    with app.app_context():
                        business_id = getattr(self, 'business_id', 1)
                        ci = CustomerIntelligence(business_id)
                        
                        # יצירת טקסט מלא מההיסטוריה הנוכחית
                        full_conversation = ""
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            full_conversation = " ".join([
                                f"{turn['user']} {turn['bot']}" 
                                for turn in self.conversation_history[-5:]  # רק 5 אחרונות
                            ])
                        
                        # זיהוי/יצירת לקוח וליד עם התמלול הנוכחי
                        customer, lead, was_created = ci.find_or_create_customer_from_call(
                            str(self.phone_number or ""),
                            self.call_sid or f"live_{int(time.time())}",
                            full_conversation,
                            conversation_data={'conversation_history': self.conversation_history}
                        )
                        
                        # סיכום חכם של השיחה
                        conversation_summary = ci.generate_conversation_summary(
                            full_conversation,
                            {'conversation_history': self.conversation_history}
                        )
                        
                        # עדכון סטטוס אוטומטי
                        new_status = ci.auto_update_lead_status(lead, conversation_summary)
                        
                        # עדכון פתקיות הליד עם התקדמות השיחה הנוכחית
                        if lead.notes:
                            lead.notes += f"\n[Live Call]: {user_text[:100]}... → {bot_reply[:50]}..."
                        else:
                            lead.notes = f"[Live Call]: {user_text[:100]}... → {bot_reply[:50]}..."
                        
                        db.session.commit()
                        
                        # רישום לוגים מפורטים
                        print(f"🎯 Live Call AI Processing: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'})")
                        print(f"📋 Live Summary: {conversation_summary.get('summary', 'N/A')}")
                        print(f"🎭 Live Intent: {conversation_summary.get('intent', 'N/A')}")
                        print(f"📊 Live Status: {new_status}")
                        print(f"⚡ Live Next Action: {conversation_summary.get('next_action', 'N/A')}")
                        
                except Exception as e:
                    print(f"❌ Customer Intelligence background processing failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # הרץ ברקע כדי לא לחסום את השיחה
            thread = threading.Thread(target=process_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Customer Intelligence setup failed: {e}")
            # אל תקריס את השיחה - המשך רגיל