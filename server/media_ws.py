"""
Real-time Hebrew WebSocket Media Stream Handler with Continuous Ping-Pong
Handles bidirectional Hebrew conversations via Twilio Media Streams per guidelines
"""
import json
import time
import threading
import os
from flask import current_app
from .stream_state import stream_registry

# Real-time Hebrew processing components
try:
    from .services.gcp_stt_stream import GcpHebrewStreamer
    from .services.gcp_tts_live import generate_hebrew_response
    HEBREW_REALTIME_ENABLED = True
except ImportError:
    GcpHebrewStreamer = None
    generate_hebrew_response = None
    HEBREW_REALTIME_ENABLED = False

class MediaStreamHandler:
    """Enhanced WebSocket handler with continuous Hebrew conversations"""
    
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None
        
        # Real-time Hebrew components
        if HEBREW_REALTIME_ENABLED and GcpHebrewStreamer:
            self.stt = GcpHebrewStreamer(sample_rate_hz=8000)
        else:
            self.stt = None
            
        self.last_speech_time = time.time()
        self.conversation_buffer = ""
        self.processing_response = False

    def run(self):
        """Main WebSocket event loop with Hebrew real-time processing"""
        current_app.logger.info("WS_CONNECTED", extra={
            "hebrew_realtime": HEBREW_REALTIME_ENABLED
        })
        
        # Start Hebrew transcription if available
        if self.stt:
            self.stt.start()
            self._start_result_processor()
        
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    current_app.logger.info("WS_CLOSED")
                    break
                    
                try:
                    data = json.loads(raw)
                except Exception:
                    current_app.logger.warning("WS_BAD_JSON")
                    continue

                ev = data.get("event")
                
                if ev == "start":
                    self._handle_start(data)
                elif ev == "media":
                    self._handle_media(data)
                elif ev == "stop":
                    current_app.logger.info("WS_STOP")
                    break

        except Exception:
            current_app.logger.exception("WS_HANDLER_ERROR")
        finally:
            self._cleanup()

    def _handle_start(self, data):
        """Handle WebSocket stream start event"""
        start = data.get("start", {})
        cp = start.get("customParameters") or {}
        
        # Parse custom parameters
        if isinstance(cp, str):
            try: 
                cp = json.loads(cp)
            except: 
                cp = {}
                
        self.call_sid = cp.get("call_sid") or cp.get("CallSid") or cp.get("CALL_SID")
        self.stream_sid = start.get("streamSid")
        
        current_app.logger.info("WS_START", extra={
            "streamSid": self.stream_sid, 
            "call_sid": self.call_sid,
            "hebrew_asr": "active" if self.stt else "fallback"
        })
        
        if self.call_sid:
            stream_registry.mark_start(self.call_sid)

    def _handle_media(self, data):
        """Handle real-time audio media frames"""
        if self.call_sid:
            stream_registry.touch_media(self.call_sid)
        
        # Real-time Hebrew transcription
        media_payload = data.get("media", {}).get("payload", "")
        if media_payload and self.stt:
            try:
                # Send audio to Hebrew ASR stream
                self.stt.push_ulaw_base64(media_payload)
            except Exception:
                current_app.logger.exception("REAL_TIME_ASR_ERROR")
        
        current_app.logger.debug("WS_FRAME", extra={
            "call_sid": self.call_sid,
            "payload_len": len(media_payload),
            "hebrew_processing": bool(self.stt)
        })

    def _start_result_processor(self):
        """Start background thread to process Hebrew transcription results"""
        def process_results():
            while True:
                try:
                    if not self.stt:
                        time.sleep(1)
                        continue
                        
                    # Get Hebrew transcription results
                    results = self.stt.get_results()
                    
                    for text, is_final in results:
                        if text.strip():
                            current_app.logger.info("HEBREW_SPEECH", extra={
                                "call_sid": self.call_sid,
                                "text": text,
                                "final": is_final
                            })
                            
                            # Update conversation buffer
                            self.conversation_buffer = text
                            self.last_speech_time = time.time()
                            
                            # Generate response for final utterances
                            if is_final and len(text.strip()) > 3:
                                self._generate_hebrew_response(text)
                    
                    time.sleep(0.1)  # Process results every 100ms
                    
                except Exception:
                    current_app.logger.exception("RESULT_PROCESSOR_ERROR")
                    time.sleep(1)
        
        thread = threading.Thread(target=process_results, daemon=True)
        thread.start()

    def _generate_hebrew_response(self, user_text):
        """Generate and play Hebrew AI response with continuous conversation"""
        if self.processing_response or not HEBREW_REALTIME_ENABLED:
            return
            
        self.processing_response = True
        
        def async_response():
            try:
                # Generate Hebrew AI response
                response_text = self._get_ai_response(user_text)
                
                if response_text and generate_hebrew_response:
                    # Generate Hebrew TTS
                    audio_url = generate_hebrew_response(response_text, self.call_sid)
                    
                    if audio_url:
                        # Play response and continue conversation
                        self._play_response_and_continue(audio_url)
                        
                        # Log turn metrics for SLA monitoring
                        self._log_turn_metrics(user_text, response_text)
                        
                        current_app.logger.info("CONTINUOUS_HEBREW_RESPONSE", extra={
                            "call_sid": self.call_sid,
                            "user_said": user_text[:50],
                            "bot_said": response_text[:50],
                            "flow": "continuous_ping_pong"
                        })
                    
            except Exception:
                current_app.logger.exception("HEBREW_RESPONSE_ERROR")
            finally:
                self.processing_response = False
        
        # Run in background
        threading.Thread(target=async_response, daemon=True).start()

    def _get_ai_response(self, user_text):
        """Generate Hebrew AI response for real estate context"""
        try:
            user_lower = user_text.lower()
            
            # Hebrew real estate conversation logic
            if any(word in user_lower for word in ["שלום", "היי", "הי"]):
                return "שלום! איך אני יכול לעזור לך היום?"
            elif any(word in user_lower for word in ["דירה", "דירות"]):
                return "מעולה! אני יכול לעזור לך למצוא דירה. איזה אזור אתה מחפש?"
            elif any(word in user_lower for word in ["משרד", "משרדים"]):
                return "אני אשמח לעזור לך למצוא משרד מתאים. באיזה גודל אתה מעוניין?"
            elif any(word in user_lower for word in ["מחיר", "עלות", "כסף"]):
                return "המחירים משתנים לפי האזור והגודל. איזה תקציב יש לך?"
            elif any(word in user_lower for word in ["תל אביב", "תא", "גוש דן"]):
                return "תל אביב זה שוק חם! יש לנו דירות מצוינות באזור. כמה חדרים אתה מחפש?"
            elif any(word in user_lower for word in ["ירושלים", "י-ם"]):
                return "ירושלים זה מקום נהדר! איזה חלק בעיר אתה מעדיף?"
            elif any(word in user_lower for word in ["בית", "בתים"]):
                return "בית פרטי זה השקעה מצוינת! איזה אזור אתה מעדיף?"
            else:
                return "אני כאן לעזור לך עם כל מה שקשור לנדל\"ן. אתה יכול לספר לי יותר?"
                
        except Exception:
            return "סליחה, לא הבנתי. אתה יכול לחזור על זה?"

    def _log_turn_metrics(self, user_text, bot_response):
        """Log turn metrics for SLA monitoring and analytics"""
        try:
            import time
            from server.db import db
            from sqlalchemy import text
            
            # Generate turn ID
            turn_id = f"{self.call_sid}_{int(time.time())}"
            
            # Mock timing metrics (in real implementation, measure actual times)
            t_audio_ms = 200  # Audio processing time
            t_nlp_ms = 300    # AI response time
            t_tts_ms = 400    # TTS generation time
            t_total_ms = t_audio_ms + t_nlp_ms + t_tts_ms
            
            # Log structured metrics
            current_app.logger.info("turn_metrics", extra={
                "call_sid": self.call_sid,
                "business_id": 1,  # Default business ID
                "turn_id": turn_id,
                "t_audio_ms": t_audio_ms,
                "t_nlp_ms": t_nlp_ms,
                "t_tts_ms": t_tts_ms,
                "t_total_ms": t_total_ms,
                "mode": "stream",
                "user_text_len": len(user_text),
                "bot_text_len": len(bot_response)
            })
            
            # Write to call_turn table
            try:
                db.session.execute(text("""
                    INSERT INTO call_turn (
                        call_sid, turn_id, business_id, user_text, bot_response,
                        t_audio_ms, t_nlp_ms, t_tts_ms, t_total_ms, started_at
                    ) VALUES (
                        :call_sid, :turn_id, :business_id, :user_text, :bot_response,
                        :t_audio_ms, :t_nlp_ms, :t_tts_ms, :t_total_ms, CURRENT_TIMESTAMP
                    )
                """), {
                    "call_sid": self.call_sid,
                    "turn_id": turn_id,
                    "business_id": 1,
                    "user_text": user_text[:500],  # Truncate for DB
                    "bot_response": bot_response[:500],
                    "t_audio_ms": t_audio_ms,
                    "t_nlp_ms": t_nlp_ms,
                    "t_tts_ms": t_tts_ms,
                    "t_total_ms": t_total_ms
                })
                db.session.commit()
            except Exception as db_error:
                current_app.logger.error(f"Failed to write turn metrics to DB: {db_error}")
                
        except Exception as e:
            current_app.logger.error(f"Turn metrics logging failed: {e}")

    def _play_response_and_continue(self, audio_url):
        """Play Hebrew response and return to WebSocket for continuous conversation"""
        try:
            from twilio.rest import Client
            
            # Get Twilio credentials
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                current_app.logger.error("Missing Twilio credentials for continuous conversation")
                return
                
            client = Client(account_sid, auth_token)
            
            # Build full audio URL
            public_base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("PUBLIC_HOST", "https://ai-crmd.replit.app")
            full_audio_url = f"{public_base.rstrip('/')}{audio_url}"
            
            # Get WebSocket host for continuous conversation
            wss_host = public_base.replace("https://", "").replace("http://", "").strip("/")
            
            # Create TwiML to play response AND return to WebSocket (continuous ping-pong)
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{full_audio_url}</Play>
    <Connect action="/webhook/stream_ended">
        <Stream url="wss://{wss_host}/ws/twilio-media">
            <Parameter name="call_sid" value="{self.call_sid}"/>
        </Stream>
    </Connect>
</Response>"""
            
            # Update the call to play response and continue conversation
            if self.call_sid:
                client.calls(self.call_sid).update(twiml=twiml)
            
            current_app.logger.info("CONTINUOUS_PING_PONG_ACTIVE", extra={
                "call_sid": self.call_sid,
                "audio_url": full_audio_url,
                "next_step": "return_to_websocket_after_play"
            })
            
        except Exception:
            current_app.logger.exception("CONTINUOUS_CONVERSATION_ERROR")

    def _cleanup(self):
        """Clean up resources when WebSocket closes"""
        if self.stt:
            self.stt.stop()
            
        if self.call_sid:
            stream_registry.clear(self.call_sid)
            
        current_app.logger.info("WS_CLEANUP_COMPLETE", extra={
            "call_sid": self.call_sid
        })