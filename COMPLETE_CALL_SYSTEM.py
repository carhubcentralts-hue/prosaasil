"""
🤖 מערכת שיחות עברית מלאה - לאה AI Agent
📞 כל הקוד הקריטי למערכת הטלפוניה של "שי דירות ומשרדים"

כולל:
- ✅ Twilio Media Streams WebSocket Handler
- ✅ Hebrew AI Agent (GPT-4o-mini) 
- ✅ Google Cloud STT/TTS עברית
- ✅ VAD מותאם לעברית
- ✅ Barge-in וInterruption handling
- ✅ Loop prevention וזיכרון שיחה
- ✅ Hebrew real estate conversations

גרסה: Production Ready - ספטמבר 2025
"""

import os
import json
import time
import base64
import audioop
import math
import threading
import queue
import random
import zlib
import asyncio
import hashlib
from typing import Optional, List, Dict, Any

# ================================
# 🎯 הגדרות קריטיות למערכת
# ================================

# Twilio Media Stream Settings
SAMPLE_RATE = 8000
FRAME_SIZE = 160  # 20ms at 8kHz

# Hebrew VAD Settings (Optimized for Hebrew speech)
MIN_UTT_SEC = 0.8        # זמן מינימלי לתמלול איכותי
MAX_UTT_SEC = 3.5        # מונע מונולוגים ארוכים  
VAD_RMS = 200           # פחות רגיש - מונע חיתוכים בעברית
BARGE_IN = True         # אפשר הפרעות טבעיות
VAD_HANGOVER_MS = 200   # יותר סבלנות
RESP_MIN_DELAY_MS = 50  # תגובה מהירה
RESP_MAX_DELAY_MS = 100 # ללא השהיות מיותרות
REPLY_REFRACTORY_MS = 400 # קירור קצר יותר
BARGE_IN_VOICE_FRAMES = 75  # 1.5 שניות לפני הפרעה (Hebrew needs more)
DEDUP_WINDOW_SEC = 8    # חלון דה-דופליקציה

# AI Settings
LLM_NATURAL_STYLE = True
MAX_CONVERSATION_HISTORY = 10  # זיכרון 10 תגובות אחרונות

# States
STATE_LISTEN = "LISTENING"
STATE_THINK = "THINKING" 
STATE_SPEAK = "SPEAKING"

# ================================
# 🤖 המנגנון הראשי של לאה
# ================================

class LeahAICallHandler:
    """
    🤖 לאה - הסוכנת נדל"ן הווירטואלית
    
    מטפלת בשיחות טלפון בעברית עם Twilio Media Streams
    """
    
    def __init__(self, websocket):
        self.ws = websocket
        self.mode = "AI"
        
        # WebSocket compatibility layer
        if hasattr(websocket, 'send'):
            self._ws_send_method = websocket.send
        else:
            self._ws_send_method = getattr(websocket, 'send_text', lambda x: print(f"❌ No send method: {x}"))
        
        # Safe WebSocket wrapper
        self.ws_connection_failed = False
        self.failed_send_count = 0
        
        def _safe_ws_send(data):
            if self.ws_connection_failed:
                return False
                
            try:
                self._ws_send_method(data)
                self.failed_send_count = 0
                return True
            except Exception as e:
                self.failed_send_count += 1
                if self.failed_send_count <= 3:
                    print(f"❌ WebSocket send error #{self.failed_send_count}: {e}")
                
                if self.failed_send_count >= 10:
                    self.ws_connection_failed = True
                    print(f"🚨 WebSocket connection marked as FAILED")
                
                return False
        
        self._ws_send = _safe_ws_send
        
        # Call identifiers
        self.stream_sid = None
        self.call_sid = None
        self.rx = 0
        self.tx = 0
        
        # Audio processing
        self.buf = bytearray()
        self.last_rx = None
        self.speaking = False
        self.processing = False
        self.conversation_id = 0
        self.last_processing_id = -1
        self.response_timeout = None
        
        # Conversation state
        self.introduced = False
        self.response_history = []
        self.last_tts_end_ts = 0.0
        self.voice_in_row = 0
        self.greeting_sent = False
        self.state = STATE_LISTEN
        
        # VAD (Voice Activity Detection) - Hebrew Optimized
        self.last_voice_ts = 0.0
        self.noise_floor = 35.0
        self.vad_threshold = 200.0  # Higher for Hebrew
        self.is_calibrated = False
        self.calibration_frames = 0
        self.mark_pending = False
        self.mark_sent_ts = 0.0
        
        # Timing protection
        self.processing_start_ts = 0.0
        self.speaking_start_ts = 0.0
        
        # WebSocket keepalive
        self.last_keepalive_ts = 0.0
        self.keepalive_interval = 18.0
        self.heartbeat_counter = 0
        
        # Audio transmission queue
        self.tx_q = queue.Queue(maxsize=4096)
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        
        # Conversation history (10 latest)
        self.conversation_history = []
        
        # Hash-based deduplication
        self.last_user_hash = None
        self.last_user_hash_ts = 0.0
        self.last_reply_hash = None
        
        print("🎯 לאה - Hebrew AI Call Handler initialized")

    def run(self):
        """
        🎯 הלופ הראשי של טיפול בשיחות
        """
        print(f"🎯 CONVERSATION READY (VAD threshold: {VAD_RMS})")
        
        try:
            while True:
                # Handle different WebSocket types
                raw = None
                try:
                    ws_type = str(type(self.ws))
                    
                    if 'RFC6455WebSocket' in ws_type:
                        raw = self.ws.wait()
                    else:
                        if hasattr(self.ws, 'receive'):
                            raw = self.ws.receive()
                        elif hasattr(self.ws, 'recv'):
                            raw = self.ws.recv()
                        else:
                            print("❌ Unknown WebSocket type")
                            break
                            
                except Exception as e:
                    if "Connection is already closed" in str(e):
                        print("🔌 WebSocket connection closed")
                        break
                    else:
                        print(f"❌ WebSocket error: {e}")
                        continue
                
                if not raw:
                    continue
                    
                # Parse JSON message
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    continue
                
                et = evt.get("event", "")
                current_time = time.time()
                
                # Handle different event types
                if et == "start":
                    self._handle_start_event(evt)
                    continue
                    
                elif et == "media":
                    self._handle_media_event(evt, current_time)
                    continue
                    
                elif et == "mark":
                    self._handle_mark_event(evt)
                    continue
                    
                elif et == "stop":
                    print("🛑 Stream stopped")
                    break
                
                # Watchdog timers
                self._check_watchdog_timers(current_time)
                
                # WebSocket keepalive
                self._send_keepalive_if_needed(current_time)
                    
        except Exception as e:
            print(f"❌ Main loop error: {e}")
        finally:
            self._cleanup()

    def _handle_start_event(self, evt):
        """טיפול באירוע תחילת זרם"""
        if "start" in evt:
            self.stream_sid = evt["start"]["streamSid"]
            self.call_sid = evt["start"].get("callSid")
        else:
            self.stream_sid = evt.get("streamSid")
            self.call_sid = evt.get("callSid")
            
        self.last_rx_ts = time.time()
        self.last_keepalive_ts = time.time()
        
        print(f"🎯 WS_START sid={self.stream_sid} call_sid={self.call_sid}")
        
        # Start transmission thread
        if not self.tx_running:
            self.tx_running = True
            self.tx_thread.start()
        
        # Send immediate greeting
        if not self.greeting_sent:
            print("🎯 SENDING IMMEDIATE GREETING!")
            greet = "שלום! אני לאה משי דירות ומשרדים. איך אני יכולה לעזור?"
            self._speak_simple(greet)
            self.greeting_sent = True

    def _handle_media_event(self, evt, current_time):
        """טיפול בנתוני אודיו נכנסים"""
        self.rx += 1
        b64 = evt["media"]["payload"]
        mulaw = base64.b64decode(b64)
        pcm16 = audioop.ulaw2lin(mulaw, 2)
        self.last_rx_ts = time.time()
        
        # VAD - Voice Activity Detection
        rms = audioop.rms(pcm16, 2)
        
        # Calibration phase (Hebrew optimized)
        if not self.is_calibrated and self.calibration_frames < 60:
            self.noise_floor = (self.noise_floor * self.calibration_frames + rms) / (self.calibration_frames + 1)
            self.calibration_frames += 1
            if self.calibration_frames >= 60:
                # Hebrew needs higher threshold
                self.vad_threshold = max(200, self.noise_floor * 6.0 + 120)
                self.is_calibrated = True
                print(f"🎛️ VAD CALIBRATED for HEBREW (threshold: {self.vad_threshold:.1f})")
        
        # Barge-in detection (Hebrew optimized)
        if self.speaking and BARGE_IN:
            grace_period = 2.0  # 2 seconds grace period
            time_since_tts_start = current_time - self.speaking_start_ts
            
            if time_since_tts_start < grace_period:
                # Inside grace period - NO barge-in allowed
                pass
            else:
                # Hebrew barge-in: Extra high threshold
                barge_in_threshold = max(500, self.noise_floor * 8.0 + 200) if self.is_calibrated else 600
                is_barge_in_voice = rms > barge_in_threshold
                
                if is_barge_in_voice:
                    self.voice_in_row += 1
                    # Hebrew speech: Require 1.5s continuous voice
                    if self.voice_in_row >= BARGE_IN_VOICE_FRAMES:  # 1.5 seconds
                        print(f"⚡ BARGE-IN DETECTED (after {time_since_tts_start*1000:.0f}ms)")
                        
                        # Stop TTS immediately
                        self.speaking = False
                        self._interrupt_speaking()
                        
                        print(f"⚡ BARGE-IN SUCCESS - Hebrew interrupt handled")
                else:
                    self.voice_in_row = 0
        
        # If speaking, clear input buffer
        if self.speaking:
            self.buf.clear()
            return
        
        # Regular VAD for speech detection
        is_voice = rms > self.vad_threshold if self.is_calibrated else rms > VAD_RMS
        
        if is_voice:
            self.last_voice_ts = current_time
            self.buf.extend(pcm16)
        else:
            # Check for end of utterance
            silence_duration = current_time - self.last_voice_ts
            if len(self.buf) > 0 and silence_duration > 0.5:  # 500ms silence
                self._process_utterance()

    def _handle_mark_event(self, evt):
        """טיפול בסימני TTS"""
        mark_name = evt.get("mark", {}).get("name", "")
        if mark_name == "assistant_tts_end":
            print("🎯 TTS_MARK_ACK: assistant_tts_end -> LISTENING")
            self.speaking = False
            self.state = STATE_LISTEN
            self.mark_pending = False

    def _check_watchdog_timers(self, current_time):
        """בדיקת טיימרים למניעת תקיעות"""
        # Speaking timeout - prevent cutoff mid-sentence
        if self.speaking and (current_time - self.speaking_start_ts) > 15.0:
            print("⚠️ SPEAKING TIMEOUT - forcing reset after 15s")
            self.speaking = False
            self.state = STATE_LISTEN
        
        # Processing timeout
        if self.processing and (current_time - self.processing_start_ts) > 10.0:
            print("⚠️ PROCESSING TIMEOUT - forcing reset after 10s")
            self.processing = False
            self.state = STATE_LISTEN

    def _send_keepalive_if_needed(self, current_time):
        """שליחת keepalive למניעת timeout"""
        if current_time - self.last_keepalive_ts > self.keepalive_interval:
            self.heartbeat_counter += 1
            keepalive_msg = json.dumps({
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": f"keepalive_{self.heartbeat_counter}_{int(current_time)}"}
            })
            
            if self._ws_send(keepalive_msg):
                self.last_keepalive_ts = current_time
                print(f"💓 Keepalive #{self.heartbeat_counter}")

    def _interrupt_speaking(self):
        """עצירה מיידית של דיבור הבוט"""
        if not self.speaking:
            return
            
        print("🚨 BARGE-IN: interrupt")
        self.speaking = False
        
        # Clear transmission queue
        try:
            while not self.tx_q.empty():
                self.tx_q.get_nowait()
        except:
            pass
        
        # Send clear command
        clear_msg = json.dumps({"event": "clear", "streamSid": self.stream_sid})
        self._ws_send(clear_msg)
        
        self.state = STATE_LISTEN

    def _process_utterance(self):
        """עיבוד הקלטה של המשתמש"""
        if not self.buf or self.processing or self.speaking:
            return
            
        self.processing = True
        self.processing_start_ts = time.time()
        self.state = STATE_THINK
        
        try:
            # Convert to audio
            pcm16_data = bytes(self.buf)
            self.buf.clear()
            
            # Skip very short utterances
            duration_sec = len(pcm16_data) / (2 * SAMPLE_RATE)
            if duration_sec < MIN_UTT_SEC:
                print(f"🚫 Utterance too short: {duration_sec:.2f}s")
                self.processing = False
                return
            
            print(f"🎙️ Processing {duration_sec:.2f}s Hebrew speech...")
            
            # Speech to Text (Hebrew)
            hebrew_text = self._hebrew_stt(pcm16_data)
            if not hebrew_text:
                self.processing = False
                return
            
            print(f"👤 USER: '{hebrew_text}'")
            
            # Generate AI response
            ai_response = self._generate_ai_response(hebrew_text)
            if ai_response:
                print(f"🤖 LEAH: '{ai_response}'")
                self._speak_hebrew(ai_response)
            
        except Exception as e:
            print(f"❌ Utterance processing error: {e}")
        finally:
            self.processing = False

    def _hebrew_stt(self, pcm16_data: bytes) -> Optional[str]:
        """Speech-to-Text עברית עם Google Cloud"""
        try:
            from google.cloud import speech
            
            # Get STT client (implement your credential loading)
            client = self._get_stt_client()
            if not client:
                return None
            
            # Configure for Hebrew
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=SAMPLE_RATE,
                language_code="he-IL",
                speech_contexts=[
                    # Real estate context for better recognition
                    speech.SpeechContext(phrases=[
                        "דירה", "דירות", "בית", "בתים", "נדלן", "שכירות", "מכירה",
                        "חדרים", "מחיר", "אזור", "שכונה", "מיקום", "קומה",
                        "תל אביב", "ירושלים", "חיפה", "באר שבע", "פתח תקווה",
                        "אני מעוניין", "אני מחפש", "כמה עולה", "איפה", "מתי"
                    ])
                ]
            )
            
            audio = speech.RecognitionAudio(content=pcm16_data)
            response = client.recognize(config=config, audio=audio)
            
            if response.results:
                transcript = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                print(f"🎙️ STT: '{transcript}' (confidence: {confidence:.2f})")
                return transcript
            
        except Exception as e:
            print(f"❌ Hebrew STT error: {e}")
            
        return None

    def _generate_ai_response(self, user_text: str) -> Optional[str]:
        """יצירת תגובת AI בעברית"""
        try:
            # Deduplication check
            user_hash = hashlib.md5(user_text.encode()).hexdigest()[:8]
            current_time = time.time()
            
            if (self.last_user_hash == user_hash and 
                current_time - self.last_user_hash_ts < DEDUP_WINDOW_SEC):
                print(f"🚫 DUPLICATE detected: '{user_text}' (hash: {user_hash})")
                return None
            
            self.last_user_hash = user_hash
            self.last_user_hash_ts = current_time
            
            # Loop prevention check
            if len(self.conversation_history) >= 2:
                last_responses = [item['bot'] for item in self.conversation_history[-4:]]
                response_counts = {}
                for resp in last_responses:
                    response_counts[resp] = response_counts.get(resp, 0) + 1
                    if response_counts[resp] >= 2:
                        print(f"🚫 LOOP detected in recent responses")
                        return "איך אני יכולה לעזור אותך היום?"
            
            # Check for conversation context
            if self.conversation_history:
                recent = self.conversation_history[-2:]
                recent_text = ' '.join([turn['user'] + ' ' + turn['bot'] for turn in recent])
            else:
                recent_text = ""
            
            # Determine if first call
            is_first_call = len(self.conversation_history) == 0
            
            # Create context-aware prompt
            if is_first_call:
                greeting_prompt = """את סוכנת נדלן של "שי דירות ומשרדים". 
שמך לאה. זו השיחה הראשונה.
התחילי בברכה חמה: "שלום! אני לאה מ'שי דירות ומשרדים'. אני כאן לעזור לך למצוא את הנכס המושלם!"
עזרי ללקוח למצוא דירה או נכס. בואי שאלות ממוקדות."""
            else:
                greeting_prompt = """את סוכנת נדלן מקצועית. אל תזכירי שוב את שמך או את שם החברה.
התרכזי בעזרה למציאת הנכס הנכון."""
            
            # Build the AI prompt
            smart_prompt = f"""{greeting_prompt}

הקשר האחרון: {recent_text[-200:] if recent_text else "אין"}

לקוח אומר: "{user_text}"

כללים חשובים:
1. תגובה קצרה - מקסימום 15 מילים
2. שאלה אחת בלבד  
3. אל תניחי - תשאלי הבהרות
4. דברי עברית טבעית
5. התמחי בנדלן ישראלי
6. אל תחזרי על תגובות קודמות

תגיבי בעברית:"""

            # Call OpenAI API
            ai_answer = self._call_openai_api(smart_prompt)
            
            if ai_answer:
                # Save to conversation history
                self.conversation_history.append({
                    'user': user_text.strip(),
                    'bot': ai_answer,
                    'time': time.time()
                })
                
                # Keep only last 10 conversations
                if len(self.conversation_history) > MAX_CONVERSATION_HISTORY:
                    self.conversation_history = self.conversation_history[-MAX_CONVERSATION_HISTORY:]
                    
                return ai_answer
            else:
                print("AI returned empty response")
                return "איך אני יכולה לעזור אותך?"
                
        except Exception as e:
            print(f"❌ AI response error: {e}")
            return "איך אני יכולה לעזור אותך?"

    def _call_openai_api(self, prompt: str) -> Optional[str]:
        """קריאה ל-OpenAI API"""
        try:
            import openai
            
            # Set API key (implement your key loading)
            openai.api_key = os.getenv('OPENAI_API_KEY')
            if not openai.api_key:
                print("❌ OpenAI API key not found")
                return None
            
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,  # Short responses
                temperature=0.7,
                top_p=0.9
            )
            
            if response.choices:
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            print(f"❌ OpenAI API error: {e}")
            
        return None

    def _speak_hebrew(self, text: str):
        """דיבור בעברית עם Google TTS"""
        if self.speaking:
            print("🚫 Already speaking - stopping current and starting new")
            self.speaking = False
            self.state = STATE_LISTEN
            time.sleep(0.05)
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        print(f"🔊 TTS_START: '{text}'")
        
        # Generate Hebrew TTS
        audio_data = self._hebrew_tts(text)
        if audio_data:
            self._stream_audio(audio_data)
        else:
            print("❌ TTS failed")
            self.speaking = False

    def _speak_simple(self, text: str):
        """דיבור פשוט ללא בדיקות מורכבות"""
        self.speaking = True
        self.state = STATE_SPEAK
        self.speaking_start_ts = time.time()
        
        try:
            # Add breathing pause (human-like)
            time.sleep(random.uniform(0.22, 0.36))
            
            # Generate TTS
            audio_data = self._hebrew_tts(text)
            if audio_data:
                self._stream_audio(audio_data)
                
        except Exception as e:
            print(f"❌ Simple speak error: {e}")
        finally:
            self._finalize_speaking()

    def _hebrew_tts(self, text: str) -> Optional[bytes]:
        """Hebrew Text-to-Speech using Google Cloud TTS"""
        try:
            from google.cloud import texttospeech
            
            # Get TTS client (implement your credential loading)
            client = self._get_tts_client()
            if not client:
                return None
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="he-IL",
                name="he-IL-Wavenet-A"  # Best Hebrew voice
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=SAMPLE_RATE,
                speaking_rate=1.1,   # Slightly faster
                pitch=0.0,           # Natural tone
                effects_profile_id=["telephony-class-application"]
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            print(f"✅ Hebrew TTS generated: {len(response.audio_content)} bytes")
            return response.audio_content
            
        except Exception as e:
            print(f"❌ Hebrew TTS error: {e}")
            return None

    def _stream_audio(self, audio_data: bytes):
        """זרמת אודיו ל-Twilio"""
        if not audio_data:
            return
            
        # Convert PCM16 to μ-law
        mulaw = audioop.lin2ulaw(audio_data, 2)
        
        # Stream in chunks
        total_frames = len(mulaw) // FRAME_SIZE
        frames_sent = 0
        
        for i in range(0, len(mulaw), FRAME_SIZE):
            # Check for barge-in
            if not self.speaking:
                print(f"🚨 BARGE-IN! Stopped at frame {frames_sent}/{total_frames}")
                self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
                return
                
            chunk = mulaw[i:i+FRAME_SIZE]
            if len(chunk) < FRAME_SIZE:
                chunk += b'\x00' * (FRAME_SIZE - len(chunk))
            
            payload = base64.b64encode(chunk).decode()
            
            msg = json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload}
            })
            
            if not self._ws_send(msg):
                break
                
            frames_sent += 1
            # Small delay to match real-time playback
            time.sleep(0.02)  # 20ms
        
        if self.speaking:
            print(f"✅ Complete audio sent: {frames_sent}/{total_frames} frames")
            
            # Send end marker
            end_mark = json.dumps({
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": "assistant_tts_end"}
            })
            self._ws_send(end_mark)
            self.mark_pending = True
            self.mark_sent_ts = time.time()

    def _finalize_speaking(self):
        """סיום דיבור עם חזרה להאזנה"""
        self.speaking = False
        self.last_tts_end_ts = time.time()
        self.state = STATE_LISTEN
        print("🎯 SPEAKING -> LISTENING")

    def _tx_loop(self):
        """לולאת שידור נפרדת"""
        while self.tx_running:
            try:
                # Simple transmission queue processing
                time.sleep(0.01)
            except Exception as e:
                print(f"❌ TX loop error: {e}")
                break

    def _cleanup(self):
        """ניקוי משאבים"""
        self.tx_running = False
        print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    # ================================
    # 🔧 Service Clients (Implement these)
    # ================================
    
    def _get_stt_client(self):
        """Get Google Cloud STT client - IMPLEMENT WITH YOUR CREDENTIALS"""
        try:
            from google.cloud import speech
            return speech.SpeechClient()
        except:
            print("❌ STT client failed - check Google Cloud credentials")
            return None
    
    def _get_tts_client(self):
        """Get Google Cloud TTS client - IMPLEMENT WITH YOUR CREDENTIALS"""
        try:
            from google.cloud import texttospeech
            return texttospeech.TextToSpeechClient()
        except:
            print("❌ TTS client failed - check Google Cloud credentials")
            return None


# ================================
# 📞 Twilio Integration Functions
# ================================

def create_twilio_media_stream_response(call_sid: str, server_url: str) -> str:
    """
    יצירת TwiML Response לחיבור Media Stream
    
    Args:
        call_sid: מזהה השיחה
        server_url: כתובת השרת (לדוגמה: https://yourdomain.com)
    
    Returns:
        TwiML XML string
    """
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="{server_url}/webhook/stream_ended">
    <Stream url="wss://{server_url.replace('https://', '').replace('http://', '')}/ws/twilio-media" 
            statusCallback="{server_url}/webhook/stream_status">
      <Parameter name="CallSid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>'''
    
    return twiml

def handle_incoming_call(from_number: str, to_number: str, call_sid: str, server_url: str) -> str:
    """
    טיפול בשיחה נכנסת
    
    Args:
        from_number: מספר המתקשר
        to_number: מספר הנקרא  
        call_sid: מזהה השיחה
        server_url: כתובת השרת
        
    Returns:
        TwiML response
    """
    print(f"📞 INCOMING CALL: {from_number} -> {to_number} (CallSid: {call_sid})")
    
    # בדיקות אבטחה בסיסיות
    if not from_number or not call_sid:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">שגיאה בשיחה</Say>
  <Hangup/>
</Response>'''
    
    # יצירת Media Stream response
    return create_twilio_media_stream_response(call_sid, server_url)


# ================================
# 🌐 WebSocket Server Integration
# ================================

def create_websocket_handler(websocket_library="flask-sock"):
    """
    יצירת handler ל-WebSocket במגוון ספריות
    
    Args:
        websocket_library: "flask-sock", "eventlet", "fastapi"
    
    Returns:
        Handler function
    """
    
    if websocket_library == "flask-sock":
        # Flask-Sock integration
        def flask_sock_handler(ws):
            handler = LeahAICallHandler(ws)
            handler.run()
        return flask_sock_handler
        
    elif websocket_library == "eventlet":
        # EventLet WebSocket integration  
        def eventlet_handler(ws):
            handler = LeahAICallHandler(ws)
            handler.run()
        return eventlet_handler
        
    elif websocket_library == "fastapi":
        # FastAPI WebSocket integration
        async def fastapi_handler(websocket):
            await websocket.accept()
            handler = LeahAICallHandler(websocket)
            handler.run()
        return fastapi_handler
        
    else:
        raise ValueError(f"Unsupported WebSocket library: {websocket_library}")


# ================================
# 🔧 Configuration & Environment
# ================================

class CallSystemConfig:
    """הגדרות המערכת"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')  
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.google_credentials_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        
        # Twilio phone numbers
        self.twilio_phone_from = os.getenv('TWILIO_PHONE_FROM', '+972504294724')
        self.twilio_phone_to = os.getenv('TWILIO_PHONE_TO', '+97233763805')
        
        # Server settings
        self.server_url = os.getenv('SERVER_URL', 'https://localhost:5000')
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
    def validate(self) -> bool:
        """בדיקת תקינות ההגדרות"""
        required = [
            ('OPENAI_API_KEY', self.openai_api_key),
            ('TWILIO_ACCOUNT_SID', self.twilio_account_sid),
            ('TWILIO_AUTH_TOKEN', self.twilio_auth_token),
            ('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON', self.google_credentials_json)
        ]
        
        missing = []
        for name, value in required:
            if not value:
                missing.append(name)
        
        if missing:
            print(f"❌ Missing required environment variables: {', '.join(missing)}")
            return False
        
        print("✅ All required environment variables are set")
        return True


# ================================
# 🚀 Usage Examples
# ================================

def example_flask_integration():
    """דוגמה לשילוב עם Flask"""
    
    from flask import Flask, request
    from flask_sock import Sock
    
    app = Flask(__name__)
    sock = Sock(app)
    config = CallSystemConfig()
    
    if not config.validate():
        print("❌ Configuration validation failed")
        return None
    
    # WebSocket endpoint for Twilio Media Streams
    @sock.route('/ws/twilio-media')
    def twilio_media_websocket(ws):
        """WebSocket endpoint for Twilio Media Streams"""
        print("🔌 New WebSocket connection for Twilio Media Stream")
        handler = LeahAICallHandler(ws)
        handler.run()
    
    # Webhook for incoming calls
    @app.route('/webhook/incoming_call', methods=['POST'])
    def incoming_call():
        """Webhook עבור שיחות נכנסות"""
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        call_sid = request.form.get('CallSid', '')
        
        twiml_response = handle_incoming_call(from_number, to_number, call_sid, config.server_url)
        
        return twiml_response, 200, {'Content-Type': 'application/xml'}
    
    # Health check
    @app.route('/healthz')
    def health_check():
        return {"status": "ok", "service": "Hebrew AI Call Center"}, 200
    
    return app


def example_direct_usage():
    """דוגמה לשימוש ישיר"""
    
    # Test configuration
    config = CallSystemConfig()
    if not config.validate():
        print("❌ Cannot run without proper configuration")
        return
    
    print("🤖 Hebrew AI Call System Ready!")
    print(f"📞 From: {config.twilio_phone_from}")
    print(f"📞 To: {config.twilio_phone_to}")
    print(f"🌐 Server: {config.server_url}")
    
    # Create TwiML for test call
    test_twiml = create_twilio_media_stream_response("TEST_CALL_123", config.server_url)
    print(f"📄 Sample TwiML:\n{test_twiml}")


# ================================
# 🎯 Main Entry Point  
# ================================

if __name__ == "__main__":
    print("""
🤖 מערכת שיחות עברית מלאה - לאה AI Agent
📞 Hebrew AI Call Center System

Features:
✅ Twilio Media Streams WebSocket Handler
✅ Hebrew AI Agent (GPT-4o-mini)
✅ Google Cloud STT/TTS עברית
✅ VAD מותאם לעברית
✅ Barge-in וInterruption handling
✅ Loop prevention וזיכרון שיחה
✅ Hebrew real estate conversations

""")
    
    # Run example
    print("🚀 Running configuration test...")
    example_direct_usage()
    
    print("\n📘 To integrate with your Flask app:")
    print("   app = example_flask_integration()")
    print("   app.run(host='0.0.0.0', port=5000)")
    
    print("\n📞 To handle calls, set Twilio webhook URL to:")
    print("   https://yourdomain.com/webhook/incoming_call")
    
    print("\n🎯 לאה מוכנה לשיחות! Ready for Hebrew conversations!")