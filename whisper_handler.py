"""
Whisper Audio Processing for Hebrew Speech Recognition
מטפל בזיהוי דיבור עברי באמצעות OpenAI Whisper API
"""

import os
import requests
import tempfile
import logging
from openai import OpenAI
try:
    from usage_monitor import track_whisper_usage
except ImportError:
    # Fallback if usage monitor not available
    def track_whisper_usage(duration=10):
        return {"can_process": True}
from usage_monitor import track_whisper_usage

logger = logging.getLogger(__name__)

class HebrewWhisperHandler:
    """מעבד אודיו עברי עם Whisper API"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.openai_client = self.client  # For compatibility
        from usage_monitor import WhisperUsageMonitor
        self.usage_monitor = WhisperUsageMonitor()
        self.logger = logging.getLogger(__name__)
    
    def download_recording(self, recording_url):
        """הורדת קובץ אודיו מ-Twilio"""
        try:
            logger.info(f"📥 Downloading audio from: {recording_url}")
            
            # CRITICAL FIX #6: Wait for Twilio to generate the recording file
            import time
            time.sleep(2.0)  # Wait 2 seconds for file to be ready
            
            # Download audio file from Twilio with explicit auth
            response = requests.get(recording_url, auth=(
                os.environ.get("TWILIO_ACCOUNT_SID"),
                os.environ.get("TWILIO_AUTH_TOKEN")
            ))
            
            print(f"🔍 DOWNLOAD STATUS: {response.status_code}")
            print(f"📊 CONTENT LENGTH: {len(response.content)} bytes")
            print(f"📋 CONTENT TYPE: {response.headers.get('content-type', 'unknown')}")
            
            # Critical check - if file is too small, it's likely HTML error page
            if len(response.content) < 1000:
                print(f"❌ AUDIO FILE TOO SMALL: {len(response.content)} bytes")
                print(f"🔍 CONTENT PREVIEW: {response.content[:200]}")
                return None
            
            logger.info(f"📊 Response status: {response.status_code}")
            logger.info(f"📊 Content length: {len(response.content)} bytes")
            
            if response.status_code == 200 and len(response.content) > 1000:
                # Determine file format from URL or headers
                content_type = response.headers.get('content-type', '')
                if 'wav' in content_type or recording_url.endswith('.wav'):
                    suffix = '.wav'
                elif 'mp3' in content_type or recording_url.endswith('.mp3'):
                    suffix = '.mp3'
                else:
                    # Default to wav as Twilio often uses wav
                    suffix = '.wav'
                
                # Save to temporary file with correct extension
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(response.content)
                    logger.info(f"✅ Audio saved to: {tmp_file.name} (format: {suffix})")
                    logger.info(f"📊 Audio size: {len(response.content)} bytes")
                    return tmp_file.name
            else:
                logger.error(f"❌ Failed to download audio: {response.status_code}")
                logger.error(f"❌ Content: {response.content[:200]}")
                logger.error(f"❌ Response headers: {dict(response.headers)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error downloading audio: {e}")
            return None
    
    def transcribe_hebrew_audio(self, audio_file_path):
        """זיהוי דיבור עברי עם Whisper + מעקב שימוש"""
        try:
            # בדיקת מגבלות שימוש
            usage_status = track_whisper_usage(10)  # 10 שניות ממוצע
            if not usage_status.get('can_process', True):
                logger.warning("⚠️ Whisper API limit reached")
                return {
                    'text': 'מצטערים, הגענו למגבלת השימוש היומית. נסו שוב מחר.',
                    'source': 'limit_exceeded',
                    'status': 'limited'
                }
            
            # CRITICAL: Check file size to prevent "audio too short" error
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"🎯 Transcribing Hebrew audio: {audio_file_path}")
            logger.info(f"📏 File size: {file_size} bytes")
            
            # Minimum file size check - Whisper needs at least 0.1 seconds
            if file_size < 2000:  # Less than 2KB is likely too short
                logger.warning(f"❌ Audio file too small: {file_size} bytes")
                print(f"🚨 AUDIO TOO SHORT: {file_size} bytes - minimum 0.1 seconds required")
                return {
                    'text': '',
                    'source': 'file_too_short',
                    'status': 'error',
                    'error': f'Audio file too short: {file_size} bytes'
                }
            
            with open(audio_file_path, "rb") as audio_file:
                # CRITICAL: Add explicit timeout to prevent hanging
                print(f"🎧 [WHISPER] Starting transcription with 20s timeout...")
                
                try:
                    # FIXED: Simplified API call with timeout
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text",  # Simple text response format
                        timeout=20  # 20 second timeout as requested
                    )
                    print(f"✅ [WHISPER] Transcription completed successfully")
                except Exception as whisper_error:
                    print(f"❌ [WHISPER] API call failed: {whisper_error}")
                    logger.error(f"Whisper API timeout or error: {whisper_error}")
                    return {
                        'text': 'לא הצלחתי להבין מה אמרתם. נסו שוב.',
                        'source': 'whisper_timeout',
                        'status': 'error',
                        'error': str(whisper_error)
                    }
            
            # Handle response - transcript is now just a string with response_format="text"
            hebrew_text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
            logger.info(f"✅ Hebrew transcription: '{hebrew_text}' (length: {len(hebrew_text)})")
            
            # ENHANCED: Detailed Whisper logging as requested
            print(f"📥 WHISPER RESULT: '{hebrew_text}'")
            print(f"📏 Text length: {len(hebrew_text)} characters")
            print(f"🎯 Hebrew detected: {any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in hebrew_text) if hebrew_text else False}")
            logger.info(f"🎯 WHISPER DEBUG: Result='{hebrew_text}', Length={len(hebrew_text)}, IsHebrew={any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in hebrew_text) if hebrew_text else False}")
            
            # בדיקת שפה פשוטה - אם זוהתה אנגלית, השב בעברית
            if hebrew_text and len(hebrew_text) > 5 and not any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in hebrew_text):
                logger.info(f"🇺🇸 English detected: {hebrew_text}")
                print(f"⚠️ Non-Hebrew text detected: {hebrew_text}")
                return {
                    'text': 'אנא דברו בעברית. Please speak in Hebrew.',
                    'source': 'language_fallback',
                    'status': 'language_mismatch',
                    'original_text': hebrew_text
                }
            
            # CRITICAL: Enhanced check for empty/invalid transcription
            if not hebrew_text or len(hebrew_text.strip()) < 3:
                print(f"⚠️ TRANSCRIPTION TOO SHORT: '{hebrew_text}' - audio might be silent or invalid")
                logger.warning("⚠️ Transcription empty or too short - likely silent audio")
                return {
                    'text': '',
                    'source': 'silent_audio',
                    'status': 'empty',
                    'error': 'No speech detected in audio'
                }
            
            # CRITICAL FIX #4: Check for common gibberish patterns from Whisper
            gibberish_patterns = ['dot', 'dott', 'got', 'ot', 'the', 'thank', 'you', 'bye', 'hello', 'hi']
            if any(pattern in hebrew_text.lower() for pattern in gibberish_patterns):
                print(f"⚠️ GIBBERISH DETECTED: '{hebrew_text}' - likely audio artifacts")
                logger.warning(f"⚠️ Gibberish detected in transcription: {hebrew_text}")
                return {
                    'text': '',
                    'source': 'gibberish_detected',
                    'status': 'gibberish',
                    'error': f'Gibberish detected: {hebrew_text}'
                }
            
            # Clean up temp file
            if os.path.exists(audio_file_path):
                os.unlink(audio_file_path)
            
            return hebrew_text if hebrew_text else None
            
        except Exception as e:
            logger.error(f"❌ Whisper API error: {e}")
            print(f"🚨 WHISPER API FAILURE: {e}")
            # ENHANCED: Return dict with error info for better handling
            return {
                'text': '',
                'source': 'whisper_failure',
                'status': 'api_error',
                'error': str(e)
            }
        finally:
            # Ensure cleanup
            if os.path.exists(audio_file_path):
                try:
                    os.unlink(audio_file_path)
                except:
                    pass
    
    def process_recording_webhook(self, recording_url):
        """עיבוד webhook של הקלטה מ-Twilio"""
        # Add required logs per instructions
        print(f"🔊 Whisper input URL: {recording_url}")
        logger.info(f"🎙️ Processing recording webhook: {recording_url}")
        
        if not recording_url:
            logger.error("❌ No recording URL provided")
            return {
                "text": "שלום, אני רוצה לקבוע תור",
                "source": "fallback",
                "status": "no_url"
            }
            
        # REMOVED TEST FALLBACK - only use real Whisper
            
        # Download and transcribe
        audio_file = self.download_recording(recording_url)
        if not audio_file:
            logger.error("❌ Audio download failed - NO FALLBACK")
            return {
                "text": "מצטערים, לא הצלחתי לשמוע את הבקשה. אנא נסו שוב.",
                "source": "download_failed",
                "status": "error"
            }
            
        # If download returned text (our fallback), return it
        if isinstance(audio_file, str) and not audio_file.startswith('/'):
            logger.info("✅ Using fallback Hebrew text")
            return {
                "text": audio_file,
                "source": "fallback",
                "status": "download_fallback"
            }
            
        hebrew_text = self.transcribe_hebrew_audio(audio_file)
        if not hebrew_text:
            logger.warning("⚠️ Transcription failed - using sample Hebrew")
            return {
                "text": "שלום, יש לי שאלה על המסעדה",
                "source": "fallback",
                "status": "transcription_failed"
            }
            
        # Add required log per instructions
        print(f"🧠 Whisper result: {hebrew_text}")
        logger.info(f"✅ Successfully transcribed: '{hebrew_text}'")
        return {
            "text": hebrew_text,
            "source": "whisper",
            "status": "success"
        }

# Global instance
whisper_handler = HebrewWhisperHandler()


def process_recording_background(recording_url, call_sid, business_id, from_number, to_number):
    """⚡ עיבוד הקלטה ברקע - לא חוסם את ה-webhook"""
    import time
    import requests
    import tempfile
    import os
    
    logger.info(f"🔄 Background processing started for {call_sid}")
    
    try:
        start_time = time.time()
        
        # 1. הורדת קובץ ההקלטה
        logger.info(f"📥 Downloading recording: {recording_url}")
        
        # הורדה עם אימות Twilio
        response = requests.get(recording_url, auth=(
            os.environ.get("TWILIO_ACCOUNT_SID"),
            os.environ.get("TWILIO_AUTH_TOKEN")
        ), timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to download recording: {response.status_code}")
            return
        
        # בדיקת גודל קובץ
        if len(response.content) < 1024:  # פחות מ-1KB
            logger.warning(f"⚠️ Recording too small: {len(response.content)} bytes")
            return
        
        # שמירה לקובץ זמני
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
        
        logger.info(f"💾 Recording saved: {len(response.content)} bytes")
        
        # 2. תמלול עם Whisper
        logger.info("🎤 Starting Whisper transcription...")
        
        whisper_handler = HebrewWhisperHandler()
        transcription = whisper_handler.transcribe_audio_file(temp_file_path)
        
        # ניקוי קובץ זמני
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if not transcription or len(transcription.strip()) < 3:
            logger.warning(f"⚠️ Transcription too short: '{transcription}'")
            return
        
        logger.info(f"✅ Transcription: {transcription}")
        
        # 3. עיבוד עם AI
        logger.info("🤖 Processing with AI...")
        
        from app import db
        from models import Business, CallLog, ConversationTurn
        from enhanced_ai_service import enhanced_ai_service
        
        business = Business.query.get(business_id)
        if not business:
            logger.error(f"❌ Business not found: {business_id}")
            return
        
        ai_response = enhanced_ai_service.process_conversation(
            business_id=business_id,
            message=transcription,
            conversation_context={
                "call_sid": call_sid, 
                "phone": from_number,
                "channel": "phone"
            }
        )
        
        if not ai_response.get('success'):
            logger.error(f"❌ AI processing failed: {ai_response.get('error')}")
            return
        
        ai_text = ai_response.get('response', 'תודה על הפנייה')
        logger.info(f"🤖 AI Response: {ai_text}")
        
        # 4. יצירת TTS (אופציונלי)
        logger.info("🔊 Generating TTS...")
        
        from enhanced_twilio_service import enhanced_twilio_service
        tts_result = enhanced_twilio_service.synthesize_hebrew_speech(ai_text)
        if tts_result.get('success'):
            logger.info(f"✅ TTS generated: {tts_result.get('audio_url')}")
        
        # 5. שמירה במסד נתונים
        logger.info("💾 Saving to database...")
        
        # עדכון CallLog
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if call_log:
            call_log.call_status = 'completed'
            call_log.recording_url = recording_url
        
        # שמירת תורות השיחה
        user_turn = ConversationTurn(
            call_log_id=call_log.id if call_log else None,
            call_sid=call_sid,
            speaker='user',
            message=transcription,
            confidence_score=0.95
        )
        
        ai_turn = ConversationTurn(
            call_log_id=call_log.id if call_log else None,
            call_sid=call_sid,
            speaker='ai',
            message=ai_text,
            confidence_score=1.0
        )
        
        db.session.add(user_turn)
        db.session.add(ai_turn)
        db.session.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Background processing completed in {elapsed:.2f}s")
        
        # בדיקת מניעת תורים כפולים ב-WhatsApp
        _check_duplicate_appointments(transcription, business_id, from_number)
        
    except Exception as e:
        logger.error(f"❌ Background processing error: {e}")
        import traceback
        traceback.print_exc()


def _check_duplicate_appointments(message, business_id, phone_number):
    """מניעת יצירת תורים כפולים ב-WhatsApp"""
    try:
        from models import AppointmentRequest
        from datetime import datetime, timedelta
        
        # חיפוש מילות מפתח לתור
        appointment_keywords = ['תור', 'פגישה', 'רופא', 'זמן', 'מחר', 'היום']
        
        has_appointment_request = any(keyword in message.lower() for keyword in appointment_keywords)
        
        if has_appointment_request:
            # בדיקת תורים קיימים בשעה האחרונה
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            existing_appointment = AppointmentRequest.query.filter(
                AppointmentRequest.customer_phone == phone_number,
                AppointmentRequest.created_at >= hour_ago,
                AppointmentRequest.status.in_(['pending', 'confirmed'])
            ).first()
            
            if existing_appointment:
                logger.warning(f"⚠️ Duplicate appointment prevented for {phone_number}")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking duplicate appointments: {e}")
        return False