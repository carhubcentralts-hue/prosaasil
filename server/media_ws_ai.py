"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
"""
import os, json, time, base64, audioop, math
from simple_websocket import ConnectionClosed

SR = 8000
MIN_UTT_SEC = 0.7   # סוף-מבע לפי דממה קצרה
MAX_UTT_SEC = 6.0   # חיתוך בטיחות

class MediaStreamHandler:
    def __init__(self, ws):
        self.ws = ws
        self.mode = os.getenv("WS_MODE", "AI").upper()  # ודא ש-WS_MODE=AI בסביבה
        self.stream_sid = None
        self.rx = 0
        self.tx = 0
        self.buf = bytearray()
        self.last_rx = None
        self.speaking = False  # חסם לולאה

    def run(self):
        print(f"🚨 MEDIA_STREAM_HANDLER: mode={self.mode}")
        try:
            while True:
                raw = self.ws.receive()
                if raw is None:
                    break
                evt = json.loads(raw)
                et = evt.get("event")

                if et == "start":
                    self.stream_sid = evt["start"]["streamSid"]
                    self.last_rx = time.time()
                    print(f"WS_START sid={self.stream_sid} mode={self.mode}")
                    # פתיחה עם ברכה ב-TTS (בטוח יותר מ-<Play>)
                    if self.mode == "AI":
                        self._speak_text("שלום! איך אפשר לעזור?")
                    continue

                if et == "media":
                    self.rx += 1
                    mulaw = base64.b64decode(evt["media"]["payload"])
                    pcm16 = audioop.ulaw2lin(mulaw, 2)
                    self.last_rx = time.time()

                    if self.mode == "AI" and not self.speaking:
                        self.buf.extend(pcm16)
                        dur = len(self.buf) / (2 * SR)
                        silent = (time.time() - self.last_rx) >= MIN_UTT_SEC
                        too_long = dur >= MAX_UTT_SEC
                        if (silent or too_long) and dur > 0.25:
                            self._process_utterance(bytes(self.buf))
                            self.buf.clear()
                    continue

                if et == "stop":
                    print(f"WS_STOP sid={self.stream_sid} rx={self.rx} tx={self.tx}")
                    break

        except ConnectionClosed:
            print(f"WS_CLOSED sid={self.stream_sid} rx={self.rx} tx={self.tx}")
        except Exception as e:
            print("WS_ERR:", e)
        finally:
            try: 
                self.ws.close()
            except: 
                pass
            print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    # --- מבע → ASR → LLM → TTS ---
    def _process_utterance(self, pcm16_8k: bytes):
        self.speaking = True
        try:
            # For now, simple response without real ASR/LLM
            text = "שמעתי אותך"  # TODO: Replace with real ASR
            print("ASR_TEXT:", text)
            
            reply = "תודה שפנית אלינו. איך אפשר לעזור לך היום?"  # TODO: Replace with LLM
            print("LLM_REPLY:", reply)
            
            # Simple TTS - for now generate a beep
            self._send_beep(700)
            print("TTS_LEN_BYTES: BEEP_SENT")

        finally:
            self.speaking = False

    def _speak_text(self, text: str):
        try:
            print(f"SPEAKING: {text}")
            # For now, generate a welcome beep
            self._send_beep(500)
        except Exception as e:
            print("TTS_INIT_ERR:", e)

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        # clear לפני פריים ראשון
        if self.stream_sid:
            self.ws.send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        for i in range(0, len(mulaw), FR):
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                break
            payload = base64.b64encode(chunk).decode("ascii")
            self.ws.send(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload}
            }))
            self.tx += 1
        # mark (אופציונלי)
        self.ws.send(json.dumps({"event":"mark","streamSid":self.stream_sid,"mark":{"name":"tts_done"}}))

    def _send_beep(self, ms: int):
        # בסיסי: 440Hz ב-PCM16 8kHz
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        self._send_pcm16_as_mulaw_frames(bytes(out))