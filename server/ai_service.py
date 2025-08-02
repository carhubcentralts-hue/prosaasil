import json
import logging
import os
import tempfile
from uuid import uuid4
from openai import OpenAI
from gtts import gTTS
from datetime import datetime

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.api_available = True
        else:
            self.client = None
            self.api_available = False
            logger.warning("OpenAI API key not found - using fallback responses")
        
        # The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # Do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
    
    def generate_response(self, user_input, business, conversation_history, caller_info):
        """Generate AI response for Hebrew conversation with enhanced fallback"""
        try:
            logger.info(f"🧠 Generating AI response for: '{user_input}'")
            
            # CRITICAL: Check message limit first (6 messages max)
            if len(conversation_history) >= 6:
                logger.warning("Message limit reached - transferring to human agent")
                return {
                    'message': 'נראה שאתם זקוקים לעזרה מעמיקה יותר. אעביר אתכם לנציג האנושי שלנו שיוכל לסייע בצורה מותאמת.',
                    'continue_conversation': False,
                    'structured_data': None,
                    'transfer_to_agent': True
                }
            
            # Check for transfer to human based on unclear responses
            if self._should_transfer_to_human(conversation_history):
                logger.info("Transferring to human due to unclear conversation pattern")
                return {
                    'message': 'אני רוצה לוודא שתקבלו את השירות הטוב ביותר. אחבר אתכם לנציג האנושי שלנו.',
                    'continue_conversation': False,
                    'structured_data': None,
                    'transfer_to_agent': True
                }
            
            # Handle case where business is None
            if not business:
                logger.error("Business object is None")
                return {
                    'message': 'מצטער, יש בעיה זמנית במערכת. אנא נסה שוב מאוחר יותר.',
                    'continue_conversation': False,
                    'structured_data': None
                }
            
            # Safely get business attributes
            business_name = getattr(business, 'name', 'העסק')
            business_type = getattr(business, 'business_type', 'עסק')
            system_prompt_text = getattr(business, 'system_prompt', 'שירות מקצועי')
            
            # Check API availability and test connection
            if not self._test_api_connection():
                return self._fallback_response_hebrew(user_input, business)
            
            # Build conversation context
            context = self._build_conversation_context(conversation_history)
            
            # Create comprehensive system prompt for Hebrew conversation
            system_prompt = f"""
אתה עוזר AI מתקדם ברמה הגבוהה ביותר עבור {business_name} ({business_type}).
אתה מומחה בשירות לקוחות יוקרתי בעברית עם יכולות מתקדמות.

מידע על העסק:
{system_prompt_text}

🎯 המומחיות שלך:
1. הבנה מושלמת של כוונות לקוח בעברית (intent recognition)
2. ייעוץ מקצועי בתפריט עם המלצות אישיות
3. הזמנת תורים מדויקת עם אישור מיידי
4. טיפול בבקשות מיוחדות, אלרגיות וצרכים מיוחדים
5. מידע מדויק על מחירים, שעות ומיקום
6. עזרה בארגון אירועים וחגיגות פרטיות

⚡ כללי עבודה מחמירים:
- ענה תמיד בעברית מושלמת ומקצועית (ZERO אנגלית!)
- היה יעיל, מדויק ומועיל ב-50-80 מילים בלבד
- תמיד הציע פתרונות יצירתיים ושירות VIP
- לתורים: תאריך מלא + שעה + מספר סועדים + שם מלא
- אם לא יודע - העבר לצוות המקצועי שלנו
- זהה רגשות הלקוח והתאם את הטון בהתאם

השב רק בפורמט JSON בדיוק כך:
{{
    "message": "התגובה שלך בעברית ללקוח",
    "continue_conversation": true/false,
    "structured_data": {{}} או null
}}

עבור בקשות תור, structured_data:
{{
    "type": "appointment", 
    "customer_name": "שם",
    "customer_phone": "טלפון", 
    "requested_date": "תאריך",
    "requested_service": "שירות"
}}
"""
            
            # Build messages for GPT
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history for context
            for turn in conversation_history:
                role = "user" if turn.speaker == "user" else "assistant"
                messages.append({"role": role, "content": turn.message})
            
            # בדיקת הגבלת הודעות - מעקב אחר שיחות ארוכות
            message_count = len(conversation_history)
            if message_count >= 6:
                return {
                    "message": "אני מעביר אותך לנציג אנושי שיוכל לעזור לך טוב יותר. בהקדם מישהו יחזור אליך.",
                    "continue_conversation": False,
                    "transfer_to_human": True,
                    "reason": "conversation_too_long"
                }

            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            # Call OpenAI API with explicit timeout
            print(f"🤖 GPT-4o generating response for: {user_input[:50]}...")
            print(f"⏰ [GPT] Starting with 10s timeout...")
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=500,
                    temperature=0.7,
                    timeout=10  # 10 second timeout as requested
                )
                print(f"✅ [GPT] Response generated successfully")
            except Exception as gpt_error:
                print(f"❌ [GPT] API call failed: {gpt_error}")
                logger.error(f"GPT-4o timeout or error: {gpt_error}")
                return {
                    'message': 'מצטערים, יש לנו בעיה טכנית קטנה. אנא נסו שוב בעוד רגע.',
                    'source': 'gpt_timeout',
                    'status': 'error',
                    'error': str(gpt_error)
                }
            
            # Parse response
            content = response.choices[0].message.content
            if content:
                try:
                    ai_response = json.loads(content)
                except json.JSONDecodeError:
                    # Fallback if response is not JSON
                    ai_response = {
                        'message': content,
                        'continue_conversation': True,
                        'structured_data': None
                    }
            else:
                raise ValueError("Empty response from OpenAI")
            
            # Add required log per instructions
            message = ai_response.get('message', 'מצטער, לא הצלחתי להבין את הבקשה')
            print(f"🤖 GPT response: {ai_response}")
            logger.info(f"AI Response: {ai_response}")
            
            # CRITICAL FIX: Enhanced goodbye detection for proper conversation ending
            should_continue = ai_response.get('continue_conversation', True)
            
            # Additional goodbye detection based on user input - מורחב
            goodbye_indicators = [
                'תודה', 'ביי', 'להתראות', 'זהו', 'זה הכל', 'סיימתי', 
                'שלום', 'נעים', 'טוב', 'כבר לא צריך', 'אין לי יותר',
                'שיהיה בהצלחה', 'נעים היה', 'עד הפעם הבאה',
                'תודה רבה', 'בסדר ביי', 'נתראה', 'יאללה ביי',
                'עד כאן', 'אני נגמר', 'סלאמה', 'חבל על הזמן',
                'אני סוגר', 'מספיק', 'אני אגמור', 'נגמר לי'
            ]
            
            # Check user input for goodbye
            if any(word in user_input.lower() for word in goodbye_indicators):
                should_continue = False
                print(f"🛑 GOODBYE detected in user input: '{user_input}'")
            
            # Check AI response for goodbye
            if any(phrase in message.lower() for phrase in ['יום טוב', 'תודה רבה', 'נעים לפגוש', 'שיהיה בהצלחה']):
                should_continue = False
                print(f"🛑 GOODBYE detected in AI response: '{message}'")
            
            return {
                'message': message,
                'continue_conversation': should_continue,
                'structured_data': ai_response.get('structured_data')
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return self._fallback_response_hebrew(user_input, business)
    
    def _test_api_connection(self):
        """Test OpenAI API connection"""
        if not self.client or not self.api_available:
            return False
        
        try:
            # Quick test to verify API key works
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI API test failed: {e}")
            self.api_available = False
            return False
    
    def _fallback_response_hebrew(self, user_input, business):
        """Generate fallback response when OpenAI is not available"""
        user_lower = user_input.lower()
        
        # Get business details safely
        business_name = getattr(business, 'name', business.get('name', 'המסעדה') if isinstance(business, dict) else 'המסעדה')
        business_type = getattr(business, 'business_type', business.get('business_type', 'restaurant') if isinstance(business, dict) else 'restaurant')
        
        # Debug logging
        logger.info(f"Processing input: '{user_input}' for business: {business_name} ({business_type})")
        
        # INTELLIGENT Hebrew responses based on keywords and business context
        if any(word in user_lower for word in ['תור', 'פגישה', 'הזמנה', 'לקבוע', 'לזמן', 'שולחן']):
            if business_type == 'מסעדה' or business_type == 'restaurant':
                message = f"בהחלט! אשמח לעזור לכם לקבוע שולחן ב{business_name}. באיזה תאריך ושעה תרצו? כמה אנשים?"
            else:
                message = f"אשמח לעזור לכם לקבוע תור ב{business_name}. מה השם שלכם ומתי מתאים לכם?"
                
        elif any(word in user_lower for word in ['שעות', 'פתוח', 'זמינות', 'מתי', 'זמן']):
            if business_type == 'מסעדה' or business_type == 'restaurant':
                message = f"{business_name} פתוח כל יום בין השעות 12:00-23:00. האם תרצו לקבוע שולחן?"
            else:
                message = f"{business_name} פועל לפי שעות העבודה. איזה זמן מתאים לכם לקבוע?"
                
        elif any(word in user_lower for word in ['מחיר', 'עלות', 'כמה', 'מחירון']):
            if business_type == 'מסעדה' or business_type == 'restaurant':
                message = "המחירים שלנו תחרותיים מאוד! יש לנו תפריט מגוון עם מנות בשר, דגים וצמחוניות. מה הטעם שלכם?"
            else:
                message = "המחירים שלנו הוגנים וידידותיים. תוכלו לקבל פרטים מדויקים כשנתאם פגישה."
                
        elif any(word in user_lower for word in ['תפריט', 'מנות', 'אוכל', 'מה יש', 'צמחוני', 'בשר', 'מנה', 'דגים', 'פיצה', 'פיצות']):
            logger.info(f"Detected menu question - business_type: {business_type}")
            if business_type == 'מסעדה' or business_type == 'restaurant':
                message = f"התפריט של {business_name} מגוון ומעולה! יש לנו מנות בשר, דגים, פיצות ומבחר מנות צמחוניות. מה הטעם שלכם?"
            else:
                message = f"נשמח לספר לכם על כל השירותים ב{business_name}. תוכלו לפרט מה אתם מחפשים?"
                
        elif any(word in user_lower for word in ['שלום', 'היי', 'טוב', 'בוקר', 'ערב']):
            if business_type == 'restaurant':
                message = f"שלום וברוכים הבאים ל{business_name}! הגעתם למסעדה המובילה. איך אוכל לעזור לכם היום?"
            else:
                message = f"שלום וברוכים הבאים ל{business_name}! איך אוכל לעזור לכם?"
                
        elif any(word in user_lower for word in ['תודה', 'בסדר', 'להתראות', 'שלום']):
            message = f"תודה רבה שפניתם ל{business_name}! נשמח לראות אתכם אצלנו. יום נהדר!"
            
        else:
            # Smart generic response based on business type
            if business_type == 'restaurant':
                message = f"שלום! זה {business_name} - המסעדה שלכם לחוויה קולינרית מעולה. תוכלו לקבוע שולחן, לשאול על התפריט או כל דבר אחר!"
            else:
                message = f"שלום! אתם מדברים עם {business_name}. איך אוכל לעזור לכם? תוכלו לפרט את הבקשה שלכם."
        
        return {
            "message": message,
            "continue_conversation": True,
            "structured_data": None
        }
    
    def process_hebrew_conversation(self, user_text, business_id, call_sid):
        """Process Hebrew conversation - the function that was missing!"""
        try:
            from models import Business, ConversationTurn
            
            # Get business
            business = Business.query.get(business_id) if business_id else Business.query.first()
            if not business:
                return {"message": "מצטער, יש בעיה במערכת."}
            
            # Get conversation history
            conversation_history = ConversationTurn.query.filter_by(call_sid=call_sid).all()
            
            # Generate response using existing method
            response = self.generate_response(user_text, business, conversation_history, {})
            
            # Save conversation turn to database
            try:
                from app import db
                # Save user message
                user_turn = ConversationTurn(
                    call_sid=call_sid,
                    speaker='user',
                    message=user_text,
                    confidence_score=1.0
                )
                db.session.add(user_turn)
                
                # Save AI response
                ai_turn = ConversationTurn(
                    call_sid=call_sid,
                    speaker='ai',
                    message=response.get('message', ''),
                    confidence_score=1.0
                )
                db.session.add(ai_turn)
                db.session.commit()
                
                logger.info(f"✅ Saved conversation turn for call {call_sid}")
            except Exception as db_error:
                logger.error(f"❌ Failed to save conversation: {db_error}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in process_hebrew_conversation: {e}")
            return {"message": "מצטער, יש בעיה טכנית. איך אוכל לעזור?"}
    
    def generate_whatsapp_response(self, business_id, customer_message, conversation_history=None):
        """Generate WhatsApp AI response"""
        try:
            from models import Business
            business = Business.query.get(business_id) if business_id else Business.query.first()
            if not business:
                return {"response": "שלום! איך אפשר לעזור?"}
            
            response = self.generate_response(customer_message, business, conversation_history or [], {})
            return {
                "response": response.get("message", "שלום! איך אפשר לעזור?"),
                "continue": response.get("continue_conversation", True)
            }
        except Exception as e:
            logger.error(f"Error in generate_whatsapp_response: {e}")
            return {"response": "שלום! איך אפשר לעזור?"}
    
    def process_structured_data(self, call_log_id, structured_data):
        """Process structured data from AI response (appointments, etc.)"""
        try:
            if structured_data and structured_data.get('type') == 'appointment':
                # Create appointment request
                appointment = AppointmentRequest(
                    call_log_id=call_log_id,
                    customer_name=structured_data.get('customer_name'),
                    customer_phone=structured_data.get('customer_phone'),
                    requested_service=structured_data.get('requested_service'),
                    status='pending'
                )
                
                # Parse requested date if provided
                if structured_data.get('requested_date'):
                    try:
                        appointment.requested_date = datetime.fromisoformat(
                            structured_data['requested_date']
                        )
                    except ValueError:
                        logger.warning(f"Invalid date format: {structured_data['requested_date']}")
                
                db.session.add(appointment)
                logger.info(f"Created appointment request for call {call_log_id}")
                
        except Exception as e:
            logger.error(f"Error processing structured data: {str(e)}")
    
    def _build_conversation_context(self, conversation_history):
        """Build conversation context from history"""
        context = []
        for turn in conversation_history[-10:]:  # Last 10 turns
            speaker = "לקוח" if turn.speaker == "user" else "עוזר"
            context.append(f"{speaker}: {turn.message}")
        
        return "\n".join(context)
    
    def transcribe_hebrew_audio(self, audio_path):
        """Convert Hebrew audio to text using OpenAI Whisper"""
        if not self.api_available:
            logger.warning("OpenAI API not available for transcription")
            return ""
        
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="he"  # Hebrew language
                )
                hebrew_text = transcript.text
                logger.info(f"🎤 Transcribed Hebrew: {hebrew_text}")
                return hebrew_text
        except Exception as e:
            logger.error(f"❌ Error in transcription: {e}")
            return ""
    
    def synthesize_hebrew_speech(self, text):
        """יצירת תגובה עברית ישירה - NO AUDIO FILES"""
        try:
            logger.info(f"🔊 Returning direct Hebrew text instead of audio: {text}")
            return text  # Return text directly instead of audio file
                
        except Exception as e:
            logger.error(f"❌ Error in Hebrew TTS: {e}")
            return text
            
    def _is_request_clear(self, user_input):
        """בדיקה האם הבקשה ברורה ומובנת"""
        if not user_input or len(user_input.strip()) < 2:
            return False
            
        # בדיקת מילים מובנות בעברית
        clear_words = [
            'תור', 'הזמנה', 'שלום', 'מידע', 'שעות', 'פתוח', 'סגור',
            'מחיר', 'עלות', 'כמה', 'איך', 'מה', 'איפה', 'מתי',
            'רוצה', 'צריך', 'אפשר', 'יכול', 'בבקשה', 'תודה'
        ]
        
        # בדיקה אם יש לפחות מילה אחת מובנת
        return any(word in user_input.lower() for word in clear_words)
        
    def _should_transfer_to_human(self, user_input, conversation_history):
        """בדיקה האם צריך להעביר לצוות אמיתי"""
        transfer_triggers = [
            'רוצה לדבר עם אדם', 'אדם אמיתי', 'מנהל', 'תלונה',
            'לא מבין', 'לא עוזר', 'בעיה', 'כועס', 'זה לא עובד'
        ]
        
        # אם יש 3+ סיבובי שיחה ללא פתרון
        if len(conversation_history) >= 6:
            return True
            
        # אם יש ביטויי תסכול
        return any(trigger in user_input.lower() for trigger in transfer_triggers)
