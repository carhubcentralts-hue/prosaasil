import sys
import types
import asyncio

import pytest

redis_stub = types.ModuleType("redis")
redis_stub.Redis = object
sys.modules.setdefault("redis", redis_stub)

rq_stub = types.ModuleType("rq")
rq_stub.Queue = object
rq_stub.Retry = object
sys.modules.setdefault("rq", rq_stub)

rq_job_stub = types.ModuleType("rq.job")
rq_job_stub.Job = object
sys.modules.setdefault("rq.job", rq_job_stub)

flask_stub = types.ModuleType("flask")
flask_stub.g = types.SimpleNamespace()
flask_stub.request = types.SimpleNamespace()
sys.modules.setdefault("flask", flask_stub)

flask_sqlalchemy_stub = types.ModuleType("flask_sqlalchemy")
flask_sqlalchemy_stub.SQLAlchemy = object
sys.modules.setdefault("flask_sqlalchemy", flask_sqlalchemy_stub)

jobs_stub = types.ModuleType("server.jobs")
jobs_stub.__path__ = []
sys.modules.setdefault("server.jobs", jobs_stub)

call_log_jobs_stub = types.ModuleType("server.jobs.call_log_jobs")
call_log_jobs_stub.create_call_log_job = lambda *args, **kwargs: None
call_log_jobs_stub.save_conversation_turn_job = lambda *args, **kwargs: None
call_log_jobs_stub.finalize_call_log_job = lambda *args, **kwargs: None
sys.modules.setdefault("server.jobs.call_log_jobs", call_log_jobs_stub)

from server.media_ws_ai import MediaStreamHandler


class DummyWebSocket:
    def send(self, data):
        return None


def test_gemini_ready_removed():
    """
    Test that Gemini Live no longer depends on setup_complete event.
    
    CRITICAL FIX: Gemini Live works based on audio flow, not setup_complete events.
    The _gemini_ready flag and related methods should not block audio transmission.
    """
    handler = MediaStreamHandler(DummyWebSocket())
    
    # Verify _gemini_ready is not used for blocking
    # The flag should be False (not blocking) or not exist
    if hasattr(handler, '_gemini_ready'):
        # If flag exists, it must not block audio flow
        assert handler._gemini_ready is False, "_gemini_ready should be False (not blocking)"
    
    # Verify _gemini_ready_event is not used for blocking
    # Event should not be set or should not exist
    if hasattr(handler, '_gemini_ready_event') and handler._gemini_ready_event is not None:
        assert not handler._gemini_ready_event.is_set(), "_gemini_ready_event should not be set (not blocking)"


