"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib, asyncio
import builtins
from server.services.mulaw_fast import mulaw_to_pcm16_fast

# ⚡ PHASE 1: DEBUG mode - חונק כל print ב-hot path
DEBUG = os.getenv("DEBUG", "0") == "1"
_orig_print = builtins.print

def _dprint(*args, **kwargs):
    """Print only when DEBUG=1 (gating for hot path)"""
    if DEBUG:
        _orig_print(*args, **kwargs)

def force_print(*args, **kwargs):
    """Always print (for critical errors only)"""
    _orig_print(*args, **kwargs)

# חונקים כל print במודול הזה כש-DEBUG=0
builtins.print = _dprint

# ⚡ PHASE 1 Task 4: טלמטריה - 4 מדדים בכל TURN
import logging
_now_ms = lambda: int(time.time() * 1000)

def emit_turn_metrics(first_partial, final_ms, tts_ready, total, barge_in=False, eou_reason="unknown"):
    """
    ⚡ PHASE 1: Emit turn latency metrics (non-blocking, uses async logger)
    
    Critical metrics for performance monitoring:
    - STT_FIRST_PARTIAL_MS: Time to first partial from STT
    - STT_FINAL_MS: Time to final/EOU
    - TTS_READY_MS: Time until TTS audio is ready
    - TOTAL_LATENCY_MS: Time until first audio frame sent
    """
    payload = {
        "STT_FIRST_PARTIAL_MS": first_partial,
        "STT_FINAL_MS": final_ms,
        "TTS_READY_MS": tts_ready,
        "TOTAL_LATENCY_MS": total,
        "BARGE_IN_HIT": barge_in,
        "EOU_REASON": eou_reason
    }
    logging.getLogger("turn").info(json.dumps(payload, ensure_ascii=False))

# ⚡ STREAMING STT: דיפולט מופעל בקוד, כדי שלא ניפול לסינגל-ריקווסט אם ENV לא נטען
USE_STREAMING_STT = True
if os.getenv("ENABLE_STREAMING_STT", "").lower() in ("false", "0", "no"):
    USE_STREAMING_STT = False

# ✅ CRITICAL: App Singleton - create ONCE for entire process lifecycle
# This prevents Flask app recreation per-call which caused 5-6s delays and 503 errors
_flask_app_singleton = None
_flask_app_lock = threading.Lock()

def _get_flask_app():
    """Get or create Flask app singleton - prevents app recreation per-call"""
    global _flask_app_singleton
    if _flask_app_singleton is None:
        with _flask_app_lock:
            if _flask_app_singleton is None:  # Double-check after acquiring lock
                from server.app_factory import create_app
                _flask_app_singleton = create_app()
                force_print("✅ Flask app singleton created for media handlers")
    return _flask_app_singleton

# ⚡ BUILD 116: אופטימיזציות לזמן תגובה <2s
print("="*80)
print("⚡ BUILD 116 - SUB-2S RESPONSE OPTIMIZATION + PHASE 1")
print("="*80)
print(f"[BOOT] DEBUG = {DEBUG}")
print(f"[BOOT] USE_STREAMING_STT = {USE_STREAMING_STT}")
print(f"[BOOT] GOOGLE_CLOUD_REGION = {os.getenv('GOOGLE_CLOUD_REGION', 'europe-west1')}")
print(f"[BOOT] GCP_STT_MODEL = {os.getenv('GCP_STT_MODEL', 'phone_call')} (ENHANCED=True enforced)")
print(f"[BOOT] GCP_STT_LANGUAGE = {os.getenv('GCP_STT_LANGUAGE', 'he-IL')}")
print(f"[BOOT] STT_BATCH_MS = {os.getenv('STT_BATCH_MS', '40')}")
print(f"[BOOT] STT_PARTIAL_DEBOUNCE_MS = {os.getenv('STT_PARTIAL_DEBOUNCE_MS', '90')}")
print(f"[BOOT] VAD_HANGOVER_MS = {os.getenv('VAD_HANGOVER_MS', '180')}")
print(f"[BOOT] UTTERANCE_TIMEOUT = 320ms (aggressive for sub-2s response)")
print("="*80)

if USE_STREAMING_STT:
    print("🚀 STT MODE: Real-time Streaming (Session-per-call)")
else:
    print("⚠️  WARNING: STT MODE is Single-request (SLOW!) - Set ENABLE_STREAMING_STT=true")
    print("📝 STT MODE: Single-request (fast μ-law + optimized Google STT)")

# ⚡ THREAD-SAFE SESSION REGISTRY for multi-call support
# Each call_sid has its own session + dispatcher state
_sessions_registry = {}  # call_sid -> {"session": StreamingSTTSession, "utterance": {...}, "tenant": str, "ts": float}
_registry_lock = threading.RLock()
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "50"))

def _register_session(call_sid: str, session, tenant_id=None):
    """Register a new STT session for a call (thread-safe)"""
    with _registry_lock:
        if len(_sessions_registry) >= MAX_CONCURRENT_CALLS:
            raise RuntimeError(f"Over capacity: {len(_sessions_registry)}/{MAX_CONCURRENT_CALLS} calls")
        _sessions_registry[call_sid] = {
            "session": session,
            "utterance": {
                "id": None, 
                "partial_cb": None, 
                "final_buf": None,
                "final_received": None,  # ⚡ NEW: Event for waiting on final
                "last_partial": ""  # ⚡ NEW: Backup partial text
            },
            "tenant": tenant_id,
            "ts": time.time()
        }
        if DEBUG: print(f"✅ [REGISTRY] Registered session for call {call_sid[:8]}... (tenant: {tenant_id}, total: {len(_sessions_registry)})")

def _get_session(call_sid: str):
    """Get STT session for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.get(call_sid)
        return item["session"] if item else None

def _get_utterance_state(call_sid: str):
    """Get utterance state for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.get(call_sid)
        return item["utterance"] if item else None

def _close_session(call_sid: str):
    """Close and remove STT session for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.pop(call_sid, None)
    
    if item:
        try:
            item["session"].close()
            if DEBUG: print(f"✅ [REGISTRY] Closed session for call {call_sid[:8]}... (remaining: {len(_sessions_registry)})")
        except Exception as e:
            if DEBUG: print(f"⚠️ [REGISTRY] Error closing session for {call_sid[:8]}...: {e}")

def _create_dispatcher_callbacks(call_sid: str):
    """Create partial/final callbacks that route to the correct call's utterance"""
    def on_partial(text: str):
        utt = _get_utterance_state(call_sid)
        if utt:
            # ⚡ BUILD 112: Save last partial as backup and log it
            with _registry_lock:
                utt["last_partial"] = text
            if DEBUG: print(f"🟡 [PARTIAL] '{text}' saved for {call_sid[:8]}... (utterance: {utt.get('id', '???')})")
            
            # ⚡ BUILD 114: Early Finalization - if partial is strong enough, trigger final AND continue
            # This saves 400-600ms by triggering final event early
            if text and len(text) > 15 and text.rstrip().endswith(('.', '?', '!')):
                if DEBUG: print(f"⚡ [EARLY_FINALIZE] Strong partial detected: '{text}' → triggering final event")
                # Trigger final event (but continue to call partial callback)
                final_event = utt.get("final_received")
                if final_event:
                    final_event.set()
            
            # Call the utterance's partial callback
            cb = utt.get("partial_cb")
            if cb:
                try:
                    cb(text)
                except Exception as e:
                    print(f"⚠️ Partial callback error for {call_sid[:8]}...: {e}")
    
    def on_final(text: str):
        utt = _get_utterance_state(call_sid)
        if utt:
            buf = utt.get("final_buf")
            if buf is not None:
                buf.append(text)
                if DEBUG: print(f"✅ [FINAL] '{text}' received for {call_sid[:8]}... (utterance: {utt.get('id', '???')})")
                
                # ⚡ Signal that final has arrived!
                final_event = utt.get("final_received")
                if final_event:
                    final_event.set()
                    if DEBUG: print(f"📢 [FINAL_EVENT] Set for {call_sid[:8]}...")
    
    return on_partial, on_final

def _cleanup_stale_sessions():
    """Cleanup sessions that haven't received audio for >2 minutes (edge case protection)"""
    STALE_TIMEOUT = 120  # 2 minutes
    current_time = time.time()
    
    with _registry_lock:
        stale_call_sids = [
            call_sid for call_sid, item in _sessions_registry.items()
            if current_time - item["ts"] > STALE_TIMEOUT
        ]
    
    for call_sid in stale_call_sids:
        if DEBUG: print(f"🧹 [REAPER] Cleaning stale session: {call_sid[:8]}... (inactive for >{STALE_TIMEOUT}s)")
        _close_session(call_sid)

# Start session reaper thread
def _start_session_reaper():
    """Background thread that cleans up stale sessions every 60s"""
    def reaper_loop():
        while True:
            time.sleep(60)  # Check every 60 seconds
            try:
                _cleanup_stale_sessions()
            except Exception as e:
                print(f"⚠️ [REAPER] Error during cleanup: {e}")
    
    reaper_thread = threading.Thread(target=reaper_loop, daemon=True, name="SessionReaper")
    reaper_thread.start()
    print("🧹 [REAPER] Session cleanup thread started")

# Start reaper on module load (only if streaming enabled)
if USE_STREAMING_STT:
    _start_session_reaper()

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
# ⚡ BUILD 114: VAD OPTIMIZED FOR SPEED (Streaming STT enabled, ≤2s latency target)
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.6"))        # ⚡ 0.6s - מאפשר תגובות קצרות כמו "כן"
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "12.0"))       # ✅ 12.0s - זמן מספיק לתיאור נכסים מפורט
VAD_RMS = int(os.getenv("VAD_RMS", "65"))                   # ✅ פחות רגיש לרעשים - מפחית קטיעות שגויות
BARGE_IN = os.getenv("BARGE_IN", "true").lower() == "true"
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "180"))  # ⚡ BUILD 116: 180ms - aggressive for sub-2s response
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "50")) # ⚡ SPEED: 50ms במקום 80ms - תגובה מהירה
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "120")) # ⚡ SPEED: 120ms במקום 200ms - פחות המתנה
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "1100")) # ⚡ BUILD 107: 1100ms - קירור מהיר יותר
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
        
        # ⚡ BUILD 109: Smart barge-in - disable for long responses
        self.long_response = False       # האם התשובה ארוכה (>20 מילים)
        
        # ✅ BUILD 117: WebSocket Keepalive with more frequent pings
        self.last_keepalive_ts = 0.0     # זמן keepalive אחרון
        self.keepalive_interval = 10.0   # ✅ שלח כל 10 שניות (was 18s) - prevents timeouts
        self.heartbeat_counter = 0       # מונה heartbeat
        
        # ⚡ BUILD 116: Enhanced telemetry - track every stage
        self.t0_connected = 0.0          # [T0] WebSocket connected
        self.t1_greeting_start = 0.0     # [T1] Greeting started
        self.t2_greeting_end = 0.0       # [T2] Greeting last frame sent
        self.s1_stream_opened = 0.0      # [S1] STT stream opened
        self.s2_first_partial = 0.0      # [S2] First partial received
        self.s3_final = 0.0              # [S3] Final text received
        self.a1_ai_start = 0.0           # [A1] AI processing started
        self.a2_ai_done = 0.0            # [A2] AI response ready
        self.v1_tts_start = 0.0          # [V1] TTS synthesis started
        self.v2_tts_done = 0.0           # [V2] TTS synthesis completed
        self.tx_first_frame = 0.0        # [TX] First reply frame sent
        
        # TX Queue for smooth audio transmission
        # ⚡ BUILD 115.1: Reduced to 120 frames (~2.4s buffer) to prevent lag
        self.tx_q = queue.Queue(maxsize=120)
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._last_overflow_log = 0.0  # For throttled logging
        
        print("🎯 AI CONVERSATION STARTED")
        
        # מאפיינים לזיהוי עסק
        self.business_id = None  # ✅ יזוהה דינמית לפי to_number
        self.phone_number = None
        
        # ⚡ DTMF phone collection (digits gathered from keypad)
        self.dtmf_buffer = ""  # Accumulated digits from phone keypad
        self.waiting_for_dtmf = False  # Are we waiting for phone input?
        self.dtmf_purpose = None  # What are we collecting? 'phone', etc.
        
        # היסטוריית שיחה למעקב אחר הקשר
        self.conversation_history = []  # רשימה של הודעות {'user': str, 'bot': str}
        self.turn_count = 0  # ⚡ Phase 2C: Track turns for first-turn optimization
        
        # ✅ CRITICAL: Track background threads for proper cleanup
        self.background_threads = []
        
        # ⚡ BUILD 115: Async executor for non-blocking fallback STT
        from concurrent.futures import ThreadPoolExecutor
        self.loop = None  # Will be set when needed
        self.exec = ThreadPoolExecutor(max_workers=1)  # Per-call executor
        self.events_q = None  # Will be created if async mode is used
        
        # ⚡ STREAMING STT: Will be initialized after business identification (in "start" event)

    def _init_streaming_stt(self):
        """
        ⚡ BUILD 114: Initialize streaming STT with retry mechanism
        3 attempts before falling back to single-request mode
        """
        if not USE_STREAMING_STT or not self.call_sid:
            return
        
        from server.services.gcp_stt_stream import StreamingSTTSession
        
        # ⚡ RETRY MECHANISM: 3 attempts before fallback
        for attempt in range(3):
            try:
                # Create dispatcher callbacks for this specific call
                on_partial, on_final = _create_dispatcher_callbacks(self.call_sid)
                
                # Create session
                session = StreamingSTTSession(
                    on_partial=on_partial,
                    on_final=on_final
                )
                
                # Register in thread-safe registry
                _register_session(self.call_sid, session, tenant_id=self.business_id)
                
                self.s1_stream_opened = time.time()  # ⚡ [S1] STT stream opened
                if DEBUG: print(f"✅ [S1={self.s1_stream_opened:.3f}] Streaming session started for call {self.call_sid[:8]}... (business: {self.business_id}, attempt: {attempt+1}, Δ={(self.s1_stream_opened - self.t0_connected)*1000:.0f}ms from T0)")
                return  # Success!
                
            except RuntimeError as e:
                if DEBUG: print(f"🚨 [STT] Over capacity (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(0.2)  # Brief delay before retry
                    continue
                # Don't crash - will use fallback STT
                return
                
            except Exception as e:
                if DEBUG: print(f"⚠️ [STT] Streaming start failed (attempt {attempt+1}/3): {e}", flush=True)
                if attempt < 2:
                    time.sleep(0.2)  # Brief delay before retry
                    continue
                if DEBUG:
                    import traceback
                    traceback.print_exc()
                return
        
        # If we get here, all 3 attempts failed
        if DEBUG: print(f"❌ [STT] All streaming attempts failed for call {self.call_sid[:8]} → using fallback single request", flush=True)
    
    def _close_streaming_stt(self):
        """Close streaming STT session at end of call"""
        if self.call_sid:
            _close_session(self.call_sid)
    
    def _utterance_begin(self, partial_cb=None):
        """
        Mark start of new utterance.
        Switches dispatcher target to new utterance buffer.
        """
        import uuid
        import threading
        
        if not self.call_sid:
            return
        
        utt_state = _get_utterance_state(self.call_sid)
        if utt_state is not None:
            with _registry_lock:
                utt_state["id"] = uuid.uuid4().hex[:8]
                utt_state["partial_cb"] = partial_cb
                utt_state["final_buf"] = []
                utt_state["final_received"] = threading.Event()  # ⚡ NEW: wait for final
                utt_state["last_partial"] = ""  # ⚡ NEW: save last partial as backup
            
            if DEBUG: print(f"🎤 [{self.call_sid[:8]}] Utterance {utt_state['id']} BEGIN")
    
    def _utterance_end(self, timeout=0.850):
        """
        Mark end of utterance.
        ⚡ BUILD 118: Increased timeout to 850ms - streaming STT needs time for final results
        """
        if not self.call_sid:
            print("⚠️ _utterance_end: No call_sid")
            return ""
        
        utt_state = _get_utterance_state(self.call_sid)
        if utt_state is None:
            print(f"⚠️ _utterance_end: No utterance state for call {self.call_sid[:8]}")
            return ""
        
        utt_id = utt_state.get("id", "???")
        print(f"🎤 [{self.call_sid[:8]}] _utterance_end: Collecting results for utterance {utt_id} (timeout={timeout}s)")
        
        # ⚡ BUILD 118: Wait 850ms for streaming results - allows time for final transcription
        # Streaming STT enabled by default → fast partial results
        wait_start = time.time()
        wait_duration = 0.0
        final_event = utt_state.get("final_received")
        if final_event:
            got_final = final_event.wait(timeout=timeout)  # 850ms wait for streaming
            wait_duration = time.time() - wait_start
            if got_final:
                print(f"✅ [{self.call_sid[:8]}] Got final event in {wait_duration:.3f}s")
            else:
                print(f"⚠️ [{self.call_sid[:8]}] Timeout after {wait_duration:.3f}s - using fallback")  
        
        # Collect text - prioritize partial over finals
        with _registry_lock:
            # ⚡ PRIMARY: Use last partial (this is what we actually get!)
            last_partial = utt_state.get("last_partial", "")
            
            # FALLBACK: Check finals buffer (rarely populated)
            finals = utt_state.get("final_buf") or []
            finals_text = " ".join(finals).strip()
            
            # Use partial if available, otherwise finals
            if last_partial:
                text = last_partial
                print(f"✅ [{self.call_sid[:8]}] Using partial: '{text[:50]}...' ({len(text)} chars)")
            elif finals_text:
                text = finals_text
                print(f"✅ [{self.call_sid[:8]}] Using final: '{text[:50]}...' ({len(text)} chars)")
            else:
                text = ""
                print(f"⚠️ [{self.call_sid[:8]}] No text available - returning empty")
            
            # Reset dispatcher
            utt_state["id"] = None
            utt_state["partial_cb"] = None
            utt_state["final_buf"] = None
            utt_state["final_received"] = None
            utt_state["last_partial"] = ""
        
        # ⚡ BUILD 114: Detailed latency logging
        print(f"🏁 [{self.call_sid[:8]}] Utterance {utt_id} COMPLETE: returning '{text[:30] if text else '(empty)'}'")
        print(f"[LATENCY] final_wait={wait_duration:.2f}s, utterance_total={time.time() - wait_start:.2f}s")
        
        return text

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
                        
                        # 🔍 DEBUG: Log phone numbers from customParameters
                        print(f"\n📞 START EVENT (customParameters path):")
                        print(f"   customParams.From: {custom_params.get('From')}")
                        print(f"   customParams.CallFrom: {custom_params.get('CallFrom')}")
                        print(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        print(f"   ✅ self.to_number set to: '{self.to_number}'")
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                        self.phone_number = evt.get("from") or evt.get("phone_number")
                        self.to_number = evt.get("to") or evt.get("called")
                        
                        # 🔍 DEBUG: Log phone number on start
                        print(f"\n📞 START EVENT - Phone numbers:")
                        print(f"   from field: {evt.get('from')}")
                        print(f"   phone_number field: {evt.get('phone_number')}")
                        print(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        
                    self.last_rx_ts = time.time()
                    self.last_keepalive_ts = time.time()  # ✅ התחל keepalive
                    self.t0_connected = time.time()  # ⚡ [T0] WebSocket connected
                    print(f"🎯 [T0={time.time():.3f}] WS_START sid={self.stream_sid} call_sid={self.call_sid} from={self.phone_number} to={getattr(self, 'to_number', 'N/A')} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                    
                    # ⚡ OPTIMIZED: זיהוי עסק + ברכה בשאילתה אחת!
                    try:
                        app = _get_flask_app()  # ✅ Use singleton
                        with app.app_context():
                            business_id, greet = self._identify_business_and_get_greeting()
                        print(f"⚡ FAST: business_id={business_id}, greeting loaded in single query!")
                    except Exception as e:
                        print(f"❌ CRITICAL ERROR in business identification: {e}")
                        import traceback
                        traceback.print_exc()
                        self.business_id = 1
                        greet = "שלום! איך אפשר לעזור?"
                    
                    # ⚡ STREAMING STT: Initialize NOW (after business_id is known)
                    self._init_streaming_stt()
                    
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
                        self.t1_greeting_start = time.time()  # ⚡ [T1] Greeting start
                        print(f"🎯 [T1={self.t1_greeting_start:.3f}] SENDING IMMEDIATE GREETING! (Δ={(self.t1_greeting_start - self.t0_connected)*1000:.0f}ms from T0)")
                        try:
                            self._speak_greeting(greet)  # ✅ פונקציה מיוחדת לברכה ללא sleep!
                            self.t2_greeting_end = time.time()  # ⚡ [T2] Greeting end
                            print(f"🎯 [T2={self.t2_greeting_end:.3f}] GREETING_COMPLETE! (Duration={(self.t2_greeting_end - self.t1_greeting_start)*1000:.0f}ms)")
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
                    # ⚡ SPEED: Fast μ-law decode using lookup table (~10-20x faster)
                    pcm16 = mulaw_to_pcm16_fast(mulaw)
                    self.last_rx_ts = time.time()
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    
                    # ⚡ STREAMING STT: Feed audio to session (continuous streaming)
                    if self.call_sid and pcm16:
                        session = _get_session(self.call_sid)
                        if session:
                            session.push_audio(pcm16)
                            # Update session timestamp to prevent cleanup
                            with _registry_lock:
                                item = _sessions_registry.get(self.call_sid)
                                if item:
                                    item["ts"] = time.time()
                        elif USE_STREAMING_STT:
                            # ⚠️ Session should exist but doesn't!
                            if not hasattr(self, '_session_warning_logged'):
                                print(f"⚠️ [STT] No streaming session for {self.call_sid[:8]} - using fallback")
                                self._session_warning_logged = True
                    
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

                    # ⚡ BUILD 109: SMART BARGE-IN - Disable for long responses, enable for short ones
                    # ⚡ BUILD 121: DISABLE barge-in when waiting for DTMF input!
                    if self.speaking and BARGE_IN and not self.waiting_for_dtmf:
                        # 🧠 SMART: If response is long (>20 words), DISABLE barge-in completely!
                        if self.long_response:
                            # 🔒 Long response - let it finish! No interruptions allowed
                            continue
                        
                        # 🔓 Short response - allow barge-in with grace period
                        grace_period = 2.5  # ✅ BUILD 117: 2.5 שניות למנוע קטיעות
                        time_since_tts_start = current_time - self.speaking_start_ts
                        
                        if time_since_tts_start < grace_period:
                            # Inside grace period - NO barge-in allowed
                            continue
                        
                        # ✅ BUILD 117: ULTRA-HIGH threshold to prevent false interrupts
                        barge_in_threshold = max(1500, self.noise_floor * 18.0 + 600) if self.is_calibrated else 1800
                        is_barge_in_voice = rms > barge_in_threshold
                        
                        if is_barge_in_voice:
                            self.voice_in_row += 1
                            # ✅ BUILD 117: Require 2000ms continuous LOUD voice - very strict!
                            if self.voice_in_row >= 100:  # 2000ms קול רציף חזק - ממש ממש בטוח!
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
                                        self._tx_enqueue({"type": "clear"})
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
                            # ⚡ STREAMING STT: Mark start of new utterance (once) + save partial text
                            if len(self.buf) == 0 and is_strong_voice:
                                # Callback to save partial text for early EOU detection
                                def save_partial(text):
                                    self.last_partial_text = text
                                    print(f"🔊 PARTIAL: '{text}'")
                                
                                self.last_partial_text = ""  # Reset
                                self._utterance_begin(partial_cb=save_partial)
                            
                            self.buf.extend(pcm16)
                            dur = len(self.buf) / (2 * SR)
                            
                            # ⚡ BUILD 107: ULTRA-LOW LATENCY - 0.5s silence for FAST responses
                            # תגובות קצרות: min_silence קצר מאוד (0.5s) ⚡⚡⚡
                            # משפטים ארוכים: min_silence קצר (1.8s במקום 3.0s)
                            if dur < 2.0:
                                min_silence = 0.5  # ⚡ תגובה קצרה - סופר מהר! (חצי שניה!)
                            else:
                                min_silence = 1.8  # ⚡ משפט ארוך - מהיר (במקום 3.0s)
                            
                            silent = silence_time >= min_silence  
                            too_long = dur >= MAX_UTT_SEC
                            min_duration = 0.6  # ⚡ BUILD 107: מינימום קצר יותר - 0.6s במקום 0.7s
                            
                            # ⚡ BUILD 107: באפר קטן יותר = תגובה מהירה יותר!
                            buffer_big_enough = len(self.buf) > 8000  # ⚡ 0.5s במקום 0.8s - חוסך 300ms!
                            
                            # ⚡⚡⚡ BUILD 107: EARLY EOU - מענה מוקדם על partial חזק!
                            # אם יש partial חזק (12+ תווים וסיום במשפט) + 0.35s דממה - קפיצה מיד!
                            last_partial = getattr(self, "last_partial_text", "")
                            high_conf_partial = (len(last_partial) >= 12) and any(last_partial.endswith(p) for p in (".", "?", "!", "…", ":", ";"))
                            early_silence = silence_time >= 0.35  # דממה קצרצרה
                            
                            if high_conf_partial and early_silence and dur >= 0.5:
                                print(f"⚡⚡⚡ EARLY EOU on strong partial: '{last_partial}' ({dur:.1f}s, {silence_time:.2f}s silence)")
                                # קפיצה מיידית לעיבוד!
                                silent = True
                                buffer_big_enough = True
                            
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
                        len(self.buf) > 96000 and  # ✅ FIX: 6.0s של אודיו (לא קוטע משפטים ארוכים!)
                        silence_time > 2.0):      # ✅ FIX: 2.0s שקט לחירום - שקט אמיתי!
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
                
                if et == "dtmf":
                    # ⚡ BUILD 121: DTMF digit collection for phone number input
                    digit = evt.get("dtmf", {}).get("digit", "")
                    print(f"📞 DTMF pressed: {digit} (buffer={self.dtmf_buffer})")
                    
                    if digit == "#":
                        # End of input - process collected digits
                        if self.dtmf_buffer and len(self.dtmf_buffer) >= 9:
                            phone_number = self.dtmf_buffer
                            print(f"✅ DTMF phone collected: {phone_number}")
                            
                            # Clear buffer
                            self.dtmf_buffer = ""
                            self.waiting_for_dtmf = False
                            
                            # Inject as if customer said the number
                            hebrew_text = f"המספר שלי הוא {phone_number}"
                            print(f"🎯 DTMF -> AI: '{hebrew_text}'")
                            
                            # Process as normal utterance (trigger AI response)
                            try:
                                self._process_dtmf_phone(phone_number)
                            except Exception as e:
                                print(f"❌ DTMF processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"⚠️ DTMF input too short: {self.dtmf_buffer} (need 9+ digits)")
                            # Don't speak - just reset and let user retry
                        
                        # Reset buffer anyway
                        self.dtmf_buffer = ""
                        self.waiting_for_dtmf = False
                        
                    elif digit == "*":
                        # Clear/restart input
                        print(f"🔄 DTMF cleared (was: {self.dtmf_buffer})")
                        self.dtmf_buffer = ""
                        # Don't speak - just clear buffer
                        
                    elif digit.isdigit():
                        # Append digit
                        self.dtmf_buffer += digit
                        print(f"📝 DTMF buffer: {self.dtmf_buffer}")
                    
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
            # ⚡ STREAMING STT: Close session at end of call
            self._close_streaming_stt()
            
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
                self._tx_enqueue({"type": "clear"})
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
                # ⚡ PHASE 2: Use smart wrapper (streaming or single-request)
                text = self._hebrew_stt_wrapper(pcm16_8k) or ""
                print(f"🎤 USER: {text}")
                
                # ✅ מדידת ASR Latency
                if hasattr(self, 'eou_timestamp'):
                    asr_latency = time.time() - self.eou_timestamp
                    self.last_stt_time = asr_latency  # ⚡ CRITICAL: Save for TOTAL_LATENCY calculation
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
            
            # ⚡ BUILD 117: REMOVED SHORT_UNCOMMON_WORD filter - trust Google STT!
            # If STT returned text, it's real speech. Don't reject valid words like "שוודי"
            # Only reject if it's EXTREMELY short (1-2 chars) which is likely noise
            if len(text.strip()) <= 2:
                print(f"🚫 VERY_SHORT_TEXT: '{text}' (≤2 chars) - likely noise")
                self.state = STATE_LISTEN
                self.processing = False
                return
            
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
        
        # ⚡ BUILD 117: Stricter barge-in to prevent interruptions
        word_count = len(text.split())
        self.long_response = word_count > 12  # ✅ LOWERED: 12 words = ~2 sentences, disable barge-in
        if self.long_response:
            print(f"🔒 LONG_RESPONSE ({word_count} words) - BARGE-IN DISABLED")
        else:
            print(f"🔓 SHORT_RESPONSE ({word_count} words) - BARGE-IN ENABLED")
            
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
        
        # ⚡ BUILD 117: Stricter barge-in to prevent interruptions
        word_count = len(text.split())
        self.long_response = word_count > 12  # ✅ LOWERED: 12 words = ~2 sentences, disable barge-in
        if self.long_response:
            print(f"🔒 LONG_RESPONSE ({word_count} words) - BARGE-IN DISABLED")
        else:
            print(f"🔓 SHORT_RESPONSE ({word_count} words) - BARGE-IN ENABLED")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        print(f"🔊 TTS_START: '{text}'")
        
        # ⚡ BUILD 107: Save EOU timestamp for total latency calculation
        eou_saved = getattr(self, 'eou_timestamp', None)
        
        try:
            # ⚡ ULTRA-SPEED: No delay before TTS - immediately start speaking
            # time.sleep removed for minimum latency
                
            # קיצור טקסט ארוך
            if len(text) > 150:
                text = text[:150].rsplit(' ', 1)[0] + '.'
                print(f"🔪 TTS_SHORTENED: {text}")
            
            # ⏱️ TTS timing instrumentation
            tts_start = time.time()
            tts_audio = self._hebrew_tts(text)
            tts_generation_time = time.time() - tts_start
            print(f"📊 TTS_GENERATION: {tts_generation_time:.3f}s (target: <0.5s)")
            
            if tts_audio and len(tts_audio) > 1000:
                print(f"🔊 TTS SUCCESS: {len(tts_audio)} bytes")
                send_start = time.time()
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
                send_time = time.time() - send_start
                print(f"📊 TTS_SEND: {send_time:.3f}s (audio transmission)")
                
                # ⚡ BUILD 114: Detailed latency breakdown (EOU→first audio sent)
                if eou_saved:
                    turn_latency = send_start - eou_saved
                    total_latency = time.time() - eou_saved
                    stt_time = getattr(self, 'last_stt_time', 0.0)
                    ai_time = getattr(self, 'last_ai_time', 0.0)
                    
                    print(f"📊 TURN_LATENCY: {turn_latency:.3f}s (EOU→TTS start, target: <1.2s)")
                    print(f"📊 🎯 TOTAL_LATENCY: {total_latency:.3f}s (EOU→Audio sent, target: <2.0s)")
                    print(f"[LATENCY] stt={stt_time:.2f}s, ai={ai_time:.2f}s, tts={tts_generation_time:.2f}s, total={total_latency:.2f}s")
                    
                    # נקה למדידה הבאה
                    if hasattr(self, 'eou_timestamp'):
                        delattr(self, 'eou_timestamp')
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
    
    def _tx_enqueue(self, item):
        """
        ⚡ BUILD 115.1: Enqueue with drop-oldest policy
        If queue is full, drop oldest frame and insert new one (Real-time > past)
        """
        try:
            self.tx_q.put_nowait(item)
        except queue.Full:
            # Drop oldest frame
            try:
                _ = self.tx_q.get_nowait()
            except queue.Empty:
                pass
            # Try again
            try:
                self.tx_q.put_nowait(item)
            except queue.Full:
                # Throttled logging - max once per 2 seconds
                now = time.monotonic()
                if now - self._last_overflow_log > 2.0:
                    print("⚠️ tx_q full (drop oldest)", flush=True)
                    self._last_overflow_log = now
    
    def _finalize_speaking(self):
        """סיום דיבור עם חזרה להאזנה"""
        self.speaking = False
        self.long_response = False  # ⚡ BUILD 109: Reset flag
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
        
        # ⚡ Removed flooding log
        
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
                
                # ⚡ Removed flooding logs - only log errors
            except Exception as e:
                print(f"❌ Error sending frame {frames_sent}: {e}")
                break
        
        # ⚡ Only log interruptions (barge-in), not normal completions
        if not self.speaking:
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

    async def _stt_fallback_async(self, audio_data: bytes) -> str:
        """
        ⚡ BUILD 115: Async wrapper for fallback STT
        Runs _hebrew_stt in thread pool without blocking the event loop
        """
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.exec, self._hebrew_stt, audio_data)
        except Exception as e:
            print(f"❌ [STT_FALLBACK_ASYNC] Failed: {e}", flush=True)
            return ""
    
    def _stt_fallback_nonblocking(self, audio_data: bytes) -> None:
        """
        ⚡ BUILD 115: Non-blocking wrapper for fallback STT (sync → async)
        Submits work to thread pool and returns immediately.
        Result is delivered via callback to avoid blocking.
        """
        # Submit to thread pool
        fut = self.exec.submit(self._hebrew_stt, audio_data)
        
        # When done, deliver result back to event loop safely
        def _on_done(f):
            try:
                text = f.result()
            except Exception as e:
                print(f"❌ [STT_FALLBACK_NB] Failed: {e}", flush=True)
                text = ""
            
            # If there's a loop and events queue, use it
            if self.loop and self.events_q:
                events_q = self.events_q  # Type hint helper
                self.loop.call_soon_threadsafe(
                    lambda: events_q.put_nowait(("stt_final_text", text))
                )
            else:
                # Fallback: direct callback (sync mode)
                print(f"🎤 [STT_FALLBACK_NB] Result: {text[:50] if text else '(empty)'}", flush=True)
        
        fut.add_done_callback(_on_done)

    def _hebrew_stt_wrapper(self, pcm16_8k: bytes, on_partial_cb=None) -> str:
        """
        🎯 Smart wrapper: streaming (collects from dispatcher) → fallback to single-request
        """
        session = _get_session(self.call_sid) if self.call_sid else None
        
        if not USE_STREAMING_STT or not session:
            # Single-request mode (existing)
            return self._hebrew_stt(pcm16_8k)
        
        try:
            # Streaming mode: collect results from dispatcher
            # Audio is already being fed to session in WS loop
            # Just collect what's been accumulated
            print(f"⏱️ [STT_STREAM] Calling _utterance_end...")
            utt_start = time.time()
            result = self._utterance_end()
            utt_duration = time.time() - utt_start
            print(f"⏱️ [STT_STREAM] _utterance_end took {utt_duration:.3f}s, result: '{result[:50] if result else '(empty)'}'")
            
            # ✅ FIX: Fallback on empty results
            if not result or not result.strip():
                print("⚠️ [STT] Streaming returned empty → fallback to single")
                fallback_start = time.time()
                fallback_result = self._hebrew_stt(pcm16_8k)
                fallback_duration = time.time() - fallback_start
                print(f"⏱️ [STT_FALLBACK] Single-request took {fallback_duration:.3f}s, result: '{fallback_result[:50] if fallback_result else '(empty)'}'")
                return fallback_result
                
            return result
            
        except Exception as e:
            # Fallback to single-request on exception
            print(f"⚠️ [STT] Streaming failed → fallback to single. err={e}")
            import traceback
            traceback.print_exc()
            return self._hebrew_stt(pcm16_8k)

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
            
            # ⚡ BUILD 113: RELAXED validation - allow quieter speech for better transcription
            
            # 1. Basic amplitude check - RELAXED threshold (favor accuracy over noise rejection)
            if max_amplitude < 50:  # Lowered from 60 - allow quieter speech
                print(f"🚫 STT_BLOCKED: Audio too quiet (max_amplitude={max_amplitude} < 50)")
                return ""
            
            # 2. RMS energy check - RELAXED
            if rms < 30:  # Lowered from 40 - allow quieter audio
                print(f"🚫 STT_BLOCKED: Audio energy too low (rms={rms} < 30)")
                return ""
            
            # 3. Duration check
            if duration < 0.15:  # Too short to be meaningful
                print(f"🚫 STT_BLOCKED: Audio too short ({duration:.2f}s < 0.15s)")
                return ""
            
            # 4. ✅ Advanced checks with variance/ZCR - INFORMATIONAL + BLOCKING
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                zero_crossings = np.sum(np.diff(np.sign(pcm_array)) != 0) / len(pcm_array)
                
                # ✅ Block pure silence, DTMF, and carrier tones
                # Pure silence/monotonic: low variance AND low ZCR
                # DTMF tone: very low ZCR (pure sine wave)
                if (energy_variance < 200000 and zero_crossings < 0.02) or (zero_crossings < 0.005):
                    print(f"🚫 STT_BLOCKED: Non-speech audio (variance={energy_variance}, zcr={zero_crossings:.3f})")
                    return ""
                
                print(f"✅ AUDIO_VALIDATED: amp={max_amplitude}, rms={rms}, var={int(energy_variance)}, zcr={zero_crossings:.3f}")
                
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
            
            # ⚡ BUILD 117: FORCE default model - phone_call NOT supported for Hebrew!
            # Google returns error: "The phone_call model is currently not supported for language : iw-IL"
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,  
                language_code="he-IL",   # עברית ישראל
                model="default",         # ⚡ FORCED: phone_call crashes for Hebrew!
                use_enhanced=True,       # ✅ ENHANCED model for better Hebrew accuracy!
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
            
            # ⚡ AGGRESSIVE TIMEOUT: 1.5s for speed (Hebrew usually < 1s)
            try:
                response = client.recognize(
                    config=recognition_config,
                    audio=audio,
                    timeout=1.5  # ✅ FAST: 1.5s timeout (was 3s)
                )
            except Exception as timeout_error:
                # Timeout = likely empty audio, return empty
                print(f"⚠️ STT_TIMEOUT ({timeout_error}) - likely silence")
                return ""
            
            print(f"📊 GOOGLE_STT_ENHANCED: Processed {len(pcm16_8k)} bytes")
            
            if response.results and response.results[0].alternatives:
                hebrew_text = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                print(f"📊 GOOGLE_STT_RESULT: '{hebrew_text}' (confidence: {confidence:.2f})")
                
                # ⚡ BUILD 111: SMART confidence - prevent false positives
                if confidence < 0.3:  # Very low confidence = not reliable
                    print(f"🚫 LOW_CONFIDENCE: {confidence:.2f} < 0.3 - rejecting result")
                    return ""  # Return empty instead of nonsense
                
                # ⚡ BUILD 111: Additional check - reject very short results with low-medium confidence
                word_count = len(hebrew_text.split())
                if word_count <= 2 and confidence < 0.6:
                    print(f"🚫 SHORT_LOW_CONFIDENCE: {word_count} words, confidence {confidence:.2f} < 0.6 - likely noise")
                    return ""
                
                print(f"✅ GOOGLE_STT_SUCCESS: '{hebrew_text}' ({word_count} words, confidence: {confidence:.2f})")
                return hebrew_text
            else:
                # No results = silence
                print("⚠️ STT_NO_RESULTS - likely silence")
                return ""
                
        except Exception as e:
            print(f"❌ GOOGLE_STT_ERROR: {e}")
            return ""
    
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
            from server.models_sql import Business, BusinessSettings
            
            app = _get_flask_app()  # ✅ Use singleton
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
                    return "אתה עוזר נדלן מקצועי. עזור ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם hardcoded
                
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
            return "אתה עוזר נדלן מקצועי. עזור ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם/עסק hardcoded
            
        except Exception as e:
            print(f"❌ שגיאה בטעינת פרומפט מדאטאבייס: {e}")
            return "אתה עוזר נדלן מקצועי. עזור ללקוח למצוא את הנכס המתאים."  # ✅ בלי שם hardcoded

    def _identify_business_and_get_greeting(self) -> tuple:
        """⚡ זיהוי עסק וטעינת ברכה בשאילתה אחת - חוסך 50% זמן!"""
        try:
            from server.models_sql import Business
            from sqlalchemy import or_
            
            to_number = getattr(self, 'to_number', None)
            
            print(f"⚡ FAST: זיהוי עסק + ברכה בשאילתה אחת: to_number={to_number}")
            
            app = _get_flask_app()  # ✅ Use singleton
            with app.app_context():
                business = None
                
                if to_number:
                    # נרמל מספר טלפון
                    normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
                    
                    # ⚡ שאילתה אחת - עסק + כל הנתונים!
                    business = Business.query.filter(
                        or_(
                            Business.phone_e164 == to_number,
                            Business.phone_e164 == normalized_phone
                        )
                    ).first()
                    
                    if business:
                        print(f"✅ מצא עסק: {business.name} (id={business.id})")
                
                # Fallback אם לא נמצא
                if not business:
                    business = Business.query.filter_by(is_active=True).first()
                    if not business:
                        business = Business.query.first()
                    print(f"⚠️ שימוש בעסק fallback: {business.name if business else 'None'}")
                
                # עדכן business_id + חזור ברכה
                if business:
                    self.business_id = business.id
                    greeting = business.greeting_message or "שלום! איך אפשר לעזור?"
                    business_name = business.name or "העסק שלנו"
                    
                    # החלפת placeholder
                    greeting = greeting.replace("{{business_name}}", business_name)
                    greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                    
                    print(f"⚡ FAST COMPLETE: business_id={self.business_id}, greeting='{greeting[:30]}...'")
                    return (self.business_id, greeting)
                else:
                    self.business_id = 1
                    return (1, "שלום! איך אפשר לעזור?")
        
        except Exception as e:
            print(f"❌ Fast identification failed: {e}")
            import traceback
            traceback.print_exc()
            self.business_id = 1
            return (1, "שלום! איך אפשר לעזור?")
    
    def _identify_business_from_phone(self):
        """זיהוי business_id לפי to_number (wrapper for backwards compat)"""
        self._identify_business_and_get_greeting()  # קורא לפונקציה החדשה ומתעלם מהברכה

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
            
            app = _get_flask_app()  # ✅ Use singleton
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
                app = _get_flask_app()  # ✅ Use singleton
                with app.app_context():
                    self._identify_business_from_phone()
                print(f"🔍 אחרי זיהוי: business_id={getattr(self, 'business_id', 'STILL NOT SET')}")
            
            # טעינת ברכה מה-DB
            app = _get_flask_app()  # ✅ Use singleton
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

    def _process_dtmf_phone(self, phone_number: str):
        """
        ⚡ BUILD 121: Process phone number collected via DTMF
        Inject as conversation input and generate AI response
        """
        print(f"📞 Processing DTMF phone: {phone_number}")
        
        # Format as Israeli phone number if needed
        if not phone_number.startswith("+") and not phone_number.startswith("0"):
            phone_number = "0" + phone_number
        
        # Create Hebrew text as if customer said it
        hebrew_text = phone_number  # Just the digits
        
        # Get AI response (Agent will process the phone)
        ai_response = self._ai_response(hebrew_text)
        
        # Speak the response using the correct method
        if ai_response:
            self._speak_simple(ai_response)
            
            # Save to conversation history
            self.conversation_history.append({
                "user": f"[DTMF] {phone_number}",
                "bot": ai_response
            })
        
        print(f"✅ DTMF phone processed: {phone_number}")
    
    def _ai_response(self, hebrew_text: str) -> str:
        """Generate NATURAL Hebrew AI response using AgentKit - REAL ACTIONS!"""
        try:
            # ⚡ Phase 2C: Track turns and optimize first turn
            self.turn_count = getattr(self, 'turn_count', 0) + 1
            is_first_turn = (self.turn_count == 1)
            
            # 🤖 BUILD 119: Use Agent for REAL ACTIONS (appointments, leads, WhatsApp)
            from server.services.ai_service import AIService
            
            # Build context for the AI
            context = {
                "phone_number": getattr(self, 'phone_number', ''),
                "channel": "voice_call",
                "previous_messages": []
            }
            
            # Add conversation history for context - ✅ FIXED FORMAT
            if hasattr(self, 'conversation_history') and self.conversation_history:
                context["previous_messages"] = [
                    f"לקוח: {item['user']}\nעוזר: {item['bot']}"  # ✅ "עוזר" - כללי!
                    for item in self.conversation_history[-6:]  # עד 6 תורות אחרונים לזיכרון מלא
                ]
            
            # ✅ CRITICAL FIX: Use shared Flask app instance (no recreation!)
            business_id = getattr(self, 'business_id', None)
            if not business_id:
                business_id = 1  # Fallback to business 1
                print(f"⚠️ No business_id set, using fallback: {business_id}")
            
            # Get customer name from conversation if available
            customer_name = None
            lead_info = getattr(self, '_last_lead_analysis', None)
            if lead_info:
                customer_name = lead_info.get('customer_name')
            
            # ⚡ CRITICAL: Measure AI response time
            ai_start = time.time()
            
            # ✅ FIX: Use Flask app singleton (CRITICAL - prevents app restart!)
            app = _get_flask_app()
            
            with app.app_context():
                # 🤖 Use Agent for REAL booking actions!
                ai_service = AIService()
                
                # 🔍 DEBUG: Check if phone_number is set
                caller_phone = getattr(self, 'phone_number', '')
                print(f"\n📞 DEBUG: Caller phone = '{caller_phone}' (type: {type(caller_phone).__name__})")
                print(f"   self.phone_number exists: {hasattr(self, 'phone_number')}")
                if hasattr(self, 'phone_number'):
                    print(f"   self.phone_number value: '{self.phone_number}'")
                
                ai_response = ai_service.generate_response_with_agent(
                    message=hebrew_text,
                    business_id=int(business_id),
                    customer_phone=caller_phone,
                    customer_name=customer_name,
                    context=context,
                    channel='calls',  # ✅ Use 'calls' prompt for phone calls
                    is_first_turn=is_first_turn  # ⚡ Phase 2C: Optimize first turn!
                )
            
            # ⚡ CRITICAL: Save AI timing for TOTAL_LATENCY calculation
            self.last_ai_time = time.time() - ai_start
            print(f"🤖 AGENT_RESPONSE: Generated {len(ai_response)} chars in {self.last_ai_time:.3f}s (business {business_id})")
            print(f"📊 AI_LATENCY: {self.last_ai_time:.3f}s (target: <1.5s)")
            
            return ai_response
            
        except Exception as e:
            print(f"❌ AI_SERVICE_ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            print(f"⚠️ Using fallback response instead of agent")
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
                from server.services.gcp_tts_live import get_hebrew_tts, maybe_warmup
                
                # ⚡ Phase 2: Pre-warm TTS (כל 8 דקות)
                maybe_warmup()
                
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
        """
        ⚡ BUILD 115.1 FINAL: Production-grade TX loop
        - Precise 20ms/frame timing with next_deadline
        - Back-pressure at 90% threshold
        - Real-time telemetry (fps/q/drops)
        """
        print("🔊 TX_LOOP_START: Audio transmission thread started")
        
        FRAME_INTERVAL = 0.02  # 20 ms per frame expected by Twilio
        next_deadline = time.monotonic()
        tx_count = 0
        
        # Telemetry
        frames_sent_last_sec = 0
        drops_last_sec = 0
        last_telemetry_time = time.monotonic()
        
        while self.tx_running:
            try:
                item = self.tx_q.get(timeout=0.5)
            except queue.Empty:
                continue
            
            if item.get("type") == "end":
                print("🔚 TX_LOOP_END: End signal received")
                break
            
            # Handle "clear" event
            if item.get("type") == "clear" and self.stream_sid:
                success = self._ws_send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
                print(f"🧹 TX_CLEAR: {'SUCCESS' if success else 'FAILED'}")
                continue
            
            # Handle "media" event with back-pressure and rate limiting
            if item.get("type") == "media":
                # ⚡ Back-pressure: If tx_q is getting full (>90%), slow down
                queue_size = self.tx_q.qsize()
                if queue_size > 108:  # 90% of 120
                    print(f"⚠️ tx_q nearly full ({queue_size}/120) – applying back-pressure", flush=True)
                    drops_last_sec += 1
                    time.sleep(FRAME_INTERVAL * 2)  # Double wait to drain queue
                    continue
                
                # Send frame
                success = self._ws_send(json.dumps({
                    "event": "media", 
                    "streamSid": self.stream_sid,
                    "media": {"payload": item["payload"]}
                }))
                tx_count += 1
                frames_sent_last_sec += 1
                
                # ⚡ Precise timing with next_deadline
                next_deadline += FRAME_INTERVAL
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    # Missed deadline - resync
                    next_deadline = time.monotonic()
                
                # ⚡ Telemetry: Print stats every second (only if issues)
                now = time.monotonic()
                if now - last_telemetry_time >= 1.0:
                    queue_size = self.tx_q.qsize()
                    # Only log if there are drops or queue is getting full
                    if drops_last_sec > 0 or queue_size > 60:
                        print(f"[TX] fps={frames_sent_last_sec} q={queue_size} drops={drops_last_sec}", flush=True)
                    frames_sent_last_sec = 0
                    drops_last_sec = 0
                    last_telemetry_time = now
                
                continue
            
            # Handle "mark" event
            if item.get("type") == "mark":
                success = self._ws_send(json.dumps({
                    "event": "mark", 
                    "streamSid": self.stream_sid,
                    "mark": {"name": item.get("name", "mark")}
                }))
                print(f"📍 TX_MARK: {item.get('name', 'mark')} {'SUCCESS' if success else 'FAILED'}")
        
        # ⚡ Removed flooding log - TX loop ended naturally
    
    def _speak_with_breath(self, text: str):
        """דיבור עם נשימה אנושית ו-TX Queue - תמיד משדר משהו"""
        if not text:
            return
        
        # ⚡ BUILD 117: Stricter barge-in to prevent interruptions
        word_count = len(text.split())
        self.long_response = word_count > 12  # ✅ LOWERED: 12 words = ~2 sentences, disable barge-in
        if self.long_response:
            print(f"🔒 LONG_RESPONSE ({word_count} words) - BARGE-IN DISABLED")
        else:
            print(f"🔓 SHORT_RESPONSE ({word_count} words) - BARGE-IN ENABLED")
            
        self.speaking = True
        self.state = STATE_SPEAK
        self.speaking_start_ts = time.time()  # ✅ חלון חסד - זמן תחילת TTS
        
        try:
            # נשימה אנושית (220-360ms)
            breath_delay = random.uniform(RESP_MIN_DELAY_MS/1000.0, RESP_MAX_DELAY_MS/1000.0)
            time.sleep(breath_delay)
            
            # clear + שידור אם החיבור תקין
            if self.stream_sid and not self.ws_connection_failed:
                self._tx_enqueue({"type": "clear"})
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
        
        # ✅ FIX: תיאום פגישה אם יש לפחות 3 שדות (אזור + סוג נכס + טלפון)
        # לא צריך תקציב ו-timing בהכרח!
        meeting_ready = completed_fields >= 3
        
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
            meeting_prompt = f"""
זמן לתיאום פגישה! יש מספיק מידע ({completed_fields}/5 שדות).

**חשוב**: כשהלקוח מסכים לזמן ספציפי (לדוגמה "מחר ב-10" או "יום רביעי בערב"):
1. חזור על הזמן המדויק שסוכם: "מצוין! נקבע פגישה ל[יום] בשעה [שעה מדויקת]"
2. תן סיכום קצר: "נפגש ב[מיקום/נכס] ונראה [פרטי הנכס]"
3. אשר: "אראה אותך ב[תאריך ושעה מדויקים]!"

הצע 2-3 אפשרויות זמן ספציפיות, שמע מה הלקוח בוחר, וחזור על הזמן המדויק שהוסכם."""
        elif completed_fields == 3:
            meeting_prompt = """
יש מידע בסיסי טוב! עכשיו תן דוגמה אחת ספציפית מתאימה ושאל שאלה ממוקדת לפני קביעת פגישה."""
        else:
            missing = 4 - completed_fields
            meeting_prompt = f"צריך עוד {missing} שדות מידע לפני הצגת אופציות. המשך שיחה טבעית ותן פרטים נוספים על השוק והאזור."
        
        return {
            'collected': collected_info,
            'completed_count': completed_fields,
            'meeting_ready': meeting_ready,
            'summary': summary,
            'meeting_prompt': meeting_prompt
        }
    
    def _finalize_call_on_stop(self):
        """✅ סיכום מלא של השיחה בסיום - עדכון call_log וליד + יצירת פגישות"""
        try:
            from server.models_sql import CallLog
            from server.services.customer_intelligence import CustomerIntelligence
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def finalize_in_background():
                try:
                    app = _get_flask_app()  # ✅ Use singleton
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
                                f"לקוח: {turn['user']}\nעוזר: {turn['bot']}"  # ✅ כללי - לא hardcoded!
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
                        
                        # 🤖 BUILD 119: Agent handles appointments during conversation!
                        # AUTO-APPOINTMENT disabled - Agent creates appointments in real-time
                        print(f"ℹ️ Appointment handling: Managed by Agent during call (BUILD 119)")
                        
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
                    app = _get_flask_app()  # ✅ Use singleton
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
                        call_log = CallLog()  # type: ignore[call-arg]
                        call_log.business_id = getattr(self, 'business_id', 1)
                        call_log.call_sid = self.call_sid
                        call_log.from_number = str(self.phone_number or "")
                        call_log.to_number = str(getattr(self, 'to_number', '') or '')
                        call_log.call_status = "in_progress"
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
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        # מצא call_log קיים (אמור להיות כבר נוצר ב-_create_call_log_on_start)
                        call_log = None
                        if hasattr(self, 'call_sid') and self.call_sid:
                            call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        
                        if not call_log:
                            print(f"⚠️ Call log not found for {self.call_sid} - conversation turn not saved")
                            return
                        
                        # שמור תור משתמש
                        user_turn = ConversationTurn()  # type: ignore[call-arg]
                        user_turn.call_log_id = call_log.id
                        user_turn.call_sid = self.call_sid or f"live_{int(time.time())}"
                        user_turn.speaker = 'user'
                        user_turn.message = user_text
                        user_turn.confidence_score = 1.0
                        db.session.add(user_turn)
                        
                        # שמור תור AI
                        bot_turn = ConversationTurn()  # type: ignore[call-arg]
                        bot_turn.call_log_id = call_log.id
                        bot_turn.call_sid = self.call_sid or f"live_{int(time.time())}"
                        bot_turn.speaker = 'assistant'
                        bot_turn.message = bot_reply
                        bot_turn.confidence_score = 1.0
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
                    app = _get_flask_app()  # ✅ Use singleton
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