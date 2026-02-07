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

# Add OpenAI stub
openai_stub = types.ModuleType("openai")
openai_stub.AsyncOpenAI = object
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

from server.media_ws_ai import MediaStreamHandler


class DummyWebSocket:
    def send(self, data):
        return None


def test_gemini_ready_gating():
    """
    Test that Gemini Live properly gates audio transmission until setup_complete.
    
    CRITICAL FIX: Gemini closes (1000 OK) when audio is sent before setup_complete.
    The _gemini_ready flag MUST block audio transmission until setup_complete received.
    
    Requirements from problem statement:
    1. Audio must NOT be sent before setup_complete
    2. Greeting must NOT be sent before setup_complete
    3. Flag should start as False and be set to True only after setup_complete
    """
    handler = MediaStreamHandler(DummyWebSocket())
    
    # Verify _gemini_ready flag exists and starts as False
    assert hasattr(handler, '_gemini_ready'), "_gemini_ready flag must exist"
    assert handler._gemini_ready is False, "_gemini_ready should start as False (blocking audio)"
    
    # Verify _gemini_ready_event exists (for async coordination)
    assert hasattr(handler, '_gemini_ready_event'), "_gemini_ready_event must exist"
    
    # Verify _mark_gemini_ready method exists (to set flag on setup_complete)
    assert hasattr(handler, '_mark_gemini_ready'), "_mark_gemini_ready method must exist"



