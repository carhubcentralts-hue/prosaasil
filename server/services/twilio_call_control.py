import logging
import os
import sys
from typing import Optional

from twilio.rest import Client

logger = logging.getLogger(__name__)

def _stdout_log(line: str) -> None:
    """
    Write to the real stdout even if builtins.print was monkey-patched.
    """
    try:
        sys.__stdout__.write(line.rstrip("\n") + "\n")
        sys.__stdout__.flush()
    except Exception:
        # Fall back to logger only.
        pass


def hangup_call(call_sid: Optional[str]) -> bool:
    """
    Hang up a Twilio call via REST API.

    Contract:
    - Returns True on success, False otherwise.
    - Must emit a success log in this exact shape:
      [HANGUP] success call_sid=...
    """
    if not call_sid:
        logger.error("[HANGUP] error missing_call_sid")
        _stdout_log("[HANGUP] error missing_call_sid")
        return False

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        logger.error("[HANGUP] error missing_twilio_credentials call_sid=%s", call_sid)
        _stdout_log(f"[HANGUP] error missing_twilio_credentials call_sid={call_sid}")
        return False

    try:
        client = Client(account_sid, auth_token)
        client.calls(call_sid).update(status="completed")
        logger.info("[HANGUP] success call_sid=%s", call_sid)
        _stdout_log(f"[HANGUP] success call_sid={call_sid}")
        return True
    except Exception as e:
        logger.exception("[HANGUP] error call_sid=%s", call_sid)
        _stdout_log(f"[HANGUP] error call_sid={call_sid} err={type(e).__name__}:{str(e)[:200]}")
        return False

