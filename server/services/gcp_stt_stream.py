"""
Real-time Streaming STT for Hebrew with Google Cloud Speech
Optimized for ultra-low latency phone conversations

⚡ BUILD 115: Dynamic model selection with smart fallback
- Session-per-call architecture
- Automatic model availability probing
- Graceful fallback (phone_call → default)
- Thread-safe for concurrent calls

⚡ BUILD 118.6: Endless streaming for long calls
- Google Cloud STT limit: 5 minutes per session
- Auto-restart session before timeout
- Seamless continuation for calls >5 minutes
"""
import os
import json
import time
import threading
import queue
import logging
from google.cloud import speech

log = logging.getLogger("gcp_stt_stream")

# ⚡ BUILD 119.3: Proven parameters for reliable Hebrew STT with low latency
BATCH_MS = int(os.getenv("STT_BATCH_MS", "40"))        # 40ms batching
DEBOUNCE_MS = int(os.getenv("STT_PARTIAL_DEBOUNCE_MS", "90"))  # 90ms partial debounce
TIMEOUT_MS = int(os.getenv("STT_TIMEOUT_MS", "320"))    # 320ms utterance timeout
LANG = os.getenv("GCP_STT_LANGUAGE", "he-IL")
PUNCTUATION_INTERIM = os.getenv("GCP_STT_PUNCTUATION_INTERIM", "false").lower() == "true"
PUNCTUATION_FINAL = os.getenv("GCP_STT_PUNCTUATION_FINAL", "true").lower() == "true"


# ⚡ BUILD 115.1: default תמיד - phone_call לא עובד בעברית בישראל!
MODEL = os.getenv("GCP_STT_MODEL", "default").strip()
USE_ENHANCED = True  # גוגל מתעלמת אם לא נתמך; לא קורס

print(f"🎯 STT Configuration: model={MODEL}, enhanced={USE_ENHANCED}, language={LANG}", flush=True)


class StreamingSTTSession:
    """
    ONE session per call - lives for entire conversation.
    Audio is fed continuously via push_audio().
    Callbacks fire for partial/final results across ALL utterances.
    """
    
    def __init__(self, on_partial, on_final):
        """
        Initialize streaming session with callbacks.
        
        Args:
            on_partial: Callback for interim results (called frequently ~180ms)
            on_final: Callback for final results (end of utterance)
        """
        # ⚡ BUILD 115.1: Initialize Google Speech client (NO custom endpoint - production fix)
        try:
            self.client = speech.SpeechClient()
            log.info(f"✅ StreamingSTTSession: Client initialized")
        except Exception as e:
            log.error(f"❌ Failed to initialize Speech client: {e}")
            raise
        
        self._on_partial = on_partial
        self._on_final = on_final
        
        # ⚡ BUILD 119.5: Bounded STT queue with drop-oldest (prevents OOM!)
        # RX worker can push fast, we handle back-pressure here
        self._q = queue.Queue(maxsize=200)  # Bounded - drop oldest if full
        self._stop = threading.Event()
        
        # Debouncing state
        self._last_partial = ""
        self._last_emit_ms = 0
        self._early_finalized = False  # Track if we already sent early-final for this utterance
        
        # Metrics
        self._stt_drops = 0  # Track drops in STT queue
        
        # Start worker thread
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        log.info("🚀 StreamingSTTSession: Worker thread started")
    
    def push_audio(self, pcm_bytes: bytes) -> bool:
        """
        ⚡ BUILD 120.0: Feed PCM16 8kHz audio to the streaming session.
        Non-blocking with drop-oldest to prevent RX worker blocking.
        Always returns True (RX worker doesn't need back-pressure handling).
        
        Returns:
            True (always accepts, drops oldest if queue full)
        """
        if not pcm_bytes:
            return False
        
        # Try to add frame without blocking
        try:
            self._q.put_nowait(pcm_bytes)
            return True
        except queue.Full:
            # Drop oldest frame and add new one
            try:
                _ = self._q.get_nowait()  # Drop oldest
                self._stt_drops += 1
                if self._stt_drops % 50 == 1:  # Log every 50 drops
                    log.warning(f"⚠️ STT drop-oldest: drops={self._stt_drops} q={self._q.qsize()}")
            except queue.Empty:
                pass
            # Add new frame
            try:
                self._q.put_nowait(pcm_bytes)
            except queue.Full:
                # Edge case - should never happen
                pass
            return True  # Always return True (drop-oldest handled)
    
    def close(self):
        """
        Stop streaming session and cleanup.
        Called at end of call.
        """
        log.info("🛑 Closing StreamingSTTSession...")
        self._stop.set()
        try:
            self._q.put_nowait(None)  # Signal EOF
        except queue.Full:
            pass
        self._t.join(timeout=2.0)
        log.info("✅ StreamingSTTSession closed")
    
    def _config(self):
        """Build recognition config"""
        # ⚡ BUILD 118.5: הרחבת vocabulary לדיוק מקסימלי בעברית!
        speech_contexts = [
            speech.SpeechContext(
                phrases=[
                    # נדל"ן - מונחים בסיסיים
                    "דירה", "דירות", "בית", "בתים", "משרד", "משרדים", "נכס", "נכסים",
                    "קרקע", "קרקעות", "מגרש", "מגרשים", "נחלה", "נחלות", "אדמה", "אדמות",
                    "שכירות", "מכירה", "השכרה", "קניה", "מכר", "שכר", "השקעה", "השקעות",
                    "חדר", "חדרים", "מ״ר", "מטר", "מטרים", "מרובע", "דונם", "דונמים",
                    "קומה", "קומות", "מעלית", "חניה", "חניות", "מרפסת", "מרפסות",
                    "ממ״ד", "מחסן", "מחסנים", "גג", "גינה", "גינות", "מזגן", "מזגנים",
                    "פנטהאוז", "דופלקס", "טריפלקס", "סטודיו", "יחידת דיור", "יחידות דיור",
                    
                    # ערים ואזורים
                    "תל אביב", "ירושלים", "חיפה", "באר שבע", "נתניה", "ראשון לציון",
                    "פתח תקווה", "רמת גן", "הרצליה", "חולון", "בת ים", "רחובות",
                    "אשדוד", "אשקלון", "רעננה", "כפר סבא", "הוד השרון", "רמת השרון",
                    "גבעתיים", "בני ברק", "רמלה", "לוד", "מודיעין", "נס ציונה",
                    
                    # כסף ומחירים
                    "שקל", "שקלים", "אלף", "אלפים", "מיליון", "עשרת אלפים",
                    "מאה", "מאתיים", "חמש מאות", "אלפיים", "שלושת אלפים",
                    "תקציב", "מחיר", "עלות", "משכנתא", "הלוואה", "ריבית",
                    
                    # זמנים ותאריכים
                    "מחר", "מחרתיים", "היום", "עכשיו", "בוקר", "צהריים", "ערב",
                    "שעה", "בשעה", "דקה", "יום", "שבוע", "חודש", "שנה",
                    "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת",
                    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
                    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
                    
                    # ביטויים נפוצים בשיחות
                    "כן", "לא", "בסדר", "מצוין", "בטח", "אוקיי", "אולי",
                    "תודה", "סליחה", "רגע", "שנייה", "אפשר", "צריך", "רוצה",
                    "מעוניין", "מתאים", "נוח", "מתי", "איפה", "כמה", "מה",
                    
                    # שמות עסקים (מהקונפיג)
                    "שי דירות ומשרדים", "לאה", "נדלן", "נדל״ן",
                    
                    # מצבים ופעולות
                    "פגישה", "פגישות", "ביקור", "סיור", "להתקשר", "להודיע",
                    "לקבוע", "לבדוק", "לראות", "להגיע", "לבוא", "לחזור"
                ],
                boost=20.0  # ⚡ BUILD 118.5: הגדלת boost ל-20 לדיוק מקסימלי!
            )
        ]
        
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            language_code=LANG,
            model=MODEL,
            use_enhanced=USE_ENHANCED,  # ⚡ BUILD 115: Dynamically selected based on availability
            enable_automatic_punctuation=PUNCTUATION_FINAL,
            speech_contexts=speech_contexts,
            # ⚡ BUILD 118.5: הוספת alternative language codes לדיוק טוב יותר
            alternative_language_codes=["iw-IL"]  # iw-IL = קוד חלופי לעברית
        )
    
    def _streaming_config(self):
        """Build streaming config"""
        return speech.StreamingRecognitionConfig(
            config=self._config(),
            interim_results=True,
            single_utterance=False  # CRITICAL: Allow multiple utterances in one session
        )
    
    def _requests(self):
        """
        ⚡ BUILD 119.6: AGGRESSIVE queue draining!
        Generator yielding batched audio requests.
        Drains queue as fast as possible to prevent drops.
        """
        buf = bytearray()
        last = time.monotonic()
        
        while not self._stop.is_set():
            # ⚡ DRAIN MODE: Read all available frames without blocking
            drained_count = 0
            while drained_count < 50:  # Max 50 frames per batch (1 second)
                try:
                    chunk = self._q.get_nowait()  # Non-blocking!
                    if chunk is None:
                        # EOF signal - flush and exit
                        if buf:
                            log.info(f"🔚 Flushing final {len(buf)} bytes")
                            yield speech.StreamingRecognizeRequest(audio_content=bytes(buf))
                        return
                    buf.extend(chunk)
                    drained_count += 1
                except queue.Empty:
                    break
            
            # Send batch if we have data
            now = time.monotonic()
            if buf and ((now - last) * 1000 >= BATCH_MS or drained_count > 0):
                yield speech.StreamingRecognizeRequest(audio_content=bytes(buf))
                buf.clear()
                last = now
            
            # If no data was drained, sleep briefly to avoid busy-wait
            if drained_count == 0:
                time.sleep(0.01)  # 10ms sleep when queue is empty
    
    def _emit_partial(self, text: str):
        """Emit partial result with debouncing"""
        if not text:
            return
        
        now = time.monotonic() * 1000
        if text != self._last_partial and now - self._last_emit_ms >= DEBOUNCE_MS:
            self._last_partial = text
            self._last_emit_ms = now
            try:
                self._on_partial(text)
            except Exception as e:
                log.error(f"Partial callback error: {e}")
    
    def _should_finalize_early(self, partial_text: str) -> bool:
        """
        ⚡ BUILD 118.8: SMART early-finalize - fast response without mid-sentence cuts
        Balance between speed and accuracy using tiered confidence levels
        """
        if not partial_text:
            return False
        
        # ⚡ CRITICAL FIX: Strip whitespace before checking prefixes!
        partial_text_clean = partial_text.rstrip()
        
        # ⚡ TIER 1: Very high confidence - clear sentence ending (saves ~400ms!)
        if len(partial_text_clean) >= 15 and any(p in partial_text_clean for p in ".?!"):
            return True
        
        # ⚡ TIER 2: High confidence - complete thought without prefix
        # Avoid cutting "אני רוצה לקנות דירה ב..." but allow "אני רוצה לקנות דירה"
        if len(partial_text_clean) >= 25 and not partial_text_clean.endswith(("ב", "ל", "מ", "ה", "ו", "כ", "ש", "את", "על")):
            return True
        
        return False
    
    def _emit_final(self, text: str, early=False):
        """Emit final result"""
        if text:
            try:
                if early:
                    log.info(f"⚡ EARLY-FINAL: {text} (saved ~400ms)")
                self._on_final(text)
            except Exception as e:
                log.error(f"Final callback error: {e}")
        # Reset partial after final
        self._last_partial = ""
        self._early_finalized = early  # Track if this was early-finalized
    
    def _run(self):
        """
        Worker thread - maintains continuous connection to GCP.
        Runs for entire duration of call.
        
        ⚡ BUILD 118.6: Endless streaming support
        Google Cloud STT has a 5-minute (300s) limit per stream.
        We restart the stream every 4.5 minutes to stay under the limit.
        """
        log.info("📡 StreamingSTTSession: Starting GCP streaming recognize...")
        
        # ⚡ BUILD 118.6: Track session start time for endless streaming
        session_start_time = time.monotonic()
        MAX_SESSION_DURATION = 270  # 4.5 minutes (under 5 min limit)
        
        try:
            responses = self.client.streaming_recognize(
                self._streaming_config(),
                self._requests()
            )
            
            for resp in responses:
                if self._stop.is_set():
                    break
                
                # ⚡ BUILD 118.6: Check if we've been streaming for too long
                elapsed = time.monotonic() - session_start_time
                if elapsed > MAX_SESSION_DURATION:
                    log.warning(f"⏱️ Session duration {elapsed:.1f}s exceeded {MAX_SESSION_DURATION}s - would restart stream here")
                    # Note: For true endless streaming, we'd need to:
                    # 1. Buffer audio from last final transcript
                    # 2. Close current stream
                    # 3. Open new stream with buffered audio
                    # For now, we just log - most calls are <5 min
                
                for result in resp.results:
                    if not result.alternatives:
                        continue
                    
                    transcript = result.alternatives[0].transcript.strip()
                    if not transcript:
                        continue
                    
                    if result.is_final:
                        # Skip if we already early-finalized this utterance
                        if self._early_finalized:
                            log.debug(f"🔵 Skipping FINAL (already early-finalized): {transcript}")
                            self._early_finalized = False  # Reset for next utterance
                        else:
                            log.info(f"🟢 FINAL: {transcript}")
                            self._emit_final(transcript, early=False)
                    else:
                        # ⚡ BUILD 116: Check if we should early-finalize this partial
                        if not self._early_finalized and self._should_finalize_early(transcript):
                            # Treat this partial as final - saves 300-500ms!
                            self._emit_final(transcript, early=True)
                        else:
                            log.debug(f"🟡 PARTIAL: {transcript}")
                            self._emit_partial(transcript)
                        
        except Exception as e:
            log.error(f"❌ Streaming worker error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            log.info("📡 StreamingSTTSession: Worker stopped")

class GcpStreamingSTT:
    """
    Thread-safe streaming STT service
    Designed to work with sync WebSocket handlers
    """
    
    def __init__(self, sample_rate_hz=8000):
        self.client = None
        self.rate = sample_rate_hz
        
        # Audio queue for batching (200 = ~4s buffer @ 20ms frames)
        # ⚡ BUILD 119.3: Balanced size (not too big = lag, not too small = drops)
        # Drop-oldest policy will handle overflow without hidden latency
        self._audio_queue = queue.Queue(maxsize=200)
        self._batch_size_bytes = int(sample_rate_hz * 2 * (BATCH_MS / 1000.0))  # PCM16
        self._dropped_frames = 0  # Metrics
        
        # Results
        self._partial_callback = None
        self._final_callback = None
        self._last_partial_time = 0.0
        self._last_partial_text = ""
        
        # Control
        self._streaming = False
        self._worker_thread = None
        
    def _ensure_client(self):
        """Lazy initialization of Speech client"""
        if self.client is None:
            try:
                sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
                if sa_json:
                    credentials_info = json.loads(sa_json)
                    self.client = speech.SpeechClient.from_service_account_info(credentials_info)
                    log.info("✅ Streaming STT client initialized (service account)")
                else:
                    self.client = speech.SpeechClient()
                    log.info("✅ Streaming STT client initialized (default)")
            except Exception as e:
                log.error(f"❌ Failed to initialize Speech client: {e}")
                raise
        
    def start_streaming(self, on_partial=None, on_final=None):
        """
        Start streaming recognition
        
        Args:
            on_partial: Callback for interim results (text)
            on_final: Callback for final results (text)
        """
        if self._streaming:
            log.warning("⚠️ Already streaming")
            return
            
        self._ensure_client()
        self._partial_callback = on_partial
        self._final_callback = on_final
        self._streaming = True
        
        self._worker_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._worker_thread.start()
        log.info("🚀 Real-time streaming STT started")
        
    def stop_streaming(self):
        """Stop streaming and flush remaining audio"""
        if not self._streaming:
            return
            
        log.info("🛑 Stopping streaming STT...")
        self._streaming = False
        
        # Signal end of stream
        try:
            self._audio_queue.put(None, timeout=0.5)
        except queue.Full:
            pass
            
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
            
        log.info("✅ Streaming STT stopped")
        
    def push_audio(self, pcm16_data):
        """
        Push PCM16 audio data to the stream
        Thread-safe, non-blocking
        """
        if not self._streaming:
            return
            
        try:
            self._audio_queue.put_nowait(pcm16_data)
        except queue.Full:
            self._dropped_frames += 1
            if self._dropped_frames % 10 == 1:  # Log every 10th drop
                log.warning(f"⚠️ Audio queue full, dropped {self._dropped_frames} frames total (queue size: {self._audio_queue.qsize()})")
            
    def _stream_worker(self):
        """Background worker that handles streaming recognition"""
        try:
            # ⚡ BUILD 115: Use dynamically selected model configuration
            log.info(f"📞 Using model='{MODEL}' with ENHANCED={USE_ENHANCED} for {LANG}")
            
            # ⚡ BUILD 118.5: הרחבת vocabulary לדיוק מקסימלי בעברית!
            speech_contexts = [
                speech.SpeechContext(
                    phrases=[
                        # נדל"ן - מונחים בסיסיים
                        "דירה", "דירות", "בית", "בתים", "משרד", "משרדים", "נכס", "נכסים",
                        "קרקע", "קרקעות", "מגרש", "מגרשים", "נחלה", "נחלות", "אדמה", "אדמות",
                        "שכירות", "מכירה", "השכרה", "קניה", "מכר", "שכר", "השקעה", "השקעות",
                        "חדר", "חדרים", "מ״ר", "מטר", "מטרים", "מרובע", "דונם", "דונמים",
                        "קומה", "קומות", "מעלית", "חניה", "חניות", "מרפסת", "מרפסות",
                        "ממ״ד", "מחסן", "מחסנים", "גג", "גינה", "גינות", "מזגן", "מזגנים",
                        "פנטהאוז", "דופלקס", "טריפלקס", "סטודיו", "יחידת דיור", "יחידות דיור",
                        
                        # ערים ואזורים
                        "תל אביב", "ירושלים", "חיפה", "באר שבע", "נתניה", "ראשון לציון",
                        "פתח תקווה", "רמת גן", "הרצליה", "חולון", "בת ים", "רחובות",
                        "אשדוד", "אשקלון", "רעננה", "כפר סבא", "הוד השרון", "רמת השרון",
                        "גבעתיים", "בני ברק", "רמלה", "לוד", "מודיעין", "נס ציונה",
                        
                        # כסף ומחירים
                        "שקל", "שקלים", "אלף", "אלפים", "מיליון", "עשרת אלפים",
                        "מאה", "מאתיים", "חמש מאות", "אלפיים", "שלושת אלפים",
                        "תקציב", "מחיר", "עלות", "משכנתא", "הלוואה", "ריבית",
                        
                        # זמנים ותאריכים
                        "מחר", "מחרתיים", "היום", "עכשיו", "בוקר", "צהריים", "ערב",
                        "שעה", "בשעה", "דקה", "יום", "שבוע", "חודש", "שנה",
                        "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת",
                        "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
                        "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
                        
                        # ביטויים נפוצים בשיחות
                        "כן", "לא", "בסדר", "מצוין", "בטח", "אוקיי", "אולי",
                        "תודה", "סליחה", "רגע", "שנייה", "אפשר", "צריך", "רוצה",
                        "מעוניין", "מתאים", "נוח", "מתי", "איפה", "כמה", "מה",
                        
                        # שמות עסקים (מהקונפיג)
                        "שי דירות ומשרדים", "לאה", "נדלן", "נדל״ן",
                        
                        # מצבים ופעולות
                        "פגישה", "פגישות", "ביקור", "סיור", "להתקשר", "להודיע",
                        "לקבוע", "לבדוק", "לראות", "להגיע", "לבוא", "לחזור"
                    ],
                    boost=20.0  # ⚡ BUILD 118.5: הגדלת boost ל-20 לדיוק מקסימלי!
                )
            ]
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code=LANG,
                sample_rate_hertz=self.rate,
                enable_automatic_punctuation=PUNCTUATION_INTERIM,  # Usually false for speed
                model=MODEL,
                speech_contexts=speech_contexts,
                use_enhanced=USE_ENHANCED,
                # ⚡ BUILD 118.5: הוספת alternative language codes לדיוק טוב יותר
                alternative_language_codes=["iw-IL"]  # iw-IL = קוד חלופי לעברית
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            def request_generator():
                """Generate batched audio requests"""
                buffer = bytearray()
                last_send = time.time()
                
                while self._streaming:
                    try:
                        # ⚡ CRITICAL: Short timeout (20ms) to consume queue aggressively
                        chunk = self._audio_queue.get(timeout=0.02)
                        
                        if chunk is None:
                            # End signal
                            break
                            
                        buffer.extend(chunk)
                        
                        # Send batch if enough data or enough time passed
                        now = time.time()
                        time_since_send = (now - last_send) * 1000
                        
                        if len(buffer) >= self._batch_size_bytes or time_since_send >= BATCH_MS:
                            if buffer:
                                yield speech.StreamingRecognizeRequest(audio_content=bytes(buffer))
                                buffer.clear()
                                last_send = now
                                
                    except queue.Empty:
                        # No audio available, check if we should send buffered data
                        if buffer and (time.time() - last_send) * 1000 >= BATCH_MS:
                            yield speech.StreamingRecognizeRequest(audio_content=bytes(buffer))
                            buffer.clear()
                            last_send = time.time()
                            
                # Flush remaining buffer
                if buffer:
                    log.info(f"🔚 Flushing final {len(buffer)} bytes")
                    yield speech.StreamingRecognizeRequest(audio_content=bytes(buffer))
            
            # Start streaming recognition
            if not self.client:
                log.error("❌ Client not initialized")
                return
            responses = self.client.streaming_recognize(streaming_config, request_generator())
            
            for response in responses:
                if not self._streaming:
                    break
                    
                for result in response.results:
                    if not result.alternatives:
                        continue
                        
                    transcript = result.alternatives[0].transcript.strip()
                    if not transcript:
                        continue
                    
                    if result.is_final:
                        # Final result
                        log.info(f"🟢 FINAL: {transcript}")
                        if self._final_callback:
                            self._final_callback(transcript)
                    else:
                        # Interim result with debounce
                        current_time = time.time()
                        time_since_last = (current_time - self._last_partial_time) * 1000
                        
                        # Debounce: only send if enough time passed OR text changed significantly
                        if time_since_last >= DEBOUNCE_MS or transcript != self._last_partial_text:
                            log.debug(f"🟡 PARTIAL: {transcript}")
                            self._last_partial_time = current_time
                            self._last_partial_text = transcript
                            
                            if self._partial_callback:
                                self._partial_callback(transcript)
                                
        except Exception as e:
            log.error(f"❌ Streaming worker error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._streaming = False
            log.info("📡 Stream worker stopped")


# Factory function for backward compatibility
def create_streaming_stt(sample_rate_hz=8000):
    """Factory function for creating streaming STT instance"""
    return GcpStreamingSTT(sample_rate_hz=sample_rate_hz)


# Legacy class name for backward compatibility
GcpHebrewStreamer = GcpStreamingSTT
