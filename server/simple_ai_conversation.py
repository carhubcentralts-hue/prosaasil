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
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def get_business_context(self, business_id: int = 1):
        """קבלת הקשר העסק לתשובות AI"""
        return {
            'name': 'שי דירות ומשרדים בע״מ',
            'type': 'real_estate',
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
    
    def simple_transcribe(self, recording_url: str) -> str:
        """תמלול פשוט עם OpenAI Whisper"""
        try:
            logger.info(f"🎙️ Transcribing recording: {recording_url}")
            
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
                transcript = self.openai_client.audio.transcriptions.create(
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
            messages = [
                {"role": "system", "content": business_context['ai_prompt']},
                {"role": "user", "content": user_input}
            ]
            
            response = self.openai_client.chat.completions.create(
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
        """שמירה פשוטה של השיחה בקובץ JSON"""
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