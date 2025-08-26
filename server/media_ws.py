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
    mode = os.getenv("WS_MODE", "SINK")  # SINK, ECHO, or AI
    
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
    """Legacy handler - maintained for compatibility"""
    
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None
        
        # Echo mode counters (לאבחון חיבור)
        self.rx = 0  # Received frames
        self.tx = 0  # Transmitted frames  
        self.sent_clear = False
        
        # Real-time Hebrew components
        if HEBREW_REALTIME_ENABLED and GcpHebrewStreamer:
            self.stt = GcpHebrewStreamer(sample_rate_hz=8000)
        else:
            self.stt = None
            
        self.last_speech_time = time.time()
        self.conversation_buffer = ""
        self.processing_response = False

    def run(self):
        """Delegate to the new run_media_stream function"""
        return run_media_stream(self.ws)