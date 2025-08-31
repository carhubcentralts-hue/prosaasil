"""
Google Cloud Speech-to-Text Streaming for Hebrew
Real-time Hebrew speech recognition from Twilio Media Streams
"""
import os
import json
from google.cloud import speech
import base64
import audioop
import logging
import threading
import queue
import time

log = logging.getLogger("gcp_stt_stream")

class GcpHebrewStreamer:
    """Real-time Hebrew speech recognition for Twilio Media Streams"""
    
    def __init__(self, sample_rate_hz=8000):
        self.client = None
        self.rate = sample_rate_hz
        self._audio_queue = queue.Queue()
        self._results_queue = queue.Queue()
        self._streaming = False
        self._stream = None
        self._thread = None
        
    def _ensure_client(self):
        """Lazy initialization of Speech client with proper credentials"""
        if self.client is None:
            try:
                # Use service account JSON from environment (same as TTS)
                import json
                sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
                if sa_json:
                    credentials_info = json.loads(sa_json)
                    self.client = speech.SpeechClient.from_service_account_info(credentials_info)
                    log.info("✅ Google Cloud Speech client initialized with credentials")
                else:
                    # Fallback to default credentials
                    self.client = speech.SpeechClient()
                    log.info("✅ Google Cloud Speech client initialized (default)")
            except Exception as e:
                log.error(f"❌ Failed to initialize Speech client: {e}")
                raise
        
    def start(self):
        """Start streaming recognition"""
        if self._streaming:
            return
            
        # Ensure client is initialized
        self._ensure_client()
            
        self._streaming = True
        self._thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._thread.start()
        log.info("Hebrew streaming ASR started")
        
    def stop(self):
        """Stop streaming recognition"""
        self._streaming = False
        if self._thread:
            self._thread.join(timeout=1.0)
        log.info("Hebrew streaming ASR stopped")
        
    def push_ulaw_base64(self, b64_payload):
        """Push μ-law audio from Twilio Media Streams"""
        if not self._streaming:
            return
            
        try:
            # Decode base64 → μ-law → PCM 16-bit
            mulaw_data = base64.b64decode(b64_payload)
            pcm16_data = audioop.ulaw2lin(mulaw_data, 2)
            
            # Queue for processing
            if not self._audio_queue.full():
                self._audio_queue.put(pcm16_data, block=False)
                
        except Exception as e:
            log.error(f"Audio conversion failed: {e}")
            
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
        """Background worker for streaming recognition"""
        try:
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="he-IL",
                sample_rate_hertz=self.rate,
                enable_automatic_punctuation=True,
                model="latest_long",
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            def audio_generator():
                """Generate audio chunks for streaming"""
                while self._streaming:
                    try:
                        chunk = self._audio_queue.get(timeout=0.1)
                        yield speech.StreamingRecognizeRequest(audio_content=chunk)
                    except queue.Empty:
                        continue
                    except Exception as e:
                        log.error(f"Audio generator error: {e}")
                        break
                        
            # Start streaming recognition with client validation
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
                        if transcript:
                            self._results_queue.put((transcript, result.is_final))
                            
        except Exception as e:
            log.error(f"Streaming ASR worker failed: {e}")
        finally:
            self._streaming = False