"""
Real-time Streaming STT for Hebrew with Google Cloud Speech
Optimized for ultra-low latency phone conversations

Based on Phase 2 optimization guidelines:
- Batching: 150ms chunks
- Partial debounce: 180ms
- Thread-safe for sync WebSocket handlers
"""
import os
import json
import time
import threading
import queue
import logging
from google.cloud import speech

log = logging.getLogger("gcp_stt_stream")

# Configuration from environment
BATCH_MS = int(os.getenv("STT_BATCH_MS", "150"))
DEBOUNCE_MS = int(os.getenv("STT_PARTIAL_DEBOUNCE_MS", "180"))
LANG = os.getenv("GCP_STT_LANGUAGE", "he-IL")
MODEL = os.getenv("GCP_STT_MODEL", "default")
PUNCTUATION_INTERIM = os.getenv("GCP_STT_PUNCTUATION_INTERIM", "false").lower() == "true"
PUNCTUATION_FINAL = os.getenv("GCP_STT_PUNCTUATION_FINAL", "true").lower() == "true"

class GcpStreamingSTT:
    """
    Thread-safe streaming STT service
    Designed to work with sync WebSocket handlers
    """
    
    def __init__(self, sample_rate_hz=8000):
        self.client = None
        self.rate = sample_rate_hz
        
        # Audio queue for batching
        self._audio_queue = queue.Queue(maxsize=100)
        self._batch_size_bytes = int(sample_rate_hz * 2 * (BATCH_MS / 1000.0))  # PCM16
        
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
            log.warning("⚠️ Audio queue full, dropping frame")
            
    def _stream_worker(self):
        """Background worker that handles streaming recognition"""
        try:
            # Configure recognition
            use_enhanced = os.getenv("GCP_STT_ENHANCED", "true").lower() == "true"
            
            # Safe model selection for he-IL
            model = MODEL
            if model == "phone_call":
                use_enhanced = False
                log.info("📞 Using phone_call model (enhanced disabled for he-IL)")
            
            speech_contexts = [
                speech.SpeechContext(
                    phrases=[
                        "שי דירות ומשרדים", "לאה", "דירה", "משרד", "שכר", "מכירה",
                        "חדרים", "מטר", "קומה", "מעלית", "חניה", "מרפסת", "אזור",
                        "תל אביב", "ירושלים", "חיפה", "פתח תקווה", "רמת גן",
                        "שקל", "אלף", "מיליון", "תקציב", "משכנתא", "נדלן"
                    ],
                    boost=15.0
                )
            ]
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code=LANG,
                sample_rate_hertz=self.rate,
                enable_automatic_punctuation=PUNCTUATION_INTERIM,  # Usually false for speed
                model=model,
                speech_contexts=speech_contexts,
                use_enhanced=use_enhanced
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
                        # Get audio from queue (blocking with timeout)
                        chunk = self._audio_queue.get(timeout=0.05)
                        
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
