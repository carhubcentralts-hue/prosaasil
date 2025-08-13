"""
Hebrew AI Conversation Handler - Simplified Version
מטפל בשיחות AI בעברית עם תמלול ותשובות - גרסה מפושטת
"""

import os
import openai
from datetime import datetime
from whisper_handler import transcribe_hebrew
from hebrew_tts_fixed import HebrewTTSService
import logging

logger = logging.getLogger(__name__)

class HebrewAIConversation:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tts_service = HebrewTTSService()
        
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
        """יצירת תשובת AI מותאמת אישית"""
        try:
            # בניית הקשר שיחה
            messages = [
                {
                    "role": "system", 
                    "content": f"""{business_context['ai_prompt']}
                    
שם העסק: {business_context['name']}
סוג העסק: {business_context['type']}

חוקים חשובים:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 50 מילים)
3. שאל שאלה אחת רלוונטית בכל תשובה  
4. אם הלקוח רוצה לסיים ("ביי", "תודה ולהתראות", "זה הכל"), ענה בנימוס ותסיים
5. אל תמציא פרטים ספציפיים - הפנה לפגישה או לאיש קשר
6. היה חמ ומקצועי"""
                },
                {"role": "user", "content": user_input}
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
        """עיבוד תור שיחה מלא: תמלול → AI → TTS"""
        logger.info(f"🎙️ Processing turn {turn_number} for call {call_sid}")
        
        try:
            # 1. תמלול הקלטה
            user_input = ""
            if recording_url:
                try:
                    user_input = transcribe_hebrew(recording_url)
                    logger.info(f"🎤 Transcribed: {user_input}")
                except Exception as e:
                    logger.error(f"❌ Transcription failed: {e}")
                    user_input = "לא הצלחתי לשמוע אותך, אפשר לחזור?"
            
            # 2. בדיקה מוקדמת לסיום שיחה
            should_end = self.check_conversation_end(user_input, "")
            
            # 3. יצירת הקשר עסקי
            business_context = self.get_business_context()
            
            # 4. יצירת תשובת AI
            ai_response = ""
            if not should_end and user_input and len(user_input.strip()) > 1:
                ai_response = self.generate_ai_response(user_input, business_context)
                
                # בדיקה נוספת לסיום לאחר תשובת AI  
                should_end = self.check_conversation_end(user_input, ai_response)
            else:
                ai_response = "לא שמעתי אותך בבירור. אפשר לחזור על השאלה?"
            
            # 5. יצירת קובץ TTS
            response_audio_url = None
            if ai_response:
                try:
                    audio_filename = self.tts_service.synthesize_hebrew_audio(ai_response)
                    if audio_filename:
                        response_audio_url = f"https://ai-crmd.replit.app{audio_filename}"
                        logger.info(f"🔊 TTS created: {audio_filename}")
                except Exception as e:
                    logger.error(f"❌ TTS failed: {e}")
                    response_audio_url = "https://ai-crmd.replit.app/static/voice_responses/processing.mp3"
            
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