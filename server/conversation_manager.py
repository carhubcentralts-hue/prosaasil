"""
Advanced Conversation Manager - מנהל שיחות מתקדם למניעת לולאות
"""
import os
import json
import uuid
import random
import logging
from typing import Dict, List, Optional
import openai
# from server.hebrew_tts_enhanced import EnhancedHebrewTTS

logger = logging.getLogger(__name__)

class AdvancedConversationManager:
    def __init__(self):
        """Initialize advanced conversation manager with loop prevention"""
        if os.getenv("OPENAI_API_KEY"):
            try:
                self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except:
                self.openai_client = None
        else:
            self.openai_client = None
        # self.tts_service = EnhancedHebrewTTS()  # Disabled for now
        self.conversation_history = {}  # Store conversation context
        
    def get_business_context(self) -> Dict:
        """Get enhanced business context"""
        return {
            'name': 'מערכת CRM',
            'type': 'real_estate',
            'specialties': ['דירות', 'משרדים', 'השקעות', 'השכרה', 'מכירה'],
            'areas': ['תל אביב', 'רמת גן', 'הרצליה', 'מרכז', 'דרום'],
            'services': ['ייעוץ נדלן', 'הערכת שווי', 'ליווי עסקאות', 'השקעות']
        }
    
    def generate_varied_response(self, user_input: str, call_sid: str) -> str:
        """Generate varied AI responses with loop prevention"""
        
        # Handle empty or unclear input with variety
        if not user_input or len(user_input.strip()) < 3:
            unclear_responses = [
                "סליחה, לא שמעתי אותך בבירור. תוכל לחזור?",
                "מצטער, הקליטה לא ברורה. אפשר לדבר שוב?",
                "לא הבנתי מה אמרת. תוכל לחזור על השאלה?",
                "הקול לא ברור. אפשר לנסות שוב?",
                "לא קלטתי. תדבר קצת יותר חזק?"
            ]
            return random.choice(unclear_responses)
        
        # Get conversation history for this call
        if call_sid not in self.conversation_history:
            self.conversation_history[call_sid] = {
                'turns': [],
                'topics_covered': [],
                'response_patterns': []
            }
        
        history = self.conversation_history[call_sid]
        business = self.get_business_context()
        
        try:
            # Create context-aware prompt
            system_prompt = self._create_dynamic_prompt(business, history, user_input)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"הלקוח אמר: '{user_input}'. תן תשובה מגוונת ומעניינת שלא חוזרת על תשובות קודמות."}
            ]
            
            # Add conversation history context
            if history['turns']:
                recent_turns = history['turns'][-2:]  # Last 2 turns
                context_msg = "הקשר השיחה: "
                for turn in recent_turns:
                    context_msg += f"לקוח: {turn.get('user', '')} | AI: {turn.get('ai', '')} | "
                messages.insert(1, {"role": "assistant", "content": context_msg})
            
            # Convert to proper OpenAI message types
            from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam, ChatCompletionAssistantMessageParam
            
            typed_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    typed_messages.append(ChatCompletionSystemMessageParam(role="system", content=msg["content"]))
                elif msg["role"] == "user":
                    typed_messages.append(ChatCompletionUserMessageParam(role="user", content=msg["content"]))
                elif msg["role"] == "assistant":
                    typed_messages.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg["content"]))
            
            # Call OpenAI with enhanced parameters for variety
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=typed_messages,
                max_tokens=120,
                temperature=0.9,  # Higher temperature for more variety
                frequency_penalty=0.7,  # Penalize repetition
                presence_penalty=0.6,   # Encourage new topics
                top_p=0.9
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
                
                # Store this interaction
                history['turns'].append({
                    'user': user_input,
                    'ai': ai_response
                })
                
                # Track response patterns to avoid repetition
                pattern = ai_response[:30]  # First 30 chars as pattern
                history['response_patterns'].append(pattern)
                
                # Keep only last 5 patterns
                if len(history['response_patterns']) > 5:
                    history['response_patterns'] = history['response_patterns'][-5:]
                
                logger.info(f"✅ Generated varied response: {ai_response[:50]}...")
                return ai_response
            else:
                return self._get_fallback_response()
                
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return self._get_fallback_response()
    
    def _create_dynamic_prompt(self, business: Dict, history: Dict, user_input: str) -> str:
        """Create dynamic prompt based on conversation history"""
        
        # Identify conversation stage
        turn_count = len(history['turns'])
        
        if turn_count == 0:
            stage = "פתיחה"
            focus = "קבלת פנים חמה ושאלה כללית על הצרכים"
        elif turn_count <= 2:
            stage = "זיהוי צרכים"
            focus = "הבנת סוג הנכס והאזור המבוקש"
        elif turn_count <= 4:
            stage = "פירוט דרישות"
            focus = "תקציב, מועדים, דרישות ספציפיות"
        else:
            stage = "סיכום וקביעת פגישה"
            focus = "הצעת פגישה אישית לפרטים נוספים"
        
        # Previous topics to avoid repetition
        covered_topics = ', '.join(history.get('topics_covered', []))
        previous_patterns = ', '.join(history.get('response_patterns', []))
        
        return f"""אתה {business['name']} - סוכן נדלן מקצועי ומנוסה.
התמחויות: {', '.join(business['specialties'])}
אזורי פעילות: {', '.join(business['areas'])}
שירותים: {', '.join(business['services'])}

שלב שיחה נוכחי: {stage}
מיקוד: {focus}

כללי תשובה:
1. תשובות קצרות (30-50 מילים) ומקצועיות
2. שאל שאלה אחת ספציפית ומעניינת
3. השתמש בשמות מקומות אמיתיים בישראל
4. היה חם ואנושי, לא רובוטי
5. אל תחזור על הנושאים: {covered_topics}
6. אל תחזור על הביטויים: {previous_patterns}
7. תן תשובות מגוונות ויצירתיות
8. התייחס ישירות למה שהלקוח אמר

אם הלקוח אומר "ביי" או "תודה ולהתראות" - סיים בנימוס.
אל תמציא מחירים או נכסים ספציפיים - הפנה לפגישה."""

    def _get_fallback_response(self) -> str:
        """Get varied fallback responses"""
        fallbacks = [
            "אשמח לעזור לך למצוא את הנכס המושלם. איזה אזור מעניין אותך?",
            "בואו נדבר על מה שאתה מחפש. דירה או משרד?",
            "יש לי ניסיון רב בשוק הנדלן. איך אני יכול לעזור?",
            "תגיד לי על הנכס שאתה מחפש ואני אמצא לך את הפתרון הטוב ביותר.",
            "אני כאן לעזור לך בכל נושא הנדלן. מה חשוב לך בנכס?"
        ]
        return random.choice(fallbacks)
    
    def check_conversation_end(self, user_input: str, ai_response: str) -> bool:
        """Check if conversation should end"""
        end_phrases = [
            'ביי', 'בי בי', 'להתראות', 'תודה ולהתראות', 
            'זה הכל', 'תודה רבה', 'נשמע טוב תודה', 'אני אחזור'
        ]
        
        user_wants_end = any(phrase in user_input.lower() for phrase in end_phrases)
        ai_says_goodbye = any(word in ai_response.lower() for word in ['להתראות', 'יום נעים', 'נשמח לשמוע'])
        
        return user_wants_end or ai_says_goodbye
    
    def process_conversation_turn(self, call_sid: str, recording_url: str, turn_number: int) -> Dict:
        """Process complete conversation turn with enhanced variety"""
        logger.info(f"🎙️ Processing enhanced turn {turn_number} for call {call_sid}")
        
        try:
            # 1. Transcription (simplified for now)
            user_input = ""
            if recording_url:
                # In real implementation, use Whisper here
                logger.info(f"🎤 Would transcribe: {recording_url}")
                user_input = "לא הצלחתי לשמוע, אפשר לחזור?"
            
            # 2. Generate varied AI response
            ai_response = self.generate_varied_response(user_input, call_sid)
            
            # 3. Check for conversation end
            should_end = self.check_conversation_end(user_input, ai_response)
            
            # 4. Create professional TTS audio
            response_audio_url = None
            if ai_response:
                try:
                    audio_path = self.tts_service.synthesize_professional_hebrew(ai_response)
                    if audio_path:
                        response_audio_url = f"https://ai-crmd.replit.app{audio_path}"
                        logger.info(f"🔊 Professional TTS created: {audio_path}")
                except Exception as e:
                    logger.error(f"❌ TTS failed: {e}")
                    response_audio_url = "https://ai-crmd.replit.app/static/voice_responses/processing.mp3"
            
            return {
                'success': True,
                'user_input': user_input,
                'ai_response': ai_response,
                'response_audio_url': response_audio_url,
                'should_end': should_end,
                'turn_number': turn_number
            }
            
        except Exception as e:
            logger.error(f"❌ Conversation processing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'response_audio_url': "https://ai-crmd.replit.app/static/voice_responses/processing.mp3"
            }