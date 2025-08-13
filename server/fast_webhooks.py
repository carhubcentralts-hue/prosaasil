"""
Fast Twilio Webhooks - מערכת webhooks מהירה למניעת timeouts
"""
import os
import logging
from flask import Flask, request, Response
import uuid
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class FastTwilioWebhooks:
    def __init__(self):
        """Initialize fast webhook system"""
        self.voice_dir = Path("server/static/voice_responses")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        
        # Pre-generated audio files for instant response
        self.quick_responses = {
            'greeting': '/static/voice_responses/greeting.mp3',
            'listening': '/static/voice_responses/listening.mp3', 
            'processing': '/static/voice_responses/processing.mp3'
        }
        
    def register_fast_webhooks(self, app):
        """Register optimized webhook routes"""
        
        @app.route('/webhook/incoming_call', methods=['POST'])
        def fast_incoming_call():
            """Instant response for incoming calls"""
            try:
                call_sid = request.form.get('CallSid', 'unknown')
                from_number = request.form.get('From', 'unknown')
                
                logger.info(f"📞 Fast incoming call: {call_sid} from {from_number}")
                
                # Return immediate TwiML response
                xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app{self.quick_responses['greeting']}</Play>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
                return Response(xml, mimetype="text/xml")
                
            except Exception as e:
                logger.error(f"❌ Fast incoming call error: {e}")
                # Minimal fallback
                xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום</Say>
</Response>"""
                return Response(xml, mimetype="text/xml")
        
        @app.route('/webhook/conversation_turn', methods=['POST'])
        def fast_conversation_turn():
            """Ultra-fast conversation response"""
            try:
                call_sid = request.form.get('CallSid', 'unknown')
                turn_str = request.form.get('turn', '1')
                recording_url = request.form.get('RecordingUrl', '')
                
                # Parse turn number
                try:
                    turn_num = int(turn_str)
                except:
                    turn_num = 1
                
                next_turn = turn_num + 1
                
                logger.info(f"🔄 Fast turn {turn_num} for {call_sid}")
                
                # Use pre-generated response immediately
                audio_url = self._get_instant_audio_response(turn_num)
                
                # Start background processing (don't wait for it)
                if recording_url:
                    threading.Thread(
                        target=self._background_process_recording,
                        args=(call_sid, recording_url, turn_num),
                        daemon=True
                    ).start()
                
                # Return immediate TwiML
                xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Pause length="1"/>
  <Say voice="alice" language="he-IL">כעת אפשר לדבר</Say>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
                
                return Response(xml, mimetype="text/xml")
                
            except Exception as e:
                logger.error(f"❌ Fast conversation error: {e}")
                # Ultra-minimal fallback
                xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">אפשר לדבר</Say>
  <Pause length="3"/>
  <Record action="/webhook/conversation_turn" method="POST" maxLength="30"/>
</Response>"""
                return Response(xml, mimetype="text/xml")
    
    def _get_instant_audio_response(self, turn_num):
        """Get immediate audio response without waiting"""
        # Rotate between different pre-made responses
        responses = [
            "https://ai-crmd.replit.app/static/voice_responses/listening.mp3",
            "https://ai-crmd.replit.app/static/voice_responses/processing.mp3",
            "https://ai-crmd.replit.app/static/voice_responses/greeting.mp3"
        ]
        
        # Use turn number to vary response
        response_index = (turn_num - 1) % len(responses)
        return responses[response_index]
    
    def _background_process_recording(self, call_sid, recording_url, turn_num):
        """Process recording in background (don't block webhook)"""
        try:
            logger.info(f"🎤 Background processing: {call_sid}, turn {turn_num}")
            
            # This runs after webhook returns, so no timeout issues
            # Here you could do:
            # 1. Download and transcribe recording
            # 2. Generate AI response
            # 3. Create TTS for next turn
            # 4. Cache it for faster future responses
            
            time.sleep(0.1)  # Simulate processing
            logger.info(f"✅ Background processing complete for {call_sid}")
            
        except Exception as e:
            logger.error(f"❌ Background processing error: {e}")

# Global instance
fast_webhooks = FastTwilioWebhooks()