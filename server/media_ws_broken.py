import json
import time
import threading
import os
from flask import current_app
from .stream_state import stream_registry
from .services.gcp_stt_stream import GcpHebrewStreamer
from .services.gcp_tts_live import generate_hebrew_response

class MediaStreamHandler:
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None
        self.stt = GcpHebrewStreamer(sample_rate_hz=8000)
        self.last_speech_time = time.time()
        self.conversation_buffer = ""
        self.processing_response = False

    def run(self):
        current_app.logger.info("WS_CONNECTED - Starting Hebrew real-time ASR")
        
        # Start real-time Hebrew transcription
        self.stt.start()
        
        # Start result processing thread
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
                    start = data.get("start", {})
                    cp = start.get("customParameters") or {}
                    # לפעמים Twilio שולחת customParameters כמחרוזת JSON
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
                        "hebrew_asr": "active"
                    })
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)

                elif ev == "media":
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    
                    # Real-time Hebrew transcription
                    media_payload = data.get("media", {}).get("payload", "")
                    if media_payload:
                        try:
                            # Send audio to Hebrew ASR
                            self.stt.push_ulaw_base64(media_payload)
                        except Exception:
                            current_app.logger.exception("REAL_TIME_ASR_ERROR")
                    
                    current_app.logger.debug("WS_FRAME", extra={
                        "call_sid": self.call_sid,
                        "payload_len": len(media_payload),
                        "hebrew_processing": True
                    })

                elif ev == "stop":
                    current_app.logger.info("WS_STOP")
                    break

        except Exception:
            current_app.logger.exception("WS_HANDLER_ERROR")
        finally:
            # Cleanup
            self.stt.stop()
            if self.call_sid:
                stream_registry.clear(self.call_sid)

    def _start_result_processor(self):
        """Start background thread to process Hebrew transcription results"""
        def process_results():
            while True:
                try:
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
                            
                            # If final utterance, generate response
                            if is_final and len(text.strip()) > 3:
                                self._generate_hebrew_response(text)
                    
                    time.sleep(0.1)  # Process results every 100ms
                    
                except Exception:
                    current_app.logger.exception("RESULT_PROCESSOR_ERROR")
                    time.sleep(1)
        
        thread = threading.Thread(target=process_results, daemon=True)
        thread.start()

    def _generate_hebrew_response(self, user_text):
        """Generate Hebrew AI response and play it in the call"""
        if self.processing_response:
            return  # Avoid overlapping responses
            
        self.processing_response = True
        
        def async_response():
            try:
                # Generate Hebrew AI response (simplified for now)
                response_text = self._get_ai_response(user_text)
                
                if response_text:
                    # Generate Hebrew TTS
                    audio_url = generate_hebrew_response(response_text, self.call_sid)
                    
                    if audio_url:
                        # Play response in call via Twilio API
                        self._play_response_in_call(audio_url)
                        
                        current_app.logger.info("HEBREW_RESPONSE_SENT", extra={
                            "call_sid": self.call_sid,
                            "user_said": user_text[:50],
                            "bot_said": response_text[:50]
                        })
                    
            except Exception:
                current_app.logger.exception("HEBREW_RESPONSE_ERROR")
            finally:
                self.processing_response = False
        
        # Run in background thread
        threading.Thread(target=async_response, daemon=True).start()

    def _get_ai_response(self, user_text):
        """Generate AI response for user input (Hebrew real estate context)"""
        try:
            # Simple response logic - can be enhanced with OpenAI GPT
            user_lower = user_text.lower()
            
            if any(word in user_lower for word in ["שלום", "היי", "הי"]):
                return "שלום! איך אני יכול לעזור לך היום?"
            elif any(word in user_lower for word in ["דירה", "דירות"]):
                return "מעולה! אני יכול לעזור לך למצוא דירה. איזה אזור אתה מחפש?"
            elif any(word in user_lower for word in ["משרד", "משרדים"]):
                return "אני אשמח לעזור לך למצוא משרד מתאים. באיזה גודל אתה מעוניין?"
            elif any(word in user_lower for word in ["מחיר", "עלות", "כסף"]):
                return "המחירים משתנים לפי האזור והגודל. איזה תקציב יש לך?"
            else:
                return "אני כאן לעזור לך עם כל מה שקשור לנדל\"ן. אתה יכול לספר לי יותר?"
                
        except Exception:
            return "סליחה, לא הבנתי. אתה יכול לחזור על זה?"

    def _play_response_in_call(self, audio_url):
        """Play Hebrew response in the active Twilio call"""
        try:
            from twilio.rest import Client
            
            # Get Twilio credentials
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                current_app.logger.error("Missing Twilio credentials for live response")
                return
                
            client = Client(account_sid, auth_token)
            
            # Get public base URL
            public_base = os.environ.get("PUBLIC_BASE_URL", "https://ai-crmd.replit.app")
            full_audio_url = f"{public_base.rstrip('/')}{audio_url}"
            
            # Update call with TwiML to play response
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{full_audio_url}</Play>
</Response>"""
            
            # Update the call
            client.calls(self.call_sid).update(twiml=twiml)
            
            current_app.logger.info("LIVE_HEBREW_RESPONSE_PLAYING", extra={
                "call_sid": self.call_sid,
                "audio_url": full_audio_url
            })
            
        except Exception:
            current_app.logger.exception("PLAY_RESPONSE_ERROR")

    def _play_response_in_call(self, audio_url):
        """Play Hebrew response in the active Twilio call"""
        try:
            from twilio.rest import Client
            
            # Get Twilio credentials
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                current_app.logger.error("Missing Twilio credentials for live response")
                return
                
            client = Client(account_sid, auth_token)
            
            # Get public base URL
            public_base = os.environ.get("PUBLIC_BASE_URL", "https://ai-crmd.replit.app")
            full_audio_url = f"{public_base.rstrip('/')}{audio_url}"
            
            # Update call with TwiML to play response
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{full_audio_url}</Play>
</Response>"""
            
            # Update the call
            client.calls(self.call_sid).update(twiml=twiml)
            
            current_app.logger.info("LIVE_HEBREW_RESPONSE_PLAYING", extra={
                "call_sid": self.call_sid,
                "audio_url": full_audio_url
            })
            
        except Exception:
            current_app.logger.exception("PLAY_RESPONSE_ERROR")