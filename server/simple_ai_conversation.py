"""
Simple Hebrew AI Conversation Handler - No GRPC Dependencies
מטפל בשיחות AI בעברית עם תמלול, תשובות, ושמירה במסד נתונים
ללא תלות ב-GRPC שגורמת לבעיות
"""

import os
import requests
import openai
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SimpleHebrewAI:
    def __init__(self):
        # Initialize without OpenAI client to avoid httpcore issues
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = None
        
    def get_business_context(self, business_id: int = 1):
        """קבלת הקשר העסק מהמסד נתונים"""
        try:
            from app_simple import app
            from models import Business
            
            with app.app_context():
                business = Business.query.filter_by(id=business_id).first()
                if business:
                    return {
                        'id': business.id,
                        'name': business.name,
                        'type': business.business_type,
                        'phone': business.phone,
                        'ai_prompt': """אתה סוכן נדל"ן מקצועי וחברותי של שי דירות ומשרדים בע"מ.
אתה מומחה בשוק הנדל"ן הישראלי, מכיר מחירים עדכניים ואזורים טובים.
תפקידך לעזור ללקוחות למצוא נכסים מתאימים, להעריך נכסים, ולתת ייעוץ נדל"ן מקצועי.
התנהג בצורה חמה ומקצועית. שאל שאלות רלוונטיות כמו: סוג הנכס, אזור מועדף, תקציב, מועד.
אל תמציא מחירים או נכסים ספציפיים - הפנה לפגישה אישית לפרטים מדויקים.

חוקים חשובים:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 50 מילים)
3. שאל שאלה אחת רלוונטית בכל תשובה  
4. אם הלקוח רוצה לסיים ("ביי", "תודה ולהתראות", "זה הכל"), ענה בנימוס ותסיים
5. אל תמציא פרטים ספציפיים - הפנה לפגישה או לאיש קשר
6. היה חם ומקצועי""",
                        'greeting': None
                    }
                    
        except Exception as e:
            logger.error(f"❌ Failed to get business from database: {e}")
            
        # Fallback if database fails
        return {
            'id': 1,
            'name': 'שי דירות ומשרדים בע״מ', 
            'type': 'real_estate',
            'phone': '+972-3-555-7777',
            'ai_prompt': """אתה סוכן נדל"ן מקצועי וחברותי של שי דירות ומשרדים בע"מ.
אתה מומחה בשוק הנדל"ן הישראלי, מכיר מחירים עדכניים ואזורים טובים.
תפקידך לעזור ללקוחות למצוא נכסים מתאימים, להעריך נכסים, ולתת ייעוץ נדל"ן מקצועי.
התנהג בצורה חמה ומקצועית. שאל שאלות רלוונטיות כמו: סוג הנכס, אזור מועדף, תקציב, מועד.
אל תמציא מחירים או נכסים ספציפיים - הפנה לפגישה אישית לפרטים מדויקים.

חוקים חשובים:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 50 מילים)
3. שאל שאלה אחת רלוונטית בכל תשובה  
4. אם הלקוח רוצה לסיים ("ביי", "תודה ולהתראות", "זה הכל"), ענה בנימוס ותסיים
5. אל תמציא פרטים ספציפיים - הפנה לפגישה או לאיש קשר
6. היה חם ומקצועי""",
            'greeting': None
        }
    
    def _get_openai_client(self):
        """Get OpenAI client with error handling"""
        if self.openai_client is None and self.api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                return None
        return self.openai_client
    
    def simple_transcribe(self, recording_url: str) -> str:
        """תמלול פשוט עם OpenAI Whisper"""
        try:
            logger.info(f"🎙️ Transcribing recording: {recording_url}")
            
            client = self._get_openai_client()
            if not client:
                logger.error("OpenAI client not available")
                return ""
            
            # Download audio file
            response = requests.get(recording_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to download recording: {response.status_code}")
                return ""
            
            # Save temporarily
            temp_file = f"/tmp/recording_{datetime.now().timestamp()}.mp3"
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            # Transcribe with OpenAI Whisper
            with open(temp_file, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="he"
                )
            
            # Clean up
            os.remove(temp_file)
            
            transcription = transcript.text.strip()
            logger.info(f"📝 Transcription result: {transcription}")
            return transcription
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            return ""
    
    def generate_ai_response(self, user_input: str, business_context: dict) -> str:
        """יצירת תשובת AI מותאמת אישית"""
        try:
            client = self._get_openai_client()
            if not client:
                return "סליחה, המערכת זמנית לא זמינה. אפשר לנסות שוב?"
            
            messages = [
                {"role": "system", "content": business_context['ai_prompt']},
                {"role": "user", "content": user_input}
            ]
            
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
                logger.info(f"✅ AI Response generated: {ai_response[:50]}...")
                return ai_response
            else:
                return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
                
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
    
    def check_conversation_end(self, user_input: str, ai_response: str) -> bool:
        """בדיקה אם הלקוח רוצה לסיים את השיחה"""
        end_words = ['ביי', 'בי בי', 'להתראות', 'תודה ולהתראות', 'זה הכל', 'תודה רבה ולהתראות']
        user_wants_end = any(word in user_input.lower() for word in end_words)
        ai_says_goodbye = any(word in ai_response.lower() for word in ['להתראות', 'יום נעים', 'נשמח לעזור שוב'])
        return user_wants_end or ai_says_goodbye
    
    def simple_save_conversation(self, call_sid: str, transcription: str, ai_response: str, recording_url: str):
        """שמירה של השיחה במסד נתונים"""
        try:
            # Try to save to database first
            from app_simple import app
            from models import db, CallLog, ConversationTurn
            from datetime import datetime
            
            with app.app_context():
                # Find or create call log
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if not call_log:
                    call_log = CallLog()
                    call_log.call_sid = call_sid
                    call_log.business_id = 1  # Default business
                    call_log.from_number = 'unknown'
                    call_log.to_number = '+972-3-555-7777'
                    call_log.call_status = 'completed'
                    call_log.created_at = datetime.utcnow()
                    db.session.add(call_log)
                    db.session.commit()
                
                # Create conversation turn
                turn_count = ConversationTurn.query.filter_by(call_log_id=call_log.id).count() + 1
                
                turn = ConversationTurn()
                turn.call_log_id = call_log.id
                turn.turn_number = turn_count
                turn.user_input = transcription
                turn.ai_response = ai_response
                turn.recording_url = recording_url
                turn.timestamp = datetime.utcnow()
                
                db.session.add(turn)
                db.session.commit()
                
                logger.info(f"✅ Conversation saved to database (Call: {call_sid}, Turn: {turn_count})")
                return
                
        except Exception as db_error:
            logger.error(f"❌ Database save failed: {db_error}")
            
        # Fallback to JSON file if database fails
        try:
            # Create simple log structure
            conversation_data = {
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat(),
                'transcription': transcription,
                'ai_response': ai_response,
                'recording_url': recording_url
            }
            
            # Save to file (temporary solution until DB works)
            log_file = 'conversation_log.json'
            conversations = []
            
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        conversations = json.load(f)
                except:
                    conversations = []
            
            conversations.append(conversation_data)
            
            # Keep only last 100 conversations
            if len(conversations) > 100:
                conversations = conversations[-100:]
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Conversation saved to {log_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save conversation: {e}")
    
    def process_conversation_turn(self, call_sid: str, recording_url: str, turn_number: int) -> dict:
        """עיבוד תור שיחה מלא: תמלול → AI → שמירה"""
        logger.info(f"🎙️ Processing turn {turn_number} for call {call_sid}")
        
        try:
            # 1. תמלול ההקלטה עם Whisper
            logger.info("🔄 Transcribing with Whisper...")
            transcription = self.simple_transcribe(recording_url)
            
            if not transcription or len(transcription.strip()) < 2:
                return {
                    'success': False,
                    'message': 'לא שמעתי טוב, אפשר לחזור על השאלה?',
                    'end_conversation': False
                }
            
            # 2. קבלת הקשר עסקי
            business_context = self.get_business_context(1)
            
            # 3. יצירת תשובת AI
            logger.info("🤖 Generating AI response...")
            ai_response = self.generate_ai_response(transcription, business_context)
            
            # 4. בדיקת סיום שיחה
            should_end = self.check_conversation_end(transcription, ai_response)
            
            # 5. שמירת השיחה
            self.simple_save_conversation(call_sid, transcription, ai_response, recording_url)
            
            logger.info("✅ Turn processed successfully")
            
            return {
                'success': True,
                'transcription': transcription,
                'ai_response': ai_response,
                'end_conversation': should_end,
                'turn_number': turn_number
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing conversation turn: {e}")
            return {
                'success': False,
                'message': 'סליחה, יש לי בעיה טכנית. אפשר לנסות שוב?',
                'end_conversation': False
            }

# Global instance
simple_ai = SimpleHebrewAI()