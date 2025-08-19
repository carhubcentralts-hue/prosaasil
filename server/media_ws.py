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
from flask import current_app
from server.logging_setup import set_request_context
from server.stream_state import stream_registry

log = logging.getLogger(__name__)

def handle_media_stream_simple(ws):
    """Handle Twilio Media Stream WebSocket - simple-websocket compatible"""
    try:
        log.info("🔗 Media stream WebSocket connection opened")
        print("🔗 WebSocket connection established!")
        
        # Create handler instance
        handler = MediaStreamHandler(ws)
        handler.handle_connection()
        
    except Exception as e:
        log.error("WebSocket handler failed: %s", e)
    finally:
        log.info("🔌 Media stream WebSocket connection closed")

class MediaStreamHandler:
    """Handle Twilio Media Stream WebSocket connections"""
    
    def __init__(self, websocket):
        self.websocket = websocket
        self.call_sid = None
        self.stream_sid = None
        self.business_id = None
        self.is_connected = False
        self.heartbeat_timer = None
        current_app.logger.info("WS_CONNECTED")
        
    def handle_connection(self):
        """Main WebSocket connection handler"""
        try:
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
            
            print(f"🔥 WebSocket message: {event}", flush=True)
            
            if event == 'connected':
                log.info("Media stream connected", extra={"protocol_version": data.get('protocol')})
                print(f"✅ WebSocket connected successfully", flush=True)
                
            elif event == 'start':
                # Extract parameters - CRITICAL: Use exact streamSid from Twilio
                self.call_sid = data.get('start', {}).get('callSid')
                self.stream_sid = data.get('start', {}).get('streamSid')  # ← Must be EXACT from Twilio
                custom_params = data.get('start', {}).get('customParameters', {})
                self.business_id = custom_params.get('business_id', '1')
                
                # Set logging context
                set_request_context(self.call_sid, self.business_id)
                
                # CRITICAL: Log exact streamSid received from Twilio
                log.info("WS_START", extra={
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,  # ← This must be used exactly for all mark/clear
                    "business_id": self.business_id,
                    "media_format": data.get('start', {}).get('mediaFormat')
                })
                
                # Mark stream as started in registry
                if self.call_sid:
                    stream_registry.mark_start(self.call_sid)
                    print(f"✅ Stream registry marked start for {self.call_sid}", flush=True)
                
                print(f"📡 WebSocket START: call={self.call_sid}, streamSid={self.stream_sid}", flush=True)
                print(f"🔍 EXACT streamSid from Twilio: '{self.stream_sid}'", flush=True)
                
                # Send automatic Hebrew greeting when stream starts
                self._send_automatic_greeting()
                
            elif event == 'media':
                # Touch media activity in registry
                if self.call_sid:
                    stream_registry.touch_media(self.call_sid)
                # Process audio data
                self._process_audio(data.get('media', {}))
                
            elif event == 'stop':
                log.info("Media stream stopped", extra={"call_sid": self.call_sid})
                current_app.logger.info("WS_STOP", extra={"call_sid": self.call_sid})
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
        
        try:
            # Step 1: Transcribe Hebrew with Whisper
            from server.services.whisper_handler import transcribe_he
            call_sid = self.call_sid or "unknown"
            transcript = transcribe_he(audio_bytes, call_sid)
            
            if not transcript:
                log.info("No valid transcript - ignoring audio chunk")
                return
                
            log.info("🧠 Hebrew transcript received", extra={
                "call_sid": self.call_sid,
                "transcript": transcript[:100],
                "chars": len(transcript)
            })
            
            # Step 2: Generate Hebrew AI response using GPT
            response_text = self._generate_ai_response(transcript)
            
            if not response_text:
                response_text = "מצטער, לא הבנתי. אתה יכול לחזור על השאלה?"
                
            log.info("🤖 AI response generated", extra={
                "call_sid": self.call_sid,
                "response": response_text[:100]
            })
            
            # Step 3: Generate Hebrew TTS and save for fallback
            tts_audio = self._generate_hebrew_tts(response_text)
            
            if tts_audio:
                # Save response for potential playback via recording fallback
                self._save_response_audio(response_text, tts_audio)
                
                # Mark that response is ready (only mark/clear allowed in Media Streams)
                self._send_mark("response_generated")
                
                log.info("🗣️ Hebrew AI response prepared", extra={
                    "call_sid": self.call_sid,
                    "transcript": transcript[:50],
                    "response": response_text[:50],
                    "audio_size": len(tts_audio)
                })
            else:
                log.warning("TTS generation failed", extra={"call_sid": self.call_sid})
                
        except Exception as e:
            log.error("AI pipeline failed: %s", e, extra={"call_sid": self.call_sid})
            
    def _generate_hebrew_tts(self, text):
        """Generate Hebrew TTS using Google Cloud"""
        try:
            import os
            import json
            from google.cloud import texttospeech
            
            # Set up Google credentials from environment
            sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
            if sa_json:
                creds_path = '/tmp/google_service_account.json'
                with open(creds_path, 'w') as f:
                    f.write(sa_json)
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
        """
        IMPORTANT: Twilio Media Streams does NOT support sending audio back!
        Only mark/clear events are allowed. This function is disabled.
        """
        log.warning("Audio sending disabled - Twilio Media Streams only accepts mark/clear events", extra={
            "call_sid": self.call_sid,
            "audio_size": len(audio_data) if audio_data else 0
        })
        # Instead, we could use mark events to signal completion
        self._send_mark("audio_response_ready")
            
    def _send_automatic_greeting(self):
        """Send automatic Hebrew greeting when stream starts"""
        try:
            # Get business-specific greeting
            greeting_text = self._get_business_greeting()
            
            log.info("🎙️ Sending automatic Hebrew greeting", extra={
                "call_sid": self.call_sid,
                "business_id": self.business_id,
                "greeting": greeting_text[:50]
            })
            
            # Generate Hebrew TTS greeting
            greeting_audio = self._generate_hebrew_tts(greeting_text)
            
            if greeting_audio:
                # Save greeting for potential playback (Media Streams can't send audio back)
                self._save_response_audio("greeting", greeting_audio)
                
                # Mark greeting ready
                self._send_mark("greeting_ready")
                
                log.info("✅ Automatic greeting prepared", extra={
                    "call_sid": self.call_sid,
                    "audio_size": len(greeting_audio)
                })
            else:
                log.warning("❌ Failed to generate greeting audio", extra={"call_sid": self.call_sid})
                
        except Exception as e:
            log.error("Failed to send automatic greeting: %s", e, extra={"call_sid": self.call_sid})
            
    def _get_business_greeting(self):
        """Get business-specific Hebrew greeting"""
        if self.business_id == "1":  # Shai Real Estate
            return """שלום וברוכים הבאים לשי דירות ומשרדים בעמ! 
אני העוזר הדיגיטלי שלנו ואני כאן לעזור לכם למצוא את הנכס המושלם. 
איך אוכל לעזור לכם היום?"""
        else:
            return "שלום! איך אוכל לעזור לכם היום?"
            
    def _generate_ai_response(self, transcript):
        """Generate AI response using GPT-4o for Hebrew real estate conversation"""
        try:
            import openai
            import os
            
            if os.getenv("NLP_DISABLED", "false").lower() in ("true", "1"):
                return "המערכת זמנית לא זמינה. אנא נסו שוב מאוחר יותר."
            
            # Get business-specific prompt  
            system_prompt = self._load_business_prompt()

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
            else:
                ai_response = "מצטער, לא הבנתי."
            
            log.info("GPT-4o Hebrew response generated", extra={
                "call_sid": self.call_sid,
                "input_chars": len(transcript),
                "output_chars": len(ai_response)
            })
            
            return ai_response
            
        except Exception as e:
            log.error("AI response generation failed: %s", e, extra={"call_sid": self.call_sid})
            return "מצטער, יש לי בעיה טכנית. אתה יכול לנסות שוב או להתקשר מאוחר יותר?"
        
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
        
    def _send_mark(self, name: str):
        """Send mark event to Twilio (only allowed outbound message type)"""
        try:
            if not self.stream_sid:
                log.warning("Cannot send mark - no stream_sid", extra={"call_sid": self.call_sid})
                return
                
            # CRITICAL: Use EXACT streamSid from Twilio start event
            mark_message = {
                "event": "mark",
                "streamSid": self.stream_sid,  # ← Must be EXACT from start event
                "mark": {"name": name}
            }
            
            # CRITICAL: Log exact streamSid being sent back to Twilio
            print(f"🔍 SENDING MARK streamSid: '{self.stream_sid}' (call: {self.call_sid})", flush=True)
            
            self.websocket.send(json.dumps(mark_message))
            
            log.info("WS_TX_MARK", extra={
                "call_sid": self.call_sid,
                "stream_sid": self.stream_sid,  # ← This should match exactly what we got in start
                "mark_name": name
            })
            
        except Exception as e:
            log.error("Failed to send mark: %s", e, extra={"call_sid": self.call_sid})
            
    def _save_response_audio(self, text: str, audio_data: bytes):
        """Save response audio for fallback playback"""
        try:
            import hashlib
            import os
            
            # Create unique filename
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"response_{self.call_sid}_{text_hash}.wav"
            filepath = f"/tmp/{filename}"
            
            # Save audio file
            with open(filepath, 'wb') as f:
                f.write(audio_data)
                
            log.info("Response audio saved", extra={
                "call_sid": self.call_sid,
                "filepath": filepath,
                "size": len(audio_data)
            })
            
        except Exception as e:
            log.error("Failed to save response audio: %s", e)
    
    def _cleanup(self):
        """Clean up connection resources"""
        self.is_connected = False
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
        log.info("Media stream connection closed", extra={"call_sid": self.call_sid})

# Main entry point is already defined at top of file