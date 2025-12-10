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
    
    # 🔥 FIX #2: Store metadata for fast greeting (pre-built prompts, etc.)
    def set_metadata(self, call_sid, key, value):
        """Store metadata for a call (e.g., pre-built prompts)"""
        with self._lock:
            self._st.setdefault(call_sid, {})[key] = value
    
    def get_metadata(self, call_sid, key, default=None):
        """Retrieve metadata for a call"""
        with self._lock:
            return self._st.get(call_sid, {}).get(key, default)
    
    # 🔥 MASTER FIX: Performance stamp tracking for SLA metrics
    def stamp(self, call_sid, name):
        """
        Record a performance timeline event for SLA tracking
        
        Args:
            call_sid: Call session ID
            name: Event name (e.g., 'compact_checked', 'full_upgraded', 'greeting_start')
        """
        with self._lock:
            state = self._st.setdefault(call_sid, {})
            stamps = state.setdefault("perf_stamps", {})
            stamps[name] = time.time()
            # Log for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[PERF] {call_sid[:8]}... {name} @ {stamps[name]:.3f}")
    
    def get_stamps(self, call_sid):
        """Get all performance stamps for a call"""
        with self._lock:
            state = self._st.get(call_sid, {})
            return dict(state.get("perf_stamps", {}))
    
    # 🔥 MASTER FIX: Helper methods for greeting SLA metrics
    def set_metric(self, call_sid, metric_name, value_ms):
        """
        Store a performance metric in milliseconds
        
        Args:
            call_sid: Call session ID
            metric_name: Metric name (e.g., 'openai_connect_ms', 'first_greeting_audio_ms')
            value_ms: Value in milliseconds
        """
        with self._lock:
            state = self._st.setdefault(call_sid, {})
            metrics = state.setdefault("metrics", {})
            metrics[metric_name] = int(value_ms)
    
    def get_metric(self, call_sid, metric_name, default=0):
        """Retrieve a performance metric"""
        with self._lock:
            state = self._st.get(call_sid, {})
            metrics = state.get("metrics", {})
            return metrics.get(metric_name, default)
    
    def get_all_metrics(self, call_sid):
        """Get all performance metrics for a call"""
        with self._lock:
            state = self._st.get(call_sid, {})
            return dict(state.get("metrics", {}))

stream_registry = StreamRegistry()