# twilio_security.py - SIMPLIFIED FOR DEVELOPMENT
import os
from functools import wraps
from flask import request
import logging

logger = logging.getLogger(__name__)

def require_twilio_signature(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # SIMPLE BYPASS: Development always passes
        logger.info("Twilio webhook called - development mode bypass active")
        return f(*args, **kwargs)
    return wrapper