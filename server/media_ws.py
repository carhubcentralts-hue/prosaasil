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
            log.info("🔗 Media stream connection opened")
            print("🔗 WebSocket connection established!")
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
                
                log.info("🎉 Media stream started for Shai Real Estate", extra={
                    "call_sid": self.call_sid,
                    "business_id": self.business_id,
                    "media_format": data.get('start', {}).get('mediaFormat')
                })
                
                print(f"📡 WebSocket connected: {self.call_sid}")
                
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
        log.info("🎤 Processing audio chunk", extra={
            "call_sid": self.call_sid,
            "business_id": self.business_id,
            "audio_size": len(audio_bytes)
        })
        
        # For now, send back a simple Hebrew response to test the pipeline
        try:
            # Send a test Hebrew TTS response back to Twilio
            response_text = "שלום, אני שומע אותך. זה עובד!"
            
            # Generate TTS audio
            tts_audio = self._generate_hebrew_tts(response_text)
            
            if tts_audio:
                # Send audio back through WebSocket 
                self._send_audio_to_twilio(tts_audio)
                log.info("🗣️ Sent Hebrew TTS response", extra={
                    "call_sid": self.call_sid,
                    "text": response_text,
                    "audio_size": len(tts_audio)
                })
            else:
                log.warning("TTS generation failed", extra={"call_sid": self.call_sid})
                
        except Exception as e:
            log.error("TTS pipeline failed: %s", e, extra={"call_sid": self.call_sid})
            
    def _generate_hebrew_tts(self, text):
        """Generate Hebrew TTS using Google Cloud"""
        try:
            import os
            import json
            from google.cloud import texttospeech
            
            # Set up Google credentials from environment
            if os.getenv('GOOGLE_TTS_SA_JSON'):
                creds_path = '/tmp/google_service_account.json'
                with open(creds_path, 'w') as f:
                    f.write(os.getenv('GOOGLE_TTS_SA_JSON'))
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
            
            # Initialize TTS client
            client = texttospeech.TextToSpeechClient()
            
            # Configure Hebrew voice
            voice = texttospeech.VoiceSelectionParams(
                language_code="he-IL",
                name="he-IL-Wavenet-B"  # Female Hebrew voice
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MULAW,
                sample_rate_hertz=8000  # Twilio format
            )
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Generate speech
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            return response.audio_content
            
        except Exception as e:
            log.error("Hebrew TTS generation failed: %s", e)
            return None
            
    def _send_audio_to_twilio(self, audio_data):
        """Send audio back to Twilio via WebSocket"""
        try:
            import base64
            
            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Create Twilio media message
            media_message = {
                "event": "media",
                "streamSid": f"MZ{self.call_sid}",
                "media": {
                    "payload": audio_b64
                }
            }
            
            # Send via WebSocket
            self.websocket.send(json.dumps(media_message))
            log.info("Audio sent to Twilio", extra={
                "call_sid": self.call_sid,
                "payload_size": len(audio_b64)
            })
            
        except Exception as e:
            log.error("Failed to send audio to Twilio: %s", e, extra={"call_sid": self.call_sid})
        
    def _load_business_prompt(self):
        """Load business system prompt from database"""
        try:
            # For now, return the known prompt for Shai Real Estate
            if self.business_id == "1":
                return '''אתה סוכן נדל"ן מקצועי עבור שי דירות ומשרדים בע"מ בישראל. 
אנחנו מתמחים במכירת דירות, השכרת נכסים, ייעוץ הערכת שווי ונכסי יוקרה. 
הצוות כולל 15 מתווכים מנוסים המכסים את תל אביב, ירושלים, חיפה והמרכז. 
דבר בעברית טבעית ומקצועית, היה ידידותי וסבלני. 
תמיד עזור ללקוחות למצוא את הפתרון הנכון.'''
            return "אתה עוזר AI מקצועי ונוח דבר בעברית."
        except Exception as e:
            log.error("Failed to load business prompt: %s", e)
            return "אתה עוזר AI מקצועי ונוח דבר בעברית."
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