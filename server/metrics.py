"""
server/metrics.py — Lightweight Metrics Collection
====================================================
In-memory counters for key operational metrics.
Exposed via /metrics.json endpoint (admin-token protected).
No external dependencies (Prometheus optional).
"""

import time
import threading
from collections import defaultdict


class MetricsCollector:
    """Thread-safe metrics collector with atomic counter operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters = defaultdict(int)
        self._gauges = defaultdict(float)
        self._start_time = time.time()

    def increment(self, name: str, value: int = 1):
        """Atomically increment a counter."""
        with self._lock:
            self._counters[name] += value

    def set_gauge(self, name: str, value: float):
        """Set a gauge to a specific value."""
        with self._lock:
            self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        with self._lock:
            return self._counters[name]

    def get_gauge(self, name: str) -> float:
        """Get current gauge value."""
        with self._lock:
            return self._gauges[name]

    def snapshot(self) -> dict:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timestamp": time.time(),
            }


# Global singleton
metrics = MetricsCollector()

# ─── Counter names (SSOT) ─────────────────────────────────

# WhatsApp
WHATSAPP_INBOUND = "whatsapp_inbound_messages"
WHATSAPP_OUTBOUND = "whatsapp_outbound_messages"
WHATSAPP_ERRORS = "whatsapp_errors"

# Calls
CALLS_STARTED = "calls_started"
CALLS_COMPLETED = "calls_completed"
CALLS_REJECTED = "calls_rejected_max_concurrent"
CALLS_ERRORS = "calls_errors"
CALLS_ACTIVE = "calls_active"  # gauge

# Queue
QUEUE_ENQUEUED = "queue_jobs_enqueued"
QUEUE_COMPLETED = "queue_jobs_completed"
QUEUE_FAILED = "queue_jobs_failed"
QUEUE_DEAD_LETTER = "queue_jobs_dead_letter"

# API
API_REQUESTS = "api_requests_total"
API_ERRORS = "api_errors_total"


def register_metrics_endpoint(app):
    """Register /metrics.json endpoint on a Flask app."""
    from flask import jsonify, request

    @app.route("/metrics.json")
    def metrics_json():
        # Protect with admin token from config (read at request time)
        from server.config import METRICS_TOKEN, INTERNAL_SECRET
        token = METRICS_TOKEN or INTERNAL_SECRET or ""
        auth = request.headers.get("Authorization", "")
        provided = request.args.get("token", "")

        if token and auth != f"Bearer {token}" and provided != token:
            return jsonify({"error": "unauthorized"}), 401

        return jsonify(metrics.snapshot())

    return app
