"""
ULTRA-LOW-LATENCY Google Cloud Speech-to-Text Streaming for Hebrew
Optimized for real-time phone conversations with Twilio Media Streams

Key optimizations:
1. Fast μ-law→PCM conversion (lookup table, ~10-20x faster)
2. Smart batching (100-200ms) to reduce overhead
3. Partial debounce (150-250ms) to avoid flooding
4. Phone call model for telephony
5. Disabled punctuation in interim results for speed
"""
import os
import json
from google.cloud import speech
import base64
import logging
import threading
import queue
import time
from server.services.mulaw_fast import mulaw_to_pcm16_fast

log = logging.getLogger("gcp_stt_stream")

class GcpHebrewStreamerOptimized:
    """Ultra-low-latency Hebrew STT for Twilio (target: <1.2s first partial)"""
    
    def __init__(self, sample_rate_hz=8000):
        self.client = None
        self.rate = sample_rate_hz
        
        # Audio batching for efficiency (100-200ms chunks)
        self._audio_buffer = bytearray()
        self._audio_lock = threading.Lock()
        self._batch_size_bytes = int(sample_rate_hz * 2 * 0.15)  # 150ms of PCM16
        
        # Results with debounce
        self._last_partial_text = ""
        self._last_partial_time = 0.0
        self._partial_debounce_sec = 0.18  # 180ms between partials
        self._results_queue = queue.Queue()
        
        # Streaming control
        self._streaming = False
        self._thread = None
        self._flush_remaining = False
        
    def _ensure_client(self):
        """Lazy initialization of Speech client"""
        if self.client is None:
            try:
                sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
                if sa_json:
                    credentials_info = json.loads(sa_json)
                    self.client = speech.SpeechClient.from_service_account_info(credentials_info)
                    log.info("✅ Speech client initialized (service account)")
                else:
                    self.client = speech.SpeechClient()
                    log.info("✅ Speech client initialized (default)")
            except Exception as e:
                log.error(f"❌ Failed to initialize Speech client: {e}")
                raise
        
    def start(self):
        """Start streaming recognition"""
        if self._streaming:
            return
            
        self._ensure_client()
        self._streaming = True
        self._thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._thread.start()
        log.info("🚀 Ultra-low-latency Hebrew STT started")
        
    def stop(self):
        """Stop streaming recognition and flush remaining audio"""
        # ✅ FIX: Flush remaining buffered audio before stopping
        with self._audio_lock:
            if len(self._audio_buffer) > 0:
                log.info(f"📤 Flushing {len(self._audio_buffer)} bytes of remaining audio")
                # Mark that we want to flush
                self._flush_remaining = True
        
        self._streaming = False
        if self._thread:
            self._thread.join(timeout=1.0)
        log.info("🛑 STT stopped")
        
    def push_ulaw_base64(self, b64_payload):
        """
        Fast μ-law decode and buffering
        This is called from WebSocket loop - MUST BE FAST (<2ms)
        """
        if not self._streaming:
            return
            
        try:
            # Fast decode: base64 → μ-law → PCM16
            mulaw_data = base64.b64decode(b64_payload)
            pcm16_data = mulaw_to_pcm16_fast(mulaw_data)  # ⚡ 10-20x faster than audioop
            
            # Buffer for batching (reduces STT API overhead)
            with self._audio_lock:
                self._audio_buffer.extend(pcm16_data)
                
        except Exception as e:
            log.error(f"❌ Audio decode error: {e}")
            
    def get_results(self):
        """Get available transcription results [(text, is_final)]"""
        results = []
        try:
            while not self._results_queue.empty():
                results.append(self._results_queue.get_nowait())
        except queue.Empty:
            pass
        return results
        
    def _stream_worker(self):
        """Background worker with optimized config"""
        try:
            # ⚡ OPTIMIZED CONFIG for low latency
            speech_contexts = [
                speech.SpeechContext(
                    phrases=[
                        "שי דירות ומשרדים", "לאה", "דירה", "משרד", "שכר", "מכירה",
                        "חדרים", "מטר", "קומה", "מעלית", "חניה", "מרפסת", "אזור",
                        "תל אביב", "ירושלים", "חיפה", "פתח תקווה", "רמת גן",
                        "שקל", "אלף", "מיליון", "תקציב", "משכנתא", "נדלן"
                    ],
                    boost=15.0  # Strong boost for common terms
                )
            ]
            
            # ✅ FIX: Default model for he-IL (phone_call + enhanced not supported)
            model = os.getenv("GCP_STT_MODEL", "default")
            use_enhanced = os.getenv("GCP_STT_ENHANCED", "true").lower() == "true"
            
            # ✅ SAFE: Don't combine phone_call with enhanced for he-IL
            if model == "phone_call":
                use_enhanced = False
                log.info("📞 Using phone_call model (enhanced disabled for compatibility)")
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="he-IL",
                sample_rate_hertz=self.rate,
                
                # ⚡ SPEED: Disable punctuation in interim results
                enable_automatic_punctuation=False,
                
                # ✅ Safe model selection
                model=model,
                speech_contexts=speech_contexts,
                use_enhanced=use_enhanced
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,  # ✅ Critical for low latency
                single_utterance=False,
            )
            
            def audio_generator():
                """
                Generate batched audio chunks (100-200ms)
                Reduces API overhead while maintaining low latency
                """
                while self._streaming:
                    try:
                        # Check if we have enough data for a batch
                        with self._audio_lock:
                            if len(self._audio_buffer) >= self._batch_size_bytes:
                                # Send batch
                                chunk = bytes(self._audio_buffer[:self._batch_size_bytes])
                                del self._audio_buffer[:self._batch_size_bytes]
                            else:
                                chunk = None
                        
                        if chunk:
                            yield speech.StreamingRecognizeRequest(audio_content=chunk)
                        else:
                            # Small sleep to avoid spinning
                            time.sleep(0.02)  # 20ms
                            
                    except Exception as e:
                        log.error(f"❌ Audio generator error: {e}")
                        break
                
                # ✅ FIX: Flush remaining audio when streaming stops
                if self._flush_remaining:
                    with self._audio_lock:
                        if len(self._audio_buffer) > 0:
                            final_chunk = bytes(self._audio_buffer)
                            self._audio_buffer.clear()
                            log.info(f"🔚 Flushing final {len(final_chunk)} bytes")
                            yield speech.StreamingRecognizeRequest(audio_content=final_chunk)
                        
            # Start streaming recognition
            if self.client is None:
                log.error("❌ Speech client not initialized")
                return
                
            responses = self.client.streaming_recognize(streaming_config, audio_generator())
            
            for response in responses:
                if not self._streaming:
                    break
                    
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript.strip()
                        
                        if not transcript:
                            continue
                        
                        # ⚡ DEBOUNCE partials to avoid flooding (150-250ms)
                        is_final = result.is_final
                        current_time = time.time()
                        
                        if not is_final:
                            # Partial result - apply debounce
                            time_since_last = current_time - self._last_partial_time
                            
                            if time_since_last < self._partial_debounce_sec:
                                # Too soon - skip this partial
                                continue
                            
                            # Update debounce tracking
                            self._last_partial_text = transcript
                            self._last_partial_time = current_time
                        
                        # Queue result
                        self._results_queue.put((transcript, is_final))
                        
                        # Log for monitoring
                        result_type = "FINAL" if is_final else "PARTIAL"
                        log.debug(f"📝 {result_type}: {transcript[:50]}...")
                            
        except Exception as e:
            log.error(f"❌ STT worker failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._streaming = False
            log.info("STT worker stopped")
