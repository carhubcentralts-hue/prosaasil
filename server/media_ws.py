"""
WebSocket Media Stream Handler - תיקון Error 31924
Implements Twilio Media Streams protocol exactly per specifications
"""
import json
import time
import threading
import os
import base64
import traceback
import audioop
from simple_websocket import ConnectionClosed
from flask import current_app
from .stream_state import stream_registry

# Real-time Hebrew processing components
try:
    from .services.gcp_stt_stream import GcpHebrewStreamer
    from .services.gcp_tts_live import generate_hebrew_response
    HEBREW_REALTIME_ENABLED = True
except ImportError:
    GcpHebrewStreamer = None
    generate_hebrew_response = None
    HEBREW_REALTIME_ENABLED = False

def run_media_stream(ws):
    """
    Main WebSocket handler - תיקון 31924 Protocol Error
    Two-phase approach: SINK mode first, then ECHO mode
    """
    stream_sid = None
    frames = 0
    mode = os.getenv("WS_MODE", "AI")  # SINK, ECHO, or AI - DEFAULT AI
    
    print(f"WS_CONNECTED mode={mode} hebrew_realtime={HEBREW_REALTIME_ENABLED}")
    
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
                
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                print("WS_BAD_JSON")
                continue
                
            event_type = evt.get("event")
            
            if event_type == "start":
                stream_sid = evt["start"]["streamSid"]
                print(f"WS_START sid={stream_sid}")
                
            elif event_type == "media":
                b64_payload = evt["media"]["payload"]  # µ-law 8kHz Base64
                frames += 1
                
                if mode == "SINK":
                    # SINK mode: receive only, don't send anything back
                    # This tests if the connection stays stable without protocol errors
                    pass
                    
                elif mode == "ECHO":
                    # ECHO mode: send back the exact same frame
                    if frames == 1 and stream_sid:
                        # Send clear on first frame to empty buffers
                        ws.send(json.dumps({
                            "event": "clear", 
                            "streamSid": stream_sid
                        }))
                    
                    # Echo the frame back - you should hear yourself
                    ws.send(json.dumps({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": b64_payload}
                    }))
                    
                    # Send mark every ~1 second (50 frames) for debugging
                    if frames % 50 == 0 and stream_sid:
                        ws.send(json.dumps({
                            "event": "mark",
                            "streamSid": stream_sid,
                            "mark": {"name": f"f{frames}"}
                        }))
                        
                elif mode == "AI" and HEBREW_REALTIME_ENABLED:
                    # AI mode: process with Hebrew STT/TTS
                    # TODO: Implement after ECHO works
                    pass
                    
            elif event_type == "mark":
                mark_name = evt.get("mark", {}).get("name", "")
                print(f"WS_MARK name={mark_name}")
                
            elif event_type == "stop":
                print(f"WS_STOP sid={stream_sid} frames={frames}")
                break
                
    except ConnectionClosed:
        print(f"WS_CLOSED sid={stream_sid} frames={frames}")
    except Exception as e:
        print(f"WS_ERR: {e}")
        traceback.print_exc()
    finally:
        try:
            ws.close()
        except:
            pass
            
    return ("", 204)

class MediaStreamHandler:
    """WebSocket handler with AI mode support"""
    
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None
        
        # Echo mode counters (לאבחון חיבור)
        self.rx = 0  # Received frames
        self.tx = 0  # Transmitted frames  
        self.sent_clear = False
        
        # AI mode components
        self.audio_buffer = bytearray()  # PCM16 8kHz mono buffer
        self.last_audio_time = time.time()
        self.speaking = False  # Prevent echo during TTS playback
        
        # Real-time Hebrew components
        if HEBREW_REALTIME_ENABLED and GcpHebrewStreamer:
            self.stt = GcpHebrewStreamer(sample_rate_hz=8000)
        else:
            self.stt = None
            
        self.last_speech_time = time.time()
        self.conversation_buffer = ""
        self.processing_response = False

    def run(self):
        """Main WebSocket handler with ECHO mode support"""
        mode = os.getenv("WS_MODE", "AI")  # Default to AI now
        frames = 0
        
        print(f"WS_CONNECTED mode={mode} hebrew_realtime={HEBREW_REALTIME_ENABLED}")
        
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    break
                    
                try:
                    evt = json.loads(raw)
                except json.JSONDecodeError:
                    print("WS_BAD_JSON")
                    continue
                    
                event_type = evt.get("event")
                
                if event_type == "start":
                    self.stream_sid = evt["start"]["streamSid"]
                    print(f"WS_START sid={self.stream_sid}")
                    
                elif event_type == "media":
                    b64_payload = evt["media"]["payload"]
                    frames += 1
                    self.rx += 1
                    
                    if mode == "ECHO":
                        # Send clear on first frame to empty buffers
                        if not self.sent_clear and self.stream_sid:
                            self.ws.send(json.dumps({
                                "event": "clear", 
                                "streamSid": self.stream_sid
                            }))
                            self.sent_clear = True
                        
                        # Echo the frame back - you should hear yourself
                        self.ws.send(json.dumps({
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": b64_payload}
                        }))
                        self.tx += 1
                        
                        # Send mark every ~1 second (50 frames) for debugging
                        if frames % 50 == 0 and self.stream_sid:
                            self.ws.send(json.dumps({
                                "event": "mark",
                                "streamSid": self.stream_sid,
                                "mark": {"name": f"f{frames}"}
                            }))
                            
                    elif mode == "SINK":
                        # SINK mode: receive only, don't send anything
                        pass
                        
                    elif mode == "AI":
                        # AI mode: Hebrew STT → AI → TTS pipeline
                        if not self.speaking:  # Only collect audio when not playing TTS
                            # Convert µ-law to PCM16 and add to buffer
                            mulaw_data = base64.b64decode(b64_payload)
                            pcm16_data = audioop.ulaw2lin(mulaw_data, 2)
                            self.audio_buffer.extend(pcm16_data)
                            self.last_audio_time = time.time()
                            
                            # Check for end of utterance
                            buffer_duration = len(self.audio_buffer) / (2 * 8000)  # PCM16 8kHz
                            silence_duration = time.time() - self.last_audio_time
                            
                            # Process if we have enough silence or buffer is too long
                            if ((silence_duration >= 0.8 and buffer_duration > 0.3) or 
                                buffer_duration >= 6.0) and not self.speaking:
                                self._process_hebrew_utterance(bytes(self.audio_buffer))
                                self.audio_buffer.clear()
                        
                elif event_type == "mark":
                    mark_name = evt.get("mark", {}).get("name", "")
                    print(f"WS_MARK name={mark_name}")
                    
                elif event_type == "stop":
                    print(f"WS_STOP sid={self.stream_sid} frames={frames}")
                    break
                    
        except Exception as e:
            print(f"WS_ERR: {e}")
            traceback.print_exc()
        finally:
            print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")
            try:
                self.ws.close()
            except:
                pass
    
    def _process_hebrew_utterance(self, pcm16_data):
        """Process Hebrew audio: STT → AI → TTS → Send frames"""
        if not pcm16_data or self.speaking:
            return
            
        self.speaking = True
        try:
            print(f"AI_PROCESSING: {len(pcm16_data)} bytes audio")
            
            # 1. Speech-to-Text (Hebrew)
            hebrew_text = self._speech_to_text(pcm16_data)
            if not hebrew_text or len(str(hebrew_text).strip()) < 3:
                print("AI_STT: No speech detected")
                return
                
            print(f"AI_STT: {hebrew_text}")
            
            # 2. Generate AI response
            ai_response = self._generate_ai_response(hebrew_text)
            if not ai_response:
                ai_response = "סליחה, לא הבנתי. אפשר לחזור?"
                
            print(f"AI_RESPONSE: {ai_response}")
            
            # 3. Text-to-Speech (Hebrew)
            tts_pcm16 = self._text_to_speech(ai_response)
            if tts_pcm16:
                # 4. Send as µ-law frames to Twilio
                self._send_pcm16_as_mulaw_frames(tts_pcm16)
                print(f"AI_TTS: Sent {len(tts_pcm16)} bytes audio")
            else:
                print("AI_TTS: Failed to generate speech")
                
        except Exception as e:
            print(f"AI_ERROR: {e}")
            traceback.print_exc()
        finally:
            self.speaking = False
    
    def _speech_to_text(self, pcm16_data):
        """Convert PCM16 8kHz audio to Hebrew text"""
        try:
            if HEBREW_REALTIME_ENABLED and self.stt:
                # Use Google Cloud STT - implement simple transcription
                try:
                    # Simplified STT for now - use Whisper fallback
                    return self._whisper_transcribe(pcm16_data)
                except Exception as e:
                    print(f"GCP_STT_ERROR: {e}")
                    return self._whisper_transcribe(pcm16_data)
            else:
                # Fallback to OpenAI Whisper
                return self._whisper_transcribe(pcm16_data)
                    
        except Exception as e:
            print(f"STT_ERROR: {e}")
            return None
    
    def _generate_ai_response(self, hebrew_text):
        """Generate AI response in Hebrew for real estate context"""
        try:
            import openai
            client = openai.OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-4",  # the newest OpenAI model is "gpt-5" which was released August 7, 2025. do not change this unless explicitly requested by the user
                messages=[
                    {
                        "role": "system",
                        "content": """אתה נציג שירות לקוחות של 'שי דירות ומשרדים בע״מ' - חברת נדל״ן מובילה.
                        
תפקידך:
- לענות בעברית בצורה מקצועית וידידותית
- לעזור עם שאלות על דירות, משרדים, מחירים ותהליכי השכירות/קנייה
- לקבוע פגישות עם יועצי המכירות
- לתת מידע על השירותים שלנו

השב תמיד בעברית, בקצרה (1-2 משפטים), ובצורה מועילה."""
                    },
                    {
                        "role": "user", 
                        "content": hebrew_text
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            return content.strip() if content else "סליחה, לא הבנתי"
            
        except Exception as e:
            print(f"AI_ERROR: {e}")
            return "סליחה, יש לי בעיה טכנית כרגע. אפשר לנסות שוב?"
    
    def _text_to_speech(self, hebrew_text):
        """Convert Hebrew text to PCM16 8kHz audio"""
        try:
            if HEBREW_REALTIME_ENABLED:
                # Use Google Cloud TTS
                from server.services.gcp_tts_live import HebrewTTSLive
                tts = HebrewTTSLive()
                mp3_path = tts.synthesize_hebrew(hebrew_text)
                
                if mp3_path:
                    # Convert MP3 to PCM16 8kHz
                    return self._convert_mp3_to_pcm16_8k(mp3_path)
            
            return None
            
        except Exception as e:
            print(f"TTS_ERROR: {e}")
            return None
    
    def _convert_mp3_to_pcm16_8k(self, mp3_path):
        """Convert MP3 file to PCM16 8kHz mono"""
        try:
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                # Use ffmpeg to convert MP3 to PCM16 8kHz mono WAV
                subprocess.run([
                    'ffmpeg', '-i', mp3_path, 
                    '-ar', '8000',  # 8kHz sample rate
                    '-ac', '1',     # Mono
                    '-f', 'wav',    # WAV format
                    '-y',           # Overwrite
                    temp_wav.name
                ], check=True, capture_output=True)
                
                # Read PCM data from WAV
                import wave
                with wave.open(temp_wav.name, 'rb') as wav_file:
                    pcm16_data = wav_file.readframes(-1)
                
                os.unlink(temp_wav.name)
                os.unlink(mp3_path)  # Clean up MP3
                return pcm16_data
                
        except Exception as e:
            print(f"MP3_CONVERT_ERROR: {e}")
            return None
    
    def _send_pcm16_as_mulaw_frames(self, pcm16_data):
        """Send PCM16 audio as µ-law frames to Twilio"""
        try:
            # Clear Twilio's audio buffer first
            if self.stream_sid:
                self.ws.send(json.dumps({
                    "event": "clear",
                    "streamSid": self.stream_sid
                }))
            
            # Convert PCM16 to µ-law
            mulaw_data = audioop.lin2ulaw(pcm16_data, 2)
            
            # Send in 20ms chunks (160 bytes for 8kHz µ-law)
            chunk_size = 160
            for i in range(0, len(mulaw_data), chunk_size):
                chunk = mulaw_data[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    # Pad last chunk if needed
                    chunk += b'\x7f' * (chunk_size - len(chunk))
                
                payload = base64.b64encode(chunk).decode('ascii')
                self.ws.send(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload}
                }))
                self.tx += 1
            
            # Send mark to indicate TTS completion
            if self.stream_sid:
                self.ws.send(json.dumps({
                    "event": "mark",
                    "streamSid": self.stream_sid,
                    "mark": {"name": "tts_complete"}
                }))
                
        except Exception as e:
            print(f"SEND_FRAMES_ERROR: {e}")
    
    def _whisper_transcribe(self, pcm16_data):
        """Transcribe using OpenAI Whisper"""
        try:
            import tempfile
            import openai
            import wave
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                # Convert PCM16 to WAV format
                with wave.open(f.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(8000)  # 8kHz
                    wav_file.writeframes(pcm16_data)
                
                # Transcribe with Whisper
                client = openai.OpenAI()
                with open(f.name, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he"
                    )
                
                os.unlink(f.name)
                return transcript.text
                
        except Exception as e:
            print(f"WHISPER_ERROR: {e}")
            return None