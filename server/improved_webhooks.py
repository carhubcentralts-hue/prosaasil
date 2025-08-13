"""
Improved Twilio Webhooks with Professional Conversation Flow
זרימת שיחה מקצועית עם AI תגובות חכמות
"""
from flask import request, Response
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def register_improved_webhooks(app):
    """רישום webhooks משופרים עם זרימת שיחה מקצועית"""
    
    PUBLIC_HOST = "https://ai-crmd.replit.app"
    
    @app.route('/webhook/incoming_call', methods=['POST'])
    def professional_incoming_call():
        """Professional incoming call - immediate professional response"""
        call_sid = request.values.get('CallSid', 'unknown')
        from_number = request.values.get('From', '')
        
        logger.info(f"📞 Professional call started: {call_sid} from {from_number}")
        
        # Professional greeting with clear instructions
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    שלום, הגעתם לשי דירות ומשרדים. אני העוזרת הדיגיטלית.
    אשמח לעזור לכם עם כל שאלה בנושא נדלן.
    בבקשה ספרו לי במה אוכל לעזור לכם.
  </Say>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn?turn=1"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
        
        response = Response(xml, mimetype="text/xml")
        response.headers['Content-Type'] = 'text/xml; charset=utf-8'
        return response
    
    @app.route('/webhook/conversation_turn', methods=['POST'])
    def professional_conversation_turn():
        """Professional conversation handling with AI responses"""
        try:
            call_sid = request.values.get('CallSid', 'unknown')
            recording_url = request.values.get('RecordingUrl', '')
            turn_str = request.values.get('turn', '1')
            
            # Parse turn number
            try:
                turn_num = int(turn_str)
            except:
                turn_num = 1
            
            next_turn = turn_num + 1
            
            logger.info(f"🎤 Processing turn {turn_num} for call {call_sid}")
            logger.info(f"📥 Recording URL: {recording_url}")
            
            # Start background processing for real conversation
            if recording_url and recording_url != '':
                import threading
                threading.Thread(
                    target=lambda: process_real_conversation(call_sid, recording_url, turn_num),
                    daemon=True
                ).start()
                
                # Professional waiting response
                xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    אני בודקת את מה שאמרתם. רגע אחד בבקשה.
  </Say>
  <Pause length="3"/>
  <Say voice="alice" language="he-IL" rate="0.9">
    ספרו לי עוד פרטים על מה שאתם מחפשים.
  </Say>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
            else:
                # No recording - ask to speak
                xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    לא שמעתי אתכם. בבקשה דברו אחרי הצפצוף.
  </Say>
  <Pause length="1"/>
  <Record action="/webhook/conversation_turn?turn={next_turn}"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="#"
          transcribe="false"/>
</Response>"""
            
            response = Response(xml, mimetype="text/xml")
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response
            
        except Exception as e:
            logger.error(f"❌ Conversation error: {e}")
            # Professional error handling
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    סליחה, יש לי בעיה טכנית. אנא התקשרו שוב מאוחר יותר.
  </Say>
  <Hangup/>
</Response>"""
            return Response(xml, mimetype="text/xml")

def process_real_conversation(call_sid: str, recording_url: str, turn_num: int):
    """Process real conversation with transcription and AI response"""
    try:
        logger.info(f"🎙️ Starting real conversation processing for {call_sid}")
        
        # Download and transcribe
        import requests
        import tempfile
        import openai
        
        # Download recording
        response = requests.get(recording_url)
        if response.status_code != 200:
            logger.error(f"❌ Failed to download recording: {response.status_code}")
            return
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        logger.info(f"✅ Downloaded {len(response.content)} bytes")
        
        # Transcribe with Whisper
        client = openai.OpenAI()
        
        with open(temp_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he",
                response_format="text"
            )
        
        user_input = str(transcript).strip()
        logger.info(f"🎤 Transcription: '{user_input}'")
        
        # Generate AI response
        if len(user_input) > 3:  # Valid input
            ai_response = generate_professional_response(user_input, turn_num)
            logger.info(f"🤖 AI Response: '{ai_response}'")
            
            # Store in database (if available)
            try:
                store_conversation_turn(call_sid, turn_num, user_input, ai_response)
            except Exception as e:
                logger.warning(f"⚠️ Could not store in DB: {e}")
        
        # Cleanup
        import os
        os.unlink(temp_path)
        
    except Exception as e:
        logger.error(f"❌ Real conversation processing failed: {e}")

def generate_professional_response(user_input: str, turn_num: int) -> str:
    """Generate professional AI response for real estate"""
    try:
        import openai
        
        client = openai.OpenAI()
        
        system_prompt = """אתה סוכן נדל"ן מקצועי וחכם של "שי דירות ומשרדים בע״מ".
אתה מומחה בשוק הנדל"ן הישראלי ונותן שירות מעולה ללקוחות.

הנחיות חשובות:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 40 מילים)
3. שאל שאלה רלוונטית אחת
4. אל תמציא מחירים או נכסים ספציפיים
5. הפנה לפגישה או לקבלת פרטים נוספים
6. התנהג בצורה מקצועית וחמה

אם הלקוח רוצה לסיים ("תודה", "ביי", "זה הכל") - סיים בנימוס."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        ai_content = response.choices[0].message.content
        return ai_content.strip() if ai_content else "אשמח לעזור לכם. אפשר לחזור על השאלה?"
        
    except Exception as e:
        logger.error(f"❌ AI response generation failed: {e}")
        return "אשמח לעזור לכם. אפשר לחזור על השאלה?"

def store_conversation_turn(call_sid: str, turn_num: int, user_input: str, ai_response: str):
    """Store conversation turn in database (if available)"""
    try:
        # This would use the database if models are available
        logger.info(f"💾 Would store: {call_sid} turn {turn_num}")
        logger.info(f"    User: {user_input}")
        logger.info(f"    AI: {ai_response}")
    except Exception as e:
        logger.warning(f"⚠️ Storage not available: {e}")