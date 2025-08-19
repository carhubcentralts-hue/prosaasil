# server/stream_state.py
import time, threading

class StreamRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {}  # call_sid -> {"started": bool, "last_media_at": float}

    def mark_start(self, call_sid):
        with self._lock:
            self._state.setdefault(call_sid, {})["started"] = True
            self._state[call_sid]["last_media_at"] = time.time()

    def touch_media(self, call_sid):
        with self._lock:
            self._state.setdefault(call_sid, {})["last_media_at"] = time.time()

    def get(self, call_sid):
        with self._lock:
            return dict(self._state.get(call_sid, {}))

    def clear(self, call_sid):
        with self._lock:
            self._state.pop(call_sid, None)

stream_registry = StreamRegistry()