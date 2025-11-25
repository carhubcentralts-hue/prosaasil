"""
Echo Mode for WebSocket Testing - One True Path
Implements echo functionality to verify bidirectional WebSocket communication
"""
import json
import base64
import os

class EchoModeHandler:
    """Echo handler for testing Twilio Media Streams connectivity"""
    
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.echo_enabled = os.getenv("ECHO_TEST", "0") == "1"
        
    def run(self):
        """Main echo loop - returns received audio frames immediately"""
        print(f"ECHO_MODE_STARTED enabled={self.echo_enabled}")
        
        if not self.echo_enabled:
            print("Echo mode disabled - use ECHO_TEST=1 to enable")
            return
            
        try:
            while True:
                msg = self.ws.receive()
                if msg is None:
                    break
                    
                evt = json.loads(msg)
                event_type = evt.get("event")
                
                if event_type == "start":
                    self.stream_sid = evt["start"]["streamSid"]
                    print(f"ECHO_STREAM_STARTED sid={self.stream_sid}")
                    continue
                    
                elif event_type == "media":
                    if self.stream_sid:
                        # Echo the exact same frame back to Twilio
                        b64_payload = evt["media"]["payload"]
                        echo_frame = {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": b64_payload}
                        }
                        self.ws.send(json.dumps(echo_frame))
                        print("ECHO_FRAME_SENT")
                        
                elif event_type == "stop":
                    print("ECHO_STREAM_STOPPED")
                    break
                    
        except Exception as e:
            print(f"ECHO_ERROR: {e}")