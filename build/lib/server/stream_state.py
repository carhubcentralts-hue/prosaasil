import time
import threading

class StreamRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._st = {}
    
    def mark_start(self, call_sid):
        with self._lock:
            self._st.setdefault(call_sid, {})["started"] = True
            self._st[call_sid]["last_media_at"] = time.time()
    
    def touch_media(self, call_sid):
        with self._lock:
            self._st.setdefault(call_sid, {})["last_media_at"] = time.time()
    
    def get(self, call_sid):
        with self._lock:
            return dict(self._st.get(call_sid, {}))
    
    def clear(self, call_sid):
        with self._lock:
            self._st.pop(call_sid, None)

stream_registry = StreamRegistry()