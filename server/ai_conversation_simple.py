"""
Hebrew AI Conversation Handler - Simplified Version
מטפל בשיחות AI בעברית עם תמלול ותשובות - גרסה מפושטת
"""

import os
import openai
from datetime import datetime
from whisper_handler import transcribe_hebrew
from conversation_manager import AdvancedConversationManager
import logging

logger = logging.getLogger(__name__)

class HebrewAIConversation:
    def __init__(self):
        # Use enhanced conversation manager
        self.conversation_manager = AdvancedConversationManager()
        # Keep compatibility for old methods that might still call these
        self.openai_client = self.conversation_manager.openai_client  
        self.tts_service = self.conversation_manager.tts_service
        
    def get_business_context(self, business_id: int = 1):
        """קבלת הקשר העסק לתשובות AI"""
        return {
            'name': 'שי דירות ומשרדים בע״מ',
            'type': 'real_estate',
            'ai_prompt': self.get_default_prompt('real_estate'),
            'greeting': None
        }
    
    def get_default_prompt(self, business_type: str) -> str:
        """פרומפט ברירת מחדל לפי סוג העסק"""
        prompts = {
            'real_estate': """אתה סוכן נדל"ן מקצועי וחברותי של שי דירות ומשרדים בע"מ.
אתה מומחה בשוק הנדל"ן הישראלי, מכיר מחירים עדכניים ואזורים טובים.
תפקידך לעזור ללקוחות למצוא נכסים מתאימים, להעריך נכסים, ולתת ייעוץ נדל"ן מקצועי.
התנהג בצורה חמה ומקצועית. שאל שאלות רלוונטיות כמו: סוג הנכס, אזור מועדף, תקציב, מועד.
אל תמציא מחירים או נכסים ספציפיים - הפנה לפגישה אישית לפרטים מדויקים.""",
        }
        return prompts.get(business_type, prompts['real_estate'])
    
    def generate_ai_response(self, user_input: str, business_context: dict) -> str:
        """יצירת תשובת AI מגוונת ללא לולאות"""
        try:
            # בדיקה לטקסט ריק או לא ברור
            if not user_input or len(user_input.strip()) < 3:
                responses = [
                    "סליחה, לא שמעתי אותך בבירור. אפשר לחזור?",
                    "מצטער, הקליטה לא ברורה. תוכל לדבר שוב?", 
                    "לא הבנתי מה אמרת. אפשר לחזור על השאלה?"
                ]
                import random
                return random.choice(responses)
            
            # בניית הקשר שיחה משופר
            messages = [
                {
                    "role": "system", 
                    "content": f"""{business_context['ai_prompt']}
                    
שם העסק: {business_context['name']}
סוג העסק: {business_context['type']}

חוקים חשובים:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 50 מילים)
3. שאל שאלה אחת ספציפית ומגוונת בכל תשובה
4. אם הלקוח רוצה לסיים ("ביי", "תודה ולהתראות", "זה הכל"), ענה בנימוס ותסיים
5. אל תמציא פרטים ספציפיים - הפנה לפגישה או לאיש קשר
6. היה חם ומקצועי ומגוון בתשובותיך
7. אל תחזור על אותה תשובה - תן תשובות מגוונות ורלוונטיות"""
                },
                {"role": "user", "content": f"הלקוח אמר: '{user_input}' - תן תשובה חדשה ומגוונת"}
            ]
            
            # קריאה ל-OpenAI
            from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
            
            # Convert to proper OpenAI message types
            typed_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    typed_messages.append(ChatCompletionSystemMessageParam(role="system", content=msg["content"]))
                elif msg["role"] == "user":
                    typed_messages.append(ChatCompletionUserMessageParam(role="user", content=msg["content"]))
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=typed_messages,
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
                return "סליחה, לא הבנתי. אפשר לחזור על השאלה?"
            
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
    
    def check_conversation_end(self, user_input: str, ai_response: str) -> bool:
        """בדיקה אם הלקוח רוצה לסיים את השיחה"""
        end_words = ['ביי', 'בי בי', 'להתראות', 'תודה ולהתראות', 'זה הכל', 'תודה רבה ולהתראות']
        user_wants_end = any(word in user_input.lower() for word in end_words)
        
        ai_says_goodbye = any(word in ai_response.lower() for word in ['להתראות', 'יום נעים', 'נשמח לעזור שוב'])
        
        return user_wants_end or ai_says_goodbye
    
    def process_conversation_turn(self, call_sid: str, recording_url: str, turn_number: int) -> dict:
        """עיבוד תור שיחה מלא עם מערכת מגוונת משופרת"""
        logger.info(f"🎙️ Processing enhanced turn {turn_number} for call {call_sid}")
        
        try:
            # 1. תמלול הקלטה
            user_input = ""
            if recording_url:
                try:
                    user_input = transcribe_hebrew(recording_url)
                    logger.info(f"🎤 Transcribed: {user_input}")
                except Exception as e:
                    logger.error(f"❌ Transcription failed: {e}")
                    user_input = ""  # Empty will trigger varied fallback
            
            # 2. השתמש במנהל השיחות המשופר
            result = self.conversation_manager.process_conversation_turn(
                call_sid, recording_url, turn_number
            )
            
            # 3. אם יש תמלול אמיתי, עדכן את התוצאה
            if user_input:
                # עדכן עם התמלול האמיתי
                ai_response = self.conversation_manager.generate_varied_response(user_input, call_sid)
                should_end = self.conversation_manager.check_conversation_end(user_input, ai_response)
                
                # יצירת TTS איכותי
                try:
                    audio_path = self.conversation_manager.tts_service.synthesize_professional_hebrew(ai_response)
                    response_audio_url = f"https://ai-crmd.replit.app{audio_path}" if audio_path else result.get('response_audio_url')
                except Exception as e:
                    logger.error(f"❌ Enhanced TTS failed: {e}")
                    response_audio_url = result.get('response_audio_url')
                
                result.update({
                    'user_input': user_input,
                    'ai_response': ai_response,
                    'response_audio_url': response_audio_url,
                    'should_end': should_end
                })
            
            return result
            
            return {
                'success': True,
                'user_input': user_input,
                'ai_response': ai_response,
                'response_audio_url': response_audio_url,
                'should_end': should_end,
                'turn_number': turn_number,
                'call_sid': call_sid
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing conversation turn: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_input': '',
                'ai_response': 'סליחה, הייתה תקלה. אפשר לנסות שוב?',
                'response_audio_url': 'https://ai-crmd.replit.app/static/voice_responses/listening.mp3',
                'should_end': False,
                'turn_number': turn_number,
                'call_sid': call_sid
            }