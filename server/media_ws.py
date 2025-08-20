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
                except:
                    current_app.logger.warning("WS_BAD_JSON")
                    continue

                ev = data.get("event")
                if ev == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    # Extract call_sid from parameters if available
                    parameters = data["start"].get("customParameters", {})
                    self.call_sid = parameters.get("call_sid")
                    
                    current_app.logger.info("WS_START", extra={"streamSid": self.stream_sid, "call_sid": self.call_sid})
                    
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)

                elif ev == "media":
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    # TODO: Accumulate and send to STT (Hebrew), then NLP+TTS

                elif ev == "stop":
                    current_app.logger.info("WS_STOP")
                    break

        except Exception:
            current_app.logger.exception("WS_HANDLER_ERROR")
        finally:
            if self.call_sid:
                stream_registry.clear(self.call_sid)