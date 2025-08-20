import json
from flask import current_app
from .stream_state import stream_registry

class MediaStreamHandler:
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_sid = None
        self.call_sid = None

    def run(self):
        current_app.logger.info("WS_CONNECTED")
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    current_app.logger.info("WS_CLOSED")
                    break
                try:
                    data = json.loads(raw)
                except Exception:
                    current_app.logger.warning("WS_BAD_JSON")
                    continue

                ev = data.get("event")
                if ev == "start":
                    start = data.get("start", {})
                    cp = start.get("customParameters") or {}
                    # לפעמים Twilio שולחת customParameters כמחרוזת JSON
                    if isinstance(cp, str):
                        try: 
                            cp = json.loads(cp)
                        except: 
                            cp = {}
                    self.call_sid = cp.get("call_sid") or cp.get("CallSid") or cp.get("CALL_SID")
                    self.stream_sid = start.get("streamSid")  # לא ממציאים streamSid - לוקחים רק מה שבא מstart
                    current_app.logger.info("WS_START", extra={"streamSid": self.stream_sid, "call_sid": self.call_sid})
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)

                elif ev == "media":
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    
                    # TODO: Live transcription של audio frames
                    # media_payload = data.get("media", {}).get("payload", "")
                    # if media_payload:
                    #     # Decode base64 → PCM audio → Whisper
                    #     pass
                    
                    current_app.logger.debug("WS_FRAME", extra={"len": len(data.get("media",{}).get("payload",""))})

                elif ev == "stop":
                    current_app.logger.info("WS_STOP")
                    break

        except Exception:
            current_app.logger.exception("WS_HANDLER_ERROR")
        finally:
            if self.call_sid:
                stream_registry.clear(self.call_sid)