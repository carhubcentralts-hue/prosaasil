#!/usr/bin/env python3
"""
Clean AI System - מערכת AI נקייה וללא בעיות
"""

import os
import json
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class CleanHebrewAI:
    """מערכת AI נקייה לשיחות בעברית"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = None
        
        if not self.api_key:
            logger.warning("❌ OpenAI API Key not found in environment")
    
    def _initialize_openai_client(self):
        """אתחול לקוח OpenAI עם טיפול בשגיאות"""
        if self.openai_client is not None:
            return self.openai_client
            
        if not self.api_key:
            logger.error("OpenAI API key not available")
            return None
            
        try:
            # Import here to avoid initialization issues
            import openai
            
            self.openai_client = openai.OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI client initialized successfully")
            return self.openai_client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            return None
    
    def get_business_context(self, business_id: int = 1) -> Dict[str, Any]:
        """קבלת הקשר עסקי למערכת AI"""
        try:
            from app_clean import app
            from models_clean import CleanBusiness
            
            with app.app_context():
                business = CleanBusiness.query.filter_by(id=business_id).first()
                if business:
                    return {
                        'id': business.id,
                        'name': business.name,
                        'type': business.business_type,
                        'phone': business.phone,
                        'email': business.email,
                        'ai_prompt': self._get_ai_prompt()
                    }
        except Exception as e:
            logger.error(f"❌ Failed to get business from database: {e}")
        
        # Fallback context
        return {
            'id': 1,
            'name': 'שי דירות ומשרדים בע״מ',
            'type': 'real_estate',
            'phone': '+972-3-555-7777',
            'email': 'info@shai-realestate.co.il',
            'ai_prompt': self._get_ai_prompt()
        }
    
    def _get_ai_prompt(self) -> str:
        """הוראות AI מותאמות לסוכן נדל״ן בעברית"""
        return """אתה סוכן נדל"ן מקצועי וחברותי של שי דירות ומשרדים בע"מ.
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
6. היה חם ומקצועי"""
    
    def transcribe_audio(self, recording_url: str) -> str:
        """תמלול הקלטה עם OpenAI Whisper"""
        try:
            logger.info(f"🎙️ Starting transcription: {recording_url}")
            
            client = self._initialize_openai_client()
            if not client:
                logger.error("OpenAI client not available for transcription")
                return ""
            
            # Download audio file
            response = requests.get(recording_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to download recording: {response.status_code}")
                return ""
            
            # Save temporarily
            temp_file = f"/tmp/clean_recording_{datetime.now().timestamp()}.mp3"
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            # Transcribe with OpenAI Whisper
            with open(temp_file, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="he"  # Hebrew
                )
            
            # Clean up
            os.remove(temp_file)
            
            transcription = transcript.text.strip()
            logger.info(f"✅ Transcription completed: {transcription}")
            return transcription
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            return ""
    
    def generate_response(self, user_input: str, business_context: Dict[str, Any]) -> str:
        """יצירת תשובת AI מותאמת לעסק"""
        try:
            client = self._initialize_openai_client()
            if not client:
                return "סליחה, המערכת זמנית לא זמינה. אפשר לנסות שוב?"
            
            messages = [
                {"role": "system", "content": business_context['ai_prompt']},
                {"role": "user", "content": user_input}
            ]
            
            response = client.chat.completions.create(
                model="gpt-4o",  # Latest OpenAI model
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
                logger.info(f"✅ AI response generated: {ai_response[:50]}...")
                return ai_response
            else:
                return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
                
        except Exception as e:
            logger.error(f"❌ AI response generation failed: {e}")
            return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
    
    def should_end_conversation(self, user_input: str, ai_response: str) -> bool:
        """בדיקה אם צריך לסיים את השיחה"""
        end_words = ['ביי', 'תודה ולהתראות', 'להתראות', 'זה הכל', 'תודה רבה']
        user_wants_end = any(word in user_input.lower() for word in end_words)
        ai_says_goodbye = any(word in ai_response.lower() for word in ['להתראות', 'יום נעים', 'נשמח לעזור שוב'])
        return user_wants_end or ai_says_goodbye
    
    def save_conversation(self, call_sid: str, transcription: str, ai_response: str, recording_url: str):
        """שמירת השיחה למעקב העסק"""
        try:
            # Try database first
            from app_clean import app
            from models_clean import db, CleanCallLog, CleanConversationTurn
            
            with app.app_context():
                # Find or create call log
                call_log = CleanCallLog.query.filter_by(call_sid=call_sid).first()
                if not call_log:
                    call_log = CleanCallLog()
                    call_log.call_sid = call_sid
                    call_log.business_id = 1
                    call_log.from_number = 'unknown'
                    call_log.to_number = '+972-3-555-7777'
                    call_log.call_status = 'completed'
                    call_log.created_at = datetime.utcnow()
                    db.session.add(call_log)
                    db.session.commit()
                
                # Create conversation turn
                turn_count = CleanConversationTurn.query.filter_by(call_log_id=call_log.id).count() + 1
                
                turn = CleanConversationTurn()
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
        
        # Fallback to JSON file
        try:
            conversation_data = {
                "call_sid": call_sid,
                "timestamp": datetime.now().isoformat(),
                "transcription": transcription,
                "ai_response": ai_response,
                "recording_url": recording_url
            }
            
            # Load existing conversations
            conversations = []
            if os.path.exists('conversation_log.json'):
                with open('conversation_log.json', 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
            
            # Add new conversation
            conversations.append(conversation_data)
            
            # Save updated conversations
            with open('conversation_log.json', 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Conversation saved to JSON file")
            
        except Exception as json_error:
            logger.error(f"❌ JSON save failed: {json_error}")
    
    def process_complete_turn(self, call_sid: str, recording_url: str, turn_count: int) -> Dict[str, Any]:
        """עיבוד תור שיחה מלא: תמלול + AI + שמירה"""
        logger.info(f"🔄 Processing conversation turn {turn_count} for call {call_sid}")
        
        # Step 1: Transcribe
        transcription = self.transcribe_audio(recording_url)
        if not transcription:
            return {
                'continue_conversation': True,
                'ai_response': 'סליחה, לא שמעתי טוב. אפשר לחזור על מה שאמרת?',
                'transcription': '',
                'should_end': False
            }
        
        # Step 2: Generate AI response
        business_context = self.get_business_context(1)
        ai_response = self.generate_response(transcription, business_context)
        
        # Step 3: Check if conversation should end
        should_end = self.should_end_conversation(transcription, ai_response)
        
        # Step 4: Save conversation
        self.save_conversation(call_sid, transcription, ai_response, recording_url)
        
        return {
            'continue_conversation': not should_end,
            'ai_response': ai_response,
            'transcription': transcription,
            'should_end': should_end
        }

# Global instance
clean_ai = CleanHebrewAI()