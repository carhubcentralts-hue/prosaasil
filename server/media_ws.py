"""
WebSocket Media Streaming Handler - Moved from root
Real-time Hebrew AI conversation processing
"""
import json
import base64
import logging
import time
import threading
from typing import Optional
from server.logging_setup import set_request_context

log = logging.getLogger(__name__)

class MediaStreamHandler:
    """Handle Twilio Media Stream WebSocket connections"""
    
    def __init__(self, websocket):
        self.websocket = websocket
        self.call_sid = None
        self.business_id = None
        self.is_connected = False
        self.heartbeat_timer = None
        
    def handle_connection(self):
        """Main WebSocket connection handler"""
        try:
            log.info("Media stream connection opened")
            self.is_connected = True
            self._start_heartbeat()
            
            # Handle messages
            while self.is_connected:
                try:
                    message = self.websocket.receive()
                    if message is None:
                        break
                        
                    self._handle_message(message)
                    
                except Exception as e:
                    log.error("Message handling error: %s", e)
                    break
                    
        except Exception as e:
            log.error("WebSocket connection error: %s", e)
        finally:
            self._cleanup()
            
    def _handle_message(self, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            event = data.get('event')
            
            if event == 'connected':
                log.info("Media stream connected", extra={"protocol_version": data.get('protocol')})
                
            elif event == 'start':
                # Extract parameters
                self.call_sid = data.get('start', {}).get('callSid')
                custom_params = data.get('start', {}).get('customParameters', {})
                self.business_id = custom_params.get('business_id', '1')
                
                # Set logging context
                set_request_context(self.call_sid, self.business_id)
                
                log.info("Media stream started", extra={
                    "call_sid": self.call_sid,
                    "business_id": self.business_id,
                    "media_format": data.get('start', {}).get('mediaFormat')
                })
                
            elif event == 'media':
                # Process audio data
                self._process_audio(data.get('media', {}))
                
            elif event == 'stop':
                log.info("Media stream stopped", extra={"call_sid": self.call_sid})
                self.is_connected = False
                
        except json.JSONDecodeError as e:
            log.error("Invalid JSON message: %s", e)
        except Exception as e:
            log.error("Message processing error: %s", e, extra={"call_sid": self.call_sid})
            
    def _process_audio(self, media_data):
        """Process incoming audio chunk"""
        if not media_data:
            return
            
        start_time = time.time()
        
        try:
            # Decode audio
            payload = media_data.get('payload', '')
            audio_bytes = base64.b64decode(payload)
            
            t_audio_ms = int((time.time() - start_time) * 1000)
            
            # Process with Whisper + GPT + TTS pipeline
            # Real-time AI conversation processing
            self._process_with_ai(audio_bytes)
            
            # For now, log metrics
            log.info("turn_metrics", extra={
                "call_sid": self.call_sid,
                "business_id": self.business_id,
                "turn_id": f"{self.call_sid}_{int(time.time())}",
                "t_audio_ms": t_audio_ms,
                "t_nlp_ms": 0,  # Placeholder
                "t_tts_ms": 0,  # Placeholder  
                "t_total_ms": t_audio_ms,
                "mode": "stream",
                "audio_bytes": len(audio_bytes)
            })
            
        except Exception as e:
            log.error("Audio processing failed: %s", e, extra={
                "call_sid": self.call_sid,
                "error_details": str(e)
            })
            
    def _process_with_ai(self, audio_bytes):
        """Process audio with Whisper + GPT + TTS pipeline"""
        try:
            # Import services
            from server.services.whisper_handler import transcribe_he
            
            # Transcribe audio
            text = transcribe_he(audio_bytes, self.call_sid)
            
            if text and len(text.strip()) > 2:
                log.info("Real-time transcription", extra={
                    "call_sid": self.call_sid,
                    "text": text[:100],
                    "mode": "live_stream"
                })
                
                # TODO: Generate AI response and send back via TTS
                # For now just log the successful transcription
                
            else:
                log.debug("No speech detected in chunk", extra={"call_sid": self.call_sid})
                
        except Exception as e:
            log.error("AI pipeline failed: %s", e, extra={"call_sid": self.call_sid})
            
    def _start_heartbeat(self):
        """Start heartbeat timer"""
        def heartbeat():
            if self.is_connected:
                log.debug("ws_heartbeat", extra={"call_sid": self.call_sid})
                # Schedule next heartbeat
                self.heartbeat_timer = threading.Timer(15.0, heartbeat)
                self.heartbeat_timer.start()
                
        self.heartbeat_timer = threading.Timer(15.0, heartbeat)
        self.heartbeat_timer.start()
        
    def _cleanup(self):
        """Clean up connection resources"""
        self.is_connected = False
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
        log.info("Media stream connection closed", extra={"call_sid": self.call_sid})

def handle_media_stream(websocket):
    """Main entry point for media stream WebSocket"""
    handler = MediaStreamHandler(websocket)
    handler.handle_connection()