"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib
# Using Flask-Sock for WebSocket handling  
from simple_websocket import ConnectionClosed
from server.stream_state import stream_registry

SR = 8000
# 🎯 פרמטרים מותאמים לשיחה מהירה וחלקה! - OPTIMIZED
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.4"))        # זמן קצר יותר לתגובה מהירה
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "2.5"))        # מקצר מונולוגים
VAD_RMS = int(os.getenv("VAD_RMS", "45"))                   # רגיש יותר לקול רך
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "150"))  # פחות סבלנות = תגובה מהירה
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "30")) # תגובה מיידית!
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "80")) # ללא השהיות
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "250")) # קירור מהיר יותר
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","8"))  # 160ms לפני הפרעה - מהיר!
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
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                    self.last_rx_ts = time.time()
                    self.last_keepalive_ts = time.time()  # ✅ התחל keepalive
                    print(f"🎯 WS_START sid={self.stream_sid} call_sid={self.call_sid} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                    
                    # ✅ ברכה מיידית - בלי השהיה!
                    if not self.tx_running:
                        self.tx_running = True
                        self.tx_thread.start()
                    
                    if not self.greeting_sent:
                        print("🎯 SENDING IMMEDIATE GREETING!")
                        greet = "שלום! אני לאה משי דירות ומשרדים. איך אני יכולה לעזור?"  # קצר וישר
                        self._speak_simple(greet)
                        self.greeting_sent = True
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
                            # ✅ HEBREW-OPTIMIZED: Much higher threshold for Hebrew speech
                            self.vad_threshold = max(200, self.noise_floor * 6.0 + 120)  # Hebrew needs higher threshold
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
                        import numpy as np
                        try:
                            pcm_np = np.frombuffer(pcm16, dtype=np.int16)
                            zero_crossings = np.sum(np.diff(np.sign(pcm_np)) != 0) / len(pcm_np) if len(pcm_np) > 0 else 0
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

                    # ⚡ FIXED BARGE-IN: Prevent false interruptions
                    if self.speaking and BARGE_IN:
                        # ✅ Grace period מאוזן - לא יותר מדי
                        grace_period = 2.0  # 2 שניות - מספיק לגמור משפט
                        time_since_tts_start = current_time - self.speaking_start_ts
                        
                        if time_since_tts_start < grace_period:
                            # Inside grace period - NO barge-in allowed
                            continue
                        
                        # ✅ HEBREW BARGE-IN: Extra high threshold
                        barge_in_threshold = max(500, self.noise_floor * 8.0 + 200) if self.is_calibrated else 600
                        is_barge_in_voice = rms > barge_in_threshold
                        
                        if is_barge_in_voice:
                            self.voice_in_row += 1
                                # ✅ HEBREW SPEECH: Require 1.5s continuous voice to prevent false interrupts
                            if self.voice_in_row >= 75:  # 1500ms (1.5s) of continuous voice - Hebrew needs more time
                                print(f"⚡ BARGE-IN DETECTED (after {time_since_tts_start*1000:.0f}ms)")
                                
                                # ✅ מדידת Interrupt Halt Time
                                interrupt_start = time.time()
                                
                                # ✅ עצירת TTS מיידית - לא עוד פריימים!
                                self.speaking = False
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
                            min_silence = 0.35 if dur > 1.5 else 0.5  # 350-500ms לפי ההנחיות
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
            
        # שלח CLEAR לטוויליו אם החיבור תקין
        if not self.ws_connection_failed:
            try:
                self.tx_q.put_nowait({"type": "clear"})
            except:
                pass
        else:
            print("💔 SKIPPING clear - WebSocket connection failed")
        
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
                print(f"🎤 USER: {text}")
                
                # ✅ מדידת ASR Latency
                if hasattr(self, 'eou_timestamp'):
                    asr_latency = time.time() - self.eou_timestamp
                    print(f"📊 ASR_LATENCY: {asr_latency:.3f}s (target: <0.7s)")
                    
            except Exception as e:
                print(f"❌ STT ERROR: {e}")
                text = ""
            
            if not text.strip():
                text = "אפשר לחזור על זה במשפט קצר?"
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
            
            # ✅ מניעת כפילויות מתקדמת - בדיקת 3 תשובות אחרונות
            if not hasattr(self, 'recent_replies'):
                self.recent_replies = []
            
            # בדוק אם התשובה כבר נאמרה ב-3 התשובות האחרונות
            reply_trimmed = reply.strip()
            if reply_trimmed in self.recent_replies:
                print("🚫 DUPLICATE BOT REPLY detected in recent history - using alternative")
                # תשובות חלופיות מועילות ומגוונות
                alternatives = [
                    "בואו נתקדם עם הפרטים. איזה אזור מעניין אותך הכי הרבה?",
                    "אני כאן לעזור לך למצוא בית חלומות. איזה תקציב יש לך?", 
                    "יש לי דירות מדהימות לכל תקציב. מה חשוב לך יותר - מיקום או גודל?",
                    "בואו נמצא לך משהו מושלם. באיזה שכונה אתה מעוניין?"
                ]
                import random
                reply = random.choice(alternatives)
                reply_trimmed = reply.strip()
                
            # עדכן היסטוריה - שמור רק 3 אחרונות
            self.recent_replies.append(reply_trimmed)
            if len(self.recent_replies) > 3:
                self.recent_replies = self.recent_replies[-3:]
            print(f"🤖 BOT: {reply}")
            
            # ✅ מדידת AI Processing Time
            ai_processing_time = time.time() - ai_processing_start
            print(f"📊 AI_PROCESSING: {ai_processing_time:.3f}s")
            
            # 5. הוסף להיסטוריה
            self.response_history.append({
                'id': conversation_id,
                'user': text,
                'bot': reply,
                'time': time.time()
            })
            
            # PATCH 6: Always speak something
            self._speak_simple(reply)
            
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
                emergency_response = "מצטערת, לא שמעתי טוב בגלל החיבור. אני לאה מ'שי דירות ומשרדים' ויש לי דירות מדהימות במרכז. בואו נתחיל מחדש - איזה סוג נכס אתה מחפש ובאיזה אזור?"
                self._speak_with_breath(emergency_response)
                self.state = STATE_LISTEN
                print(f"✅ RETURNED TO LISTEN STATE after error in conversation #{conversation_id}")
            except Exception as emergency_err:
                print(f"❌ EMERGENCY RESPONSE FAILED: {emergency_err}")
                self.state = STATE_LISTEN
                # ✅ חזור למצב האזנה בכל מקרה


    # ✅ דיבור מתקדם עם סימונים לטוויליו
    def _speak_simple(self, text: str):
        """TTS עם מעקב מצבים וסימונים"""
        if not text:
            return
            
        if self.speaking:
            print("🚫 Already speaking - stopping current and starting new")
            # ✅ עצור TTS נוכחי והתחל חדש
            self.speaking = False
            self.state = STATE_LISTEN
            time.sleep(0.05)  # המתנה קצרה
            
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
            # המתנה קצרה לתחושת טבעיות
            time.sleep(random.uniform(0.2, 0.4))
                
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
            print(f"🔊 TTS ERROR: {e} - sending beep")
            self._send_beep(800)
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
        
        # ✅ LONGER timeout to prevent premature cutoff
        def mark_timeout():
            time.sleep(0.5)  # 500ms timeout (longer)
            if self.mark_pending and (time.time() - self.mark_sent_ts) > 0.45:
                print("⚠️ TTS_MARK_TIMEOUT -> LISTENING") 
                self._finalize_speaking()
        
        import threading
        threading.Thread(target=mark_timeout, daemon=True).start()

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
            
        except Exception as e:
            print(f"⚠️ Audio processing failed, using simple resample: {e}")
            # Fallback: resample פשוט ל-16kHz
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
            print(f"🎤 STT_START: Processing {len(pcm16_8k)} bytes with Google STT Streaming Hebrew")
            
            # Check if audio has sufficient content for recognition
            try:
                import audioop
                max_amplitude = audioop.max(pcm16_8k, 2)
                rms = audioop.rms(pcm16_8k, 2)
                print(f"📊 AUDIO_STATS: max_amplitude={max_amplitude}, rms={rms}, duration={len(pcm16_8k)/(2*8000):.1f}s")
                
                # ✅ הגדלת VAD threshold - מניעת זיהוי רעש כקול 
                if max_amplitude < 100:  # מאוזן - יזהה דיבור רך אבל לא רעש רקע
                    print("🔇 STT_SKIP: Audio too quiet (likely background noise)")
                    return ""  # החזר ריק עבור רעש
                    
            except Exception as e:
                print(f"⚠️ Audio analysis failed: {e}")
            
            from server.services.lazy_services import get_stt_client
            from google.cloud import speech
            
            client = get_stt_client()
            if not client:
                print("❌ Google STT client not available - fallback to Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            # ✅ FIXED Google STT Configuration - use default model for Hebrew
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,  # Keep 8kHz for telephony
                language_code="he-IL",   # Hebrew Israel
                # NO MODEL specified - use default for Hebrew (latest_short not supported)
                use_enhanced=True,       # Better quality
                enable_automatic_punctuation=True,
                speech_contexts=[        # ✅ Hebrew real estate terms
                    speech.SpeechContext(phrases=[
                        "שי דירות ומשרדים", "לאה", "סוכנת נדלן",
                        "תל אביב", "רמת גן", "רמלה", "לוד", "בית שמש", 
                        "מודיעין", "פתח תקווה", "רחובות", "הרצליה",
                        "דירה", "חדרים", "שכירות", "קניה", "משכנתא",
                        "תקציב", "שקל", "אלף", "מיליון", "נדלן", 
                        "שלום", "כן", "לא", "בסדר", "נהדר", "לאה"  # הוסרתי 'תודה' - גורם לזיהוי שקר
                    ])
                ]
            )
            
            # Single request recognition (לא streaming למבע קצר)
            audio = speech.RecognitionAudio(content=pcm16_8k)
            
            # ✅ FAST timeout for real-time conversation
            response = client.recognize(
                config=recognition_config,
                audio=audio,
                timeout=1.5  # ✅ FASTER: 1.5 seconds max for real-time
            )
            
            if response.results and response.results[0].alternatives:
                hebrew_text = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                print(f"✅ GOOGLE_STT_SUCCESS: '{hebrew_text}' (confidence: {confidence:.2f})")
                return hebrew_text
            else:
                print("❌ Google STT returned no results - fallback to Whisper")
                return self._whisper_fallback(pcm16_8k)
                
        except Exception as e:
            print(f"❌ GOOGLE_STT_ERROR: {e} - fallback to Whisper")
            return self._whisper_fallback(pcm16_8k)
    
    def _whisper_fallback(self, pcm16_8k: bytes) -> str:
        """Whisper fallback for Google STT failures"""
        try:
            print(f"🔄 WHISPER_FALLBACK: Processing {len(pcm16_8k)} bytes")
            
            # Check if audio has actual content
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            print(f"📊 AUDIO_ANALYSIS: max_amplitude={max_amplitude}, rms={rms}")
            
            if max_amplitude < 200 or rms < 150:  # HEBREW: Much stricter threshold 
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
            
            # ✅ זיהוי לולאות משופר - מניעת חזרות
            if len(self.conversation_history) >= 2:
                last_responses = [item['bot'] for item in self.conversation_history[-4:]]  # בדוק 4 אחרונים
                # בדוק האם יש יותר מידי דמיון
                response_count = {}
                for resp in last_responses:
                    key_words = ' '.join(resp.split()[:5])  # 5 מילים ראשונות
                    response_count[key_words] = response_count.get(key_words, 0) + 1
                    if response_count[key_words] >= 2:
                        print(f"🚫 RESPONSE_LOOP_DETECTED: Preventing repetitive responses")
                        if "תודה" in hebrew_text:
                            return "איזה אזור מעניין אותך?"
                        else:
                            return "איזה סוג נכס אתה מחפש?"
                    
            # 📜 הקשר מהיסטוריה (להבנה טובה יותר)
            history_context = ""
            if self.conversation_history:
                recent = self.conversation_history[-2:]  # 2 אחרונים
                history_context = "הקשר שיחה: "
                for turn in recent:
                    history_context += f"לקוח אמר: '{turn['user'][:40]}' ענינו: '{turn['bot'][:40]}' | "
            
            # 🎯 זיהוי אזור מהבקשה
            requested_area = self._detect_area(hebrew_text) or ""
            
            # ✅ בדיקת מידע שנאסף לתיאום פגישה
            lead_info = self._analyze_lead_completeness()
            
            # ✅ אם זו השיחה הראשונה - ברכה מלאה
            is_first_call = len(self.conversation_history) == 0
            
            if is_first_call:
                greeting_prompt = """את סוכנת נדלן של "שי דירות ומשרדים". 
                
                התחילי בברכה חמה: "שלום! אני לאה מ'שי דירות ומשרדים'. אני כאן לעזור לך למצוא את הנכס המושלם!"
                
                אחרי הברכה שאלי שאלה אחת: "איזה אזור מעניין אותך?"""
            else:
                greeting_prompt = """את סוכנת נדלן מקצועית. אל תזכירי שוב את שמך או את שם החברה.
                
                תני תגובה ישירה ומוקדת למה שהלקוח אומר."""
            
            # ✅ פרומפט נקי ללא ברכות חוזרות
            smart_prompt = f"""{greeting_prompt}

מטרה: לאסוף את הפרטים - אזור, סוג נכס, תקציב, זמן כניסה, שם וטלפון.

תשובות טובות:
- תני מידע מקצועי על האזור
- הסבירי למה את שואלת
- שאלי שאלה אחת בסוף

אזור מזוהה: {requested_area or 'לא ידוע'}
מידע נאסף: {lead_info['summary']}
היסטוריה: {history_context}

{lead_info['meeting_prompt']}

הלקוח אומר: "{hebrew_text}"
תגובה (40-60 מילים, תשובה מלאה ומועילה + שאלה אחת בסוף):"""

            # ✅ GPT-4o MINI מהיר יותר לשיחה חיה!
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",      # Fast model
                    messages=[
                        {"role": "system", "content": smart_prompt},
                        {"role": "user", "content": hebrew_text}
                    ],
                    max_tokens=120,           # ✅ אפשר תשובות יותר מלאות
                    temperature=0.2,          # ✅ More consistent responses
                    timeout=1.5               # ✅ SUPER FAST: 1.5 seconds max!
                )
            except Exception as e:
                print(f"⏰ AI timeout/error ({e}) - FAST emergency response")
                # ✅ CLEAN emergency response - NO retry needed for speed
                if requested_area and requested_area.strip():
                    return f"סליחה! איזה סוג דירה אתה מחפש ב{requested_area}?"
                elif "תודה" in hebrew_text:
                    return "בשמחה! יש לי עוד אפשרויות אם אתה מעוניין."
                else:
                    return "איזה אזור מעניין אותך? יש לי נכסים במרכז הארץ."
            
            content = response.choices[0].message.content
            if content and content.strip():
                ai_answer = content.strip()
                
                # ✅ אל תקצר מדי - תן לה לתת תשובות מלאות!
                words = ai_answer.split()
                if len(words) > 16:  # מקס 16 מילים - קצר ויעיל!
                    # קיצור חכם - שמור על משמעות ושאלה
                    if '?' in ai_answer:
                        first_question = ai_answer.split('?')[0] + '?'
                        if len(first_question.split()) <= 16:
                            ai_answer = first_question
                        else:
                            ai_answer = ' '.join(words[:14]) + '?'
                    else:
                        ai_answer = ' '.join(words[:14]) + '?'
                    print(f"🔪 SHORTENED: {len(words)} → {len(ai_answer.split())} words")
                
                # ✅ חסימת תגובות גנריות וקליטות - עודד ספציפיות
                generic_phrases = [
                    "איך אפשר לעזור", "אני צריכה עוד פרטים", "תודה רבה", "שמחתי לעזור", 
                    "תמיד פה", "יש לי דירה", "אני מציעה", "5 חדרים", "3 חדרים"
                ]
                if (any(phrase in ai_answer for phrase in generic_phrases) or 
                    len(ai_answer.strip()) < 10 or ai_answer.count('?') > 1):
                    # תשובה ספציפית יותר לפי הקשר
                    if requested_area:
                        ai_answer = f"מעולה! {requested_area} אזור מבוקש. איזה סוג נכס אתה מחפש?"
                    else:
                        ai_answer = "שלום! אני לאה. באיזה אזור אתה מעוניין?"
                    print(f"🚫 BLOCKED_GENERIC: Using specific question")
                
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
                print("AI returned empty response - should not happen with good prompt")
                # ✅ תגובת חירום חכמה רק אם באמת אין תוכן
                if requested_area:
                    return f"איזה סוג דירה אתה מחפש ב{requested_area}? יש לי כמה אפשרויות מעניינות."
                else:
                    return "איזה אזור מעניין אותך? יש לי דירות במרכז הארץ, מרכז-דרום ואזור ירושלים."
            
        except Exception as e:
            print(f"AI_ERROR: {e} - Using intelligent emergency response")
            # ✅ תגובת חירום חכמה על בסיס זיהוי האזור
            emergency_area = self._detect_area(hebrew_text) or ""
            print(f"🚨 CRITICAL AI_ERROR for: '{hebrew_text}' - detected area: {emergency_area}")
            if emergency_area:
                return f"מצטערת להשהיה! איזה סוג דירה אתה מחפש ב{emergency_area}? יש לי כמה אפשרויות."
            elif "תודה" in hebrew_text or "ביי" in hebrew_text:
                return "תודה רבה! אני כאן לכל שאלה."
            elif any(word in hebrew_text for word in ["שלום", "היי", "הלו"]):
                return "שלום! אני לאה משי דירות ומשרדים. איך אני יכולה לעזור?"
            else:
                return "איזה אזור מעניין אותך? יש לי דירות במרכז הארץ, מרכז-דרום ואזור ירושלים."
    
    def _hebrew_tts(self, text: str) -> bytes | None:
        """Hebrew Text-to-Speech using Google Cloud TTS with Wavenet voice"""
        try:
            print(f"🔊 TTS_START: Generating Hebrew TTS with Google Wavenet for '{text[:50]}...' (length: {len(text)} chars)")
            from server.services.lazy_services import get_tts_client
            from google.cloud import texttospeech
            
            client = get_tts_client()
            if not client:
                print("❌ Google TTS client not available")
                return None
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="he-IL",
                name="he-IL-Wavenet-A"  # ✅ Wavenet - הקול הטוב ביותר לעברית
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                speaking_rate=1.4,   # מהיר יותר לשיחה חלקה
                pitch=0.0,           # טון טבעי
                effects_profile_id=["telephony-class-application"]  # אופטימיזציה לטלפון
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            print(f"✅ TTS_SUCCESS: Generated {len(response.audio_content)} bytes of Wavenet audio ({len(response.audio_content)/16000:.1f}s estimated)")
            return response.audio_content
            
        except Exception as e:
            print(f"❌ TTS_CRITICAL_ERROR: {e}")
            print(f"   Text was: '{text}'")
            print(f"   Check Google Cloud credentials!")
            # ✅ תיקון קריטי: אל תקריס - המשך לעבוד
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
        
        # תיאום פגישה אם יש לפחות 3 שדות
        meeting_ready = completed_fields >= 3
        
        # יצירת סיכום
        summary_parts = []
        if collected_info['area']: summary_parts.append('אזור')
        if collected_info['property_type']: summary_parts.append('סוג נכס')
        if collected_info['budget']: summary_parts.append('תקציב')
        if collected_info['timing']: summary_parts.append('זמן')
        if collected_info['contact']: summary_parts.append('קשר')
        
        summary = f"{len(summary_parts)}/5 שדות: {', '.join(summary_parts) if summary_parts else 'אין'}"
        
        # הודעה לתיאום פגישה
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
        else:
            missing = 3 - completed_fields
            meeting_prompt = f"צריך עוד {missing} שדות מידע לפני תיאום פגישה."
        
        return {
            'collected': collected_info,
            'completed_count': completed_fields,
            'meeting_ready': meeting_ready,
            'summary': summary,
            'meeting_prompt': meeting_prompt
        }