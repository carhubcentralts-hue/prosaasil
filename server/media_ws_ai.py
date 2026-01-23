"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
🚫 Google STT/TTS DISABLED for production stability
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib, asyncio, re, unicodedata
import builtins
from dataclasses import dataclass
from typing import Optional
from server.services.mulaw_fast import mulaw_to_pcm16_fast
from server.services.appointment_nlp import extract_appointment_request
from server.services.hebrew_stt_validator import validate_stt_output, is_gibberish, load_hebrew_lexicon
from server.config.voices import DEFAULT_VOICE, OPENAI_VOICES, REALTIME_VOICES  # 🎤 Voice Library

# 🔥 SERVER-FIRST scheduling (Realtime, no tools):
# ⚠️⚠️⚠️ PERMANENTLY DISABLED ⚠️⚠️⚠️
# Appointments MUST use Realtime tools (check_availability, schedule_appointment).
# CORRECT WAY: Use OpenAI Realtime API tools for appointment scheduling
SERVER_FIRST_SCHEDULING = False  # HARDCODED FALSE - DO NOT USE ENV VAR

# 🚫 DISABLE_GOOGLE: Hard off - prevents stalls and latency issues
DISABLE_GOOGLE = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'

# ⚠️ NOTE: ENABLE_REALTIME_TOOLS removed - replaced with per-call _build_realtime_tools_for_call()
# Realtime phone calls now use dynamic tool selection (appointments only when enabled)

# ⚡ PHASE 1: DEBUG mode - חונק כל print ב-hot path
# 🔥 DEBUG=1 → PRODUCTION (minimal logs, quiet mode)
# 🔥 DEBUG=0 → DEVELOPMENT (full logs, verbose mode)
DEBUG = os.getenv("DEBUG", "1") == "1"
DEBUG_TX = os.getenv("DEBUG_TX", "0") == "1"  # 🔥 Separate flag for TX diagnostics

# 🔥 REMOVED: Extra debug flags - use only DEBUG=0 or DEBUG=1
# Per user requirement: "שיש כמה שפחות לוגים בdebug 1!!!!"
# All verbose logging is now controlled by DEBUG flag only

_orig_print = builtins.print

def _dprint(*args, **kwargs):
    """Print only when DEBUG=1 (gating for hot path)"""
    if DEBUG:
        _orig_print(*args, **kwargs)

def force_print(*args, **kwargs):
    """Always print (for critical errors only)"""
    _orig_print(*args, **kwargs)

# חונקים כל print במודול הזה כש-DEBUG=0
builtins.print = _dprint

# ⚡ PHASE 1 Task 4: טלמטריה - 4 מדדים בכל TURN
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

# 🔥 SSOT: Rate limiter for hot path logging
from server.logging_setup import RateLimiter
_event_loop_rate_limiter = RateLimiter()

_now_ms = lambda: int(time.time() * 1000)

def emit_turn_metrics(first_partial, final_ms, tts_ready, total, barge_in=False, eou_reason="unknown"):
    """
    ⚡ PHASE 1: Emit turn latency metrics (non-blocking, uses async logger)
    
    Critical metrics for performance monitoring:
    - STT_FIRST_PARTIAL_MS: Time to first partial from STT
    - STT_FINAL_MS: Time to final/EOU
    - TTS_READY_MS: Time until TTS audio is ready
    - TOTAL_LATENCY_MS: Time until first audio frame sent
    """
    payload = {
        "STT_FIRST_PARTIAL_MS": first_partial,
        "STT_FINAL_MS": final_ms,
        "TTS_READY_MS": tts_ready,
        "TOTAL_LATENCY_MS": total,
        "BARGE_IN_HIT": barge_in,
        "EOU_REASON": eou_reason
    }
    logging.getLogger("turn").info(json.dumps(payload, ensure_ascii=False))

# 🔥 BUILD 186: DISABLED Google Streaming STT - Use OpenAI Realtime API only!
USE_STREAMING_STT = False  # PERMANENTLY DISABLED - OpenAI only!

# 🔥 NAME VALIDATION: Import from centralized module (single source of truth)
from server.services.name_validation import is_valid_customer_name, INVALID_NAME_PLACEHOLDERS
from server.services.prompt_hashing import hash_prompt

# 🔥 BUILD 325: Import all call configuration from centralized config
try:
    from server.config.calls import (
        AUDIO_CONFIG, SIMPLE_MODE, COST_EFFICIENT_MODE, COST_MIN_RMS_THRESHOLD, COST_MAX_FPS,
        VAD_BASELINE_TIMEOUT, VAD_ADAPTIVE_CAP, VAD_ADAPTIVE_OFFSET,
        ECHO_GATE_MIN_RMS, ECHO_GATE_MIN_FRAMES,
        BARGE_IN_VOICE_FRAMES, BARGE_IN_DEBOUNCE_MS,
        MAX_REALTIME_SECONDS_PER_CALL, MAX_AUDIO_FRAMES_PER_CALL,
        NOISE_GATE_MIN_FRAMES,
        GREETING_PROTECT_DURATION_MS, GREETING_MIN_SPEECH_DURATION_MS
    )
except ImportError:
    SIMPLE_MODE = True
    COST_EFFICIENT_MODE = False   # ✅ DISABLED - No FPS throttling (NO FILTERS requirement)
    COST_MIN_RMS_THRESHOLD = 0
    COST_MAX_FPS = 70  # Not used when COST_EFFICIENT_MODE=False
    VAD_BASELINE_TIMEOUT = 80.0
    VAD_ADAPTIVE_CAP = 120.0
    VAD_ADAPTIVE_OFFSET = 60.0
    ECHO_GATE_MIN_RMS = 300.0
    ECHO_GATE_MIN_FRAMES = 5
    BARGE_IN_VOICE_FRAMES = 8
    BARGE_IN_DEBOUNCE_MS = 350
    GREETING_PROTECT_DURATION_MS = 500
    GREETING_MIN_SPEECH_DURATION_MS = 250
    MAX_REALTIME_SECONDS_PER_CALL = 600  # BUILD 335: 10 minutes
    MAX_AUDIO_FRAMES_PER_CALL = 42000    # BUILD 341: 70fps × 600s
    NOISE_GATE_MIN_FRAMES = 0  # Fallback: disabled in Simple Mode
    AUDIO_CONFIG = {
        "simple_mode": True,
        "audio_guard_enabled": False,
        "music_mode_enabled": False,
        "noise_gate_min_frames": 0,
        "echo_guard_enabled": True,
        "frame_pacing_ms": 20,
        "vad_rms": 60,
        "rms_silence_threshold": 30,
        "min_speech_rms": 40,
        "min_rms_delta": 5.0,
    }

# 🎯 BARGE-IN: Allow users to interrupt AI mid-sentence
# Enabled by default with smart state tracking (is_ai_speaking + has_pending_ai_response)
ENABLE_BARGE_IN = os.getenv("ENABLE_BARGE_IN", "true").lower() in ("true", "1", "yes")

# 🚀 REALTIME API MODE - OpenAI Realtime API for phone calls
# 🔥 BUILD 186: ALWAYS enabled - no fallback to Google STT/TTS!
USE_REALTIME_API = True  # FORCED TRUE - OpenAI Realtime API only!

# 🔥 BUILD 318: COST OPTIMIZATION - Use gpt-4o-mini-realtime-preview (75% cheaper!)
# - $10/1M input vs $40/1M for gpt-4o-realtime
# - $20/1M output vs $80/1M for gpt-4o-realtime
# - Good quality for Hebrew voice calls
OPENAI_REALTIME_MODEL = "gpt-4o-mini-realtime-preview"

# ⭐⭐⭐ BUILD 350: REMOVE ALL MID-CALL LOGIC & TOOLS
# Keep calls 100% pure conversation. Only allow appointment scheduling when enabled.
# Everything else (service, city, details) must happen AFTER the call via summary.
# ⭐⭐⭐ CRITICAL: APPOINTMENT SYSTEM SELECTION ⭐⭐⭐
# 
# TWO SYSTEMS EXIST:
# 1. LEGACY: appointment_nlp.py - NLP parsing (DISABLED)
# 2. MODERN: Realtime Tools - check_availability + schedule_appointment (ENABLED)
#
# ⚠️ ONLY ONE SHOULD BE ACTIVE AT A TIME!
# 
# Set to False = Use MODERN Realtime Tools (RECOMMENDED)
# Set to True = Use LEGACY NLP parsing (DEPRECATED)
ENABLE_LEGACY_TOOLS = False  # ✅ MODERN SYSTEM ACTIVE - Realtime Tools only!

# 🔥 FIX: Loop detection disabled (was causing false positives)
ENABLE_LOOP_DETECT = False  # ✅ DISABLED - Loops handled by OpenAI naturally

# 🔥 FIX: Legacy city/service logic disabled (MODERN system handles via post-call summary)
ENABLE_LEGACY_CITY_LOGIC = False  # ✅ DISABLED - City extraction happens post-call

# 🔍 OVERRIDE: Allow env var to switch model if needed
_env_model = os.getenv("OPENAI_REALTIME_MODEL")
if _env_model:
    import logging
    logging.getLogger(__name__).info(
        f"📢 [BUILD 318] Using OPENAI_REALTIME_MODEL from env: {_env_model}"
    )
    OPENAI_REALTIME_MODEL = _env_model

logger.info(f"💰 [BUILD 318] Using model: {OPENAI_REALTIME_MODEL} (cost-optimized)")
logger.info(f"🔊 [NO FILTERS] FPS throttling: DISABLED - all audio passes through, constant pacing only")

# ✅ CRITICAL: App Singleton - create ONCE for entire process lifecycle
# This prevents Flask app recreation per-call which caused 5-6s delays and 503 errors
_flask_app_singleton = None
_flask_app_lock = threading.Lock()

def _get_flask_app():
    """🔥 CRITICAL FIX: Get Flask app WITHOUT creating new instance"""
    from server.app_factory import get_process_app
    return get_process_app()

# 🔥 BUILD 172: CALL STATE MACHINE - Proper lifecycle management
from enum import Enum

class CallState(Enum):
    """Call lifecycle states for proper state machine management"""
    WARMUP = "warmup"      # First 800ms - ignore STT results
    ACTIVE = "active"       # Normal conversation
    CLOSING = "closing"     # Final message sent, waiting to hang up
    ENDED = "ended"         # Call finished, cleanup done


class FrameDropReason(Enum):
    """
    🔥 DIAGNOSTIC: Precise reasons for frame drops in SIMPLE_MODE
    
    Used to track WHY frames are being dropped even when all filters should be off.
    Each drop path must increment the appropriate counter to enable debugging.
    """
    GREETING_LOCK = "greeting_lock"          # Dropped during greeting protection window
    ECHO_GATE = "echo_gate"                  # Dropped by echo suppression (AI speaking)
    ECHO_DECAY = "echo_decay"                # Dropped during post-AI echo decay window
    AUDIO_GUARD = "audio_guard"              # Dropped by audio quality filter
    MUSIC_MODE = "music_mode"                # Dropped during music detection
    QUEUE_FULL = "queue_full"                # Dropped due to queue capacity
    NOISE_GATE = "noise_gate"                # Dropped by noise threshold
    SESSION_NOT_READY = "session_not_ready"  # Dropped before session.updated
    OTHER = "other"                          # Unknown/uncategorized drop


# 🔥 BUILD 172: CALL CONFIG - Loaded from BusinessSettings
@dataclass
class CallConfig:
    """
    Per-call configuration loaded from BusinessSettings at call start.
    All values come from DB - no hardcoded defaults in call logic.
    """
    business_id: int
    business_name: str = ""
    
    # Greeting settings
    greeting_enabled: bool = True
    bot_speaks_first: bool = False  # 🔥 DEPRECATED: Always True in runtime (hardcoded)
    greeting_text: str = ""
    
    # Call control settings
    auto_end_after_lead_capture: bool = False
    auto_end_on_goodbye: bool = True  # Changed default to True - auto-hangup on goodbye
    smart_hangup_enabled: bool = True
    enable_calendar_scheduling: bool = True  # 🔥 BUILD 186: AI can schedule appointments
    verification_enabled: bool = False  # 🔥 FIX: Disable legacy verification/lead confirmed early hangup
    
    # 🔥 BUILD 309: SIMPLE_MODE Call Profile
    call_goal: str = "lead_only"  # "lead_only" or "appointment"
    confirm_before_hangup: bool = True  # Always confirm before disconnecting
    
    # Timeouts
    silence_timeout_sec: int = 15
    silence_max_warnings: int = 2
    max_call_duration_sec: int = 600  # 10 minutes default
    
    # STT/VAD tuning
    # 🔥 BUILD 186: Balanced values - filter noise but remain responsive
    stt_warmup_ms: int = 800   # Ignore first 800ms of STT (greeting protection)
    barge_in_delay_ms: int = 500  # Require 500ms of continuous speech before barge-in
    
    # Required fields for lead capture
    required_lead_fields: list = None
    
    # Closing sentence - loaded from BusinessSettings, no hardcoded default
    closing_sentence: str = ""
    
    def __post_init__(self):
        if self.required_lead_fields is None:
            # 🔥 PROMPT-ONLY MODE: No hardcoded required fields
            # What is "required" is defined by the business system prompt only
            self.required_lead_fields = []


def load_call_config(business_id: int) -> CallConfig:
    """
    🔥 BUILD 172: Load call configuration from BusinessSettings.
    Called at call start to get all per-business settings.
    """
    try:
        from server.models_sql import Business, BusinessSettings
        from sqlalchemy import text
        from server.db import db
        
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"⚠️ [CALL CONFIG] Business {business_id} not found - using defaults")
            return CallConfig(business_id=business_id)
        
        # 🔥 BUILD 309: Try to load new columns with raw SQL first (handles missing columns gracefully)
        call_goal = 'lead_only'
        confirm_before_hangup = True
        try:
            result = db.session.execute(text(
                "SELECT call_goal, confirm_before_hangup FROM business_settings WHERE tenant_id = :bid LIMIT 1"
            ), {"bid": business_id})
            row = result.fetchone()
            if row:
                call_goal = row[0] or 'lead_only'
                confirm_before_hangup = row[1] if row[1] is not None else True
        except Exception as sql_err:
            logger.debug(f"🔧 [BUILD 309] New columns not yet in DB: {sql_err}")
        
        # 🔥 BUILD 186 FIX: Handle missing columns gracefully
        settings = None
        try:
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        except Exception as db_err:
            logger.warning(f"⚠️ [CALL CONFIG] Could not load settings for {business_id} (DB schema issue): {db_err}")
        
        # 🔥 PROMPT-ONLY MODE: No hardcoded required fields
        # What is "required" comes from the business system prompt, not Python code
        raw_required_fields = getattr(settings, 'required_lead_fields', None) if settings else None
        if raw_required_fields and isinstance(raw_required_fields, list):
            # Remove 'phone' - it's collected at end of call, not a required field
            sanitized_fields = [f for f in raw_required_fields if f != 'phone']
            required_lead_fields = sanitized_fields if sanitized_fields else []
        else:
            required_lead_fields = []
        
        logger.info(f"🔧 [PROMPT-ONLY] required_lead_fields: {raw_required_fields} → {required_lead_fields}")
        
        config = CallConfig(
            business_id=business_id,
            business_name=business.name or "",
            greeting_enabled=True,
            bot_speaks_first=getattr(settings, 'bot_speaks_first', False) if settings else False,  # 🔥 DEPRECATED: Loaded but ignored in runtime
            greeting_text=business.greeting_message or "",
            auto_end_after_lead_capture=getattr(settings, 'auto_end_after_lead_capture', False) if settings else False,
            auto_end_on_goodbye=getattr(settings, 'auto_end_on_goodbye', True) if settings else True,  # Changed default to True
            smart_hangup_enabled=getattr(settings, 'smart_hangup_enabled', True) if settings else True,
            enable_calendar_scheduling=getattr(settings, 'enable_calendar_scheduling', True) if settings else True,
            verification_enabled=getattr(settings, 'verification_enabled', False) if settings else False,
            call_goal=call_goal,
            confirm_before_hangup=confirm_before_hangup,
            silence_timeout_sec=getattr(settings, 'silence_timeout_sec', 15) if settings else 15,
            silence_max_warnings=getattr(settings, 'silence_max_warnings', 2) if settings else 2,
            required_lead_fields=required_lead_fields,
            closing_sentence=getattr(settings, 'closing_sentence', None) or business.greeting_message or ""
        )
        
        logger.info(f"✅ [CALL CONFIG] Loaded for business {business_id}: "
                   f"bot_speaks_first={config.bot_speaks_first}, "
                   f"auto_end_goodbye={config.auto_end_on_goodbye}, "
                   f"auto_end_lead={config.auto_end_after_lead_capture}, "
                   f"calendar_scheduling={config.enable_calendar_scheduling}, "
                   f"call_goal={config.call_goal}, "
                   f"confirm_before_hangup={config.confirm_before_hangup}, "
                   f"silence_timeout={config.silence_timeout_sec}s")
        
        return config
        
    except Exception as e:
        logger.error(f"❌ [CALL CONFIG] Error loading config for business {business_id}: {e}")
        return CallConfig(business_id=business_id)


# 📋 CRM CONTEXT: Track lead and appointment state during call
@dataclass
class CallCrmContext:
    """
    Context for tracking CRM state during a phone call.
    Ensures every call creates/updates a lead and can schedule appointments.
    
    🔥 NEW: has_appointment_created flag - set true only after server appointment creation
    🔥 NEW: pending_slot - tracks date/time that was checked for availability
    🔥 NEW: customer_name - persists extracted name between NLP runs (survives 10-message window)
    """
    business_id: int
    customer_phone: str
    customer_name: Optional[str] = None  # 🔥 Persist name from NLP to survive conversation window
    lead_id: Optional[int] = None
    last_appointment_id: Optional[int] = None
    has_appointment_created: bool = False  # 🔥 GUARD: True only after [SERVER] ✅ appointment_created
    pending_slot: Optional[dict] = None  # 🔥 {"date": "2025-11-17", "time": "18:00", "available": True}


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 MASTER FIX: AUDIO STATE MACHINE - Central control for all audio state
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class AudioState:
    """
    Unified audio state machine for reliable turn-taking and barge-in.
    
    Controls:
    - is_ai_speaking: Flips only on response.audio.start/response.audio.done
    - active_response_id: Synchronized with OpenAI response lifecycle
    - is_playing_greeting: Set only on first response.audio.delta, cleared on done
    - user_has_spoken: Per-utterance tracking
    - barge_in_active: Debounced barge-in state (one trigger per utterance)
    
    Thread-safe via _lock.
    """
    # Core state flags
    is_ai_speaking: bool = False
    active_response_id: Optional[str] = None
    is_playing_greeting: bool = False
    user_has_spoken: bool = False
    barge_in_active: bool = False
    
    # Debouncing
    last_barge_in_ts: Optional[float] = None
    barge_in_debounce_ms: int = 350  # Default from config (BARGE_IN_DEBOUNCE_MS)
    
    # VAD smoothing state
    ema_noise_floor: float = 20.0  # EMA of noise floor
    consecutive_voice_frames: int = 0
    consecutive_silence_frames: int = 0
    voice_started_ts: Optional[float] = None
    
    # 🔥 FIX: Track AI audio start time for echo suppression window
    last_ai_audio_start_ts: Optional[float] = None
    
    # 🔥 FIX: Track last hallucination to prevent repeats
    last_hallucination: str = ""
    
    # Safety tracking
    _lock: threading.RLock = None  # Thread-safe state access
    
    def __post_init__(self):
        """Initialize lock after dataclass creation"""
        if self._lock is None:
            self._lock = threading.RLock()
    
    def set_ai_speaking(self, speaking: bool, response_id: Optional[str] = None):
        """
        Set AI speaking state (thread-safe)
        
        Args:
            speaking: True if AI is speaking
            response_id: Response ID if starting, None if stopping
        """
        with self._lock:
            self.is_ai_speaking = speaking
            if speaking and response_id:
                self.active_response_id = response_id
                logger.debug(f"[AUDIO_STATE] AI speaking started: response_id={response_id}")
            elif not speaking:
                # 🔥 CRITICAL FIX: DON'T clear active_response_id when audio stops!
                # Keep it until response.done arrives so barge-in can still cancel
                # Old bug: Clearing here prevented barge-in after audio.done but before response.done
                logger.debug(f"[AUDIO_STATE] AI speaking stopped: response_id={self.active_response_id}")
                # active_response_id stays set - will be cleared in response.done handler
    
    def set_greeting_playing(self, playing: bool):
        """Set greeting playing state (thread-safe)"""
        with self._lock:
            self.is_playing_greeting = playing
            logger.debug(f"[AUDIO_STATE] Greeting playing: {playing}")
    
    def mark_user_spoken(self):
        """Mark that user has spoken (thread-safe)"""
        with self._lock:
            self.user_has_spoken = True
            logger.debug(f"[AUDIO_STATE] User has spoken")
    
    def try_trigger_barge_in(self) -> bool:
        """
        Try to trigger barge-in with debouncing
        
        Returns:
            True if barge-in triggered, False if debounced
        """
        with self._lock:
            now = time.time()
            
            # Check debounce
            if self.last_barge_in_ts:
                elapsed_ms = (now - self.last_barge_in_ts) * 1000
                if elapsed_ms < self.barge_in_debounce_ms:
                    logger.debug(f"[AUDIO_STATE] Barge-in debounced ({elapsed_ms:.0f}ms < {self.barge_in_debounce_ms}ms)")
                    return False
            
            # Trigger barge-in
            self.barge_in_active = True
            self.last_barge_in_ts = now
            logger.info(f"[AUDIO_STATE] Barge-in triggered! response_id={self.active_response_id}")
            return True
    
    def clear_barge_in(self):
        """Clear barge-in state after utterance completes"""
        with self._lock:
            self.barge_in_active = False
            logger.debug(f"[AUDIO_STATE] Barge-in cleared")
    
    def update_vad_smoothing(self, rms: float, is_voice: bool, frame_duration_ms: int = 20):
        """
        Update VAD smoothing state with EMA noise floor
        
        Args:
            rms: Current frame RMS
            is_voice: Whether frame is classified as voice
            frame_duration_ms: Frame duration in milliseconds
        """
        with self._lock:
            # Import config here to avoid circular imports
            try:
                from server.config.calls import (
                    AUDIO_GUARD_EMA_ALPHA,
                    AUDIO_GUARD_MIN_SPEECH_FRAMES,
                    AUDIO_GUARD_SILENCE_RESET_FRAMES
                )
            except ImportError:
                AUDIO_GUARD_EMA_ALPHA = 0.12
                AUDIO_GUARD_MIN_SPEECH_FRAMES = 12
                AUDIO_GUARD_SILENCE_RESET_FRAMES = 20
            
            # Update EMA noise floor
            if not is_voice:
                self.ema_noise_floor = (AUDIO_GUARD_EMA_ALPHA * rms + 
                                       (1 - AUDIO_GUARD_EMA_ALPHA) * self.ema_noise_floor)
            
            # Track consecutive frames
            if is_voice:
                self.consecutive_voice_frames += 1
                self.consecutive_silence_frames = 0
                if self.voice_started_ts is None:
                    self.voice_started_ts = time.time()
            else:
                self.consecutive_silence_frames += 1
                self.consecutive_voice_frames = 0
                
                # Reset on long silence
                if self.consecutive_silence_frames >= AUDIO_GUARD_SILENCE_RESET_FRAMES:
                    self.voice_started_ts = None
    
    def should_send_audio(self) -> bool:
        """
        Check if audio should be sent based on VAD smoothing
        
        Returns:
            True if audio meets quality criteria
        """
        with self._lock:
            # Import config
            try:
                from server.config.calls import AUDIO_GUARD_MIN_SPEECH_FRAMES
            except ImportError:
                AUDIO_GUARD_MIN_SPEECH_FRAMES = 12
            
            # Require minimum consecutive voice frames
            return self.consecutive_voice_frames >= AUDIO_GUARD_MIN_SPEECH_FRAMES
    
    def get_dynamic_threshold(self) -> float:
        """
        Calculate dynamic VAD threshold based on EMA noise floor
        
        Returns:
            Dynamic threshold value
        """
        with self._lock:
            try:
                from server.config.calls import VAD_ADAPTIVE_OFFSET
            except ImportError:
                VAD_ADAPTIVE_OFFSET = 55.0
            
            return self.ema_noise_floor + VAD_ADAPTIVE_OFFSET


# 🔧 APPOINTMENT VALIDATION HELPER
def validate_appointment_slot(business_id: int, requested_dt) -> bool:
    """
    Validate that requested appointment slot is available:
    1. Within business hours
    2. No overlapping appointments (checks calendar availability)
    3. Uses slot_size_min from business settings
    
    Args:
        business_id: Business ID
        requested_dt: datetime object - can be:
            - Timezone-aware: will be converted to business timezone
            - Naive: ASSUMED to be in business timezone (Asia/Jerusalem for Israel)
    
    Returns:
        True if slot is valid AND available, False otherwise
        
    Note: This system operates in Israel timezone. Naive datetimes are 
    assumed to be Israel local time. For cross-timezone support, always 
    pass timezone-aware datetimes.
    """
    try:
        from server.policy.business_policy import get_business_policy
        from datetime import datetime, timedelta
        import pytz
        
        policy = get_business_policy(business_id)
        business_tz = pytz.timezone(policy.tz)  # Get business timezone early
        
        # 🔥 STRICT TIMEZONE HANDLING:
        # 1. Timezone-aware input: Convert to business timezone
        # 2. Naive input: Assume it's already in business timezone (Israel local time)
        if requested_dt.tzinfo is not None:
            # Convert from source timezone to business timezone
            requested_dt = requested_dt.astimezone(business_tz)
            logger.debug(f"[VALIDATION] Timezone-aware input converted to {policy.tz}: {requested_dt}")
        else:
            # Naive datetime - assume it's in business local time
            logger.debug(f"[VALIDATION] Naive input assumed to be in {policy.tz}: {requested_dt}")
        
        # 🔥 BUILD 183: Check booking_window_days and min_notice_min FIRST
        now = datetime.now(business_tz)
        
        # Check minimum notice time
        if policy.min_notice_min > 0:
            min_allowed_time = now + timedelta(minutes=policy.min_notice_min)
            if requested_dt.tzinfo is None:
                # Make requested_dt timezone-aware for comparison
                requested_dt_aware = business_tz.localize(requested_dt)
            else:
                requested_dt_aware = requested_dt
            
            if requested_dt_aware < min_allowed_time:
                logger.error(f"❌ [VALIDATION] Slot {requested_dt} too soon! Minimum {policy.min_notice_min}min notice required (earliest: {min_allowed_time.strftime('%H:%M')})")
                return False
            else:
                logger.info(f"✅ [VALIDATION] Min notice check passed ({policy.min_notice_min}min)")
        
        # Check booking window (max days ahead)
        if policy.booking_window_days > 0:
            max_booking_date = now + timedelta(days=policy.booking_window_days)
            if requested_dt.tzinfo is None:
                requested_dt_aware = business_tz.localize(requested_dt)
            else:
                requested_dt_aware = requested_dt
            
            if requested_dt_aware > max_booking_date:
                logger.error(f"❌ [VALIDATION] Slot {requested_dt.date()} too far ahead! Max {policy.booking_window_days} days allowed (until {max_booking_date.date()})")
                return False
            else:
                logger.info(f"✅ [VALIDATION] Booking window check passed ({policy.booking_window_days} days)")
        
        # 🔥 STEP 1: Check business hours (skip for 24/7)
        if not policy.allow_24_7:
            # Python datetime.weekday(): Mon=0, Tue=1, ..., Sun=6
            # Policy format: "sun", "mon", "tue", "wed", "thu", "fri", "sat"
            weekday_map = {
                0: "mon",
                1: "tue",
                2: "wed",
                3: "thu",
                4: "fri",
                5: "sat",
                6: "sun"
            }
            
            weekday_key = weekday_map.get(requested_dt.weekday())
            if not weekday_key:
                logger.error(f"❌ [VALIDATION] Invalid weekday: {requested_dt.weekday()}")
                return False
            
            # Get opening hours for this day
            day_hours = policy.opening_hours.get(weekday_key, [])
            if not day_hours:
                logger.error(f"❌ [VALIDATION] Business closed on {weekday_key}")
                return False
            
            # Check if time falls within any window
            requested_time = requested_dt.time()
            time_valid = False
            
            for window in day_hours:
                start_str, end_str = window[0], window[1]
                
                # Parse times
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()
                
                # Handle overnight windows (e.g., 21:00-02:00)
                if start_time <= end_time:
                    # Normal window (same day)
                    if start_time <= requested_time <= end_time:
                        time_valid = True
                        break
                else:
                    # Overnight window
                    if requested_time >= start_time or requested_time <= end_time:
                        time_valid = True
                        break
            
            if not time_valid:
                logger.error(f"❌ [VALIDATION] Slot {requested_time} outside business hours {day_hours}")
                return False
            else:
                logger.info(f"✅ [VALIDATION] Slot {requested_time} within business hours")
        else:
            logger.info(f"✅ [VALIDATION] 24/7 business - hours check skipped")
        
        # 🔥 STEP 2: Check calendar availability (prevent overlaps!)
        # Calculate end time using slot_size_min from policy
        slot_duration_min = policy.slot_size_min  # 15, 30, or 60 minutes
        
        # Note: requested_dt is already normalized to business timezone at the start
        # Convert to naive for DB comparison (DB stores naive in Israel local time)
        requested_end_dt = requested_dt + timedelta(minutes=slot_duration_min)
        
        # Strip tzinfo for DB comparison - requested_dt is already in correct timezone
        if hasattr(requested_dt, 'tzinfo') and requested_dt.tzinfo:
            requested_start_naive = requested_dt.replace(tzinfo=None)
            requested_end_naive = requested_end_dt.replace(tzinfo=None)
        else:
            # Already naive
            requested_start_naive = requested_dt
            requested_end_naive = requested_end_dt
        
        logger.debug(f"[VALIDATION] Checking calendar: {requested_start_naive.strftime('%Y-%m-%d %H:%M')} - {requested_end_naive.strftime('%H:%M')} (slot_size={slot_duration_min}min)")
        
        # Query DB for overlapping appointments
        from server.models_sql import Appointment
        app = _get_flask_app()
        with app.app_context():
            # Find appointments that overlap with requested slot
            # Overlap logic: (start1 < end2) AND (end1 > start2)
            overlapping = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.status.in_(['scheduled', 'confirmed']),  # Only active appointments
                Appointment.start_time < requested_end_naive,  # Existing start before our end
                Appointment.end_time > requested_start_naive  # Existing end after our start
            ).count()
            
            if overlapping > 0:
                logger.error(f"❌ [VALIDATION] CONFLICT! Found {overlapping} overlapping appointment(s) in calendar")
                return False
            else:
                logger.info(f"✅ [VALIDATION] Calendar available - no conflicts")
                return True
        
    except Exception as e:
        logger.error(f"❌ [VALIDATION] Error validating slot: {e}")
        import traceback
        traceback.print_exc()
        return False


# 🔧 CRM HELPER FUNCTIONS (Server-side only, no Realtime Tools)
def ensure_lead(business_id: int, customer_phone: str) -> Optional[int]:
    """
    Find or create lead at call start
    
    ⚠️ P0-1 FIX: This function runs in background threads with proper session management.
    Each call creates its own scoped session for thread safety.
    
    Args:
        business_id: Business ID
        customer_phone: Customer phone in E.164 format
    
    Returns:
        Lead ID if found/created, None on error
    """
    try:
        from server.models_sql import Lead
        from server.db import db
        from sqlalchemy.orm import scoped_session, sessionmaker
        from datetime import datetime
        
        app = _get_flask_app()
        with app.app_context():
            # ✅ P0-1: Create new scoped session for this background thread
            # Note: Each background thread MUST have its own session. We cannot reuse
            # Flask's db.session because it's not thread-safe. Creating a new scoped
            # session for each operation ensures proper isolation.
            engine = db.engine
            Session = scoped_session(sessionmaker(bind=engine))
            session = Session()
            
            try:
                # Normalize phone to E.164
                phone = customer_phone.strip()
                if not phone.startswith('+'):
                    if phone.startswith('0'):
                        phone = '+972' + phone[1:]
                    else:
                        phone = '+972' + phone
                
                # Search for existing lead
                lead = session.query(Lead).filter_by(
                    tenant_id=business_id,
                    phone_e164=phone
                ).first()
                
                if lead:
                    # Update last contact time
                    lead.last_contact_at = datetime.utcnow()
                    session.commit()
                    lead_id = lead.id
                    logger.info(f"✅ [CRM] Found existing lead #{lead_id} for {phone}")
                    return lead_id
                else:
                    # Create new lead
                    lead = Lead(
                        tenant_id=business_id,
                        phone_e164=phone,
                        first_name="Customer",  # Will be updated during call
                        source="phone_call",
                        status="new",
                        created_at=datetime.utcnow(),
                        last_contact_at=datetime.utcnow()
                    )
                    session.add(lead)
                    session.commit()
                    lead_id = lead.id
                    logger.info(f"✅ [CRM] Created new lead #{lead_id} for {phone}")
                    return lead_id
                    
            except Exception as e:
                session.rollback()
                logger.error(f"❌ [CRM] ensure_lead DB error: {e}")
                import traceback
                traceback.print_exc()
                return None
            finally:
                session.close()
                Session.remove()
                
    except Exception as e:
        logger.error(f"❌ [CRM] ensure_lead error: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_lead_on_call(lead_id: int, summary: Optional[str] = None, 
                        status: Optional[str] = None, notes: Optional[str] = None):
    """
    Update lead at call end with summary/status
    
    ✅ P0-1 FIX: Uses proper session management for background threads
    
    Args:
        lead_id: Lead ID to update
        summary: Call summary (optional)
        status: New status (optional)
        notes: Additional notes (optional)
    """
    try:
        from server.models_sql import Lead
        from server.db import db
        from sqlalchemy.orm import scoped_session, sessionmaker
        from datetime import datetime
        
        app = _get_flask_app()
        with app.app_context():
            # ✅ P0-1: Create new session for this operation
            engine = db.engine
            Session = scoped_session(sessionmaker(bind=engine))
            session = Session()
            
            try:
                lead = session.query(Lead).get(lead_id)
                if not lead:
                    logger.warning(f"⚠️ [CRM] Lead #{lead_id} not found")
                    return
                
                # Update fields
                if summary:
                    lead.summary = summary
                
                if status:
                    lead.status = status
                
                if notes:
                    existing_notes = lead.notes or ""
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                    lead.notes = f"{existing_notes}\n\n[{timestamp}] {notes}".strip()
                
                lead.updated_at = datetime.utcnow()
                session.commit()
                
                logger.info(f"✅ [CRM] Updated lead #{lead_id}: summary={bool(summary)}, status={status}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"❌ [CRM] update_lead_on_call DB error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                session.close()
                Session.remove()
            
    except Exception as e:
        logger.error(f"❌ [CRM] update_lead_on_call error: {e}")
        import traceback
        traceback.print_exc()


def create_appointment_from_realtime(business_id: int, customer_phone: str, 
                                     customer_name: str, treatment_type: str,
                                     start_iso: str, end_iso: str, 
                                     notes: Optional[str] = None):
    """
    Create appointment directly from server (no Realtime Tools)
    Called when AI mentions date/time in conversation
    
    Args:
        business_id: Business ID
        customer_phone: Customer phone
        customer_name: Customer name
        treatment_type: Service type
        start_iso: Start time in ISO format
        end_iso: End time in ISO format
        notes: Optional notes
    
    Returns:
        dict with ok/error/message/appointment_id OR
        int (appointment ID) for backwards compatibility OR
        None on error
    """
    logger.info(f"")
    logger.info(f"🔧 [CREATE_APPT] ========== create_appointment_from_realtime called ==========")
    logger.info(f"🔧 [CREATE_APPT] Input parameters:")
    logger.info(f"🔧 [CREATE_APPT]   - business_id: {business_id}")
    logger.info(f"🔧 [CREATE_APPT]   - customer_name: {customer_name}")
    logger.info(f"🔧 [CREATE_APPT]   - customer_phone: {customer_phone}")
    logger.info(f"🔧 [CREATE_APPT]   - treatment_type: {treatment_type}")
    logger.info(f"🔧 [CREATE_APPT]   - start_iso: {start_iso}")
    logger.info(f"🔧 [CREATE_APPT]   - end_iso: {end_iso}")
    logger.info(f"🔧 [CREATE_APPT]   - notes: {notes}")
    
    try:
        from server.agent_tools.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
        
        app = _get_flask_app()
        with app.app_context():
            logger.info(f"🔧 [CREATE_APPT] Creating CreateAppointmentInput...")
            input_data = CreateAppointmentInput(
                business_id=business_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                treatment_type=treatment_type,
                start_iso=start_iso,
                end_iso=end_iso,
                notes=notes,
                source="realtime_phone"
            )
            logger.info(f"🔧 [CREATE_APPT] Input created successfully, calling _calendar_create_appointment_impl...")
            
            result = _calendar_create_appointment_impl(input_data, context=None, session=None)
            logger.info(f"🔧 [CREATE_APPT] _calendar_create_appointment_impl returned: {type(result)}")
            
            # 🔥 FIX: Handle CreateAppointmentOutput dataclass (not dict!)
            if hasattr(result, 'appointment_id'):
                # Success - got CreateAppointmentOutput
                appt_id = result.appointment_id
                logger.info(f"✅ [CREATE_APPT] SUCCESS! Appointment #{appt_id} created")
                logger.info(f"✅ [CREATE_APPT]   - status: {result.status}")
                logger.info(f"✅ [CREATE_APPT]   - whatsapp_status: {result.whatsapp_status}")
                logger.info(f"✅ [CREATE_APPT]   - lead_id: {result.lead_id}")
                logger.info(f"✅ [CREATE_APPT]   - message: {result.confirmation_message}")
                # Return dict for backwards compatibility
                return {
                    "ok": True,
                    "appointment_id": appt_id,
                    "status": result.status,
                    "message": result.confirmation_message,
                    "whatsapp_status": result.whatsapp_status,
                    "lead_id": result.lead_id
                }
            elif isinstance(result, dict):
                # Legacy dict format
                logger.info(f"🔧 [CREATE_APPT] Got dict result: {result}")
                if result.get("ok"):
                    appt_id = result.get("appointment_id")
                    logger.info(f"✅ [CREATE_APPT] SUCCESS (dict)! Appointment #{appt_id} created")
                else:
                    error_msg = result.get("message", "Unknown error")
                    logger.error(f"❌ [CREATE_APPT] FAILED (dict): {error_msg}")
                return result
            else:
                # Unexpected result format
                logger.error(f"❌ [CREATE_APPT] UNEXPECTED RESULT TYPE: {type(result)}")
                logger.error(f"❌ [CREATE_APPT] Result value: {result}")
                return None
                
    except Exception as e:
        logger.error(f"❌ [CRM] create_appointment_from_realtime error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 🔥 SERVER-FIRST APPOINTMENT PARSING (deterministic, no LLM)
# ──────────────────────────────────────────────────────────────────────────────
_DATE_TOKEN_RE = re.compile(r"(היום|מחרתיים|מחר|(?:ביום\s+)?(?:יום\s+)?(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת))")

def _extract_hebrew_date_token(text: str) -> str:
    if not text:
        return ""
    m = _DATE_TOKEN_RE.search(text)
    return (m.group(1) or "").strip() if m else ""

def _extract_hebrew_time_token(text: str) -> str:
    """
    Best-effort extraction of a time phrase from Hebrew STT.
    Returns a short string that resolve_hebrew_time() can parse (e.g. "15:30", "שלוש וחצי", "בשעה 3").
    """
    if not text:
        return ""
    t = text.strip()
    # HH:MM
    m = re.search(r"\b(\d{1,2}:\d{2})\b", t)
    if m:
        return m.group(1)
    # "בשעה 3", "ב 15", "בשעה שלוש וחצי", etc.
    m = re.search(r"(?:בשעה|בש|ב)\s+([^\s,\.!?]+(?:\s+(?:וחצי|ורבע))?)", t)
    if m:
        return m.group(1).strip()
    # Hebrew number word standalone + optional "וחצי/ורבע"
    m = re.search(
        r"\b(אחת|אחד|שתיים|שניים|שתים|שלוש|ארבע|חמש|חמישה|שש|שבע|שמונה|תשע|עשר|עשרה|אחת עשרה|אחד עשר|שתים עשרה|שנים עשר)(?:\s+(וחצי|ורבע))?\b",
        t,
    )
    if m:
        base = m.group(1)
        suf = m.group(2) or ""
        return (base + (" " + suf if suf else "")).strip()
    # Digit hour near "שעה/בשעה"
    m = re.search(r"(?:שעה|בשעה)\s+(\d{1,2})(?:\b|:)", t)
    if m:
        return m.group(1)
    return ""


# ⚡ BUILD 168.2: Minimal boot logging (clean startup)
logger.info(f"[BOOT] USE_REALTIME_API={USE_REALTIME_API} MODEL={OPENAI_REALTIME_MODEL}")
if not USE_REALTIME_API:
    logger.warning("[BOOT] USE_REALTIME_API=FALSE - AI will NOT speak during calls!")

# 🎯 AUDIO MODE STARTUP LOG - Single source of truth
logger.info(
    f"[AUDIO_MODE] simple_mode={AUDIO_CONFIG['simple_mode']}, "
    f"audio_guard_enabled={AUDIO_CONFIG['audio_guard_enabled']}, "
    f"music_mode_enabled={AUDIO_CONFIG['music_mode_enabled']}, "
    f"noise_gate_min_frames={AUDIO_CONFIG['noise_gate_min_frames']}, "
    f"echo_guard_enabled={AUDIO_CONFIG['echo_guard_enabled']}"
)

# ⚡ THREAD-SAFE SESSION REGISTRY for multi-call support
# Each call_sid has its own session + dispatcher state
_sessions_registry = {}  # call_sid -> {"session": StreamingSTTSession, "utterance": {...}, "tenant": str, "ts": float}
_registry_lock = threading.RLock()
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "50"))

# 🔥 SESSION LIFECYCLE: Handler registry for webhook-triggered close
# Maps call_sid -> MediaStreamHandler instance for external close triggers
_handler_registry = {}  # call_sid -> MediaStreamHandler
_handler_registry_lock = threading.RLock()

def _register_session(call_sid: str, session, tenant_id=None):
    """Register a new STT session for a call (thread-safe)"""
    with _registry_lock:
        if len(_sessions_registry) >= MAX_CONCURRENT_CALLS:
            raise RuntimeError(f"Over capacity: {len(_sessions_registry)}/{MAX_CONCURRENT_CALLS} calls")
        _sessions_registry[call_sid] = {
            "session": session,
            "utterance": {
                "id": None, 
                "partial_cb": None, 
                "final_buf": None,
                "final_received": None,  # ⚡ NEW: Event for waiting on final
                "last_partial": ""  # ⚡ NEW: Backup partial text
            },
            "tenant": tenant_id,
            "ts": time.time()
        }
        if DEBUG: logger.debug(f"✅ [REGISTRY] Registered session for call {call_sid[:8]}... (tenant: {tenant_id}, total: {len(_sessions_registry)})")

def _get_session(call_sid: str):
    """Get STT session for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.get(call_sid)
        return item["session"] if item else None

def _get_utterance_state(call_sid: str):
    """Get utterance state for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.get(call_sid)
        return item["utterance"] if item else None

def _close_session(call_sid: str):
    """Close and remove STT session for a call (thread-safe)"""
    with _registry_lock:
        item = _sessions_registry.pop(call_sid, None)
    
    if item:
        try:
            item["session"].close()
            if DEBUG: logger.debug(f"✅ [REGISTRY] Closed session for call {call_sid[:8]}... (remaining: {len(_sessions_registry)})")
        except Exception as e:
            if DEBUG: logger.debug(f"⚠️ [REGISTRY] Error closing session for {call_sid[:8]}...: {e}")

def _register_handler(call_sid: str, handler):
    """
    Register MediaStreamHandler for webhook-triggered close (thread-safe)
    
    🔥 SHADOW HANDLER PROTECTION: If handler already exists for call_sid,
    close it first to prevent duplicate handlers causing weird behavior.
    """
    with _handler_registry_lock:
        # Check if handler already exists (shadow handler from previous instance)
        existing_handler = _handler_registry.get(call_sid)
        # Only close if it's a different handler (not the same object being re-registered)
        if existing_handler and existing_handler is not handler:
            _orig_print(
                f"⚠️ [REGISTRY_REPLACED] Found existing handler for {call_sid[:8]}... - closing shadow handler",
                flush=True
            )
            # Close the existing handler outside the lock to prevent deadlock
            # Store it to close after releasing lock
            shadow_handler = existing_handler
        else:
            shadow_handler = None
        
        # Register new handler
        _handler_registry[call_sid] = handler
        _orig_print(f"✅ [HANDLER_REGISTRY] Registered handler for {call_sid}", flush=True)
    
    # Close shadow handler if found (outside lock to prevent deadlock)
    # This runs outside the lock to prevent blocking and potential deadlocks
    if shadow_handler:
        try:
            _orig_print(f"🧹 [REGISTRY_REPLACED] Closing shadow handler for {call_sid[:8]}...", flush=True)
            shadow_handler.close_session("replaced_by_new_handler")
        except Exception as e:
            _orig_print(f"⚠️ [REGISTRY_REPLACED] Error closing shadow handler: {e}", flush=True)
            import traceback
            _orig_print(f"   Traceback: {traceback.format_exc()}", flush=True)

def _get_handler(call_sid: str):
    """Get MediaStreamHandler for a call (thread-safe)"""
    with _handler_registry_lock:
        return _handler_registry.get(call_sid)

def _unregister_handler(call_sid: str):
    """Remove handler from registry (thread-safe)"""
    with _handler_registry_lock:
        handler = _handler_registry.pop(call_sid, None)
        if handler:
            _orig_print(f"✅ [HANDLER_REGISTRY] Unregistered handler for {call_sid}", flush=True)
        return handler

def close_handler_from_webhook(call_sid: str, reason: str):
    """
    🔥 SESSION LIFECYCLE: Close handler from webhook (call_status, stream_ended)
    
    This is called by Twilio webhooks when call ends externally.
    Returns True if handler was found and closed, False otherwise.
    
    🔥 CRITICAL: Never throws exceptions - always returns gracefully to prevent webhook 500 errors
    """
    try:
        handler = _get_handler(call_sid)
        if handler and hasattr(handler, 'close_session'):
            _orig_print(f"🔥 [WEBHOOK_CLOSE] Triggering close_session from webhook: {reason} for {call_sid}", flush=True)
            handler.close_session(reason)
            return True
        else:
            # 🔥 This is normal during race conditions - webhook arrives after cleanup or before registration
            _orig_print(f"⚠️ [WEBHOOK_CLOSE] No handler found for {call_sid} (reason={reason})", flush=True)
            return False
    except Exception as e:
        # 🔥 CRITICAL: Log but don't propagate - webhooks must always return 200 OK
        _orig_print(f"❌ [WEBHOOK_CLOSE] Exception closing handler for {call_sid}: {e}", flush=True)
        import traceback
        _orig_print(f"[WEBHOOK_CLOSE] Traceback: {traceback.format_exc()}", flush=True)
        return False

def _create_dispatcher_callbacks(call_sid: str):
    """Create partial/final callbacks that route to the correct call's utterance"""
    def on_partial(text: str):
        utt = _get_utterance_state(call_sid)
        if utt:
            # 🔥 CRITICAL FIX: Save LONGEST partial only! Google STT sometimes sends shorter corrections
            with _registry_lock:
                current_best = utt.get("last_partial", "")
                if len(text) > len(current_best):
                    utt["last_partial"] = text
                    if DEBUG: logger.debug(f"🟡 [PARTIAL] BEST updated: '{text}' ({len(text)} chars) for {call_sid[:8]}...")
                else:
                    if DEBUG: logger.debug(f"🟡 [PARTIAL] IGNORED (shorter): '{text}' ({len(text)} chars) vs '{current_best}' ({len(current_best)} chars)")
            
            # ⚡ BUILD 114: Early Finalization - if partial is strong enough, trigger final AND continue
            # This saves 400-600ms by triggering final event early
            if text and len(text) > 15 and text.rstrip().endswith(('.', '?', '!')):
                if DEBUG: logger.debug(f"⚡ [EARLY_FINALIZE] Strong partial detected: '{text}' → triggering final event")
                # Trigger final event (but continue to call partial callback)
                final_event = utt.get("final_received")
                if final_event:
                    final_event.set()
            
            # Call the utterance's partial callback
            cb = utt.get("partial_cb")
            if cb:
                try:
                    cb(text)
                except Exception as e:
                    logger.error(f"⚠️ Partial callback error for {call_sid[:8]}...: {e}")
    
    def on_final(text: str):
        utt = _get_utterance_state(call_sid)
        if utt:
            buf = utt.get("final_buf")
            if buf is not None:
                buf.append(text)
                if DEBUG: logger.debug(f"✅ [FINAL] '{text}' received for {call_sid[:8]}... (utterance: {utt.get('id', '???')})")
                
                # ⚡ Signal that final has arrived!
                final_event = utt.get("final_received")
                if final_event:
                    final_event.set()
                    if DEBUG: logger.debug(f"📢 [FINAL_EVENT] Set for {call_sid[:8]}...")
    
    return on_partial, on_final

def _cleanup_stale_sessions():
    """Cleanup sessions that haven't received audio for >2 minutes (edge case protection)"""
    STALE_TIMEOUT = 120  # 2 minutes
    current_time = time.time()
    
    with _registry_lock:
        stale_call_sids = [
            call_sid for call_sid, item in _sessions_registry.items()
            if current_time - item["ts"] > STALE_TIMEOUT
        ]
    
    for call_sid in stale_call_sids:
        if DEBUG: logger.debug(f"🧹 [REAPER] Cleaning stale session: {call_sid[:8]}... (inactive for >{STALE_TIMEOUT}s)")
        _close_session(call_sid)

# Start session reaper thread
def _start_session_reaper():
    """Background thread that cleans up stale sessions every 60s"""
    def reaper_loop():
        while True:
            time.sleep(60)  # Check every 60 seconds
            try:
                _cleanup_stale_sessions()
            except Exception as e:
                logger.error(f"⚠️ [REAPER] Error during cleanup: {e}")
    
    reaper_thread = threading.Thread(target=reaper_loop, daemon=True, name="SessionReaper")
    reaper_thread.start()
    logger.info("🧹 [REAPER] Session cleanup thread started")

# Start reaper on module load (only if streaming enabled)
if USE_STREAMING_STT:
    _start_session_reaper()

# Override print to always flush (CRITICAL for logs visibility)
_original_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _original_print(*args, **kwargs)
builtins.print = print

# WebSocket ConnectionClosed exception (works with both Flask-Sock and Starlette)
class ConnectionClosed(Exception):
    """WebSocket connection closed"""
    pass

from server.stream_state import stream_registry

SR = 8000

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 325: OPTIMAL HEBREW THRESHOLDS - Hardcoded for best performance
# Trust OpenAI's Realtime API VAD - minimal local filtering
# ═══════════════════════════════════════════════════════════════════════════════

# SPEECH DETECTION - Use values from centralized AUDIO_CONFIG
MIN_UTT_SEC = 0.35              # Minimum utterance: 350ms - allows short Hebrew words like "כן", "לא"
MAX_UTT_SEC = 12.0              # Maximum utterance: 12s - enough for detailed Hebrew descriptions
VAD_RMS = AUDIO_CONFIG.get("vad_rms", 60)                       # From AUDIO_CONFIG
RMS_SILENCE_THRESHOLD = AUDIO_CONFIG.get("rms_silence_threshold", 30)  # From AUDIO_CONFIG
MIN_SPEECH_RMS = AUDIO_CONFIG.get("min_speech_rms", 40)        # From AUDIO_CONFIG
MIN_SPEECH_DURATION_MS = 350   # Minimum speech duration: 350ms - short Hebrew confirmations

# 🎯 MASTER DIRECTIVE 3.1: VAD - Voice Detection
# Continuous voice frames to prevent short noise spikes
# Reduced from 400ms to 240ms to avoid missing short valid utterances like "כן", "לא"
# 12 frames @ 20ms/frame = 240ms (balances noise rejection with responsiveness)
MIN_CONSECUTIVE_VOICE_FRAMES = max(0, NOISE_GATE_MIN_FRAMES) if not SIMPLE_MODE else 12  # 12 frames = 240ms minimum

# TIMING - Fast Hebrew response
POST_AI_COOLDOWN_MS = 800      # Cooldown after AI speaks: 800ms - fast response
NOISE_HOLD_MS = 150            # Noise hold: 150ms - short grace period
VAD_HANGOVER_MS = 150          # VAD hangover: 150ms - quick transition
RESP_MIN_DELAY_MS = 50         # Min response delay: 50ms - fast
RESP_MAX_DELAY_MS = 120        # Max response delay: 120ms - responsive
REPLY_REFRACTORY_MS = 1100     # Refractory period: 1100ms - prevents loops

# BARGE-IN configuration imported from server.config.calls
# See server/config/calls.py for BARGE_IN_VOICE_FRAMES and BARGE_IN_DEBOUNCE_MS values

# TX BURST PROTECTION - Prevent chipmunk effect from audio bursts
# ✅ P0-1: Constants for queue backlog management
TX_BACKLOG_THRESHOLD_FRAMES = 100  # 100 frames = 2 seconds of audio - trigger burst protection
TX_BACKLOG_TARGET_FRAMES = 50      # Target queue size after dropping frames
TX_BACKLOG_MAX_DROP_FRAMES = 25    # Maximum frames to drop in one burst protection cycle

# STT MERGING - Hebrew segment handling
STT_MERGE_WINDOW_MS = 600      # Merge window: 600ms - balances speed and accuracy
THINKING_HINT_MS = 0           # No "thinking" message - immediate response
THINKING_TEXT_HE = ""          # No thinking text
DEDUP_WINDOW_SEC = 8           # Deduplication window: 8 seconds
LLM_NATURAL_STYLE = True       # Natural Hebrew responses

# ═══════════════════════════════════════════════════════════════════════════════

# 🎯 STT GUARD: Use values from centralized AUDIO_CONFIG
# These parameters ensure we only accept real speech, not silence/noise
MIN_UTTERANCE_MS = 200      # Minimum utterance duration (200ms allows short valid responses like "כן", "לא")
MIN_RMS_DELTA = AUDIO_CONFIG.get("min_rms_delta", 5.0)  # From AUDIO_CONFIG - microphone sensitivity
MIN_WORD_COUNT = 2          # Minimum word count to accept (prevents single-word hallucinations like "היי", "מה")
ECHO_SUPPRESSION_WINDOW_MS = 800  # 🔥 FIX ISSUE 5: Relaxed from 200ms (was too aggressive with jitter)
ECHO_WINDOW_MS = 350        # Time window after AI audio where user speech is likely echo (for speech_started)
ECHO_HIGH_RMS_THRESHOLD = 150.0  # RMS threshold to allow speech through echo window (real user is loud)

# 🔥 BUILD 341: Minimum transcription length to mark user_has_spoken
# Requirement: At least 2 characters after cleanup (not just whitespace/single char)
# This prevents state progression on meaningless single-character transcriptions
MIN_TRANSCRIPTION_LENGTH = 2

# 🔥 SIMPLE_MODE: Early user_has_spoken detection threshold
# 1.5x multiplier provides confident speech detection: 
# - Below 1x: Too sensitive, may trigger on noise
# - At 1x: Matches normal validation, defeats purpose of early detection
# - At 1.5x: Clear speech signal, confident real user input (not echo/noise)
# - Above 2x: Too strict, may miss quiet speakers
SIMPLE_MODE_RMS_MULTIPLIER = 1.5  # Sweet spot: confident speech without missing quiet users

# Valid short Hebrew phrases that should ALWAYS pass (even if 1 word when RMS is high)
VALID_SHORT_HEBREW_PHRASES = {
    "כן", "לא", "רגע", "שניה", "שנייה", "תן לי", "אני פה", "שומע",
    "טוב", "בסדר", "תודה", "סליחה", "יופי", "נכון", "מעולה", "בדיוק",
    "יאללה", "סבבה", "אוקיי", "אה", "אהה", "מה", "איפה", "מתי", "למה",
    "איך", "כמה", "מי", "איזה", "זה", "אני", "היי", "הלו", "שלום", "ביי"
}

# 🎯 MASTER DIRECTIVE 3.2: FILLER DETECTION - Hebrew filler words that should NOT trigger bot responses
# These are thinking sounds, not real speech. Drop silently at STT level.
HEBREW_FILLER_WORDS = {
    "אמ", "אם", "אממ", "אמממ", 
    "אה", "אהה", "אההה", "אההההה",
    "הממ", "אהם", "אהממ", "ממ", "הם"
}

# 🔧 GOODBYE DETECTION: Shared patterns for ignore list and greeting detection
GOODBYE_IGNORE_PHRASES = ["היי כבי", "היי ביי", "הי כבי", "הי ביי"]
GOODBYE_GREETING_WORDS = ["היי", "הי", "שלום וברכה", "בוקר טוב", "צהריים טובים", "ערב טוב"]

# 🔧 GOODBYE DETECTION: Clear goodbye words shared across functions
CLEAR_GOODBYE_WORDS = [
    "להתראות", "ביי", "bye", "bye bye", "goodbye",
    "יאללה ביי", "יאללה להתראות",
    "ביי יום טוב"  # "bye, good day"
]

# 🔴 CRITICAL — Real Hangup (transcript-only, closing-sentence only)
# -----------------------------------------------------------------------------
# Goal: When user/bot ends the call for real, do REAL hangup (Twilio REST),
# not just "say bye".
#
# Rules:
# - Decision is based ONLY on transcript text (STT final / input_text / audio transcript).
# - Trigger ONLY if the utterance is a closing sentence (no extra content).
# - Anti-accidental rule: "ביי ... רגע" / "ביי אבל ..." → do NOT hangup, ask clarification once.
REAL_HANGUP_USER_PHRASES = [
    "ביי",
    "ביי ביי",
    "להתראות",
    "יאללה ביי",
    "סיימנו",
    "תודה ביי",
    "אין צורך",
    "ניתוק",
    "סגור",
]

REAL_HANGUP_BOT_PHRASES = [
    "ביי",
    "להתראות",
    "תודה ביי",
    "תודה להתראות",
    "יום טוב ביי",
    "בסדר גמור להתראות",
]

REAL_HANGUP_CONTINUATION_MARKERS = {"אבל", "רגע"}
_REAL_HANGUP_NIKUD_RE = re.compile(r"[\u0591-\u05C7]")
_REAL_HANGUP_PUNCT_RE = re.compile(r"[\"'“”‘’`´~!?.…,;:\(\)\[\]\{\}\-–—_/\\|]+")


def _normalize_for_real_hangup(text: str) -> str:
    """
    Normalize text for hangup intent matching:
    - NFKC normalize
    - Remove Hebrew diacritics (nikud)
    - Strip punctuation into spaces
    - Collapse whitespace
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _REAL_HANGUP_NIKUD_RE.sub("", t)
    t = _REAL_HANGUP_PUNCT_RE.sub(" ", t)
    t = " ".join(t.split())
    return t.strip()


def _compile_phrase_tuples(phrases: list[str]) -> list[tuple[str, ...]]:
    tuples: list[tuple[str, ...]] = []
    for p in phrases:
        w = tuple(_normalize_for_real_hangup(p).split())
        if w:
            tuples.append(w)
    # Prefer longest matches first (e.g., "ביי ביי" before "ביי")
    tuples.sort(key=len, reverse=True)
    return tuples


_REAL_HANGUP_USER_TUPLES = _compile_phrase_tuples(REAL_HANGUP_USER_PHRASES)
_REAL_HANGUP_BOT_TUPLES = _compile_phrase_tuples(REAL_HANGUP_BOT_PHRASES)


def _is_closing_sentence_only(text: str, phrase_tuples: list[tuple[str, ...]]) -> bool:
    """
    True only if the utterance consists solely of 1+ allowed phrases (optionally combined),
    e.g. "ביי", "ביי להתראות", "תודה ביי להתראות".
    """
    norm = _normalize_for_real_hangup(text)
    if not norm:
        return False
    words = norm.split()
    i = 0
    matched_any = False
    while i < len(words):
        matched = False
        for phrase in phrase_tuples:
            n = len(phrase)
            if n and i + n <= len(words) and tuple(words[i : i + n]) == phrase:
                matched_any = True
                i += n
                matched = True
                break
        if not matched:
            return False
    return matched_any


def _is_ambiguous_goodbye(text: str) -> bool:
    """
    Detect "goodbye but continuing" patterns like:
    - "ביי אבל רגע"
    - "ביי... רגע"
    """
    norm = _normalize_for_real_hangup(text)
    if not norm:
        return False
    words = norm.split()
    if not words:
        return False
    starts_with_goodbye = words[0] in {"ביי", "להתראות"}
    if not starts_with_goodbye:
        return False
    # If there's a continuation marker anywhere after the goodbye opener, treat as ambiguous.
    return any(w in REAL_HANGUP_CONTINUATION_MARKERS for w in words[1:])

# 🔧 GOODBYE DETECTION: Thresholds for polite ending detection
# Short utterances (≤3 words) with polite phrases are likely goodbyes (e.g., "תודה רבה")
# Longer utterances require phrase to be ≥50% of content to avoid false positives
GOODBYE_SHORT_UTTERANCE_MAX_WORDS = 3  # Max words for "short utterance" classification
GOODBYE_PHRASE_MIN_PERCENTAGE = 0.5  # Minimum 50% of utterance must be the goodbye phrase

def is_valid_transcript(text: str) -> bool:
    """
    ✅ NO FILTERS: Always accept transcripts (except completely empty)
    
    If transcript arrives → it's real input. Process it.
    No filler filtering, no length filtering.
    
    Args:
        text: Transcribed text from STT
        
    Returns:
        True if any text, False only if completely empty
    """
    # Only reject completely empty
    if not text or not text.strip():
        return False
    
    # Everything else is accepted - NO FILTERS
    # No filler check, no length check
    return True

def should_accept_realtime_utterance(stt_text: str, utterance_ms: float, 
                                     rms_snapshot: float, noise_floor: float,
                                     ai_speaking: bool = False, 
                                     last_ai_audio_start_ms: float = 0,
                                     last_hallucination: str = "") -> bool:
    """
    ✅ NO FILTERS: Always accept transcripts from OpenAI
    
    If transcript arrives from speech_started or transcription.completed → it's real input.
    Process it and generate response. No filtering.
    
    Args:
        stt_text: The transcribed text from OpenAI
        utterance_ms: Duration (unused - kept for signature compatibility)
        rms_snapshot: RMS level (unused - kept for signature compatibility)
        noise_floor: Baseline (unused - kept for signature compatibility)
        ai_speaking: Whether AI speaking (unused - kept for signature compatibility)
        last_ai_audio_start_ms: Time since AI audio (unused - kept for signature compatibility)
        last_hallucination: Last rejection (unused - kept for signature compatibility)
        
    Returns:
        True if there's any text, False only if empty
    """
    # Only reject completely empty text
    if not stt_text or not stt_text.strip():
        return False
    
    # Everything else is accepted - NO FILTERS
    # No duration check, no RMS check, no hallucination check, no word count check
    return True

# מכונת מצבים
STATE_LISTEN = "LISTENING"
STATE_THINK  = "THINKING"
STATE_SPEAK  = "SPEAKING"

# 🔥 BUILD 170.4: HEBREW DICTIONARY - Normalize common STT mistakes
HEBREW_NORMALIZATION = {
    # Common misrecognitions - numbers
    "אחת": "אחד",
    "שתים": "שתיים",
    "שלש": "שלוש",
    "ארבה": "ארבע",
    "חמישה": "חמש",
    "שישה": "שש",
    "שבעה": "שבע",
    "שמנה": "שמונה",
    "תשעה": "תשע",
    "עשרה": "עשר",
    # Common greeting variations
    "שלומ": "שלום",
    "שאלום": "שלום",
    "שלים": "שלום",
    "היי יי": "היי",
    "הלוו": "הלו",
    "הלוא": "הלו",
    # Confirmation words
    "קן": "כן",
    "קאן": "כן",
    "יאן": "כן",
    "נקון": "נכון",
    "נכונ": "נכון",
    "בסדור": "בסדר",
    "בסדור גמור": "בסדר גמור",
    "ביידיוק": "בדיוק",
    "בידיוק": "בדיוק",
    "יופיי": "יופי",
    "יאפי": "יופי",
    # Negation
    "לאא": "לא",
    "לוא": "לא",
    # Common words
    "טודה": "תודה",
    "טודא": "תודה",
    "תודא": "תודה",
    "רגאע": "רגע",
    "רגאה": "רגע",
    "שניה": "שנייה",
    "שניא": "שנייה",
    "אוקי": "אוקיי",
    "או קי": "אוקיי",
    "אוו קי": "אוקיי",
    "סבאבה": "סבבה",
    "סאבאבה": "סבבה",
    "יאללה": "יאללה",  # Keep as is
    "יאלא": "יאללה",
    "יאלאה": "יאללה",
    # Request words
    "בבקשא": "בבקשה",
    "בבאקשה": "בבקשה",
    "בואקשה": "בבקשה",
    # Goodbye
    "ביי יי": "ביי",
    "ביייי": "ביי",
    "להיתראות": "להתראות",
    "להתאאות": "להתראות",
    # Question words
    "למא": "למה",
    "לאמה": "למה",
    "מאתי": "מתי",
    "מאתיי": "מתי",
    "אייפה": "איפה",
    "אייפא": "איפה",
    "כאמה": "כמה",
    "קאמה": "כמה",
    "מאה": "מה",
    # Service-related
    "פאגישה": "פגישה",
    "פגישא": "פגישה",
    "טורר": "תור",
    "תאור": "תור",
    # Time-related
    "דאקה": "דקה",
    "דאקות": "דקות",
    "שאעה": "שעה",
    "שאעות": "שעות",
    "יאום": "יום",
    "יאומים": "ימים",
    # Days of week
    "ראאשון": "ראשון",
    "שאני": "שני",
    "שאלישי": "שלישי",
    "רביאעי": "רביעי",
    "חאמישי": "חמישי",
    "שיאשי": "שישי",
    "שאבת": "שבת",
    # Names - common variations
    "משא": "משה",
    "יאוסי": "יוסי",
    "יאוסף": "יוסף",
    "דאני": "דני",
    "דאניאל": "דניאל",
    "מיכאאל": "מיכאל",
    "אאלי": "אלי",
    "שאי": "שי",
    # Cities
    "תאל אביב": "תל אביב",
    "תאל-אביב": "תל אביב",
    "יארושלים": "ירושלים",
    "יארושאלים": "ירושלים",
    "חאיפה": "חיפה",
    "באר שאבע": "באר שבע",
    "באאר שבע": "באר שבע",
    "ראמת גן": "רמת גן",
    "ראמאת גן": "רמת גן",
    "פאתח תקווה": "פתח תקווה",
    "פאתח תיקווה": "פתח תקווה",
    "נאתניה": "נתניה",
    "נאתאניה": "נתניה",
    "אאשדוד": "אשדוד",
    "אאשקלון": "אשקלון",
    "חאדרה": "חדרה",
    "קאריות": "קריות",
}

def normalize_hebrew_text(text: str) -> str:
    """
    BUILD 170.4: Normalize Hebrew STT output using dictionary
    """
    if not text:
        return text
    
    result = text
    for wrong, correct in HEBREW_NORMALIZATION.items():
        # Case insensitive replace (Hebrew doesn't have case, but for mixed text)
        if wrong in result.lower():
            result = result.replace(wrong, correct)
    
    return result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 VOICEMAIL DETECTION: Helper functions for detecting answering machines
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Module-level constants for performance (avoid recreation on every call)
_VOICEMAIL_KEYWORDS = [
    "תא קולי",
    "משיבון קולי",
    "תא הודעות",
    "תאה קולי",  # Common STT error
    "משיבון",
    "תא קול",
    "נא להשאיר הודעה",  # "please leave a message"
    "השאירו הודעה",      # "leave a message"
    "השאר הודעה",        # "leave a message" (singular)
    "להשאיר הודעות",     # "to leave messages"
]

_HEBREW_DIGIT_WORDS = [
    "אפס", "אחד", "שתיים", "שלוש", "ארבע", "חמש", "שש", "שבע", "שמונה", "תשע",
    "עשר", "עשרה", "אחת", "שניים", "שתים"
]

# Compile regex patterns once at module load
_PHONE_PATTERN_MOBILE = re.compile(r'05[0-9]{8}')
_PHONE_PATTERN_INTL = re.compile(r'\+?972[0-9]{7,9}')
_PHONE_PATTERN_LANDLINE = re.compile(r'0[2-9][0-9]{7}')
_PHONE_PATTERN_DIGITS = re.compile(r'[0-9]{5,}')

# Translation table for string optimization (created once at module load)
_PHONE_TRANS_TABLE = str.maketrans('', '', ' -.,')


def _has_voicemail_keyword(text: str) -> bool:
    """
    Check if text contains Hebrew voicemail keywords.
    
    Detects phrases like:
    - "תא קולי" (voice mailbox)
    - "משיבון קולי" (answering machine)
    - "תא הודעות" (message box)
    
    Args:
        text: The transcript text to check
        
    Returns:
        True if voicemail keywords detected, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _VOICEMAIL_KEYWORDS)

def _has_phone(text: str) -> bool:
    """
    Check if text contains Israeli phone number being read aloud.
    
    Detects patterns like:
    - "05X..." (Israeli mobile)
    - "+972..." (International format)
    - "972..." (Without plus)
    - Numbers read with spaces: "0 5 2 1 2 3 4 5 6 7"
    - Partial numbers (5+ consecutive digits)
    - Hebrew digit words being read
    
    Args:
        text: The transcript text to check
        
    Returns:
        True if phone number pattern detected, False otherwise
    """
    if not text:
        return False
    
    # Optimize: Use pre-created translation table for faster character removal
    text_normalized = text.translate(_PHONE_TRANS_TABLE)
    
    # Quick checks using pre-compiled regex patterns
    if _PHONE_PATTERN_MOBILE.search(text_normalized):
        return True
    
    if _PHONE_PATTERN_INTL.search(text_normalized):
        return True
    
    if _PHONE_PATTERN_LANDLINE.search(text_normalized):
        return True
    
    if _PHONE_PATTERN_DIGITS.search(text_normalized):
        return True
    
    # Check for Hebrew digit words (split into words for exact matching)
    text_lower = text.lower()
    words = text_lower.split()
    digit_count = sum(1 for word in words if word in _HEBREW_DIGIT_WORDS)
    if digit_count >= 4:  # If 4+ digit words, likely reading a number
        return True
    
    return False


# 🔥 PERFORMANCE OPTIMIZATION: CallContext Class
# Immutable cache of all DB data needed for a call
# Loaded once at start, eliminates 17 queries during call
class CallContext:
    """
    Immutable cache of all DB data needed for a call.
    Loaded once at call start via single JOIN query, used throughout call.
    
    PERFORMANCE: Eliminates ~17 DB queries (~200ms) during call.
    """
    def __init__(self, call_log, lead, business, settings, outbound_job=None):
        # CallLog data
        self.call_sid = call_log.call_sid if call_log else None
        self.call_log_id = call_log.id if call_log else None
        self.lead_id = call_log.lead_id if call_log else None
        self.customer_name = call_log.customer_name if call_log else None
        
        # Lead data
        self.lead_full_name = lead.full_name if lead else None
        self.lead_first_name = lead.first_name if lead else None
        self.lead_phone = lead.phone_e164 if lead else None
        # 🔥 FIX: Use defensive getattr - Lead model doesn't have customer_name field
        # Try first_name (most common), then full_name, with None fallback
        self.lead_customer_name = (
            getattr(lead, "first_name", None) or 
            getattr(lead, "full_name", None)
        ) if lead else None
        self.lead_gender = getattr(lead, 'gender', None) if lead else None
        self.lead_tenant_id = lead.tenant_id if lead else None
        
        # Business data
        self.business_id = business.id if business else None
        self.business_name = business.name if business else None
        self.business_voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) if business else DEFAULT_VOICE  # 🎤 Voice Library
        
        # Settings data
        self.opening_hours = settings.opening_hours_json if settings else None
        self.working_hours = settings.working_hours if settings else None
        
        # Outbound data
        self.outbound_lead_name = outbound_job.lead_name if outbound_job else None
        self.outbound_template_id = outbound_job.template_id if outbound_job else None
        
        # Derived/cached values
        self._first_name_cache = None
        self._extraction_attempted = False
    
    def get_first_name(self):
        """Extract and cache first name from full name"""
        if self._first_name_cache is None and not self._extraction_attempted:
            self._extraction_attempted = True
            if self.lead_full_name:
                try:
                    from server.services.realtime_prompt_builder import extract_first_name
                    self._first_name_cache = extract_first_name(self.lead_full_name)
                except Exception as e:
                    logger.warning(f"[CALL_CACHE] Failed to extract first name: {e}")
        return self._first_name_cache or self.lead_first_name or self.lead_customer_name
    
    def get_customer_name(self):
        """Get best available customer name"""
        return self.customer_name or self.lead_customer_name or self.lead_full_name or self.outbound_lead_name


class MediaStreamHandler:
    """
    WebSocket handler for Twilio Media Streams + OpenAI Realtime API integration.
    
    🎯 SSOT RESPONSIBILITIES:
    ✅ OWNER: Real-time conversation storage (ConversationTurn)
    ✅ OWNER: Audio streaming and turn-taking logic
    ✅ READER: CallLog status (reads only, never updates)
    ❌ NEVER: Update CallLog.status (webhooks own this)
    ❌ NEVER: Download recordings (recording_service owns this)
    
    This handler manages:
    - Audio I/O (Twilio <-> OpenAI)
    - Conversation turns (user/assistant messages)
    - Barge-in detection and handling
    - Greeting/hangup logic
    
    Does NOT manage:
    - Call status transitions (webhooks do this)
    - Recording downloads (recording_service does this)
    - Post-call transcription (workers do this)
    """
    def __init__(self, ws):
        self.ws = ws
        self.mode = "AI"  # תמיד במצב AI
        
        # 🔥 CRITICAL FIX: Initialize audio counters FIRST (before any threads/queues)
        # These counters MUST exist for every call direction (inbound/outbound)
        # Must be initialized before thread objects created to prevent race conditions
        self.realtime_audio_in_chunks = 0   # Count of audio chunks received from Twilio
        self.realtime_audio_out_chunks = 0  # Count of audio chunks sent to Twilio
        
        # 🔥 SESSION LIFECYCLE GUARD: Atomic close protection
        self.closed = False
        self.close_lock = threading.Lock()
        self.close_reason = None
        
        # 🔥 FIX: Guard against double-close websocket error
        self._ws_closed = False
        
        # 🔧 תאימות WebSocket - EventLet vs RFC6455 עם טיפול שגיאות
        if hasattr(ws, 'send'):
            self._ws_send_method = ws.send
        else:
            # אם אין send, נסה send_text או כל שיטה אחרת
            self._ws_send_method = getattr(ws, 'send_text', lambda x: print(f"❌ No send method: {x}"))
        
        # 🛡️ Safe WebSocket send wrapper with connection health
        self.ws_connection_failed = False
        self.failed_send_count = 0
        
        # 🎯 TX PERFORMANCE: Track slow sends for diagnostics
        self._slow_send_count = 0
        self._last_slow_send_warning = 0.0
        
        def _safe_ws_send(data):
            if self.ws_connection_failed:
                return False  # Don't spam when connection is dead
                
            try:
                # 🎯 VERIFY TX: Measure send time to detect blocking (requirement from issue)
                send_start = time.perf_counter()
                self._ws_send_method(data)
                send_duration_ms = (time.perf_counter() - send_start) * 1000
                
                # ⚠️ Warn if send takes >5ms (indicates blocking/backpressure)
                if send_duration_ms > 5.0:
                    self._slow_send_count += 1
                    now = time.time()
                    # Log warning every 5 seconds (throttled to avoid spam)
                    if now - self._last_slow_send_warning > 5.0:
                        _orig_print(f"⚠️ [TX_SLOW] WebSocket send took {send_duration_ms:.1f}ms (>5ms threshold) - potential backpressure (count={self._slow_send_count})", flush=True)
                        self._last_slow_send_warning = now
                
                self.failed_send_count = 0  # Reset on success
                return True
            except Exception as e:
                self.failed_send_count += 1
                if self.failed_send_count <= 3:  # Only log first 3 errors
                    logger.error(f"❌ WebSocket send error #{self.failed_send_count}: {e}")
                
                if self.failed_send_count >= 10:  # Increased threshold - After 10 failures, mark as dead
                    self.ws_connection_failed = True
                    logger.error(f"🚨 WebSocket connection marked as FAILED after {self.failed_send_count} attempts")
                
                return False
        
        self._ws_send = _safe_ws_send
        self.stream_sid = None
        self.call_sid = None  # PATCH 3: For watchdog connection
        self.rx = 0
        self.tx = 0
        
        # 🎯 פתרון פשוט ויעיל לניהול תורות
        self.buf = bytearray()
        self.last_rx = None
        self.speaking = False           # האם הבוט מדבר כרגע
        self.processing = False         # האם מעבד מבע כרגע
        self.conversation_id = 0        # מונה שיחות למניעת כפילויות
        self.last_processing_id = -1    # מזהה העיבוד האחרון
        self.response_timeout = None    # זמן תגובה מקסימלי
        
        # דה-דופליקציה מתקדמת עם hash
        self.last_user_hash = None
        self.last_user_hash_ts = 0.0
        self.last_reply_hash = None
        self.introduced = False
        self.response_history = []       # היסטוריית תגובות
        self.last_tts_end_ts = 0.0
        self.voice_in_row = 0
        self.greeting_sent = False
        self.user_has_spoken = False  # Track if user has spoken at least once
        self.is_playing_greeting = False  # True only while greeting audio is playing
        self.state = STATE_LISTEN        # מצב נוכחי
        
        # ✅ תיקון קריטי: מעקב נפרד אחר קול ושקט
        self.last_voice_ts = 0.0         # זמן הקול האחרון - לחישוב דממה אמיתי
        # 🔥 BUILD 325: RELAXED thresholds - trust OpenAI VAD more
        self.noise_floor = 50.0          # Starting baseline (will calibrate)
        self.vad_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 325: Uses MIN_SPEECH_RMS=60 - allow quiet speech
        self.is_calibrated = False       # האם כוילרנו את רמת הרעש
        self.calibration_frames = 0      # מונה פריימים לכיול
        
        # 🔥 BUILD 171: CONSECUTIVE FRAME TRACKING - Prevent noise spikes from triggering transcription
        self._consecutive_voice_frames = 0  # Count of consecutive frames above RMS threshold
        self._ai_finished_speaking_ts = 0.0  # When AI finished speaking (for cooldown)
        self.mark_pending = False        # האם ממתינים לסימון TTS
        self.mark_sent_ts = 0.0          # זמן שליחת סימון
        
        # הגנות Watchdog
        self.processing_start_ts = 0.0   # תחילת עיבוד
        self.speaking_start_ts = 0.0     # תחילת דיבור
        
        # ⚡ BUILD 109: Smart barge-in - disable for long responses
        self.long_response = False       # האם התשובה ארוכה (>20 מילים)
        
        # ✅ BUILD 117: WebSocket Keepalive with more frequent pings
        self.last_keepalive_ts = 0.0     # זמן keepalive אחרון
        self.keepalive_interval = 10.0   # ✅ שלח כל 10 שניות (was 18s) - prevents timeouts
        self.heartbeat_counter = 0       # מונה heartbeat
        
        # ⚡ BUILD 116: Enhanced telemetry - track every stage
        self.t0_connected = 0.0          # [T0] WebSocket connected
        self.t1_greeting_start = 0.0     # [T1] Greeting started
        self.t2_greeting_end = 0.0       # [T2] Greeting last frame sent
        self.s1_stream_opened = 0.0      # [S1] STT stream opened
        self.s2_first_partial = 0.0      # [S2] First partial received
        self.s3_final = 0.0              # [S3] Final text received
        self.a1_ai_start = 0.0           # [A1] AI processing started
        self.a2_ai_done = 0.0            # [A2] AI response ready
        self.v1_tts_start = 0.0          # [V1] TTS synthesis started
        self.v2_tts_done = 0.0           # [V2] TTS synthesis completed
        self.tx_first_frame = 0.0        # [TX] First reply frame sent
        
        # TX Queue for smooth audio transmission
        # 🔥 BARGE-IN FIX: Optimal size for responsive barge-in
        # ✅ P0 FIX + AUDIO BACKPRESSURE FIX: Increased queue size to prevent drops
        # 400 frames = 8s buffer - prevents mid-sentence audio cutting
        # OpenAI sends audio in bursts, larger queue prevents drops while TX catches up
        # Combined with backpressure (blocking put), this eliminates speech cuts
        self.tx_q = queue.Queue(maxsize=400)  # 400 frames = 8s buffer
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._last_overflow_log = 0.0  # For throttled logging
        self._audio_gap_recovery_active = False  # 🔥 BUILD 181: Gap recovery state
        
        # ═══════════════════════════════════════════════════════════════════════════
        # 🎯 TASK 0.1: Log AUDIO_CONFIG at startup (Master QA - Single Source of Truth)
        # ═══════════════════════════════════════════════════════════════════════════
        _orig_print(f"[AUDIO_MODE] simple_mode={AUDIO_CONFIG['simple_mode']}, "
                   f"audio_guard_enabled={AUDIO_CONFIG['audio_guard_enabled']}, "
                   f"music_mode_enabled={AUDIO_CONFIG['music_mode_enabled']}, "
                   f"noise_gate_min_frames={AUDIO_CONFIG['noise_gate_min_frames']}, "
                   f"frame_pacing_ms={AUDIO_CONFIG['frame_pacing_ms']}, "
                   f"sample_rate=8000, encoding=pcmu", flush=True)
        
        logger.info("🎯 AI CONVERSATION STARTED")
        
        # מאפיינים לזיהוי עסק
        self.business_id = None  # ✅ יזוהה דינמית לפי to_number
        self.phone_number = None
        
        # ⚡ DTMF phone collection (digits gathered from keypad)
        self.dtmf_buffer = ""  # Accumulated digits from phone keypad
        self.waiting_for_dtmf = False  # Are we waiting for phone input?
        self.dtmf_purpose = None  # What are we collecting? 'phone', etc.
        
        # היסטוריית שיחה למעקב אחר הקשר
        self.conversation_history = []  # רשימה של הודעות {'user': str, 'bot': str}
        self.turn_count = 0  # ⚡ Phase 2C: Track turns for first-turn optimization
        
        # 🚨 COST SAFETY: Rate limiting for OpenAI Realtime API
        self.last_session_update_time = 0
        self.last_transcription_request_time = 0
        self.transcription_failed_count = 0
        
        # ✅ CRITICAL: Track background threads for proper cleanup
        self.background_threads = []
        
        # ⚡ BUILD 115: Async executor for non-blocking fallback STT
        from concurrent.futures import ThreadPoolExecutor
        self.loop = None  # Will be set when needed
        self.exec = ThreadPoolExecutor(max_workers=1)  # Per-call executor
        self.events_q = None  # Will be created if async mode is used
        
        # 🚀 REALTIME API: Thread-safe queues and state for OpenAI Realtime mode
        # ✅ Use imported queue module (at top of file) - NOT queue_module alias
        import queue as _queue_module  # Local import to avoid shadowing
        self.realtime_audio_in_queue = _queue_module.Queue(maxsize=1000)  # Twilio → Realtime
        self.realtime_audio_out_queue = _queue_module.Queue(maxsize=1000)  # Realtime → Twilio
        self.realtime_text_input_queue = _queue_module.Queue(maxsize=10)  # DTMF/text → Realtime
        self.realtime_greeting_queue = _queue_module.Queue(maxsize=1)  # Greeting → Realtime
        self.realtime_stop_flag = False  # Signal to stop Realtime threads
        self.realtime_thread = None  # Thread running asyncio loop
        self.realtime_client = None  # 🔥 NEW: Store Realtime client for barge-in response.cancel
        
        # 🔥 Counters moved to top of __init__ (line ~1624) for race condition prevention
        
        # 🔥 NEW: Initialize backlog monitoring timestamps
        self._last_backlog_warning = 0.0  # For tx_q backlog warnings
        self._last_realtime_backlog_warning = 0.0  # For realtime_audio_out_queue backlog warnings
        
        # 🎯 PROBE 4: Queue Flow Probe tracking
        self._enq_counter = 0  # Frames enqueued to realtime_audio_out_queue
        self._enq_last_log_time = time.monotonic()
        
        # 🔥 BUILD 331: Usage guard tracking fields
        self._limit_exceeded = False
        self._limit_frames = 0
        self._limit_seconds = 0.0
        self._usage_guard_frames = 0
        self._usage_guard_seconds = 0.0
        self._usage_guard_limit_hit = False
        
        # 🎯 SMART BARGE-IN: Track AI speaking state and user interruption detection
        self.is_ai_speaking_event = threading.Event()  # Thread-safe flag for AI speaking state
        self.has_pending_ai_response = False  # Is AI response pending?
        self.last_ai_audio_ts = None  # Last time AI audio was received from Realtime
        self.ai_speaking_start_ts = None  # 🔥 FIX: When AI STARTED speaking (for grace period)
        self.last_user_turn_id = None  # Last user conversation item ID
        
        # 🚀 PARALLEL STARTUP: Event to signal business info is ready
        self.business_info_ready_event = threading.Event()  # Signal when DB query completes
        self.last_ai_turn_id = None  # Last AI conversation item ID
        self.active_response_id = None  # 🔥 Track active response ID for cancellation
        self.active_response_status = None  # 🔥 IDEMPOTENT CANCEL: Track response status ("in_progress" | "done" | "cancelled")
        self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Prevent double-cancel
        self._last_flushed_response_id = None  # 🔥 IDEMPOTENT CANCEL: Track last flushed response to prevent duplicate flushes
        self.min_ai_talk_guard_ms = 150  # 🔥 BUILD 164B: 150ms grace period
        self.barge_in_rms_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 170.3: RMS > 60 now (was 200) - better barge-in
        self.min_voice_duration_ms = MIN_SPEECH_DURATION_MS  # 🔥 BUILD 164B: 220ms continuous speech
        self.barge_in_min_ms = MIN_SPEECH_DURATION_MS  # 🔥 BUILD 164B: Match min_voice_duration_ms
        self.barge_in_cooldown_ms = 500  # 🔥 BUILD 164B: Standard cooldown
        self.last_barge_in_ts = None  # Last time barge-in was triggered
        self.current_user_voice_start_ts = None  # When current user voice started
        self.barge_in_voice_frames = 0  # 🎯 NEW: Count continuous voice frames for 180ms detection
        self.barge_in_enabled_after_greeting = False  # 🎯 FIX: Allow barge-in after greeting without forcing user_has_spoken
        self.barge_in_enabled = True  # 🔥 BARGE-IN: Always enabled by default (can be disabled during DTMF)
        self.barge_in_active = False  # 🔥 BARGE-IN FIX: Track if user is currently interrupting AI
        self.barge_in_stop_tx = False  # 🔥 NEW FIX: Flag to immediately stop TX loop from sending audio
        # 🔄 ADAPTIVE: Second confirmation for barge-in - require OpenAI speech_started confirmation
        self._openai_speech_started_confirmed = False  # Set on speech_started event, cleared after barge-in
        self._cancelled_response_ids = set()  # Track locally cancelled responses to ignore late deltas
        # ✅ NEW REQ 4: Add TTL tracking to prevent memory leak
        self._cancelled_response_timestamps = {}  # response_id -> timestamp when cancelled
        self._cancelled_response_max_age_sec = 60  # Clean up after 60 seconds
        self._cancelled_response_max_size = 100  # Cap at 100 entries
        
        # 🔥 CRITICAL: User speaking state - blocks response.create until speech complete
        # This is THE key to making barge-in actually listen (not just stop talking)
        self.user_speaking = False  # True from speech_started until speech_stopped+transcription.completed
        
        # ✅ P0 FIX: Track which response IDs we've sent cancel for (prevent duplicate cancel)
        self._cancel_sent_for_response_ids = set()  # Response IDs we've already sent cancel event for
        
        # 🧘 BUILD 345: Post-greeting breathing window state
        self._post_greeting_breath_window_sec = 3.5
        self._post_greeting_window_active = False
        self._post_greeting_window_started_at = None
        self._post_greeting_window_finished = False
        self._post_greeting_heard_user = False
        self._post_greeting_speech_cycle_complete = False
        
        # 🔥 FIX BUG 2: User turn timeout tracking (prevents stuck silence)
        self._last_user_audio_ts = None  # Last time user audio was received
        self._user_turn_timeout_ms = 1800  # 1.8s timeout for user turn finalization
        
        # 🔥 FIX BUG 3: Enhanced STT guard tracking
        self._last_hallucination = ""  # Last rejected hallucination (to prevent repeats)
        self._last_ai_audio_start_ts = None  # When AI audio started (for echo suppression)
        self._last_ai_audio_ts = None  # Track last AI audio sent (for ECHO_GUARD at speech_started level)
        
        # 🔥 BUILD 165: LOOP PREVENTION - Track consecutive AI responses without user input
        self._consecutive_ai_responses = 0
        self._max_consecutive_ai_responses = 5  # 🔥 BUILD 170.3: 5 (was 3) - less aggressive blocking
        self._last_user_transcript_ts = None
        self._loop_guard_engaged = False  # 🛑 When True, ALL AI audio is blocked
        self._last_user_speech_ts = time.time()  # 🔥 BUILD 170.3: Track when user last spoke for loop guard
        
        # 🔥 BUILD 169: STT SEGMENT MERGING - Debounce/merge multiple STT segments
        self._stt_merge_buffer = []  # List of (timestamp, text) for merging
        self._stt_last_segment_ts = 0  # Last STT segment timestamp
        
        # 🔥 BUILD 169: LOOP/MISHEARING PROTECTION - Track AI responses for repetition detection
        self._last_ai_responses = []  # Last 3-5 AI responses for similarity check
        self._mishearing_count = 0  # Count of consecutive misunderstandings
        
        # 🔥 BUILD 169: CALL SESSION LOGGING - Enhanced diagnostics
        self._call_session_id = None  # Unique session ID for logging
        
        # 🔥 BUILD 166: NOISE GATE BYPASS during active speech detection
        # When OpenAI Realtime detects speech_started, we MUST send all audio until speech_stopped
        # Otherwise OpenAI never gets enough audio to complete the utterance
        self._realtime_speech_active = False  # Set on speech_started, cleared on speech_stopped
        self._realtime_speech_started_ts = None  # When speech_started was received (for timeout)
        self._realtime_speech_timeout_sec = 30.0  # Auto-clear after 30 seconds if no speech_stopped (was 5s - too short!)
        
        # 🔥 BUILD 187: CANCELLED RESPONSE RECOVERY
        # When response is cancelled before any audio is sent (turn_detected), we need to trigger new response
        self._cancelled_response_needs_recovery = False
        self._cancelled_response_recovery_ts = 0
        self._cancelled_response_recovery_delay_sec = 0.25  # 🎯 P0-5: 250ms (200-300ms range)
        self._response_created_ts = 0  # 🔥 BUILD 187: Track when response was created for grace period
        self._cancel_retry_attempted = False  # 🎯 P0-5: Track if we already attempted retry (one retry only)
        
        # 🔥 BUILD 302: HARD BARGE-IN - When user speaks over AI, we hard-cancel everything
        # During barge-in, ALL audio gates are bypassed so user's full utterance goes through
        self.barge_in_active = False
        self._barge_in_started_ts = None  # When barge-in started (for timeout)
        
        # 🔥 GREETING PROTECT: Transcription confirmation flag for intelligent greeting protection
        self._greeting_needs_transcription_confirm = False  # Wait for transcription to confirm interruption

        # 🔴 FINAL CRITICAL FIX: Greeting lock (NO cancel/clear/turn-taking during greeting)
        # Active from greeting response.create(is_greeting=True) until response.done for THAT greeting response_id.
        self.greeting_lock_active = False
        self._greeting_lock_response_id = None
        
        # 🔥 FIX: CLOSING STATE TRACKING - Block audio input when call is closing
        self._closing_block_logged = False  # Track if we've logged the closing state message
        
        # 🎯 STT GUARD: Track utterance metadata for validation
        # Prevents hallucinated transcriptions during silence from triggering barge-in
        self._candidate_user_speaking = False  # Set on speech_started, validated on transcription.completed
        self._utterance_start_ts = None  # When speech_started was received (for duration calculation)
        self._utterance_start_rms = 0  # RMS level when speech started
        self._utterance_start_noise_floor = 50.0  # Noise floor when speech started
        
        # 🔥 BUILD 303: GREETING FLOW MANAGEMENT - Wait for user answer to greeting question
        # Ensures we don't skip to next question before processing user's response to greeting
        self.awaiting_greeting_answer = False  # True after greeting ends, until first utterance is processed
        self.first_post_greeting_utterance_handled = False  # True after we processed first utterance post-greeting
        self.user_utterance_count = 0  # Count total user utterances in this call (for patience with early STT)
        
        # 🔥 BUILD 303: NEGATIVE ANSWER DETECTION - Don't skip questions when user says "no"
        self.last_ai_question_type = None  # Track what AI asked: 'city', 'service', 'confirmation', etc.
        
        # ═══════════════════════════════════════════════════════════════════════════
        # 🔥 REALTIME STABILITY: Hardening timeouts and fallback mechanism
        # ═══════════════════════════════════════════════════════════════════════════
        self.realtime_failed = False  # Set True when Realtime can't connect/work - triggers fallback
        self._realtime_failure_reason = None  # Reason for failure (for logging)
        self._ws_open_ts = None  # Timestamp when WebSocket opened (for START timeout)
        self._openai_connect_attempts = 0  # Count OpenAI connection attempts
        self._greeting_audio_first_ts = None  # When first greeting audio delta was received
        self._greeting_audio_received = False  # True after at least one greeting audio delta
        self._greeting_audio_timeout_sec = 5.0  # 🔥 BUILD 350: Increased to 5s for outbound reliability
        
        # 🎯 FIX A: GREETING STATE - Only first response is greeting, not all responses!
        self.greeting_mode_active = False  # True only during FIRST response (real greeting)
        self.greeting_completed = False    # Becomes True after first response.audio.done
        
        # Timeout configuration (optimized for fast response + stability)
        # 🔥 FIX: Increased from 1.5s to 2.5s - some calls have START delay of 1.6-1.8s
        self._twilio_start_timeout_sec = 2.5  # Max wait for Twilio START event
        # NOTE: OpenAI connection uses client.connect() internal retry with 5s total timeout
        
        # Timing metrics for diagnostics
        self._metrics_openai_connect_ms = 0  # Time to connect to OpenAI
        self._metrics_first_greeting_audio_ms = 0  # Time from greeting trigger to first audio delta
        
        # 🔥 BUILD 303: SMART HANGUP - Always send goodbye before disconnect
        self.goodbye_message_sent = False  # Track if we sent a proper goodbye
        self.user_said_goodbye = False  # Track if USER said goodbye (separate from AI polite closing)
        self.last_user_goodbye_at = None  # Timestamp in milliseconds when user said goodbye (time.time() * 1000)

        # 🔴 CRITICAL: Real hangup duplicate guard + clarification guard (one-shot)
        self.hangup_requested = False  # One-shot: once True, never request hangup again
        self.hangup_clarification_asked = False  # One-shot: ask "רצית לסיים?" only once
        self._hangup_request_lock = threading.Lock()  # Atomic guard across async/tasks/threads
        
        # 🔥 BUILD 200: SINGLE PIPELINE LOCKDOWN - Stats for monitoring
        self._stats_audio_sent = 0  # Total audio chunks sent to OpenAI
        self._stats_audio_blocked = 0  # Total audio chunks blocked (greeting, etc.)
        self._stats_last_log_ts = 0  # Last time we logged pipeline status
        self._stats_log_interval_sec = 3.0  # Log every 3 seconds
        
        # 🔥 BUILD 320: AUDIO_GUARD - Lightweight filtering for noisy PSTN calls
        # 🔥 CRITICAL HOTFIX: Import MUSIC_MODE_ENABLED flag
        # Imports config values - see server/config/calls.py for tuning
        from server.config.calls import (
            AUDIO_GUARD_ENABLED, MUSIC_MODE_ENABLED, AUDIO_GUARD_INITIAL_NOISE_FLOOR,
            AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR, AUDIO_GUARD_MIN_ZCR_FOR_SPEECH,
            AUDIO_GUARD_MIN_RMS_DELTA, AUDIO_GUARD_MUSIC_ZCR_THRESHOLD,
            AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER, AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES
        )
        self._audio_guard_enabled = AUDIO_GUARD_ENABLED
        self._music_mode_enabled = MUSIC_MODE_ENABLED
        self._audio_guard_noise_floor = AUDIO_GUARD_INITIAL_NOISE_FLOOR
        self._audio_guard_speech_factor = AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR
        self._audio_guard_prev_rms = 0.0
        self._audio_guard_music_mode = False
        self._audio_guard_music_frames_counter = 0
        self._audio_guard_music_cooldown_frames = 0
        self._audio_guard_drop_count = 0  # Rate-limited logging
        self._audio_guard_last_summary_ts = 0.0  # For periodic summary logs
        logger.info(f"🔊 [AUDIO_GUARD] Enabled={AUDIO_GUARD_ENABLED}, MusicMode={MUSIC_MODE_ENABLED} (dynamic noise floor, speech gating, gap_recovery={'OFF' if AUDIO_GUARD_ENABLED else 'ON'})")
        
        # ⚡ STREAMING STT: Will be initialized after business identification (in "start" event)
        
        # 🎯 APPOINTMENT PARSER: DB-based deduplication via CallSession table
        self.call_sid = None  # Will be set from 'start' event
        self.last_nlp_processed_hash = None  # Hash of last processed conversation for NLP dedup
        self.last_nlp_hash_timestamp = 0  # Timestamp when hash was set (for TTL)
        self.nlp_processing_lock = threading.Lock()  # Prevent concurrent NLP runs
        self.nlp_is_processing = False  # 🛡️ BUILD 149: Flag to prevent concurrent NLP threads
        
        # 🔒 Response collision prevention - thread-safe optimistic lock
        self.response_pending_event = threading.Event()  # Thread-safe flag
        
        # 🔥 BUILD 172: CALL STATE MACHINE + CONFIG
        self.call_state = CallState.WARMUP  # Start in warmup, transition to ACTIVE after 800ms
        self.call_config: Optional[CallConfig] = None  # Loaded at call start
        self.call_start_time = time.time()  # Track call duration
        
        # 🔥 BUILD 172: SILENCE TIMER - Track user/AI speech for auto-hangup
        self._last_speech_time = time.time()  # Either user or AI speech
        self._silence_warning_count = 0  # How many "are you there?" warnings sent
        self._silence_check_task = None  # Background task for silence monitoring
        # ✅ HARD SILENCE WATCHDOG (telephony): hang up on real inactivity (not AI-dependent)
        # Updated on input_audio_buffer.speech_started and response.audio.delta.
        self._last_user_voice_started_ts = None
        self._hard_silence_hangup_sec = 20.0  # 🔥 AUTO-HANGUP: 20 seconds of continuous silence
        
        # 🔥 BUILD 338: COST TRACKING - Count response.create calls per call
        self._response_create_count = 0  # Track for cost debugging
        
        # 🔥 LATENCY THRESHOLD: Max acceptable time from session.updated to greeting
        # Used for monitoring and alerting on slow initialization  
        self.MAX_SESSION_TO_GREETING_MS = 100  # milliseconds
        
        # 🔥 PERFORMANCE OPTIMIZATION: Call Cache System
        # Load all DB data once at start, never query again during call
        # Eliminates 17 queries (~200ms) → 1 batch query (~15ms) = 92% improvement
        self.call_ctx = None  # CallContext object with all cached data
        self.call_ctx_loaded = False  # True after successful cache load
        self.db_write_queue = []  # Buffer for mid-call DB writes (flushed at end)
        self.in_live_call = False  # Guard: True during active call, prevents DB access
        self._last_response_create_ts = 0  # Track timing for double-create detection
        
        # 🔥 BUILD 172 SINGLE SOURCE OF TRUTH: Call behavior settings
        # DEFAULTS only - overwritten by load_call_config(business_id) when business is identified
        # Do NOT modify these directly - always use self.call_config for the authoritative values
        # 🔥 MASTER FIX: bot_speaks_first is now ALWAYS True (hardcoded) - flag deprecated
        self.bot_speaks_first = True  # HARDCODED: Always speak first (was: overwritten by CallConfig)
        self.auto_end_after_lead_capture = False  # Default: don't auto-end - overwritten by CallConfig
        self.auto_end_on_goodbye = True  # Default: auto-end on goodbye - NOW ENABLED BY DEFAULT - overwritten by CallConfig
        self.lead_captured = False  # Runtime state: tracks if all required lead info is collected
        self.goodbye_detected = False  # Runtime state: tracks if goodbye phrase detected
        self.bot_said_goodbye = False  # 🔥 NEW: Tracks if BOT said goodbye (ביי/להתראות) - watchdog uses this
        self.bot_said_goodbye_at = None  # 🔥 NEW: Timestamp when bot said goodbye
        self.pending_hangup = False  # Runtime state: signals that call should end after current TTS
        self.hangup_triggered = False  # Runtime state: prevents multiple hangup attempts
        # 🎯 Polite hangup metadata (execute only after response.audio.done)
        self.pending_hangup_reason = None
        self.pending_hangup_source = None
        self.pending_hangup_response_id = None
        self.pending_hangup_set_at = None
        # 🎯 Polite hangup fallback (prevents stuck pending state)
        self._pending_hangup_set_mono = None
        self._pending_hangup_fallback_task = None
        # 🎯 FIX: Race condition tracking - audio.done arriving before transcript.done
        self.audio_done_by_response_id = {}  # Tracks which response_ids have completed audio (max 2 recent)
        self.hangup_executed = False  # Idempotent flag - prevents duplicate hangup execution
        self.hangup_executed_at = None  # Timestamp when hangup was executed
        self.greeting_completed_at = None  # Runtime state: timestamp when greeting finished
        self.min_call_duration_after_greeting_ms = 3000  # Fixed: don't hangup for 3s after greeting
        self.silence_timeout_sec = 15  # Default - overwritten by CallConfig
        self.silence_max_warnings = 2  # Default - overwritten by CallConfig
        self.smart_hangup_enabled = True  # Default - overwritten by CallConfig
        # 🔥 PROMPT-ONLY MODE: No hardcoded required fields
        # What is "required" is defined by the business system prompt only
        self.required_lead_fields = []
        # 🔥 BUILD 309: SIMPLE_MODE settings
        self.call_goal = 'lead_only'  # Default - "lead_only" or "appointment"
        self.confirm_before_hangup = True  # Default - Always confirm before disconnecting
        # 🎯 DYNAMIC LEAD CAPTURE STATE: Tracks ALL captured fields from conversation
        # Updated by _update_lead_capture_state() from AI responses and DTMF
        self.lead_capture_state = {}  # e.g., {'name': 'דני', 'city': 'תל אביב', 'service_type': 'ניקיון'}
        
        # 🔥 BUILD 313: SIMPLIFIED - Only track last AI mentioned city for confirmation
        self._last_ai_mentioned_city = None  # Track city from AI confirmation for user "נכון" locking
        
        # 🔥 BUILD 336: STT TRUTH STORE - Prevent AI from hallucinating ANY values
        # When user says a value, we LOCK it and use it for confirmation template
        # AI can NEVER change locked values - only user correction can unlock
        self._city_locked = False           # True = city is locked from user utterance
        self._city_raw_from_stt = None      # Raw city text from STT (source of truth)
        self._city_source = None            # 'user_utterance' or 'ai_extraction'
        self._known_city_names_set = None
        self._current_stt_confidence = None
        self._current_transcript_token_count = 0
        self._current_transcript_is_first_answer = False
        
        # 🔥 BUILD 336: SERVICE TYPE LOCK - Same logic for service
        self._service_locked = False        # True = service is locked from user utterance
        self._service_raw_from_stt = None   # Raw service text from STT (source of truth)
        
        # 🔥 BUILD 336: Expected confirmation for validation
        self._expected_confirmation = None  # The confirmation we told AI to say
        self._confirmation_validated = False  # True if AI said correct confirmation
        self._speak_exact_resend_count = 0  # Track resend attempts to prevent infinite loops
        
        # 🛡️ BUILD 168: VERIFICATION GATE - Only disconnect after user confirms
        # Set to True when user says confirmation words: "כן", "נכון", "בדיוק", "כן כן"
        self.verification_confirmed = False  # Must be True before AI-triggered hangup is allowed
        self._verification_prompt_sent = False  # Tracks if we already asked for verification
        self._silence_final_chance_given = False  # Tracks if we gave extra chance before silence hangup
        self._awaiting_confirmation_reply = False  # Prevent duplicate confirmation prompts
        self._lead_confirmation_received = False  # True once user explicitly confirmed details
        self._lead_closing_dispatched = False  # Prevent duplicate closing prompts
        # 🔥 BUILD 203: REJECTION GATE - Blocks hangup when user rejects confirmation
        self.user_rejected_confirmation = False  # Set when user says "לא", "ממש לא" etc.
        
        # 🔥 BUILD 308: POST-REJECTION COOL-OFF - Give user time to provide correction
        self._awaiting_user_correction = False  # Set after user rejects, cleared when they speak again
        self._rejection_timestamp = 0  # When user last rejected
        
        # 🔥 BUILD 311: POST-GREETING PATIENCE - Don't skip questions after greeting!
        # Grace period: Don't count consecutive responses or trigger LOOP GUARD for X seconds after greeting
        # 🔥 BUILD 311.1: Reduced to 5 seconds - enough time but not too long
        self._post_greeting_grace_period_sec = 5.0  # 5 seconds after greeting to let user respond
        self._is_silence_handler_response = False  # Track if current response is from SILENCE_HANDLER (shouldn't count)
        self._user_responded_after_greeting = False  # Track if user has responded after greeting (end grace early)
        
        # 🔥 SESSION CONFIGURATION VALIDATION: Track session.update success/failure
        self._session_config_confirmed = False  # True when session.updated received
        self._session_config_failed = False  # True when session.update error received
        self._session_config_event = asyncio.Event()  # Event for efficient waiting (no polling)
        
        # 🔥 CALL METRICS: Performance tracking counters
        self._barge_in_event_count = 0  # Count of barge-in events during call
        self._silence_10s_count = 0  # Count of 10s+ silence gaps during call
        self._stt_hallucinations_dropped = 0  # Count of STT hallucinations rejected by STT_GUARD
        self.connection_start_time = time.time()  # Track connection start for metrics
        
        # 🔥 SIMPLE_MODE FIX: Separate frame drop counters for diagnostics
        self._frames_dropped_by_greeting_lock = 0  # Frames dropped during greeting_lock
        self._frames_dropped_by_filters = 0  # Frames dropped by audio filters (echo gate, decay, etc.)
        self._frames_dropped_by_queue_full = 0  # Frames dropped due to queue full
        
        # 🔥 DIAGNOSTIC: Detailed frame drop tracking by reason
        # Dictionary mapping FrameDropReason -> count for precise debugging
        self._frames_dropped_by_reason = {
            FrameDropReason.GREETING_LOCK: 0,
            FrameDropReason.ECHO_GATE: 0,
            FrameDropReason.ECHO_DECAY: 0,
            FrameDropReason.AUDIO_GUARD: 0,
            FrameDropReason.MUSIC_MODE: 0,
            FrameDropReason.QUEUE_FULL: 0,
            FrameDropReason.NOISE_GATE: 0,
            FrameDropReason.SESSION_NOT_READY: 0,
            FrameDropReason.OTHER: 0,
        }
        
        # 🔥 VERIFICATION: VAD calibration tracking (first 3 seconds)
        self._vad_calibration_start_ts = None  # When first audio frame received
        self._vad_calibration_complete = False  # Set after 3 seconds
        self._vad_frames_in_first_3s = 0  # Count frames received in first 3 seconds
        self._vad_speech_started_count_first_3s = 0  # Count speech_started events in first 3 seconds
        self._vad_calibrated_noise_floor = None  # Calibrated noise floor value
        self._vad_calibrated_threshold = None  # Calibrated VAD threshold
        
        # ═══════════════════════════════════════════════════════════════════════════
        # 🔥 VOICEMAIL DETECTION & SILENCE WATCHDOG: Aggressive disconnect features
        # ═══════════════════════════════════════════════════════════════════════════
        self._call_started_ts = time.time()  # Track call start for 10-second voicemail window
        self._last_activity_ts = time.time()  # Track last activity (user OR bot) for silence watchdog
        self._silence_watchdog_running = True  # Flag to control watchdog thread
        self._silence_watchdog_task = None  # Asyncio task for silence monitoring

    def _check_queue_backlog(self, queue, queue_name: str, threshold: int = 200) -> None:
        """
        🔥 Helper method to monitor queue backlog and log warnings
        ⚠️ WARN-ONLY: Does not drop, truncate, or modify queue - just logs
        
        Args:
            queue: The queue object to check
            queue_name: Name for logging (e.g., 'tx_q', 'realtime_audio_out_queue')
            threshold: Frame threshold for warning (default 200 = 4 seconds @ 50fps)
        """
        try:
            current_qsize = queue.qsize()
            if current_qsize > threshold:
                now_mono = time.monotonic()
                warning_attr = f'_last_{queue_name}_backlog_warning'
                last_warning = getattr(self, warning_attr, 0.0)
                
                if now_mono - last_warning > 3.0:
                    # Include full context for debugging
                    call_sid_short = self.call_sid[:8] if hasattr(self, 'call_sid') and self.call_sid else 'unknown'
                    stream_sid_short = self.stream_sid[:8] if hasattr(self, 'stream_sid') and self.stream_sid else 'none'
                    active_resp = getattr(self, 'active_response_id', None)
                    active_resp_short = active_resp[:8] if active_resp else 'none'
                    is_speaking = getattr(self, 'is_ai_speaking_event', None)
                    speaking_status = is_speaking.is_set() if is_speaking else False
                    
                    _orig_print(
                        f"⚠️ [BACKLOG] {queue_name}={current_qsize} frames (>{threshold}) | "
                        f"call={call_sid_short} stream={stream_sid_short} "
                        f"resp={active_resp_short} ai_speaking={speaking_status}",
                        flush=True
                    )
                    setattr(self, warning_attr, now_mono)
        except Exception as e:
            # Don't let backlog monitoring crash the call
            pass
    
    async def _maybe_hangup_voicemail(self, user_text: str):
        """
        🔥 VOICEMAIL DETECTION: Check if user transcript indicates voicemail/answering machine
        
        Only checks within first 10 seconds of call. Disconnects immediately if:
        - User transcript contains voicemail keywords (משיבון, תא קולי, etc.)
        - User transcript contains phone number being read (05x..., +972...)
        
        ⚠️ CRITICAL: 10-second window prevents false positives mid-call
        (customer might mention phone numbers or similar phrases during conversation)
        
        Args:
            user_text: The user's transcript text to check
        """
        # Only check within first 10 seconds (strict time limit to prevent false positives)
        elapsed = time.time() - self._call_started_ts
        if elapsed > 10.0:
            return
        
        # Check for voicemail keywords
        kw = _has_voicemail_keyword(user_text)
        
        # Check for phone number
        ph = _has_phone(user_text)
        
        if kw or ph:
            # 🔥 ONE-LINE LOG: Production visibility for voicemail detection
            logger.warning(
                f"[VOICEMAIL_DETECT] elapsed={elapsed:.1f}s kw={kw} phone={ph} text={user_text[:120]!r} -> IMMEDIATE_HANGUP"
            )
            _orig_print(
                f"🚨 [VOICEMAIL_DETECT] elapsed={elapsed:.1f}s kw={kw} phone={ph} -> IMMEDIATE_HANGUP",
                flush=True
            )
            
            # Trigger IMMEDIATE hangup (bypasses all protections)
            self._immediate_hangup(reason="voicemail_detected")
    
    async def _silence_watchdog(self):
        """
        🔥 SMART SILENCE WATCHDOG: Intelligent conversation monitoring with context awareness
        
        Runs continuously, checking every 1 second.
        
        🎯 DISCONNECT LOGIC (OR not AND!):
        The watchdog disconnects in ONE of these scenarios:
        
        SCENARIO 1: Bot said goodbye (ביי/להתראות)
        - Bot must have said goodbye → Disconnect immediately after audio completes
        - Handled by pending_hangup flow (not watchdog)
        
        SCENARIO 2: 20 seconds of TRUE silence (OR)
        - 20+ seconds with NO activity (no bot speaking, no user speaking)
        - This is the watchdog's job
        
        🔥 KEY: "Silence" means NO bot activity:
        - EVERY iteration checks if bot is speaking (audio in queues)
        - If bot is speaking → IMMEDIATELY reset activity timestamp (not just at 20s threshold)
        - If bot just finished speaking → Start counting from that moment
        - If user speaks → Reset counter (via _last_activity_ts update)
        
        This prevents false disconnects during:
        - Long AI responses (audio still playing)
        - AI responses that start near the 20-second mark
        - Audio drain period (after response.done)
        - Active conversation (user or bot speaking)
        
        Authority level: Non-blocking, bypasses queues/locks for reliable disconnection.
        """
        try:
            while self._silence_watchdog_running:
                # 🔥 CRITICAL: "CALL END = שקט" - Stop watchdog when call ends
                if self.closed or getattr(self, 'call_state', None) in (CallState.CLOSING, CallState.ENDED):
                    logger.debug(f"[WATCHDOG] Stopping - call ended")
                    self._silence_watchdog_running = False
                    return
                
                await asyncio.sleep(1)
                
                # 🔥 CRITICAL FIX: Check if AI is speaking FIRST, before calculating idle time
                # This ensures that AI speech ALWAYS resets the activity timer, preventing false disconnects
                # The issue: Previously checked queues only AFTER idle >= 20s, which meant if AI started
                # speaking at 19s, the watchdog would still disconnect at 20s
                q1_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
                tx_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
                total_queued = q1_size + tx_size
                
                # If bot is actively speaking (audio in queues), reset activity timestamp
                if total_queued > 0:
                    self._last_activity_ts = time.time()
                    if DEBUG:
                        logger.debug(f"[WATCHDOG] bot still speaking ({total_queued} frames queued) - activity timestamp reset")
                    continue
                
                idle = time.time() - self._last_activity_ts
                
                # 🔥 SMART LOGIC: Check for 20 seconds of TRUE silence
                if idle >= 20.0:
                    # Check 1: Hangup already triggered (cleanup in progress)
                    hangup_triggered = getattr(self, 'hangup_triggered', False)
                    if hangup_triggered:
                        if DEBUG:
                            logger.debug(f"[WATCHDOG] idle={idle:.1f}s but hangup_triggered=True - already disconnecting")
                        continue
                    
                    # Check 2: Polite hangup already in progress (bot said goodbye, waiting for audio)
                    pending_hangup = getattr(self, 'pending_hangup', False)
                    if pending_hangup:
                        if DEBUG:
                            logger.debug(f"[WATCHDOG] idle={idle:.1f}s but pending_hangup=True - polite hangup in progress")
                        else:
                            _orig_print(f"⏳ [WATCHDOG] idle={idle:.1f}s but polite hangup in progress - allowing completion", flush=True)
                        continue
                    
                    # All checks passed:
                    # - 20 seconds of TRUE silence (no bot speaking, no user speaking) ✅
                    # - No audio in queues ✅
                    # - No hangup in progress ✅
                    # → Disconnect due to silence
                    
                    logger.warning(f"[WATCHDOG] {idle:.1f}s of true silence (no user OR bot activity) → DISCONNECT")
                    _orig_print(f"🚨 [WATCHDOG] {idle:.1f}s of TRUE silence → DISCONNECT", flush=True)
                    
                    # Stop watchdog before triggering hangup to prevent race conditions
                    self._silence_watchdog_running = False
                    
                    # Trigger IMMEDIATE hangup (bypasses all protections)
                    self._immediate_hangup(reason="silence_20s")
                    return
        except asyncio.CancelledError:
            # Normal cancellation during cleanup
            logger.debug("[WATCHDOG] Task cancelled during cleanup")
        except Exception as e:
            # Unexpected error - log but don't crash
            logger.error(f"[WATCHDOG] Unexpected error: {e}")
            _orig_print(f"⚠️ [WATCHDOG] Error: {e}", flush=True)

    def _build_realtime_tools_for_call(self) -> list:
        """
        🎯 SMART TOOL SELECTION for Realtime phone calls
        
        Realtime phone calls policy:
        - Default: NO tools (pure conversation)
        - If business has appointments enabled: ONLY appointment scheduling tool
        - Never: city tools, lead tools, WhatsApp tools, AgentKit tools
        
        Returns:
            list[dict]: Tool schemas for OpenAI Realtime (empty list or appointment tool only)
        """
        tools = []
        
        # 🔥 SERVER-FIRST: Do NOT expose scheduling tools to Realtime.
        # Server will decide when to check/schedule and will inject verbatim sentences.
        if SERVER_FIRST_SCHEDULING:
            logger.debug("[TOOLS][REALTIME] SERVER_FIRST_SCHEDULING=1 - no tools exposed")
            return tools
        
        # Check if business has appointment scheduling enabled
        try:
            business_id = getattr(self, 'business_id', None)
            if not business_id:
                logger.debug("[TOOLS][REALTIME] No business_id - no tools enabled")
                return tools
            
            # 🔥 FIX: Database queries need Flask app context!
            app = _get_flask_app()
            with app.app_context():
                # Load business settings to check if appointments are enabled
                from server.models_sql import BusinessSettings
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                
                # 🔥 CHECK: call_goal == "appointment" - that's the only requirement!
                # Business policy will handle hours, slot size, etc.
                call_goal = getattr(settings, 'call_goal', 'lead_only') if settings else 'lead_only'
                
                if call_goal == 'appointment':
                    # 🔥 TOOL 1: Check Availability - MUST be called before booking
                    availability_tool = {
                        "type": "function",
                        "name": "check_availability",
                        "description": "Check available appointment slots for a specific date (server-side). MUST be called before claiming availability or offering times.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "date": {
                                    "type": "string",
                                    "description": "Date to check. Accepts YYYY-MM-DD OR Hebrew like 'היום'/'מחר'/'ראשון'/'שני' (server will normalize to a full date + weekday)."
                                },
                                "preferred_time": {
                                    "type": "string",
                                    "description": "Optional preferred time. Accepts HH:MM or Hebrew like 'שלוש'/'שלוש וחצי'. Server will normalize and return slots near that time."
                                },
                                "service_type": {
                                    "type": "string",
                                    "description": "Type of service requested (used to determine duration)"
                                }
                            },
                            "required": ["date"]
                        }
                    }
                    
                    # 🔥 TOOL 2: Schedule Appointment - MUST be called to create booking
                    appointment_tool = {
                        "type": "function",
                        "name": "schedule_appointment",
                        "description": "Create an appointment ONLY after a real availability check. Server will normalize Hebrew date/time and will refuse to book if slot is not available.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "customer_name": {
                                    "type": "string",
                                    "description": "Customer's full name"
                                },
                                "appointment_date": {
                                    "type": "string",
                                    "description": "Appointment date. Accepts YYYY-MM-DD OR Hebrew like 'היום'/'מחר'/'ראשון'."
                                },
                                "appointment_time": {
                                    "type": "string",
                                    "description": "Appointment time. Accepts HH:MM or Hebrew like 'שלוש'/'שלוש וחצי'."
                                },
                                "service_type": {
                                    "type": "string",
                                    "description": "Type of service requested"
                                }
                            },
                            "required": ["customer_name", "appointment_date", "appointment_time"]
                        }
                    }
                    
                    tools.append(availability_tool)
                    tools.append(appointment_tool)
                    logger.debug(f"[TOOLS][REALTIME] Appointment tools ENABLED (call_goal=appointment) for business {business_id}")
                else:
                    logger.debug(f"[TOOLS][REALTIME] Appointments DISABLED (call_goal={call_goal}) - no tools for business {business_id}")
                
        except Exception as e:
            logger.error(f"[TOOLS][REALTIME] Error checking appointment settings: {e}")
            import traceback
            traceback.print_exc()
            # Safe fallback - no tools
        
        return tools
    
    def _init_streaming_stt(self):
        """
        🚫 DISABLED - Google streaming STT is turned off for production stability
        
        This function is deprecated and should not be called.
        Use OpenAI Realtime API instead.
        """
        # Always skip initialization when Google is disabled or streaming STT is off
        return
    
    def _close_streaming_stt(self):
        """Close streaming STT session at end of call"""
        if self.call_sid:
            _close_session(self.call_sid)
    
    def _utterance_begin(self, partial_cb=None):
        """
        Mark start of new utterance.
        Switches dispatcher target to new utterance buffer.
        """
        import uuid
        import threading
        
        if not self.call_sid:
            return
        
        utt_state = _get_utterance_state(self.call_sid)
        if utt_state is not None:
            with _registry_lock:
                utt_state["id"] = uuid.uuid4().hex[:8]
                utt_state["partial_cb"] = partial_cb
                utt_state["final_buf"] = []
                utt_state["final_received"] = threading.Event()  # ⚡ NEW: wait for final
                utt_state["last_partial"] = ""  # ⚡ NEW: save last partial as backup
            
            if DEBUG: logger.debug(f"🎤 [{self.call_sid[:8]}] Utterance {utt_state['id']} BEGIN")
    
    def _utterance_end(self, timeout=0.850):
        """
        Mark end of utterance.
        ⚡ BUILD 118: Increased timeout to 850ms - streaming STT needs time for final results
        """
        if not self.call_sid:
            logger.warning("⚠️ _utterance_end: No call_sid")
            return ""
        
        utt_state = _get_utterance_state(self.call_sid)
        if utt_state is None:
            logger.warning(f"⚠️ _utterance_end: No utterance state for call {self.call_sid[:8]}")
            return ""
        
        utt_id = utt_state.get("id", "???")
        logger.info(f"🎤 [{self.call_sid[:8]}] _utterance_end: Collecting results for utterance {utt_id} (timeout={timeout}s)")
        
        # ⚡ BUILD 118: Wait 850ms for streaming results - allows time for final transcription
        # Streaming STT enabled by default → fast partial results
        wait_start = time.time()
        wait_duration = 0.0
        final_event = utt_state.get("final_received")
        if final_event:
            got_final = final_event.wait(timeout=timeout)  # 850ms wait for streaming
            wait_duration = time.time() - wait_start
            if got_final:
                logger.info(f"✅ [{self.call_sid[:8]}] Got final event in {wait_duration:.3f}s")
            else:
                logger.warning(f"⚠️ [{self.call_sid[:8]}] Timeout after {wait_duration:.3f}s - using fallback")
        
        # Collect text - prioritize partial over finals
        with _registry_lock:
            # ⚡ PRIMARY: Use last partial (this is what we actually get!)
            last_partial = utt_state.get("last_partial", "")
            
            # FALLBACK: Check finals buffer (rarely populated)
            finals = utt_state.get("final_buf") or []
            finals_text = " ".join(finals).strip()
            
            # Use partial if available, otherwise finals
            if last_partial:
                text = last_partial
                logger.info(f"✅ [{self.call_sid[:8]}] Using partial: '{text[:50]}...' ({len(text)} chars)")
            elif finals_text:
                text = finals_text
                logger.info(f"✅ [{self.call_sid[:8]}] Using final: '{text[:50]}...' ({len(text)} chars)")
            else:
                text = ""
                logger.warning(f"⚠️ [{self.call_sid[:8]}] No text available - returning empty")
            
            # Reset dispatcher
            utt_state["id"] = None
            utt_state["partial_cb"] = None
            utt_state["final_buf"] = None
            utt_state["final_received"] = None
            utt_state["last_partial"] = ""
        
        # ⚡ BUILD 114: Detailed latency logging
        logger.info(f"🏁 [{self.call_sid[:8]}] Utterance {utt_id} COMPLETE: returning '{text[:30] if text else '(empty)'}'")
        logger.info(f"[LATENCY] final_wait={wait_duration:.2f}s, utterance_total={time.time() - wait_start:.2f}s")
        
        return text
    
    # 🔥 PERFORMANCE: Call Cache System - Load all DB data once
    def _load_call_context_batch(self, call_sid, business_id, lead_id=None):
        """
        Load all call data in single JOIN query.
        PERFORMANCE: Replaces ~17 individual queries with 1 batch query.
        Returns CallContext with all needed data cached.
        """
        from server.models_sql import CallLog, Lead, Business, BusinessSettings, OutboundCallJob
        from server.db import db
        
        try:
            app = _get_flask_app()
            with app.app_context():
                # Single JOIN query - loads everything at once
                query = db.session.query(
                    CallLog, Lead, Business, BusinessSettings
                ).outerjoin(
                    Lead, CallLog.lead_id == Lead.id
                ).outerjoin(
                    Business, Business.id == business_id
                ).outerjoin(
                    BusinessSettings, BusinessSettings.tenant_id == business_id
                ).filter(
                    CallLog.call_sid == call_sid
                )
                
                result = query.first()
                
                # Try to load outbound job if available
                outbound_job = None
                try:
                    outbound_job = OutboundCallJob.query.filter_by(
                        twilio_call_sid=call_sid
                    ).first()
                except Exception:
                    pass
                
                if result:
                    call_log, lead, business, settings = result
                    ctx = CallContext(call_log, lead, business, settings, outbound_job)
                    logger.info(f"✅ [CALL_CACHE] Loaded context: lead_id={ctx.lead_id}, business={ctx.business_name}")
                    return ctx
                else:
                    # Call not in DB yet - create minimal context
                    business = Business.query.get(business_id)
                    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                    ctx = CallContext(None, None, business, settings, outbound_job)
                    logger.info(f"✅ [CALL_CACHE] Minimal context: business={ctx.business_name}")
                    return ctx
                    
        except Exception as e:
            logger.error(f"[CALL_CACHE] Failed to load context: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _check_db_guard(self, operation="DB query"):
        """
        Guard against DB access during live call.
        Returns True if access should be blocked.
        """
        if getattr(self, 'in_live_call', False):
            logger.warning(f"[DB_GUARD] Blocked {operation} during live call")
            logger.warning(f"⚠️ [DB_GUARD] Attempted {operation} during live call - using cache instead")
            return True
        return False
    
    def _flush_db_writes(self):
        """
        Flush all buffered DB writes at call end.
        PERFORMANCE: Single commit instead of 3-4 mid-call commits.
        """
        if not self.db_write_queue:
            logger.info(f"✅ [DB_FLUSH] No buffered writes to flush")
            return
        
        try:
            from server.models_sql import Lead, CallSession
            from server.db import db
            
            app = _get_flask_app()
            with app.app_context():
                write_count = len(self.db_write_queue)
                logger.info(f"🔄 [DB_FLUSH] Flushing {write_count} buffered writes...")
                
                for write in self.db_write_queue:
                    try:
                        if write['type'] == 'lead_update':
                            lead = Lead.query.get(write['lead_id'])
                            if lead:
                                for field, value in write['updates'].items():
                                    setattr(lead, field, value)
                                    logger.info(f"   ✓ Lead {lead.id}.{field} = {value}")
                        
                        elif write['type'] == 'callsession_update':
                            session = CallSession.query.filter_by(
                                call_sid=write['call_sid']
                            ).first()
                            if session:
                                for field, value in write['updates'].items():
                                    setattr(session, field, value)
                                    logger.info(f"   ✓ CallSession.{field} = {value}")
                        
                    except Exception as write_err:
                        logger.error(f"[DB_FLUSH] Failed to apply write {write}: {write_err}")
                
                # Single commit for all writes
                db.session.commit()
                logger.info(f"✅ [DB_FLUSH] Successfully committed {write_count} writes")
                self.db_write_queue = []
                
        except Exception as e:
            logger.error(f"[DB_FLUSH] Failed to flush writes: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except:
                pass

    def _set_safe_business_defaults(self, force_greeting=False):
        """🔥 SAFETY: Set ONLY MISSING fields with safe defaults. Never overwrite valid data."""
        # ⛔ CRITICAL: NEVER allow calls without business_id - this causes cross-business contamination!
        if not hasattr(self, 'business_id') or self.business_id is None:
            logger.error(f"❌ CRITICAL: Call without business_id! call_sid={getattr(self, 'call_sid', 'unknown')}, to={getattr(self, 'to_number', 'unknown')}")
            raise ValueError("CRITICAL: business_id is required - cannot process call without valid business identification")
        if not hasattr(self, 'business_name') or self.business_name is None:
            self.business_name = "העסק"
        if not hasattr(self, 'bot_speaks_first'):
            self.bot_speaks_first = True
        if not hasattr(self, 'auto_end_after_lead_capture'):
            self.auto_end_after_lead_capture = False
        # 🔥 FIX: Ensure auto_end_on_goodbye is set to True by default if not present
        if not hasattr(self, 'auto_end_on_goodbye'):
            self.auto_end_on_goodbye = True  # Default: auto-end on goodbye - NOW ENABLED BY DEFAULT
        if not hasattr(self, 'greeting_text'):
            self.greeting_text = None
        
        # 🔥 BUILD 172: Ensure CallConfig is set with defaults
        if not hasattr(self, 'call_config') or self.call_config is None:
            self.call_config = CallConfig(
                business_id=self.business_id,
                business_name=getattr(self, 'business_name', "העסק"),
                bot_speaks_first=self.bot_speaks_first,
                auto_end_after_lead_capture=self.auto_end_after_lead_capture,
                auto_end_on_goodbye=self.auto_end_on_goodbye,
                silence_timeout_sec=self.silence_timeout_sec,
                silence_max_warnings=self.silence_max_warnings,
                smart_hangup_enabled=self.smart_hangup_enabled,
                required_lead_fields=self.required_lead_fields,
                closing_sentence=""
            )
            logger.info(f"🔒 [DEFAULTS] Created fallback CallConfig for business={self.business_id}")
        
        # Force bot_speaks_first on error/timeout paths
        if force_greeting:
            self.bot_speaks_first = True
            logger.info(f"🔒 [DEFAULTS] Forced bot_speaks_first=True for greeting")

    def _run_realtime_mode_thread(self):
        """
        🚀 OpenAI Realtime API Mode - Runs in dedicated thread with asyncio loop
        
        This replaces the Google STT/TTS pipeline with OpenAI Realtime API:
        - Twilio μ-law audio → Realtime API (input_audio_buffer.append)
        - Realtime API audio deltas → Twilio (response.audio.delta)
        - Server-side tool orchestration (calendar, leads) - NO AgentKit
        
        Thread architecture:
        - Main thread (Eventlet): Twilio WebSocket handling
        - This thread: asyncio event loop for Realtime API WebSocket
        - Communication via thread-safe queues
        
        🚨 COST SAFETY: Each call creates ONE fresh Realtime session (no reuse)
        
        🔥 REALTIME STABILITY: Enhanced exception handling with REALTIME_FATAL logging
        """
        call_id = self.call_sid[:8] if self.call_sid else "unknown"
        
        # 🔥 CRITICAL: Unconditional logs at the very top
        _orig_print(f"🚀 [REALTIME] _run_realtime_mode_thread ENTERED for call {call_id} (FRESH SESSION)", flush=True)
        logger.debug(f"[REALTIME] _run_realtime_mode_thread ENTERED for call {call_id}")
        logger.debug(f"[REALTIME] Thread started for call {call_id}")
        logger.debug(f"[REALTIME] About to run asyncio.run(_run_realtime_mode_async)...")
        
        try:
            asyncio.run(self._run_realtime_mode_async())
            logger.debug(f"[REALTIME] asyncio.run completed normally for call {call_id}")
        except Exception as e:
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME_FATAL: Critical exception in realtime thread
            # ═══════════════════════════════════════════════════════════════════════
            import traceback
            tb_str = traceback.format_exc()
            _orig_print(f"🔥 [REALTIME_FATAL] Unhandled exception in _run_realtime_mode_thread: {e}", flush=True)
            _orig_print(f"🔥 [REALTIME_FATAL] call_id={call_id}", flush=True)
            traceback.print_exc()
            logger.error(f"[REALTIME_FATAL] Unhandled exception in thread for call {call_id}: {e}")
            logger.error(f"[REALTIME_FATAL] Full traceback:\n{tb_str}")
            
            # Mark realtime as failed
            self.realtime_failed = True
            self._realtime_failure_reason = f"THREAD_EXCEPTION: {type(e).__name__}"
            
            # Log metrics for failed call
            logger.debug(f"[METRICS] REALTIME_TIMINGS: openai_connect_ms={self._metrics_openai_connect_ms}, first_greeting_audio_ms={self._metrics_first_greeting_audio_ms}, realtime_failed=True, reason=THREAD_EXCEPTION")
            _orig_print(f"❌ [REALTIME_FALLBACK] Call {call_id} handled without realtime (reason=THREAD_EXCEPTION: {type(e).__name__})", flush=True)
        finally:
            logger.info(f"🔚 [REALTIME] Thread ended for call {call_id}")
            logger.debug(f"[REALTIME] Thread ended for call {call_id}")
    
    async def _run_realtime_mode_async(self):
        """
        🚀 OpenAI Realtime API - Async main loop with PARALLEL startup
        
        Handles bidirectional audio streaming:
        1. Connect to OpenAI IMMEDIATELY (parallel with DB query)
        2. Wait for business info from main thread
        3. Configure session and trigger greeting
        4. Stream audio bidirectionally
        """
        from server.services.openai_realtime_client import OpenAIRealtimeClient
        from server.config.calls import SERVER_VAD_THRESHOLD, SERVER_VAD_SILENCE_MS
        # Note: realtime_prompt_builder imported inside try block at line ~1527
        
        _orig_print(f"🚀 [REALTIME] Async loop starting - connecting to OpenAI IMMEDIATELY", flush=True)
        logger.debug(f"[REALTIME] _run_realtime_mode_async STARTED for call {self.call_sid}")
        
        # Helper function for session configuration (used for initial config and retry)
        async def _send_session_config(client, greeting_prompt, call_voice, greeting_max_tokens, tools=None, tool_choice="auto", force=False, send_reason="initial"):
            """Send session.update event with specified configuration
            
            Args:
                tools: Optional list of Realtime API tools (for appointments)
                tool_choice: Tool selection mode ("auto", "none", or specific tool)
                force: Set to True to bypass hash check (for retry)
                send_reason: Reason for send ("initial" or "retry")
            """
            # 🔥 VOICE VALIDATION: Ensure only Realtime-supported voices are sent
            if call_voice not in REALTIME_VOICES:
                _orig_print(f"⚠️ [SESSION_CONFIG] CRITICAL: Invalid voice '{call_voice}' detected in _send_session_config!", flush=True)
                logger.error(f"[SESSION_CONFIG] Invalid voice '{call_voice}' -> forcing DEFAULT_VOICE '{DEFAULT_VOICE}'")
                call_voice = DEFAULT_VOICE
            
            # 🔥 CRITICAL: Realtime is sensitive to heavy/dirty instructions.
            # Sanitize + hard cap to prevent silent starts / long delays.
            
            # 🔒 CHECK 2: Calculate hash BEFORE sanitization
            import hashlib
            hash_before = hashlib.md5((greeting_prompt or "").encode()).hexdigest()[:8]
            
            try:
                from server.services.realtime_prompt_builder import (
                    sanitize_realtime_instructions,
                    FULL_PROMPT_MAX_CHARS,
                )
                original_len = len(greeting_prompt or "")
                # 🔥 LATENCY-FIRST: Use FULL prompt from start (no compact anymore)
                greeting_prompt = sanitize_realtime_instructions(
                    greeting_prompt or "",
                    max_chars=FULL_PROMPT_MAX_CHARS
                )
                sanitized_len = len(greeting_prompt)
                if sanitized_len != original_len:
                    _orig_print(
                        f"🧽 [PROMPT_SANITIZE] instructions_len {original_len}→{sanitized_len} (cap={FULL_PROMPT_MAX_CHARS})",
                        flush=True,
                    )
            except Exception as _sanitize_err:
                # Never block the call on sanitizer issues; proceed with original prompt.
                _orig_print(f"⚠️ [PROMPT_SANITIZE] Failed: {_sanitize_err}", flush=True)
            
            # 🔒 CHECK 2: Calculate hash AFTER sanitization
            hash_after = hashlib.md5((greeting_prompt or "").encode()).hexdigest()[:8]

            # 🔥 SERVER-FIRST: For appointment calls we disable auto response creation so the server
            # can decide when/how to respond (verbatim injection after scheduling).
            call_goal = getattr(self, "call_goal", None) or getattr(getattr(self, "call_config", None), "call_goal", "lead_only")
            manual_turns = bool(SERVER_FIRST_SCHEDULING and call_goal == "appointment")
            self._server_first_scheduling_enabled = bool(SERVER_FIRST_SCHEDULING and call_goal == "appointment")
            self._manual_response_turns_enabled = bool(manual_turns)

            # 🔒 CHECK 2: Log detailed send information
            _orig_print(
                f"[SESSION_SEND] send_reason={send_reason} force={force} "
                f"hash_before={hash_before} hash_after={hash_after} "
                f"len={len(greeting_prompt)}",
                flush=True
            )
            
            # Call configure_session which has its own hash-based deduplication
            # It will return True if sent or skipped (via dedup)
            dedup_result = await client.configure_session(
                instructions=greeting_prompt,
                voice=call_voice,
                input_audio_format="g711_ulaw",
                output_audio_format="g711_ulaw",
                auto_create_response=not manual_turns,
                vad_threshold=SERVER_VAD_THRESHOLD,        # Use config (0.85) - reduced false positives
                silence_duration_ms=SERVER_VAD_SILENCE_MS, # Use config (600ms) - optimal for Hebrew
                # 🔥 CRITICAL FIX: Remove temperature=0.0 - let configure_session use default 0.6
                # OpenAI Realtime API requires temperature >= 0.6 (decimal_below_min_value error)
                # The configure_session method now handles clamping automatically
                max_tokens=greeting_max_tokens,
                # 🔥 PRODUCTION STT QUALITY: Neutral transcription prompt for Hebrew
                # Per OpenAI best practices: Keep prompt simple and neutral
                # Don't instruct model to skip/omit - let VAD threshold handle false triggers
                transcription_prompt=(
                    # EN: "Accurate transcription in Israeli Hebrew. Transcribe only what was actually said."
                    "תמלול מדויק בעברית ישראלית. "
                    "תמלל רק מה שנאמר בפועל."
                ),
                tools=tools,  # 🔥 NEW: Include tools in first session.update
                tool_choice=tool_choice if tools else None,  # Only set if tools exist
                force=force  # 🔥 FIX 3: Pass force flag to bypass hash check on retry
            )
            
            # 🔒 CHECK 2: Log if deduplication skipped the send
            # Note: configure_session returns True whether it sent or skipped
            # We need to check the client's internal state to know if it was skipped
            dedup_skipped = hasattr(client, '_last_instructions_hash') and not force and client._last_instructions_hash == hash_after
            
            _orig_print(
                f"[SESSION_SEND_RESULT] send_reason={send_reason} dedup_skipped={dedup_skipped} "
                f"hash={hash_after}",
                flush=True
            )
            
            return dedup_result
        
        client = None
        call_start_time = time.time()
        
        # 🔥 REMOVED: Counters now initialized in __init__ (line ~1806)
        # self.realtime_audio_in_chunks = 0
        # self.realtime_audio_out_chunks = 0
        self._user_speech_start = None
        self._ai_speech_start = None
        
        try:
            t_start = time.time()
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME STABILITY: OpenAI connection with SINGLE timeout
            # ═══════════════════════════════════════════════════════════════════════
            # NOTE: client.connect() already has internal retry (3 attempts with exponential backoff)
            # We only add a timeout wrapper to prevent infinite hangs - NO external retry loop!
            # Total internal retry time: ~7s (1s + 2s + 4s backoff)
            # ═══════════════════════════════════════════════════════════════════════
            logger.info(f"[CALL DEBUG] Creating OpenAI client with model={OPENAI_REALTIME_MODEL}")
            client = OpenAIRealtimeClient(model=OPENAI_REALTIME_MODEL)
            t_client = time.time()
            if DEBUG: logger.debug(f"⏱️ [PARALLEL] Client created in {(t_client-t_start)*1000:.0f}ms")
            
            t_connect_start = time.time()
            _orig_print(f"🔌 [REALTIME] Connecting to OpenAI (internal retry: 3 attempts)...", flush=True)
            
            try:
                # 🔥 FIX #3: Increased timeout to 8s and max_retries to 3 for better reliability
                # Timeout: 8s covers internal retries (1s + 2s + 4s + margin)
                # max_retries=3 gives more chances to connect (was 2)
                await asyncio.wait_for(client.connect(max_retries=3, backoff_base=0.5), timeout=8.0)
                connect_ms = (time.time() - t_connect_start) * 1000
                self._openai_connect_attempts = 1
                self._metrics_openai_connect_ms = int(connect_ms)
                _orig_print(f"✅ [REALTIME] OpenAI connected in {connect_ms:.0f}ms (max_retries=3)", flush=True)
                
            except asyncio.TimeoutError:
                connect_ms = (time.time() - t_connect_start) * 1000
                self._metrics_openai_connect_ms = int(connect_ms)
                _orig_print(f"⚠️ [REALTIME] OPENAI_CONNECT_TIMEOUT after {connect_ms:.0f}ms", flush=True)
                logger.error(f"[REALTIME] OpenAI connection timeout after {connect_ms:.0f}ms")
                
                self.realtime_failed = True
                self._realtime_failure_reason = "OPENAI_CONNECT_TIMEOUT"
                logger.debug(f"[METRICS] REALTIME_TIMINGS: openai_connect_ms={self._metrics_openai_connect_ms}, first_greeting_audio_ms=0, realtime_failed=True, reason=OPENAI_CONNECT_TIMEOUT")
                _orig_print(f"❌ [REALTIME_FALLBACK] Call {self.call_sid} handled without realtime (reason=OPENAI_CONNECT_TIMEOUT)", flush=True)
                return
                
            except Exception as connect_err:
                connect_ms = (time.time() - t_connect_start) * 1000
                self._metrics_openai_connect_ms = int(connect_ms)
                
                # 🔥 FIX #3: Enhanced error logging with full traceback for diagnostics
                import traceback
                error_details = traceback.format_exc()
                _orig_print(f"❌ [REALTIME] OpenAI connect error: {connect_err}", flush=True)
                _orig_print(f"❌ [REALTIME] Error type: {type(connect_err).__name__}", flush=True)
                _orig_print(f"❌ [REALTIME] Full traceback:\n{error_details}", flush=True)
                logger.error(f"[REALTIME] OpenAI connection error: {connect_err}")
                logger.error(f"[REALTIME] Full error details:\n{error_details}")
                
                self.realtime_failed = True
                self._realtime_failure_reason = f"OPENAI_CONNECT_ERROR: {type(connect_err).__name__}"
                logger.debug(f"[METRICS] REALTIME_TIMINGS: openai_connect_ms={self._metrics_openai_connect_ms}, first_greeting_audio_ms=0, realtime_failed=True, reason={self._realtime_failure_reason}")
                _orig_print(f"❌ [REALTIME_FALLBACK] Call {self.call_sid} handled without realtime (reason={self._realtime_failure_reason})", flush=True)
                
                # 🔥 FIX #3: Log call context for debugging
                _orig_print(f"📊 [REALTIME] Call context: business_id={business_id_safe}, direction={call_direction}, call_sid={self.call_sid}", flush=True)
                return
            
            t_connected = time.time()
            
            # Warn if connection is slow (>1.5s is too slow for good UX)
            if connect_ms > 1500:
                logger.warning(f"⚠️ [PARALLEL] SLOW OpenAI connection: {connect_ms:.0f}ms (target: <1000ms)")
            if DEBUG: logger.debug(f"⏱️ [PARALLEL] OpenAI connected in {connect_ms:.0f}ms (T0+{(t_connected-self.t0_connected)*1000:.0f}ms)")
            
            self.realtime_client = client
            
            is_mini = "mini" in OPENAI_REALTIME_MODEL.lower()
            cost_info = "MINI (80% cheaper)" if is_mini else "STANDARD"
            logger.debug("[REALTIME] Connected")
            
            # 🚀 PARALLEL STEP 2: Wait briefly for business info (do NOT block greeting)
            logger.info(f"⏳ [PARALLEL] Waiting for business info from DB query...")
            
            # Use asyncio to wait for the threading.Event
            loop = asyncio.get_event_loop()
            try:
                # Keep this short: greeting must not depend on DB readiness.
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self.business_info_ready_event.wait(0.3)),
                    timeout=0.6
                )
                t_ready = time.time()
                wait_ms = (t_ready - t_connected) * 1000
                logger.info(f"✅ [PARALLEL] Business info ready! Wait time: {wait_ms:.0f}ms")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ [PARALLEL] Timeout waiting for business info - proceeding with defaults (do not block greeting)")
                # Use helper with force_greeting=True to ensure greeting fires
                self._set_safe_business_defaults(force_greeting=True)
            
            # 🔥 BUILD 315: FULL PROMPT FROM START - AI has complete context from first moment!
            # This ensures the AI understands the business, services, and context when greeting
            # and when interpreting user responses (e.g., city names like "קריית אתא")
            t_before_prompt = time.time()
            greeting_text = getattr(self, 'greeting_text', None)
            biz_name = getattr(self, 'business_name', None) or "העסק"
            
            # ⛔ CRITICAL: business_id must be set before this point - no fallback allowed
            if self.business_id is None:
                logger.error(f"❌ CRITICAL: business_id is None at greeting! call_sid={self.call_sid}")
                _orig_print(f"❌ [BUSINESS_ISOLATION] OpenAI session rejected - no business_id", flush=True)
                raise ValueError("CRITICAL: business_id required for greeting")
            
            business_id_safe = self.business_id
            call_direction = getattr(self, 'call_direction', 'inbound')
            outbound_lead_name = getattr(self, 'outbound_lead_name', None)
            
            # 🔥 PERFORMANCE: Load call cache once at start (replaces ~17 queries during call)
            if not self.call_ctx_loaded:
                self.call_ctx = self._load_call_context_batch(
                    self.call_sid,
                    business_id_safe,
                    lead_id=getattr(self, 'outbound_lead_id', None)
                )
                if self.call_ctx:
                    self.call_ctx_loaded = True
                    logger.info(f"✅ [CALL_CACHE] Context loaded and ready")
                else:
                    logger.error(f"⚠️ [CALL_CACHE] Failed to load - will use direct queries as fallback")
            
            # 🔥 NAME SSOT: Resolve customer name from database by call_sid, lead_id, or phone
            # This is the authoritative source for outbound call names
            def _resolve_customer_name(call_sid: str, business_id: int, lead_id: Optional[int] = None, phone_number: Optional[str] = None) -> tuple:
                """
                Resolve customer name from database based on available identifiers.
                
                Priority order (SSOT):
                1. CallLog.customer_name (if exists)
                2. Lead by lead_id (if provided)
                3. OutboundCallJob.lead_name (for bulk calls)
                4. Lead.full_name (via CallLog.lead_id relationship)
                5. Fallback: Lead lookup by phone number
                6. Final fallback: None
                
                Args:
                    call_sid: Twilio call SID
                    business_id: Business ID for filtering
                    lead_id: Optional lead ID from customParameters
                    phone_number: Optional phone number for fallback lookup
                
                Returns:
                    (name, source) tuple where source is one of:
                    "call_log", "lead_id", "outbound_job", "lead_calllog", "lead_phone", None
                """
                if not call_sid and not lead_id and not phone_number:
                    return (None, None)
                
                # 🔥 PERFORMANCE: Use cache if available (avoids DB queries)
                if self.call_ctx_loaded and self.call_ctx:
                    name = self.call_ctx.get_customer_name()
                    if name and name != "ללא שם":
                        from server.services.realtime_prompt_builder import extract_first_name
                        first_name = extract_first_name(name) if name else None
                        if first_name:
                            logger.info(f"✅ [CALL_CACHE] Using cached name: {first_name}")
                            return (first_name, "call_cache")
                
                try:
                    from server.models_sql import CallLog, OutboundCallJob, Lead
                    from server.services.realtime_prompt_builder import extract_first_name
                    
                    # 🔥 ENHANCED DEBUG: Log all input parameters
                    logger.info(f"[NAME_RESOLVE] Starting resolution: call_sid={call_sid[:8] if call_sid else 'N/A'}, lead_id={lead_id}, phone={phone_number}, business_id={business_id}")
                    _orig_print(f"[NAME_RESOLVE DEBUG] call_sid={call_sid[:8] if call_sid else 'N/A'} lead_id={lead_id} phone={phone_number}", flush=True)
                    
                    # 🔥 CRITICAL FIX: Must have app_context for DB queries in async context
                    app = _get_flask_app()
                    with app.app_context():
                        call_log = None
                        
                        # Priority 1: CallLog.customer_name
                        if call_sid:
                            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                            if call_log and call_log.customer_name:
                                full_name = str(call_log.customer_name).strip()
                                if full_name and full_name != "ללא שם":
                                    # Extract first name only (max 2 words, skip complex names)
                                    name = extract_first_name(full_name)
                                    if name:
                                        logger.info(f"[NAME_RESOLVE] source=call_log full_name=\"{full_name}\" first_name=\"{name}\" call_sid={call_sid[:8]}")
                                        _orig_print(f"[NAME_RESOLVE] source=call_log name=\"{name}\"", flush=True)
                                        return (name, "call_log")
                                    else:
                                        logger.info(f"[NAME_RESOLVE] source=call_log skipped complex name: \"{full_name}\"")
                                        _orig_print(f"[NAME_RESOLVE] Skipped complex name from call_log", flush=True)
                        
                        # Priority 2: Lead by lead_id (from customParameters)
                        if lead_id:
                            try:
                                lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id).first()
                                if lead:
                                    full_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                                    # 🔥 DEBUG: Log what we found
                                    logger.info(f"[NAME_RESOLVE] Found lead: id={lead_id}, first_name='{lead.first_name}', last_name='{lead.last_name}', full_name='{full_name}'")
                                    if full_name and full_name != "ללא שם":
                                        # Extract first name only (max 2 words, skip complex names)
                                        name = extract_first_name(full_name)
                                        if name:
                                            logger.info(f"[NAME_RESOLVE] source=lead_id full_name=\"{full_name}\" first_name=\"{name}\" lead_id={lead_id}")
                                            _orig_print(f"[NAME_RESOLVE] source=lead_id name=\"{name}\" lead_id={lead_id}", flush=True)
                                            return (name, "lead_id")
                                        else:
                                            logger.info(f"[NAME_RESOLVE] source=lead_id skipped complex name: \"{full_name}\"")
                                            _orig_print(f"[NAME_RESOLVE] Lead {lead_id} has complex name, skipped", flush=True)
                                    else:
                                        logger.info(f"[NAME_RESOLVE] Lead {lead_id} exists but has no valid name (first_name='{lead.first_name}', last_name='{lead.last_name}')")
                                        _orig_print(f"[NAME_RESOLVE] Lead {lead_id} has no name", flush=True)
                                else:
                                    logger.info(f"[NAME_RESOLVE] Lead {lead_id} not found in database")
                                    _orig_print(f"[NAME_RESOLVE] Lead {lead_id} not found", flush=True)
                            except Exception as e:
                                logger.warning(f"[NAME_RESOLVE] Failed to query lead by ID: {e}")
                        
                        # Priority 3: OutboundCallJob.lead_name (for bulk calls)
                        if call_sid:
                            job = OutboundCallJob.query.filter_by(twilio_call_sid=call_sid).first()
                            if job and job.lead_name:
                                full_name = str(job.lead_name).strip()
                                if full_name and full_name != "ללא שם":
                                    # Extract first name only (max 2 words, skip complex names)
                                    name = extract_first_name(full_name)
                                    if name:
                                        logger.info(f"[NAME_RESOLVE] source=outbound_job full_name=\"{full_name}\" first_name=\"{name}\" call_sid={call_sid[:8]}")
                                        _orig_print(f"[NAME_RESOLVE] source=outbound_job name=\"{name}\"", flush=True)
                                        return (name, "outbound_job")
                                    else:
                                        logger.info(f"[NAME_RESOLVE] source=outbound_job skipped complex name: \"{full_name}\"")
                                        _orig_print(f"[NAME_RESOLVE] Skipped complex name from outbound_job", flush=True)
                        
                        # Priority 4: Lead.full_name (via CallLog.lead_id)
                        if call_log and call_log.lead_id:
                            lead = Lead.query.get(call_log.lead_id)
                            if lead:
                                full_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                                if full_name and full_name != "ללא שם":
                                    # Extract first name only (max 2 words, skip complex names)
                                    name = extract_first_name(full_name)
                                    if name:
                                        logger.info(f"[NAME_RESOLVE] source=lead_calllog full_name=\"{full_name}\" first_name=\"{name}\" call_sid={call_sid[:8]}")
                                        _orig_print(f"[NAME_RESOLVE] source=lead_calllog name=\"{name}\"", flush=True)
                                        return (name, "lead_calllog")
                                    else:
                                        logger.info(f"[NAME_RESOLVE] source=lead_calllog skipped complex name: \"{full_name}\"")
                                        _orig_print(f"[NAME_RESOLVE] Skipped complex name from lead_calllog", flush=True)
                        
                        # Priority 5: Fallback - Lead lookup by phone number
                        if phone_number:
                            try:
                                # 🔥 CRITICAL: Normalize phone for comparison
                                # Handle both E.164 (+972...) and local (05...) formats
                                # If Twilio gives +9725... but DB has 05..., we must search both
                                
                                phone_variants = [phone_number]  # Start with original
                                
                                # Generate normalized variants
                                cleaned = phone_number.replace('+', '').replace('-', '').replace(' ', '')
                                
                                # If E.164 format (+972...), also try local format (0...)
                                if phone_number.startswith('+972'):
                                    local_format = '0' + cleaned[3:]  # +972501234567 -> 0501234567
                                    phone_variants.append(local_format)
                                # If local format (0...), also try E.164 (+972...)
                                elif phone_number.startswith('0'):
                                    e164_format = '+972' + cleaned[1:]  # 0501234567 -> +972501234567
                                    phone_variants.append(e164_format)
                                
                                logger.debug(f"[NAME_RESOLVE] Phone variants for lookup: {phone_variants}")
                                
                                # Query with all variants (only phone_e164 exists in Lead model)
                                lead = Lead.query.filter_by(
                                    tenant_id=business_id
                                ).filter(
                                    Lead.phone_e164.in_(phone_variants)
                                ).order_by(Lead.updated_at.desc()).first()
                                
                                if lead:
                                    full_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                                    if full_name and full_name != "ללא שם":
                                        # Extract first name only (max 2 words, skip complex names)
                                        name = extract_first_name(full_name)
                                        if name:
                                            logger.info(f"[NAME_RESOLVE] source=lead_phone full_name=\"{full_name}\" first_name=\"{name}\" phone={phone_number} matched={phone_variants}")
                                            _orig_print(f"[NAME_RESOLVE] source=lead_phone name=\"{name}\" phone={phone_number}", flush=True)
                                            return (name, "lead_phone")
                                        else:
                                            logger.info(f"[NAME_RESOLVE] source=lead_phone skipped complex name: \"{full_name}\"")
                                            _orig_print(f"[NAME_RESOLVE] Skipped complex name from lead_phone", flush=True)
                            except Exception as e:
                                logger.warning(f"[NAME_RESOLVE] Failed to query lead by phone: {e}")
                        
                        # Final fallback: No name found
                        logger.info(f"[NAME_RESOLVE] source=none name=None call_sid={call_sid[:8] if call_sid else 'N/A'}")
                        _orig_print(f"[NAME_RESOLVE] source=none name=None", flush=True)
                        return (None, None)
                    
                except Exception as e:
                    logger.error(f"[NAME_RESOLVE] Error resolving name: {e}")
                    logger.exception("Full traceback:")
                    _orig_print(f"[NAME_RESOLVE] Error: {e}", flush=True)
                    return (None, None)
            
            # 🔥 CRITICAL: Resolve customer name from DB for ALL calls (inbound + outbound)
            # This provides name + gender detection for both inbound and outbound calls
            if self.call_sid:
                # Get lead_id from outbound_lead_id (set from customParameters for outbound)
                # For inbound, this may be None but we can still look up by phone
                lead_id = getattr(self, 'outbound_lead_id', None)
                # Convert to int if it's a string
                if lead_id and isinstance(lead_id, str):
                    try:
                        lead_id = int(lead_id)
                    except ValueError:
                        logger.debug(f"[NAME_RESOLVE] Failed to convert lead_id to int: {lead_id}")
                        lead_id = None
                
                # Get phone number for fallback lookup (works for both inbound + outbound)
                phone_number = getattr(self, 'phone_number', None) or getattr(self, 'caller_number', None)
                
                # Call resolution with all available identifiers
                resolved_name, name_source = _resolve_customer_name(
                    self.call_sid, 
                    business_id_safe,
                    lead_id=lead_id,
                    phone_number=phone_number
                )
                
                if resolved_name:
                    # Store in pending_customer_name for NAME_ANCHOR extraction
                    self.pending_customer_name = resolved_name
                    # Also update outbound_lead_name if it was empty (for outbound calls)
                    if call_direction == "outbound" and not outbound_lead_name:
                        self.outbound_lead_name = resolved_name
                        outbound_lead_name = resolved_name
                    
                    # 🆕 GENDER + NOTES: Also fetch gender and notes from same Lead for context
                    try:
                        from server.models_sql import Lead, LeadNote
                        app = _get_flask_app()
                        with app.app_context():
                            lead_for_context = None
                            
                            # Try to find Lead by same identifiers used for name resolution
                            if lead_id:
                                lead_for_context = Lead.query.filter_by(id=lead_id, tenant_id=business_id_safe).first()
                            elif phone_number:
                                # Generate phone variants for lookup
                                phone_variants = [phone_number]
                                cleaned = phone_number.replace('+', '').replace('-', '').replace(' ', '')
                                if phone_number.startswith('+972'):
                                    phone_variants.append('0' + cleaned[3:])
                                elif phone_number.startswith('0'):
                                    phone_variants.append('+972' + cleaned[1:])
                                
                                lead_for_context = Lead.query.filter_by(
                                    tenant_id=business_id_safe
                                ).filter(
                                    Lead.phone_e164.in_(phone_variants)
                                ).order_by(Lead.updated_at.desc()).first()
                            
                            if lead_for_context:
                                # Fetch gender
                                if lead_for_context.gender:
                                    self.pending_customer_gender = lead_for_context.gender
                                    logger.info(f"✅ [GENDER] Fetched from Lead: '{lead_for_context.gender}' (lead_id={lead_for_context.id})")
                                
                                # 🔥 NEW: Fetch lead notes (last 3 notes for context)
                                # Notes provide critical context about customer history, preferences, issues
                                try:
                                    recent_notes = LeadNote.query.filter_by(
                                        lead_id=lead_for_context.id,
                                        tenant_id=business_id_safe
                                    ).order_by(LeadNote.created_at.desc()).limit(3).all()
                                    
                                    if recent_notes:
                                        # Combine notes into single context string
                                        notes_parts = []
                                        for note in recent_notes:
                                            if note.content and note.content.strip():
                                                # Truncate each note to 150 chars for efficiency
                                                note_text = note.content.strip()[:150]
                                                if len(note.content.strip()) > 150:
                                                    note_text += "..."
                                                notes_parts.append(note_text)
                                        
                                        if notes_parts:
                                            combined_notes = " | ".join(notes_parts)
                                            self.pending_lead_notes = combined_notes
                                            logger.info(f"✅ [NOTES] Fetched {len(notes_parts)} notes from Lead (lead_id={lead_for_context.id})")
                                            logger.info(f"📝 [NOTES] Preview: {combined_notes[:100]}...")
                                except Exception as notes_err:
                                    logger.warning(f"[NOTES] Failed to fetch notes: {notes_err}")
                                    logger.error(f"⚠️ [NOTES] Error fetching notes: {notes_err}")
                    except Exception as e:
                        logger.warning(f"[CONTEXT] Failed to fetch lead context (gender/notes): {e}")
                    
                    # 🔥 DEBUG LOG: Show what we resolved
                    logger.debug(f"🎯 [NAME_ANCHOR DEBUG] Resolved from DB ({call_direction}):")
                    logger.info(f"   call_sid: {self.call_sid[:8]}...")
                    logger.info(f"   lead_id from customParameters: {lead_id}")
                    logger.info(f"   phone_number for fallback: {phone_number}")
                    logger.info(f"   resolved_name: {resolved_name}")
                    logger.info(f"   name_source: {name_source}")
                    logger.info(f"   call_direction: {call_direction}")
                    logger.info(f"   pending_customer_name: {self.pending_customer_name}")
                    logger.info(f"   pending_customer_gender: {getattr(self, 'pending_customer_gender', None)}")
                else:
                    # 🔥 DEBUG: Log why resolution failed
                    logger.error(f"⚠️ [NAME_ANCHOR DEBUG] Name resolution FAILED ({call_direction}):")
                    logger.info(f"   call_sid: {self.call_sid[:8]}...")
                    logger.info(f"   lead_id from customParameters: {lead_id}")
                    logger.info(f"   phone_number for fallback: {phone_number}")
                    logger.info(f"   call_direction: {call_direction}")
                    logger.info(f"   Result: No name found in any source")
            
            # 🔒 LOG BUSINESS ISOLATION: Confirm which business is being used for this OpenAI session
            logger.info(f"[BUSINESS_ISOLATION] openai_session_start business_id={business_id_safe} call_sid={self.call_sid}")
            _orig_print(f"🔒 [BUSINESS_ISOLATION] OpenAI session for business {business_id_safe}", flush=True)
            
            # 🔥 NEW: Set agent context for Realtime API tool calls
            # This allows tools like schedule_appointment to access call metadata
            # Note: This only works when called within a Flask request context.
            # WebSocket handlers may not have access to g, which is acceptable.
            try:
                caller_phone = getattr(self, 'phone_number', None) or getattr(self, 'caller_number', None)
                # Store in instance for tools that need it
                self.agent_context = {
                    'business_id': business_id_safe,
                    'business_name': biz_name,
                    'caller_number': caller_phone,
                    'from_number': caller_phone,
                    'customer_phone': caller_phone,
                    'channel': 'phone',
                    'call_sid': self.call_sid,
                    'call_direction': call_direction,
                    'business_prompt': None,  # Will be set after prompt is loaded
                }
                logger.info(f"✅ [AGENT_CONTEXT] Agent context stored for Realtime tools: business={business_id_safe}, phone={caller_phone}")
            except Exception as ctx_err:
                # Not critical for call to proceed - tools will work without context
                logger.warning(f"⚠️ [AGENT_CONTEXT] Failed to set agent context: {ctx_err}")
                pass
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 LATENCY-FIRST: FULL PROMPT ONLY from the very first second
            # Strategy: Load pre-built FULL prompt from registry (built in webhook)
            # Send IMMEDIATELY in session.update - AI is "loaded" before first word
            # NO COMPACT, NO UPGRADE, NO PROMPT REPLACEMENT mid-conversation
            # ═══════════════════════════════════════════════════════════════════════
            
            from server.stream_state import stream_registry
            
            # Step 1: Load FULL BUSINESS prompt from registry (built in webhook - ZERO latency!)
            full_prompt = stream_registry.get_metadata(self.call_sid, '_prebuilt_full_prompt') if self.call_sid else None
            prebuilt_direction = stream_registry.get_metadata(self.call_sid, '_prebuilt_direction') if self.call_sid else None
            
            # Step 2: Validate or rebuild
            if not full_prompt:
                logger.warning(f"⚠️ [PROMPT] Pre-built FULL prompt not found in registry - building fresh from DB")
                logger.debug(f"🔍 [PROMPT_DEBUG] Missing prebuilt for call_direction={call_direction}")
                # Build fresh from DB
                from server.services.realtime_prompt_builder import build_realtime_system_prompt
                full_prompt = build_realtime_system_prompt(business_id_safe, call_direction=call_direction, use_cache=True)
            else:
                logger.info(f"🚀 [PROMPT] Using PRE-BUILT FULL prompt from registry (LATENCY-FIRST)")
                logger.info(f"   └─ FULL: {len(full_prompt)} chars (sent ONCE at start)")
                
                # 🔥 CRITICAL: Validate direction matches - REBUILD if mismatch
                if prebuilt_direction and prebuilt_direction != call_direction:
                    logger.error(f"❌ [PROMPT_MISMATCH] Direction mismatch detected!")
                    logger.info(f"   Expected: {call_direction}, Pre-built for: {prebuilt_direction}")
                    logger.info(f"   🔄 REBUILDING with correct direction from DB")
                    _orig_print(f"[PROMPT_MISMATCH] call_sid={self.call_sid[:8]}... expected={call_direction} prebuilt={prebuilt_direction} action=REBUILD", flush=True)
                    
                    # Rebuild with correct direction
                    from server.services.realtime_prompt_builder import build_realtime_system_prompt
                    full_prompt = build_realtime_system_prompt(business_id_safe, call_direction=call_direction, use_cache=False)
                    logger.info(f"   ✅ Rebuilt prompt: {len(full_prompt)} chars")
                else:
                    logger.info(f"✅ [PROMPT_VERIFY] Pre-built prompt matches call direction: {call_direction}")
                    _orig_print(f"[PROMPT_BIND] call_sid={self.call_sid[:8]}... direction={call_direction} status=MATCHED", flush=True)
            
            # Use FULL prompt immediately - no compact, no upgrade
            greeting_prompt_to_use = full_prompt
            logger.info(f"🎯 [LATENCY-FIRST] Using FULL prompt from start: {len(greeting_prompt_to_use)} chars")
            logger.info(f"[PROMPT-LOADING] business_id={business_id_safe} direction={call_direction} source=registry strategy=FULL_ONLY")
            
            # 🔥 NEW: Update agent_context with business prompt
            try:
                if hasattr(self, 'agent_context') and isinstance(self.agent_context, dict):
                    self.agent_context['business_prompt'] = full_prompt
                    logger.info(f"✅ [AGENT_CONTEXT] Updated with business_prompt ({len(full_prompt)} chars)")
            except Exception:
                pass  # Not critical
            
            # 🔥 CRITICAL LOGGING: Verify business isolation
            if full_prompt and f"Business ID: {business_id_safe}" in full_prompt:
                logger.info(f"✅ [BUSINESS ISOLATION] Verified business_id={business_id_safe} in FULL BUSINESS prompt")
            elif full_prompt:
                logger.warning(f"⚠️ [BUSINESS ISOLATION] Business ID marker not found in FULL BUSINESS prompt")
            
            logger.info(f"📊 [PROMPT STATS] full={len(full_prompt)} chars (SENT ONCE at start)")
            
            # 🔥 FINAL: Set greeting prompt to FULL
            # No compact, no upgrade - AI gets full context from the start
            greeting_prompt = greeting_prompt_to_use
            has_custom_greeting = True

            
            t_before_config = time.time()
            logger.info(f"[CALL DEBUG] PHASE 1: Configure with greeting prompt...")
            
            # 🎯 VOICE LIBRARY: Load voice from business settings (per-business voice selection)
            # Get voice_id from business via CallContext (cached, no DB query)
            # Fallback chain: business.voice_id -> DEFAULT_VOICE
            
            # Try to get voice from cached call context first (avoids DB query)
            call_voice = DEFAULT_VOICE  # Default fallback
            if self.call_ctx_loaded and self.call_ctx:
                call_voice = getattr(self.call_ctx, 'business_voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
                logger.info(f"🎤 [VOICE_LIBRARY] Using cached voice from CallContext: {call_voice}")
            else:
                # Fallback: Load business from DB if cache not available
                try:
                    from server.models_sql import Business
                    business = Business.query.get(business_id_safe)
                    if business:
                        business_voice = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
                        # Validate voice is in allowed list
                        if business_voice in OPENAI_VOICES:
                            call_voice = business_voice
                        else:
                            logger.warning(f"[AI][VOICE_FALLBACK] invalid_voice db_value={business_voice} fallback={DEFAULT_VOICE}")
                            call_voice = DEFAULT_VOICE
                        logger.info(f"🎤 [VOICE_LIBRARY] Loaded voice from DB: {call_voice}")
                except Exception as e:
                    logger.warning(f"[VOICE_LIBRARY] Failed to load voice from DB: {e}, using default: {DEFAULT_VOICE}")
                    call_voice = DEFAULT_VOICE
            
            # Validate voice is in allowed list (final safety check)
            # 🔥 CRITICAL: Only use Realtime-supported voices to prevent session.update timeouts
            if call_voice not in REALTIME_VOICES:
                logger.warning(f"[AI][VOICE_FALLBACK] invalid_voice value={call_voice} fallback={DEFAULT_VOICE} (not in REALTIME_VOICES)")
                _orig_print(f"⚠️ [VOICE_VALIDATION] Rejecting unsupported voice '{call_voice}' -> fallback to '{DEFAULT_VOICE}'")
                call_voice = DEFAULT_VOICE
            
            self._call_voice = call_voice  # Store for session.update reuse
            logger.info(f"🎤 [VOICE] Using voice={call_voice} for entire call (business={self.business_id})")
            logger.info(f"[VOICE_LIBRARY] Call voice selected: {call_voice} for business {business_id_safe}")
            
            # 🔥 FIX: Calculate max_tokens based on greeting length
            # Long greetings (14 seconds = ~280 words in Hebrew) need 500+ tokens
            # 🔥 BUILD 178: For outbound calls, use greeting_prompt length instead of greeting_text
            # 🔥 BUILD 179: Outbound calls need MUCH higher token limits for sales pitches!
            if call_direction == 'outbound':
                greeting_length = len(greeting_prompt) if greeting_prompt else 100
            else:
                greeting_length = len(greeting_text) if (has_custom_greeting and greeting_text) else 0
            
            # 🔥 BUILD 329: REVERTED - Let OpenAI handle token limits naturally
            # User reported reduced max_tokens causes AI silence!
            # OpenAI knows how to manage tokens efficiently
            greeting_max_tokens = 4096
            logger.info(f"🎤 [GREETING] max_tokens={greeting_max_tokens} (direction={call_direction})")
            
            # 🔥 BUILD 316: NO STT PROMPT - Let OpenAI transcribe naturally!
            # Vocabulary prompts were causing hallucinations with business names
            # Pure approach: language="he" + no prompt = best accuracy
            logger.info(f"🎤 [BUILD 316] ULTRA SIMPLE STT: language=he, NO vocabulary prompt")
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 STEP 0.5: Build tools BEFORE session.update (must be included in FIRST update!)
            # ═══════════════════════════════════════════════════════════════════════
            # 🎯 SMART TOOL SELECTION: Check if appointment tool should be enabled
            # Realtime phone calls: NO tools by default, ONLY appointment tool when enabled
            # 🔥 CRITICAL FIX: Tools MUST be included in FIRST session.update to avoid losing context!
            # Sending a second session.update later causes OpenAI to reset the conversation context!
            realtime_tools = []
            tool_choice = "auto"
            
            try:
                logger.debug(f"[REALTIME] Building tools for call...")
                realtime_tools = self._build_realtime_tools_for_call()
                logger.debug(f"[REALTIME] Tools built successfully: count={len(realtime_tools)}")
                
                if realtime_tools:
                    logger.info(f"[TOOLS][REALTIME] Appointment tools ENABLED - count={len(realtime_tools)} (will be sent in FIRST session.update)")
                    logger.debug(f"[TOOLS][REALTIME] Tools will be included in initial session configuration")
                else:
                    logger.info(f"[TOOLS][REALTIME] NO tools for this call (disabled or not applicable)")
                    
            except Exception as tools_error:
                logger.error(f"[REALTIME] Failed to build tools - continuing with empty tools: {tools_error}")
                import traceback
                traceback.print_exc()
                realtime_tools = []  # Safe fallback - no tools
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 STEP 1: Start RX loop BEFORE session.update to prevent event loss
            # ═══════════════════════════════════════════════════════════════════════
            _orig_print(f"🚀 [RX_LOOP] Starting receiver task BEFORE session.update (prevents event loss)", flush=True)
            logger.debug(f"[REALTIME] Starting receiver loop before session configuration")
            
            # Initialize flag to track when RX loop is ready
            self._recv_loop_started = False
            
            audio_out_task = asyncio.create_task(self._realtime_audio_receiver(client))
            
            # Wait for RX loop to signal it's listening (max 2 seconds)
            rx_wait_start = time.time()
            rx_max_wait = 2.0
            while not self._recv_loop_started:
                if time.time() - rx_wait_start > rx_max_wait:
                    _orig_print(f"⚠️ [RX_LOOP] Timeout waiting for recv_loop_started flag - proceeding anyway", flush=True)
                    break
                await asyncio.sleep(0.01)  # Check every 10ms
            
            rx_ready_ms = (time.time() - rx_wait_start) * 1000
            _orig_print(f"✅ [RX_LOOP] Receiver loop confirmed ready in {rx_ready_ms:.0f}ms - safe to send session.update", flush=True)
            
            # Send initial session configuration
            _orig_print(f"📤 [SESSION] Sending session.update with config...", flush=True)
            
            # 🔥 CRITICAL: Clear event and flags before sending session.update
            # This ensures we wait for THIS session.updated, not a stale one
            self._session_config_confirmed = False
            self._session_config_failed = False
            self._session_config_event.clear()  # Clear any previous event
            _orig_print(f"🔄 [SESSION] Cleared session flags - waiting for fresh confirmation", flush=True)
            
            await _send_session_config(client, greeting_prompt, call_voice, greeting_max_tokens, tools=realtime_tools, tool_choice=tool_choice, send_reason="initial")
            _orig_print(f"✅ [SESSION] session.update sent - waiting for confirmation", flush=True)
            
            # 🔒 PROMPT INTEGRITY: Store business prompt hash for final verification
            import hashlib
            self._business_prompt_hash = hashlib.md5(greeting_prompt.encode()).hexdigest()[:8]
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 STEP 3: Event-driven wait for session.updated confirmation
            # ═══════════════════════════════════════════════════════════════════════
            # CRITICAL: Wait for session.updated confirmation before proceeding
            # This prevents race condition where response.create is sent before session is configured
            # Without this wait: PCM16 audio (noise) + English responses + no instructions
            _orig_print(f"⏳ [SESSION] Waiting for session.updated confirmation (max 8s with retry)...", flush=True)
            wait_start = time.time()
            max_wait = 8.0  # Maximum 8 seconds total
            retry_at = 3.0  # Retry after 3 seconds if no response
            retried = False
            
            # 🔥 PERFORMANCE FIX: Use event-driven wait instead of polling
            # This eliminates CPU waste and reduces latency from 50ms to <1ms
            while True:
                # Check if session configuration failed
                if getattr(self, '_session_config_failed', False):
                    _orig_print(f"🚨 [SESSION] Configuration FAILED - aborting call", flush=True)
                    raise RuntimeError("Session configuration failed - cannot proceed with call")
                
                # Check timeout
                elapsed = time.time() - wait_start
                
                # Retry logic: Send session.update again if no response within 3s
                if elapsed >= retry_at and not retried:
                    retried = True
                    _orig_print(f"⏰ [SESSION] No session.updated after {retry_at}s - retrying session.update", flush=True)
                    # 🔥 FIX 3: Pass force=True to bypass hash check on retry
                    await _send_session_config(client, greeting_prompt, call_voice, greeting_max_tokens, tools=realtime_tools, tool_choice=tool_choice, force=True, send_reason="retry")
                    _orig_print(f"📤 [SESSION] Retry session.update sent with force=True - continuing to wait", flush=True)
                
                if elapsed > max_wait:
                    _orig_print(f"🚨 [SESSION] Timeout waiting for session.updated ({max_wait}s, retried={retried}) - aborting", flush=True)
                    raise RuntimeError(f"Session configuration timeout after {max_wait}s - cannot proceed")
                
                # 🔥 PERFORMANCE: Use event-driven wait with timeout
                # This is MUCH faster than polling (reacts instantly, no CPU waste)
                remaining_time = max_wait - elapsed
                try:
                    # Wait for event with timeout (returns True if set, False if timeout)
                    await asyncio.wait_for(
                        self._session_config_event.wait(),
                        timeout=min(0.1, remaining_time)  # Check every 100ms for failure/timeout
                    )
                    # Event was set - session confirmed!
                    break
                except asyncio.TimeoutError:
                    # Timeout - check flags and retry logic in next iteration
                    continue
            
            session_wait_ms = (time.time() - wait_start) * 1000
            _orig_print(f"✅ [SESSION] session.updated confirmed in {session_wait_ms:.0f}ms (retried={retried}) - safe to proceed", flush=True)
            
            # 🔥 NEW: Mark timestamp for latency measurement
            t_session_confirmed = time.time()

            # ─────────────────────────────────────────────────────────────────────
            # 🔥 ARCHITECTURE DECISION: System Prompt in session.update ONLY
            # ─────────────────────────────────────────────────────────────────────
            # System behavior rules are included in session.update.instructions (FULL prompt).
            # NO separate conversation.item.create for system rules.
            # This prevents duplication and ensures single source of truth.
            #
            # REMOVED: Global system prompt injection via conversation.item.create
            # All system rules are now part of the FULL prompt sent in session.update.
            # ─────────────────────────────────────────────────────────────────────
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 🔥 NAME ANCHOR SYSTEM: Persistent customer name + usage policy
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # This replaces the old CRM context injection with a permanent NAME_ANCHOR
            # that tells the AI:
            # 1. The customer's actual name (if available)
            # 2. Whether to use it (based on business prompt analysis)
            # 3. How to use it (naturally, not in every sentence)
            
            # 🔥 USE CENTRALIZED VALIDATION: Imported from name_validation module
            # All name validation uses single source of truth - no local duplicates
            
            def _extract_customer_name() -> Optional[str]:
                """Extract customer name from available sources."""
                # Source 1: outbound_lead_name (for outbound calls)
                if outbound_lead_name and str(outbound_lead_name).strip():
                    name = str(outbound_lead_name).strip()
                    if is_valid_customer_name(name):
                        return name
                
                # Source 2: crm_context (if already available)
                if hasattr(self, 'crm_context') and self.crm_context:
                    if hasattr(self.crm_context, 'customer_name') and self.crm_context.customer_name:
                        name = str(self.crm_context.customer_name).strip()
                        if is_valid_customer_name(name):
                            return name
                
                # Source 3: pending_customer_name (if stored)
                if hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    name = str(self.pending_customer_name).strip()
                    if is_valid_customer_name(name):
                        return name
                
                return None
            
            try:
                # Step 1: Detect name usage policy from business prompt (once per session)
                from server.services.realtime_prompt_builder import detect_name_usage_policy
                
                # Use the FULL business prompt for policy detection
                # (no compact prompt anymore - we use FULL from the start)
                business_prompt_for_policy = full_prompt
                use_name_policy, matched_phrase = detect_name_usage_policy(business_prompt_for_policy)
                
                # Store policy in session (persistent across PROMPT_UPGRADE)
                self.use_name_policy = use_name_policy
                
                # Log policy determination with source
                logger.info(f"[NAME_POLICY] source=business_prompt result={use_name_policy} matched=\"{matched_phrase or 'none'}\"")
                logger.info(f"🎯 [NAME_POLICY] source=business_prompt result={use_name_policy} (matched: '{matched_phrase or 'none'}')")
                _orig_print(f"[NAME_POLICY] source=business_prompt result={use_name_policy} matched=\"{matched_phrase or 'none'}\"", flush=True)
                
                # Step 2: Extract customer name
                customer_name_to_inject = _extract_customer_name()
                
                # 🔥 ENHANCED DEBUG: Show comprehensive name resolution state
                logger.debug(f"🔍 [NAME_ANCHOR DEBUG] Extraction attempt:")
                logger.info(f"   call_sid: {self.call_sid[:8] if self.call_sid else 'N/A'}...")
                logger.info(f"   business_id: {business_id_safe}")
                logger.info(f"   call_direction: {call_direction}")
                logger.info(f"   outbound_lead_name: {outbound_lead_name}")
                logger.info(f"   crm_context exists: {hasattr(self, 'crm_context') and self.crm_context is not None}")
                logger.info(f"   pending_customer_name: {getattr(self, 'pending_customer_name', None)}")
                logger.info(f"   extracted name: {customer_name_to_inject}")
                logger.info(f"   use_name_policy: {use_name_policy}")
                
                # 🔥 CRITICAL: Do NOT inject NAME_ANCHOR if name is None or invalid
                # This prevents the bug where we inject "name='None'" into the conversation
                if customer_name_to_inject is None:
                    logger.warning(f"⚠️ [NAME_ANCHOR] Skipping injection - no valid customer name found")
                    logger.info(f"[NAME_ANCHOR] skipped reason=no_name call_sid={self.call_sid[:8] if self.call_sid else 'N/A'}")
                    _orig_print(f"[NAME_ANCHOR] skipped reason=no_name", flush=True)
                else:
                    # Step 3: Build and inject NAME_ANCHOR (idempotent with hash)
                    # 🔥 ANTI-DUPLICATE: Calculate hash fingerprint
                    import hashlib
                    name_anchor_hash = f"{customer_name_to_inject}|{use_name_policy}"
                    name_anchor_hash_short = hashlib.md5(name_anchor_hash.encode()).hexdigest()[:8]
                    
                    # Check if this exact anchor was already injected
                    existing_hash = getattr(self, '_name_anchor_hash', None)
                    if existing_hash != name_anchor_hash_short:
                        from server.services.realtime_prompt_builder import build_name_anchor_message, detect_gender_from_name
                        
                        # 🧠 GENDER DETECTION: Priority order (SSOT)
                        # 1. pending_customer_gender (from early Lead lookup)
                        # 2. Database (if manually set or detected from previous conversation)
                        # 3. Name-based detection (if not unisex)
                        customer_gender = None
                        
                        # Priority 0: Check if we already fetched gender during name resolution
                        if hasattr(self, 'pending_customer_gender') and self.pending_customer_gender:
                            customer_gender = self.pending_customer_gender
                            logger.info(f"[GENDER_DETECT] Using pending gender from early lookup: {customer_gender}")
                            logger.info(f"🧠 [GENDER] Using pending: {customer_gender}")
                        
                        # Priority 1: Check database for saved gender (fallback if pending not available)
                        if not customer_gender:
                            try:
                                from server.models_sql import CallLog, Lead
                                app = _get_flask_app()
                                with app.app_context():
                                    call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                                    lead = None
                                    
                                    if call_log and call_log.lead_id:
                                        lead = Lead.query.get(call_log.lead_id)
                                    elif hasattr(self, 'outbound_lead_id') and self.outbound_lead_id:
                                        lead = Lead.query.get(self.outbound_lead_id)
                                    
                                    if lead and lead.gender:
                                        customer_gender = lead.gender
                                        logger.info(f"[GENDER_DETECT] Using saved gender from database: {customer_gender} (Lead {lead.id})")
                                        logger.info(f"🧠 [GENDER] Using saved: {customer_gender} from Lead {lead.id}")
                            except Exception as e:
                                logger.warning(f"[GENDER_DETECT] Error checking database gender: {e}")
                        
                        # Priority 2: Detect from name (only if not in database)
                        if not customer_gender:
                            customer_gender = detect_gender_from_name(customer_name_to_inject)
                            if customer_gender:
                                logger.info(f"[GENDER_DETECT] Detected from name: {customer_gender} for '{customer_name_to_inject}'")
                                logger.info(f"🧠 [GENDER] Detected from name: {customer_gender} for '{customer_name_to_inject}'")
                            else:
                                logger.info(f"[GENDER_DETECT] Cannot determine gender from name: '{customer_name_to_inject}' (unisex or unknown)")
                                logger.info(f"🧠 [GENDER] Unknown/unisex name: '{customer_name_to_inject}' (will wait for conversation)")
                        
                        # 🔥 NEW: Get lead notes if available (fetched during name resolution)
                        lead_notes = getattr(self, 'pending_lead_notes', None)
                        
                        name_anchor_text = build_name_anchor_message(
                            customer_name_to_inject, 
                            use_name_policy, 
                            customer_gender,
                            lead_notes  # 🔥 NEW: Pass notes to context builder
                        )
                        
                        # Inject as conversation system message
                        name_anchor_event = await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": name_anchor_text,
                                        }
                                    ],
                                },
                            }
                        )
                        
                        # Store injection state with hash
                        self._name_anchor_injected = True
                        self._name_anchor_customer_name = customer_name_to_inject
                        self._name_anchor_policy = use_name_policy
                        self._name_anchor_hash = name_anchor_hash_short
                        self._name_anchor_count = getattr(self, '_name_anchor_count', 0) + 1
                        
                        # Get item_id if available from response
                        item_id = name_anchor_event.get('item', {}).get('id', 'unknown') if isinstance(name_anchor_event, dict) else 'unknown'
                        
                        # Log injection with hash
                        logger.info(f"[NAME_ANCHOR] injected enabled={use_name_policy} name=\"{customer_name_to_inject}\" item_id={item_id} hash={name_anchor_hash_short}")
                        logger.info(f"✅ [NAME_ANCHOR] Injected: enabled={use_name_policy}, name='{customer_name_to_inject}', hash={name_anchor_hash_short}")
                        _orig_print(f"[NAME_ANCHOR] injected enabled={use_name_policy} name=\"{customer_name_to_inject}\" hash={name_anchor_hash_short}", flush=True)
                    else:
                        logger.info(f"ℹ️ [NAME_ANCHOR] Skip duplicate (hash={name_anchor_hash_short} already injected)")
                        logger.debug(f"[NAME_ANCHOR] skip_duplicate hash={name_anchor_hash_short}")
                    
            except Exception as e:
                # Do not fail call if NAME_ANCHOR injection fails
                logger.error(f"[NAME_ANCHOR] Failed to inject NAME_ANCHOR: {e}")
                import traceback
                traceback.print_exc()
            
            # 🔥 PROMPT_SUMMARY: Single-line summary of all injected prompts
            # System rules are now part of FULL prompt (session.update), not separate
            system_count = 0  # No separate system injection (included in FULL prompt)
            business_count = 1  # FULL prompt sent in session.update
            name_count = getattr(self, '_name_anchor_count', 0)
            system_hash = 'in_full_prompt'  # System rules included in business prompt
            business_hash = hash_prompt(full_prompt) if full_prompt else 'none'
            name_hash = getattr(self, '_name_anchor_hash', 'none')
            
            _orig_print(f"[PROMPT_SUMMARY] system=0 (in_full) business={business_count} name_anchor={name_count} hashes: biz={business_hash}, name={name_hash}", flush=True)
            logger.info(f"[PROMPT_SUMMARY] Prompt injection summary at call start: system=0 (included in FULL), business={business_count}, name_anchor={name_count}")
            
            # 🔥 PROMPT_BIND LOGGING: Track prompt binding (should happen ONCE per call)
            import hashlib
            prompt_hash = hashlib.md5(greeting_prompt.encode()).hexdigest()[:8]
            logger.info(f"🔒 [PROMPT_BIND] business_id={business_id_safe} direction={call_direction} hash={prompt_hash} binding=INITIAL")
            _orig_print(f"[PROMPT_BIND] call_sid={self.call_sid[:8]}... business_id={business_id_safe} direction={call_direction} hash={prompt_hash}", flush=True)
            
            t_after_config = time.time()
            config_ms = (t_after_config - t_before_config) * 1000
            total_ms = (t_after_config - t_start) * 1000
            logger.info(f"⏱️ [PHASE 1] Session configured in {config_ms:.0f}ms (total: {total_ms:.0f}ms)")
            logger.info(f"✅ [REALTIME] FAST CONFIG: greeting prompt ready, voice={call_voice}")
            
            # 🔥 MASTER FIX: ALWAYS trigger greeting immediately - no flag checks!
            # Bot speaks first is now HARDCODED behavior for all calls
            logger.info(f"[REALTIME] ENFORCING bot_speaks_first=True (hardcoded)")
            
            # 🔥 MASTER FIX: Store OpenAI connect metric
            from server.stream_state import stream_registry
            if hasattr(self, '_metrics_openai_connect_ms') and self.call_sid:
                stream_registry.set_metric(self.call_sid, 'openai_connect_ms', self._metrics_openai_connect_ms)
            
            # 🔥 MASTER FIX: Always trigger greeting (hardcoded bot-first behavior)
            greeting_start_ts = time.time()
            logger.info(f"🎤 [GREETING] Bot speaks first - triggering greeting at {greeting_start_ts:.3f}")
            self.greeting_sent = True  # Mark greeting as sent to allow audio through
            self.is_playing_greeting = True
            self.greeting_mode_active = True  # 🎯 FIX A: Enable greeting mode for FIRST response only
            # 🔥 REMOVED: greeting_lock mechanism - allow audio through during greeting
            self._greeting_start_ts = greeting_start_ts  # Store for duration logging
            # ✅ CRITICAL: Wait until Twilio streamSid exists before greeting trigger (inbound + outbound)
            # This ensures the first audio frames can be delivered immediately to the caller.
            sid_wait_start = time.time()
            while not getattr(self, "stream_sid", None) and (time.time() - sid_wait_start) < 2.0:
                await asyncio.sleep(0.01)

            # 🔥 BUILD 200: Use trigger_response for greeting (forced, no user_speaking/user_has_spoken dependency)
            triggered = await self.trigger_response("GREETING", client, is_greeting=True, force=True)
            if triggered:
                t_speak = time.time()
                total_openai_ms = (t_speak - t_start) * 1000
                
                # 🔥 LATENCY METRIC: session.updated → greeting time
                session_to_greeting_ms = int((t_speak - t_session_confirmed) * 1000)
                _orig_print(f"⏱️ [LATENCY] session.updated → greeting = {session_to_greeting_ms}ms (should be <{self.MAX_SESSION_TO_GREETING_MS}ms)", flush=True)

                # ═══════════════════════════════════════════════════════════════════════
                # 🔥 PART D: Detailed timing breakdown for latency analysis
                # ═══════════════════════════════════════════════════════════════════════
                t0 = getattr(self, "t0_connected", t_start)  # WS open time
                connect_delta = int((t_connected - t_start) * 1000)
                try:
                    wait_delta = int((t_ready - t_connected) * 1000)
                except NameError:
                    wait_delta = 0  # t_ready not defined (timeout case)
                config_delta = int((t_after_config - t_before_config) * 1000)
                total_from_t0 = int((t_speak - t0) * 1000)

                _orig_print(
                    f"⏱️ [LATENCY BREAKDOWN] connect={connect_delta}ms, wait_biz={wait_delta}ms, config={config_delta}ms, total={total_openai_ms:.0f}ms (T0→greeting={total_from_t0}ms)",
                    flush=True,
                )
                logger.info(f"🎯 [BUILD 200] GREETING response.create sent! OpenAI time: {total_openai_ms:.0f}ms")
            else:
                logger.error(f"❌ [BUILD 200] Failed to trigger greeting via trigger_response")
                # Reset flags since greeting failed
                self.greeting_sent = False
                self.is_playing_greeting = False

            # 🚀 Start audio/text bridges after greeting trigger attempt:
            # - If greeting triggered: start immediately after trigger to enforce "bot speaks first"
            # - If greeting failed: still start so the call can proceed
            logger.debug("[REALTIME] Starting audio/text sender tasks (post-greeting trigger attempt)...")
            audio_in_task = asyncio.create_task(self._realtime_audio_sender(client))
            text_in_task = asyncio.create_task(self._realtime_text_sender(client))
            logger.debug("[REALTIME] Audio/text tasks created successfully")
            
            # 🔥 SILENCE WATCHDOG: Start 20-second silence monitoring task
            # Reset activity timestamp to start countdown from NOW (not from object creation)
            # This ensures watchdog doesn't falsely disconnect during initial greeting/setup
            self._last_activity_ts = time.time()
            logger.debug("[SILENCE_WATCHDOG] Starting silence watchdog task...")
            self._silence_watchdog_task = asyncio.create_task(self._silence_watchdog())
            logger.debug("[SILENCE_WATCHDOG] Watchdog task created successfully")

            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME STABILITY: Greeting audio timeout watchdog (only when greeting triggered)
            # ═══════════════════════════════════════════════════════════════════════
            if triggered:
                async def _greeting_audio_timeout_watchdog():
                    """Monitor for greeting audio timeout - cancel if no audio within timeout window."""
                    watchdog_start = time.time()
                    timeout_sec = self._greeting_audio_timeout_sec

                    # Wait for greeting audio or timeout
                    while (time.time() - watchdog_start) < timeout_sec:
                        # Check if we received greeting audio
                        if self._greeting_audio_received:
                            # Greeting audio arrived - success!
                            return

                        # Check if greeting is no longer playing (user barged in, etc.)
                        if not self.is_playing_greeting:
                            return

                        # Check if realtime already failed
                        if self.realtime_failed:
                            return

                        await asyncio.sleep(0.1)  # Check every 100ms

                    # Timeout reached - check if audio ever arrived
                    if not self._greeting_audio_received and self.is_playing_greeting:
                        elapsed_ms = int((time.time() - watchdog_start) * 1000)
                        _orig_print(f"⚠️ [GREETING] NO_AUDIO_FROM_OPENAI ({elapsed_ms}ms) - canceling greeting", flush=True)
                        logger.warning(f"[GREETING] No audio from OpenAI after {elapsed_ms}ms - canceling greeting")

                        # Cancel the greeting - let call continue without it
                        self.is_playing_greeting = False
                        self.greeting_sent = True  # Mark as done so we don't retry
                        self.barge_in_enabled_after_greeting = True  # Allow barge-in

                        # Don't set realtime_failed - the call can still proceed.
                        # Just skip the greeting and let user audio through.
                        _orig_print("⚠️ [GREETING] GREETING_SKIPPED - continuing call without greeting", flush=True)

                # Start the watchdog
                asyncio.create_task(_greeting_audio_timeout_watchdog())
            
            # 📋 CRM: Initialize context in background (non-blocking for voice)
            # This runs in background thread while AI is already speaking
            customer_phone = getattr(self, 'phone_number', None) or getattr(self, 'customer_phone_dtmf', None)
            
            # 🔥 BUILD 174: For outbound calls, use the pre-existing lead_id
            outbound_lead_id = getattr(self, 'outbound_lead_id', None)
            call_direction = getattr(self, 'call_direction', 'inbound')
            
            if customer_phone or outbound_lead_id:
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 🔥 DISABLED: Legacy CRM context injection (replaced by NAME_ANCHOR)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # This background thread CRM init is DISABLED.
                # Customer name is now injected ONLY via NAME_ANCHOR at call start.
                # This prevents duplicate injections and reduces model confusion.
                pass  # 🔥 NO-OP: CRM context injection disabled
            else:
                logger.warning(f"⚠️ [CRM] No customer phone or lead_id - skipping lead creation")
                self.crm_context = None
            
            logger.debug(f"[REALTIME] Entering main audio/text loop (gather tasks)...")
            await asyncio.gather(audio_in_task, audio_out_task, text_in_task, self._silence_watchdog_task)
            logger.debug(f"[REALTIME] Main audio/text loop completed")
            
        except Exception as e:
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME_FATAL: Critical exception in async loop
            # ═══════════════════════════════════════════════════════════════════════
            import traceback
            tb_str = traceback.format_exc()
            _orig_print(f"🔥 [REALTIME_FATAL] Unhandled exception in _run_realtime_mode_async: {e}", flush=True)
            _orig_print(f"🔥 [REALTIME_FATAL] call_sid={self.call_sid}", flush=True)
            traceback.print_exc()
            logger.error(f"[REALTIME_FATAL] Unhandled exception in async loop: {e}")
            logger.error(f"[REALTIME_FATAL] Full traceback:\n{tb_str}")
            
            # Mark realtime as failed
            self.realtime_failed = True
            self._realtime_failure_reason = f"ASYNC_EXCEPTION: {type(e).__name__}"
        finally:
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME STABILITY: Log final metrics
            # ═══════════════════════════════════════════════════════════════════════
            # Log timing metrics at end of call
            logger.debug(f"[METRICS] REALTIME_TIMINGS: openai_connect_ms={self._metrics_openai_connect_ms}, first_greeting_audio_ms={self._metrics_first_greeting_audio_ms}, realtime_failed={self.realtime_failed}")
            
            # 🔒 FINAL PROMPT INTEGRITY SUMMARY
            # This log confirms that prompts were sent exactly once with no duplications
            # NOTE: System rules are now part of FULL prompt (no separate injection)
            name_injected = 1 if getattr(self, '_name_anchor_hash', None) else 0
            business_hash = hash_prompt(full_prompt) if full_prompt else 'none'
            
            _orig_print(
                f"[PROMPT_FINAL_SUMMARY] system=0 (in_full) universal=0 "
                f"business=1 name_anchor={name_injected} business_hash={business_hash}",
                flush=True
            )
            logger.info(
                f"[PROMPT_FINAL_SUMMARY] system=0 (included in FULL) universal=0 "
                f"business=1 name_anchor={name_injected}"
            )
            
            # 💰 COST TRACKING: Use centralized cost calculation
            self._calculate_and_log_cost()
            
            if client:
                # 🔥 BUILD 331: Pass reason for disconnect logging
                disconnect_reason = "limit_exceeded" if getattr(self, 'realtime_stop_flag', False) else "normal_end"
                await client.disconnect(reason=disconnect_reason)
                logger.info(f"🔌 [REALTIME] Disconnected")
                logger.info(f"[CALL DEBUG] OpenAI Realtime disconnected")
    
    async def _realtime_audio_sender(self, client):
        """
        Send audio from Twilio to Realtime API
        
        ═══════════════════════════════════════════════════════════════════════
        🔥 BUILD 200: SINGLE AUDIO PIPELINE - This is the ONLY audio path!
        ═══════════════════════════════════════════════════════════════════════
        
        Twilio Media (μ-law base64)
             ↓
        media frame handler (ws_handler → process_twilio_frame)
             ↓
        enqueue to realtime_audio_in_queue   # exactly one queue
             ↓
        THIS FUNCTION (audio sender task)    # single loop
             ↓
        client.send_audio_chunk(...)         # OpenAI Realtime
        
        ═══════════════════════════════════════════════════════════════════════
        """
        logger.info(f"[PIPELINE] LIVE AUDIO PIPELINE ACTIVE: Twilio → realtime_audio_in_queue → send_audio_chunk (single path)")
        
        # 🛡️ BUILD 168.5: Track if we've logged the greeting block message
        _greeting_block_logged = False
        _greeting_resumed_logged = False
        # 🔴 GREETING_LOCK (HARD): Do NOT send/commit or buffer user audio during greeting.
        # Requirement (NO-BARGE-IN on greeting): user speech during greeting must be ignored and NOT
        # leak into transcription after greeting ends.
        if not hasattr(self, "_greeting_input_audio_buffer"):
            self._greeting_input_audio_buffer = []
        
        # 🔥 BUILD 341: FRAME METRICS - Track all frames for quality monitoring
        _frames_in = 0        # Total frames received from queue
        _frames_sent = 0      # Total frames sent to OpenAI
        _frames_dropped = 0   # Total frames dropped (FPS limit or other)
        _metrics_last_log = time.time()
        _metrics_log_interval = 5.0  # Log every 5 seconds
        
        # 🔥 BUILD 318: FPS LIMITER - Prevent sending too many frames/second
        # This is a critical cost optimization - limits frames to COST_MAX_FPS per second
        _fps_frame_count = 0
        _fps_window_start = time.time()
        _fps_throttle_logged = False
        
        # 🔥 BUILD 331: HARD SAFETY LIMITS - Prevent runaway token consumption
        _call_start_time = time.time()
        _total_frames_sent = 0
        _limit_exceeded = False
        _limit_logged = False
        
        # ═══════════════════════════════════════════════════════════════════════
        # 🔥 STEP 5: Queue audio until session is confirmed
        # ═══════════════════════════════════════════════════════════════════════
        _session_wait_logged = False
        
        while not self.realtime_stop_flag and not self.closed:
            try:
                if not hasattr(self, 'realtime_audio_in_queue'):
                    await asyncio.sleep(0.01)
                    continue
                
                # 🔥 STEP 5: Wait for session confirmation before sending audio
                # This prevents audio from being sent with wrong config (PCM16 instead of g711_ulaw)
                if not getattr(self, '_session_config_confirmed', False):
                    if not _session_wait_logged:
                        _orig_print(f"⏸️ [AUDIO_GATE] Queuing audio - waiting for session.updated confirmation", flush=True)
                        _session_wait_logged = True
                    # 🔥 PERFORMANCE: Use event wait instead of polling
                    try:
                        await asyncio.wait_for(self._session_config_event.wait(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue  # Timeout - check again
                    # Event was set - continue to send audio
                elif _session_wait_logged:
                    _orig_print(f"▶️ [AUDIO_GATE] Session confirmed - starting audio transmission to OpenAI", flush=True)
                    _session_wait_logged = False  # Reset for next check
                
                try:
                    audio_chunk = self.realtime_audio_in_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                
                if audio_chunk is None:
                    logger.info(f"📤 [REALTIME] Stop signal received")
                    break
                
                # 🔥 BUILD 341: Count incoming frames
                _frames_in += 1
                
                # 🔥 REMOVED: greeting_lock frame dropping - all frames are now processed
                
                # If greeting just ended, discard any buffered audio (should be empty) and resume live audio.
                if _greeting_block_logged and not _greeting_resumed_logged:
                    buffered = getattr(self, "_greeting_input_audio_buffer", [])
                    if buffered:
                        logger.info(f"🗑️ [GREETING_LOCK] Discarding buffered user audio (frames={len(buffered)})")
                        buffered.clear()
                    logger.info("✅ [GREETING_LOCK] Greeting done - resuming live audio to OpenAI")
                    _greeting_resumed_logged = True
                
                # 🔥 FIX: CLOSING STATE - Block audio input when call is closing
                # Once BOT_BYE_DETECTED, we enter CLOSING state and must NOT send any more audio to OpenAI
                # This prevents VAD/STT from triggering new END_OF_UTTERANCE events during goodbye audio drain
                if self.call_state == CallState.CLOSING:
                    if not hasattr(self, '_closing_block_logged') or not self._closing_block_logged:
                        logger.info("🚫 [CLOSING] Call in CLOSING state - ignoring all user audio input")
                        self._closing_block_logged = True
                    self._stats_audio_blocked += 1
                    _frames_dropped += 1
                    continue
                
                # ✅ NO FPS LIMITING - All frames pass through
                # TX loop maintains strict 20ms pacing, no artificial throttling here
                
                _fps_frame_count += 1
                
                # 🔥 BUILD 331: HARD SAFETY LIMITS - Check before sending any audio!
                call_elapsed = time.time() - _call_start_time
                _total_frames_sent += 1
                
                # Check if we've exceeded hard limits
                if not _limit_exceeded:
                    if call_elapsed > MAX_REALTIME_SECONDS_PER_CALL:
                        _limit_exceeded = True
                        logger.info(f"🛑 [BUILD 331] HARD LIMIT EXCEEDED! call_duration={call_elapsed:.1f}s > max={MAX_REALTIME_SECONDS_PER_CALL}s")
                    elif _total_frames_sent > MAX_AUDIO_FRAMES_PER_CALL:
                        _limit_exceeded = True
                        logger.info(f"🛑 [BUILD 331] HARD LIMIT EXCEEDED! frames={_total_frames_sent} > max={MAX_AUDIO_FRAMES_PER_CALL}")
                
                # If limit exceeded, stop sending audio and trigger IMMEDIATE call termination
                if _limit_exceeded:
                    if not _limit_logged:
                        _limit_logged = True
                        logger.info(f"🛑 [BUILD 331] OPENAI_USAGE_GUARD: frames_sent={_total_frames_sent}, estimated_seconds={call_elapsed:.1f}")
                        logger.info(f"🛑 [BUILD 332] HARD LIMIT HIT - Triggering immediate call termination!")
                        
                        # 🔥 BUILD 332: Set flags to trigger FULL call shutdown
                        self.realtime_stop_flag = True
                        self._limit_exceeded = True  # Store for logging in finally block
                        self._limit_frames = _total_frames_sent
                        self._limit_seconds = call_elapsed
                        
                        # 🔥 BUILD 332: FORCE SOCKET SHUTDOWN - Unblocks Eventlet's wait() immediately!
                        # ws.close() doesn't break Eventlet's wait() loop, but socket.shutdown() does
                        if hasattr(self, 'ws') and self.ws:
                            try:
                                import socket
                                # Get the underlying socket and force shutdown
                                if hasattr(self.ws, 'socket'):
                                    self.ws.socket.shutdown(socket.SHUT_RDWR)
                                    logger.info(f"✅ [BUILD 332] Socket shutdown triggered - main loop will exit!")
                                elif hasattr(self.ws, '_socket'):
                                    self.ws._socket.shutdown(socket.SHUT_RDWR)
                                    logger.info(f"✅ [BUILD 332] Socket shutdown triggered via _socket!")
                                else:
                                    # Fallback: try to close normally (set flag to prevent double close)
                                    if not self._ws_closed:
                                        self.ws.close()
                                        self._ws_closed = True
                                        logger.warning(f"⚠️ [BUILD 332] Used ws.close() fallback (no direct socket access)")
                            except Exception as e:
                                logger.error(f"⚠️ [BUILD 332] Socket shutdown failed: {e}")
                        
                        # 🔥 BUILD 332: ALSO CALL TWILIO API as additional guarantee
                        if hasattr(self, 'call_sid') and self.call_sid:
                            try:
                                import os
                                from twilio.rest import Client as TwilioClient
                                account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                                auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
                                if account_sid and auth_token:
                                    twilio_client = TwilioClient(account_sid, auth_token)
                                    twilio_client.calls(self.call_sid).update(status='completed')
                                    logger.info(f"✅ [BUILD 332] Twilio call {self.call_sid} terminated via API!")
                            except Exception as e:
                                logger.warning(f"⚠️ [BUILD 332] Could not terminate call via Twilio API: {e}")
                    
                    break  # Exit the audio sender loop immediately
                
                # 💰 COST TRACKING: Start timer on first chunk
                if not hasattr(self, '_user_speech_start') or self._user_speech_start is None:
                    self._user_speech_start = time.time()
                # 🔥 FIX: realtime_audio_in_chunks is now incremented at frame reception (line ~8398)
                # not here after filtering - this prevents accounting errors
                
                # 🔥 BUILD 341: Count frames sent and log metrics periodically
                _frames_sent += 1
                
                # Log metrics every 5 seconds (DEBUG only)
                current_time = time.time()
                if current_time - _metrics_last_log >= _metrics_log_interval:
                    call_duration = current_time - _call_start_time
                    logger.debug(f"[FRAME_METRICS] StreamSid={self.stream_sid} | "
                          f"frames_in={_frames_in}, frames_sent={_frames_sent}, frames_dropped={_frames_dropped} | "
                          f"call_duration={call_duration:.1f}s")
                    _metrics_last_log = current_time
                
                # 🔥 BUILD 200: Track audio sent stats
                self._stats_audio_sent += 1
                
                # 🔥 Log first frame sent after gate opens
                if _frames_sent == 0:
                    _orig_print(f"🎵 [AUDIO_GATE] First audio frame sent to OpenAI - transmission started", flush=True)
                
                await client.send_audio_chunk(audio_chunk)
                
                # 🔥 BUILD 301: Enhanced pipeline status with stuck response detection
                now = time.time()
                if now - self._stats_last_log_ts >= self._stats_log_interval_sec:
                    self._stats_last_log_ts = now
                    
                    # 🔥 BUILD 301: SAFETY NET - Clear stuck active_response_id
                    # If active_response_id has been set for >10 seconds, it's stuck (response.done was missed)
                    # This prevents AI freeze without adding a watchdog - just inline check
                    response_stuck_seconds = 10.0
                    if self.active_response_id:
                        # Get response start time - use _response_created_ts if available
                        response_started = getattr(self, '_response_created_ts', None)
                        if response_started and response_started > 0:
                            response_age = now - response_started
                        else:
                            # Fallback: track first time we saw this response in status log
                            if not hasattr(self, '_stuck_check_first_seen_ts'):
                                self._stuck_check_first_seen_ts = now
                            response_age = now - self._stuck_check_first_seen_ts
                        
                        if response_age > response_stuck_seconds:
                            logger.info(f"🔧 [BUILD 301] STUCK RESPONSE DETECTED! Clearing active_response_id after {response_age:.1f}s")
                            logger.info(f"   Was: {self.active_response_id[:20]}...")
                            self.active_response_id = None
                            self.active_response_status = "done"  # 🔥 IDEMPOTENT CANCEL: Mark as done (timeout)
                            self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                            self.response_pending_event.clear()
                            self.is_ai_speaking_event.clear()
                            self._stuck_check_first_seen_ts = None  # Reset for next response
                            logger.info(f"   ✅ Response guards cleared - AI can respond again")
                    else:
                        # No active response - reset the tracking
                        if hasattr(self, '_stuck_check_first_seen_ts'):
                            self._stuck_check_first_seen_ts = None
                    
                    # 🔥 BUILD 302: BARGE-IN FAILSAFE - Clear if stuck for >5 seconds
                    # If speech_stopped never fires (e.g., network issue), don't leave barge_in_active stuck
                    BARGE_IN_TIMEOUT_SEC = 5.0
                    if self.barge_in_active:
                        barge_start = getattr(self, '_barge_in_started_ts', None)
                        if barge_start:
                            barge_age = now - barge_start
                            if barge_age > BARGE_IN_TIMEOUT_SEC:
                                logger.info(f"🔧 [BUILD 302] BARGE-IN TIMEOUT! Clearing after {barge_age:.1f}s (speech_stopped never received)")
                                self.barge_in_active = False
                                self._barge_in_started_ts = None
                    
                    logger.debug(
                        f"[PIPELINE STATUS] sent={self._stats_audio_sent} blocked={self._stats_audio_blocked} | "
                        f"active_response={self.active_response_id[:15] if self.active_response_id else 'None'}... | "
                        f"ai_speaking={self.is_ai_speaking_event.is_set()} | barge_in={self.barge_in_active}"
                    )
                
            except Exception as e:
                # ═══════════════════════════════════════════════════════════════════════
                # 🔥 REALTIME_FATAL: Exception in audio sender loop
                # ═══════════════════════════════════════════════════════════════════════
                import traceback
                _orig_print(f"🔥 [REALTIME_FATAL] Unhandled exception in _realtime_audio_sender: {e}", flush=True)
                _orig_print(f"🔥 [REALTIME_FATAL] call_sid={self.call_sid}", flush=True)
                traceback.print_exc()
                logger.error(f"[REALTIME_FATAL] Exception in audio sender: {e}")
                break
        
        # 🔥 BUILD 331: Store values for final logging in main finally block
        self._usage_guard_frames = _total_frames_sent
        self._usage_guard_seconds = time.time() - _call_start_time
        self._usage_guard_limit_hit = _limit_exceeded
        logger.info(f"📤 [REALTIME] Audio sender ended (frames={_total_frames_sent}, seconds={self._usage_guard_seconds:.1f})")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ✅ NO QUEUE FLUSH: Removed per requirements - no flush on barge-in
    # Audio drains naturally, no manual queue manipulation
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 BUILD 320: AUDIO_GUARD - Lightweight filtering for noisy PSTN calls
    # ═══════════════════════════════════════════════════════════════════════════════
    def _compute_zcr(self, pcm_samples: bytes) -> float:
        """
        Compute Zero-Crossing Rate (ZCR) for audio frame.
        ZCR = (number of sign changes) / (total samples)
        Speech typically has moderate ZCR (0.02-0.10), music/noise can be higher or lower.
        """
        if not pcm_samples or len(pcm_samples) < 4:
            return 0.0
        
        import struct
        try:
            # PCM16 = 2 bytes per sample
            num_samples = len(pcm_samples) // 2
            if num_samples < 2:
                return 0.0
            
            samples = struct.unpack(f'<{num_samples}h', pcm_samples[:num_samples*2])
            zero_crossings = 0
            for i in range(1, len(samples)):
                if (samples[i] >= 0 and samples[i-1] < 0) or (samples[i] < 0 and samples[i-1] >= 0):
                    zero_crossings += 1
            
            return zero_crossings / num_samples
        except Exception:
            return 0.0
    
    def _is_probable_speech(self, rms: float, zcr: float, effective_threshold: float, prev_rms: float) -> bool:
        """
        🔥 BUILD 320: Determine if audio frame is probably speech vs noise/music.
        Uses RMS, ZCR, and RMS delta to distinguish speech from background noise.
        
        Returns True if frame should be sent to OpenAI, False to drop.
        """
        from server.config.calls import AUDIO_GUARD_MIN_ZCR_FOR_SPEECH, AUDIO_GUARD_MIN_RMS_DELTA
        
        # Hard silence - definitely not speech
        if rms < 0.5 * effective_threshold:
            return False
        
        # Clearly loud segment (speech or loud noise) - let OpenAI decide
        if rms >= 1.5 * effective_threshold:
            return True
        
        # Mid-range: use ZCR and dynamics to distinguish speech vs flat noise
        # Speech has characteristic ZCR patterns and amplitude variations
        if zcr >= AUDIO_GUARD_MIN_ZCR_FOR_SPEECH:
            return True
        
        # Speech has dynamic amplitude changes between frames
        if abs(rms - prev_rms) >= AUDIO_GUARD_MIN_RMS_DELTA:
            return True
        
        return False
    
    def _update_audio_guard_state(self, rms: float, zcr: float) -> bool:
        """
        🔥 BUILD 320: Update audio guard state (noise floor, music mode) and decide if frame passes.
        
        Returns True if frame should be sent to OpenAI, False to drop.
        """
        from server.config.calls import (
            AUDIO_GUARD_MUSIC_ZCR_THRESHOLD, AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER,
            AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES
        )
        
        # Calculate effective speech threshold
        effective_threshold = self._audio_guard_noise_floor * self._audio_guard_speech_factor
        
        # Update noise floor when frame is "probably silence" (below threshold)
        if rms < effective_threshold:
            # Exponential moving average: 90% old + 10% new
            self._audio_guard_noise_floor = 0.9 * self._audio_guard_noise_floor + 0.1 * rms
        
        # ═══ MUSIC MODE DETECTION ═══
        # 🔥 CRITICAL HOTFIX: Only enter music mode if MUSIC_MODE_ENABLED is True
        if self._music_mode_enabled:
            # Detect continuous background music: sustained RMS + moderate-high ZCR
            if rms > effective_threshold and zcr > AUDIO_GUARD_MUSIC_ZCR_THRESHOLD:
                self._audio_guard_music_frames_counter += 1
            else:
                self._audio_guard_music_frames_counter = 0
            
            # Enter music mode after sustained detection (~300ms)
            if not self._audio_guard_music_mode and self._audio_guard_music_frames_counter >= AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER:
                self._audio_guard_music_mode = True
                self._audio_guard_music_cooldown_frames = AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES
                logger.info(f"🎵 [AUDIO_GUARD] Entering music_mode (rms={rms:.1f}, zcr={zcr:.3f}) - filtering background music")
            
            # Exit music mode after cooldown
            if self._audio_guard_music_mode:
                self._audio_guard_music_cooldown_frames -= 1
                if self._audio_guard_music_cooldown_frames <= 0:
                    self._audio_guard_music_mode = False
                    self._audio_guard_music_frames_counter = 0
                    logger.info(f"🎵 [AUDIO_GUARD] Leaving music_mode - resuming normal audio")
                # During music mode, drop all frames
                return False
        else:
            # Music mode disabled - reset state only if needed (avoid per-frame overhead)
            if self._audio_guard_music_mode or self._audio_guard_music_frames_counter > 0:
                self._audio_guard_music_mode = False
                self._audio_guard_music_frames_counter = 0
        
        # ═══ SPEECH DETECTION ═══
        is_speech = self._is_probable_speech(rms, zcr, effective_threshold, self._audio_guard_prev_rms)
        
        # Update previous RMS for next frame
        self._audio_guard_prev_rms = rms
        
        # Rate-limited logging for dropped frames
        if not is_speech:
            self._audio_guard_drop_count += 1
            if self._audio_guard_drop_count % 50 == 0:  # Log every 50 drops (~1 second)
                logger.info(f"🔇 [AUDIO_GUARD] Dropped {self._audio_guard_drop_count} non-speech frames (rms={rms:.1f}, zcr={zcr:.3f}, threshold={effective_threshold:.1f})")
        
        # Periodic summary log every 5 seconds
        now = time.time()
        if now - self._audio_guard_last_summary_ts >= 5.0:
            self._audio_guard_last_summary_ts = now
            logger.info(f"📊 [AUDIO_GUARD] noise_floor={self._audio_guard_noise_floor:.1f}, threshold={effective_threshold:.1f}, music_mode={self._audio_guard_music_mode}")
        
        return is_speech
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 BUILD 200: SINGLE RESPONSE TRIGGER - Central function for ALL response.create
    # ═══════════════════════════════════════════════════════════════════════════════
    async def trigger_response(self, reason: str, client=None, is_greeting: bool = False, force: bool = False) -> bool:
        """
        🎯 BUILD 200: Central function for triggering response.create
        
        ALL response.create calls MUST go through this function!
        This ensures:
        1. Proper lifecycle tracking of active_response_id
        2. Loop guard protection
        3. Consistent logging
        4. 🔥 FIX: NO blocking guards - cancel happens in barge-in handler only
        5. 🔥 SESSION GATE: Blocks until session.updated is confirmed
        
        Cancel/replace pattern:
        - response.cancel is called ONLY in speech_started handler when real barge-in detected
        - This function never blocks based on active_response_id or is_ai_speaking
        - Allows AI to finish speaking unless user actually interrupts
        
        Args:
            reason: Why we're creating a response (for logging)
            client: The realtime client (uses self.realtime_client if not provided)
            is_greeting: If True, this is the initial greeting - skip loop guard (first response)
            force: If True, bypass lifecycle locks for the initial greeting trigger only
            
        Returns:
            True if response was triggered, False if blocked by lifecycle guards only
        """
        # Use stored client if not provided
        _client = client or self.realtime_client
        if not _client:
            logger.warning(f"⚠️ [RESPONSE GUARD] No client available - cannot trigger ({reason})")
            return False
        
        # 🔥 CRITICAL SESSION GATE: Block response.create until session is confirmed
        # This prevents race condition where response.create uses default settings (PCM16, English)
        # Must wait for session.updated confirmation BEFORE any response.create
        if not getattr(self, '_session_config_confirmed', False):
            # Check if configuration failed
            if getattr(self, '_session_config_failed', False):
                _orig_print(f"🚨 [RESPONSE GUARD] Session config FAILED - blocking response.create ({reason})", flush=True)
                return False
            
            # Configuration not yet confirmed - wait a bit for greeting case
            if is_greeting:
                # For greeting, we've already waited in connect_realtime, so this shouldn't happen
                # But if it does, it's a critical error
                _orig_print(f"🚨 [RESPONSE GUARD] CRITICAL: Greeting triggered before session confirmed! ({reason})", flush=True)
                return False
            else:
                # For non-greeting, session should already be confirmed
                # If not, block the response
                _orig_print(f"🛑 [RESPONSE GUARD] Session not confirmed - blocking response.create ({reason})", flush=True)
                return False
        
        # 🔥 FIX: Cancel/replace ONLY on real barge-in (user speaking while AI speaking)
        # Do NOT cancel just because active_response_id exists - let AI finish speaking
        # Cancel only happens in the barge-in handler (speech_started event), not here
        # This prevents cutting off AI mid-sentence when there's no actual interruption
        
        # 🔥 CRITICAL GUARD: Block response.create while user is speaking
        # This is THE key to proper turn-taking: wait until user finishes before responding
        if getattr(self, 'user_speaking', False) and not is_greeting:
            logger.info(f"🛑 [RESPONSE GUARD] USER_SPEAKING=True - blocking response until speech complete ({reason})")
            return False
        
        # 🛡️ GUARD 0.25: BUILD 310 - Block new AI responses when hangup is pending or call is closing
        # Don't let AI start new conversation loops after call should end
        if getattr(self, 'pending_hangup', False):
            logger.info(f"⏸️ [RESPONSE GUARD] Hangup pending - blocking new responses ({reason})")
            return False
        
        # 🔥 FIX: Block response.create when call is in CLOSING state
        # Once BOT_BYE_DETECTED, no more AI responses should be created
        if self.call_state == CallState.CLOSING:
            logger.info(f"🚫 [RESPONSE GUARD] Call in CLOSING state - blocking new responses ({reason})")
            return False
        
        # 🛡️ GUARD 0.5: BUILD 308 - POST-REJECTION TRACKING
        # After user says "לא", city is cleared so AI will naturally ask for it again
        # No artificial delay - the city clearing is the main fix
        # AI will dynamically ask for whatever field is missing based on business settings
        if getattr(self, '_awaiting_user_correction', False):
            # Clear the flag - AI can respond (but city is empty so it will ask dynamically)
            self._awaiting_user_correction = False
            logger.info(f"🔄 [BUILD 308] User rejected - city cleared, AI will ask dynamically")
        
        # 🛡️ GUARD 2: Check if response is pending (race condition prevention)
        if self.response_pending_event.is_set() and not (force and is_greeting):
            logger.info(f"⏸️ [RESPONSE GUARD] Response pending - skipping ({reason})")
            return False
        
        # 🛡️ GUARD 3: Loop guard check (inbound calls only, skip for greeting)
        if not is_greeting:
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if not is_outbound:
                if self._loop_guard_engaged:
                    logger.info(f"🛑 [RESPONSE GUARD] Loop guard engaged - blocking ({reason})")
                    return False
                if self._consecutive_ai_responses >= self._max_consecutive_ai_responses:
                    logger.info(f"🛑 [RESPONSE GUARD] Too many consecutive responses ({self._consecutive_ai_responses}) - blocking ({reason})")
                    return False
        
        # ✅ All guards passed - trigger response
        try:
            # For forced greeting, make sure we don't inherit a stale pending lock.
            if force and is_greeting and self.response_pending_event.is_set():
                self.response_pending_event.clear()
            
            # 🔥 NEW: DOUBLE CREATE TELEMETRY - Detect rapid response.create without completion
            # This prevents "weird speech" / audio overlap from concurrent responses
            prev_active_id = getattr(self, 'active_response_id', None)
            prev_status = getattr(self, 'active_response_status', None)
            last_create_ts = getattr(self, '_last_response_create_ts', 0)
            now = time.time()
            time_since_last = (now - last_create_ts) * 1000  # milliseconds
            
            # Warn if creating response while previous still active
            if prev_active_id and prev_status == "in_progress":
                _orig_print(
                    f"⚠️ [DOUBLE_CREATE_RISK] Creating new response while prev active | "
                    f"reason={reason}, prev_id={prev_active_id[:8]}, "
                    f"prev_status={prev_status}, time_since_last={time_since_last:.0f}ms",
                    flush=True
                )
            
            # Warn if creating response too quickly (< 500ms since last)
            if time_since_last < 500 and time_since_last > 0:
                _orig_print(
                    f"⚠️ [RAPID_CREATE] response.create very fast | "
                    f"reason={reason}, interval={time_since_last:.0f}ms (<500ms)",
                    flush=True
                )
            
            self._last_response_create_ts = now
            
            self.response_pending_event.set()  # 🔒 Lock BEFORE sending (thread-safe)
            
            # Log with full context for debugging
            tx_q_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
            out_q_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
            is_speaking = self.is_ai_speaking_event.is_set() if hasattr(self, 'is_ai_speaking_event') else False
            
            _orig_print(
                f"🎯 [RESPONSE_CREATE] reason={reason}, "
                f"prev_active={prev_active_id[:8] if prev_active_id else 'none'}, "
                f"is_ai_speaking={is_speaking}, "
                f"tx_q={tx_q_size}, out_q={out_q_size}",
                flush=True
            )
            
            await _client.send_event({"type": "response.create"})
            
            # 🔥 BUILD 338: Track response.create count for cost debugging
            self._response_create_count += 1
            logger.info(f"🎯 [BUILD 200] response.create triggered ({reason}) [TOTAL: {self._response_create_count}]")
            return True
        except Exception as e:
            # 🔓 CRITICAL: Clear lock immediately on failure
            self.response_pending_event.clear()
            logger.error(f"❌ [RESPONSE GUARD] Failed to trigger ({reason}): {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 TOOL RESPONSE TRIGGER - Wrapper for tool/function handlers
    # ═══════════════════════════════════════════════════════════════════════════════
    async def trigger_response_from_tool(self, client, tool_name: str, *, force: bool = False) -> bool:
        """
        🎯 Tool handlers MUST call this instead of direct response.create.
        
        This ensures ALL safety guards apply to tool responses:
        1. Session gate (session.updated confirmed)
        2. User speaking check (don't interrupt user)
        3. Hangup/closing checks (don't waste tokens)
        4. Consistent cost tracking and logging
        
        Args:
            client: The realtime client
            tool_name: Descriptive tool name for logging (e.g., "save_lead_info", 
                      "check_availability_success", "schedule_appointment_disabled").
                      Should be specific, not generic like "FUNCTION_CALL".
            force: If True, bypass lifecycle locks (rarely needed for tools)
            
        Returns:
            True if response was triggered, False if blocked by guards
            
        Examples:
            await self.trigger_response_from_tool(client, "save_lead_info")
            await self.trigger_response_from_tool(client, "check_availability_success")
            await self.trigger_response_from_tool(client, "schedule_appointment_disabled")
        """
        # Reuse existing trigger_response with all its guards
        # Log format: TOOL_<name> for easy identification in logs
        return await self.trigger_response(f"TOOL_{tool_name}", client, is_greeting=False, force=force)
    
    async def _ensure_name_anchor_present(self, client):
        """
        Ensure NAME_ANCHOR is present after PROMPT_UPGRADE or other context changes.
        
        This is an IDEMPOTENT operation that:
        1. Checks if NAME_ANCHOR needs to be updated (name or policy changed)
        2. Re-injects NAME_ANCHOR if needed
        3. Logs the operation for debugging
        
        Called after PROMPT_UPGRADE to ensure name context persists.
        
        CRITICAL: This MUST actually re-inject if name/policy changed, not just check flags!
        """
        try:
            # Check if we have a name anchor already injected
            if not hasattr(self, '_name_anchor_injected'):
                # No anchor yet - skip (should have been injected at session start)
                logger.warning("[NAME_ANCHOR] ensure called but no initial injection - skipping")
                return
            
            # Extract current customer name from various sources
            def _extract_current_name():
                """Get the current customer name from all available sources."""
                # Try pending_customer_name first (most recent)
                if hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    name = str(self.pending_customer_name).strip()
                    if name and name.lower() not in ['unknown', 'test', '-', 'null', 'none']:
                        return name
                
                # Try crm_context
                if hasattr(self, 'crm_context') and self.crm_context:
                    if hasattr(self.crm_context, 'customer_name') and self.crm_context.customer_name:
                        name = str(self.crm_context.customer_name).strip()
                        if name and name.lower() not in ['unknown', 'test', '-', 'null', 'none']:
                            return name
                
                # Try outbound_lead_name
                if hasattr(self, 'outbound_lead_name') and self.outbound_lead_name:
                    name = str(self.outbound_lead_name).strip()
                    if name and name.lower() not in ['unknown', 'test', '-', 'null', 'none']:
                        return name
                
                return None
            
            current_name = _extract_current_name()
            current_policy = getattr(self, 'use_name_policy', False)
            
            # 🔥 FIX: Skip re-injection if name is None or invalid
            # This prevents injecting name='None' which is a bug
            if not current_name or not str(current_name).strip():
                logger.debug(f"[NAME_ANCHOR] ensure: skipping - no valid name available")
                logger.info(f"ℹ️ [NAME_ANCHOR] ensure: No valid name to re-inject")
                return
            
            # Validate name is not a placeholder
            name_lower = str(current_name).lower().strip()
            if name_lower in INVALID_NAME_PLACEHOLDERS:
                logger.debug(f"[NAME_ANCHOR] ensure: skipping - invalid name '{current_name}'")
                logger.info(f"ℹ️ [NAME_ANCHOR] ensure: Invalid placeholder name '{current_name}'")
                return
            
            # 🔥 ANTI-DUPLICATE: Check using hash fingerprint
            import hashlib
            new_hash = f"{current_name}|{current_policy}"
            new_hash_short = hashlib.md5(new_hash.encode()).hexdigest()[:8]
            
            existing_hash = getattr(self, '_name_anchor_hash', None)
            
            # Only re-inject if hash changed
            if existing_hash != new_hash_short:
                from server.services.realtime_prompt_builder import build_name_anchor_message, detect_gender_from_name
                
                # 🧠 GENDER DETECTION: Priority order (SSOT)
                # 1. Database (if manually set or detected from previous conversation)
                # 2. Name-based detection (if not unisex)
                customer_gender = None
                
                # Priority 1: Check database for saved gender
                try:
                    from server.models_sql import CallLog, Lead
                    app = _get_flask_app()
                    with app.app_context():
                        call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        lead = None
                        
                        if call_log and call_log.lead_id:
                            lead = Lead.query.get(call_log.lead_id)
                        elif hasattr(self, 'outbound_lead_id') and self.outbound_lead_id:
                            lead = Lead.query.get(self.outbound_lead_id)
                        
                        if lead and lead.gender:
                            customer_gender = lead.gender
                            logger.info(f"[GENDER_DETECT] Using saved gender from database: {customer_gender} (Lead {lead.id})")
                except Exception as e:
                    logger.warning(f"[GENDER_DETECT] Error checking database gender: {e}")
                
                # Priority 2: Detect from name (only if not in database)
                if not customer_gender:
                    customer_gender = detect_gender_from_name(current_name)
                    if customer_gender:
                        logger.info(f"[GENDER_DETECT] Detected from name: {customer_gender} for '{current_name}'")
                    else:
                        logger.info(f"[GENDER_DETECT] Cannot determine from name: '{current_name}' (unisex/unknown)")
                
                # 🔥 NEW: Get lead notes if available (may have been fetched earlier)
                lead_notes = getattr(self, 'pending_lead_notes', None)
                
                # Build updated NAME_ANCHOR
                name_anchor_text = build_name_anchor_message(
                    current_name, 
                    current_policy, 
                    customer_gender,
                    lead_notes  # 🔥 NEW: Pass notes to context builder
                )
                
                # Re-inject NAME_ANCHOR
                name_anchor_event = await client.send_event(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "system",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": name_anchor_text,
                                }
                            ],
                        },
                    }
                )
                
                # Update stored state with hash
                self._name_anchor_customer_name = current_name
                self._name_anchor_policy = current_policy
                self._name_anchor_hash = new_hash_short
                self._name_anchor_count = getattr(self, '_name_anchor_count', 0) + 1
                
                # Get item_id
                item_id = name_anchor_event.get('item', {}).get('id', 'unknown') if isinstance(name_anchor_event, dict) else 'unknown'
                
                # Log re-injection with hash
                logger.info(f"[NAME_ANCHOR] re-injected enabled={current_policy} name=\"{current_name}\" item_id={item_id} hash={new_hash_short}")
                logger.info(f"✅ [NAME_ANCHOR] Re-injected after upgrade: enabled={current_policy}, name='{current_name}', hash={new_hash_short}")
                _orig_print(f"[NAME_ANCHOR] re-injected enabled={current_policy} name=\"{current_name}\" hash={new_hash_short}", flush=True)
            else:
                # No change needed - log with hash
                logger.debug(f"[NAME_ANCHOR] ensured ok (no change) hash={existing_hash}")
                logger.info(f"ℹ️ [NAME_ANCHOR] Ensured - no change needed (hash={existing_hash})")
                _orig_print(f"[NAME_ANCHOR] ensured ok (no change) hash={existing_hash}", flush=True)
                
        except Exception as e:
            logger.error(f"[NAME_ANCHOR] Failed to ensure NAME_ANCHOR: {e}")
            import traceback
            traceback.print_exc()
    
    async def _realtime_text_sender(self, client):
        """
        Send text input (e.g., DTMF) from queue to Realtime API
        ✅ Resilient: Retries on failure, never drops DTMF input silently
        """
        logger.info(f"📝 [REALTIME] Text sender started")
        
        while not self.realtime_stop_flag and not self.closed:
            try:
                if not hasattr(self, 'realtime_text_input_queue'):
                    await asyncio.sleep(0.01)
                    continue
                
                try:
                    text_message = self.realtime_text_input_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                
                if text_message is None:
                    logger.info(f"📝 [REALTIME] Stop signal received")
                    break
                
                # ✅ Resilient send with retry
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        logger.info(f"📝 [REALTIME] Sending user message (attempt {attempt+1}/{max_retries}): '{text_message[:50]}...'")
                        await client.send_user_message(text_message)
                        logger.info(f"✅ [REALTIME] User message sent successfully")
                        break  # Success - exit retry loop
                    except Exception as send_error:
                        if attempt < max_retries - 1:
                            logger.error(f"⚠️ [REALTIME] Send failed (attempt {attempt+1}), retrying: {send_error}")
                            await asyncio.sleep(0.1)  # Brief delay before retry
                        else:
                            # All retries exhausted - log critical error
                            logger.error(f"❌ [REALTIME] CRITICAL: Failed to send DTMF input after {max_retries} attempts: {send_error}")
                            logger.error(f"❌ [REALTIME] Lost message: '{text_message[:100]}'")
                            import traceback
                            traceback.print_exc()
                            # Don't re-raise - continue processing queue
                
            except Exception as e:
                logger.error(f"❌ [REALTIME] Text sender error: {e}")
                import traceback
                traceback.print_exc()
                # Don't stop the loop - keep trying to process messages
        
        logger.info(f"📝 [REALTIME] Text sender ended")
    
    async def _realtime_audio_receiver(self, client):
        """Receive audio and events from Realtime API"""
        logger.info(f"📥 [REALTIME] Audio receiver started")
        
        # 🔥 CRITICAL: Signal that RX loop is ready to receive events
        # This ensures session.update is sent ONLY after recv_events() is listening
        self._recv_loop_started = True
        _orig_print(f"🎯 [RX_LOOP] recv_events() loop is now ACTIVE and listening", flush=True)
        
        try:
            async for event in client.recv_events():
                event_type = event.get("type", "")
                
                # ═══════════════════════════════════════════════════════════════════════
                # 🔥 STEP 2: RAW EVENT TRACE - Log ALL events to diagnose missing events
                # ═══════════════════════════════════════════════════════════════════════
                # PRODUCTION: Do NOT log raw events (high I/O, hot-path overhead).
                # Keep these only for DEBUG investigations with rate limiting.
                # 🔥 SSOT: Rate-limited to prevent log spam (max once per 5 seconds)
                if DEBUG and _event_loop_rate_limiter.every("raw_event_trace", 5.0):
                    error_info = event.get("error")
                    if error_info:
                        error_type = error_info.get("type", "unknown")
                        error_code = error_info.get("code", "unknown")
                        error_msg = error_info.get("message", "")
                        logger.debug(
                            "[RAW_EVENT] type=%s error_type=%s error_code=%s error_msg=%s",
                            event_type,
                            error_type,
                            error_code,
                            error_msg,
                        )
                    elif event_type in ("session.created", "session.updated", "error"):
                        # Avoid dumping full event payloads (can be huge).
                        logger.debug("[RAW_EVENT] type=%s", event_type)
                    elif not event_type.endswith(".delta"):
                        logger.debug("[RAW_EVENT] type=%s", event_type)
                
                response_id = event.get("response_id")
                if not response_id and "response" in event:
                    response_id = event.get("response", {}).get("id")
                
                if response_id and response_id in self._cancelled_response_ids:
                    if event_type in ("response.done", "response.cancelled"):
                        # ✅ CRITICAL FIX: Reset state on response.cancelled just like response.done
                        # Per הנחיה: IDEMPOTENT CANCEL - Clear all response state flags to prevent stale state
                        if self.active_response_id == response_id:
                            self.active_response_id = None
                            self.active_response_status = "cancelled"  # 🔥 IDEMPOTENT CANCEL
                            self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                            self.is_ai_speaking_event.clear()
                            self.speaking = False
                            self.barge_in_stop_tx = False  # 🔥 NEW FIX: Re-enable TX transmission
                            if hasattr(self, 'ai_response_active'):
                                self.ai_response_active = False
                            logger.info(f"✅ [STATE_RESET] Cancelled response cleanup: active_response_id=None, status=cancelled, cancel_in_flight=False, is_ai_speaking=False, ai_response_active=False, barge_in_stop_tx=False (response_id={response_id[:20]}...)")
                        
                        self._cancelled_response_ids.discard(response_id)
                        # ✅ NEW REQ 4: Also remove from timestamps dict
                        self._cancelled_response_timestamps.pop(response_id, None)
                        # ✅ P0 FIX: Also remove from cancel guard set
                        self._cancel_sent_for_response_ids.discard(response_id)
                        logger.info(f"🪓 [BARGE-IN] Final event for cancelled response {response_id[:20]}... (type={event_type})")
                        # Don't continue - let it process through normal response.done/cancelled handler below
                    else:
                        # ✅ P0-3: Log when dropping audio delta for cancelled response
                        if event_type == "response.audio.delta":
                            logger.info(f"[BARGE_IN_DROP_DELTA] response_id={response_id[:20]}... reason=cancelled_response")
                        else:
                            logger.info(f"🪓 [BARGE-IN] Dropping {event_type} for cancelled response {response_id[:20]}...")
                        continue
                
                # 🔥 DEBUG BUILD 168.5: Log ALL events to diagnose missing audio
                # 🔥 SSOT: Rate-limited to prevent log spam
                if event_type.startswith("response."):
                    # Log all response-related events with details
                    if event_type == "response.audio.delta":
                        delta = event.get("delta", "")
                        # 🚫 Production mode: Only log in DEBUG with rate limiting
                        if DEBUG and _event_loop_rate_limiter.every("audio_delta", 10.0):
                            logger.debug(f"[REALTIME] response.audio.delta: {len(delta)} bytes")
                        elif not DEBUG and _event_loop_rate_limiter.every("audio_delta_print", 10.0):
                            _orig_print(f"🔊 [REALTIME] response.audio.delta: {len(delta)} bytes", flush=True)
                    elif event_type == "response.done":
                        # 🔥 FIX: Update activity timestamp when response completes
                        # The AI just finished generating a complete response, so the call is active
                        self._last_activity_ts = time.time()
                        
                        response = event.get("response", {})
                        status = response.get("status", "?")
                        output = response.get("output", [])
                        status_details = response.get("status_details", {})
                        resp_id = response.get("id", "?")

                        # NOTE: greeting_lock must be released only after response.audio.done (playback-end),
                        # not on response.done (generation-end).
                        if DEBUG:
                            _orig_print(
                                f"🔊 [REALTIME] response.done: status={status}, output_count={len(output)}, details={status_details}",
                                flush=True,
                            )
                            for i, item in enumerate(output[:3]):  # First 3 items
                                item_type = item.get("type", "?")
                                content = item.get("content", [])
                                content_types = [c.get("type", "?") for c in content] if content else []
                                _orig_print(f"   output[{i}]: type={item_type}, content_types={content_types}", flush=True)
                        
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🎯 TASK D.2: Log response completion metrics for audio quality analysis
                        # Per הנחיה 5: Log frames_sent==0 cases with full snapshot
                        # ═══════════════════════════════════════════════════════════════════════
                        if hasattr(self, '_response_tracking') and resp_id in self._response_tracking:
                            tracking = self._response_tracking[resp_id]
                            end_time = time.time()
                            duration_ms = int((end_time - tracking['start_time']) * 1000)
                            frames_sent = tracking['frames_sent']
                            avg_fps = frames_sent / ((end_time - tracking['start_time']) or 1)
                            
                            # 🔥 CRITICAL: Log frames_sent==0 cases with full diagnostic snapshot
                            if frames_sent == 0:
                                # Keep TX diagnostics only for debug investigations (hot path).
                                if DEBUG_TX:
                                    _orig_print(f"⚠️ [TX_DIAG] frames_sent=0 for response {resp_id[:20]}...", flush=True)
                                    _orig_print(f"   SNAPSHOT:", flush=True)
                                    _orig_print(f"   - streamSid: {self.stream_sid}", flush=True)
                                    _orig_print(f"   - tx_queue_size: {self.tx_q.qsize() if hasattr(self, 'tx_q') else 'N/A'}", flush=True)
                                    _orig_print(f"   - realtime_audio_out_queue_size: {self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 'N/A'}", flush=True)
                                    _orig_print(f"   - active_response_id: {self.active_response_id[:20] if self.active_response_id else 'None'}...", flush=True)
                                    _orig_print(f"   - ai_response_active: {getattr(self, 'ai_response_active', False)}", flush=True)
                                    _orig_print(f"   - is_ai_speaking: {self.is_ai_speaking_event.is_set()}", flush=True)
                                    _orig_print(f"   - status: {status}", flush=True)
                                    _orig_print(f"   - duration_ms: {duration_ms}", flush=True)
                            
                            # 🔥 TX_RESPONSE: Changed to DEBUG to reduce production spam
                            logger.debug(f"[TX_RESPONSE] end response_id={resp_id[:20]}..., frames_sent={frames_sent}, duration_ms={duration_ms}, avg_fps={avg_fps:.1f}")
                            # Cleanup
                            del self._response_tracking[resp_id]
                        
                        # 🔥 LATENCY-FIRST: No prompt upgrade logic needed
                        # FULL prompt was already sent in session.update at the start
                        # AI has full context from the very first word - nothing to upgrade
                        
                        # 🔥 PROMPT-ONLY: Handle OpenAI server_error with retry + graceful failure
                        if status == "failed":
                            error_info = status_details.get("error") if isinstance(status_details, dict) else None
                            if not error_info:
                                # Try alternate location for error info
                                error_info = response.get("error")
                            
                            if error_info and error_info.get("type") == "server_error":
                                _orig_print(f"🔥 [SERVER_ERROR] OpenAI Realtime server error detected", flush=True)
                                
                                # Initialize retry flag if not exists
                                if not hasattr(self, '_server_error_retried'):
                                    self._server_error_retried = False
                                
                                # Get call duration to decide if we should retry
                                call_duration = time.time() - getattr(self, 'call_start_time', time.time())
                                
                                # Retry once if not already retried and call is not too old
                                if not self._server_error_retried and call_duration < 60:
                                    self._server_error_retried = True
                                    _orig_print(f"🔄 [SERVER_ERROR] Retrying response (first attempt)...", flush=True)
                                    
                                    # Send technical context (no scripted response)
                                    retry_msg = "[SYSTEM] Technical error occurred. Please retry your last response."
                                    await self._send_text_to_ai(retry_msg)
                                    
                                    # Trigger new response - 🔥 USE GATE
                                    triggered = await self.trigger_response("SERVER_ERROR_RETRY", client, force=False)
                                    if triggered:
                                        _orig_print(f"✅ [SERVER_ERROR] Retry response.create sent", flush=True)
                                    else:
                                        _orig_print(f"❌ [SERVER_ERROR] Retry blocked by gate", flush=True)
                                
                                else:
                                    # Already retried or call too long - graceful failure
                                    _orig_print(f"🚨 [SERVER_ERROR] Max retries reached or call too long - graceful hangup", flush=True)
                                    
                                    # Send technical context (AI decides how to handle based on Business Prompt)
                                    failure_msg = "[SYSTEM] Technical issue - system unavailable. End call politely."
                                    await self._send_text_to_ai(failure_msg)
                                    
                                    # Trigger final response - 🔥 USE GATE
                                    triggered = await self.trigger_response("SERVER_ERROR_GRACEFUL", client, force=False)
                                    if triggered:
                                        _orig_print(f"✅ [SERVER_ERROR] Graceful failure response sent", flush=True)
                                    else:
                                        _orig_print(f"❌ [SERVER_ERROR] Graceful failure blocked by gate", flush=True)
                        
                        # ✅ CRITICAL FIX: Full state reset on response.done
                        # Per הנחיה: IDEMPOTENT CANCEL - Clear state only for matching response_id
                        # Clear active_response_id, set status to done/cancelled, clear cancel_in_flight
                        # DO NOT reset session/conversation/STT - only AI speaking flags
                        resp_id = response.get("id", "")
                        if resp_id and self.active_response_id == resp_id:
                            # This response is done - clear all response state
                            self.active_response_id = None
                            self.active_response_status = "done" if status != "cancelled" else "cancelled"  # 🔥 IDEMPOTENT CANCEL
                            self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                            self.is_ai_speaking_event.clear()
                            self.speaking = False
                            # 🔥 BARGE-IN FIX: Clear all response flags
                            self.barge_in_active = False
                            self.barge_in_stop_tx = False  # 🔥 NEW FIX: Re-enable TX transmission for next response
                            if hasattr(self, 'ai_response_active'):
                                self.ai_response_active = False
                            _orig_print(f"✅ [STATE_RESET] Response complete: active_response_id=None, status={self.active_response_status}, cancel_in_flight=False, is_ai_speaking=False, ai_response_active=False, barge_in=False, barge_in_stop_tx=False ({resp_id[:20]}... status={status})", flush=True)
                        elif self.active_response_id:
                            # Mismatch - log but still clear to prevent deadlock
                            _orig_print(f"⚠️ [STATE_RESET] Response ID mismatch: active={self.active_response_id[:20] if self.active_response_id else 'None'}... done={resp_id[:20] if resp_id else 'None'}...", flush=True)
                            self.active_response_id = None
                            self.active_response_status = "done" if status != "cancelled" else "cancelled"  # 🔥 IDEMPOTENT CANCEL
                            self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                            self.is_ai_speaking_event.clear()
                            self.speaking = False
                            # 🔥 BARGE-IN FIX: Clear all response flags
                            self.barge_in_active = False
                            self.barge_in_stop_tx = False  # 🔥 NEW FIX: Re-enable TX transmission
                            if hasattr(self, 'ai_response_active'):
                                self.ai_response_active = False
                        
                        # 🛡️ BUILD 168.5 FIX: If greeting was cancelled, unblock audio input!
                        # Otherwise is_playing_greeting stays True forever and blocks all audio
                        if status == "cancelled" and self.is_playing_greeting:
                            _orig_print(f"⚠️ [GREETING CANCELLED] Unblocking audio input (was greeting)", flush=True)
                            self.is_playing_greeting = False
                            # 🔥 DON'T set greeting_sent=False! That would trigger GUARD block.
                            # Instead, enable barge-in to allow next response to pass
                            self.barge_in_enabled_after_greeting = True
                        
                        # 🔥 BUILD 168.5: If ANY response is cancelled and user hasn't spoken,
                        # allow next AI response by keeping greeting_sent=True
                        if status == "cancelled" and not self.user_has_spoken:
                            _orig_print(f"⚠️ [RESPONSE CANCELLED] Allowing next response (user hasn't spoken yet)", flush=True)
                            # greeting_sent stays True to bypass GUARD for next response
                        
                        # 🎯 P0-5: RECOVERY for false cancel (Master Instruction)
                        # When response is cancelled before ANY audio was sent:
                        # - Could be false positive (echo/noise triggered turn_detected)
                        # - If user is NOT actually speaking, retry ONCE after 200-300ms
                        # - This prevents silence when cancel was spurious
                        #
                        # Conditions for recovery (ALL must be true):
                        # 1. status == "cancelled"
                        # 2. frames_sent == 0 (no audio was delivered)
                        # 3. !user_has_spoken (not a real user interruption)
                        #
                        # Safety: Only ONE retry per response (prevent loops)
                        if status == "cancelled" and len(output) == 0 and not self.user_has_spoken:
                            # Check if we already retried this response
                            if not self._cancel_retry_attempted:
                                _orig_print(f"🔄 [P0-5] Response cancelled with NO audio and NO user speech - scheduling retry...", flush=True)
                                self._cancelled_response_needs_recovery = True
                                self._cancelled_response_recovery_ts = time.time()
                                self._cancel_retry_attempted = True  # Mark that we're attempting retry
                            else:
                                _orig_print(f"⚠️ [P0-5] Response cancelled again - already attempted retry, not retrying again", flush=True)
                    elif event_type == "response.created":
                        resp_id = event.get("response", {}).get("id", "?")
                        _orig_print(f"🔊 [REALTIME] response.created: id={resp_id[:20]}...", flush=True)
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🎯 TASK D.2: Per-response markers to track audio delivery quality
                        # ═══════════════════════════════════════════════════════════════════════
                        if not hasattr(self, '_response_tracking'):
                            self._response_tracking = {}
                        self._response_tracking[resp_id] = {
                            'start_time': time.time(),
                            'frames_sent': 0,
                            'first_audio_ts': None
                        }
                        # 🔥 TX_RESPONSE: Changed to DEBUG to reduce production spam
                        logger.debug(f"[TX_RESPONSE] start response_id={resp_id[:20]}..., t={time.time():.3f}")
                    elif event_type == "response.audio_transcript.delta":
                        # 🔥 FIX: Update activity timestamp for transcript deltas to prevent watchdog false positives
                        # The AI is actively transcribing its speech, so the call is definitely not idle
                        self._last_activity_ts = time.time()
                        # 🔥 FIX: Gate transcript delta spam - only log in DEVELOPMENT (DEBUG=0)
                        # DEBUG=1 → production (quiet), DEBUG=0 → development (verbose)
                        if not DEBUG:
                            _orig_print(f"🔊 [REALTIME] {event_type}", flush=True)
                    else:
                        # 🔥 FIX: Gate other realtime event logs - only log in DEVELOPMENT (DEBUG=0)
                        if not DEBUG:
                            _orig_print(f"🔊 [REALTIME] {event_type}", flush=True)
                
                # ✅ CRITICAL FIX: Handle response.cancelled event explicitly
                # Per הנחיה: IDEMPOTENT CANCEL - Clear state only for matching response_id
                # Ensure state cleanup even if response.done doesn't arrive
                if event_type == "response.cancelled":
                    _orig_print(f"❌ [REALTIME] RESPONSE CANCELLED: {event}", flush=True)
                    
                    # Extract response_id from event
                    cancelled_resp_id = event.get("response_id")
                    if not cancelled_resp_id and "response" in event:
                        cancelled_resp_id = event.get("response", {}).get("id")
                    
                    # Clear state for this response (IDEMPOTENT - only if it matches active_response_id)
                    if cancelled_resp_id and self.active_response_id == cancelled_resp_id:
                        self.active_response_id = None
                        self.active_response_status = "cancelled"  # 🔥 IDEMPOTENT CANCEL
                        self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                        self.is_ai_speaking_event.clear()
                        self.speaking = False
                        self.barge_in_stop_tx = False  # 🔥 NEW FIX: Re-enable TX transmission
                        logger.info(f"✅ [STATE_RESET] response.cancelled cleanup: active_response_id=None, status=cancelled, cancel_in_flight=False, is_ai_speaking=False, barge_in_stop_tx=False ({cancelled_resp_id[:20]}...)")
                
                # 🔥 DEBUG: Log errors
                if event_type == "error":
                    error = event.get("error", {})
                    error_code = error.get("code", "")
                    
                    # 🔥 FIX: response_cancel_not_active is expected after successful cancellation
                    # This occurs when OpenAI processes cancel asynchronously and sends error event
                    # after the response has already been cancelled. This is NOT a real error.
                    if error_code == "response_cancel_not_active":
                        if DEBUG:
                            logger.debug(f"[REALTIME] response_cancel_not_active (expected after cancel)")
                        # Silently ignore - this is normal behavior
                        continue
                    
                    # Log all other errors as ERROR level
                    _orig_print(f"❌ [REALTIME] ERROR: {error}", flush=True)
                    _orig_print(f"❌ [REALTIME] Error event: {error.get('message', 'Unknown error')}", flush=True)
                    
                    # 🔥 CRITICAL: Validate session.update errors
                    # If session.update fails, the session uses default settings which causes:
                    # - PCM16 instead of G.711 μ-law → "vacuum cleaner" noise on Twilio
                    # - English instead of Hebrew → AI speaks wrong language
                    # - Missing instructions → AI doesn't follow business prompt
                    error_msg = error.get("message", "")
                    error_code = error.get("code", "")
                    error_type = error.get("type", "")
                    
                    # More specific detection: Check error type, code, and message
                    # Known session.update errors:
                    # - type: "invalid_request_error"
                    # - code: "invalid_value" or "invalid_type"
                    # - message contains: "session", "input_audio_noise_reduction", etc.
                    is_session_error = (
                        error_type == "invalid_request_error" and 
                        ("session" in error_msg.lower() or "session" in error_code.lower())
                    )
                    
                    # 🔥 FALLBACK: If noise_reduction caused error, retry without it
                    is_noise_reduction_error = (
                        is_session_error and 
                        "noise_reduction" in error_msg.lower()
                    )
                    
                    if is_noise_reduction_error:
                        _orig_print(f"⚠️ [SESSION ERROR] noise_reduction not supported - retrying without it", flush=True)
                        logger.warning(f"[SESSION ERROR] noise_reduction not supported on this model/version - retrying")
                        
                        # Retry without noise_reduction if we have pending config
                        client = getattr(self, 'realtime_client', None)
                        if client and hasattr(client, '_pending_session_config'):
                            pending_config = client._pending_session_config
                            if pending_config and "input_audio_noise_reduction" in pending_config:
                                # Remove noise_reduction and retry
                                del pending_config["input_audio_noise_reduction"]
                                client._session_config_retry_without_noise_reduction = True
                                
                                _orig_print(f"🔄 [SESSION RETRY] Sending session.update without noise_reduction", flush=True)
                                await client.send_event({
                                    "type": "session.update",
                                    "session": pending_config
                                })
                                logger.info("[SESSION RETRY] Retried session.update without noise_reduction")
                                continue  # Don't mark as failed yet - wait for retry result
                    
                    if is_session_error:
                        _orig_print(f"🚨 [SESSION ERROR] session.update FAILED! Error: {error_msg}", flush=True)
                        _orig_print(f"🚨 [SESSION ERROR] Error type: {error_type}, code: {error_code}", flush=True)
                        _orig_print(f"🚨 [SESSION ERROR] Session will use DEFAULT settings (PCM16, English, no instructions)", flush=True)
                        _orig_print(f"🚨 [SESSION ERROR] This will cause audio noise and wrong language!", flush=True)
                        logger.error(f"[SESSION ERROR] session.update failed - type={error_type}, code={error_code}, msg={error_msg}")
                        
                        # Mark that session configuration failed
                        self._session_config_failed = True
                
                # ═══════════════════════════════════════════════════════════════════════
                # 🔥 STEP 4: session.created - Log only, DO NOT use as fallback
                # ═══════════════════════════════════════════════════════════════════════
                # CRITICAL FIX: session.created shows the INITIAL/DEFAULT state BEFORE session.update is applied
                # OpenAI sends events in this order:
                # 1. session.created (default config, no instructions)
                # 2. [client sends session.update]
                # 3. session.updated (confirmed config with instructions)
                # 
                # If response.create happens between session.created and session.updated, it uses DEFAULT settings:
                # - No instructions (AI doesn't follow prompt)
                # - Default language (English instead of Hebrew)
                # - Wrong audio format (PCM16 instead of g711_ulaw)
                # 
                # NEVER accept session.created as confirmation - only session.updated is valid!
                # ═══════════════════════════════════════════════════════════════════════
                if event_type == "session.created":
                    _orig_print(f"📋 [SESSION] session.created received (baseline state - NOT confirmed)", flush=True)
                    session_data = event.get("session", {})
                    
                    # Log session.created for debugging, but NEVER set _session_config_confirmed
                    # This event shows the state BEFORE session.update is applied
                    if not getattr(self, '_session_config_confirmed', False):
                        output_format = session_data.get("output_audio_format", "unknown")
                        input_format = session_data.get("input_audio_format", "unknown")
                        voice = session_data.get("voice", "unknown")
                        instructions = session_data.get("instructions", "")
                        # 🔥 FIX: Handle None transcription safely - use or {} to prevent crash
                        transcription = session_data.get("input_audio_transcription") or {}
                        turn_detection = session_data.get("turn_detection", {})
                        
                        _orig_print(f"🔍 [SESSION.CREATED] Baseline config (BEFORE session.update): input={input_format}, output={output_format}, voice={voice}, instructions_len={len(instructions)}", flush=True)
                        _orig_print(f"⏳ [SESSION.CREATED] Waiting for session.updated to confirm configuration...", flush=True)
                
                # 🔥 VALIDATION: Confirm session.updated received after session.update
                if event_type == "session.updated":
                    _orig_print(f"✅ [SESSION] session.updated received - configuration applied successfully!", flush=True)
                    
                    # Log the session configuration for verification
                    session_data = event.get("session", {})
                    output_format = session_data.get("output_audio_format", "unknown")
                    input_format = session_data.get("input_audio_format", "unknown")
                    voice = session_data.get("voice", "unknown")
                    instructions = session_data.get("instructions", "")
                    modalities = session_data.get("modalities", [])
                    # 🔥 FIX: Handle None transcription safely - use or {} to prevent crash
                    transcription = session_data.get("input_audio_transcription") or {}
                    turn_detection = session_data.get("turn_detection", {})
                    
                    _orig_print(f"✅ [SESSION] Confirmed settings: input={input_format}, output={output_format}, voice={voice}", flush=True)
                    _orig_print(f"✅ [SESSION] Modalities: {modalities}, transcription: model={transcription.get('model')}, lang={transcription.get('language')}", flush=True)
                    
                    # 🔊 AUDIO_PIPELINE_CONFIG: Log DSP/audio processing parameters
                    # Check for noise reduction, echo cancellation, AGC, or other audio processing
                    input_audio_noise_reduction = session_data.get("input_audio_noise_reduction")
                    # Check for any other DSP-related fields that might exist
                    dsp_fields = []
                    if input_audio_noise_reduction is not None:
                        dsp_fields.append(f"noise_reduction={input_audio_noise_reduction}")
                    
                    # Check for other potential audio processing fields
                    for key in session_data.keys():
                        if any(term in key.lower() for term in ["echo", "aec", "agc", "noise", "gain"]):
                            if key != "input_audio_noise_reduction":  # Already logged above
                                dsp_fields.append(f"{key}={session_data[key]}")
                    
                    if dsp_fields:
                        _orig_print(f"🔊 [AUDIO_PIPELINE_CONFIG] DSP parameters: {', '.join(dsp_fields)}", flush=True)
                        logger.info(f"[AUDIO_PIPELINE_CONFIG] DSP active: {', '.join(dsp_fields)}")
                    else:
                        _orig_print(f"🔊 [AUDIO_PIPELINE_CONFIG] DSP_NOT_CONFIGURED (VAD only, no client-side audio processing)", flush=True)
                        logger.info("[AUDIO_PIPELINE_CONFIG] DSP_NOT_CONFIGURED (VAD only)")
                    
                    # 🚨 CRITICAL VALIDATION: Verify all critical settings
                    validation_failed = False
                    
                    # Validate output format (CRITICAL for Twilio)
                    if output_format != "g711_ulaw":
                        _orig_print(f"🚨 [SESSION ERROR] Wrong output format! Expected g711_ulaw, got {output_format}", flush=True)
                        _orig_print(f"🚨 [SESSION ERROR] Twilio will receive {output_format} and produce noise!", flush=True)
                        logger.error(f"[SESSION ERROR] Wrong output_audio_format: {output_format} (expected g711_ulaw)")
                        validation_failed = True
                    
                    # Validate input format (CRITICAL for Twilio)
                    if input_format != "g711_ulaw":
                        _orig_print(f"🚨 [SESSION ERROR] Wrong input format! Expected g711_ulaw, got {input_format}", flush=True)
                        logger.error(f"[SESSION ERROR] Wrong input_audio_format: {input_format} (expected g711_ulaw)")
                        validation_failed = True
                    
                    # Validate instructions are not empty
                    if not instructions or len(instructions.strip()) < 10:
                        _orig_print(f"🚨 [SESSION ERROR] Instructions are empty or too short! AI will use default behavior", flush=True)
                        logger.error(f"[SESSION ERROR] Instructions missing or invalid (length={len(instructions)})")
                        validation_failed = True
                    
                    # Validate transcription is enabled (safely handle None case)
                    if not transcription or transcription.get("model") != "gpt-4o-transcribe":
                        _orig_print(f"🚨 [SESSION ERROR] Transcription not properly configured!", flush=True)
                        logger.error(f"[SESSION ERROR] Transcription config invalid: {transcription}")
                        validation_failed = True
                    
                    # Validate Hebrew language (only if transcription has language configured)
                    if "language" in transcription and transcription.get("language") != "he":
                        _orig_print(f"⚠️ [SESSION WARNING] Transcription language is not Hebrew: {transcription.get('language')}", flush=True)
                        logger.warning(f"[SESSION WARNING] Transcription language: {transcription.get('language')} (expected 'he')")
                    
                    # Validate turn_detection
                    if not turn_detection or turn_detection.get("type") != "server_vad":
                        _orig_print(f"🚨 [SESSION ERROR] Turn detection not properly configured!", flush=True)
                        logger.error(f"[SESSION ERROR] Turn detection invalid: {turn_detection}")
                        validation_failed = True
                    
                    # Set validation flags
                    if validation_failed:
                        self._session_config_failed = True
                        _orig_print(f"🚨 [SESSION] Configuration INVALID - do NOT proceed with response.create!", flush=True)
                    else:
                        self._session_config_confirmed = True
                        # 🔥 PERFORMANCE: Set event to wake up waiting coroutines instantly
                        self._session_config_event.set()
                        _orig_print(f"✅ [SESSION] All validations passed - safe to proceed with response.create", flush=True)
                        _orig_print(f"✅ [SESSION] validation passed: g711_ulaw + he + server_vad + instructions", flush=True)
                        logger.info("[SESSION] session.updated confirmed - audio format, voice, and instructions are active")
                
                
                # 🚨 COST SAFETY: Log transcription failures but DO NOT retry
                if event_type == "conversation.item.input_audio_transcription.failed":
                    self.transcription_failed_count += 1
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    logger.error(f"[SAFETY] Transcription failed (#{self.transcription_failed_count}): {error_msg}")
                    logger.info(f"[SAFETY] NO RETRY - continuing conversation without transcription")
                    # ✅ Continue processing - don't retry, don't crash, just log and move on
                    continue
                
                # 🎯 Handle function calls from Realtime (appointment scheduling)
                if event_type == "response.function_call_arguments.done":
                    logger.info(f"🔧 [TOOLS][REALTIME] Function call received!")
                    logger.debug(f"[TOOLS][REALTIME] Processing function call from OpenAI Realtime")
                    await self._handle_function_call(event, client)
                    continue
                
                # 🔍 DEBUG: Log all event types to catch duplicates (DEBUG level in production)
                if not event_type.endswith(".delta") and not event_type.startswith("session") and not event_type.startswith("response."):
                    if DEBUG:
                        logger.debug(f"[REALTIME] event: {event_type}")
                    else:
                        logger.info(f"[REALTIME] event: {event_type}")
                
                # 🔥 CRITICAL FIX: Mark user as speaking when speech starts (before transcription completes!)
                # This prevents the GUARD from blocking AI response audio
                if event_type == "input_audio_buffer.speech_started":
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 GREETING PROTECTION FIX + SIMPLE BARGE-IN
                    # ═══════════════════════════════════════════════════════════════════════
                    # Issue: Greeting sometimes interrupted by false speech_started from echo/noise
                    # Solution: During greeting, require REAL speech before allowing barge-in
                    # 
                    # Rules:
                    # 1. During greeting (first 500ms): Block barge-in on speech_started alone
                    #    - Wait for transcription.completed OR 250ms+ of continuous speech
                    #    - This prevents false triggers from echo/background noise
                    # 2. After greeting: Normal barge-in (immediate cancel on speech_started)
                    # 3. Set barge_in=True flag and wait for transcription.completed
                    # ═══════════════════════════════════════════════════════════════════════
                    
                    # 🔥 VERIFICATION: Track speech_started during calibration period
                    if not self._vad_calibration_complete and self._vad_calibration_start_ts:
                        calibration_elapsed = time.time() - self._vad_calibration_start_ts
                        if calibration_elapsed <= 3.0:
                            self._vad_speech_started_count_first_3s += 1
                    
                    if DEBUG:
                        logger.debug(f"[SPEECH_STARTED] User started speaking")
                    else:
                        logger.info(f"🎤 [SPEECH_STARTED] User started speaking")
                    
                    # 🔥 NEW REQUIREMENT: ECHO PROTECTION - Verify real speech vs background noise
                    # Check time since last AI audio to avoid canceling on echo
                    now = time.time()
                    time_since_ai_audio = (now - self._last_ai_audio_ts) * 1000 if self._last_ai_audio_ts else 999999
                    
                    # If speech detected within ECHO_WINDOW after AI audio, be cautious
                    is_in_echo_window = time_since_ai_audio < ECHO_WINDOW_MS
                    
                    if is_in_echo_window:
                        # Within echo window - this might be echo, not real speech
                        # Log but continue - we'll verify with transcription
                        logger.warning(f"⚠️ [ECHO_CHECK] Speech {time_since_ai_audio:.0f}ms after AI (within {ECHO_WINDOW_MS}ms window) - verifying...")

                    # 🔥 REMOVED: greeting_lock check - allow speech detection during greeting
                    
                    # Track utterance start for validation
                    self._candidate_user_speaking = True
                    self._utterance_start_ts = time.time()
                    # ✅ HARD SILENCE WATCHDOG: treat speech_started as user activity
                    # (Even if transcription never arrives, this prevents zombie "quiet but connected" calls.)
                    self._last_user_voice_started_ts = time.time()
                    
                    # 🔥 SILENCE WATCHDOG: Update activity timestamp on VAD detection (not just transcription)
                    # This ensures watchdog tracks actual audio activity, not just completed transcripts
                    self._last_activity_ts = time.time()
                    
                    # Set user_speaking to block new AI responses until transcription completes
                    self.user_speaking = True
                    if DEBUG:
                        logger.debug(f"[TURN_TAKING] user_speaking=True - blocking response.create")
                    else:
                        logger.info(f"🛑 [TURN_TAKING] user_speaking=True - blocking response.create")
                    
                    # Set user_has_spoken flag (user has interacted)
                    if not self.user_has_spoken:
                        self.user_has_spoken = True
                        logger.info(f"✅ [FIRST_SPEECH] user_has_spoken=True")
                    
                    # Reset loop guard when user speaks
                    if self._consecutive_ai_responses > 0:
                        self._consecutive_ai_responses = 0
                        logger.info(f"✅ [LOOP_GUARD] Reset counter on user speech")
                    if self._loop_guard_engaged:
                        self._loop_guard_engaged = False
                        logger.info(f"✅ [LOOP_GUARD] Disengaged on user speech")
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 BARGE-IN LOGIC - ALWAYS CANCEL ON SPEECH_STARTED (Golden Rule)
                    # ═══════════════════════════════════════════════════════════════════════
                    # NEW REQUIREMENT: speech_started => cancel ALWAYS, regardless of other flags
                    # 
                    # Golden Rule: If active_response_id exists, CANCEL IT immediately when user speaks
                    # - Don't wait for is_ai_speaking flag
                    # - Don't wait for voice_frames counter
                    # - Cancel immediately and flush audio queues
                    # 
                    # Exception: Still protect greeting_lock (hard lock during greeting)
                    # ═══════════════════════════════════════════════════════════════════════
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 IDEMPOTENT CANCEL: Cancel response ONCE only, with proper state tracking
                    # ═══════════════════════════════════════════════════════════════════════
                    # Requirements per הנחיה:
                    # 1. If active_response_id is empty → do nothing
                    # 2. If active_response_status != "in_progress" → do nothing
                    # 3. If cancel_in_flight == True → do nothing (already canceling)
                    # 4. Otherwise: Set cancel_in_flight=True, send cancel ONCE, mark locally
                    # 5. Only clear "AI speaking" flags - do NOT reset session/conversation/STT
                    # ═══════════════════════════════════════════════════════════════════════
                    
                    # 🔥 CRITICAL FIX: ALWAYS try to cancel if there's an active response
                    # The old code had too many guards that prevented barge-in from working
                    # NEW RULE: If speech_started AND active_response_id exists → CANCEL IT
                    
                    has_active_response = bool(self.active_response_id)
                    
                    # 🔥 REMOVED: greeting_lock check - allow barge-in during greeting
                    # 🔥 פשוט: אם המשתמש מדבר - עוצרים הכל מיד!
                    
                    # 🔥 המשתמש מדבר - עוצרים הכל מיד! בלי תנאים!
                    _orig_print(f"🎙️ [BARGE-IN] המשתמש מדבר - עוצר את הבוט מיד!", flush=True)
                    
                    # שלב 1: עצירה מיידית של שידור אודיו
                    self.barge_in_stop_tx = True
                    self.barge_in_active = True
                    self._barge_in_started_ts = time.time()
                    _orig_print(f"🛑 [BARGE-IN] barge_in_stop_tx=True - TX loop יעצור מיד", flush=True)
                    
                    # שלב 2: ניקוי דגלים
                    self.is_ai_speaking_event.clear()
                    self.speaking = False
                    if hasattr(self, 'ai_response_active'):
                        self.ai_response_active = False
                    _orig_print(f"✅ [BARGE-IN] דגלי דיבור נוקו - is_ai_speaking=False", flush=True)
                    
                    # שלב 3: ניקוי תורים
                    self._flush_tx_queue()
                    _orig_print(f"🧹 [BARGE-IN] תורים נוקו", flush=True)
                    
                    # שלב 4: שליחת clear ל-Twilio
                    if self.stream_sid:
                        try:
                            clear_event = {"event": "clear", "streamSid": self.stream_sid}
                            self._ws_send(json.dumps(clear_event))
                            _orig_print(f"📤 [BARGE-IN] נשלח clear ל-Twilio", flush=True)
                        except Exception as e:
                            pass
                    
                    # שלב 5: ביטול response ב-OpenAI (אם יש)
                    if has_active_response and self.realtime_client:
                        response_id_to_cancel = self.active_response_id
                        # רק אם עוד לא ביטלנו את אותו response
                        if self._should_send_cancel(response_id_to_cancel):
                            self.cancel_in_flight = True
                            try:
                                await self.realtime_client.cancel_response(response_id_to_cancel)
                                self._mark_response_cancelled_locally(response_id_to_cancel, "barge_in")
                                _orig_print(f"✅ [BARGE-IN] response בוטל ב-OpenAI: {response_id_to_cancel[:20]}...", flush=True)
                            except Exception as e:
                                error_str = str(e).lower()
                                if 'not_active' in error_str or 'no active' in error_str:
                                    _orig_print(f"ℹ️ [BARGE-IN] Response כבר לא פעיל (זה בסדר)", flush=True)
                                else:
                                    _orig_print(f"⚠️ [BARGE-IN] שגיאה בביטול: {e}", flush=True)
                                self.cancel_in_flight = False
                        else:
                            _orig_print(f"ℹ️ [BARGE-IN] Response כבר בוטל קודם", flush=True)
                    
                    _orig_print(f"✅ [BARGE-IN] הבוט נעצר! המשתמש יכול לדבר עכשיו", flush=True)
                    
                    # Enable OpenAI to receive all audio (bypass noise gate)
                    self._realtime_speech_active = True
                    self._realtime_speech_started_ts = time.time()
                    logger.info(f"🎤 [SPEECH_ACTIVE] Bypassing noise gate - sending all audio to OpenAI")
                
                # 🔥 BUILD 166: Clear speech active flag when speech ends
                if event_type == "input_audio_buffer.speech_stopped":
                    self._realtime_speech_active = False
                    # 🔄 ADAPTIVE: Clear OpenAI confirmation flag when speech stops
                    if self._openai_speech_started_confirmed:
                        logger.info(f"🎤 [REALTIME] Speech stopped - clearing OpenAI confirmation flag")
                        self._openai_speech_started_confirmed = False
                    logger.info(f"🎤 [BUILD 166] Speech ended - noise gate RE-ENABLED")
                    
                    # 🔥 CRITICAL: Keep user_speaking=True until transcription.completed
                    # Don't allow response.create between speech_stopped and transcription
                    if DEBUG:
                        logger.debug(f"[TURN_TAKING] Speech stopped - waiting for transcription.completed before allowing response")
                    else:
                        logger.info(f"⏸️ [TURN_TAKING] Speech stopped - waiting for transcription.completed before allowing response")
                    
                    # 🔥 FIX BUG 2: Start timeout for user turn finalization
                    # If no transcription arrives within 1.8s, finalize the turn anyway
                    async def _user_turn_timeout_check():
                        try:
                            await asyncio.sleep(self._user_turn_timeout_ms / 1000.0)
                            # Check if we're still waiting for transcription
                            if self._candidate_user_speaking and not self.user_has_spoken:
                                # Timeout expired - force turn finalization
                                logger.info(f"[TURN_END] 1800ms timeout triggered - finalizing user turn")
                                self._finalize_user_turn_on_timeout()
                        except asyncio.CancelledError:
                            # Task was cancelled (connection closed or transcription received)
                            logger.info(f"[TURN_END] Timeout check cancelled")
                        except Exception as e:
                            # Log but don't crash
                            logger.error(f"[TURN_END] Error in timeout check: {e}")
                    
                    # Schedule timeout check and track it for cleanup
                    timeout_task = asyncio.create_task(_user_turn_timeout_check())
                    if not hasattr(self, '_timeout_tasks'):
                        self._timeout_tasks = []
                    self._timeout_tasks.append(timeout_task)
                    
                    if self._post_greeting_window_active and self._post_greeting_heard_user and not self._post_greeting_speech_cycle_complete:
                        self._post_greeting_speech_cycle_complete = True
                        self._maybe_release_post_greeting_window("user_cycle")
                    
                    # 🔥 BUILD 302: Clear barge-in flag when user finishes speaking
                    if self.barge_in_active:
                        # 🔥 FIX: Guard against None - use 0 duration if timestamp not set
                        barge_start = getattr(self, '_barge_in_started_ts', None)
                        if barge_start is not None:
                            barge_duration = time.time() - barge_start
                        else:
                            barge_duration = 0
                        logger.info(f"✅ [BARGE-IN] User utterance completed - barge-in ended (duration={barge_duration:.1f}s)")
                        self.barge_in_active = False
                        self._barge_in_started_ts = None
                    
                    # 🔥 BUILD 187: Check if we need recovery after cancelled response
                    if self._cancelled_response_needs_recovery:
                        logger.info(f"🔄 [P0-5] Speech stopped - waiting {self._cancelled_response_recovery_delay_sec}s for recovery...")
                        # Schedule a delayed recovery check in a separate task
                        async def _recovery_check():
                            await asyncio.sleep(self._cancelled_response_recovery_delay_sec)
                            # 🎯 P0-5: Multiple guards to prevent double triggers
                            # Guard 1: Check if recovery is still needed
                            if not self._cancelled_response_needs_recovery:
                                logger.info(f"🔄 [P0-5] Recovery cancelled - flag cleared")
                                return
                            # Guard 2: Check if AI is already speaking
                            if self.is_ai_speaking_event.is_set():
                                self._cancelled_response_needs_recovery = False
                                logger.info(f"🔄 [P0-5] Recovery skipped - AI already speaking")
                                return
                            # Guard 3: Check if there's a pending response
                            if self.response_pending_event.is_set():
                                self._cancelled_response_needs_recovery = False
                                logger.info(f"🔄 [P0-5] Recovery skipped - response pending")
                                return
                            # Guard 4: Check if user is speaking (prevents retry during real user speech)
                            if self._realtime_speech_active or self.user_has_spoken:
                                self._cancelled_response_needs_recovery = False
                                logger.info(f"🔄 [P0-5] Recovery skipped - user is speaking")
                                return
                            
                            # All guards passed - trigger recovery via central function
                            # 🔥 BUILD 200: Use trigger_response for consistent response management
                            self._cancelled_response_needs_recovery = False  # Clear BEFORE triggering
                            triggered = await self.trigger_response("P0-5_FALSE_CANCEL_RECOVERY", client)
                            if not triggered:
                                logger.warning(f"⚠️ [P0-5] Recovery was blocked by trigger_response guards")
                            else:
                                logger.info(f"✅ [P0-5] Recovery response triggered successfully")
                        asyncio.create_task(_recovery_check())
                
                # 🔥 Track response ID for barge-in cancellation
                if event_type == "response.created":
                    response = event.get("response", {})
                    response_id = response.get("id")
                    # 🔍 DEBUG: Log full response configuration to diagnose missing audio
                    output_audio_format = response.get("output_audio_format", "NONE")
                    modalities = response.get("modalities", [])
                    status = response.get("status", "?")
                    _orig_print(f"🎯 [RESPONSE.CREATED] id={response_id[:20] if response_id else '?'}... status={status} modalities={modalities} output_format={output_audio_format}", flush=True)
                    if response_id:
                        # 🔥 BARGE-IN FIX: Set BOTH active_response_id AND ai_response_active immediately
                        # Per הנחיה: Enable barge-in detection on response.created (not audio.delta)
                        # This allows cancellation even if audio hasn't started yet
                        self.active_response_id = response_id
                        self.active_response_status = "in_progress"  # 🔥 IDEMPOTENT CANCEL: Mark as in_progress
                        self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag for new response
                        self.response_pending_event.clear()  # 🔒 Clear thread-safe lock

                        # 🔥 REMOVED: greeting_lock binding - no longer needed
                        
                        # 🔥 NEW: Set ai_response_active=True immediately (per requirements)
                        # This is THE fix for barge-in timing issues
                        # ai_response_active means "response exists and can be cancelled"
                        # is_ai_speaking will still be set on first audio.delta when actual audio arrives
                        if not hasattr(self, 'ai_response_active'):
                            self.ai_response_active = False
                        self.ai_response_active = True
                        _orig_print(f"✅ [BARGE-IN] ai_response_active=True, status=in_progress on response.created (id={response_id[:20]}...)", flush=True)
                        self.barge_in_active = False  # Reset barge-in flag for new response
                        self.barge_in_stop_tx = False  # 🔥 NEW FIX: Re-enable TX transmission for new response
                        logger.info(f"🔊 [RESPONSE.CREATED] response_id={response_id[:20]}... stored for cancellation (is_ai_speaking will be set on first audio.delta)")
                        
                        logger.info(f"[BARGE_IN] Stored active_response_id={response_id[:20]}... for cancellation")
                        # 🔥 BUILD 187: Response grace period - track when response started
                        # This prevents false turn_detected from echo/noise in first 500ms
                        self._response_created_ts = time.time()
                        # 🔥 BUILD 187: Clear recovery flag - new response was created!
                        if self._cancelled_response_needs_recovery:
                            logger.info(f"🔄 [P0-5] New response created - cancelling recovery")
                            self._cancelled_response_needs_recovery = False
                        # 🎯 P0-5: Reset retry flag for new response (allows recovery for this response)
                        self._cancel_retry_attempted = False
                        # 🔥 BUILD 305: Reset gap detector for new response
                        # This prevents false "AUDIO GAP" warnings between responses
                        self._last_audio_chunk_ts = time.time()
                        self._openai_audio_chunks_received = 0
                        
                        # 🔥 SILENCE FAILSAFE: Cancel any pending response timeout
                        # Response was created, so we're not stuck in silence
                        if hasattr(self, '_response_timeout_task') and self._response_timeout_task:
                            if not self._response_timeout_task.done():
                                self._response_timeout_task.cancel()
                            self._response_timeout_task = None
                            logger.info("[SILENCE_FAILSAFE] Response created - cancelled pending timeout")
                
                # ✅ ONLY handle audio.delta - ignore other audio events!
                # 🔥 FIX: Use response.audio_transcript.delta for is_ai_speaking (reliable text-based flag)
                if event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    response_id = event.get("response_id", "")
                    if audio_b64:
                        # ═══════════════════════════════════════════════════════════════
                        # 🔥 TX DIAGNOSTIC: Log audio delta → queue pipeline (DEBUG only)
                        # ═══════════════════════════════════════════════════════════════
                        import base64
                        audio_bytes = base64.b64decode(audio_b64)
                        logger.debug(f"[AUDIO_DELTA] response_id={response_id[:20] if response_id else '?'}..., bytes={len(audio_bytes)}, base64_len={len(audio_b64)}")
                        
                        # 🔥 CRITICAL BARGE-IN FIX: Update is_ai_speaking FIRST, before any guards!
                        # This ensures the system ALWAYS knows the AI is speaking, even if audio is blocked
                        # This is essential for mid-sentence barge-in detection during long responses
                        now = time.time()
                        if not self.is_ai_speaking_event.is_set():
                            # First audio delta - initialize timestamps
                            if DEBUG:
                                logger.info(f"🔊 [REALTIME] AI started speaking (audio.delta)")
                            logger.info(f"🔊 [STATE] AI started speaking (first audio.delta) - is_ai_speaking=True")
                            self.ai_speaking_start_ts = now
                            self.speaking_start_ts = now
                            self.speaking = True
                            self._last_ai_audio_start_ts = now
                            if self._cancelled_response_needs_recovery:
                                logger.info(f"🔄 [P0-5] Audio started - cancelling recovery")
                                self._cancelled_response_needs_recovery = False
                        
                        # 🔥 CRITICAL: Set flag on EVERY audio.delta to maintain state during long responses
                        self.is_ai_speaking_event.set()  # Thread-safe: AI is speaking
                        self.speaking = True  # Ensure synchronization
                        self.has_pending_ai_response = True
                        self.last_ai_audio_ts = now
                        self._last_ai_audio_ts = now  # For echo detection
                        
                        # 🔥 SILENCE WATCHDOG: Update activity timestamp when bot speaks (response.audio.delta)
                        # This prevents watchdog from disconnecting during active bot responses
                        self._last_activity_ts = now
                        
                        # 🛑 BUILD 165: LOOP GUARD - DROP all AI audio when engaged
                        # 🔥 BUILD 178: Disabled for outbound calls
                        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
                        if self._loop_guard_engaged and not is_outbound:
                            # Silently drop audio - don't even log each frame
                            continue
                        
                        # 🎯 FIX A: GREETING MODE - Only apply to FIRST response, not all responses!
                        # OLD: if self.greeting_sent and not self.user_has_spoken:
                        # NEW: Only when greeting_mode_active (first response only)
                        if self.greeting_mode_active and not self.greeting_completed:
                            # ═══════════════════════════════════════════════════════════════
                            # 🔥 REALTIME STABILITY: Mark greeting audio as received
                            # ═══════════════════════════════════════════════════════════════
                            now = time.time()
                            if not self._greeting_audio_received:
                                self._greeting_audio_received = True
                                self._greeting_audio_first_ts = now
                                # Calculate time from greeting trigger to first audio
                                greeting_start = getattr(self, '_greeting_start_ts', now)
                                first_audio_ms = int((now - greeting_start) * 1000)
                                self._metrics_first_greeting_audio_ms = first_audio_ms
                                _orig_print(f"🎤 [GREETING] FIRST_AUDIO_DELTA received! delay={first_audio_ms}ms", flush=True)
                                
                                # 🔥 MASTER FIX: Store first_greeting_audio_ms metric
                                from server.stream_state import stream_registry
                                if self.call_sid:
                                    stream_registry.set_metric(self.call_sid, 'first_greeting_audio_ms', first_audio_ms)
                                    
                                    # 🔥 MASTER FIX: Log structured greeting metrics
                                    call_direction = getattr(self, 'call_direction', 'inbound')
                                    openai_connect_ms = getattr(self, '_metrics_openai_connect_ms', 0)
                                    logger.info(f"[GREETING_METRICS] openai_connect_ms={openai_connect_ms}, first_greeting_audio_ms={first_audio_ms}, direction={call_direction}")
                            
                            # 🔥 TASK 0.4: THROTTLED GREETING LOG - Log only first chunk, not all chunks
                            if not hasattr(self, '_greeting_audio_started_logged'):
                                self._greeting_audio_started_logged = False
                            if not self._greeting_audio_started_logged:
                                logger.info(f"[GREETING] Passing greeting audio to caller (greeting_sent={self.greeting_sent}, user_has_spoken={self.user_has_spoken})")
                                self._greeting_audio_started_logged = True
                            # Enqueue greeting audio - NO guards, NO cancellation
                            # Note: is_ai_speaking already set above at start of audio.delta handler
                            self.is_playing_greeting = True
                            # 🔥 VERIFICATION #3: Block enqueue if closed
                            if not self.closed:
                                try:
                                    # 🔥 NEW: BACKLOG GUARD - Monitor realtime_audio_out_queue overflow
                                    self._check_queue_backlog(
                                        self.realtime_audio_out_queue,
                                        'realtime_audio_out_queue',
                                        threshold=200
                                    )
                                    
                                    self.realtime_audio_out_queue.put_nowait(audio_b64)
                                    # 🎯 PROBE 4: Track enqueue for rate monitoring
                                    self._enq_counter += 1
                                    
                                    # 🔥 TX DIAGNOSTICS: Log greeting audio bytes queued
                                    if not hasattr(self, '_greeting_audio_bytes_queued'):
                                        self._greeting_audio_bytes_queued = 0
                                        self._greeting_audio_chunks_queued = 0
                                    self._greeting_audio_bytes_queued += len(audio_b64)
                                    self._greeting_audio_chunks_queued += 1
                                    
                                    # Log first and every 10th chunk
                                    if DEBUG_TX and (self._greeting_audio_chunks_queued == 1 or self._greeting_audio_chunks_queued % 10 == 0):
                                        _orig_print(
                                            f"📊 [TX_DIAG] Greeting audio queued: {self._greeting_audio_chunks_queued} chunks, {self._greeting_audio_bytes_queued} bytes (streamSid={self.stream_sid is not None})",
                                            flush=True,
                                        )
                                    now_mono = time.monotonic()
                                    if now_mono - self._enq_last_log_time >= 1.0:
                                        qsize = self.realtime_audio_out_queue.qsize()
                                        if DEBUG_TX:
                                            _orig_print(f"[ENQ_RATE] frames_enqueued_per_sec={self._enq_counter}, qsize={qsize}", flush=True)
                                        self._enq_counter = 0
                                        self._enq_last_log_time = now_mono
                                except queue.Full:
                                    pass
                            continue
                        
                        # 🛡️ GUARD: Block AI audio before first real user utterance (non-greeting)
                        # ✅ RULE 3: Allow greeting audio even before user speaks
                        # In SIMPLE_MODE, we trust speech_started event + RMS to detect real user speech
                        is_greeting_response = self.greeting_mode_active and not self.greeting_completed
                        if not SIMPLE_MODE and not self.user_has_spoken and not is_greeting_response:
                            # User never spoke, and this is not the greeting – block it
                            logger.info(f"[GUARD] Blocking AI audio response before first real user utterance (greeting_sent={getattr(self, 'greeting_sent', False)}, user_has_spoken={self.user_has_spoken})")
                            # If there is a response_id in the event, send response.cancel once (with duplicate guard)
                            response_id = event.get("response_id")
                            if response_id and self._should_send_cancel(response_id):
                                try:
                                    await client.send_event({
                                        "type": "response.cancel",
                                        "response_id": response_id,
                                    })
                                    self._mark_response_cancelled_locally(response_id, "pre_user_guard")
                                except Exception:
                                    logger.error("[GUARD] Failed to send response.cancel for pre-user-response")
                            continue  # do NOT enqueue audio for TTS
                        
                        # Note: is_ai_speaking was already set at the beginning of audio.delta handler (before all guards)
                        # This ensures proper barge-in detection even when audio is blocked by guards
                        
                        # 💰 COST TRACKING: Count AI audio chunks
                        # μ-law 8kHz: ~160 bytes per 20ms chunk = 50 chunks/second
                        if not hasattr(self, '_ai_speech_start') or self._ai_speech_start is None:
                            self._ai_speech_start = now
                        # Counter initialized in __init__ - direct increment (no getattr masking)
                        self.realtime_audio_out_chunks += 1
                        
                        # ✅ P0-3: Track last audio delta timestamp for watchdog
                        self._last_audio_delta_ts = now
                        
                        # 🔍 DEBUG: Verify μ-law format from OpenAI + GAP DETECTION
                        if not hasattr(self, '_openai_audio_chunks_received'):
                            self._openai_audio_chunks_received = 0
                            self._last_audio_chunk_ts = now
                        self._openai_audio_chunks_received += 1
                        
                        # 🔍 GAP DETECTION: Log if >500ms between chunks (potential pause source)
                        gap_ms = (now - getattr(self, '_last_audio_chunk_ts', now)) * 1000
                        if gap_ms > 500 and self._openai_audio_chunks_received > 3:
                            logger.warning(f"⚠️ [AUDIO GAP] {gap_ms:.0f}ms gap between chunks #{self._openai_audio_chunks_received-1} and #{self._openai_audio_chunks_received} - OpenAI delay!")
                            
                            # 🔥 BUILD 181: GAP RECOVERY - Insert silence frames for gaps >3 seconds
                            # 🔥 BUILD 320: DISABLED when AUDIO_GUARD is ON - let real timing flow naturally
                            # 🔥 FIX #3: Fill up to 2000ms instead of 500ms for better stream stability
                            # This prevents audio distortion by maintaining continuous playback
                            if gap_ms > 3000 and not getattr(self, '_audio_guard_enabled', False):
                                # Calculate how many silence frames needed to smooth transition
                                # Fill up to 2000ms cap (was 500ms) to stabilize stream
                                fill_ms = min(gap_ms, 2000)  # Cap at 2000ms as per fix requirements
                                silence_frames_needed = int(fill_ms / 20)  # 20ms per frame
                                import base64
                                # Generate 160-byte μ-law silence frames (0xFF = silence in μ-law)
                                silence_frame = base64.b64encode(bytes([0xFF] * 160)).decode('utf-8')
                                # 🔥 VERIFICATION #3: Block silence fill if closed
                                if not self.closed:
                                    for _ in range(silence_frames_needed):
                                        try:
                                            self.realtime_audio_out_queue.put_nowait(silence_frame)
                                            # 🎯 PROBE 4: Track enqueue for rate monitoring
                                            self._enq_counter += 1
                                        except queue.Full:
                                            break
                                logger.info(f"🔧 [GAP RECOVERY] Inserted {silence_frames_needed} silence frames ({silence_frames_needed * 20}ms) for {gap_ms:.0f}ms gap")
                        self._last_audio_chunk_ts = now
                        
                        if self._openai_audio_chunks_received <= 3:
                            import base64
                            chunk_bytes = base64.b64decode(audio_b64)
                            first5_bytes = ' '.join([f'{b:02x}' for b in chunk_bytes[:5]])
                            
                            # 🔥 BARGE-IN FIX: Better logging to distinguish greeting vs. regular AI talk
                            audio_type = "[GREETING]" if self.is_playing_greeting else "[AI_TALK]"
                            if DEBUG:
                                logger.debug(f"{audio_type} chunk from OpenAI: chunk#{self._openai_audio_chunks_received}, bytes={len(chunk_bytes)}, first5={first5_bytes}")
                            else:
                                logger.info(f"{audio_type} Audio chunk from OpenAI: chunk#{self._openai_audio_chunks_received}, bytes={len(chunk_bytes)}, first5={first5_bytes} | greeting_sent={self.greeting_sent}, user_has_spoken={self.user_has_spoken}, is_ai_speaking={self.is_ai_speaking_event.is_set()}")
                        
                        # 🔥 VERIFICATION #3: Block audio enqueue if closed
                        if not self.closed:
                            try:
                                # 🔥 NEW: BACKLOG GUARD - Monitor realtime_audio_out_queue overflow
                                self._check_queue_backlog(
                                    self.realtime_audio_out_queue,
                                    'realtime_audio_out_queue',
                                    threshold=200
                                )
                                
                                self.realtime_audio_out_queue.put_nowait(audio_b64)
                                # 🎯 PROBE 4: Track enqueue for rate monitoring
                                self._enq_counter += 1
                                now_mono = time.monotonic()
                                if now_mono - self._enq_last_log_time >= 1.0:
                                    qsize = self.realtime_audio_out_queue.qsize()
                                    if DEBUG_TX:
                                        _orig_print(f"[ENQ_RATE] frames_enqueued_per_sec={self._enq_counter}, qsize={qsize}", flush=True)
                                    self._enq_counter = 0
                                    self._enq_last_log_time = now_mono
                                # 🎯 TASK D.2: Track frames sent for this response
                                response_id = event.get("response_id")
                                if response_id and hasattr(self, '_response_tracking') and response_id in self._response_tracking:
                                    self._response_tracking[response_id]['frames_sent'] += 1
                                    if self._response_tracking[response_id]['first_audio_ts'] is None:
                                        self._response_tracking[response_id]['first_audio_ts'] = time.time()
                            except queue.Full:
                                pass
                
                # ❌ IGNORE these audio events - they contain duplicate/complete audio buffers:
                elif event_type in ("response.audio.done", "response.output_item.done"):
                    # 🔥 FIX: Update activity timestamp when audio or output item completes
                    # The AI is finishing a response, so the call is definitely active
                    self._last_activity_ts = time.time()
                    
                    # 🎯 FIX: Track audio.done per response_id (for race condition handling)
                    if event_type == "response.audio.done":
                        done_resp_id = event.get("response_id") or (event.get("response", {}) or {}).get("id")
                        if done_resp_id:
                            # Track this response as done
                            self.audio_done_by_response_id[done_resp_id] = True
                            
                            # Cleanup: Keep only last 2 response_ids to prevent memory leak
                            if len(self.audio_done_by_response_id) > 2:
                                # Remove oldest entries (keep 2 most recent)
                                keys = list(self.audio_done_by_response_id.keys())
                                for old_key in keys[:-2]:
                                    del self.audio_done_by_response_id[old_key]
                    
                    # 🔥 REMOVED: greeting_lock release logic - no longer needed

                    # 🎯 FIX A: Complete greeting mode after FIRST response only
                    if self.greeting_mode_active and not self.greeting_completed:
                        greeting_end_ts = time.time()
                        greeting_duration = 0
                        if hasattr(self, '_greeting_start_ts') and self._greeting_start_ts:
                            greeting_duration = (greeting_end_ts - self._greeting_start_ts) * 1000
                        logger.info(f"🎤 [GREETING] Greeting finished at {greeting_end_ts:.3f} (duration: {greeting_duration:.0f}ms)")
                        
                        # 🎯 FIX A: Mark greeting as completed - ALL future responses are NORMAL
                        self.greeting_mode_active = False
                        self.greeting_completed = True
                        self.is_playing_greeting = False
                        _orig_print(f"✅ [GREETING] Completed - switching to NORMAL AI responses. From now on NO greeting protect.", flush=True)
                        
                        # 🔥 PERFORMANCE: Mark call as live (DB access forbidden from now on)
                        self.in_live_call = True
                        logger.info(f"🔒 [DB_GUARD] Live call active - DB access blocked until call ends")
                        
                        # 🎯 FIX: Enable barge-in after greeting completes
                        # Use dedicated flag instead of user_has_spoken to preserve guards
                        self.barge_in_enabled_after_greeting = True
                        logger.info(f"✅ [GREETING] Barge-in now ENABLED for rest of call")
                    elif self.is_playing_greeting:
                        # This shouldn't happen after our fix, but handle gracefully
                        logger.warning(f"⚠️ [GREETING] is_playing_greeting was True but greeting already completed - clearing flag")
                        self.is_playing_greeting = False
                        
                        # 🔥 MASTER FIX: Validation check for greeting SLA
                        self._validate_greeting_sla()
                        # 🔥 PROTECTION: Mark greeting completion time for hangup protection
                        self.greeting_completed_at = time.time()
                        logger.info(f"🛡️ [PROTECTION] Greeting completed - hangup blocked for {self.min_call_duration_after_greeting_ms}ms")
                        
                        # 🔥 BUILD 303: GREETING FLOW - Now waiting for first user utterance
                        # Don't let AI create new response until user answers the greeting question
                        self.awaiting_greeting_answer = True
                        self.first_post_greeting_utterance_handled = False
                        logger.info(f"⏳ [BUILD 303] Waiting for user's first response to greeting...")
                        self._post_greeting_window_active = True
                        self._post_greeting_window_started_at = time.time()
                        self._post_greeting_window_finished = False
                        self._post_greeting_heard_user = False
                        self._post_greeting_speech_cycle_complete = False
                        logger.info(f"🧘 [GREETING] Breathing window started ({self._post_greeting_breath_window_sec:.1f}s)")
                        
                        # 🔥 BUILD 172: Transition to ACTIVE state and start silence monitor
                        if self.call_state == CallState.WARMUP:
                            self.call_state = CallState.ACTIVE
                            logger.info(f"📞 [STATE] Transitioned WARMUP → ACTIVE (greeting done)")
                            asyncio.create_task(self._start_silence_monitor())
                    
                    # Don't process - would cause duplicate playback
                    # 🎯 Mark AI response complete
                    if self.is_ai_speaking_event.is_set():
                        logger.info(f"🔇 [REALTIME] AI stopped speaking ({event_type})")
                    self.is_ai_speaking_event.clear()  # Thread-safe: AI stopped speaking
                    self.speaking = False  # 🔥 BUILD 165: SYNC with self.speaking flag
                    self.ai_speaking_start_ts = None  # 🔥 FIX: Clear start timestamp
                    
                    # 🔥 Track when AI finished speaking (for metrics only, no cooldown enforcement)
                    self._ai_finished_speaking_ts = time.time()
                    
                    # 🔥 BUILD 172: Update speech time for silence detection
                    self._update_speech_time()
                    
                    # 🔥🔥 CRITICAL FIX: Do NOT clear audio queue here!
                    # The queue may still have audio chunks that need to be sent to Twilio.
                    # Clearing prematurely causes greeting/response truncation!
                    # Let the audio bridge naturally drain the queue.
                    queue_size = self.realtime_audio_out_queue.qsize()
                    if queue_size > 0:
                        logger.info(f"⏳ [AUDIO] {queue_size} frames still in queue - letting them play (NO TRUNCATION)")
                    
                    self.has_pending_ai_response = False
                    self.active_response_id = None  # Clear response ID
                    self.active_response_status = "done"  # 🔥 IDEMPOTENT CANCEL: Mark as done (audio.done)
                    self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                    self.response_pending_event.clear()  # 🔒 Clear thread-safe lock
                    
                    # 🎯 SINGLE SOURCE OF TRUTH: Check for hangup via maybe_execute_hangup()
                    if event_type == "response.audio.done":
                        done_resp_id = event.get("response_id") or (event.get("response", {}) or {}).get("id")
                        if done_resp_id:
                            # Cancel fallback timer (if any) now that we got audio.done
                            try:
                                t = getattr(self, "_pending_hangup_fallback_task", None)
                                if t and not t.done():
                                    t.cancel()
                            except Exception:
                                pass
                            
                            # Wait for audio to drain, then try to execute hangup
                            async def delayed_hangup():
                                # 🔥 FIX: TRUE AUDIO DRAIN - Calculate exact time needed for remaining frames
                                # Per expert feedback: Must wait for frames to actually PLAY, not just transmit
                                
                                # Capture initial queue sizes at audio.done moment
                                initial_q1_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
                                initial_tx_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
                                total_frames_remaining = initial_q1_size + initial_tx_size
                                
                                if total_frames_remaining > 0:
                                    # Calculate time needed: each frame = 20ms, plus 400ms buffer for Twilio playback
                                    remaining_ms = total_frames_remaining * 20
                                    buffer_ms = 400
                                    total_wait_ms = remaining_ms + buffer_ms
                                    _orig_print(f"⏳ [AUDIO DRAIN] {total_frames_remaining} frames remaining (q1={initial_q1_size}, tx={initial_tx_size}) → waiting {total_wait_ms}ms", flush=True)
                                
                                # STEP 1: Wait for OpenAI queue to drain (max 30 seconds for long sentences)
                                for i in range(300):  # 300 * 100ms = 30 seconds max (was 5s)
                                    q1_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
                                    if q1_size == 0:
                                        if DEBUG:
                                            _orig_print(f"✅ [POLITE HANGUP] OpenAI queue empty after {i*100}ms", flush=True)
                                        break
                                    await asyncio.sleep(0.1)
                                
                                # STEP 2: Wait for Twilio TX queue to drain (max 60 seconds for long sentences)
                                last_tx_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
                                stuck_iterations = 0
                                STUCK_THRESHOLD = 10  # 1000ms without progress (10 * 100ms) - increased from 500ms
                                
                                for i in range(600):  # 600 * 100ms = 60 seconds max (was 10s)
                                    tx_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
                                    if tx_size == 0:
                                        if DEBUG:
                                            _orig_print(f"✅ [POLITE HANGUP] TX queue empty after {i*100}ms", flush=True)
                                        break
                                    
                                    # Detect stuck queue (1000ms without progress)
                                    if tx_size == last_tx_size:
                                        stuck_iterations += 1
                                        if stuck_iterations >= STUCK_THRESHOLD:
                                            # Check if TX thread is dead or stop flag set
                                            tx_running = getattr(self, 'tx_running', False)
                                            if not tx_running:
                                                # TX thread stopped but queue has frames - proceed with hangup
                                                _orig_print(f"⚠️ [POLITE HANGUP] TX thread stopped with {tx_size} frames stuck - proceeding anyway", flush=True)
                                                break
                                    else:
                                        stuck_iterations = 0
                                    
                                    last_tx_size = tx_size
                                    await asyncio.sleep(0.1)
                                
                                # STEP 3: Extra buffer for Twilio/network to actually PLAY the last frames
                                # This is critical - Twilio needs time to play frames even after we send them
                                playback_buffer_seconds = 0.5  # 500ms buffer for Twilio playback latency
                                _orig_print(f"⏳ [AUDIO DRAIN] Queues empty, waiting {playback_buffer_seconds}s for Twilio playback", flush=True)
                                await asyncio.sleep(playback_buffer_seconds)
                                
                                # Now try to execute hangup via single source of truth
                                await self.maybe_execute_hangup(via="audio.done", response_id=done_resp_id)
                            
                            asyncio.create_task(delayed_hangup())
                
                elif event_type == "response.audio_transcript.done":
                    # 🔥 FIX: Update activity timestamp when transcript completes
                    # The AI just finished transcribing its speech, so the call is active
                    self._last_activity_ts = time.time()
                    
                    transcript = event.get("transcript", "")
                    if transcript:
                        logger.info(f"🤖 [REALTIME] AI said: {transcript}")
                        
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🔥 VOICEMAIL DETECTION: Check AI transcript too (first 10 seconds only)
                        # ═══════════════════════════════════════════════════════════════════════
                        # Voicemail messages sometimes appear in AI transcript (response.audio_transcript)
                        # instead of user transcript, depending on the audio pipeline
                        await self._maybe_hangup_voicemail(transcript)

                        # 🔴 BYE-ONLY HANGUP: Disconnect ONLY if BOT says explicit goodbye phrases
                        # CRITICAL RULES (SIMPLIFIED):
                        # 1. Only BOT saying bye (not user) - checked by event type (response.audio_transcript.done)
                        # 2. Must match ביי OR להתראות (word boundary, anywhere in text)
                        # 3. Mark for hangup but DON'T execute until response.audio.done + queue drain
                        # 4. No complex logic - just simple keyword matching
                        try:
                            _t_raw = (transcript or "").strip()
                            
                            # 🔥 SIMPLIFIED: Just check if ביי OR להתראות appears with word boundaries
                            # No need to check "end of sentence" - just presence of goodbye keyword
                            # This matches: "ביי", "תודה ביי", "ביי ולהתראות", "להתראות", etc.
                            # ✅ CRITICAL: Simple regex - one of two words must appear
                            has_goodbye = re.search(r"\b(ביי|ו?להתראות)\b", _t_raw)
                            
                            if has_goodbye:
                                resp_id = event.get('response_id')
                                # 🔥 FIX: Log full text without truncation to see complete goodbye sentence
                                logger.info(f"[BOT_BYE_DETECTED] resp_id={resp_id} text='{_t_raw}'")
                                logger.info(f"[BOT_BYE_DETECTED] resp_id={resp_id} text='{_t_raw}'")
                                
                                # 🔥 FIX: Only MARK for hangup, don't execute until audio.done
                                # This ensures AI finishes saying the entire goodbye sentence
                                await self.request_hangup(
                                    "bot_goodbye_bye_only",  # 🔥 NEW REASON: Explicit bye-only
                                    "response.audio_transcript.done",
                                    _t_raw,
                                    "bot",
                                    response_id=resp_id,
                                )
                                logger.info(f"[BOT_BYE] Marked for hangup - will execute after audio completes (response.audio.done)")
                                
                                # ⚠️ REMOVED: Don't check audio_already_done here
                                # Let the response.audio.done handler do the hangup AFTER audio completes
                                # This ensures the AI finishes speaking the entire sentence
                                
                                continue
                        except Exception as e:
                            # Never break the realtime loop due to hangup matching errors.
                            logger.error(f"⚠️ [BOT_BYE_DETECT] Error checking goodbye: {e}")
                            pass
                        
                        # ⭐ BUILD 350: SIMPLE KEYWORD-BASED APPOINTMENT DETECTION
                        # Only if appointments are enabled in business settings
                        if not ENABLE_LEGACY_TOOLS:
                            self._check_simple_appointment_keywords(transcript)
                        
                        # 🔥 BUILD 336: CONFIRMATION VALIDATION - Check if AI said what we asked
                        if self._expected_confirmation and not self._confirmation_validated:
                            expected = self._expected_confirmation
                            
                            # 🔥 BUILD 338 FIX: Enhanced Hebrew normalization for validation
                            def _normalize_hebrew(text):
                                """Normalize Hebrew text for comparison (strip punctuation, diacritics, prefixes, plural)"""
                                import unicodedata
                                import re
                                # NFKC normalization
                                text = unicodedata.normalize('NFKC', text)
                                # Strip Hebrew diacritics (nikud)
                                text = re.sub(r'[\u0591-\u05C7]', '', text)
                                # Strip punctuation
                                text = re.sub(r'[\.,:;!\?"\'\(\)\-–—]', '', text)
                                # Collapse whitespace
                                text = ' '.join(text.split())
                                return text.strip()
                            
                            def _normalize_hebrew_token(word):
                                """Normalize a single Hebrew word - remove prefixes and plural suffixes"""
                                import re
                                # Remove common Hebrew prefixes: ב/ל/ה/מ/ו/ש/כ
                                # Must be at least 3 chars after stripping to avoid over-stripping
                                prefixes = ['וב', 'ול', 'וה', 'ומ', 'ב', 'ל', 'ה', 'מ', 'ו', 'ש', 'כ']
                                stripped = word
                                for prefix in prefixes:
                                    if word.startswith(prefix) and len(word) > len(prefix) + 2:
                                        stripped = word[len(prefix):]
                                        break
                                
                                # Handle plural suffixes: ים/ות
                                # צילינדרים → צילינדר, דלתות → דלת
                                if stripped.endswith('ים') and len(stripped) > 4:
                                    stripped = stripped[:-2]
                                elif stripped.endswith('ות') and len(stripped) > 4:
                                    stripped = stripped[:-2]
                                
                                return stripped
                            
                            def _tokens_match_flexibly(expected_tokens, actual_tokens):
                                """Check if tokens match with Hebrew prefix/plural flexibility"""
                                # Normalize all tokens
                                normalized_expected = {_normalize_hebrew_token(t) for t in expected_tokens}
                                normalized_actual = {_normalize_hebrew_token(t) for t in actual_tokens}
                                
                                # Find truly extra tokens (after normalization)
                                return normalized_actual - normalized_expected
                            
                            normalized_transcript = _normalize_hebrew(transcript)
                            normalized_expected = _normalize_hebrew(expected)
                            
                            # 🔥 BUILD 338 FIX: TOKEN-BASED VALIDATION WITH HEBREW PREFIX/PLURAL FLEXIBILITY
                            # AI must say the expected confirmation with NO extra substantive content
                            # Strategy: Tokenize both, normalize with Hebrew rules, ensure no unexpected tokens
                            
                            # Get expected tokens (what we told AI to say)
                            expected_tokens = set(normalized_expected.split())
                            
                            # Get AI's actual tokens
                            actual_tokens = set(normalized_transcript.split())
                            
                            # 🔥 BUILD 338: Use flexible Hebrew matching for extra token detection
                            # This handles: "בעפולה" ↔ "עפולה", "צילינדרים" ↔ "צילינדר"
                            extra_tokens_flexible = _tokens_match_flexibly(expected_tokens, actual_tokens)
                            
                            # Allowed filler tokens (greetings, acknowledgements, and harmless location words)
                            # 🔥 BUILD 338: Also normalize the filler for comparison
                            # 🔥 BUILD 339: Added "עיר" and "בעיר" as harmless filler (they don't change meaning)
                            allowed_filler = {
                                # Greetings and acknowledgements
                                "כן", "בסדר", "אוקיי", "טוב", "יופי", "אמ", "אה", "אז", "נו", "בבקשה", "תודה", "נכון", "מצוין",
                                # Function words / prepositions that don't change meaning
                                "עיר", "בעיר", "ב", "ל", "של", "את", "אתה", "אני", "זה", "זו", "היא", "הוא",
                                "רק", "מוודא", "האם", "צריך", "צריכה", "צריכים",
                                "מאוד", "באמת", "כבר", "עכשיו", "שוב", "עוד", "גם", "רגע"
                            }
                            allowed_filler_normalized = {_normalize_hebrew_token(t) for t in allowed_filler}
                            
                            # Remove allowed filler from extra tokens
                            substantive_extras = extra_tokens_flexible - allowed_filler_normalized
                            
                            # 🔥 BUILD 338 DEBUG: Log the comparison details
                            if extra_tokens_flexible:
                                logger.info(f"🔍 [BUILD 338] Extra tokens (after prefix/plural normalization): {extra_tokens_flexible}")
                                logger.info(f"🔍 [BUILD 338] After removing filler: {substantive_extras}")
                            
                            # 🔥 BUILD 339 FIX: GENERIC TOKEN-BASED VALIDATION
                            # city_ok: STRICT - ALL city tokens must be present (for multi-word cities like "קריית גת")
                            # service_ok: FLEXIBLE - Use Jaccard similarity, no domain-specific hardcoding
                            
                            def _city_tokens_all_present(city_value, transcript_text):
                                """
                                🔥 BUILD 339: STRICT city validation - ALL city tokens must be present.
                                Example: city="קריית גת" → both "קריית" and "גת" must be in transcript.
                                "יערת גת" would fail because "קריית" is missing.
                                """
                                # Get city tokens (normalized)
                                city_tokens = [_normalize_hebrew_token(t) for t in city_value.split() if t.strip()]
                                # Get transcript tokens (normalized)
                                transcript_tokens = {_normalize_hebrew_token(t) for t in transcript_text.split()}
                                
                                # Check each city token is present in transcript
                                for city_token in city_tokens:
                                    found = False
                                    for t_token in transcript_tokens:
                                        # Exact normalized match
                                        if city_token == t_token:
                                            found = True
                                            break
                                        # Partial match (handles בקריית → קריית)
                                        if len(city_token) >= 3 and len(t_token) >= 3:
                                            if city_token in t_token or t_token in city_token:
                                                found = True
                                                break
                                    if not found:
                                        logger.warning(f"⚠️ [BUILD 339] City token '{city_token}' NOT FOUND in transcript tokens: {transcript_tokens}")
                                        return False
                                return True
                            
                            def _service_matches_semantically(service_value, transcript_text, filler_set):
                                """
                                🔥 BUILD 339: GENERIC service validation using Jaccard similarity.
                                No domain-specific hardcoding (no locksmith/pizza/plumber words).
                                Works purely based on the canonical service string.
                                
                                Example: service="הנצרים פריצה דלתות", AI says "פריצה לדלת"
                                → Strong token overlap → service_ok=True
                                """
                                # Tokenize and normalize service
                                service_tokens = [_normalize_hebrew_token(t) for t in service_value.split() if t.strip()]
                                # Remove filler from service tokens (keep only substantive words)
                                service_tokens = [t for t in service_tokens if t and t not in filler_set and len(t) > 1]
                                
                                # Tokenize and normalize transcript
                                transcript_tokens = [_normalize_hebrew_token(t) for t in transcript_text.split() if t.strip()]
                                # Remove filler from transcript tokens
                                transcript_tokens = [t for t in transcript_tokens if t and t not in filler_set and len(t) > 1]
                                
                                if not service_tokens:
                                    # No substantive service tokens to match - accept by default
                                    return True
                                
                                canon_set = set(service_tokens)
                                ai_set = set(transcript_tokens)
                                
                                # Calculate intersection
                                intersection = canon_set & ai_set
                                
                                # Also check with partial matching (handles דלתות→דלת, צילינדרים→צילינדר)
                                partial_matches = 0
                                for canon_token in canon_set:
                                    for ai_token in ai_set:
                                        if canon_token != ai_token:  # Not already counted
                                            if len(canon_token) >= 3 and len(ai_token) >= 3:
                                                if canon_token in ai_token or ai_token in canon_token:
                                                    partial_matches += 1
                                                    break
                                
                                # Effective matches = direct + partial
                                effective_matches = len(intersection) + partial_matches
                                
                                # Jaccard-like similarity
                                jaccard = effective_matches / max(len(canon_set), 1)
                                
                                logger.info(f"🔍 [BUILD 339] Service matching: canon_set={canon_set}, ai_set={ai_set}, intersection={intersection}, partial={partial_matches}, jaccard={jaccard:.2f}")
                                
                                # Accept if:
                                # 1) At least 1 token matches AND jaccard >= 0.5
                                if effective_matches >= 1 and jaccard >= 0.5:
                                    return True
                                
                                # 2) Fallback: substring match on normalized full strings
                                norm_canon_str = " ".join(service_tokens)
                                norm_ai_str = " ".join(transcript_tokens)
                                if norm_canon_str in norm_ai_str or norm_ai_str in norm_canon_str:
                                    return True
                                
                                return False
                            
                            city_ok = True
                            service_ok = True
                            
                            # CITY: If locked, ALL city tokens MUST be in transcript (strict matching for multi-word cities)
                            if self._city_locked:
                                if self._city_raw_from_stt:
                                    normalized_city = _normalize_hebrew(self._city_raw_from_stt)
                                    city_ok = _city_tokens_all_present(normalized_city, normalized_transcript)
                                    if not city_ok:
                                        logger.error(f"⚠️ [BUILD 339] City FAILED! Expected ALL tokens of '{self._city_raw_from_stt}' (normalized: '{normalized_city}') in transcript")
                                else:
                                    # Lock set but no value - inconsistent state, fail
                                    city_ok = False
                                    logger.warning(f"⚠️ [BUILD 339] City locked but no raw STT value!")
                            
                            # SERVICE: If locked, use generic semantic matching (Jaccard similarity)
                            if self._service_locked:
                                if self._service_raw_from_stt:
                                    normalized_service = _normalize_hebrew(self._service_raw_from_stt)
                                    service_ok = _service_matches_semantically(normalized_service, normalized_transcript, allowed_filler_normalized)
                                    if not service_ok:
                                        logger.error(f"⚠️ [BUILD 339] Service FAILED! Expected semantic match for '{self._service_raw_from_stt}' (normalized: '{normalized_service}') in transcript")
                                else:
                                    # Lock set but no value - inconsistent state, fail
                                    service_ok = False
                                    logger.warning(f"⚠️ [BUILD 339] Service locked but no raw STT value!")
                            
                            # Check for extra substantive tokens (after filler removal)
                            no_extra_content = len(substantive_extras) == 0
                            
                            exact_match = normalized_expected == normalized_transcript
                            
                            # 🔥 BUILD 339: Detailed logging for debugging
                            if substantive_extras:
                                logger.warning(f"⚠️ [BUILD 339] Extra tokens after filler removal: {substantive_extras}")
                            
                            # 🔥 BUILD 339 VALIDATION LOGIC:
                            # Accept confirmation if:
                            # 1. Exact match (AI said exactly what we asked), OR
                            # 2. city_ok=True AND service_ok=True AND no substantive extra tokens
                            # 
                            # Reject if:
                            # - city_ok=False (city tokens missing), OR
                            # - service_ok=False (service doesn't match semantically), OR
                            # - Non-filler extra tokens present
                            
                            if exact_match:
                                self._confirmation_validated = True
                                logger.info(f"✅ [BUILD 339] EXACT MATCH! AI said exactly what we asked")
                            elif city_ok and service_ok and no_extra_content:
                                self._confirmation_validated = True
                                logger.info(f"✅ [BUILD 339] VALID CONFIRMATION (city_ok=True, service_ok=True, no extras)")
                            else:
                                # 🚨 BUILD 339: Validation failed - wrong city, wrong service, or extra content
                                logger.error(f"🚨 [BUILD 339] VALIDATION FAILED! Extras: {substantive_extras}, city_ok={city_ok}, service_ok={service_ok}")
                                # AI deviated - resend instruction (limit to 2 retries to prevent infinite loop)
                                if self._speak_exact_resend_count < 2:
                                    self._speak_exact_resend_count += 1
                                    logger.info(f"🔁 [BUILD 339] Resending [SPEAK_EXACT] instruction (attempt {self._speak_exact_resend_count}/2)")
                                    # 🔥 FIX: Clear stale state before resend
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        f"[SPEAK_EXACT] עצור! אמרת פרטים שגויים. אמור בדיוק: \"{expected}\""
                                    ))
                                else:
                                    logger.error(f"❌ [BUILD 339] Max resends reached - AI keeps deviating")
                                    # 🔥 FIX: Reset state to allow retry with fresh data
                                    self._expected_confirmation = None
                                    self._speak_exact_resend_count = 0
                                    self._verification_prompt_sent = False
                        
                        # 🔥 BUILD 169.1: IMPROVED SEMANTIC LOOP DETECTION (Architect-reviewed)
                        # 🚫 DISABLED: Loop detection disabled via ENABLE_LOOP_DETECT flag
                        is_repeating = False
                        if ENABLE_LOOP_DETECT:
                            # Added: length floor to avoid false positives on short confirmations
                            MIN_LENGTH_FOR_SIMILARITY = 15  # Don't compare short confirmations
                            
                            def _text_similarity(a, b):
                                """Simple word overlap similarity (0-1)"""
                                words_a = set(a.split())
                                words_b = set(b.split())
                                if not words_a or not words_b:
                                    return 0
                                intersection = words_a & words_b
                                union = words_a | words_b
                                return len(intersection) / len(union) if union else 0
                            
                            # Track last AI responses for similarity check
                            self._last_ai_responses.append(transcript)
                            if len(self._last_ai_responses) > 5:
                                self._last_ai_responses.pop(0)  # Keep only last 5
                            
                            # Check for semantic repetition (similarity > 70% with any of last 3 responses)
                            # 🔥 ARCHITECT FIX: Only check if responses are long enough (avoid short template FP)
                            if len(self._last_ai_responses) >= 2 and len(transcript) >= MIN_LENGTH_FOR_SIMILARITY:
                                for prev_response in self._last_ai_responses[:-1]:
                                    if len(prev_response) < MIN_LENGTH_FOR_SIMILARITY:
                                        continue  # Skip short responses
                                    similarity = _text_similarity(transcript, prev_response)
                                    if similarity > 0.70:
                                        is_repeating = True
                                        logger.warning(f"⚠️ [LOOP DETECT] AI repeating! Similarity={similarity:.0%} with: '{prev_response[:50]}...'")
                                        break
                        
                        # 🔥 BUILD 169.1: MISHEARING DETECTION (Architect: reduced to 2 for better UX)
                        # 🚫 DISABLED: Loop detection disabled via ENABLE_LOOP_DETECT flag
                        is_confused = False
                        if ENABLE_LOOP_DETECT:
                            confusion_phrases = ["לא הבנתי", "לא שמעתי", "אפשר לחזור", "מה אמרת", "לא הצלחתי", "בבקשה חזור"]
                            is_confused = any(phrase in transcript for phrase in confusion_phrases)
                            if is_confused:
                                self._mishearing_count += 1
                                logger.info(f"❓ [MISHEARING] AI confused ({self._mishearing_count} times): '{transcript[:50]}...'")
                            else:
                                self._mishearing_count = 0  # Reset on clear response
                        
                        # 🔥 BUILD 311.1: POST-GREETING PATIENCE - Smart grace period!
                        # Grace period ends early when user speaks (user_has_spoken=True)
                        in_post_greeting_grace = False
                        if self.greeting_completed_at and not self.user_has_spoken:
                            time_since_greeting = time.time() - self.greeting_completed_at
                            grace_period = getattr(self, '_post_greeting_grace_period_sec', 5.0)
                            if time_since_greeting < grace_period:
                                in_post_greeting_grace = True
                        # If user has spoken, grace period is over - normal rules apply
                        
                        # 🔥 BUILD 311: DON'T count SILENCE_HANDLER responses towards consecutive
                        is_silence_handler = getattr(self, '_is_silence_handler_response', False)
                        if is_silence_handler:
                            logger.info(f"📢 [BUILD 311] SILENCE_HANDLER response - NOT counting towards consecutive")
                            self._is_silence_handler_response = False  # Reset flag
                            # Don't increment consecutive counter for silence warnings
                        else:
                            # 🔥 BUILD 170.3: IMPROVED LOOP PREVENTION with time-based check
                            self._consecutive_ai_responses += 1
                        
                        # 🔥 BUILD 170.3: Only count as "no user input" if >8 seconds since last speech
                        last_user_ts = getattr(self, '_last_user_speech_ts', 0) or 0
                        seconds_since_user = time.time() - last_user_ts if last_user_ts > 0 else 0
                        user_silent_long_time = seconds_since_user > 8.0  # 8 seconds without user input
                        
                        # Trigger loop guard if:
                        # 1. Too many consecutive AI responses AND user silent for >8s, OR
                        # 2. AI is semantically repeating itself (long responses only), OR
                        # 3. AI has been confused 3+ times in a row (BUILD 170.3: back to 3)
                        # 🔥 BUILD 178: COMPLETELY DISABLE loop guard for outbound calls!
                        # 🔥 BUILD 179: Also disable if call is CLOSING or hangup already triggered
                        # 🔥 BUILD 182: Also disable during appointment scheduling flow
                        # 🔥 BUILD 311: Also disable during post-greeting grace period!
                        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
                        is_closing = getattr(self, 'call_state', None) == CallState.CLOSING
                        is_hanging_up = getattr(self, 'hangup_triggered', False)
                        
                        # 🚫 DISABLED: Loop guard disabled via ENABLE_LOOP_DETECT flag
                        should_engage_guard = False
                        if ENABLE_LOOP_DETECT:
                            # 🔥 BUILD 182: Check if appointment was recently created/scheduled
                            crm_ctx = getattr(self, 'crm_context', None)
                            has_appointment = crm_ctx and getattr(crm_ctx, 'has_appointment_created', False)
                            
                            # 🔥 BUILD 337 FIX: Check scheduling mode flag OR keywords in transcript
                            # The flag persists across responses, keywords are transient
                            is_scheduling_flag = getattr(self, '_is_scheduling_mode', False)
                            
                            # 🔥 BUILD 337 FIX: Extended keyword list + check both original and lowercase
                            appointment_keywords = [
                                'תור', 'פגישה', 'לקבוע', 'זמינות', 'אשר', 'מאשר', 'תאריך', 'שעה',
                                'קביעת', 'לתאם', 'לזמן', 'להזמין', 'פנוי', 'תפוס', 'מתי', 'יום'
                            ]
                            transcript_lower = transcript.lower() if transcript else ""
                            has_keywords = any(kw in transcript or kw in transcript_lower for kw in appointment_keywords) if transcript else False
                            
                            # Set scheduling mode flag if keywords detected
                            if has_keywords and not is_scheduling_flag:
                                self._is_scheduling_mode = True
                                logger.info(f"📋 [BUILD 337] Scheduling mode ACTIVATED (keywords detected)")
                            
                            # Clear scheduling mode if appointment created
                            if has_appointment and is_scheduling_flag:
                                self._is_scheduling_mode = False
                                logger.info(f"✅ [BUILD 337] Scheduling mode DEACTIVATED (appointment created)")
                            
                            is_scheduling = is_scheduling_flag or has_keywords
                            
                            if in_post_greeting_grace:
                                # 🔥 BUILD 311: NEVER engage loop guard during grace period - give customer time to respond!
                                should_engage_guard = False
                                logger.info(f"⏳ [BUILD 311] Post-greeting grace period ({time_since_greeting:.1f}s/{grace_period}s) - LOOP GUARD DISABLED")
                            elif is_outbound:
                                # 🔥 OUTBOUND: Never engage loop guard - let AI talk freely
                                should_engage_guard = False
                            elif is_closing or is_hanging_up:
                                # 🔥 BUILD 179: Never engage loop guard during call ending
                                should_engage_guard = False
                                logger.info(f"⏭️ [LOOP GUARD] Skipped - call is ending (closing={is_closing}, hangup={is_hanging_up})")
                            elif has_appointment:
                                # 🔥 BUILD 182: Skip loop guard ONLY if appointment already created
                                should_engage_guard = False
                                logger.info(f"⏭️ [LOOP GUARD] Skipped - appointment confirmed (has_appointment=True)")
                            elif is_scheduling:
                                # 🔥 BUILD 337: LIMITED loop guard during scheduling - prevent AI monologues!
                                # Allow 2 consecutive responses during scheduling, then engage guard
                                # This prevents AI from looping while still allowing back-and-forth
                                max_scheduling_consecutive = 2
                                if self._consecutive_ai_responses >= max_scheduling_consecutive and user_silent_long_time:
                                    should_engage_guard = True
                                    logger.warning(f"⚠️ [BUILD 337] LOOP GUARD ENGAGED during scheduling! ({self._consecutive_ai_responses} consecutive, user silent)")
                                else:
                                    should_engage_guard = False
                                    logger.info(f"📋 [BUILD 337] Scheduling flow - limited guard ({self._consecutive_ai_responses}/{max_scheduling_consecutive})")
                            else:
                                # INBOUND: Normal loop guard logic
                                max_consecutive = self._max_consecutive_ai_responses
                                should_engage_guard = (
                                    (self._consecutive_ai_responses >= max_consecutive and user_silent_long_time) or
                                    (is_repeating and self._consecutive_ai_responses >= 3) or
                                    self._mishearing_count >= 3
                                )
                        
                        # 🚫 DISABLED: Loop guard actions disabled via ENABLE_LOOP_DETECT flag
                        if should_engage_guard and ENABLE_LOOP_DETECT:
                            guard_reason = "consecutive_responses" if self._consecutive_ai_responses >= self._max_consecutive_ai_responses else \
                                          "semantic_repetition" if is_repeating else "mishearing_loop"
                            logger.warning(f"⚠️ [LOOP GUARD] Triggered by {guard_reason}!")
                            logger.info(f"🛑 [LOOP GUARD] BLOCKING further responses until user speaks!")
                            # 🛑 ENGAGE GUARD FIRST - before any other operations to prevent race conditions
                            self._loop_guard_engaged = True
                            
                            # Send clarification request to AI before blocking
                            clarification_text = "[SERVER] זיהיתי שאתה חוזר על עצמך. אמור: 'לא שמעתי טוב, אפשר לחזור?' ותמתין בשקט."
                            asyncio.create_task(self._send_server_event_to_ai(clarification_text))
                            
                            # 🔥 BUILD 305: DON'T clear TX queue - causes choppy mid-sentence audio!
                            # Instead: just block NEW audio from being added via _tx_enqueue guard
                            # Let existing audio in queue play out naturally for smooth transition
                            
                            # Only cancel if there's actually an active response (with duplicate guard)
                            if self.active_response_id and self.realtime_client and self.is_ai_speaking_event.is_set():
                                cancelled_id = self.active_response_id
                                if self._should_send_cancel(cancelled_id):
                                    try:
                                        await client.send_event({
                                            "type": "response.cancel",
                                            "response_id": cancelled_id
                                        })
                                        self._mark_response_cancelled_locally(cancelled_id, "loop_guard")
                                        logger.info(f"🛑 [LOOP GUARD] Cancelled active AI response (id={cancelled_id})")
                                    except:
                                        pass
                            else:
                                logger.info(f"⏭️ [LOOP GUARD] Skipped cancel - no active response (id={self.active_response_id}, speaking={self.is_ai_speaking_event.is_set()})")
                            
                            # 🔥 BUILD 305: DON'T clear queues - this causes choppy audio!
                            # The _tx_enqueue function already blocks audio when _loop_guard_engaged=True
                            # Old code cleared TX queue here, causing mid-sentence cuts
                            logger.info(f"✅ [LOOP GUARD] Engaged - blocking new audio (existing queue: {self.tx_q.qsize()} frames will play)")
                            # Mark AI as not speaking
                            self.is_ai_speaking_event.clear()
                            self.speaking = False
                        
                        # 💰 COST TRACKING: AI finished speaking - stop timer (DEBUG only)
                        if hasattr(self, '_ai_speech_start') and self._ai_speech_start is not None:
                            ai_duration = time.time() - self._ai_speech_start
                            ai_chunks = getattr(self, 'realtime_audio_out_chunks', 0)
                            logger.debug(f"[COST] AI utterance: {ai_duration:.2f}s ({ai_chunks} chunks)")
                            self._ai_speech_start = None  # Reset for next utterance
                        
                        # Track conversation
                        self.conversation_history.append({"speaker": "ai", "text": transcript, "ts": time.time()})
                        # 🔥 FIX: Don't run NLP when AI speaks - only when USER speaks!
                        # Removing this call to prevent loop (NLP should only analyze user input)
                        
                        # 🎯 SMART HANGUP: Extract lead fields from AI confirmation patterns
                        self._extract_lead_fields_from_ai(transcript)
                        
                        # 🎯 BUILD 163: Detect goodbye phrases in AI transcript
                        # 🔥 PROTECTION: Only detect goodbye if enough time passed since greeting
                        # ONLY applies if greeting was actually played (greeting_completed_at is not None)
                        can_detect_goodbye = True
                        if self.greeting_completed_at is not None:
                            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
                            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                                can_detect_goodbye = False
                                logger.info(f"🛡️ [PROTECTION] Ignoring AI goodbye - only {elapsed_ms:.0f}ms since greeting")
                        # Note: If greeting_completed_at is None (no greeting), allow goodbye detection normally
                        
                        # 🔴 DISABLED — Old goodbye detection (replaced by BYE-ONLY at line 5131-5176)
                        # Point 1 Fix: Only ONE goodbye detection path (the strict BYE-ONLY one above)
                        # ai_polite_closing_detected = self._classify_real_hangup_intent(transcript, "bot") == "hangup"
                        ai_polite_closing_detected = False  # Disabled - use BYE-ONLY detection only
                        
                        # 🛡️ SAFETY: Don't allow hangup too early in the call (prevent premature disconnect)
                        # Wait at least 5 seconds after greeting before allowing smart ending
                        time_since_greeting = 0
                        if self.greeting_completed_at:
                            time_since_greeting = (time.time() - self.greeting_completed_at) * 1000
                        
                        # Minimum call duration before smart ending is allowed (milliseconds)
                        MIN_CALL_DURATION_FOR_SMART_ENDING = 5000  # 5 seconds
                        
                        # If AI says goodbye too early, ignore it (likely part of greeting/introduction)
                        if ai_polite_closing_detected and time_since_greeting < MIN_CALL_DURATION_FOR_SMART_ENDING:
                            logger.info(f"🛡️ [PROTECTION] Ignoring AI goodbye - only {time_since_greeting:.0f}ms since greeting (min={MIN_CALL_DURATION_FOR_SMART_ENDING}ms)")
                            ai_polite_closing_detected = False
                        
                        # 🎯 BUILD 170.5: FIXED HANGUP LOGIC
                        # Settings-based hangup respects business configuration
                        # Hangup requires EITHER:
                        # - User said goodbye (goodbye_detected=True), OR
                        # - Lead captured with auto_end_after_lead_capture=True, OR
                        # - User confirmed summary (verification_confirmed=True)
                        should_hangup = False
                        hangup_reason = ""
                        
                        # 🔥 CRITICAL FIX: Hangup ONLY when BOT says goodbye (not when user says goodbye)
                        # Disconnect conditions for NORMAL CONVERSATION:
                        # 1. BOT says goodbye (ביי/להתראות) - ALWAYS disconnect
                        # 2. OR 20 seconds of complete silence (handled by watchdog)
                        # 3. OR Voicemail detected (handled separately)
                        # 
                        # User saying goodbye does NOT trigger disconnect - bot must respond and say goodbye!
                        # This prevents premature disconnects when user says goodbye but conversation should continue.
                        
                        # ONLY CONDITION: BOT said goodbye - always disconnect
                        if ai_polite_closing_detected:
                            hangup_reason = "bot_goodbye"
                            should_hangup = True
                            logger.info(f"✅ [HANGUP] Bot said goodbye (ביי/להתראות) - disconnecting")
                            logger.info(f"📞 [HANGUP] This is the ONLY normal disconnect condition - bot must say goodbye!")
                        
                        # NOTE: All conditions below are UNREACHABLE because ai_polite_closing_detected
                        # always triggers the condition above. The bot MUST say goodbye to disconnect.
                        
                        # 🔧 NEW FIX: Guard against hangup while user is speaking
                        # In SIMPLE_MODE, check if user is currently speaking or just started
                        if should_hangup and SIMPLE_MODE:
                            # Check if there's active voice input (user speaking)
                            # barge_in_voice_frames is always initialized to 0 in __init__
                            user_is_speaking = getattr(self, 'barge_in_voice_frames', 0) > 0
                            if user_is_speaking:
                                logger.info(f"🔒 [GOODBYE] Blocking hangup - user currently speaking! voice_frames={self.barge_in_voice_frames}")
                                should_hangup = False
                        
                        if should_hangup:
                            self.goodbye_detected = True
                            self.pending_hangup = True
                            self.pending_hangup_reason = hangup_reason
                            self.pending_hangup_source = "ai_transcript"
                            # Bind hangup to THIS response so we disconnect only after its audio is done.
                            self.pending_hangup_response_id = event.get("response_id") or getattr(self, "active_response_id", None)
                            # 🔥 FIX: Mark that AI already said goodbye naturally - prevents duplicate goodbye in _trigger_auto_hangup
                            self.goodbye_message_sent = True
                            # 🔥 BUILD 172: Transition to CLOSING state
                            if self.call_state == CallState.ACTIVE:
                                self.call_state = CallState.CLOSING
                                logger.info(f"📞 [STATE] Transitioning ACTIVE → CLOSING (reason: {hangup_reason})")
                            logger.info(f"📞 [HANGUP TRIGGER] ✅ pending_hangup=True - hangup WILL execute after audio completes")
                            logger.info(f"📞 [HANGUP TRIGGER]    reason={hangup_reason}, transcript='{transcript[:50]}...'")
                            logger.info(f"📞 [HANGUP TRIGGER]    Flow: response.audio.done → delayed_hangup() → _trigger_auto_hangup()")
                        
                        # 🔥 NOTE: Hangup is now triggered in response.audio.done to let audio finish!
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    raw_text = event.get("transcript", "") or ""
                    text = raw_text.strip()
                    
                    # 🔥 BUILD 300: UNIFIED STT LOGGING - Step 1: Log raw transcript (DEBUG only)
                    logger.debug(f"[STT_RAW] '{raw_text}' (len={len(raw_text)})")
                    
                    # 🔥 MASTER CHECK: Log utterance received (verification requirement)
                    logger.info(f"[UTTERANCE] text='{raw_text}'")
                    
                    # 🔥 BUILD 170.4: Apply Hebrew normalization
                    text = normalize_hebrew_text(text)
                    
                    # ✅ P0-0: REMOVED Dynamic STT completely (causes "Working outside of application context")
                    # No DB access in realtime thread - vocabulary corrections disabled
                    # This prevents crashes/stalls during calls caused by DB/Flask context issues
                    
                    now_ms = time.time() * 1000
                    now_sec = now_ms / 1000
                    
                    # 🎯 STT GUARD: Validate utterance before accepting
                    # This prevents hallucinated transcriptions during silence from triggering barge-in
                    utterance_start_ts = getattr(self, '_utterance_start_ts', None)
                    if utterance_start_ts:
                        utterance_duration_ms = (now_sec - utterance_start_ts) * 1000
                    else:
                        # Fallback: estimate from speech_stopped event
                        utterance_duration_ms = 1000  # Assume 1s if we don't have timing
                    
                    # 🔥 FIX BUG 3: Calculate time since AI audio started (for echo suppression)
                    ai_speaking = self.is_ai_speaking_event.is_set()
                    time_since_ai_audio_start_ms = 0
                    if ai_speaking and self._last_ai_audio_start_ts:
                        time_since_ai_audio_start_ms = (now_sec - self._last_ai_audio_start_ts) * 1000
                    
                    # 🔥 PRE-COMPUTE: Check filler status once (used in both hallucination and success paths)
                    is_filler_only = not is_valid_transcript(text)
                    
                    # 🔥 PRE-COMPUTE: Save state before any modifications (used in all logging paths)
                    user_has_spoken_before = self.user_has_spoken
                    
                    # Run enhanced validation with all new parameters
                    accept_utterance = should_accept_realtime_utterance(
                        stt_text=text,
                        utterance_ms=utterance_duration_ms,
                        rms_snapshot=0.0,
                        noise_floor=0.0,
                        ai_speaking=ai_speaking,
                        last_ai_audio_start_ms=time_since_ai_audio_start_ms,
                        last_hallucination=self._last_hallucination
                    )
                    
                    if not accept_utterance:
                        # 🚫 Utterance failed validation - save as hallucination and ignore
                        logger.info(f"[STT_GUARD] Ignoring hallucinated/invalid utterance: '{text[:20]}...'")
                        
                        # 🔥 FIX: Enhanced logging for STT decisions (per problem statement)
                        logger.info(
                            f"[STT_DECISION] raw='{raw_text}' normalized='{text}' | "
                            f"is_filler_only={is_filler_only} | "
                            f"is_hallucination=True (failed validation) | "
                            f"user_has_spoken: {user_has_spoken_before} → {self.user_has_spoken} | "
                            f"will_generate_response=False (hallucination dropped)"
                        )
                        
                        # 🔥 FIX BUG 3: Save as last hallucination to prevent repeats
                        self._last_hallucination = text.strip()
                        # 🔥 METRICS: Increment STT hallucinations counter
                        self._stt_hallucinations_dropped += 1
                        # Clear candidate flag
                        self._candidate_user_speaking = False
                        self._utterance_start_ts = None
                        continue
                    
                    # ✅ Utterance passed validation
                    logger.info(
                        f"[STT_GUARD] Accepted utterance: {utterance_duration_ms:.0f}ms, text_len={len(text)}"
                    )
                    
                    # 🔥 BUILD 341: Set user_has_spoken ONLY after validated transcription with meaningful text
                    # This ensures all guards pass before we mark user as having spoken
                    # Minimum requirement: At least MIN_TRANSCRIPTION_LENGTH characters after cleanup
                    if not self.user_has_spoken and text and len(text.strip()) >= MIN_TRANSCRIPTION_LENGTH:
                        self.user_has_spoken = True
                        logger.info(f"[STT_GUARD] user_has_spoken set to True after full validation (text='{text[:40]}...', len={len(text.strip())})")
                    elif not self.user_has_spoken and text:
                        # Log when we get text but it's too short to count
                        logger.info(f"[STT_GUARD] Text too short to mark user_has_spoken (len={len(text.strip())}, need >={MIN_TRANSCRIPTION_LENGTH}): '{text}'")
                    
                    # 🔥 FIX: Enhanced logging for STT decisions (per problem statement)
                    # is_filler_only already computed above, no duplicate function call
                    logger.info(
                        f"[STT_DECISION] raw='{raw_text}' normalized='{text}' | "
                        f"is_filler_only={is_filler_only} | "
                        f"is_hallucination=False (passed validation) | "
                        f"user_has_spoken: {user_has_spoken_before} → {self.user_has_spoken} | "
                        f"will_generate_response={not is_filler_only}"
                    )
                    
                    # 🔥 MASTER CHECK: Confirm transcript committed to model (Path A - Realtime-native)
                    # Transcript is already in session state via conversation.item.input_audio_transcription.completed
                    # No manual conversation.item.create needed - OpenAI handles it automatically
                    logger.info(f"[AI_INPUT] kind=realtime_transcript committed=True text_preview='{text[:100]}'")
                    
                    # Clear candidate flag - transcription received and validated
                    self._candidate_user_speaking = False
                    self._utterance_start_ts = None
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 VOICEMAIL DETECTION & SILENCE WATCHDOG: Update activity tracking
                    # ═══════════════════════════════════════════════════════════════════════
                    # Update last activity timestamp for silence watchdog
                    self._last_activity_ts = time.time()
                    
                    # Check for voicemail/answering machine (first 10 seconds only)
                    await self._maybe_hangup_voicemail(text)
                    
                    # 🧠 GENDER DETECTION FROM CONVERSATION
                    # Detect if user explicitly states their gender ("אני אישה" / "אני גבר")
                    # This is the most reliable source - update Lead in database if detected
                    if text and len(text) > 3:  # At least a few characters
                        from server.services.realtime_prompt_builder import detect_gender_from_conversation
                        detected_gender = detect_gender_from_conversation(text)
                        
                        if detected_gender and self.call_sid:
                            # Gender detected from conversation! Update Lead in database
                            try:
                                from server.models_sql import CallLog, Lead
                                app = _get_flask_app()
                                with app.app_context():
                                    # Find the lead associated with this call
                                    call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                                    lead = None
                                    
                                    if call_log and call_log.lead_id:
                                        lead = Lead.query.get(call_log.lead_id)
                                    elif hasattr(self, 'outbound_lead_id') and self.outbound_lead_id:
                                        # Outbound call - use outbound_lead_id
                                        lead = Lead.query.get(self.outbound_lead_id)
                                    
                                    if lead:
                                        # Buffer gender update (will commit at call end)
                                        old_gender = lead.gender
                                        lead.gender = detected_gender
                                        self.db_write_queue.append({
                                            'type': 'lead_update',
                                            'lead_id': lead.id,
                                            'updates': {'gender': detected_gender}
                                        })
                                        logger.info(f"[DB_BUFFER] Queued gender update for lead {lead.id}: {detected_gender}")
                                        
                                        logger.info(f"[GENDER_CONVERSATION] Detected gender for lead {lead.id}: {old_gender} → {detected_gender} (buffered)")
                                        logger.info(f"🧠 [GENDER] Detected from conversation: {detected_gender} (will save at call end)")
                                        
                                        # Re-inject NAME_ANCHOR with updated gender
                                        if hasattr(self, '_name_anchor_customer_name') and self._name_anchor_customer_name:
                                            from server.services.realtime_prompt_builder import build_name_anchor_message
                                            use_policy = getattr(self, '_name_anchor_policy', False)
                                            lead_notes = getattr(self, 'pending_lead_notes', None)  # 🔥 NEW: Get notes
                                            updated_anchor = build_name_anchor_message(
                                                self._name_anchor_customer_name, 
                                                use_policy, 
                                                detected_gender,
                                                lead_notes  # 🔥 NEW: Pass notes
                                            )
                                            
                                            # Send updated context to AI
                                            try:
                                                await client.send_event({
                                                    "type": "conversation.item.create",
                                                    "item": {
                                                        "type": "message",
                                                        "role": "system",
                                                        "content": [{"type": "input_text", "text": updated_anchor}]
                                                    }
                                                })
                                                logger.info(f"🧠 [GENDER] Updated AI context with detected gender")
                                            except Exception as e:
                                                logger.warning(f"[GENDER_CONVERSATION] Failed to update AI context: {e}")
                                    else:
                                        logger.debug(f"[GENDER_CONVERSATION] No lead found for call_sid {self.call_sid[:8]}")
                            except Exception as e:
                                logger.error(f"[GENDER_CONVERSATION] Error updating gender: {e}")
                                logger.exception("Full traceback:")
                    
                    # 🆕 NAME DETECTION FROM CONVERSATION
                    # Detect if user introduces themselves ("אני דני" / "קוראים לי רונית")
                    # Update Lead record with detected name for both inbound and outbound calls
                    if text and len(text) > 3:  # At least a few characters
                        from server.services.realtime_prompt_builder import detect_name_from_conversation, extract_first_name
                        detected_name = detect_name_from_conversation(text)
                        
                        if detected_name and self.call_sid:
                            # Name detected from conversation! Update Lead in database
                            try:
                                from server.models_sql import CallLog, Lead
                                app = _get_flask_app()
                                with app.app_context():
                                    # Find the lead associated with this call
                                    call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                                    lead = None
                                    
                                    if call_log and call_log.lead_id:
                                        lead = Lead.query.get(call_log.lead_id)
                                    elif hasattr(self, 'outbound_lead_id') and self.outbound_lead_id:
                                        # Outbound call - use outbound_lead_id
                                        lead = Lead.query.get(self.outbound_lead_id)
                                    
                                    if lead:
                                        # Only update if lead doesn't have a name or has placeholder name
                                        current_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                                        should_update = (
                                            not current_name or 
                                            current_name in ['Customer', 'לקוח', 'ללא שם'] or
                                            current_name.startswith('לקוח מטלפון')
                                        )
                                        
                                        if should_update:
                                            # Buffer name update (will commit at call end)
                                            old_name = current_name or 'None'
                                            lead.first_name = detected_name
                                            lead.last_name = None  # Clear last name since we only extract first name
                                            self.db_write_queue.append({
                                                'type': 'lead_update',
                                                'lead_id': lead.id,
                                                'updates': {'first_name': detected_name, 'last_name': None}
                                            })
                                            logger.info(f"[DB_BUFFER] Queued name update for lead {lead.id}: '{detected_name}'")
                                            
                                            logger.info(f"[NAME_CONVERSATION] Detected name for lead {lead.id}: '{old_name}' → '{detected_name}' (buffered)")
                                            logger.info(f"📝 [NAME] Detected from conversation: '{detected_name}' (will save at call end)")
                                            
                                            # Update CRM context if it exists
                                            if hasattr(self, 'crm_context') and self.crm_context:
                                                self.crm_context.customer_name = detected_name
                                                logger.info(f"📝 [NAME] Updated CRM context with detected name")
                                        else:
                                            logger.debug(f"[NAME_CONVERSATION] Lead {lead.id} already has valid name '{current_name}' - not overriding")
                                    else:
                                        logger.debug(f"[NAME_CONVERSATION] No lead found for call_sid {self.call_sid[:8]}")
                            except Exception as e:
                                logger.error(f"[NAME_CONVERSATION] Error updating name: {e}")
                                logger.exception("Full traceback:")
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🛡️ GREETING PROTECTION - Confirm interruption after transcription
                    # ═══════════════════════════════════════════════════════════════════════
                    # If greeting was protected during speech_started, now confirm with transcription
                    # Non-empty text = real user speech → interrupt greeting (INBOUND ONLY!)
                    # 
                    # 🔥 NEW REQUIREMENT: OUTBOUND calls NEVER interrupt greeting - ignore all transcriptions
                    # ═══════════════════════════════════════════════════════════════════════
                    is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
                    
                    # 🔴 FINAL CRITICAL FIX #1:
                    # Never interrupt greeting based on local triggers/transcription.
                    # If legacy code set this flag, clear it and do nothing.
                    if getattr(self, '_greeting_needs_transcription_confirm', False):
                        self._greeting_needs_transcription_confirm = False
                        if DEBUG:
                            logger.info("🔒 [GREETING] Ignoring transcription-confirm greeting interruption")
                    
                    # 🔥 CRITICAL: Clear user_speaking flag - allow response.create now
                    # This completes the turn cycle: speech_started → speech_stopped → transcription → NOW AI can respond
                    self.user_speaking = False
                    if DEBUG:
                        logger.debug(f"[TURN_TAKING] user_speaking=False - transcription complete, AI can respond now")
                    else:
                        logger.info(f"✅ [TURN_TAKING] user_speaking=False - transcription complete, AI can respond now")
                    
                    # 🎯 MASTER DIRECTIVE 4: BARGE-IN Phase B - STT validation
                    # If final text is filler → ignore, if real text → CONFIRMED barge-in
                    if is_filler_only:
                        logger.info(f"[FILLER_DETECT] Ignoring filler-only utterance: '{text[:40]}...'")
                        
                        # Don't cancel AI, don't flush queue, just ignore
                        # If this was during AI speech, it's not a real barge-in
                        if self.barge_in_active:
                            logger.info(f"[BARGE-IN] Phase B: Filler detected - not a real barge-in, clearing flag")
                            self.barge_in_active = False
                            self._barge_in_started_ts = None
                        
                        # Save to conversation history for context but mark as filler
                        # 🔧 CODE REVIEW FIX: Initialize conversation_history if it doesn't exist
                        if not hasattr(self, 'conversation_history'):
                            self.conversation_history = []
                        self.conversation_history.append({
                            "speaker": "user",
                            "text": f"[FILLER: {text}]",
                            "ts": time.time(),
                            "filler_only": True
                        })
                        # Increment filler counter for metrics
                        if not hasattr(self, '_stt_filler_only_count'):
                            self._stt_filler_only_count = 0
                        self._stt_filler_only_count += 1
                        continue  # Skip to next event, don't process as user input
                    
                    # 🔥 FIX BUG 2: Cancel any pending timeout tasks (transcription received)
                    if hasattr(self, '_timeout_tasks'):
                        for task in self._timeout_tasks:
                            if not task.done():
                                task.cancel()
                        self._timeout_tasks.clear()
                    
                    # 🔥 BUILD 300: REMOVED POST_AI_COOLDOWN GATE
                    # The guide says: "אסור לזרוק טקסט בגלל pause ארוך" and "המודל תמיד יודע טוב יותר"
                    # OpenAI's VAD/STT is authoritative - if it transcribed something, it's valid
                    # Old code rejected transcripts arriving <1200ms after AI spoke - this blocked valid responses!
                    if self._ai_finished_speaking_ts > 0:
                        time_since_ai_finished = (now_sec - self._ai_finished_speaking_ts) * 1000
                        # 🔥 BUILD 300: Only LOG, don't reject! OpenAI knows better than local timing
                        if time_since_ai_finished < 500:  # Very fast response - just log for debugging
                            logger.info(f"⚡ [BUILD 300] Fast response: {time_since_ai_finished:.0f}ms after AI (trusting OpenAI)")
                    # 🔥 BUILD 170.3: REMOVED short text rejection - Hebrew can have short valid responses
                    
                    # 🔥 BUILD 169.1: ENHANCED NOISE/HALLUCINATION FILTER (Architect-reviewed)
                    # 1. Allow short Hebrew words (expanded list per architect feedback)
                    # 2. Block English hallucinations
                    # 3. Block gibberish (but allow natural elongations like "אמממ")
                    
                    # ✅ BUILD 170.4: EXPANDED WHITELIST - More Hebrew words
                    valid_short_hebrew = [
                        # Basic confirmations
                        "כן", "לא", "רגע", "שניה", "שנייה", "טוב", "בסדר", "תודה", "סליחה", "יופי", "נכון",
                        "מעולה", "בדיוק", "בסדר גמור", "אשמח", "אין בעיה", "ברור",
                        # Common fillers
                        "יאללה", "סבבה", "דקה", "אוקיי", "או קיי", "אוקי", "אה", "אהה", "אמ",
                        # Questions
                        "מה", "איפה", "מתי", "למה", "איך", "כמה", "מי", "איזה", "איזו", "מה זה", "למה לא",
                        # Pronouns and common words
                        "זה", "אני", "אתה", "את", "הוא", "היא", "אנחנו", "הם", "הן", "לי", "לך", "שלי", "שלך",
                        "עכשיו", "היום", "מחר", "אתמול", "פה", "שם", "כאן",
                        # Greetings
                        "שלום", "ביי", "להתראות", "בבקשה", "היי", "הלו", "בוקר טוב", "ערב טוב",
                        # Numbers (Hebrew) - include feminine forms too
                        "אחד", "אחת", "שתיים", "שניים", "שלוש", "שלושה", "ארבע", "ארבעה",
                        "חמש", "חמישה", "שש", "שישה", "שבע", "שבעה", "שמונה", "תשע", "תשעה",
                        "עשר", "עשרה", "אחד עשר", "שתים עשרה", "עשרים", "שלושים", "ארבעים", "חמישים",
                        "אפס", "מאה", "אלף", "מיליון",
                        # Days of week
                        "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת",
                        "יום ראשון", "יום שני", "יום שלישי", "יום רביעי", "יום חמישי", "יום שישי",
                        # Time-related
                        "בוקר", "צהריים", "ערב", "לילה", "שעה", "דקות", "חצי", "רבע",
                        # Service-related
                        "תור", "פגישה", "תאריך", "זמן", "שירות", "בדיקה",
                        # Natural elongations
                        "אמממ", "אההה", "אממ", "אהה", "הממ", "ווו",
                        # Short responses
                        "כמובן", "בטח", "ודאי", "אולי", "לפעמים", "תמיד", "אף פעם",
                    ]
                    
                    text_stripped = text.strip()
                    is_valid_short_hebrew = text_stripped in valid_short_hebrew
                    
                    # 🔥 BUILD 170.4: Also check if it STARTS WITH a valid word (for phrases)
                    starts_with_valid = any(text_stripped.startswith(word) for word in valid_short_hebrew if len(word) > 2)
                    
                    # 🛡️ Check if text is PURE English (likely hallucination from Hebrew audio)
                    hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', text))
                    english_chars = len(re.findall(r'[a-zA-Z]', text))
                    
                    # 🛡️ BUILD 186: EXPANDED English hallucination filter
                    # These are common Whisper mistakes when transcribing Hebrew audio as English
                    hallucination_phrases = [
                        # Greetings/farewells
                        "bye", "bye.", "bye!", "goodbye", "good bye", "hello", "hi", "hey",
                        # Thanks
                        "thank you", "thanks", "thank you very much", "thank you.", "thanks.",
                        # Confirmations
                        "ok", "okay", "o.k.", "yes", "no", "sure", "right", "yeah", "yep", "nope",
                        "alright", "all right", "fine", "good", "great",
                        # Understanding
                        "i see", "i know", "got it", "understood",
                        # Fillers
                        "mm", "uh", "hmm", "um", "uh huh", "mhm", "uh-huh", "m-hm",
                        # 🔥 BUILD 186: NEW patterns from actual Hebrew→English STT errors
                        "good luck", "a bit", "blah", "blah.", "bit", "luck",
                        "nice", "cool", "wow", "oh", "ah", "ooh", "aah",
                        "what", "well", "so", "but", "and", "or", "the",
                        "please", "sorry", "excuse me", "pardon",
                        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                        # Common short misheard phrases
                        "i'm", "it's", "that's", "there's", "here's",
                        "come", "go", "see", "look", "wait", "stop",
                        "really", "actually", "maybe", "probably", "definitely",
                        "you know", "i mean", "like", "just", "so so",
                        # Music/audio artifacts
                        "la la", "la", "na na", "da da", "ta ta"
                    ]
                    text_lower = text.lower().strip('.!?, ')
                    
                    # 🔥 BUILD 186: Check for exact match OR if text contains ONLY English words
                    is_hallucination = text_lower in hallucination_phrases
                    
                    # Also check for multi-word English phrases (e.g., "Thank you very much. Thank you")
                    if not is_hallucination and english_chars > 0 and hebrew_chars == 0:
                        # Check if ALL words are common English words
                        english_common_words = {"thank", "you", "very", "much", "good", "luck", "bye", 
                                               "hello", "hi", "hey", "ok", "okay", "yes", "no", "a", "bit",
                                               "i", "it", "is", "the", "and", "or", "but", "so", "blah",
                                               "one", "two", "three", "four", "five", "what", "where", "when",
                                               "nice", "well", "fine", "great", "cool", "wow", "please"}
                        words_in_text = set(re.findall(r'[a-zA-Z]+', text_lower))
                        if words_in_text and words_in_text.issubset(english_common_words):
                            is_hallucination = True
                            logger.info(f"🚫 [BUILD 186] ENGLISH HALLUCINATION: '{text}' (all words are common English)")
                    
                    # 🔥 BUILD 303: INCREMENT USER UTTERANCE COUNT
                    self.user_utterance_count += 1
                    
                    # 🔥 BUILD 309: SIMPLE_MODE - Bypass ALL noise/gibberish filters!
                    # In SIMPLE_MODE, trust OpenAI + Twilio completely - all text passes through
                    is_gibberish_detected = False
                    should_filter = False
                    filter_reason = ""
                    
                    if SIMPLE_MODE:
                        logger.info(f"✅ [SIMPLE_MODE] Bypassing all filters - accepting: '{text}'")
                        # In SIMPLE_MODE: skip all filtering, go straight to segment merging
                    else:
                        # 🔥 BUILD 186: GENERIC STT VALIDATION - No hardcoded patterns!
                        # Uses linguistic rules from hebrew_stt_validator service
                        natural_elongations = ["אמממ", "אההה", "אממ", "אהה", "מממ", "ווו", "אה", "אם", "אוקי", "היי"]
                        
                        # 🔥 BUILD 303: PATIENCE FOR FIRST 2 UTTERANCES - Don't reject as gibberish!
                        # The first responses after greeting are critical - trust them even if slightly broken
                        # Only require ≥4 Hebrew characters to pass
                        bypass_gibberish_for_patience = (
                            self.user_utterance_count <= 2 and
                            hebrew_chars >= 4  # At least 4 Hebrew chars
                        )
                        
                        if bypass_gibberish_for_patience:
                            logger.info(f"✅ [BUILD 303 PATIENCE] Bypassing gibberish check for utterance #{self.user_utterance_count}: '{text_stripped}' (hebrew_chars={hebrew_chars})")
                        elif hebrew_chars > 0 and text_stripped not in natural_elongations:
                            # Use the generic Hebrew STT validator (no hardcoded patterns)
                            is_gib, gib_reason, gib_confidence = is_gibberish(text_stripped)
                            if is_gib and gib_confidence >= 0.5:
                                is_gibberish_detected = True
                                logger.info(f"[GIBBERISH] Detected: '{text_stripped}' | Reason: {gib_reason} | Confidence: {gib_confidence:.0%}")
                        
                        # 🛡️ Check if pure English with no Hebrew - likely Whisper hallucination
                        is_pure_english = hebrew_chars == 0 and english_chars >= 2 and len(text) < 20
                        
                        # 🔥 BUILD 170.4: IMPROVED FILTER LOGIC
                        # Priority: Allow Hebrew > Block hallucinations > Block gibberish
                        
                        # First check: If has Hebrew characters and meaningful length, probably valid
                        has_meaningful_hebrew = hebrew_chars >= 2 and len(text) >= 3
                        
                        if is_valid_short_hebrew or starts_with_valid:
                            # ✅ ALWAYS allow valid short Hebrew words or phrases starting with them
                            should_filter = False
                            logger.info(f"✅ [NOISE FILTER] ALLOWED Hebrew: '{text}'")
                        elif has_meaningful_hebrew and not is_gibberish_detected:
                            # ✅ Has Hebrew characters and not gibberish - probably valid
                            should_filter = False
                            logger.info(f"✅ [NOISE FILTER] ALLOWED (has Hebrew): '{text}'")
                        elif is_hallucination:
                            should_filter = True
                            filter_reason = "hallucination"
                        elif is_gibberish_detected:
                            should_filter = True
                            filter_reason = "gibberish"
                        elif len(text) < 2 or all(ch in ".?!, " for ch in text):
                            should_filter = True
                            filter_reason = "too_short_or_punctuation"
                        elif is_pure_english:
                            # Pure English in Hebrew call - suspicious
                            should_filter = True
                            filter_reason = "pure_english_hallucination"
                        
                        if should_filter:
                            logger.debug(f"[NOISE FILTER] ❌ REJECTED ({filter_reason}): '{text}'")
                            logger.debug(f"[SAFETY] Transcription successful (total failures: {self.transcription_failed_count})")
                            # 🔥 BUILD 182: STILL record filtered transcripts for webhook/transcript purposes!
                            # Only skip AI processing, not conversation history
                            if len(text) >= 2 and filter_reason not in ["gibberish", "too_short_or_punctuation"]:
                                self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                                logger.info(f"📝 [TRANSCRIPT] Recorded filtered user speech for webhook: '{text}'")
                            continue
                        
                        # ✅ PASSED FILTER
                        logger.info(f"[NOISE FILTER] ✅ ACCEPTED: '{text}' (hebrew={hebrew_chars}, english={english_chars})")
                    
                    # 🔥 BUILD 169.1: IMPROVED SEGMENT MERGING (Architect-reviewed)
                    # Added: max length limit, flush on long pause, proper reset
                    # 🔥 BUILD 308: Added DEDUPE to prevent duplicate phrases like "פורץ דלתות פורץ דלתות"
                    MAX_MERGE_LENGTH = 100  # Max characters before forced flush
                    LONG_PAUSE_MS = 1500  # Flush if pause > 1.5 seconds (distinct intents)
                    
                    should_merge = False
                    should_flush = False
                    is_duplicate = False
                    
                    # 🔥 BUILD 308: DEDUPE - Skip if same as last buffered segment
                    if self._stt_merge_buffer:
                        last_buffered = self._stt_merge_buffer[-1].strip().lower()
                        current_text = text.strip().lower()
                        if last_buffered == current_text:
                            is_duplicate = True
                            logger.info(f"🔄 [BUILD 308 DEDUPE] Skipping duplicate segment: '{text}'")
                    
                    if self._stt_last_segment_ts > 0:
                        time_since_last = now_ms - self._stt_last_segment_ts
                        buffer_len = sum(len(s) for s in self._stt_merge_buffer) if self._stt_merge_buffer else 0
                        
                        # Check flush conditions (architect feedback)
                        if time_since_last >= LONG_PAUSE_MS:
                            # Long pause = distinct intent, flush buffer first
                            should_flush = True
                            logger.info(f"📝 [SEGMENT MERGE] FLUSH - long pause ({time_since_last:.0f}ms)")
                        elif buffer_len >= MAX_MERGE_LENGTH:
                            # Buffer too long, flush to avoid over-merging
                            should_flush = True
                            logger.info(f"📝 [SEGMENT MERGE] FLUSH - max length ({buffer_len} chars)")
                        elif time_since_last < STT_MERGE_WINDOW_MS:
                            # Within merge window, continue buffering
                            should_merge = True
                    
                    # Process any pending buffer if flush needed
                    if should_flush and self._stt_merge_buffer:
                        flushed_text = " ".join(self._stt_merge_buffer)
                        logger.info(f"📝 [SEGMENT MERGE] Flushed buffer: '{flushed_text}'")
                        self._stt_merge_buffer = []
                        # Process flushed text separately - let it flow through
                        # Current text will be processed as new segment
                    
                    if should_merge and not is_duplicate:
                        # Merge with previous segment (but skip duplicates!)
                        self._stt_merge_buffer.append(text)
                        self._stt_last_segment_ts = now_ms
                        logger.info(f"📝 [SEGMENT MERGE] Buffering: '{text}' (wait for more)")
                        continue  # Wait for more segments
                    elif is_duplicate:
                        # Skip duplicate, don't update timestamp
                        continue
                    
                    # Either first segment or timeout - process now
                    if self._stt_merge_buffer:
                        # Combine buffered segments with current (skip duplicate current)
                        if not is_duplicate:
                            self._stt_merge_buffer.append(text)
                        text = " ".join(self._stt_merge_buffer)
                        
                        # 🔥 BUILD 308: Final DEDUPE - Remove repeated bigrams from merged text
                        # Example: "פורץ דלתות פורץ דלתות" → "פורץ דלתות"
                        words = text.split()
                        if len(words) >= 4:
                            # Check if second half is duplicate of first half
                            mid = len(words) // 2
                            first_half = ' '.join(words[:mid])
                            second_half = ' '.join(words[mid:])
                            if first_half.strip() == second_half.strip():
                                text = first_half
                                logger.info(f"🔄 [BUILD 308 DEDUPE] Removed duplicate half: '{second_half}'")
                        
                        logger.info(f"📝 [SEGMENT MERGE] Combined {len(self._stt_merge_buffer)} segments: '{text}'")
                        self._stt_merge_buffer = []
                    
                    self._stt_last_segment_ts = now_ms
                    transcript = text
                    
                    # 🔥 SIMPLE_MODE: Structured utterance logging
                    # Single log line with all key info for debugging and analysis
                    try:
                        call_direction = getattr(self, 'call_direction', 'inbound')
                        call_goal = getattr(self, 'call_goal', 'lead_only')
                        user_has_spoken_state = self.user_has_spoken
                        is_ai_currently_speaking = self.is_ai_speaking_event.is_set()
                        
                        # Format: [UTTERANCE] SIMPLE_MODE=True direction=inbound goal=lead_only 
                        #         user_has_spoken=True ai_speaking=False text='...'
                        logger.info(
                            f"[UTTERANCE] SIMPLE_MODE={SIMPLE_MODE} direction={call_direction} "
                            f"goal={call_goal} user_has_spoken={user_has_spoken_state} "
                            f"ai_speaking={is_ai_currently_speaking} text='{transcript[:100]}'"
                        )
                    except Exception as log_err:
                        # Don't let logging errors break STT
                        logger.warning(f"[UTTERANCE] Logging error: {log_err}")
                    
                    # 🔥 BUILD 300: UNIFIED STT LOGGING - Step 3: Log final transcript
                    # Format: [STT_FINAL] → what goes into Lead State / AI processing
                    logger.info(f"[STT_FINAL] '{transcript}' (from raw: '{raw_text[:30]}...')")
                    
                    # 🔥 BUILD 204: CONSOLIDATED STT LOGGING - One line per final utterance for easy debugging
                    # Includes: business_id, raw_text, corrected_text, prompt_used, corrections applied
                    try:
                        stt_prompt_used = getattr(self, '_last_stt_prompt', 'unknown')[:80] if hasattr(self, '_last_stt_prompt') else 'unknown'
                        logger.info(
                            f"[STT_FINAL] business_id={self.business_id} "
                            f"raw='{raw_text[:50]}' "
                            f"corrected='{transcript[:50]}' "
                            f"vocab_corrections={vocab_corrections} "
                            f"prompt='{stt_prompt_used}...'"
                        )
                    except Exception as log_err:
                        pass  # Don't let logging errors break STT
                    
                    # 🎯 STT GUARD: Only NOW (after validation) mark user as having spoken
                    # This prevents hallucinated utterances from setting user_has_spoken flag
                    self.user_has_spoken = True
                    self._candidate_user_speaking = False  # Clear candidate flag
                    logger.info(f"✅ [STT_GUARD] Validated utterance - user_has_spoken=True")
                    
                    # 🔥 BUILD 170.3: LOOP PREVENTION - Reset counter when user speaks
                    self._consecutive_ai_responses = 0
                    self._last_user_transcript_ts = time.time()
                    self._last_user_speech_ts = time.time()  # 🔥 BUILD 170.3: Track for time-based guard
                    
                    # 🔥 BUILD 172: Update speech time for silence detection
                    # 🔥 BUILD 338: Mark as user speech to reset warning count
                    self._update_speech_time(is_user_speech=True)
                    # 🛑 DISENGAGE LOOP GUARD - user spoke, allow AI to respond again
                    if self._loop_guard_engaged:
                        logger.info(f"✅ [LOOP GUARD] User spoke - disengaging loop guard")
                        self._loop_guard_engaged = False
                    
                    # 💰 COST TRACKING: User finished speaking - stop timer (DEBUG only)
                    if hasattr(self, '_user_speech_start') and self._user_speech_start is not None:
                        user_duration = time.time() - self._user_speech_start
                        user_chunks = getattr(self, 'realtime_audio_in_chunks', 0)
                        logger.debug(f"[COST] User utterance: {user_duration:.2f}s ({user_chunks} chunks total)")
                        self._user_speech_start = None  # Reset for next utterance
                    
                    if transcript:
                        logger.info(f"👤 [REALTIME] User said: {transcript}")
                        if self._awaiting_confirmation_reply:
                            logger.info(f"✅ [CONFIRMATION] Received user response - clearing pending confirmation flag")
                        self._awaiting_confirmation_reply = False
                        
                        # Track metadata for downstream extraction logic
                        self._current_stt_confidence = event.get("confidence")
                        self._current_transcript_token_count = len(transcript.split())
                        self._current_transcript_is_first_answer = self.awaiting_greeting_answer and not self.first_post_greeting_utterance_handled
                        
                        # ═══════════════════════════════════════════════════════════════════════════
                        # 🔥 BUILD 303: FIRST POST-GREETING UTTERANCE HANDLING
                        # ═══════════════════════════════════════════════════════════════════════════
                        # If we're waiting for the first response after greeting, mark it as handled
                        if self.awaiting_greeting_answer and not self.first_post_greeting_utterance_handled:
                            self.first_post_greeting_utterance_handled = True
                            self.awaiting_greeting_answer = False
                            logger.info(f"✅ [BUILD 303] First post-greeting utterance: '{transcript[:50]}...' - processing as answer to greeting question")
                        
                        # ═══════════════════════════════════════════════════════════════════════════
                        # 🔥 PROMPT-ONLY: NEGATIVE ANSWER DETECTION - Full reset on "לא"
                        # ═══════════════════════════════════════════════════════════════════════════
                        # For appointment goal: do NOT reset state on every short "לא".
                        # Only treat it as a reset when it's an explicit cancellation OR it happens at a confirmation step.
                        call_goal = getattr(self, 'call_goal', 'lead_only')
                        last_ai_msg = None
                        try:
                            for msg in reversed(self.conversation_history):
                                if msg.get("speaker") == "ai":
                                    last_ai_msg = (msg.get("text", "") or "").lower()
                                    break
                        except Exception:
                            last_ai_msg = None

                        transcript_clean_neg = transcript.strip().lower().replace(".", "").replace("!", "").replace("?", "")
                        negative_answers = ["לא", "ממש לא", "חד משמעית לא", "לא צריך", "אין צורך", "לא לא", "לא נכון", "טעות"]
                        is_negative_answer = any(transcript_clean_neg.startswith(neg) for neg in negative_answers)

                        # Detect STRONG rejection: short, clear "no" (not just "לא" in a long sentence)
                        is_strong_rejection = is_negative_answer and len(transcript_clean_neg) < 20

                        if is_strong_rejection:
                            if call_goal == 'appointment':
                                explicit_cancel_phrases = [
                                    "לא רוצה", "לא מעוניין", "לא מעוניינת", "עזוב", "עזבי", "תבטל", "תבטלי", "לבטל",
                                    "לא צריך תור", "לא צריך פגישה", "לא לקבוע", "לא לקבוע תור", "לא לקבוע פגישה",
                                ]
                                is_explicit_cancel = any(p in transcript_clean_neg for p in explicit_cancel_phrases)
                                ai_is_asking_confirmation = bool(last_ai_msg) and any(
                                    p in last_ai_msg for p in ["נכון", "לאשר", "מאשר", "מאשרת", "לקבוע", "לשריין", "שנקבע", "שקובעים"]
                                )
                                if not (is_explicit_cancel or ai_is_asking_confirmation):
                                    logger.info(f"ℹ️ [APPOINTMENT] Short 'no' detected but NOT cancelling/resetting state: '{transcript}'")
                                else:
                                    # Treat as rejection/cancel at the relevant step, but avoid clearing unrelated locked fields.
                                    self.user_rejected_confirmation = True
                                    crm_ctx = getattr(self, 'crm_context', None)
                                    if crm_ctx and hasattr(crm_ctx, 'pending_slot'):
                                        # Clear only the pending slot so the flow re-asks date/time.
                                        crm_ctx.pending_slot = None
                                    asyncio.create_task(self._send_text_to_ai(
                                        "[SYSTEM] The user rejected/cancelled at the appointment confirmation step. "
                                        "Do NOT reset unrelated collected details. Ask for a new date/time or confirm if they still want to book."
                                    ))
                            else:
                                logger.info(f"🔥 [PROMPT-ONLY] STRONG REJECTION detected: '{transcript}' - resetting verification state")
                            
                            # 1) Clear verification / lead candidate state
                            self._verification_state = None
                            self._lead_candidate = {}
                            self._lead_confirmation_received = False
                            self.verification_confirmed = False
                            self.user_rejected_confirmation = True
                            
                            # 2) Clear any locked fields from previous interpretation
                            self._city_locked = False
                            self._city_raw_from_stt = None
                            self._service_locked = False
                            self._service_raw_from_stt = None
                            
                            logger.info(f"   → Cleared verification state, lead candidate, and locked fields")
                            
                            # 3) Inject system message to guide AI (context only, no script)
                            system_msg = "[SYSTEM] User rejected previous understanding. Ask again per your instructions."
                            
                            # Queue system message for next processing cycle
                            asyncio.create_task(self._send_text_to_ai(system_msg))
                            logger.info(f"   → Sent reset system message to AI")
                            
                        elif is_negative_answer:
                            logger.warning(f"⚠️ [BUILD 303] NEGATIVE ANSWER detected: '{transcript}' - user is rejecting/correcting")
                            # Mark that we need to handle this as a correction, not move forward
                            self.user_rejected_confirmation = True
                            # If we're tracking what AI asked, mark it for retry
                            if self.last_ai_question_type:
                                logger.info(f"   Last AI question type: {self.last_ai_question_type} - needs retry")
                        else:
                            # 🔥 BUILD 308: User provided meaningful content (not just rejection)
                            # Clear the cool-off flag so AI can respond normally
                            if getattr(self, '_awaiting_user_correction', False):
                                self._awaiting_user_correction = False
                                logger.info(f"✅ [BUILD 308] User provided content - clearing cool-off flag")
                        
                        # 🔥 BUILD 313: SIMPLIFIED - City correction handled by OpenAI Tool
                        # When user says "לא", AI naturally asks again and user provides correct city
                        # No need for complex city correction detection - AI handles it!
                        
                        # 🔥 BUILD 186: SEMANTIC COHERENCE GUARD
                        # Check if user's response makes sense given the last AI question
                        is_first_response = len([m for m in self.conversation_history if m.get("speaker") == "user"]) == 0
                        transcript_clean = transcript.strip().lower().replace(".", "").replace("!", "").replace("?", "")
                        
                        # Get last AI message for context check (already computed above when possible)
                        
                        is_incoherent_response = False
                        
                        # Check 1: First response after greeting should be a request, not "thank you"
                        if is_first_response and self.greeting_completed_at:
                            nonsense_first_responses = [
                                "תודה רבה", "תודה", "שלום", "היי", "ביי", "להתראות",
                                "okay", "ok", "yes", "no", "bye", "hello", "hi"
                            ]
                            if transcript_clean in nonsense_first_responses:
                                is_incoherent_response = True
                                logger.warning(f"⚠️ [BUILD 186] INCOHERENT: First response '{transcript}' doesn't make sense after greeting")
                        
                        # Check 2: If AI asked for city, response should contain city-related words or a city name
                        if last_ai_msg and ("עיר" in last_ai_msg or "איפה" in last_ai_msg or "מאיפה" in last_ai_msg):
                            # 🔥 BUILD 186: Use dynamic lexicon for city detection - no hardcoded lists!
                            cities_set, _, _ = load_hebrew_lexicon()
                            # Generic location indicators (not city-specific)
                            generic_indicators = ["ב", "מ", "עיר", "רחוב", "שכונה", "יישוב", "כפר", "מושב"]
                            has_location = any(ind in transcript_clean for ind in generic_indicators)
                            # Also check if any city from dynamic lexicon is mentioned
                            if not has_location:
                                has_location = any(city in transcript_clean for city in cities_set if len(city) > 2)
                            if not has_location and len(transcript_clean) < 15:
                                # Short response with no location after city question
                                if transcript_clean in ["תודה רבה", "תודה", "כן", "לא", "אוקי"]:
                                    is_incoherent_response = True
                                    logger.warning(f"⚠️ [BUILD 186] INCOHERENT: Response '{transcript}' doesn't match city question")
                        
                        # Check 3: If AI asked for name, response should be a name-like pattern
                        if last_ai_msg and ("שם" in last_ai_msg or "איך קוראים" in last_ai_msg):
                            # Response should be name-like (not just "thank you")
                            if transcript_clean in ["תודה רבה", "תודה", "שלום", "ביי"]:
                                is_incoherent_response = True
                                logger.warning(f"⚠️ [BUILD 186] INCOHERENT: Response '{transcript}' doesn't match name question")
                        
                        # If incoherent, mark for AI to handle with clarification
                        if is_incoherent_response:
                            # Add marker to transcript so AI knows to ask for clarification
                            logger.info(f"🔄 [BUILD 186] Marked incoherent response - AI will ask for clarification")
                        
                        # 🛡️ BUILD 168: Detect user confirmation words (expanded in BUILD 176)
                        confirmation_words = [
                            "כן", "נכון", "בדיוק", "כן כן", "yes", "correct", "exactly", 
                            "יופי", "מסכים", "בסדר", "מאה אחוז", "אוקיי", "אוקי", "ok",
                            "בטח", "סבבה", "מעולה", "תודה", "תודה רבה", "הכל נכון",
                            "זה נכון", "כן הכל", "כן כן כן", "אישור", "מאשר", "מאשרת",
                            "סגור", "סיימנו", "סיימתי", "זהו", "נכון מאוד", "אכן"
                        ]
                        transcript_lower = transcript.strip().lower()
                        if any(word in transcript_lower for word in confirmation_words):
                            # 🔥 FIX: Only set verification_confirmed if verification is enabled
                            verification_enabled = getattr(self.call_config, 'verification_enabled', False) if self.call_config else False
                            if verification_enabled:
                                logger.info(f"✅ [BUILD 176] User CONFIRMED with '{transcript[:30]}' - verification_confirmed = True")
                                self.verification_confirmed = True
                                self._lead_confirmation_received = True
                                self._awaiting_confirmation_reply = False
                                # 🔥 BUILD 203: Clear rejection flag when user confirms
                                self.user_rejected_confirmation = False
                            else:
                                logger.info(f"ℹ️ [BUILD 176] User said '{transcript[:30]}' but verification feature is DISABLED - ignoring as confirmation")
                        
                        # 🛡️ BUILD 168: If user says correction words, reset verification
                        # 🔥 BUILD 310: IMPROVED REJECTION DETECTION
                        # Only reset if:
                        # 1. Message starts with a rejection word (direct correction)
                        # 2. Message is ONLY a rejection (e.g., "לא", "לא ממש לא")
                        # 3. Message contains explicit correction phrases
                        # Don't reset for incidental "לא" like "אני לא צריך עזרה אחרת"
                        
                        transcript_stripped = transcript_lower.strip()
                        words = transcript_stripped.split()
                        
                        # Strong rejection patterns that ALWAYS trigger reset
                        strong_rejection_patterns = [
                            "לא נכון", "טעות", "תתקן", "לשנות", "ממש לא", "לא לא", 
                            "זה לא נכון", "לא זה", "אז לא", "אבל לא", "ממש ממש לא"
                        ]
                        is_strong_rejection = any(pattern in transcript_stripped for pattern in strong_rejection_patterns)
                        
                        # Weak rejection: message starts with or is just "לא" 
                        # Only trigger if short AND starts with rejection
                        is_weak_rejection = (
                            len(words) <= 4 and  # Short response
                            words and words[0] in ["לא", "רגע", "שנייה"]  # Starts with rejection
                        )
                        
                        # Check if AI just asked for confirmation (verification context)
                        ai_asked_verification = last_ai_msg and any(
                            phrase in last_ai_msg for phrase in [
                                "נכון", "האם הפרטים", "לאשר", "בסדר", "מסכים", "האם זה"
                            ]
                        )
                        
                        should_reset_verification = (
                            is_strong_rejection or 
                            (is_weak_rejection and ai_asked_verification)
                        )
                        
                        if should_reset_verification:
                            logger.info(f"🔄 [BUILD 310] User CORRECTION detected: strong={is_strong_rejection}, weak={is_weak_rejection}, ai_verify={ai_asked_verification}")
                            self.verification_confirmed = False
                            self._lead_confirmation_received = False
                            self._awaiting_confirmation_reply = False
                            # 🔥 FIX: Also reset the prompt flag so we can send a new verification request
                            self._verification_prompt_sent = False
                            # 🔥 BUILD 203: Cancel any pending hangup - user rejected!
                            self.user_rejected_confirmation = True
                            self.goodbye_detected = False  # Clear goodbye flag
                            if self.call_state == CallState.CLOSING:
                                self.call_state = CallState.ACTIVE
                                logger.info(f"📞 [BUILD 203] CLOSING → ACTIVE (user rejected confirmation)")
                            
                            # 🔥 BUILD 326: UNLOCK city - user is correcting
                            # This allows user to provide new city
                            self._unlock_city()
                            self._last_ai_mentioned_city = None
                            
                            # 🔥 BUILD 336: Also unlock service on rejection
                            self._unlock_service()
                            
                            # 🔥 BUILD 308: POST-REJECTION COOL-OFF
                            self._awaiting_user_correction = True
                            self._rejection_timestamp = time.time()
                            logger.info(f"⏳ [BUILD 308] POST-REJECTION COOL-OFF - AI will wait for user to speak")
                        elif "לא" in transcript_stripped:
                            # Incidental "לא" - just log it, don't reset
                            logger.info(f"ℹ️ [BUILD 310] Incidental 'לא' in '{transcript[:30]}' - NOT resetting verification")
                        
                        # Track conversation
                        self.conversation_history.append({"speaker": "user", "text": transcript, "ts": time.time()})
                        
                        # 🔥 SILENCE FAILSAFE: Start timeout waiting for AI response
                        # 🔥 FIX: SILENCE_FAILSAFE completely removed
                        # Expected flow when user speaks:
                        # 1. User speaks → transcription.completed fires
                        # 2. Conversation context updated with user text
                        # 3. AI should naturally respond (no synthetic prompts needed)
                        # 4. If AI doesn't respond after 15s, silence monitor asks "are you there?"
                        # No synthetic fallback content should be sent to the model
                        
                        # 🎯 SMART HANGUP: Extract lead fields from user speech as well
                        # 🔥 BUILD 307: Pass is_user_speech=True for proper city extraction
                        self._extract_lead_fields_from_ai(transcript, is_user_speech=True)
                        
                        # 🔧 FIX: Track user goodbye separately from AI polite closing
                        if self._looks_like_user_goodbye(transcript):
                            self.user_said_goodbye = True
                            self.last_user_goodbye_at = time.time() * 1000  # ms
                            logger.info(f"[USER GOODBYE] User said goodbye: '{transcript[:50]}...'")
                        
                        self._current_stt_confidence = None
                        self._current_transcript_token_count = 0
                        self._current_transcript_is_first_answer = False
                        
                        # 🔥 BUILD 313: Handle user confirmation with "נכון" - save city from AI's previous statement
                        confirmation_words = ["כן", "נכון", "בדיוק", "כן כן", "יופי", "מסכים"]
                        if any(word in transcript_lower for word in confirmation_words):
                            last_ai_city = getattr(self, '_last_ai_mentioned_city', None)
                            if last_ai_city and 'city' in getattr(self, 'required_lead_fields', []):
                                # User confirmed - save the city!
                                self._update_lead_capture_state('city', last_ai_city)
                                logger.info(f"🔒 [BUILD 313] User confirmed city '{last_ai_city}'")
                        
                        # 🎯 Mark that we have pending AI response (AI will respond to this)
                        self.has_pending_ai_response = True
                        
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🔥 BARGE-IN: Clear barge_in flag now that transcription is complete
                        # ═══════════════════════════════════════════════════════════════════════
                        if self.barge_in_active:
                            self.barge_in_active = False
                            logger.info(f"✅ [BARGE-IN] Cleared barge_in flag after transcription")
                        
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🔥 SILENCE COMMANDS: Handle "שקט/די/רגע/תפסיק" → HARD STOP
                        # ═══════════════════════════════════════════════════════════════════════
                        # This is a COMMAND, not a question that wasn't understood
                        # NEVER respond with "לא שמעתי" or any other response
                        # Just return to listening in complete silence
                        # ═══════════════════════════════════════════════════════════════════════
                        silence_commands = ["שקט", "שקטי", "די", "רגע", "תפסיק", "תפסיקי", "סתום", "סתמי", "שש", "שששש"]
                        transcript_normalized = transcript.strip().lower().replace(".", "").replace("!", "").replace(",", "").replace("?", "")
                        
                        is_silence_command = transcript_normalized in silence_commands
                        
                        if is_silence_command:
                            logger.info(f"🤫 [SILENCE_CMD] User said '{transcript}' - HARD STOP, no response, returning to listening")
                            # Clear user_speaking flag immediately - ready for next input
                            self.user_speaking = False
                            # Mark that we received input but won't respond
                            self.has_pending_ai_response = False
                            # CRITICAL: Do NOT trigger response.create
                            # Do NOT send "לא שמעתי" or any acknowledgment
                            # Just go back to listening mode
                            logger.info(f"✅ [SILENCE_CMD] Back to listening mode - awaiting next user input")
                            continue  # Skip all response logic
                        
                        # ──────────────────────────────────────────────────────────────
                        # 🔥 SERVER-FIRST APPOINTMENTS (no tools):
                        # In this mode, session.turn_detection.create_response=False, so we must manually trigger response.create.
                        # Before triggering, the server may schedule/offer alternatives deterministically and inject a verbatim sentence.
                        # ──────────────────────────────────────────────────────────────
                        manual_turn = bool(
                            getattr(self, "_manual_response_turns_enabled", False)
                            and getattr(self, "call_goal", "lead_only") == "appointment"
                        )
                        if manual_turn and transcript and len(transcript.strip()) > 0:
                            # 🔥 FIX: Cancel any active AI response before creating new one
                            # This prevents "conversation_already_has_active_response" error
                            if self.active_response_id and self.active_response_status == "in_progress":
                                if self._should_send_cancel(self.active_response_id):
                                    try:
                                        logger.info(f"🛑 [MANUAL_TURN] Cancelling active response {self.active_response_id[:20]}... before creating new one")
                                        await self.realtime_client.cancel_response(self.active_response_id)
                                        self._mark_response_cancelled_locally(self.active_response_id, "manual_turn_barge_in")
                                        
                                        # Wait for cancellation to complete (up to 500ms)
                                        # Check for active_response_id to be cleared or status to change
                                        for _ in range(50):  # 50 * 10ms = 500ms max wait
                                            if not self.active_response_id or self.active_response_status != "in_progress":
                                                logger.info(f"✅ [MANUAL_TURN] Cancellation completed, proceeding with new response")
                                                break
                                            await asyncio.sleep(0.01)
                                        else:
                                            logger.warning(f"⚠️ [MANUAL_TURN] Cancellation timeout - proceeding anyway")
                                    except Exception as cancel_err:
                                        error_str = str(cancel_err).lower()
                                        if 'not_active' not in error_str and 'already_cancelled' not in error_str:
                                            logger.error(f"⚠️ [MANUAL_TURN] Cancel error (continuing): {cancel_err}")
                            
                            try:
                                handled = await self._maybe_server_first_schedule_from_transcript(client, transcript)
                                if not handled:
                                    await self.trigger_response("APPOINTMENT_MANUAL_TURN", client)
                            except Exception as _sf_err:
                                logger.error(f"⚠️ [SERVER_FIRST] Error (continuing with normal AI turn): {_sf_err}")
                                await self.trigger_response("APPOINTMENT_MANUAL_TURN", client)

                        # 🔥 DEFAULT (Realtime-native): DO NOT manually trigger response.create here.
                        # OpenAI's server_vad already automatically creates responses when speech ends.
                        if not manual_turn:
                            if transcript and len(transcript.strip()) > 0:
                                logger.info(f"✅ [TRANSCRIPTION] Received user input: '{transcript[:40]}...' (response auto-created by server_vad)")
                            else:
                                logger.warning(f"⚠️ [TRANSCRIPTION] Empty transcript received")
                        
                        # 🛡️ CHECK: Don't run NLP twice for same appointment
                        already_confirmed = getattr(self, 'appointment_confirmed_in_session', False)
                        if already_confirmed:
                            logger.info(f"🛡️ [NLP] SKIP - Appointment already confirmed in this session")
                        else:
                            # ⭐ BUILD 350: NLP disabled - no mid-call appointment logic
                            if ENABLE_LEGACY_TOOLS:
                                # LEGACY: Check for appointment confirmation after user speaks
                                logger.debug(f"🔍 [LEGACY DEBUG] Calling NLP after user transcript: '{transcript[:50]}...'")
                                self._check_appointment_confirmation(transcript)
                        
                        # 🔴 CRITICAL — Real Hangup (USER): transcript-only + closing-sentence only
                        # Trigger hangup ONLY if the user utterance is purely a closing sentence
                        # based on the explicit list (no VAD/noise decisions).
                        if not self.pending_hangup and not getattr(self, "hangup_requested", False):
                            user_intent = self._classify_real_hangup_intent(transcript, "user")
                            if user_intent == "hangup":
                                await self.request_hangup("user_goodbye", "transcript", transcript, "user")
                                continue
                            elif user_intent == "clarify":
                                # ❗Rule against accidental hangup:
                                # "ביי... רגע" / "ביי אבל..." → ask once, do not hang up.
                                if not getattr(self, "hangup_clarification_asked", False):
                                    self.hangup_clarification_asked = True
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        "לפני שאני מנתק—רצית לסיים את השיחה?"
                                    ))
                        
                        # 🎯 BUILD 163: Check if all lead info is captured
                        # 🔥 BUILD 172 FIX: Only close after customer CONFIRMS the details!
                        # 🔥 FIX: Verification feature must be enabled for this to work
                        verification_enabled = getattr(self.call_config, 'verification_enabled', False) if self.call_config else False
                        if self.auto_end_after_lead_capture and not self.pending_hangup and verification_enabled:
                            fields_ready = self._check_lead_captured()
                            if fields_ready and not self.lead_captured:
                                self.lead_captured = True
                            readiness_confirmed = (self.lead_captured or self._lead_confirmation_received) and self.verification_confirmed
                            
                            if readiness_confirmed and not self._lead_closing_dispatched:
                                logger.info(f"✅ [BUILD 163] Lead confirmed - closing call (verification enabled)")
                                self._lead_closing_dispatched = True
                                
                                if self.call_state == CallState.ACTIVE:
                                    self.call_state = CallState.CLOSING
                                    logger.info(f"📞 [STATE] Transitioning ACTIVE → CLOSING (lead confirmed)")
                                
                                asyncio.create_task(self._send_server_event_to_ai(
                                    "[SERVER] ✅ הלקוח אישר את הפרטים! סיים בצורה מנומסת - הודה ללקוח ואמור להתראות."
                                ))
                                asyncio.create_task(self._fallback_hangup_after_timeout(10, "lead_captured_confirmed"))
                            elif fields_ready and not self.verification_confirmed and not getattr(self, '_verification_prompt_sent', False) and not self._awaiting_confirmation_reply:
                                self._verification_prompt_sent = True
                                logger.info(f"⏳ [BUILD 172] Lead fields collected - waiting for customer confirmation")
                                
                                templated_confirmation = self._build_confirmation_from_state()
                                has_locked_data = self._city_locked or self._service_locked
                                
                                if templated_confirmation and has_locked_data:
                                    logger.info(f"🎯 [BUILD 336] Injecting LOCKED templated confirmation: '{templated_confirmation}'")
                                    logger.info(f"🔒 [BUILD 336] city_locked={self._city_locked}, service_locked={self._service_locked}")
                                    
                                    self._expected_confirmation = templated_confirmation
                                    self._confirmation_validated = False
                                    self._speak_exact_resend_count = 0
                                    self._awaiting_confirmation_reply = True
                                    
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        f"[SPEAK_EXACT] אמור בדיוק את המשפט הבא ללקוח (ללא שינויים!): \"{templated_confirmation}\""
                                    ))
                                elif templated_confirmation:
                                    logger.warning(f"⚠️ [BUILD 336] Sending confirmation without locks: '{templated_confirmation}'")
                                    
                                    self._expected_confirmation = templated_confirmation
                                    self._confirmation_validated = False
                                    self._speak_exact_resend_count = 0
                                    self._awaiting_confirmation_reply = True
                                    
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        f"[SPEAK_EXACT] אמור בדיוק את המשפט הבא ללקוח: \"{templated_confirmation}\""
                                    ))
                                else:
                                    logger.error(f"❌ [BUILD 336] No STT data to confirm - waiting for more info")
                                    self._verification_prompt_sent = False
                                    self._expected_confirmation = None
                                    self._confirmation_validated = False
                                    self._speak_exact_resend_count = 0
                    
                    # ✅ COST SAFETY: Transcription completed successfully
                    logger.debug(f"[SAFETY] Transcription successful (total failures: {self.transcription_failed_count})")
                
                elif event_type.startswith("error"):
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    logger.error(f"❌ [REALTIME] Error event: {error_msg}")
                    # 🔒 Clear locks on error to prevent permanent stall
                    self.response_pending_event.clear()
                    self.active_response_id = None
                    self.active_response_status = "done"  # 🔥 IDEMPOTENT CANCEL: Mark as done (error)
                    self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
                    # 🔥 CRITICAL: Reset greeting state on error to prevent hangup block
                    if self.is_playing_greeting:
                        logger.error(f"🛡️ [ERROR CLEANUP] Resetting is_playing_greeting due to error")
                        self.is_playing_greeting = False
                        self.greeting_completed_at = time.time()  # Mark greeting as done
                
        except Exception as e:
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME_FATAL: Exception in audio receiver loop
            # ═══════════════════════════════════════════════════════════════════════
            import traceback
            _orig_print(f"🔥 [REALTIME_FATAL] Unhandled exception in _realtime_audio_receiver: {e}", flush=True)
            _orig_print(f"🔥 [REALTIME_FATAL] call_sid={self.call_sid}", flush=True)
            traceback.print_exc()
            logger.error(f"[REALTIME_FATAL] Exception in audio receiver: {e}")
            
            # 🔥 CRITICAL: Reset greeting state on exception to prevent hangup block
            if self.is_playing_greeting:
                logger.error(f"🛡️ [EXCEPTION CLEANUP] Resetting is_playing_greeting due to exception")
                self.is_playing_greeting = False
                self.greeting_completed_at = time.time()
        
        # 🔥 CRITICAL: Always reset greeting state when receiver ends
        if self.is_playing_greeting:
            logger.info(f"🛡️ [EXIT CLEANUP] Resetting is_playing_greeting on receiver exit")
            self.is_playing_greeting = False
            if self.greeting_completed_at is None:
                self.greeting_completed_at = time.time()
        
        logger.info(f"📥 [REALTIME] Audio receiver ended")
    
    async def _send_server_event_to_ai(self, message_text: str):
        """
        🚫 DEPRECATED: This function is permanently disabled and will be removed in future versions.
        
        REASON: Sending server-generated events to the AI model with role="user" violated
        the "transcription is truth" principle and caused confusion. The AI would receive
        synthetic messages as if the customer said them, leading to inappropriate responses.
        
        ⚠️ WARNING: This function does nothing. If you're calling it, remove the call.
        All server-side intelligence should be handled through proper context management,
        not synthetic user messages.
        
        Args:
            message_text: Message text - IGNORED (function does nothing)
        """
        # Log deprecated usage for tracking
        logger.warning(f"[DEPRECATED] _send_server_event_to_ai called but does nothing. "
                      f"Remove this call. Preview: '{message_text[:100]}'")
        return
    
    async def _send_silence_warning(self):
        """
        🔥 FIX BUG 2: Finalize user turn when timeout expires without transcription
        
        This prevents the system from getting stuck in silence when:
        - speech_started fired
        - speech_stopped fired
        - But no transcription.completed was received
        
        The AI should always reply, even if transcription failed.
        
        NOTE: This is async wrapper for _finalize_user_turn_on_timeout
        """
        logger.warning(f"[TURN_END] Async silence warning triggered")
        self._finalize_user_turn_on_timeout()
    
    def _finalize_user_turn_on_timeout(self):
        """
        🔥 FIX ISSUE 2: Finalize user turn when timeout expires without transcription
        
        This prevents the system from getting stuck in silence when:
        - speech_started fired
        - speech_stopped fired
        - But no transcription.completed was received
        
        The AI should always reply, even if transcription failed.
        This method is called from the timeout check in speech_started handler.
        
        ✅ NEW REQ: "Gentle" implementation - doesn't create response, doesn't override state
        """
        logger.info(f"[TURN_END] Timeout finalization triggered")
        
        # ✅ NEW REQ: Don't act if user is still speaking
        if getattr(self, 'user_speaking', False):
            logger.info(f"[TURN_END] User still speaking - skipping timeout action")
            return
        
        # ✅ NEW REQ: Don't act if session is closing/closed
        if getattr(self, 'closed', False) or getattr(self, 'hangup_triggered', False):
            logger.info(f"[TURN_END] Session closing - skipping timeout action")
            return
        
        # Clear candidate flag
        self._candidate_user_speaking = False
        self._utterance_start_ts = None
        
        # Check if we're truly stuck (no response in progress)
        # ✅ NEW REQ: Don't override state if response.created already started
        if not self.response_pending_event.is_set() and not self.is_ai_speaking_event.is_set():
            # No AI response in progress - this means we're stuck
            # The transcription probably failed or was rejected
            logger.info(f"[TURN_END] No AI response in progress - system was stuck in silence")
            
            # CORRECTIVE ACTION: Clear any stale state that might block response
            # ✅ NEW REQ: Only clear stale state, don't create new response
            if self.active_response_id:
                logger.info(f"[TURN_END] Clearing stale active_response_id: {self.active_response_id[:20]}...")
                self.active_response_id = None
                self.active_response_status = "done"  # 🔥 IDEMPOTENT CANCEL: Mark as done (timeout)
                self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
            
            if self.has_pending_ai_response:
                logger.info(f"[TURN_END] Clearing stale has_pending_ai_response flag")
                self.has_pending_ai_response = False
            
            # The silence monitor will detect this and trigger a prompt for user to speak
            # We don't force a response here to avoid AI hallucinations
            logger.info(f"[TURN_END] State cleared - silence monitor will handle next action")
        else:
            logger.info(f"[TURN_END] AI response already in progress - no action needed")
    
    def _simple_barge_in_stop(self, reason="user_speech"):
        """
        🔥 BARGE-IN: Stop AI when user starts speaking
        
        Clean barge-in implementation:
        1. Cancel OpenAI current response (if active)
        2. Flush TX queue to stop audio playback immediately
        3. Clear speaking flags
        
        Rule: Use response.cancel, never drop audio deltas.
        """
        # 🔥 REMOVED: greeting_lock protection - allow barge-in during greeting

        # 🛡️ PROTECT GREETING - Never cancel during greeting playback!
        if hasattr(self, 'is_playing_greeting') and self.is_playing_greeting:
            logger.info(f"🛡️ [BARGE_IN] Ignoring - greeting still playing")
            return
        
        # 1) Cancel OpenAI current response
        cancelled_id = None
        try:
            ai_speaking = bool(getattr(self, "is_ai_speaking_event", None) and self.is_ai_speaking_event.is_set())
            if (
                getattr(self, "active_response_id", None)
                and getattr(self, "realtime_client", None)
                and ai_speaking
                and self._should_send_cancel(self.active_response_id)
            ):
                # Create event loop if needed (reuse pattern from _handle_realtime_barge_in)
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                cancelled_id = self.active_response_id
                cancel_event = {"type": "response.cancel", "response_id": cancelled_id}
                
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.realtime_client.send_event(cancel_event),
                        loop
                    )
                    future.result(timeout=0.3)  # Quick timeout
                    logger.info(f"[BARGE_IN] cancel_sent response_id={cancelled_id[:20] if cancelled_id else 'None'}")
                except Exception as cancel_err:
                    logger.error(f"⚠️ [BARGE_IN] Cancel failed: {cancel_err}")
        except Exception as e:
            logger.error(f"⚠️ [BARGE_IN] Error during cancel: {e}")
        
        # 2) Flush BOTH queues to stop audio playback immediately
        # 🔥 FIX 5: NO TRUNCATION enforcement - MUST clear ALL queues during barge-in
        # 🔥 Point 4: TX loop verified - uses only tx_q, no local buffers
        realtime_cleared = 0
        tx_cleared = 0
        try:
            # Clear OpenAI → TX queue (realtime_audio_out_queue)
            q1 = getattr(self, "realtime_audio_out_queue", None)
            if q1:
                while True:
                    try:
                        q1.get_nowait()
                        realtime_cleared += 1
                    except queue.Empty:
                        break
            
            # Clear TX → Twilio queue (tx_q)
            q2 = getattr(self, "tx_q", None)
            if q2:
                while True:
                    try:
                        q2.get_nowait()
                        tx_cleared += 1
                    except queue.Empty:
                        break
        except Exception as e:
            logger.error(f"⚠️ [BARGE_IN] Error during flush: {e}")
        
        logger.info(f"[BARGE_IN] queues_flushed realtime={realtime_cleared} tx={tx_cleared} total={realtime_cleared + tx_cleared}")
        _orig_print(f"🧹 [FIX 5] NO TRUNCATION enforced: cleared {realtime_cleared + tx_cleared} frames", flush=True)
        
        # 3) Clear speaking flags
        try:
            if hasattr(self, 'is_ai_speaking_event'):
                self.is_ai_speaking_event.clear()
            self.speaking = False
            self.active_response_id = None
            self.active_response_status = "cancelled"  # 🔥 IDEMPOTENT CANCEL: Mark as cancelled
            self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset flag
            
            # 🔥 FIX 4: RACE CONDITION - Clear pending_hangup on barge-in
            # If user interrupts while bot saying goodbye, DON'T disconnect
            # User interrupted = conversation continues, goodbye is cancelled
            if getattr(self, 'pending_hangup', False):
                _orig_print(f"[BARGE_IN] Clearing pending_hangup (user interrupted goodbye)", flush=True)
                self.pending_hangup = False
                self.pending_hangup_response_id = None
                self.pending_hangup_reason = None
        except Exception as e:
            logger.error(f"⚠️ [BARGE_IN] Error clearing flags: {e}")
        
        logger.info(f"🛑 [BARGE_IN] Stop complete (reason={reason})")

    async def _check_appointment_confirmation_async(self):
        """
        Check for appointment requests using GPT-4o-mini NLP parser
        Runs continuously in background thread, triggered after each message
        """
        # Skip if business_id not set yet
        if not self.business_id:
            logger.warning(f"⚠️ [NLP] No business_id - skipping")
            return
        
        # Skip if no conversation history
        if not self.conversation_history:
            logger.warning(f"⚠️ [NLP] No conversation history - skipping")
            return
        
        logger.info(f"🔍 [NLP] ▶️ Analyzing conversation for appointment intent...")
        logger.info(f"🔍 [NLP] Conversation history has {len(self.conversation_history)} messages")
        logger.info(f"🔍 [NLP] Last 3 messages: {self.conversation_history[-3:]}")
        
        # Call GPT-4o-mini NLP parser
        result = await extract_appointment_request(
            self.conversation_history,
            self.business_id
        )
        
        logger.info(f"🔍 [NLP] ◀️ NLP result: {result}")
        
        if not result or result.get("action") == "none":
            logger.info(f"📭 [NLP] No appointment action detected (action={result.get('action') if result else 'None'})")
            return
        
        action = result.get("action")
        date_iso = result.get("date")
        time_str = result.get("time")
        customer_name = result.get("name")
        confidence = result.get("confidence", 0.0)
        
        # 🔥 CRITICAL FIX: Save customer name for persistence!
        # NLP only looks at last 10 messages, so name can be lost if mentioned earlier
        # Strategy: Save to crm_context if it exists, otherwise cache temporarily on handler
        if customer_name:
            # 🎯 DYNAMIC LEAD STATE: Update lead capture state for smart hangup
            self._update_lead_capture_state('name', customer_name)
            
            # 🔥 BUILD 337 FIX: Reset name reminder flag now that we have the name!
            if getattr(self, '_name_reminder_sent', False):
                self._name_reminder_sent = False
                logger.info(f"✅ [BUILD 337] Name captured - reset _name_reminder_sent flag")
            
            crm_context = getattr(self, 'crm_context', None)
            if crm_context:
                # Context exists - save there
                if not crm_context.customer_name:
                    crm_context.customer_name = customer_name
                    logger.info(f"✅ [NLP] Saved customer name to crm_context: {customer_name}")
            else:
                # Context doesn't exist yet - save to temporary cache
                self.pending_customer_name = customer_name
                logger.info(f"✅ [NLP] Saved customer name to temporary cache: {customer_name}")
        
        # Fall back to saved name if NLP returns None
        if not customer_name:
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and crm_context.customer_name:
                customer_name = crm_context.customer_name
                logger.info(f"🔄 [NLP] Retrieved customer name from crm_context: {customer_name}")
            elif hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                customer_name = self.pending_customer_name
                logger.info(f"🔄 [NLP] Retrieved customer name from temporary cache: {customer_name}")
        
        logger.info(f"🎯 [NLP] ✅ Detected action={action}, date={date_iso}, time={time_str}, name={customer_name}, confidence={confidence}")
        
        # 🔍 DEBUG: Check CRM context state
        crm_context = getattr(self, 'crm_context', None)
        if crm_context:
            logger.debug(f"[DEBUG] CRM context - name: '{crm_context.customer_name}', phone: '{crm_context.customer_phone}'")
        else:
            logger.debug(f"[DEBUG] No CRM context exists yet")
        
        # 🔥 BUILD 146 FIX: Save date/time to pending_slot from ANY NLP extraction
        # This ensures we don't lose the time when it "falls off" the 10-message history window
        if date_iso or time_str:
            crm_context = getattr(self, 'crm_context', None)
            if crm_context:
                # Initialize or update pending_slot
                if not hasattr(crm_context, 'pending_slot') or not crm_context.pending_slot:
                    crm_context.pending_slot = {}
                
                # Only update if we have new values (don't overwrite with None)
                if date_iso:
                    crm_context.pending_slot['date'] = date_iso
                    logger.info(f"💾 [NLP] Saved date to pending_slot: {date_iso}")
                if time_str:
                    crm_context.pending_slot['time'] = time_str
                    logger.info(f"💾 [NLP] Saved time to pending_slot: {time_str}")
            
            # 🔥 BUILD 340: Save preferred_time to lead_capture_state for webhook/smart hangup
            # Handle partial data - save whatever we have
            if date_iso or time_str:
                # First check if we have existing partial data in pending_slot
                existing_date = date_iso
                existing_time = time_str
                if crm_context and hasattr(crm_context, 'pending_slot') and crm_context.pending_slot:
                    existing_date = existing_date or crm_context.pending_slot.get('date')
                    existing_time = existing_time or crm_context.pending_slot.get('time')
                
                # Build preferred_time from available components
                if existing_date and existing_time:
                    preferred_time = f"{existing_date} {existing_time}"
                elif existing_date:
                    preferred_time = existing_date
                elif existing_time:
                    preferred_time = existing_time
                else:
                    preferred_time = None
                
                if preferred_time:
                    self._update_lead_capture_state('preferred_time', preferred_time, source='nlp')
                    logger.info(f"💾 [BUILD 340] Saved preferred_time to lead state: {preferred_time}")
        
        # 🔥 NEW: Handle "hours_info" action (user asking about business hours, NOT appointment!)
        if action == "hours_info":
            logger.info(f"📋 [NLP] User asking for business hours info - responding with policy")
            try:
                # Load business hours from policy
                from server.policy.business_policy import get_business_policy
                policy = get_business_policy(self.business_id)
                
                if DEBUG: logger.debug(f"📊 [DEBUG] Policy loaded: allow_24_7={policy.allow_24_7}, opening_hours={policy.opening_hours}")
                
                if policy.allow_24_7:
                    await self._send_server_event_to_ai("hours_info - העסק פתוח 24/7, אפשר לקבוע תור בכל יום ושעה.")
                elif policy.opening_hours:
                    # Format hours in Hebrew
                    day_names = {"sun": "ראשון", "mon": "שני", "tue": "שלישי", "wed": "רביעי", "thu": "חמישי", "fri": "שישי", "sat": "שבת"}
                    hours_lines = []
                    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
                        windows = policy.opening_hours.get(day_key, [])
                        if not windows:
                            hours_lines.append(f"{day_names[day_key]}: סגור")
                        else:
                            time_ranges = ", ".join([f"{w[0]}-{w[1]}" for w in windows])
                            hours_lines.append(f"{day_names[day_key]}: {time_ranges}")
                    
                    hours_text = "שעות הפעילות שלנו:\n" + "\n".join(hours_lines)
                    logger.info(f"✅ [DEBUG] Sending hours to AI: {hours_text[:100]}...")
                    await self._send_server_event_to_ai(f"hours_info - {hours_text}")
                else:
                    logger.warning(f"⚠️ [DEBUG] No opening_hours in policy!")
                    await self._send_server_event_to_ai("hours_info - שעות הפעילות לא הוגדרו במערכת.")
            except Exception as e:
                logger.error(f"❌ [ERROR] Failed to load business policy: {e}")
                import traceback
                traceback.print_exc()
                await self._send_server_event_to_ai("hours_info - לא הצלחתי לטעון את שעות הפעילות. אפשר ליצור קשר ישירות.")
            return
        
        # 🔥 NEW: Handle "ask" action (user asking for availability for specific date/time)
        if action == "ask":
            logger.info(f"❓ [NLP] User asking for availability - checking slot...")
            
            # 🔥 BUILD 186: OUTBOUND CALLS - Skip scheduling entirely!
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if is_outbound:
                logger.warning(f"⚠️ [NLP] OUTBOUND call - skipping availability check (outbound follows prompt only)")
                return
            
            # 🔥 CHECK IF APPOINTMENTS ARE ENABLED (call_goal)
            call_goal = getattr(self, 'call_goal', 'lead_only')
            if call_goal != 'appointment':
                logger.warning(f"⚠️ [NLP] Appointments not enabled (call_goal={call_goal}) - not checking availability")
                return
            
            # 🔥 BUILD 337: CHECK IF NAME IS REQUIRED BUT MISSING - BLOCK scheduling!
            # This prevents scheduling from proceeding without collecting the name first
            crm_context = getattr(self, 'crm_context', None)
            has_name = (crm_context and crm_context.customer_name) or (hasattr(self, 'pending_customer_name') and self.pending_customer_name) or customer_name
            
            # Check if name is required by business prompt
            required_fields = getattr(self, 'required_lead_fields', [])
            name_required = 'name' in required_fields
            
            # 🔥 BUILD 337 FIX: ALWAYS BLOCK if name required but missing
            # Only send reminder ONCE (track with flag), but ALWAYS block progression
            if name_required and not has_name:
                name_reminder_sent = getattr(self, '_name_reminder_sent', False)
                if not name_reminder_sent:
                    logger.warning(f"⚠️ [BUILD 337] Name required but missing! Reminding AI to ask for name FIRST")
                    await self._send_server_event_to_ai("need_name_first - לפני שנקבע תור, שאל את הלקוח: מה השם שלך?")
                    self._name_reminder_sent = True  # Don't send reminder again
                else:
                    logger.info(f"📋 [BUILD 337] Name still missing (reminder already sent) - blocking scheduling")
                # 🔥 CRITICAL: RETURN to block scheduling - don't just continue!
                return
            
            if not date_iso or not time_str:
                # User wants appointment but didn't specify date/time
                logger.warning(f"⚠️ [NLP] User wants appointment but no date/time - asking for it")
                await self._send_server_event_to_ai("need_datetime - שאל את הלקוח: באיזה תאריך ושעה היית רוצה לקבוע?")
                return
            
            # 🛡️ BUILD 149 FIX: Check if this slot was already marked as busy (prevent loop)
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and hasattr(crm_context, 'busy_slots'):
                busy_key = f"{date_iso}_{time_str}"
                if busy_key in crm_context.busy_slots:
                    logger.info(f"🛡️ [GUARD] Slot {busy_key} already marked busy - skipping re-check to prevent loop")
                    return
            
            # Parse requested datetime
            from datetime import datetime, timedelta
            import pytz
            tz = pytz.timezone('Asia/Jerusalem')
            
            try:
                target_date = datetime.fromisoformat(date_iso)
                hour, minute = map(int, time_str.split(":"))
                start_dt = tz.localize(datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0))
                
                # Check availability
                is_available = validate_appointment_slot(self.business_id, start_dt)
                
                # Get CRM context
                crm_context = getattr(self, 'crm_context', None)
                
                if is_available:
                    # ✅ SLOT AVAILABLE - Save to pending_slot and inform AI
                    logger.info(f"✅ [NLP] Slot {date_iso} {time_str} is AVAILABLE!")
                    if crm_context:
                        crm_context.pending_slot = {
                            "date": date_iso,
                            "time": time_str,
                            "available": True
                        }
                    
                    # 🔥 BUILD 340: Save confirmed slot to lead_capture_state for webhook
                    preferred_time = f"{date_iso} {time_str}"
                    self._update_lead_capture_state('preferred_time', preferred_time, source='availability_check')
                    logger.info(f"💾 [BUILD 340] Saved CONFIRMED preferred_time to lead state: {preferred_time}")
                    
                    await self._send_server_event_to_ai(f"✅ פנוי! {date_iso} {time_str}")
                else:
                    # ❌ SLOT TAKEN - Find alternatives and inform AI
                    logger.error(f"❌ [NLP] Slot {date_iso} {time_str} is TAKEN - finding alternatives...")
                    
                    # 🛡️ BUILD 149 FIX: Clear pending_slot and track busy slots to prevent loop
                    if crm_context:
                        crm_context.pending_slot = None  # Clear stale pending slot
                        # Track this slot as busy to prevent re-checking
                        if not hasattr(crm_context, 'busy_slots'):
                            crm_context.busy_slots = set()
                        busy_key = f"{date_iso}_{time_str}"
                        crm_context.busy_slots.add(busy_key)
                        logger.info(f"🛡️ [GUARD] Marked slot {busy_key} as busy - will not recheck")
                    
                    # Find next 3 available slots
                    from server.policy.business_policy import get_business_policy
                    policy = get_business_policy(self.business_id)
                    slot_size_min = policy.slot_size_min
                    
                    alternatives = []
                    check_dt = start_dt + timedelta(minutes=slot_size_min)
                    max_checks = 20  # Check up to 20 slots ahead
                    
                    for _ in range(max_checks):
                        if validate_appointment_slot(self.business_id, check_dt):
                            alternatives.append(check_dt.strftime("%H:%M"))
                            if len(alternatives) >= 3:
                                break
                        check_dt += timedelta(minutes=slot_size_min)
                    
                    if alternatives:
                        alternatives_str = " או ".join(alternatives)
                        await self._send_server_event_to_ai(f"❌ תפוס - השעה {time_str} תפוסה. מה דעתך על {alternatives_str}?")
                    else:
                        await self._send_server_event_to_ai(f"❌ תפוס - השעה {time_str} תפוסה. תנסה יום אחר?")
                    
            except Exception as e:
                logger.error(f"❌ [NLP] Error checking availability: {e}")
                import traceback
                traceback.print_exc()
                await self._send_server_event_to_ai("need_datetime - לא הצלחתי לבדוק זמינות. באיזה תאריך ושעה?")
            
            return
        
        # 🔥 NEW: Handle "confirm" action (user confirmed appointment)
        if action == "confirm":
            logger.info(f"")
            logger.info(f"=" * 80)
            logger.info(f"🎯 [APPOINTMENT FLOW] ========== CONFIRM ACTION TRIGGERED ==========")
            logger.info(f"=" * 80)
            
            # 🔥 BUILD 186: OUTBOUND CALLS - Skip scheduling entirely!
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if is_outbound:
                logger.warning(f"⚠️ [APPOINTMENT FLOW] BLOCKED - OUTBOUND call (outbound follows prompt only)")
                return
            
            # 🔥 CHECK IF APPOINTMENTS ARE ENABLED (call_goal)
            call_goal = getattr(self, 'call_goal', 'lead_only')
            if call_goal != 'appointment':
                logger.warning(f"⚠️ [APPOINTMENT FLOW] BLOCKED - call_goal={call_goal} (expected 'appointment')")
                return
            
            # 🛡️ CRITICAL GUARD: Check if appointment was already created in this session
            # This prevents the loop where NLP keeps detecting "confirm" from AI's confirmation message
            if getattr(self, 'appointment_confirmed_in_session', False):
                logger.warning(f"⚠️ [APPOINTMENT FLOW] BLOCKED - Appointment already created in this session!")
                logger.warning(f"⚠️ [APPOINTMENT FLOW] Ignoring duplicate confirm action to prevent loop")
                return
            
            # 🛡️ Also check CRM context flag
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and crm_context.has_appointment_created:
                logger.warning(f"⚠️ [APPOINTMENT FLOW] BLOCKED - CRM context shows appointment already created!")
                logger.warning(f"⚠️ [APPOINTMENT FLOW] Ignoring duplicate confirm action to prevent loop")
                return
            
            logger.info(f"📝 [FLOW STEP 1] NLP returned: action={action}, date={date_iso}, time={time_str}, name={customer_name}")
            logger.info(f"📝 [FLOW STEP 1] confidence={confidence}")
            
            logger.info(f"📝 [FLOW STEP 2] CRM context exists: {crm_context is not None}")
            
            # ✅ BUILD 145: FALLBACK - Use pending_slot if NLP didn't return date/time
            # This handles cases where user confirmed but NLP missed the time from earlier messages
            if crm_context and hasattr(crm_context, 'pending_slot') and crm_context.pending_slot:
                pending = crm_context.pending_slot
                logger.info(f"📝 [FLOW STEP 3] pending_slot found: {pending}")
                
                # Use pending_slot values if NLP values are missing
                if not date_iso and pending.get('date'):
                    date_iso = pending['date']
                    logger.info(f"📝 [FLOW STEP 3] Using date from pending_slot: {date_iso}")
                if not time_str and pending.get('time'):
                    time_str = pending['time']
                    logger.info(f"📝 [FLOW STEP 3] Using time from pending_slot: {time_str}")
            else:
                logger.info(f"📝 [FLOW STEP 3] No pending_slot available")
            
            # ✅ STEP 1: Validate we have date and time
            logger.info(f"📝 [FLOW STEP 4] Checking date/time: date={date_iso}, time={time_str}")
            if not date_iso or not time_str:
                logger.error(f"❌ [FLOW STEP 4] FAILED - Missing date/time! Asking AI to clarify")
                # Clear stale pending_slot to avoid loops
                if crm_context and hasattr(crm_context, 'pending_slot'):
                    crm_context.pending_slot = None
                    logger.info(f"🧹 [FLOW STEP 4] Cleared stale pending_slot")
                # Ask AI to clarify the time
                await self._send_server_event_to_ai("need_datetime - חסרים פרטים לקביעת התור. שאל את הלקוח: לאיזה יום ושעה תרצה לקבוע?")
                return
            
            logger.info(f"✅ [FLOW STEP 4] OK - Date/time valid: {date_iso} {time_str}")
            
            # ✅ STEP 2: Check if we have customer name and phone
            # 🔥 BUILD 182: Phone priority: 1) crm_context, 2) DTMF, 3) Caller ID
            customer_phone = None
            if crm_context and crm_context.customer_phone:
                customer_phone = crm_context.customer_phone
                logger.info(f"📝 [FLOW STEP 5] Phone from crm_context: {customer_phone}")
            elif hasattr(self, 'customer_phone_dtmf') and self.customer_phone_dtmf:
                customer_phone = self.customer_phone_dtmf
                logger.info(f"📝 [FLOW STEP 5] Phone from DTMF: {customer_phone}")
            elif hasattr(self, 'phone_number') and self.phone_number:
                # 🔥 BUILD 182: Use Caller ID as fallback!
                customer_phone = self.phone_number
                logger.info(f"📝 [FLOW STEP 5] Phone from Caller ID: {customer_phone}")
            
            logger.info(f"📝 [FLOW STEP 5] Checking customer info:")
            logger.info(f"📝 [FLOW STEP 5]   - phone: {customer_phone}")
            logger.info(f"📝 [FLOW STEP 5]   - name from NLP: {customer_name}")
            
            # 🔥 FALLBACK: If NLP didn't extract name, check temp cache and crm_context
            if not customer_name:
                if crm_context and crm_context.customer_name:
                    customer_name = crm_context.customer_name
                    logger.info(f"📝 [FLOW STEP 5]   - name from crm_context: {customer_name}")
                elif hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    customer_name = self.pending_customer_name
                    logger.info(f"📝 [FLOW STEP 5]   - name from temp cache: {customer_name}")
                    # CRITICAL: Write name back to crm_context so it's persisted!
                    if crm_context:
                        crm_context.customer_name = customer_name
                        logger.info(f"📝 [FLOW STEP 5]   - hydrated temp cache → crm_context")
            
            # 🔥 BUILD 182: Check if business requires phone verification via DTMF
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(self.business_id)
            require_phone_verification = getattr(policy, 'require_phone_before_booking', False)
            logger.info(f"📝 [FLOW STEP 5.5] Business setting require_phone_before_booking: {require_phone_verification}")
            
            # 🔥 Check if all required data is complete
            logger.info(f"📝 [FLOW STEP 6] Checking if all data is complete...")
            
            # Priority 1: Name (ALWAYS ask for name first!)
            if not customer_name:
                logger.error(f"❌ [FLOW STEP 6] BLOCKED - Need name first! Sending need_name event")
                await self._send_server_event_to_ai("need_name - שאל את הלקוח: על איזה שם לרשום את התור?")
                return
            else:
                self._update_lead_capture_state('name', customer_name, source='appointment_flow')
            
            # Priority 2: Phone - ONLY ask if require_phone_before_booking is True AND no phone available
            # 🔥 BUILD 186: Ask for DTMF (keypad) only when require_phone_before_booking=True
            # Otherwise, use Caller ID automatically - no verbal phone extraction needed!
            if not customer_phone:
                if require_phone_verification:
                    logger.error(f"❌ [FLOW STEP 6] BLOCKED - Need phone (require_phone_before_booking=True)! Asking via DTMF")
                    await self._send_server_event_to_ai("need_phone_dtmf - בקש מהלקוח להקליד את מספר הטלפון שלו על המקשים ולסיים בסולמית (#).")
                    return
                else:
                    # 🔥 BUILD 182: Try to use caller ID one more time
                    if hasattr(self, 'phone_number') and self.phone_number:
                        customer_phone = self.phone_number
                        logger.info(f"📝 [FLOW STEP 6] Using Caller ID as phone: {customer_phone}")
                    else:
                        logger.warning(f"⚠️ [FLOW STEP 6] No phone available but require_phone_before_booking=False")
                        logger.warning(f"⚠️ [FLOW STEP 6] Proceeding without phone (will use empty string)")
                        customer_phone = ""
            
            if customer_phone:
                self._update_lead_capture_state('phone', customer_phone, source='appointment_flow')
            
            logger.info(f"")
            logger.info(f"✅ [FLOW STEP 6] ALL DATA COMPLETE!")
            logger.info(f"✅ [FLOW STEP 6]   - name: {customer_name}")
            logger.info(f"✅ [FLOW STEP 6]   - phone: {customer_phone}")
            logger.info(f"✅ [FLOW STEP 6]   - date: {date_iso}")
            logger.info(f"✅ [FLOW STEP 6]   - time: {time_str}")
            
            # 🛡️ BUILD 149 FIX: Set guard IMMEDIATELY when confirm action starts processing
            # This prevents barge-in from allowing re-entry into the confirm flow
            # The guard must be set BEFORE any awaits, as barge-in can happen at any time
            self.appointment_confirmed_in_session = True
            logger.info(f"🛡️ [GUARD] Set appointment_confirmed_in_session=True EARLY to prevent re-entry")
            
            # Calculate datetime
            from datetime import datetime, timedelta
            import pytz
            
            tz = pytz.timezone('Asia/Jerusalem')
            
            # Parse date and time
            target_date = datetime.fromisoformat(date_iso)
            hour, minute = map(int, time_str.split(":"))
            
            # Create start datetime
            start_dt = tz.localize(datetime(
                target_date.year, target_date.month, target_date.day,
                hour, minute, 0
            ))
            
            # 🔥 CRITICAL: Use slot_size_min from business policy (NOT hardcoded 1 hour!)
            # Note: policy already loaded at STEP 5.5
            slot_duration_min = policy.slot_size_min  # 15, 30, or 60 minutes from DB settings
            end_dt = start_dt + timedelta(minutes=slot_duration_min)
            
            logger.info(f"📝 [FLOW STEP 7] Calculated times:")
            logger.info(f"📝 [FLOW STEP 7]   - start_dt: {start_dt.isoformat()}")
            logger.info(f"📝 [FLOW STEP 7]   - duration: {slot_duration_min} minutes (from DB policy)")
            logger.info(f"📝 [FLOW STEP 7]   - end_dt: {end_dt.isoformat()}")
            
            # ✅ STEP 1: Validate slot is within business hours AND check calendar availability
            logger.info(f"📝 [FLOW STEP 8] Validating slot availability...")
            is_valid = validate_appointment_slot(self.business_id, start_dt)
            logger.info(f"📝 [FLOW STEP 8] Slot validation result: {is_valid}")
            
            if not is_valid:
                logger.error(f"❌ [FLOW STEP 8] FAILED - Slot outside business hours or taken!")
                # 🔥 Send feedback to AI
                await self._send_server_event_to_ai(f"השעה {time_str} ביום {date_iso} תפוסה או מחוץ לשעות העבודה. תציע שעה אחרת ללקוח.")
                return
            
            logger.info(f"✅ [FLOW STEP 8] OK - Slot is available!")
            
            # 🛡️ STEP 2: DB-BASED DEDUPLICATION - Check CallSession table
            appt_hash = start_dt.isoformat()
            logger.info(f"📝 [FLOW STEP 9] Checking for duplicate appointments...")
            logger.info(f"📝 [FLOW STEP 9]   - appt_hash: {appt_hash}")
            logger.info(f"📝 [FLOW STEP 9]   - call_sid: {self.call_sid}")
            
            # Check DB for duplicate
            try:
                from server.models_sql import CallSession
                app = _get_flask_app()
                with app.app_context():
                    call_session = CallSession.query.filter_by(call_sid=self.call_sid).first()
                    logger.info(f"📝 [FLOW STEP 9]   - call_session exists: {call_session is not None}")
                    
                    if call_session and call_session.last_confirmed_slot == appt_hash:
                        logger.warning(f"⚠️ [FLOW STEP 9] SKIPPED - Duplicate detected! Appointment for {appt_hash} already created")
                        return
                    
                    logger.info(f"✅ [FLOW STEP 9] OK - No duplicate found")
                    
                    # 🛡️ CRITICAL: customer_phone is guaranteed valid from previous checks
                    logger.info(f"")
                    logger.info(f"🚀 [FLOW STEP 10] ========== CREATING APPOINTMENT IN DATABASE ==========")
                    logger.info(f"🚀 [FLOW STEP 10] Parameters:")
                    logger.info(f"🚀 [FLOW STEP 10]   - business_id: {self.business_id}")
                    logger.info(f"🚀 [FLOW STEP 10]   - customer_name: {customer_name}")
                    logger.info(f"🚀 [FLOW STEP 10]   - customer_phone: {customer_phone}")
                    logger.info(f"🚀 [FLOW STEP 10]   - start_iso: {start_dt.isoformat()}")
                    logger.info(f"🚀 [FLOW STEP 10]   - end_iso: {end_dt.isoformat()}")
                    
                    # Create appointment with call summary if available
                    appt_notes = "נקבע בשיחה טלפונית"
                    if hasattr(self, 'call_summary') and self.call_summary:
                        appt_notes = f"סיכום שיחה:\n{self.call_summary}"
                    
                    # 🔥 BUILD 200: Get treatment_type from lead state or use generic default
                    # Each business defines their service types in their AI prompt
                    service_type = self.lead_capture_state.get('service_type', '')
                    treatment_type = service_type if service_type else "פגישה"  # Fallback to generic "meeting"
                    
                    result = create_appointment_from_realtime(
                        business_id=self.business_id,
                        customer_phone=customer_phone,
                        customer_name=customer_name,
                        treatment_type=treatment_type,
                        start_iso=start_dt.isoformat(),
                        end_iso=end_dt.isoformat(),
                        notes=appt_notes
                    )
                    
                    logger.info(f"🚀 [FLOW STEP 10] create_appointment_from_realtime returned: {result}")
                    
                    # 🔥 ENHANCED: Handle appointment creation result with proper error handling
                    if result and isinstance(result, dict):
                        # Check if this is an error response
                        if not result.get("ok", True):
                            error_type = result.get("error", "unknown")
                            error_msg = result.get("message", "שגיאה לא ידועה")
                            
                            logger.error(f"❌ [FLOW STEP 10] FAILED - {error_type}: {error_msg}")

                            # 🔥 CRITICAL: Send appropriate server event based on error type
                            if error_type == "need_phone":
                                logger.info(f"📞 [DTMF VERIFICATION] Requesting phone via DTMF - AI will ask user to press digits")
                                await self._send_server_event_to_ai("missing_phone_collect_via_dtmf")
                            else:
                                await self._send_server_event_to_ai(f"❌ שגיאה: {error_msg}")
                            return
                        
                        # Success - extract appointment ID
                        appt_id = result.get("appointment_id")
                    elif result and isinstance(result, int):
                        # Old format - just ID
                        appt_id = result
                    else:
                        appt_id = None
                    
                    if appt_id:
                        # Buffer appointment marker update (will commit at call end)
                        if call_session:
                            call_session.last_confirmed_slot = appt_hash
                            self.db_write_queue.append({
                                'type': 'callsession_update',
                                'call_sid': self.call_sid,
                                'updates': {'last_confirmed_slot': appt_hash}
                            })
                            logger.info(f"[DB_BUFFER] Queued appointment marker update")
                        
                        logger.info(f"")
                        logger.info(f"=" * 80)
                        logger.info(f"✅✅✅ [FLOW STEP 11] APPOINTMENT CREATED SUCCESSFULLY! ✅✅✅")
                        logger.info(f"=" * 80)
                        logger.info(f"✅ [FLOW STEP 11]   - appointment_id: {appt_id}")
                        logger.info(f"✅ [FLOW STEP 11]   - customer: {customer_name}")
                        logger.info(f"✅ [FLOW STEP 11]   - phone: {customer_phone}")
                        logger.info(f"✅ [FLOW STEP 11]   - datetime: {date_iso} {time_str}")
                        logger.info(f"=" * 80)
                        logger.info(f"")
                        
                        # 🛡️ BUILD 149 FIX: Set ALL guards BEFORE sending any message to AI
                        # This prevents race condition where NLP triggers from AI's response
                        self.appointment_confirmed_in_session = True
                        logger.info(f"🔒 [GUARD] Set appointment_confirmed_in_session=True BEFORE AI event")
                        
                        # Update CRM context with appointment ID
                        if crm_context:
                            crm_context.last_appointment_id = appt_id
                            # 🔥 CRITICAL: Set flag - NOW AI is allowed to say "התור נקבע!"
                            crm_context.has_appointment_created = True
                            logger.info(f"✅ [APPOINTMENT VERIFICATION] Created appointment #{appt_id} in DB - has_appointment_created=True")
                            logger.info(f"🔓 [GUARD] Appointment created - AI can now confirm to customer")
                            
                        # 🔥 BUILD 146: Clear pending_slot ONLY after successful appointment creation
                        if crm_context:
                            crm_context.pending_slot = None
                            logger.info(f"🧹 [CONFIRM] Cleared pending_slot after successful creation")
                        
                        # 🔥 BUILD 149 FIX: Simplified confirmation message - don't instruct AI to "notify"
                        # Just state the fact. The system prompt already tells AI what to say.
                        await self._send_server_event_to_ai(f"✅ appointment_created: {customer_name}, {date_iso}, {time_str}")
                    else:
                        logger.info(f"")
                        logger.error(f"❌❌❌ [FLOW STEP 11] FAILED TO CREATE APPOINTMENT! ❌❌❌")
                        logger.error(f"❌ [FLOW STEP 11] Result was None or had no appointment_id")
                        # 🔥 Send failure to AI
                        await self._send_server_event_to_ai("❌ שגיאה ביצירת התור. נסה שעה אחרת.")
            except Exception as e:
                logger.info(f"")
                logger.error(f"❌❌❌ [FLOW STEP 10] EXCEPTION DURING APPOINTMENT CREATION! ❌❌❌")
                logger.error(f"❌ [FLOW STEP 10] Error: {e}")
                import traceback
                traceback.print_exc()
    
    def _check_appointment_confirmation(self, ai_transcript: str):
        """
        Wrapper to call async NLP parser from sync context
        Launches async parser in separate thread to avoid event loop conflicts
        
        🔥 DEDUPLICATION: Only runs NLP once per unique conversation state
        🛡️ BUILD 149: Added guard to prevent re-entry after appointment confirmed
        """
        import threading
        import hashlib
        
        logger.debug(f"[DEBUG] _check_appointment_confirmation called with transcript: '{ai_transcript[:50] if ai_transcript else 'EMPTY'}...'")
        logger.debug(f"[DEBUG] Conversation history length: {len(self.conversation_history)}")
        
        # 🛡️ BUILD 149 FIX: Check guard FIRST - if appointment already confirmed, skip NLP entirely
        if getattr(self, 'appointment_confirmed_in_session', False):
            logger.debug(f"[NLP] GUARD ACTIVE - appointment_confirmed_in_session=True, skipping NLP")
            return
        
        # 🛡️ Also check CRM context guard
        crm_context = getattr(self, 'crm_context', None)
        if crm_context and crm_context.has_appointment_created:
            logger.debug(f"[NLP] GUARD ACTIVE - crm_context.has_appointment_created=True, skipping NLP")
            return
        
        # 🔥 CRITICAL: Create hash of conversation to prevent duplicate NLP runs
        # ⚠️ FIX #1: Remove timestamps from hash - only text matters!
        # ⚠️ FIX #2: Hash ONLY user messages (not AI/system) - prevents re-triggering when AI responds!
        user_messages_only = [
            msg.get("text", "") 
            for msg in self.conversation_history[-10:]  # Last 10 messages
            if msg.get("speaker") == "user"
        ]
        logger.debug(f"[DEBUG] User messages for hash: {user_messages_only}")
        conversation_str = json.dumps(user_messages_only, sort_keys=True)
        current_hash = hashlib.md5(conversation_str.encode()).hexdigest()
        logger.debug(f"[DEBUG] Current conversation hash: {current_hash[:8]}...")
        
        # Skip if already processed this exact conversation state (with 30s TTL)
        should_process = False
        with self.nlp_processing_lock:
            now = time.time()
            
            # 🛡️ BUILD 149 FIX: Check if another NLP thread is still running
            if self.nlp_is_processing:
                logger.debug(f"[NLP] BLOCKED - Another NLP thread is still processing")
                return
            
            # Check if we should process (new hash OR expired TTL)
            if self.last_nlp_processed_hash is None:
                # First run
                logger.debug(f"[DEBUG] First NLP run - processing")
                should_process = True
            elif current_hash != self.last_nlp_processed_hash:
                # Different hash - always process
                logger.debug(f"[DEBUG] Hash changed ({self.last_nlp_processed_hash[:8] if self.last_nlp_processed_hash else 'None'} → {current_hash[:8]}) - processing")
                should_process = True
            elif (now - self.last_nlp_hash_timestamp) >= 30:
                # Same hash but TTL expired - reprocess
                logger.debug(f"[NLP] TTL expired - reprocessing same hash")
                should_process = True
            else:
                # Same hash within TTL - skip
                hash_age = now - self.last_nlp_hash_timestamp
                logger.debug(f"[NLP] Skipping duplicate (hash={current_hash[:8]}..., age={hash_age:.1f}s)")
                return
            
            # 🛡️ Mark as processing BEFORE releasing lock to prevent race
            if should_process:
                self.nlp_is_processing = True
        
        if not should_process:
            logger.debug(f"[DEBUG] should_process=False - returning early")
            return
        
        logger.debug(f"[NLP] WILL PROCESS new conversation state (hash={current_hash[:8]}...)")
        logger.debug(f"[DEBUG] CRM context exists: {hasattr(self, 'crm_context') and self.crm_context is not None}")
        if hasattr(self, 'crm_context') and self.crm_context:
            logger.debug(f"[DEBUG] CRM data - name: '{self.crm_context.customer_name}', phone: '{self.crm_context.customer_phone}'")
        
        def run_in_thread():
            """Run async parser in dedicated thread with its own event loop"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._check_appointment_confirmation_async())
                with self.nlp_processing_lock:
                    self.last_nlp_processed_hash = current_hash
                    self.last_nlp_hash_timestamp = time.time()
            except Exception as e:
                logger.error(f"[NLP] Error: {e}")
            finally:
                loop.close()
                with self.nlp_processing_lock:
                    self.nlp_is_processing = False
        
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
    
    def _realtime_audio_out_loop(self):
        """⚡ BUILD 168.2: Optimized audio bridge - minimal logging
        
        🔥 PART C DEBUG: Added logging to trace tx=0 issues
        🔥 FIX #1: Continue draining queue even after stop flag
        """
        if not hasattr(self, 'realtime_tx_frames'):
            self.realtime_tx_frames = 0
        if not hasattr(self, 'realtime_tx_bytes'):
            self.realtime_tx_bytes = 0
        
        # 🔥 PART C: Track first frame for diagnostics
        _first_frame_logged = False
        _frames_skipped_no_stream_sid = 0
        
        # 🎯 PROBE 4: Queue Flow Probe - Track enqueue rate every 1 second
        _enqueue_rate_counter = 0
        _last_enqueue_rate_time = time.monotonic()
        
        TWILIO_FRAME_SIZE = 160  # 20ms at 8kHz μ-law
        audio_buffer = b''  # Rolling buffer for incomplete frames
        
        _orig_print(f"🔊 [AUDIO_OUT_LOOP] Started - waiting for OpenAI audio", flush=True)
        
        # 🔥 FIX #1: Continue until queue is empty OR sentinel received
        # 🔥 SESSION LIFECYCLE: Also check self.closed to exit immediately on session close
        # Don't exit just because stop_flag is set - drain the queue first!
        while (not self.realtime_stop_flag or not self.realtime_audio_out_queue.empty()) and not self.closed:
            # 🎯 PROBE 4: Queue Flow Probe - Log enqueue rate every 1 second
            now_mono = time.monotonic()
            if now_mono - _last_enqueue_rate_time >= 1.0:
                rx_qsize = self.realtime_audio_out_queue.qsize()
                if DEBUG_TX:
                    _orig_print(f"[ENQ_RATE] frames_per_sec={_enqueue_rate_counter}, rx_qsize={rx_qsize}", flush=True)
                _enqueue_rate_counter = 0
                _last_enqueue_rate_time = now_mono
            
            try:
                audio_b64 = self.realtime_audio_out_queue.get(timeout=0.1)
                if audio_b64 is None:
                    _orig_print(f"🔊 [AUDIO_OUT_LOOP] Received None sentinel - exiting loop (frames_enqueued={self.realtime_tx_frames})", flush=True)
                    break
                
                # 🎯 PROBE 4: Count frames dequeued from realtime_audio_out_queue
                _enqueue_rate_counter += 1
                
                import base64
                chunk_bytes = base64.b64decode(audio_b64)
                self.realtime_tx_bytes += len(chunk_bytes)
                
                # 🔥 PART C: Log first frame and stream_sid state
                if not _first_frame_logged:
                    _orig_print(f"🔊 [AUDIO_OUT_LOOP] FIRST_CHUNK received! bytes={len(chunk_bytes)}, stream_sid={self.stream_sid}", flush=True)
                    _first_frame_logged = True
                
                # 🔥 RECORDING TRIGGER: Start recording when first audio sent (from TX loop flag)
                # This is done here in background thread, NOT in TX loop itself
                if getattr(self, '_first_audio_sent', False) and not getattr(self, '_recording_started', False):
                    self._recording_started = True
                    _orig_print(f"✅ [AUDIO_OUT_LOOP] Starting recording (triggered by FIRST_AUDIO_SENT flag)", flush=True)
                    threading.Thread(target=self._start_call_recording, daemon=True).start()
                
                if not self.stream_sid:
                    _frames_skipped_no_stream_sid += 1
                    if _frames_skipped_no_stream_sid <= 3 or _frames_skipped_no_stream_sid % 50 == 0:
                        _orig_print(f"⚠️ [AUDIO_OUT_LOOP] Skipping frame - no stream_sid (skipped={_frames_skipped_no_stream_sid})", flush=True)
                    continue
                
                audio_buffer += chunk_bytes
                
                while len(audio_buffer) >= TWILIO_FRAME_SIZE:
                    frame_bytes = audio_buffer[:TWILIO_FRAME_SIZE]
                    audio_buffer = audio_buffer[TWILIO_FRAME_SIZE:]
                    
                    frame_b64 = base64.b64encode(frame_bytes).decode('utf-8')
                    twilio_frame = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": frame_b64}
                    }
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 AUDIO BACKPRESSURE FIX: Pacing + Blocking put with timeout
                    # This prevents mid-sentence audio cutting by waiting instead of dropping frames
                    # ═══════════════════════════════════════════════════════════════════════
                    # Get queue state once to avoid redundant system calls
                    queue_size = self.tx_q.qsize()
                    queue_maxsize = self.tx_q.maxsize  # 400 frames = 8s
                    
                    # Thresholds for backpressure control
                    PACING_THRESHOLD = 0.6  # Start pacing at 60% full
                    BACKPRESSURE_THRESHOLD = 0.8  # Log warnings at 80% full
                    
                    pacing_threshold = int(queue_maxsize * PACING_THRESHOLD)  # 240 frames
                    backpressure_threshold = int(queue_maxsize * BACKPRESSURE_THRESHOLD)  # 320 frames
                    
                    # Apply pacing when queue ≥60% full to slow production to TX rate
                    if queue_size >= pacing_threshold:
                        time.sleep(0.02)  # 20ms = match TX loop pace (50 FPS)
                    
                    # Log when queue is getting high (throttled)
                    if queue_size >= backpressure_threshold:
                        now = time.time()
                        if not hasattr(self, '_last_backpressure_log') or now - self._last_backpressure_log > 5:
                            logger.info(f"⏸️ [BACKPRESSURE] Queue high ({queue_size}/{queue_maxsize}), applying backpressure (blocking put)")
                            self._last_backpressure_log = now
                    
                    # 🔥 FIX: Use blocking put() with timeout instead of put_nowait()
                    # This applies true backpressure - we wait for TX to catch up instead of dropping frames
                    try:
                        self.tx_q.put(twilio_frame, timeout=0.5)  # Wait up to 500ms for space
                        self.realtime_tx_frames += 1
                    except queue.Full:
                        # Queue is STILL full after 500ms timeout - this is exceptional
                        # Only happens if TX thread is stalled/dead
                        now = time.time()
                        if not hasattr(self, '_last_full_error') or now - self._last_full_error > 5:
                            logger.warning(f"⚠️ [AUDIO BACKPRESSURE TIMEOUT] Queue full for >500ms ({queue_size}/{queue_maxsize}) - TX thread may be stalled!")
                            self._last_full_error = now
                        # Drop this ONE frame only as emergency measure
                        pass
                    
            except queue.Empty:
                # 🔥 FIX #1: If stop flag is set and queue is empty, we're done draining
                if self.realtime_stop_flag:
                    _orig_print(f"🔊 [AUDIO_OUT_LOOP] Stop flag set, queue empty - drain complete", flush=True)
                    break
                continue
            except Exception as e:
                logger.error(f"[AUDIO] Bridge error: {e}")
                break
        
        # 🔥 FIX #1: Log drain completion
        remaining = self.realtime_audio_out_queue.qsize()
        _orig_print(f"🔊 [AUDIO_OUT_LOOP] Exiting - frames_enqueued={self.realtime_tx_frames}, remaining_in_queue={remaining}", flush=True)

    def _calculate_and_log_cost(self):
        """💰 Calculate and log call cost - called at end of every call"""
        try:
            call_duration = time.time() - getattr(self, 'call_start_time', time.time())
            
            # Get chunk counts
            audio_in_chunks = getattr(self, 'realtime_audio_in_chunks', 0)
            audio_out_chunks = getattr(self, 'realtime_audio_out_chunks', 0)
            
            # Precise calculation: chunks / 50 chunks/sec / 60 sec/min
            audio_in_minutes_exact = audio_in_chunks / 50.0 / 60.0 if audio_in_chunks > 0 else 0.0
            audio_out_minutes_exact = audio_out_chunks / 50.0 / 60.0 if audio_out_chunks > 0 else 0.0
            
            # Pricing lookup table
            REALTIME_PRICING = {
                "gpt-4o-realtime-preview": {"input": 0.06, "output": 0.24},
                "gpt-4o-mini-realtime-preview": {"input": 0.01, "output": 0.02},
                "gpt-realtime": {"input": 0.019, "output": 0.038},  # New 2025 model
            }
            
            # Get pricing (fallback to standard if unknown model)
            pricing = REALTIME_PRICING.get(OPENAI_REALTIME_MODEL, REALTIME_PRICING["gpt-4o-realtime-preview"])
            cost_per_min_in = pricing["input"]
            cost_per_min_out = pricing["output"]
            
            # Calculate cost
            cost_in = audio_in_minutes_exact * cost_per_min_in
            cost_out = audio_out_minutes_exact * cost_per_min_out
            total_cost = cost_in + cost_out
            
            # Convert to NIS (₪) - approximate rate
            total_cost_nis = total_cost * 3.7
            
            # 🔥 BUILD 338: Get response.create count for cost analysis
            response_create_count = getattr(self, '_response_create_count', 0)
            
            # ⚡ BUILD 168.2: Compact cost log (single line)
            # 🔥 BUILD 338: Added response.create count for cost debugging
            logger.info(f"[COST] {call_duration:.0f}s ${total_cost:.4f} (₪{total_cost_nis:.2f}) | response.create={response_create_count}")
            logger.debug(f"[COST SUMMARY] Duration: {call_duration:.0f}s | Cost: ${total_cost:.4f} (₪{total_cost_nis:.2f}) | response.create: {response_create_count}")
            
            # 🚨 BUILD 338: WARN if too many response.create calls (cost indicator)
            if response_create_count > 5:
                logger.debug(f"[COST WARNING] High response.create count: {response_create_count} (target: ≤5)")
            
            return total_cost
            
        except Exception as e:
            logger.error(f"[COST] Error calculating cost: {e}")
            return 0.0
    
    def close_session(self, reason: str):
        """
        🔥 SESSION LIFECYCLE GUARD: Atomic session close - runs ONCE only
        
        This is the SINGLE SOURCE OF TRUTH for session cleanup.
        All close triggers must call this method.
        
        Args:
            reason: Why the session is closing (e.g., "stop_event", "ws_disconnect", "call_status_completed")
        """
        with self.close_lock:
            if self.closed:
                # Already closed - this is idempotent
                if DEBUG:
                    logger.debug(f"[SESSION_CLOSE] Already closed (reason={self.close_reason}), ignoring duplicate close (trigger={reason})")
                else:
                    _orig_print(f"🔒 [SESSION_CLOSE] Already closed (reason={self.close_reason}), ignoring duplicate close (trigger={reason})", flush=True)
                return
            
            # Mark as closed FIRST to prevent re-entry
            self.closed = True
            self.close_reason = reason
            if DEBUG:
                logger.info(f"[SESSION_CLOSE] Closing session (reason={reason}, call_sid={self.call_sid}, stream_sid={self.stream_sid})")
            else:
                _orig_print(f"🔒 [SESSION_CLOSE] Closing session (reason={reason}, call_sid={self.call_sid}, stream_sid={self.stream_sid})", flush=True)
        
        # From here on, we're guaranteed to run only once
        
        # 🔥 VERIFICATION: Wrap in try/finally to ensure cleanup even on exception
        try:
            # STEP 0: Clear all state flags to prevent leakage between calls
            if not DEBUG:
                _orig_print(f"   [0/8] Clearing state flags to prevent leakage...", flush=True)
            try:
                # Clear speaking state
                if hasattr(self, 'is_ai_speaking_event'):
                    self.is_ai_speaking_event.clear()
                self.speaking = False
                self.active_response_id = None
                self.active_response_status = None  # 🔥 IDEMPOTENT CANCEL: Reset on session close
                self.cancel_in_flight = False  # 🔥 IDEMPOTENT CANCEL: Reset on session close
                self._last_flushed_response_id = None  # 🔥 IDEMPOTENT CANCEL: Reset on session close
                self._cancel_sent_for_response_ids.clear()  # 🔥 IDEMPOTENT CANCEL: Clear sent cancels on session close
                
                # Clear race condition tracking
                if hasattr(self, 'audio_done_by_response_id'):
                    self.audio_done_by_response_id.clear()
                
                # Clear hangup state
                self.pending_hangup = False
                self.pending_hangup_response_id = None
                self.pending_hangup_reason = None
                self.hangup_executed = False
                
                # Clear barge-in state
                self.barge_in_active = False
                self._barge_in_started_ts = None
                
                # Clear thread-started flags (per-instance)
                if hasattr(self, '_realtime_audio_out_thread_started'):
                    delattr(self, '_realtime_audio_out_thread_started')
                
                # Clear user speaking state
                self.user_speaking = False
                self._candidate_user_speaking = False
                self._utterance_start_ts = None
                
                # 🔥 SILENCE WATCHDOG: Stop watchdog on session close
                self._silence_watchdog_running = False
                if self._silence_watchdog_task is not None and not self._silence_watchdog_task.done():
                    self._silence_watchdog_task.cancel()
                    _orig_print(f"   🔒 Silence watchdog task cancelled", flush=True)
                
                # Clear response tracking
                self.has_pending_ai_response = False
                self.response_pending_event.clear()
                
                _orig_print(f"   ✅ State flags cleared", flush=True)
            except Exception as e:
                _orig_print(f"   ⚠️ Error clearing state flags: {e}", flush=True)
            
            # STEP 1: Set stop flags for all loops
            if not DEBUG:
                _orig_print(f"   [1/8] Setting stop flags...", flush=True)
            self.realtime_stop_flag = True
            if hasattr(self, 'tx_running'):
                self.tx_running = False
            
            # STEP 2: Signal queues to stop (sentinel values)
            if not DEBUG:
                _orig_print(f"   [2/8] Sending stop signals to queues...", flush=True)
            if hasattr(self, 'realtime_audio_in_queue') and self.realtime_audio_in_queue:
                try:
                    self.realtime_audio_in_queue.put_nowait(None)
                except:
                    pass
            if hasattr(self, 'realtime_audio_out_queue') and self.realtime_audio_out_queue:
                try:
                    self.realtime_audio_out_queue.put_nowait(None)
                except:
                    pass
            
            # STEP 3: Stop timers/watchdogs
            if not DEBUG:
                _orig_print(f"   [3/8] Stopping timers and watchdogs...", flush=True)
            # (Add any timer cleanup here if needed)
            
            # STEP 4: Close OpenAI connection
            if not DEBUG:
                _orig_print(f"   [4/8] Closing OpenAI connection...", flush=True)
            # The realtime_stop_flag will make the async tasks exit naturally
            
            # STEP 5: Wait for TX thread to finish draining
            # 🔥 VERIFICATION #2: Only drain politely if AI initiated hangup
            # If Twilio closed (call_status/stream_ended), clear queues immediately
            ai_initiated = 'twilio' not in reason and 'call_status' not in reason and 'stream_ended' not in reason
            
            if ai_initiated:
                if not DEBUG:
                    _orig_print(f"   [5/8] AI-initiated close - waiting for TX thread to drain politely...", flush=True)
                if hasattr(self, 'tx_thread') and self.tx_thread.is_alive():
                    try:
                        self.tx_thread.join(timeout=2.0)  # Give it 2s to drain
                        if self.tx_thread.is_alive():
                            _orig_print(f"   ⚠️ TX thread still alive after 2s timeout", flush=True)
                        else:
                            _orig_print(f"   ✅ TX thread drained and stopped", flush=True)
                    except:
                        pass
            else:
                # Twilio closed - clear queues immediately, no drain
                if not DEBUG:
                    _orig_print(f"   [5/8] Twilio-initiated close - clearing queues immediately (no drain)...", flush=True)
                if hasattr(self, 'tx_q'):
                    cleared = 0
                    while not self.tx_q.empty():
                        try:
                            self.tx_q.get_nowait()
                            cleared += 1
                        except:
                            break
                    if cleared > 0:
                        _orig_print(f"   🧹 Cleared {cleared} frames from TX queue", flush=True)
                if hasattr(self, 'realtime_audio_out_queue'):
                    cleared = 0
                    while not self.realtime_audio_out_queue.empty():
                        try:
                            self.realtime_audio_out_queue.get_nowait()
                            cleared += 1
                        except:
                            break
                    if cleared > 0:
                        _orig_print(f"   🧹 Cleared {cleared} frames from audio out queue", flush=True)
            
            # STEP 5.5: Join background threads (realtime_audio_out_loop, etc.)
            if not DEBUG:
                _orig_print(f"   [5.5/8] Joining background threads...", flush=True)
            if hasattr(self, 'background_threads') and self.background_threads:
                for thread in self.background_threads:
                    if thread and thread.is_alive():
                        try:
                            thread.join(timeout=1.0)
                            if thread.is_alive():
                                _orig_print(f"   ⚠️ Background thread {thread.name if hasattr(thread, 'name') else 'unnamed'} still alive after timeout", flush=True)
                        except Exception as e:
                            _orig_print(f"   ⚠️ Error joining background thread: {e}", flush=True)
                _orig_print(f"   ✅ Background threads cleanup complete", flush=True)
            
            # STEP 6: Close Twilio WebSocket
            if not DEBUG:
                _orig_print(f"   [6/8] Closing Twilio WebSocket...", flush=True)
            try:
                if hasattr(self.ws, 'close') and not self._ws_closed:
                    # 🔥 FIX: Check if websocket is still open before closing
                    # For Starlette/FastAPI, check client_state if available
                    can_close = True
                    if hasattr(self.ws, 'client_state'):
                        from starlette.websockets import WebSocketState
                        if self.ws.client_state != WebSocketState.CONNECTED:
                            can_close = False
                            if DEBUG:
                                _orig_print(f"   [DEBUG] WebSocket already disconnected (state={self.ws.client_state})", flush=True)
                    
                    if can_close:
                        self.ws.close()
                        self._ws_closed = True
                        _orig_print(f"   ✅ WebSocket closed", flush=True)
            except Exception as e:
                error_msg = str(e).lower()
                # 🔥 FIX: Expected conditions when client disconnects - log as DEBUG only
                # Be specific: check for exact ASGI message patterns, not just "closed"
                if 'websocket.close' in error_msg or 'asgi message' in error_msg or 'already closed' in error_msg:
                    logger.debug(f"   [DEBUG] WebSocket already closed: {e}")
                else:
                    _orig_print(f"   ⚠️ Error closing websocket: {e}", flush=True)
        
        finally:
            # 🔥 PERFORMANCE: Flush buffered DB writes before final cleanup
            self.in_live_call = False
            logger.info(f"🔓 [DB_GUARD] Call ended - DB access allowed for cleanup")
            self._flush_db_writes()
            
            # STEP 7: Update call_status in database immediately
            # 🔥 NEW FIX: This ensures active call detection works correctly
            if not DEBUG:
                _orig_print(f"   [7/8] Updating call_status in database...", flush=True)
            if self.call_sid:
                try:
                    # Update call_status to 'ended' immediately when session closes
                    # This fixes the active call detection issue
                    from server.models_sql import CallLog
                    from server.db import db
                    app = _get_flask_app()
                    with app.app_context():
                        call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if call_log:
                            # Update both status fields for proper detection
                            if call_log.call_status not in ['completed', 'busy', 'no-answer', 'canceled', 'failed']:
                                call_log.call_status = 'ended'
                                _orig_print(f"   ✅ Updated call_status='ended' for {self.call_sid}", flush=True)
                            if call_log.status in ['initiated', 'ringing', 'in-progress', 'queued', 'in_progress']:
                                call_log.status = 'ended'
                                _orig_print(f"   ✅ Updated status='ended' for {self.call_sid}", flush=True)
                            db.session.commit()
                            _orig_print(f"   ✅ Call status updated in database", flush=True)
                        else:
                            _orig_print(f"   ⚠️ No CallLog found for {self.call_sid}", flush=True)
                except Exception as e:
                    _orig_print(f"   ⚠️ Error updating call_status: {e}", flush=True)
            
            # STEP 8: Unregister session from registry - ALWAYS runs even on exception
            if not DEBUG:
                _orig_print(f"   [8/8] Unregistering session and handler...", flush=True)
            if self.call_sid:
                try:
                    _close_session(self.call_sid)
                except Exception as e:
                    _orig_print(f"   ⚠️ Error unregistering session: {e}", flush=True)
                try:
                    _unregister_handler(self.call_sid)
                except Exception as e:
                    _orig_print(f"   ⚠️ Error unregistering handler: {e}", flush=True)
                _orig_print(f"   ✅ Session and handler unregistered for call_sid={self.call_sid}", flush=True)
            
            # STEP 9: Final state verification
            if not DEBUG:
                _orig_print(f"   [9/9] Final state verification...", flush=True)
            is_speaking = self.is_ai_speaking_event.is_set() if hasattr(self, 'is_ai_speaking_event') else False
            if not DEBUG:
                _orig_print(f"   is_ai_speaking={is_speaking}", flush=True)
                _orig_print(f"   active_response_id={getattr(self, 'active_response_id', None)}", flush=True)
                _orig_print(f"   user_speaking={getattr(self, 'user_speaking', False)}", flush=True)
                _orig_print(f"   barge_in_active={getattr(self, 'barge_in_active', False)}", flush=True)
            
            if DEBUG:
                logger.info(f"[SESSION_CLOSE] Complete - session fully cleaned up (reason={reason})")
            else:
                _orig_print(f"✅ [SESSION_CLOSE] Complete - session fully cleaned up (reason={reason})", flush=True)
                _orig_print(f"🔒 [SHUTDOWN_VERIFICATION] After this point, NO MORE logs should appear for:", flush=True)
                _orig_print(f"   ❌ BARGE-IN DEBUG / BARGE-IN CONFIRM", flush=True)
                _orig_print(f"   ❌ WS_KEEPALIVE / TX_HEARTBEAT", flush=True)
                _orig_print(f"   ❌ SILENCE Warning / SILENCE Monitor", flush=True)
                _orig_print(f"   ❌ VAD State / Speech started/stopped", flush=True)
                _orig_print(f"   ❌ Any audio processing logs", flush=True)
                _orig_print(f"   ✅ WS_DONE and final cleanup logs are OK", flush=True)
    
    def run(self):
        """⚡ BUILD 168.2: Streamlined main loop - minimal logging
        
        🔥 REALTIME STABILITY: Added timeouts and fallback handling
        """
        import json
        
        self.call_start_time = time.time()
        self.rx_frames = 0
        self.tx_frames = 0
        
        # ═══════════════════════════════════════════════════════════════════════════
        # 🎯 [T0] WS_START - Mark WebSocket open time for timeout calculations
        # ═══════════════════════════════════════════════════════════════════════════
        self._ws_open_ts = time.time()
        _orig_print(f"🎯 [T0] WS_START call_sid=pending ws_open_ts={self._ws_open_ts:.3f}", flush=True)
        
        # 🔥 CRITICAL: Unconditional logs at the very top (always printed!)
        _orig_print(f"🔵 [REALTIME] MediaStreamHandler.run() ENTERED - waiting for START event...", flush=True)
        logger.debug("[REALTIME] MediaStreamHandler.run() ENTERED - waiting for START event")
        logger.debug(f"[REALTIME] USE_REALTIME_API={USE_REALTIME_API}, websocket_type={type(self.ws)}")
        
        # 🔥 REALTIME STABILITY: Track if START event was received
        _start_event_received = False
        
        try:
            while True:
                # 🔥 BUILD 331: Check if hard limit was exceeded - exit immediately
                if self._limit_exceeded:
                    logger.info(f"🛑 [BUILD 331] LIMIT_EXCEEDED flag detected in main loop - exiting immediately")
                    break
                
                # 🔥 CRITICAL FIX: Check if call ended externally (call_status webhook)
                # This prevents WebSocket from staying open after call completes
                if self.call_sid:
                    session = stream_registry.get(self.call_sid)
                    if session and session.get('ended'):
                        end_reason = session.get('end_reason', 'external_signal')
                        logger.info(f"🛑 [CALL_END] Call ended externally ({end_reason}) - closing WebSocket immediately")
                        self.hangup_triggered = True
                        self.call_state = CallState.ENDED
                        break
                
                # COMPATIBILITY: Handle both EventLet and Flask-Sock WebSocket APIs
                raw = None
                try:
                    # Simplified WebSocket handling - no spam logs
                    ws_type = str(type(self.ws))
                    
                    # RFC6455WebSocket-specific handling (EventLet)
                    if 'RFC6455WebSocket' in ws_type:
                        # EventLet RFC6455WebSocket uses wait() method
                        raw = self.ws.wait()
                        # רק ספירה בלי spam
                        self.rx_frames += 1
                    else:
                        # Standard WebSocket APIs
                        if hasattr(self.ws, 'receive'):
                            raw = self.ws.receive()
                        elif hasattr(self.ws, 'recv'):
                            raw = self.ws.recv()
                        elif hasattr(self.ws, 'read_message'):
                            raw = self.ws.read_message()
                        elif hasattr(self.ws, 'receive_data'):
                            raw = self.ws.receive_data()
                        elif hasattr(self.ws, 'read'):
                            raw = self.ws.read()
                        else:
                            logger.warning(f"⚠️ Unknown WebSocket type: {type(self.ws)}, available methods: {[m for m in dir(self.ws) if not m.startswith('_')]}")
                            raise Exception(f"No compatible receive method found for {type(self.ws)}")
                        
                    if raw is None or raw == '':
                        logger.info("📞 WebSocket connection closed normally")
                        break
                    
                    # 🔥 BUILD 331: Check limit flag after receiving - exit if limit exceeded
                    if self._limit_exceeded:
                        logger.info(f"🛑 [BUILD 331] LIMIT_EXCEEDED after receive - exiting main loop")
                        break
                        
                    # Handle both string and bytes
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8')
                        
                    evt = json.loads(raw)
                    et = evt.get("event")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"⚠️ Invalid JSON received: {str(raw)[:100] if raw else 'None'}... Error: {e}")
                    continue
                except Exception as e:
                    # 🔥 BUILD 331: Check limit flag on exception - exit if limit exceeded
                    if self._limit_exceeded:
                        logger.error(f"🛑 [BUILD 331] LIMIT_EXCEEDED during exception - exiting main loop")
                        break
                    logger.error(f"⚠️ WebSocket receive error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Try to continue, might be temporary - don't crash the connection
                    continue

                # ═══════════════════════════════════════════════════════════════════════
                # 🔥 FIX #1: IMPROVED START TIMEOUT HANDLING - Don't break too early!
                # ═══════════════════════════════════════════════════════════════════════
                # Strategy: Warn at timeout, but only break after 2x timeout (5 seconds total)
                # This handles cases where START is delayed but arrives soon after
                if not _start_event_received and et != "start":
                    time_since_open = time.time() - self._ws_open_ts
                    
                    # First timeout: Log warning but CONTINUE waiting
                    if time_since_open > self._twilio_start_timeout_sec and not hasattr(self, '_start_timeout_warning_logged'):
                        duration_ms = int(time_since_open * 1000)
                        _orig_print(f"⚠️ [REALTIME] SLOW_START_EVENT - no START after {duration_ms}ms (continuing to wait...)", flush=True)
                        logger.warning(f"[REALTIME] SLOW_START_EVENT - WebSocket open for {duration_ms}ms without START event (continuing)")
                        self._start_timeout_warning_logged = True
                    
                    # Hard timeout: Only break if START really never arrives (2x timeout = 5s)
                    if time_since_open > (self._twilio_start_timeout_sec * 2.0):
                        duration_ms = int(time_since_open * 1000)
                        _orig_print(f"❌ [REALTIME] NO_START_EVENT_FROM_TWILIO (call_sid=pending, duration={duration_ms}ms) - giving up", flush=True)
                        logger.warning(f"[REALTIME] NO_START_EVENT_FROM_TWILIO - WebSocket open for {duration_ms}ms without START event - giving up")
                        
                        # Mark realtime as failed
                        self.realtime_failed = True
                        self._realtime_failure_reason = "NO_START_EVENT"
                        
                        # Log metrics and break
                        logger.debug(f"[METRICS] REALTIME_TIMINGS: openai_connect_ms=0, first_greeting_audio_ms=0, realtime_failed=True, reason=NO_START_EVENT")
                        _orig_print(f"❌ [REALTIME_FALLBACK] Call pending handled without realtime (reason=NO_START_EVENT_FROM_TWILIO)", flush=True)
                        break

                if et == "start":
                    # 🔥 REALTIME STABILITY: Mark START event as received
                    _start_event_received = True
                    start_event_ts = time.time()
                    start_delay_ms = int((start_event_ts - self._ws_open_ts) * 1000)
                    
                    # 🔥 BUILD 169: Generate unique session ID for logging
                    import uuid
                    self._call_session_id = f"SES-{uuid.uuid4().hex[:8]}"
                    
                    # 🔥 CRITICAL: Unconditional logs - Force print to bypass DEBUG override
                    _orig_print(f"🎯 [REALTIME] START EVENT RECEIVED! session={self._call_session_id} (delay={start_delay_ms}ms from WS open)", flush=True)
                    logger.debug(f"[REALTIME] [{self._call_session_id}] START EVENT RECEIVED - entering start handler")
                    logger.debug(f"[REALTIME] [{self._call_session_id}] Event data keys: {list(evt.keys())}")
                    
                    # תמיכה בשני פורמטים: Twilio אמיתי ובדיקות
                    if "start" in evt:
                        # Twilio format: {"event": "start", "start": {"streamSid": "...", "callSid": "..."}}
                        self.stream_sid = evt["start"]["streamSid"]
                        self.call_sid = (
                            evt["start"].get("callSid")
                            or (evt["start"].get("customParameters") or {}).get("CallSid")
                            or (evt["start"].get("customParameters") or {}).get("call_sid")
                        )
                        
                        # ✅ זיהוי מספרי טלפון מ-customParameters
                        custom_params = evt["start"].get("customParameters", {})
                        self.phone_number = (
                            custom_params.get("From") or
                            custom_params.get("CallFrom") or  
                            custom_params.get("from") or
                            custom_params.get("phone_number")
                        )
                        # ✅ CRITICAL FIX: שמירת to_number למזהה עסק
                        self.to_number = (
                            evt["start"].get("to") or  # ✅ Twilio sends 'to' at start level
                            custom_params.get("To") or
                            custom_params.get("Called") or
                            custom_params.get("to") or
                            custom_params.get("called")
                        )
                        
                        # 🔥 BUILD 174: Outbound call parameters
                        # ⚠️ CRITICAL: call_direction is set ONCE at start and NEVER changed
                        # 🔥 HARD LOCK: Prevent any attempt to change direction after initial set
                        incoming_direction = custom_params.get("direction", "inbound")
                        
                        # Check if direction was already set (should never happen, but guard against it)
                        if hasattr(self, 'call_direction') and self.call_direction:
                            if self.call_direction != incoming_direction:
                                # 🔥 CRITICAL ERROR: Attempt to change direction after it was set
                                logger.error(f"❌ [CALL_DIRECTION_LOCK] ERROR: Attempt to change direction!")
                                logger.info(f"   Current: {self.call_direction}, Attempted: {incoming_direction}")
                                logger.info(f"   ⛔ BLOCKED - keeping original direction: {self.call_direction}")
                                _orig_print(f"[ERROR] CALL_DIRECTION_CHANGE_BLOCKED call_sid={self.call_sid[:8]}... current={self.call_direction} attempted={incoming_direction}", flush=True)
                            else:
                                logger.info(f"✅ [CALL_DIRECTION_LOCK] Direction already set to {self.call_direction} (no change)")
                        else:
                            # First time setting direction - this is the ONLY allowed assignment
                            self.call_direction = incoming_direction
                            logger.info(f"🔒 [CALL_DIRECTION_SET] Locked to: {self.call_direction} (IMMUTABLE)")
                            _orig_print(f"[CALL_DIRECTION_SET] call_sid={self.call_sid[:8]}... direction={self.call_direction} locked=True", flush=True)
                        
                        self.outbound_lead_id = custom_params.get("lead_id")
                        self.outbound_lead_name = custom_params.get("lead_name")
                        self.outbound_template_id = custom_params.get("template_id")
                        self.outbound_business_id = custom_params.get("business_id")  # 🔒 SECURITY: Explicit business_id for outbound
                        self.outbound_business_name = custom_params.get("business_name")
                        
                        # 🔥 CRITICAL DEBUG: Log all outbound parameters to verify they arrive
                        # This proves whether lead_id/phone actually reach media_ws_ai.py
                        logger.info(f"📞 [OUTBOUND_PARAMS] lead_id_raw={self.outbound_lead_id}, phone={self.phone_number}, call_sid={self.call_sid[:8] if self.call_sid else 'N/A'}...")
                        logger.info(f"[OUTBOUND_PARAMS] lead_id={self.outbound_lead_id} phone={self.phone_number} call_sid={self.call_sid}")
                        _orig_print(f"[OUTBOUND_PARAMS] lead_id_raw={self.outbound_lead_id} phone={self.phone_number} call_sid={self.call_sid[:8] if self.call_sid else 'N/A'}...", flush=True)
                        
                        # 🔥 DEBUG: Log outbound lead name explicitly
                        if self.outbound_lead_name:
                            logger.info(f"✅ [OUTBOUND] Lead name received: '{self.outbound_lead_name}'")
                        else:
                            logger.warning(f"⚠️ [OUTBOUND] No lead_name in customParameters!")
                        
                        # 🔥 OPTIMIZATION: Pre-load outbound greeting to avoid DB query in async loop
                        if self.call_direction == "outbound" and self.outbound_template_id and self.outbound_lead_name:
                            try:
                                from server.models_sql import OutboundTemplate
                                template = OutboundTemplate.query.get(self.outbound_template_id)
                                if template and template.greeting_template:
                                    biz_name = self.outbound_business_name or "העסק"
                                    self.outbound_greeting_text = template.greeting_template.replace("{{lead_name}}", self.outbound_lead_name).replace("{{business_name}}", biz_name)
                                    logger.info(f"✅ [OUTBOUND] Pre-loaded greeting: '{self.outbound_greeting_text[:50]}...'")
                            except Exception as e:
                                logger.error(f"⚠️ [OUTBOUND] Failed to pre-load greeting: {e}")
                        
                        # 🔍 DEBUG: Log phone numbers and outbound params
                        logger.info(f"\n📞 START EVENT (customParameters path):")
                        logger.info(f"   customParams.From: {custom_params.get('From')}")
                        logger.info(f"   customParams.CallFrom: {custom_params.get('CallFrom')}")
                        logger.info(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        logger.info(f"   ✅ self.to_number set to: '{self.to_number}'")
                        if self.call_direction == "outbound":
                            logger.info(f"   📤 OUTBOUND CALL: lead={self.outbound_lead_name}, template={self.outbound_template_id}")
                        
                        # 🎯 DYNAMIC LEAD STATE: Add caller phone to lead capture state
                        if self.phone_number:
                            self._update_lead_capture_state('phone', self.phone_number)
                        
                        # 🔥 SESSION LIFECYCLE: Register handler for webhook-triggered close
                        if self.call_sid:
                            _register_handler(self.call_sid, self)
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                        self.phone_number = evt.get("from") or evt.get("phone_number")
                        self.to_number = evt.get("to") or evt.get("called")
                        
                        # 🔥 SESSION LIFECYCLE: Register handler for webhook-triggered close
                        if self.call_sid:
                            _register_handler(self.call_sid, self)
                        
                        # 🔥 BUILD 174: Outbound call parameters (direct format)
                        # ⚠️ CRITICAL: call_direction is set ONCE at start and NEVER changed
                        # 🔥 HARD LOCK: Prevent any attempt to change direction after initial set
                        incoming_direction = evt.get("direction", "inbound")
                        
                        # Check if direction was already set (should never happen, but guard against it)
                        if hasattr(self, 'call_direction') and self.call_direction:
                            if self.call_direction != incoming_direction:
                                # 🔥 CRITICAL ERROR: Attempt to change direction after it was set
                                logger.error(f"❌ [CALL_DIRECTION_LOCK] ERROR: Attempt to change direction!")
                                logger.info(f"   Current: {self.call_direction}, Attempted: {incoming_direction}")
                                logger.info(f"   ⛔ BLOCKED - keeping original direction: {self.call_direction}")
                                _orig_print(f"[ERROR] CALL_DIRECTION_CHANGE_BLOCKED call_sid={self.call_sid[:8]}... current={self.call_direction} attempted={incoming_direction}", flush=True)
                            else:
                                logger.info(f"✅ [CALL_DIRECTION_LOCK] Direction already set to {self.call_direction} (no change)")
                        else:
                            # First time setting direction - this is the ONLY allowed assignment
                            self.call_direction = incoming_direction
                            logger.info(f"🔒 [CALL_DIRECTION_SET] Locked to: {self.call_direction} (IMMUTABLE)")
                            _orig_print(f"[CALL_DIRECTION_SET] call_sid={self.call_sid[:8]}... direction={self.call_direction} locked=True", flush=True)
                        
                        self.outbound_lead_id = evt.get("lead_id")
                        self.outbound_lead_name = evt.get("lead_name")
                        self.outbound_template_id = evt.get("template_id")
                        self.outbound_business_id = evt.get("business_id")  # 🔒 SECURITY: Explicit business_id for outbound
                        self.outbound_business_name = evt.get("business_name")
                        
                        # 🔥 OPTIMIZATION: Pre-load outbound greeting to avoid DB query in async loop
                        if self.call_direction == "outbound" and self.outbound_template_id and self.outbound_lead_name:
                            try:
                                from server.models_sql import OutboundTemplate
                                template = OutboundTemplate.query.get(self.outbound_template_id)
                                if template and template.greeting_template:
                                    biz_name = self.outbound_business_name or "העסק"
                                    self.outbound_greeting_text = template.greeting_template.replace("{{lead_name}}", self.outbound_lead_name).replace("{{business_name}}", biz_name)
                                    logger.info(f"✅ [OUTBOUND] Pre-loaded greeting: '{self.outbound_greeting_text[:50]}...'")
                            except Exception as e:
                                logger.error(f"⚠️ [OUTBOUND] Failed to pre-load greeting: {e}")
                        
                        # 🔍 DEBUG: Log phone number on start
                        logger.info(f"\n📞 START EVENT - Phone numbers:")
                        logger.info(f"   from field: {evt.get('from')}")
                        logger.info(f"   phone_number field: {evt.get('phone_number')}")
                        logger.info(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        
                        # 🎯 DYNAMIC LEAD STATE: Add caller phone to lead capture state
                        if self.phone_number:
                            self._update_lead_capture_state('phone', self.phone_number)
                        
                    self.last_rx_ts = time.time()
                    self.last_keepalive_ts = time.time()  # ✅ התחל keepalive
                    self.t0_connected = time.time()  # ⚡ [T0] WebSocket connected
                    logger.info(f"🎯 [T0={time.time():.3f}] WS_START sid={self.stream_sid} call_sid={self.call_sid} from={self.phone_number} to={getattr(self, 'to_number', 'N/A')} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                        
                        # 🔥 PRODUCTION LOG: [CALL_START] - Always logged (WARNING level)
                        call_direction = getattr(self, 'call_direction', 'unknown')
                        business_id = getattr(self, 'business_id', None) or getattr(self, 'outbound_business_id', None) or 'N/A'
                        logger.warning(f"[CALL_START] call_sid={self.call_sid} biz={business_id} direction={call_direction}")
                        
                        # 🔥 GREETING PROFILER: Track WS connect time
                        stream_registry.set_metric(self.call_sid, 'ws_connect_ts', self.t0_connected)
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # ⛔ CRITICAL: VALIDATE BUSINESS_ID **BEFORE** STARTING OPENAI SESSION
                    # This prevents OpenAI charges if business cannot be identified
                    # ═══════════════════════════════════════════════════════════════════════
                    logger.debug(f"[REALTIME] START event received: call_sid={self.call_sid}, to_number={getattr(self, 'to_number', 'N/A')}")
                    
                    # 🔥 STEP 1: IDENTIFY BUSINESS FIRST (before OpenAI connection)
                    t_biz_start = time.time()
                    try:
                        app = _get_flask_app()
                        with app.app_context():
                            business_id, greet = self._identify_business_and_get_greeting()
                            
                            # ⛔ CRITICAL: business_id must be set - no fallback to prevent cross-business contamination
                            if not self.business_id:
                                if not business_id:
                                    logger.error(f"❌ CRITICAL: Cannot identify business! call_sid={self.call_sid}, to={self.to_number}")
                                    _orig_print(f"❌ [BUSINESS_ISOLATION] Call rejected - no business_id for to={self.to_number}", flush=True)
                                    raise ValueError("CRITICAL: business_id required - call cannot proceed")
                                self.business_id = business_id
                            
                            # ⛔ CRITICAL: Verify business_id is set before continuing
                            if self.business_id is None:
                                logger.error(f"❌ CRITICAL: business_id still None after DB query! to={self.to_number}, call_sid={self.call_sid}")
                                _orig_print(f"❌ [BUSINESS_ISOLATION] Call rejected - business_id=None after query", flush=True)
                                raise ValueError(f"CRITICAL: Cannot identify business for to_number={self.to_number}")
                            
                            business_id_safe = self.business_id
                            call_direction = getattr(self, 'call_direction', 'inbound')
                            
                            # 🔒 LOG BUSINESS ISOLATION: Track which business is handling this call
                            logger.info(f"[BUSINESS_ISOLATION] call_accepted business_id={business_id_safe} to={self.to_number} call_sid={self.call_sid}")
                            _orig_print(f"✅ [BUSINESS_ISOLATION] Business validated: {business_id_safe}", flush=True)
                            
                            # 🔥 PART D: PRE-BUILD FULL BUSINESS prompt here (while we have app context!)
                            # This eliminates redundant DB query later and enforces prompt separation.
                            try:
                                from server.services.realtime_prompt_builder import build_full_business_prompt
                                self._prebuilt_prompt = build_full_business_prompt(business_id_safe, call_direction=call_direction)
                                logger.info(f"✅ [PART D] Pre-built FULL BUSINESS prompt: {len(self._prebuilt_prompt)} chars")
                            except Exception as prompt_err:
                                logger.error(f"⚠️ [PART D] Failed to pre-build prompt: {prompt_err}")
                                self._prebuilt_prompt = None  # Async loop will build it as fallback
                            
                        t_biz_end = time.time()
                        logger.info(f"⚡ DB QUERY + PROMPT: business_id={business_id} in {(t_biz_end-t_biz_start)*1000:.0f}ms")
                        logger.info(f"[CALL DEBUG] Business + prompt ready in {(t_biz_end-t_biz_start)*1000:.0f}ms")
                        
                        # 🔥 STEP 2: Now that business is validated, START OPENAI SESSION
                        # OpenAI connection happens ONLY AFTER business_id is confirmed
                        logger.debug(f"[REALTIME] About to check if we should start realtime thread...")
                        logger.debug(f"[REALTIME] USE_REALTIME_API={USE_REALTIME_API}, self.realtime_thread={getattr(self, 'realtime_thread', None)}")
                        
                        if USE_REALTIME_API and not self.realtime_thread:
                            logger.debug(f"[REALTIME] Condition passed - About to START realtime thread for call {self.call_sid}")
                            t_realtime_start = time.time()
                            delta_from_t0 = (t_realtime_start - self.t0_connected) * 1000
                            _orig_print(f"🚀 [REALTIME] Starting OpenAI at T0+{delta_from_t0:.0f}ms (AFTER business validation!)", flush=True)
                            
                            logger.debug(f"[REALTIME] Creating realtime thread...")
                            self.realtime_thread = threading.Thread(
                                target=self._run_realtime_mode_thread,
                                daemon=True
                            )
                            logger.debug(f"[REALTIME] Starting realtime thread...")
                            self.realtime_thread.start()
                            self.background_threads.append(self.realtime_thread)
                            logger.debug(f"[REALTIME] Realtime thread started successfully!")
                            
                            logger.debug(f"[REALTIME] Creating realtime audio out thread...")
                            # 🔥 NEW: DOUBLE LOOP GUARD - Ensure only ONE audio_out loop per call
                            if not hasattr(self, '_realtime_audio_out_thread_started'):
                                realtime_out_thread = threading.Thread(
                                    target=self._realtime_audio_out_loop,
                                    daemon=True,
                                    name=f"AudioOut-{self.call_sid[:8] if self.call_sid else 'unknown'}"
                                )
                                realtime_out_thread.start()
                                self.background_threads.append(realtime_out_thread)
                                self._realtime_audio_out_thread_started = True
                                logger.debug(f"[REALTIME] Audio out thread started (thread_id={realtime_out_thread.ident})")
                            else:
                                logger.warning(f"[REALTIME] Audio out thread already started - skipping duplicate start")
                            logger.debug(f"[REALTIME] Both realtime threads started successfully!")
                        else:
                            logger.warning(f"[REALTIME] Realtime thread NOT started! USE_REALTIME_API={USE_REALTIME_API}, self.realtime_thread exists={hasattr(self, 'realtime_thread') and self.realtime_thread is not None}")
                        if not hasattr(self, 'bot_speaks_first'):
                            self.bot_speaks_first = True
                        
                    except Exception as e:
                        import traceback
                        logger.error(f"[CALL-ERROR] Business identification failed: {e}")
                        logger.error(f"[CALL-ERROR] Traceback: {traceback.format_exc()}")
                        
                        # ⛔ CRITICAL: Cannot proceed without business_id - reject call immediately
                        # Attempting to continue would risk cross-business contamination
                        # Mask phone number for security (only show last 4 digits)
                        to_num = getattr(self, 'to_number', 'unknown')
                        to_num_masked = f"***{to_num[-4:]}" if to_num and len(to_num) >= 4 else "unknown"
                        _orig_print(f"❌ [BUSINESS_ISOLATION] Call REJECTED - cannot identify business for to={to_num_masked}", flush=True)
                        
                        # Send immediate hangup to Twilio
                        try:
                            self._immediate_hangup(reason="business_identification_failed")
                        except Exception as hangup_err:
                            logger.error(f"[CALL-ERROR] Failed to send hangup: {hangup_err}")
                        
                        # Stop processing this call
                        return
                    
                    # ⚡ STREAMING STT: Initialize ONLY if NOT using Realtime API
                    if not USE_REALTIME_API:
                        self._init_streaming_stt()
                        logger.info("✅ Google STT initialized (USE_REALTIME_API=False)")
                    
                    # 🚀 DEFERRED: Call log creation (recording deferred until FIRST_AUDIO_SENT)
                    def _deferred_call_setup():
                        try:
                            app = _get_flask_app()
                            with app.app_context():
                                if self.call_sid and not getattr(self, '_call_log_created', False):
                                    self._create_call_log_on_start()
                                    self._call_log_created = True
                                    # 🔥 RECORDING DEFERRED: Will start after FIRST_AUDIO_SENT (in TX loop)
                        except Exception as e:
                            logger.error(f"⚠️ Deferred call setup failed: {e}")
                    
                    # Start deferred setup in background (doesn't block greeting)
                    threading.Thread(target=_deferred_call_setup, daemon=True).start()
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 TX FIX: Ensure streamSid is set before starting TX loop
                    # ═══════════════════════════════════════════════════════════════════════
                    # Issue: TX loop sends to "air" if streamSid not set yet
                    # Solution: Validate streamSid before starting TX thread
                    # ═══════════════════════════════════════════════════════════════════════
                    if not self.stream_sid:
                        _orig_print(f"⚠️ [TX_FIX] streamSid not set yet - this should not happen! call_sid={self.call_sid}", flush=True)
                        logger.warning(f"[TX_FIX] streamSid missing at TX start - audio may not be sent")
                    else:
                        _orig_print(f"✅ [TX_FIX] streamSid validated: {self.stream_sid[:16]}... - TX ready", flush=True)
                    
                    # ✅ ברכה מיידית - בלי השהיה!
                    # 🔥 NEW: DOUBLE LOOP GUARD - Ensure only ONE TX thread per call
                    if not self.tx_running:
                        # Verify thread hasn't started yet
                        if self.tx_thread.is_alive():
                            _orig_print(f"⚠️ [TX_GUARD] TX thread already running - skipping start", flush=True)
                        else:
                            self.tx_running = True
                            self.tx_thread.start()
                            _orig_print(f"🚀 [TX_LOOP] Started TX thread (streamSid={'SET' if self.stream_sid else 'MISSING'}, thread_id={self.tx_thread.ident})", flush=True)
                    else:
                        _orig_print(f"⚠️ [TX_GUARD] TX loop already running - skipping duplicate start", flush=True)
                    
                    # 🔥 STEP 3: Store greeting and signal event (OpenAI thread is waiting!)
                    if not self.greeting_sent and USE_REALTIME_API:
                        self.t1_greeting_start = time.time()
                        if greet:
                            logger.info(f"🎯 [T1={self.t1_greeting_start:.3f}] STORING GREETING FOR REALTIME!")
                            self.greeting_text = greet
                            if not hasattr(self, 'greeting_sent'):
                                self.greeting_sent = False
                            logger.info(f"✅ [REALTIME] Greeting stored: '{greet[:50]}...' (len={len(greet)})")
                        else:
                            logger.info(f"🎯 [T1={self.t1_greeting_start:.3f}] NO GREETING - AI will speak first!")
                            self.greeting_text = None
                            self.greeting_sent = True
                    
                    # 🚀 SIGNAL: Tell OpenAI thread that business info is ready!
                    total_startup_ms = (time.time() - self.t0_connected) * 1000
                    logger.info(f"🚀 [PARALLEL] Signaling business info ready at T0+{total_startup_ms:.0f}ms")
                    self.business_info_ready_event.set()
                    
                    # Note: Realtime thread was already started above (BEFORE DB query)
                    
                    # 🎵 GOOGLE TTS: Send greeting via Google TTS if NOT using Realtime
                    if not self.greeting_sent and not USE_REALTIME_API:
                        self.t1_greeting_start = time.time()  # ⚡ [T1] Greeting start
                        logger.info(f"🎯 [T1={self.t1_greeting_start:.3f}] SENDING IMMEDIATE GREETING! (Δ={(self.t1_greeting_start - self.t0_connected)*1000:.0f}ms from T0)")
                        try:
                            self._speak_greeting(greet)  # ✅ פונקציה מיוחדת לברכה ללא sleep!
                            self.t2_greeting_end = time.time()  # ⚡ [T2] Greeting end
                            logger.info(f"🎯 [T2={self.t2_greeting_end:.3f}] GREETING_COMPLETE! (Duration={(self.t2_greeting_end - self.t1_greeting_start)*1000:.0f}ms)")
                            self.greeting_sent = True
                        except Exception as e:
                            logger.error(f"❌ CRITICAL ERROR sending greeting: {e}")
                            import traceback
                            traceback.print_exc()
                    continue

                if et == "media":
                    self.rx += 1
                    # 🔥 FIX: Count ALL frames received from Twilio (before any filtering)
                    # This is the source of truth for "frames_in" - must happen here, not after filters
                    # Counter initialized in __init__ - direct increment (no getattr masking)
                    self.realtime_audio_in_chunks += 1
                    # 🔥 REMOVED: greeting_lock frame dropping - all frames are now processed
                    
                    b64 = evt["media"]["payload"]
                    mulaw = base64.b64decode(b64)
                    # ⚡ SPEED: Fast μ-law decode using lookup table (~10-20x faster)
                    pcm16 = mulaw_to_pcm16_fast(mulaw)
                    self.last_rx_ts = time.time()
                    if self.call_sid:
                        stream_registry.touch_media(self.call_sid)
                    
                    # 🔥 BUILD 165: NOISE GATE BEFORE SENDING TO AI!
                    # Calculate RMS first to decide if we should send audio at all
                    rms = audioop.rms(pcm16, 2)
                    
                    # 🔥 VERIFICATION: Track VAD calibration in first 3 seconds
                    if self._vad_calibration_start_ts is None:
                        self._vad_calibration_start_ts = time.time()
                        logger.info(f"🎯 [VAD_CALIBRATION] Started tracking first 3 seconds")
                    
                    if not self._vad_calibration_complete:
                        calibration_elapsed = time.time() - self._vad_calibration_start_ts
                        if calibration_elapsed <= 3.0:
                            self._vad_frames_in_first_3s += 1
                        elif calibration_elapsed > 3.0 and not self._vad_calibration_complete:
                            # Calibration period ended - log results
                            self._vad_calibration_complete = True
                            self._vad_calibrated_noise_floor = getattr(self, '_recent_audio_rms', 0)
                            self._vad_calibrated_threshold = getattr(self, 'vad_threshold', 0)
                            logger.info(f"✅ [VAD_CALIBRATION] Complete after 3s:")
                            logger.info(f"   noise_floor={self._vad_calibrated_noise_floor:.1f}")
                            logger.info(f"   threshold={self._vad_calibrated_threshold:.1f}")
                            logger.info(f"   vad_calibrated=True")
                            logger.info(f"   frames_in_first_3s={self._vad_frames_in_first_3s}")
                            logger.info(f"   speech_started_count_first_3s={self._vad_speech_started_count_first_3s}")
                            if self._vad_speech_started_count_first_3s > 0 and self._vad_frames_in_first_3s < 50:
                                # Warning: speech_started triggered very early (possible false trigger)
                                logger.warning(
                                    f"[VAD_WARNING] speech_started triggered {self._vad_speech_started_count_first_3s} times "
                                    f"in first {self._vad_frames_in_first_3s} frames - possible false trigger!"
                                )
                    
                    # 🔥 BUILD 170: Track recent RMS for silence gate in transcription handler
                    # Use exponential moving average for smooth tracking
                    if not hasattr(self, '_recent_audio_rms'):
                        self._recent_audio_rms = rms
                    else:
                        # EMA with alpha=0.3 for quick response
                        self._recent_audio_rms = 0.3 * rms + 0.7 * self._recent_audio_rms
                    
                    # 🛡️ CRITICAL: Block pure noise BEFORE sending to OpenAI
                    # This prevents Whisper/Realtime from hallucinating on background noise
                    # 🔥 BUILD 166: BYPASS noise gate when OpenAI is actively processing speech
                    # OpenAI needs continuous audio stream to detect speech end
                    # Safety timeout: auto-reset if speech_stopped never arrives
                    speech_bypass_active = self._realtime_speech_active
                    if speech_bypass_active and self._realtime_speech_started_ts:
                        elapsed = time.time() - self._realtime_speech_started_ts
                        if elapsed > self._realtime_speech_timeout_sec:
                            self._realtime_speech_active = False
                            speech_bypass_active = False
                            logger.info(f"⏱️ [BUILD 166] Speech timeout after {elapsed:.1f}s - noise gate RE-ENABLED")
                    
                    # 🔥 BUILD 302: BARGE-IN BYPASS - During barge-in, NEVER treat anything as noise
                    # This ensures 100% of user's speech goes to OpenAI when they interrupt AI
                    if self.barge_in_active:
                        is_noise = False  # Force through during barge-in
                    else:
                        is_noise = rms < RMS_SILENCE_THRESHOLD and not speech_bypass_active  # 40 RMS = pure noise
                    
                    # 🔥 BUILD 167: MUSIC GATE DISABLED - Hebrew speech was being blocked!
                    # Hebrew has sustained consonant clusters with RMS 200-350 which matched "music" pattern
                    # The noise gate (RMS < 120) is sufficient to block background noise
                    is_music = False  # ALWAYS FALSE - no music detection
                    
                    # 🔥 BUILD 165: CALIBRATION MUST RUN FOR ALL FRAMES (even noise!)
                    # This ensures VAD thresholds stay accurate
                    if not self.is_calibrated:
                        total_frames = getattr(self, '_total_calibration_attempts', 0) + 1
                        self._total_calibration_attempts = total_frames
                        
                        # Calibrate on pure noise frames
                        if is_noise:
                            self.noise_floor = (self.noise_floor * self.calibration_frames + rms) / (self.calibration_frames + 1)
                            self.calibration_frames += 1
                        
                        # Complete calibration after 40 quiet frames OR 4 seconds timeout
                        if self.calibration_frames >= 40 or total_frames >= 200:
                            if self.calibration_frames < 10:
                                # 🔥 BUILD 325: Use config constants for VAD thresholds
                                self.vad_threshold = VAD_BASELINE_TIMEOUT  # 80.0 from config
                                logger.warning(f"🎛️ [VAD] TIMEOUT - using baseline threshold={VAD_BASELINE_TIMEOUT}")
                                logger.info(f"🎛️ VAD TIMEOUT - using baseline threshold={VAD_BASELINE_TIMEOUT}")
                            else:
                                # 🔥 BUILD 325: Adaptive: noise + offset, capped for quiet speakers
                                self.vad_threshold = min(VAD_ADAPTIVE_CAP, self.noise_floor + VAD_ADAPTIVE_OFFSET)
                                logger.info(f"✅ [VAD] Calibrated: noise={self.noise_floor:.1f}, threshold={self.vad_threshold:.1f}")
                                logger.info(f"🎛️ VAD CALIBRATED (noise={self.noise_floor:.1f}, threshold={self.vad_threshold:.1f})")
                            self.is_calibrated = True
                    
                    # 🚀 REALTIME API: Route audio to Realtime if enabled
                    if USE_REALTIME_API and self.realtime_thread and self.realtime_thread.is_alive():
                        # 🔥 REMOVED: greeting_lock frame dropping - all frames are now processed
                        
                        if not self.barge_in_enabled_after_greeting:
                            # 🔥 P0-4: Skip echo gate in SIMPLE_MODE (passthrough only)
                            if SIMPLE_MODE:
                                # SIMPLE_MODE = no guards, passthrough all audio + logs only
                                pass  # Skip all echo gate logic
                            else:
                                # 🔥 BUILD 304: ECHO GATE - Block echo while AI is speaking + 800ms after
                                # This prevents OpenAI from transcribing its own voice output as user speech!
                                # The AI's TTS audio echoes back through the phone line and causes hallucinations
                                # 
                                # CRITICAL: Echo can be HIGH RMS (2000+) because TTS plays loud through phone
                                # So we can't just use RMS threshold - we must block ALL audio during AI speech
                                # ONLY allow through if we have SUSTAINED high-RMS speech (5+ frames = 100ms)
                                
                                # Track consecutive high-RMS frames for barge-in detection
                                if not hasattr(self, '_echo_gate_consec_frames'):
                                    self._echo_gate_consec_frames = 0
                                
                                # Use calibrated noise floor for RMS-based speech detection
                                # Note: self.noise_floor is RMS value (~100), self.vad_threshold is probability (0.85)!
                                noise_floor_rms = getattr(self, 'noise_floor', 100.0)
                                # 🔥 BUILD 325: Echo gate from config - prevents AI echo from triggering barge-in
                                rms_speech_threshold = max(noise_floor_rms * 3.0, ECHO_GATE_MIN_RMS)
                                is_above_speech = rms > rms_speech_threshold
                                
                                # Count consecutive frames above RMS speech threshold
                                if is_above_speech:
                                    self._echo_gate_consec_frames += 1
                                else:
                                    # Reset quickly when audio drops - echo is intermittent
                                    self._echo_gate_consec_frames = 0
                                
                                # ═══════════════════════════════════════════════════════════════
                                # 🎯 P0-3: Stable Barge-In with Short Forwarding Window
                                # ═══════════════════════════════════════════════════════════════
                                # When AI is speaking:
                                # 1. Block ALL audio by default (no echo to OpenAI)
                                # 2. Local VAD runs continuously (RMS + consecutive frames)
                                # 3. When VAD confirms real speech → open SHORT forwarding window (200-400ms)
                                # 4. After window closes → back to blocking until next VAD confirmation
                                # ═══════════════════════════════════════════════════════════════
                                
                                # STRICT barge-in detection: ECHO_GATE_MIN_FRAMES consecutive = real speech
                                # Echo spikes are typically 1-3 frames, real speech is sustained
                                # ECHO_GATE_MIN_FRAMES comes from config (default: 5 = 100ms)
                                is_likely_real_speech = self._echo_gate_consec_frames >= ECHO_GATE_MIN_FRAMES
                                
                                # 🎯 P0-3: Short forwarding window (200-400ms) after VAD confirmation
                                FORWARDING_WINDOW_MS = 300  # 300ms window after VAD confirms speech
                                
                                # Track forwarding window state
                                if not hasattr(self, '_forwarding_window_open_ts'):
                                    self._forwarding_window_open_ts = None
                                
                                # Open forwarding window when VAD confirms real speech
                                if is_likely_real_speech and not self._forwarding_window_open_ts:
                                    self._forwarding_window_open_ts = time.time()
                                    logger.info(f"🔓 [P0-3] Opening {FORWARDING_WINDOW_MS}ms forwarding window - VAD confirmed speech")
                                
                                # Check if forwarding window is still open
                                window_is_open = False
                                if self._forwarding_window_open_ts:
                                    elapsed_ms = (time.time() - self._forwarding_window_open_ts) * 1000
                                    if elapsed_ms < FORWARDING_WINDOW_MS:
                                        window_is_open = True
                                    else:
                                        # Window expired - close it
                                        self._forwarding_window_open_ts = None
                                        logger.info(f"🔒 [P0-3] Forwarding window closed after {elapsed_ms:.0f}ms")
                                
                                if self.is_ai_speaking_event.is_set():
                                    # AI is actively speaking - block ALL audio UNLESS:
                                    # 1. Barge-in already active (user confirmed to be speaking)
                                    # 2. OpenAI speech detection active (bypass during user turn)
                                    # 3. Forwarding window is open (short window after VAD confirmation)
                                    if not self.barge_in_active and not self._realtime_speech_active and not window_is_open:
                                        # Block - this is echo or noise
                                        if not hasattr(self, '_echo_gate_logged') or not self._echo_gate_logged:
                                            logger.info(f"🛡️ [P0-3] Blocking audio - AI speaking (rms={rms:.0f}, frames={self._echo_gate_consec_frames}/{ECHO_GATE_MIN_FRAMES}, window_open={window_is_open})")
                                            self._echo_gate_logged = True
                                        # 🔥 FIX: Track frame drop reason
                                        self._stats_audio_blocked += 1
                                        self._frames_dropped_by_filters += 1  # Dropped by echo gate filter
                                        self._frames_dropped_by_reason[FrameDropReason.ECHO_GATE] += 1  # Detailed tracking
                                        continue
                                    elif window_is_open:
                                        # Forwarding window is open - let audio through
                                        if not hasattr(self, '_forwarding_window_logged'):
                                            logger.info(f"📤 [P0-3] Forwarding audio through {FORWARDING_WINDOW_MS}ms window (frames={self._echo_gate_consec_frames})")
                                            self._forwarding_window_logged = True
                                
                                # Check echo decay period (800ms after AI stops speaking)
                                if hasattr(self, '_ai_finished_speaking_ts') and self._ai_finished_speaking_ts:
                                    echo_decay_ms = (time.time() - self._ai_finished_speaking_ts) * 1000
                                    if echo_decay_ms < POST_AI_COOLDOWN_MS:
                                        # Still in echo decay period - block unless:
                                        # 1. OpenAI speech detection active
                                        # 2. Barge-in active
                                        # 3. Forwarding window is open
                                        if not self._realtime_speech_active and not self.barge_in_active and not window_is_open:
                                            if not hasattr(self, '_echo_decay_logged') or not self._echo_decay_logged:
                                                logger.info(f"🛡️ [P0-3] Blocking - echo decay ({echo_decay_ms:.0f}ms, window_open={window_is_open})")
                                                self._echo_decay_logged = True
                                            # 🔥 FIX: Track frame drop reason
                                            self._stats_audio_blocked += 1
                                            self._frames_dropped_by_filters += 1  # Dropped by echo decay filter
                                            self._frames_dropped_by_reason[FrameDropReason.ECHO_DECAY] += 1  # Detailed tracking
                                            continue
                                    else:
                                        # Echo decay complete - reset log flags for next AI response
                                        self._echo_gate_logged = False
                                        self._echo_decay_logged = False
                                        self._forwarding_window_logged = False
                                        self._echo_gate_consec_frames = 0
                                        # Also close forwarding window
                                        self._forwarding_window_open_ts = None
                        else:
                            # Greeting finished - don't block user speech at all, let OpenAI detect barge-in
                            self._echo_gate_consec_frames = 0
                        
                        # 🔥 BUILD 171: CONSECUTIVE FRAME REQUIREMENT
                        # Track consecutive voice frames before considering it real speech
                        # This prevents random noise spikes from triggering transcription
                        # 🔥 BUILD 303: During barge-in, don't decay frames - let everything through!
                        if not is_noise and rms >= MIN_SPEECH_RMS:
                            self._consecutive_voice_frames += 1
                        elif not self.barge_in_active:  # Only decay if NOT in barge-in mode
                            # Reset on silence/noise - require sustained speech
                            if self._consecutive_voice_frames > 0:
                                self._consecutive_voice_frames = max(0, self._consecutive_voice_frames - 2)  # Decay slowly
                        
                        # 🔥 BUILD 171: Only send audio if we have enough consecutive frames OR bypass is active
                        # 🔥 BUILD 302/303: ALWAYS send during barge-in, even if noise/low RMS!
                        has_sustained_speech = self._consecutive_voice_frames >= MIN_CONSECUTIVE_VOICE_FRAMES
                        
                        # ═══════════════════════════════════════════════════════════════════════
                        # 🎯 P0-4: SIMPLE_MODE Must Be Passthrough (Master Instruction)
                        # ═══════════════════════════════════════════════════════════════════════
                        # ❌ NO guards in SIMPLE_MODE
                        # ❌ NO frame dropping in SIMPLE_MODE  
                        # ❌ NO echo_window in SIMPLE_MODE
                        # ❌ NO hallucination filters in SIMPLE_MODE
                        # ✅ Passthrough + logs only
                        # ═══════════════════════════════════════════════════════════════════════
                        if SIMPLE_MODE:
                            # 🔥 P0-4: SIMPLE_MODE = passthrough ONLY, trust OpenAI completely
                            should_send_audio = True  # ALWAYS send in SIMPLE_MODE
                            is_noise = False  # Trust OpenAI's VAD for noise filtering
                        elif self.barge_in_active or self._realtime_speech_active:
                            should_send_audio = True  # Send EVERYTHING during barge-in or active speech
                            is_noise = False  # Force override noise flag too
                        else:
                            should_send_audio = (has_sustained_speech or speech_bypass_active) and not is_noise
                        
                        # 🔥 BUILD 165: ONLY send audio above noise threshold AND sustained speech!
                        if should_send_audio:
                            try:
                                # 🔍 DEBUG: Log first few frames from Twilio (only in development mode)
                                if not hasattr(self, '_twilio_audio_chunks_sent'):
                                    self._twilio_audio_chunks_sent = 0
                                self._twilio_audio_chunks_sent += 1
                                
                                # 🎯 TASK A.2: Log SIMPLE MODE bypass confirmation (first 3 frames only in dev)
                                # DEBUG=0 → development (verbose), DEBUG=1 → production (quiet)
                                if not DEBUG and self._twilio_audio_chunks_sent <= 3:
                                    # Only log first 3 frames in development mode
                                    first5_bytes = ' '.join([f'{b:02x}' for b in mulaw[:5]])
                                    mode_info = "SIMPLE_MODE" if SIMPLE_MODE else "FILTERED_MODE"
                                    guard_status = "BYPASSED" if (SIMPLE_MODE and not getattr(self, '_audio_guard_enabled', False)) else "ACTIVE"
                                    logger.info(f"🎤 [BUILD 166] Noise gate {guard_status} - sending ALL audio to OpenAI")
                                    logger.info(f"[REALTIME] sending audio TO OpenAI: chunk#{self._twilio_audio_chunks_sent}, μ-law bytes={len(mulaw)}, first5={first5_bytes}, rms={rms:.0f}, mode={mode_info}")
                                
                                self.realtime_audio_in_queue.put_nowait(b64)
                            except queue.Full:
                                # 🔥 FIX: Track queue full drops
                                self._stats_audio_blocked += 1
                                self._frames_dropped_by_queue_full += 1
                                self._frames_dropped_by_reason[FrameDropReason.QUEUE_FULL] += 1  # Detailed tracking
                                # Rate-limit logging
                                if not hasattr(self, '_queue_full_log_count'):
                                    self._queue_full_log_count = 0
                                self._queue_full_log_count += 1
                                if self._queue_full_log_count % 50 == 1:
                                    logger.warning(f"⚠️ [QUEUE_FULL] Dropped {self._queue_full_log_count} frames - realtime_audio_in_queue full")
                                pass
                        else:
                            # 🔥 BUILD 171: Enhanced logging for debugging
                            if not hasattr(self, '_noise_reject_count'):
                                self._noise_reject_count = 0
                            self._noise_reject_count += 1
                            # Log every 100 rejected frames with more detail
                            if self._noise_reject_count % 100 == 0:
                                reason = "noise" if is_noise else f"insufficient_consec_frames({self._consecutive_voice_frames}/{MIN_CONSECUTIVE_VOICE_FRAMES})"
                                logger.info(f"🔇 [AUDIO GATE] Blocked {self._noise_reject_count} frames (rms={rms:.0f}, reason={reason})")
                    # ⚡ STREAMING STT: Feed audio to Google STT ONLY if NOT using Realtime API
                    elif not USE_REALTIME_API and self.call_sid and pcm16 and not is_noise:
                        session = _get_session(self.call_sid)
                        if session:
                            session.push_audio(pcm16)
                            # Update session timestamp to prevent cleanup
                            with _registry_lock:
                                item = _sessions_registry.get(self.call_sid)
                                if item:
                                    item["ts"] = time.time()
                        elif USE_STREAMING_STT:
                            # ⚠️ Session should exist but doesn't!
                            if not hasattr(self, '_session_warning_logged'):
                                logger.warning(f"⚠️ [STT] No streaming session for {self.call_sid[:8]} - using fallback")
                                self._session_warning_logged = True
                    
                    # 🔥 BUILD 165: RMS already calculated above at line 2937 (before noise gate)
                    # No need to recalculate - reuse the 'rms' variable
                    
                    # 🔥 BUILD 165: BALANCED BARGE-IN - Filter noise while allowing speech
                    # ✅ P0-2: Clean barge-in with local RMS VAD only (no duplex/guards)
                    if USE_REALTIME_API and self.realtime_thread and self.realtime_thread.is_alive():
                        # 🔍 DEBUG: Log AI speaking state every 50 frames (~1 second)
                        if not hasattr(self, '_barge_in_debug_counter'):
                            self._barge_in_debug_counter = 0
                        self._barge_in_debug_counter += 1
                        
                        if self._barge_in_debug_counter % 50 == 0:
                            # ✅ NEW REQ 3: Enhanced logging with rms, threshold, consec_frames for tuning (DEBUG only)
                            current_threshold = MIN_SPEECH_RMS
                            logger.debug(f"[BARGE-IN DEBUG] is_ai_speaking={self.is_ai_speaking_event.is_set()}, "
                                  f"user_has_spoken={self.user_has_spoken}, waiting_for_dtmf={self.waiting_for_dtmf}, "
                                  f"rms={rms:.0f}, threshold={current_threshold:.0f}, voice_frames={self.barge_in_voice_frames}/{BARGE_IN_VOICE_FRAMES}")
                        
                        # 🔥 FIX 2: Barge-in moved to speech_started ONLY
                        # No RMS-based barge-in here - trust OpenAI VAD in speech_started event
                        # This section previously had RMS-based barge-in logic (removed)
                    
                    # 🔥 BUILD 165: Calibration already done above (before audio routing)
                    # No duplicate calibration needed here
                    
                    # 🔥 BUILD 325: Voice detection with balanced threshold
                    if self.is_calibrated:
                        is_strong_voice = rms > self.vad_threshold
                    else:
                        # Before calibration - use MIN_SPEECH_RMS (60) - trust OpenAI VAD
                        is_strong_voice = rms > MIN_SPEECH_RMS
                    
                    # ✅ FIXED: Update last_voice_ts only with VERY strong voice
                    current_time = time.time()
                    # ✅ EXTRA CHECK: Only if RMS is significantly above threshold (use calibrated or MIN_SPEECH_RMS)
                    if is_strong_voice and rms > (getattr(self, 'vad_threshold', MIN_SPEECH_RMS) * 1.2):
                        self.last_voice_ts = current_time
                        # 🔧 Reduced logging spam - max once per 3 seconds
                        if not hasattr(self, 'last_debug_ts') or (current_time - self.last_debug_ts) > 3.0:
                            logger.info(f"🎙️ REAL_VOICE: rms={rms:.1f} > threshold={getattr(self, 'vad_threshold', 'uncalibrated'):.1f}")
                            self.last_debug_ts = current_time
                    
                    # חישוב דממה אמיתי - מאז הקול האחרון! 
                    # אם אין קול בכלל, דממה = 0 (כדי שלא נתקע)
                    silence_time = (current_time - self.last_voice_ts) if self.last_voice_ts > 0 else 0
                    
                    # ✅ לוגים נקיים - רק אירועים חשובים (לא כל frame)  
                    
                    # 🔒 BARGE-IN FIX: Audio now flows continuously to OpenAI for speech detection
                    # OpenAI's server_vad detects user speech and handles barge-in automatically
                    
                    # 🔥 BUILD 165: FALLBACK BARGE-IN - ONLY for non-Realtime API mode!
                    # Realtime API has its own barge-in handler above (lines 3010-3065)
                    # This is for legacy Google STT mode only
                    if ENABLE_BARGE_IN and not self.is_playing_greeting and not USE_REALTIME_API:
                        # ספירת פריימים רצופים של קול חזק בלבד
                        if is_strong_voice:
                            self.voice_in_row += 1
                        else:
                            self.voice_in_row = max(0, self.voice_in_row - 2)  # קיזוז מהיר לרעשים

                        # ⚡ SIMPLIFIED BARGE-IN: Fast and speech-based
                        # Only trigger after user has spoken at least once (no false positives during greeting)
                        if self.speaking and not self.waiting_for_dtmf:
                            # Do NOT allow barge-in before the user has ever spoken
                            if not self.user_has_spoken:
                                # User never spoke yet → do not treat noise as barge-in
                                continue
                            
                            time_since_tts_start = current_time - self.speaking_start_ts
                            
                            # Short grace period (300ms) to avoid echo of our own TTS
                            grace_period = 0.3
                            if time_since_tts_start < grace_period:
                                continue
                            
                            # Use our calibrated speech threshold as barge-in trigger
                            speech_threshold = getattr(self, "vad_threshold", None) or MIN_SPEECH_RMS
                            
                            if rms >= speech_threshold:
                                logger.info(f"[BARGE-IN FALLBACK] User speech detected (rms={rms:.1f}, threshold={speech_threshold:.1f})")
                                
                                # Stop AI speaking
                                self.speaking = False
                                
                                # Clean up state
                                self.state = STATE_LISTEN
                                self.processing = False
                                self.buf.clear()
                                self.last_voice_ts = current_time
                                self.voice_in_row = 0
                                
                                logger.info("🎤 BARGE-IN -> LISTENING (user can speak now)")
                                
                                # Send clear to Twilio
                                if not self.ws_connection_failed:
                                    try:
                                        self._tx_enqueue({"type": "clear"})
                                    except:
                                        pass
                                continue
                    
                    # ✅ איסוף אודיו עם זיהוי דממה תקין
                    if not self.processing and self.state == STATE_LISTEN:
                        # חלון רפרקטורי אחרי TTS
                        if (current_time - self.last_tts_end_ts) < (REPLY_REFRACTORY_MS/1000.0):
                            continue
                        
                        # אסוף אודיו רק כשיש קול או כשיש כבר דבר מה בבאפר
                        if is_strong_voice or len(self.buf) > 0:
                            # ⚡ STREAMING STT: Mark start of new utterance (once) + save partial text
                            if len(self.buf) == 0 and is_strong_voice:
                                # Callback to save BEST (longest) partial text for early EOU detection
                                def save_partial(text):
                                    # 🔥 FIX: Save LONGEST partial, not last! Google STT sometimes sends shorter corrections
                                    current_best = getattr(self, "last_partial_text", "")
                                    if len(text) > len(current_best):
                                        self.last_partial_text = text
                                        logger.info(f"🔊 PARTIAL (best): '{text}' ({len(text)} chars)")
                                    else:
                                        logger.info(f"🔊 PARTIAL (ignored): '{text}' ({len(text)} chars) - keeping '{current_best}' ({len(current_best)} chars)")
                                
                                self.last_partial_text = ""  # Reset
                                self._utterance_begin(partial_cb=save_partial)
                            
                            self.buf.extend(pcm16)
                            dur = len(self.buf) / (2 * SR)
                            
                            # ⚡ BUILD 107: ULTRA-LOW LATENCY - 0.5s silence for FAST responses
                            # תגובות קצרות: min_silence קצר מאוד (0.5s) ⚡⚡⚡
                            # משפטים ארוכים: min_silence קצר (1.8s במקום 3.0s)
                            if dur < 2.0:
                                min_silence = 0.5  # ⚡ תגובה קצרה - סופר מהר! (חצי שניה!)
                            else:
                                min_silence = 1.8  # ⚡ משפט ארוך - מהיר (במקום 3.0s)
                            
                            silent = silence_time >= min_silence  
                            too_long = dur >= MAX_UTT_SEC
                            min_duration = 0.6  # ⚡ BUILD 107: מינימום קצר יותר - 0.6s במקום 0.7s
                            
                            # ⚡ BUILD 107: באפר קטן יותר = תגובה מהירה יותר!
                            buffer_big_enough = len(self.buf) > 8000  # ⚡ 0.5s במקום 0.8s - חוסך 300ms!
                            
                            # ⚡⚡⚡ BUILD 107: EARLY EOU - מענה מוקדם על partial חזק!
                            # אם יש partial חזק (12+ תווים וסיום במשפט) + 0.35s דממה - קפיצה מיד!
                            last_partial = getattr(self, "last_partial_text", "")
                            high_conf_partial = (len(last_partial) >= 12) and any(last_partial.endswith(p) for p in (".", "?", "!", "…", ":", ";"))
                            early_silence = silence_time >= 0.35  # דממה קצרצרה
                            
                            if high_conf_partial and early_silence and dur >= 0.5:
                                logger.info(f"⚡⚡⚡ EARLY EOU on strong partial: '{last_partial}' ({dur:.1f}s, {silence_time:.2f}s silence)")
                                # קפיצה מיידית לעיבוד!
                                silent = True
                                buffer_big_enough = True
                            
                            # סוף מבע: דממה מספקת OR זמן יותר מדי OR באפר גדול עם שקט
                            if ((silent and buffer_big_enough) or too_long) and dur >= min_duration:
                                logger.info(f"🎤 END OF UTTERANCE: {dur:.1f}s audio, conversation #{self.conversation_id}")
                                
                                # ✅ מדידת Turn Latency - התחלת מדידה
                                self.eou_timestamp = time.time()
                                
                                # מעבר לעיבוד
                                self.processing = True
                                self.processing_start_ts = current_time
                                self.state = STATE_THINK
                                current_id = self.conversation_id
                                self.conversation_id += 1
                                
                                # עיבוד במנותק
                                utt_pcm = bytes(self.buf)
                                self.buf.clear()
                                self.last_voice_ts = 0  # אפס לסיבוב הבא
                                
                                logger.info(f"🧠 STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                                
                                try:
                                    self._process_utterance_safe(utt_pcm, current_id)
                                except Exception as proc_err:
                                    logger.error(f"❌ Audio processing failed for conversation #{current_id}: {proc_err}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continue without crashing WebSocket
                                finally:
                                    self.processing = False
                                    if self.state == STATE_THINK:
                                        self.state = STATE_LISTEN
                                    logger.info(f"✅ Processing complete for conversation #{current_id}")
                    
                    # ✅ WebSocket Keepalive - מונע נפילות אחרי 5 דקות (DEBUG only)
                    if current_time - self.last_keepalive_ts > self.keepalive_interval:
                        self.last_keepalive_ts = current_time
                        self.heartbeat_counter += 1
                        
                        # שלח heartbeat mark event אם החיבור תקין
                        if not self.ws_connection_failed:
                            try:
                                heartbeat_msg = {
                                    "event": "mark",
                                    "streamSid": self.stream_sid,
                                    "mark": {"name": f"heartbeat_{self.heartbeat_counter}"}
                                }
                                success = self._ws_send(json.dumps(heartbeat_msg))
                                if success:
                                    logger.debug(f"WS_KEEPALIVE #{self.heartbeat_counter} (prevents 5min timeout)")
                            except Exception as e:
                                logger.debug(f"Keepalive failed: {e}")
                        else:
                            logger.debug(f"SKIPPING keepalive - WebSocket connection failed")
                    
                    # ✅ Watchdog: וודא שלא תקועים במצב + EOU כפויה
                    if self.processing and (current_time - self.processing_start_ts) > 2.5:
                        logger.warning("⚠️ PROCESSING TIMEOUT - forcing reset")
                        self.processing = False
                        self.state = STATE_LISTEN
                        self.buf.clear()
                    
                    # ✅ LONGER speaking timeout to prevent cutoff mid-sentence
                    if self.speaking and (current_time - self.speaking_start_ts) > 15.0:
                        logger.warning("⚠️ SPEAKING TIMEOUT - forcing reset after 15s")
                        self.speaking = False
                        self.state = STATE_LISTEN
                    
                    # ✅ EOU חירום: מכריח עיבוד אם הבאפר גדול מדי
                    if (not self.processing and self.state == STATE_LISTEN and 
                        len(self.buf) > 96000 and  # ✅ FIX: 6.0s של אודיו (לא קוטע משפטים ארוכים!)
                        silence_time > 2.0):      # ✅ FIX: 2.0s שקט לחירום - שקט אמיתי!
                        logger.info(f"🚨 EMERGENCY EOU: {len(self.buf)/(2*SR):.1f}s audio, silence={silence_time:.2f}s")
                        # כפה EOU
                        self.processing = True
                        self.processing_start_ts = current_time
                        self.state = STATE_THINK
                        current_id = self.conversation_id
                        self.conversation_id += 1
                        
                        utt_pcm = bytes(self.buf)
                        self.buf.clear()
                        self.last_voice_ts = 0
                        
                        logger.info(f"🧠 EMERGENCY STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                        
                        try:
                            self._process_utterance_safe(utt_pcm, current_id)
                        except Exception as proc_err:
                            logger.error(f"❌ Emergency audio processing failed for conversation #{current_id}: {proc_err}")
                            import traceback
                            traceback.print_exc()
                            # Continue without crashing WebSocket
                        finally:
                            self.processing = False
                            if self.state == STATE_THINK:
                                self.state = STATE_LISTEN
                            logger.info(f"✅ Emergency processing complete for conversation #{current_id}")
                    
                    continue
                
                if et == "dtmf":
                    # ⚡ BUILD 121: DTMF digit collection for phone number input
                    digit = evt.get("dtmf", {}).get("digit", "")
                    logger.info(f"📞 DTMF pressed: {digit} (buffer={self.dtmf_buffer})")
                    
                    if digit == "#":
                        # End of input - process collected digits
                        if not self.dtmf_buffer:
                            # 🎯 תרחיש 1: סולמית בלבד = דילוג
                            logger.info(f"⏭️ DTMF skip: empty buffer, user skipped phone input")
                            self.waiting_for_dtmf = False
                            
                            # Inject skip message to AI
                            skip_text = "אני מדלג על מתן המספר"
                            logger.info(f"🎯 DTMF skip -> AI: '{skip_text}'")
                            
                            try:
                                self._process_dtmf_skip()
                            except Exception as e:
                                logger.error(f"❌ DTMF skip processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        elif len(self.dtmf_buffer) >= 9:
                            # 🎯 תרחיש 2: ספרות + # = שליחה
                            phone_number = self.dtmf_buffer
                            logger.info(f"✅ DTMF phone collected: {phone_number}")
                            
                            # Clear buffer
                            self.dtmf_buffer = ""
                            self.waiting_for_dtmf = False
                            
                            # Inject as if customer said the number
                            hebrew_text = f"המספר שלי הוא {phone_number}"
                            logger.info(f"🎯 DTMF -> AI: '{hebrew_text}'")
                            
                            # Process as normal utterance (trigger AI response)
                            try:
                                self._process_dtmf_phone(phone_number)
                            except Exception as e:
                                logger.error(f"❌ DTMF processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            # Buffer too short
                            logger.warning(f"⚠️ DTMF input too short: {self.dtmf_buffer} (need 9+ digits)")
                            # Speak error message
                            self._speak_tts("המספר קצר מדי, נא להקיש 9 ספרות לפחות או לחץ סולמית כדי לדלג")
                        
                        # Reset buffer anyway
                        self.dtmf_buffer = ""
                        self.waiting_for_dtmf = False
                        
                    elif digit == "*":
                        # Clear/restart input
                        logger.info(f"🔄 DTMF cleared (was: {self.dtmf_buffer})")
                        self.dtmf_buffer = ""
                        # Don't speak - just clear buffer
                        
                    elif digit.isdigit():
                        # Append digit
                        self.dtmf_buffer += digit
                        logger.info(f"📝 DTMF buffer: {self.dtmf_buffer}")
                        
                        # 🔥 AUTO-SUBMIT: If we have 10 digits (Israeli mobile), auto-process without waiting for #
                        if len(self.dtmf_buffer) == 10:
                            phone_number = self.dtmf_buffer
                            logger.info(f"✅ DTMF auto-submit (10 digits): {phone_number}")
                            
                            # Clear buffer
                            self.dtmf_buffer = ""
                            self.waiting_for_dtmf = False
                            
                            # Process the phone number
                            try:
                                self._process_dtmf_phone(phone_number)
                            except Exception as e:
                                logger.error(f"❌ DTMF auto-submit processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                    
                    continue

                if et == "mark":
                    # ✅ סימון TTS הושלם - חזור להאזנה
                    mark_name = evt.get("mark", {}).get("name", "")
                    if mark_name == "assistant_tts_end":
                        logger.info("🎯 TTS_MARK_ACK: assistant_tts_end -> LISTENING")
                        self.speaking = False
                        self.state = STATE_LISTEN
                        self.mark_pending = False
                        self.last_tts_end_ts = time.time()
                        # איפוס חשוב למערכת VAD
                        self.last_voice_ts = 0
                        self.voice_in_row = 0
                        logger.info("🎤 STATE -> LISTENING | buffer_reset")
                    elif mark_name.startswith("heartbeat_"):
                        # אישור keepalive - התעלם
                        pass
                    continue

                if et == "stop":
                    logger.info(f"WS_STOP sid={self.stream_sid} rx={self.rx} tx={self.tx}")
                    # ✅ CRITICAL: סיכום שיחה בסיום
                    self._finalize_call_on_stop()
                    # 🔥 SESSION LIFECYCLE: Call atomic close_session instead of manual cleanup
                    self.close_session("twilio_stop_event")
                    break

        except ConnectionClosed as e:
            logger.info(f"📞 WS_CLOSED sid={self.stream_sid} rx={self.rx} tx={self.tx} reason=ConnectionClosed")
            # 🔥 SESSION LIFECYCLE: Call atomic close_session
            self.close_session("ws_connection_closed")
        except Exception as e:
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME_FATAL: Unhandled exception in main run loop
            # ═══════════════════════════════════════════════════════════════════════
            import traceback
            _orig_print(f"🔥 [REALTIME_FATAL] Unhandled exception in MediaStreamHandler.run: {e}", flush=True)
            _orig_print(f"🔥 [REALTIME_FATAL] call_sid={self.call_sid}, stream_sid={self.stream_sid}", flush=True)
            traceback.print_exc()
            logger.error(f"[REALTIME_FATAL] Exception in run loop: {e}")
            
            # Mark realtime as failed
            self.realtime_failed = True
            self._realtime_failure_reason = f"RUN_EXCEPTION: {type(e).__name__}"
        finally:
            # 🔥 P3-1: Release capacity slot in finally block (always executes)
            call_sid = getattr(self, 'call_sid', None)
            if call_sid:
                try:
                    from server.services.calls_capacity import release_call_slot
                    release_call_slot(call_sid)
                except Exception as cap_err:
                    logger.error(f"Failed to release capacity slot in finally: {cap_err}")
            
            # 🔥 BUILD 169: Enhanced disconnect logging
            session_id = getattr(self, '_call_session_id', 'N/A')
            call_duration = time.time() - getattr(self, 'call_start_time', time.time())
            business_id = getattr(self, 'business_id', 'N/A')
            
            # 🔥 PRODUCTION LOG: [CALL_END] - Always logged (WARNING level)
            call_sid = getattr(self, 'call_sid', None)
            if call_sid:
                # Calculate warnings/errors
                realtime_failed = getattr(self, 'realtime_failed', False)
                failure_reason = getattr(self, '_realtime_failure_reason', None)
                warnings_errors = []
                if realtime_failed:
                    warnings_errors.append(f"realtime_failed={failure_reason or 'unknown'}")
                if self.tx == 0 and call_sid:
                    warnings_errors.append("tx=0")
                
                warnings_str = ", ".join(warnings_errors) if warnings_errors else "none"
                logger.warning(f"[CALL_END] call_sid={call_sid} duration={call_duration:.1f}s warnings={warnings_str}")
            
            logger.info(f"📞 [{session_id}] CALL ENDED - duration={call_duration:.1f}s, business_id={business_id}, rx={self.rx}, tx={self.tx}")
            logger.info(f"[{session_id}] DISCONNECT - duration={call_duration:.1f}s, business={business_id}")
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 REALTIME STABILITY: Final metrics logging for every call
            # ═══════════════════════════════════════════════════════════════════════
            # Log realtime timings for analysis
            openai_connect_ms = getattr(self, '_metrics_openai_connect_ms', 0)
            first_greeting_audio_ms = getattr(self, '_metrics_first_greeting_audio_ms', 0)
            realtime_failed = getattr(self, 'realtime_failed', False)
            failure_reason = getattr(self, '_realtime_failure_reason', None) or 'N/A'
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 PART B FIX: Distinguish GHOST SESSION from REAL CALL
            # ═══════════════════════════════════════════════════════════════════════
            # Ghost session criteria:
            #   - call_sid is None (no START event received)
            #   - rx == 0 and tx == 0 (no audio traffic)
            #   - openai_connect_ms == 0 (never connected to OpenAI)
            # These are Twilio preflight/probe connections - NOT actual failures!
            # ═══════════════════════════════════════════════════════════════════════
            is_ghost_session = (
                self.call_sid is None and 
                self.rx == 0 and 
                self.tx == 0 and
                openai_connect_ms == 0 and
                first_greeting_audio_ms == 0
            )
            
            if self.tx == 0 and not realtime_failed:
                if is_ghost_session:
                    # GHOST SESSION: WS opened but Twilio never sent START event
                    # This is NOT a bug - just a preflight/probe connection
                    # Do NOT log as failure, do NOT set realtime_failed
                    _orig_print(f"📭 [REALTIME] Ghost WS session (no START, no traffic) – ignoring", flush=True)
                else:
                    # REAL CALL: START received (call_sid set) but tx=0 - this IS a bug!
                    _orig_print(f"⚠️ [REALTIME] SILENT_FAILURE_DETECTED: tx=0 but realtime_failed=False!", flush=True)
                    _orig_print(f"❌ [REALTIME_FALLBACK] Call {self.call_sid} had tx=0 (potential silent failure)", flush=True)
                    # Mark as failed with clear reason for diagnostics
                    realtime_failed = True
                    failure_reason = "TX_ZERO_REAL_CALL"
                    self.realtime_failed = True
                    self._realtime_failure_reason = failure_reason
            
            # Log metrics - include is_ghost flag for monitoring
            logger.debug(f"[METRICS] REALTIME_TIMINGS: call_sid={self.call_sid}, openai_connect_ms={openai_connect_ms}, first_greeting_audio_ms={first_greeting_audio_ms}, realtime_failed={realtime_failed}, reason={failure_reason}, tx={self.tx}, is_ghost={is_ghost_session}")
            
            # 🔥 GREETING OPTIMIZATION: Log complete timeline for latency analysis
            # Get TwiML timing from stream registry (set by webhook)
            twiml_ms = 0
            ws_start_offset_ms = 0
            call_direction = getattr(self, 'call_direction', 'unknown')
            
            if self.call_sid:
                try:
                    # Try to get webhook timing from stream registry
                    twiml_ts = stream_registry.get_metric(self.call_sid, 'twiml_ready_ts')
                    ws_connect_ts = stream_registry.get_metric(self.call_sid, 'ws_connect_ts')
                    
                    if twiml_ts and ws_connect_ts:
                        ws_start_offset_ms = int((ws_connect_ts - twiml_ts) * 1000)
                except Exception as e:
                    pass
            
            # Calculate greeting SLA result
            is_inbound = (call_direction == 'inbound')
            greeting_threshold = 1600 if is_inbound else 2000
            total_greeting_ms = openai_connect_ms + first_greeting_audio_ms
            sla_met = total_greeting_ms <= greeting_threshold and total_greeting_ms > 0
            
            if not is_ghost_session and total_greeting_ms > 0:
                # Log complete greeting timeline (only for real calls with greeting) - DEBUG ONLY
                if sla_met:
                    logger.debug(f"[GREETING_SLA_MET] {total_greeting_ms}ms (threshold={greeting_threshold}ms, direction={call_direction})")
                else:
                    logger.debug(f"[GREETING_SLA_FAILED] inbound={is_inbound} twiml_ms={twiml_ms} openai_ms={openai_connect_ms} greet_ms={first_greeting_audio_ms} total={total_greeting_ms}ms > {greeting_threshold}ms")
                
                # Unified timeline log for analysis - DEBUG ONLY
                logger.debug(f"[GREETING_TIMELINE] inbound={is_inbound} twiml_ms={twiml_ms} ws_start_offset_ms={ws_start_offset_ms} openai_connect_ms={openai_connect_ms} first_greeting_audio_ms={first_greeting_audio_ms} total={total_greeting_ms}ms sla_met={sla_met}")
                logger.info(f"[GREETING_TIMELINE] inbound={is_inbound} total={total_greeting_ms}ms sla_met={sla_met}")
            
            # ⚡ STREAMING STT: Close session at end of call
            self._close_streaming_stt()
            
            # 🔥 SESSION LIFECYCLE: Use atomic close_session for cleanup
            # This ensures single-source-of-truth cleanup even if finally block is hit without explicit close
            if not self.closed:
                self.close_session("finally_block_fallback")
            
            # 💰 CALCULATE AND LOG CALL COST
            if USE_REALTIME_API:
                self._calculate_and_log_cost()
            
            # 🔥 BUILD 331: OPENAI_USAGE_GUARD - Final logging regardless of exit path
            frames_sent = getattr(self, '_usage_guard_frames', 0)
            seconds_used = getattr(self, '_usage_guard_seconds', 0.0)
            limit_hit = getattr(self, '_usage_guard_limit_hit', False)
            limit_exceeded_flag = getattr(self, '_limit_exceeded', False)
            logger.info(f"🛡️ OPENAI_USAGE_GUARD: frames_sent={frames_sent}, estimated_seconds={seconds_used:.1f}, limit_exceeded={limit_hit or limit_exceeded_flag}")
            
            # 🔥 SESSION LIFECYCLE: close_session() already handled WebSocket close, no need to duplicate
            # Mark as ended
            if hasattr(self, 'call_sid') and self.call_sid:
                stream_registry.clear(self.call_sid)
        
        # Final cleanup
        logger.info(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    def _interrupt_speaking(self):
        """✅ FIXED: עצירה מיידית של דיבור הבוט - סדר פעולות נכון"""
        logger.info("🚨 INTERRUPT_START: Beginning full interrupt sequence")
        
        # ✅ STEP 1: שלח clear לטוויליו ראשון
        if not self.ws_connection_failed:
            try:
                self._tx_enqueue({"type": "clear"})
                logger.info("✅ CLEAR_SENT: Twilio clear command sent")
            except Exception as e:
                logger.error(f"⚠️ CLEAR_FAILED: {e}")
        
        # ✅ STEP 2: נקה את תור השידור אחר clear
        try:
            cleared_count = 0
            while not self.tx_q.empty():
                self.tx_q.get_nowait()
                cleared_count += 1
            if cleared_count > 0:
                logger.info(f"✅ TX_QUEUE_CLEARED: Removed {cleared_count} pending audio frames")
        except Exception as e:
            logger.error(f"⚠️ TX_CLEAR_FAILED: {e}")
        
        # ✅ STEP 3: עדכן מצבים
        self.state = STATE_LISTEN
        self.mark_pending = False
        self.last_voice_ts = 0
        self.voice_in_row = 0
        self.processing = False
        
        # ✅ STEP 4: רק בסוף - עדכן speaking=False
        self.speaking = False
        
        logger.info("✅ INTERRUPT_COMPLETE: Full interrupt sequence finished - ready to listen")

    # 🎯 עיבוד מבע פשוט וביטוח (ללא כפילויות)
    def _process_utterance_safe(self, pcm16_8k: bytes, conversation_id: int):
        """עיבוד מבע עם הגנה כפולה מפני לולאות"""
        # 🚀 REALTIME API: Skip Google STT/TTS completely in Realtime mode
        if USE_REALTIME_API:
            logger.info(f"⏭️ [REALTIME] Skipping Google STT/TTS - using Realtime API only")
            # Reset buffer and state to prevent accumulation
            if hasattr(self, 'buf'):
                self.buf.clear()
            self.processing = False
            self.state = STATE_LISTEN
            return
        
        # וודא שלא מעבדים את אותו ID פעמיים
        if conversation_id <= self.last_processing_id:
            logger.info(f"🚫 DUPLICATE processing ID {conversation_id} (last: {self.last_processing_id}) - SKIP")
            return
        
        self.last_processing_id = conversation_id
        
        # וודא שהמערכת לא מדברת כרגע
        if self.speaking:
            logger.info("🚫 Still speaking - cannot process new utterance")
            return
            
        logger.info(f"🎤 SAFE PROCESSING: conversation #{conversation_id}")
        self.state = STATE_THINK  # מעבר למצב חשיבה
        
        text = ""  # initialize to avoid unbound variable
        try:
            # PATCH 6: Safe ASR - never leaves empty
            try:
                # ⚡ PHASE 2: Use smart wrapper (streaming or single-request)
                text = self._hebrew_stt_wrapper(pcm16_8k) or ""
                logger.info(f"🎤 USER: {text}")
                
                # ✅ מדידת ASR Latency
                if hasattr(self, 'eou_timestamp'):
                    asr_latency = time.time() - self.eou_timestamp
                    self.last_stt_time = asr_latency  # ⚡ CRITICAL: Save for TOTAL_LATENCY calculation
                    if DEBUG: logger.debug(f"📊 ASR_LATENCY: {asr_latency:.3f}s (target: <0.7s)")
                    
            except Exception as e:
                logger.error(f"❌ STT ERROR: {e}")
                text = ""
            
            # ✅ SMART HANDLING: כשלא מבין - בשקט או "לא הבנתי" אחרי כמה ניסיונות
            if not text.strip():
                # ספירת כישלונות רצופים
                if not hasattr(self, 'consecutive_empty_stt'):
                    self.consecutive_empty_stt = 0
                self.consecutive_empty_stt += 1
                
                # אם 2 כישלונות ברצף - תגיד "לא הבנתי"
                if self.consecutive_empty_stt >= 2:
                    logger.info("🚫 MULTIPLE_EMPTY_STT: Saying 'didn't understand'")
                    self.consecutive_empty_stt = 0  # איפוס
                    try:
                        self._speak_simple("לא הבנתי, אפשר לחזור?")
                    except:
                        pass
                else:
                    logger.info("🚫 NO_SPEECH_DETECTED: Staying silent (attempt 1)")
                
                self.state = STATE_LISTEN
                self.processing = False
                return
            # ✅ איפוס מונה כישלונות - STT הצליח!
            if hasattr(self, 'consecutive_empty_stt'):
                self.consecutive_empty_stt = 0
            
            # ⚡ BUILD 117: REMOVED SHORT_UNCOMMON_WORD filter - trust Google STT!
            # If STT returned text, it's real speech. Don't reject valid words like "שוודי" or names like "שי"
            # Only reject if it's EXTREMELY short (1 char) which is likely noise
            if len(text.strip()) <= 1:
                logger.info(f"🚫 VERY_SHORT_TEXT: '{text}' (≤1 char) - likely noise")
                self.state = STATE_LISTEN
                self.processing = False
                return
            
            # PATCH 6: Anti-duplication on user text (14s window) - WITH DEBUG
            uh = zlib.crc32(text.strip().encode("utf-8"))
            if (self.last_user_hash == uh and 
                (time.time() - self.last_user_hash_ts) <= DEDUP_WINDOW_SEC):
                logger.info("🚫 DUPLICATE USER INPUT (ignored)")
                self.processing = False
                self.state = STATE_LISTEN
                return
            self.last_user_hash, self.last_user_hash_ts = uh, time.time()
            # Processing new user input")
            
            # 3. FAQ Fast-Path - Voice calls only (≤200 chars)
            # ⚡ Try FAQ matching BEFORE calling AgentKit for instant responses
            faq_match = None
            faq_start_time = time.time()
            if len(text) <= 200:  # Only short queries
                try:
                    from server.services.faq_engine import match_faq
                    business_id = getattr(self, 'business_id', None)
                    if business_id:
                        faq_match = match_faq(business_id, text, channel="voice")
                except Exception as e:
                    logger.error(f"⚠️ [FAQ_ERROR] {e}")
            
            # If FAQ matched - respond immediately and skip AgentKit!
            if faq_match:
                faq_ms = (time.time() - faq_start_time) * 1000
                logger.info(f"🚀 [FAQ_HIT] biz={getattr(self, 'business_id', '?')} intent={faq_match['intent_key']} score={faq_match['score']:.3f} method={faq_match['method']} ms={faq_ms:.0f}ms")
                reply = faq_match['answer']
                
                # Track as FAQ turn (no Agent SDK call)
                logger.info(f"🤖 [FAQ_RESPONSE] {reply[:100]}... (skipped Agent)")
                
                # Speak the FAQ answer and return to listening
                if reply and reply.strip():
                    self.conversation_history.append({
                        'user': text,
                        'bot': reply
                    })
                    self._speak_simple(reply)
                
                # Return to LISTEN state
                self.state = STATE_LISTEN
                self.processing = False
                logger.info(f"✅ [FAQ_COMPLETE] Returned to LISTEN (total: {(time.time() - faq_start_time)*1000:.0f}ms)")
                return
            else:
                # FAQ miss - proceed to AgentKit
                faq_ms = (time.time() - faq_start_time) * 1000
                logger.info(f"⏭️ [FAQ_MISS] No match found (search took {faq_ms:.0f}ms) → proceeding to AgentKit")
            
            # No FAQ match - proceed with AgentKit (normal flow)
            ai_processing_start = time.time()
            
            # ✅ השתמש בפונקציה המתקדמת עם מתמחה והמאגר הכולל!
            reply = self._ai_response(text)
            
            # ✅ FIXED: אם AI החזיר None (אין טקסט אמיתי) - אל תגיב!
            if reply is None:
                logger.info("🚫 AI_RETURNED_NONE: No response needed - returning to listen mode")
                self.processing = False
                self.state = STATE_LISTEN
                return
            
            # ✅ מניעת כפילויות משופרת - בדיקת 8 תשובות אחרונות (פחות רגיש)
            if not hasattr(self, 'recent_replies'):
                self.recent_replies = []
            
            # ✅ FIXED: מניעת כפילויות חכמה - רק כפילויות מרובות ממש
            # 🔥 BUILD 114: Normalize reply (handle dict responses from AgentKit)
            if isinstance(reply, dict):
                # Extract text from dict structure
                reply = reply.get('output', '') or reply.get('message', '') or str(reply)
                logger.warning(f"⚠️ AgentKit returned dict - extracted: '{reply[:50]}...'")
            reply_trimmed = reply.strip() if reply else ""
            exact_duplicates = [r for r in self.recent_replies if r == reply_trimmed]
            if len(exact_duplicates) >= 3:  # ✅ FIXED: רק אחרי 3 כפילויות מדויקות
                logger.info("🚫 EXACT DUPLICATE detected (3+ times) - adding variation")
                if "תודה" in text.lower():
                    reply = "בשמחה! יש לי עוד אפשרויות אם אתה מעוניין."
                else:
                    reply = reply + " או אפשר עוד פרטים?"
                reply_trimmed = reply.strip()
                
            # עדכן היסטוריה - שמור רק 8 אחרונות
            if reply_trimmed:  # ✅ רק אם יש תשובה אמיתית
                self.recent_replies.append(reply_trimmed)
            if len(self.recent_replies) > 8:
                self.recent_replies = self.recent_replies[-8:]
            
            # ✅ FIXED: רק אם יש תשובה אמיתית - דפס, שמור ודבר
            if reply and reply.strip():
                logger.info(f"🤖 BOT: {reply}")
                
                # ✅ מדידת AI Processing Time
                ai_processing_time = time.time() - ai_processing_start
                if DEBUG: logger.debug(f"📊 AI_PROCESSING: {ai_processing_time:.3f}s")
                
                # 5. הוסף להיסטוריה (שני מבנים - סנכרון)
                self.response_history.append({
                    'id': conversation_id,
                    'user': text,
                    'bot': reply,
                    'time': time.time()
                })
                
                # ✅ CRITICAL FIX: סנכרון conversation_history לזיכרון AI
                self.conversation_history.append({
                    'user': text,
                    'bot': reply
                })
                
                # ✅ שמירת תור שיחה במסד נתונים לזיכרון קבוע
                self._save_conversation_turn(text, reply)
                
                # ✨ 6. Customer Intelligence - זיהוי/יצירת לקוח וליד חכם
                self._process_customer_intelligence(text, reply)
                
                # 6. דבר רק אם יש מה לומר
                self._speak_simple(reply)
            else:
                logger.info("🚫 NO_VALID_RESPONSE: AI returned empty/None - staying silent")
                # לא דופסים, לא שומרים בהיסטוריה, לא מדברים
            
            # ✅ CRITICAL: חזור למצב האזנה אחרי כל תגובה!
            self.state = STATE_LISTEN
            logger.info(f"✅ RETURNED TO LISTEN STATE after conversation #{conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL Processing error: {e}")
            logger.info(f"   Text was: '{text}' ({len(text)} chars)")
            # ✅ תיקון קריטי: דבק לטראסבק ואל תקריס
            import traceback
            traceback.print_exc()
            # ✅ תגובת חירום מפורטת ומועילה
            try:
                self.state = STATE_SPEAK
                # 🔥 BUILD 200: Generic emergency response - works for ANY business type
                emergency_response = "מצטערת, לא שמעתי טוב. אפשר לחזור שוב בבקשה?"
                self._speak_with_breath(emergency_response)
                self.state = STATE_LISTEN
                logger.error(f"✅ RETURNED TO LISTEN STATE after error in conversation #{conversation_id}")
            except Exception as emergency_err:
                logger.error(f"❌ EMERGENCY RESPONSE FAILED: {emergency_err}")
                self.state = STATE_LISTEN
                # ✅ חזור למצב האזנה בכל מקרה


    # ✅ דיבור מתקדם עם סימונים לטוויליו
    def _speak_greeting(self, text: str):
        """⚡ TTS מהיר לברכה - ללא sleep!"""
        if not text:
            return
        
        # 🔒 HARD-CODED: ALWAYS protected - ZERO barge-in!
        word_count = len(text.split())
        self.long_response = True  # ✅ PERMANENTLY True - NEVER interrupt!
        logger.info(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        
        # 🚀 REALTIME API: Send greeting via Realtime API if enabled
        if USE_REALTIME_API:
            logger.info(f"🚀 [REALTIME] Sending greeting via Realtime API: '{text[:50]}...'")
            try:
                # ✅ FIX: Queue greeting text to be sent via Realtime API (non-blocking)
                # Queue is initialized in __init__ to avoid AttributeError
                try:
                    self.realtime_greeting_queue.put_nowait(text)
                    logger.info(f"✅ [REALTIME] Greeting queued for Realtime API")
                except queue.Full:
                    # Queue full - replace old greeting with new one
                    logger.warning(f"⚠️ [REALTIME] Greeting queue full, replacing...")
                    try:
                        self.realtime_greeting_queue.get_nowait()
                        self.realtime_greeting_queue.put_nowait(text)
                        logger.info(f"✅ [REALTIME] Greeting replaced in queue")
                    except:
                        logger.error(f"❌ [REALTIME] Failed to replace greeting - will fallback")
                        # Don't raise - fall through to Google TTS
                        pass
                except Exception as e:
                    logger.error(f"❌ [REALTIME] Failed to queue greeting: {e}")
                    # Don't raise - will try again on next attempt
                    pass
                else:
                    # Successfully queued - exit early
                    return
            except Exception as e:
                logger.error(f"❌ [REALTIME] Greeting queueing error: {e}")
                import traceback
                traceback.print_exc()
            
            # ✅ Realtime mode: Greeting will be sent by async loop, no Google TTS fallback
            logger.info(f"📭 [REALTIME] Greeting queued or will be retried by async loop")
            return
        
        # Google TTS (only when USE_REALTIME_API=False)
        logger.info(f"🔊 GREETING_TTS_START (Google): '{text[:50]}...'")
        
        try:
            # ⚡ בלי sleep - ברכה מיידית!
            tts_audio = self._hebrew_tts(text)
            if tts_audio and len(tts_audio) > 1000:
                logger.info(f"✅ GREETING_TTS_SUCCESS: {len(tts_audio)} bytes")
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
            else:
                logger.error("❌ GREETING_TTS_FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            logger.error(f"❌ GREETING_TTS_ERROR: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._send_beep(800)
            except:
                pass
            self._finalize_speaking()
    
    def _speak_simple(self, text: str):
        """TTS עם מעקב מצבים וסימונים"""
        if not text:
            return
        
        # 🚀 REALTIME API: Skip Google TTS completely in Realtime mode
        if USE_REALTIME_API:
            return
        
        # 🔥 BUILD 118: Defensive check (should be normalized already in _ai_response)
        # This is a safety net in case dict slips through
        if isinstance(text, dict):
            logger.warning(f"⚠️ DICT STILL HERE! Should have been normalized in _ai_response: {text}")
            if 'text' in text:
                text = text['text']
                logger.info(f"✅ Extracted text field: '{text}'")
            else:
                logger.error(f"❌ No 'text' field in dict - using fallback")
                text = "סליחה, לא הבנתי. אפשר לחזור?"
            
        if self.speaking:
            logger.info("🚫 Already speaking - stopping current and starting new")
            try:
                # ✅ FIXED: בצע interrupt מלא לפני התחלת TTS חדש
                self._interrupt_speaking()
                time.sleep(0.05)  # המתנה קצרה
            except Exception as e:
                logger.error(f"⚠️ Interrupt error (non-critical): {e}")
        
        # 🔒 HARD-CODED: ALWAYS protected - ZERO barge-in!
        word_count = len(text.split())
        self.long_response = True  # ✅ PERMANENTLY True - NEVER interrupt!
        logger.info(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        logger.info(f"🔊 TTS_START: '{text}'")
        
        # ⚡ BUILD 107: Save EOU timestamp for total latency calculation
        eou_saved = getattr(self, 'eou_timestamp', None)
        
        try:
            # ⚡ ULTRA-SPEED: No delay before TTS - immediately start speaking
            # time.sleep removed for minimum latency
                
            # 🔥 TTS SHORTENING DISABLED - User demand: complete sentences only!
            # User: "הוא עוצר באמצע משפטים ולא מסיים"
            # Previous logic cut at 150 chars - REMOVED to allow full responses
            if len(text) > 350:  # Safety limit only for extreme cases (novels)
                shortened = text[:350]
                # Try to end at sentence boundary ONLY for very long responses
                for delimiter in ['. ', '! ', '? ']:
                    last_sent = shortened.rfind(delimiter)
                    if last_sent > 250:  # Very high threshold
                        text = shortened[:last_sent + 1]
                        logger.info(f"🔪 TTS_SAFETY_CUT (sentence): {text}")
                        break
                else:
                    # Keep original text - don't cut!
                    logger.warning(f"⚠️ TTS_LONG_RESPONSE: {len(text)} chars (no cut)")
            
            # ⏱️ TTS timing instrumentation
            tts_start = time.time()
            
            # 🚫 Google TTS is DISABLED - OpenAI Realtime handles TTS natively
            # This code should never run when USE_REALTIME_API=True
            
            tts_audio = self._hebrew_tts(text)
            tts_generation_time = time.time() - tts_start
            if DEBUG: logger.debug(f"📊 TTS_GENERATION: {tts_generation_time:.3f}s")
            
            if tts_audio and len(tts_audio) > 1000:
                logger.info(f"🔊 TTS SUCCESS: {len(tts_audio)} bytes")
                send_start = time.time()
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
                send_time = time.time() - send_start
                if DEBUG: logger.debug(f"📊 TTS_SEND: {send_time:.3f}s (audio transmission)")
                
                # ⚡ BUILD 114: Detailed latency breakdown (EOU→first audio sent)
                if eou_saved:
                    turn_latency = send_start - eou_saved
                    total_latency = time.time() - eou_saved
                    stt_time = getattr(self, 'last_stt_time', 0.0)
                    ai_time = getattr(self, 'last_ai_time', 0.0)
                    
                    if DEBUG: logger.debug(f"📊 TURN_LATENCY: {turn_latency:.3f}s (EOU→TTS start, target: <1.2s)")
                    if DEBUG: logger.debug(f"📊 🎯 TOTAL_LATENCY: {total_latency:.3f}s (EOU→Audio sent, target: <2.0s)")
                    logger.info(f"[LATENCY] stt={stt_time:.2f}s, ai={ai_time:.2f}s, tts={tts_generation_time:.2f}s, total={total_latency:.2f}s")
                    
                    # Clear for next measurement
                    if hasattr(self, 'eou_timestamp'):
                        delattr(self, 'eou_timestamp')
            else:
                logger.error("🔊 TTS FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            logger.error(f"❌ TTS_ERROR: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._send_beep(800)
            except:
                pass
            self._finalize_speaking()
    
    def _tx_enqueue(self, item):
        """
        ⚡ BUILD 115.1: Enqueue with drop-oldest policy
        If queue is full, drop oldest frame and insert new one (Real-time > past)
        🔥 VERIFICATION #3: Block enqueue when session is closed
        🔥 NEW: Queue backlog monitoring - prevent overflow that causes "weird speech"
        """
        # 🔥 VERIFICATION #3: No enqueue after close
        if self.closed:
            return  # Silently drop - session is closing/closed
        
        # 🔥 NEW: BACKLOG GUARD - Monitor queue overflow (>200 frames = 4 seconds)
        # Large backlogs cause timing issues and weird bot behavior
        self._check_queue_backlog(self.tx_q, 'tx_q', threshold=200)
        
        # 🛑 BUILD 165: LOOP GUARD - Block all audio except "clear" when engaged
        # 🔥 BUILD 178: Disabled for outbound calls
        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
        if self._loop_guard_engaged and not is_outbound:
            if isinstance(item, dict) and item.get("type") == "clear":
                pass  # Allow clear commands through
            else:
                return  # Silently drop all other audio
        
        # 🔥 BARGE-IN: Block AI audio when user is speaking (allow "clear" and "mark" commands)
        if self.barge_in_active:
            if isinstance(item, dict) and item.get("type") in ("clear", "mark"):
                pass  # Allow clear/mark commands through
            else:
                return  # Silently drop AI audio during barge-in
        try:
            self.tx_q.put_nowait(item)
        except queue.Full:
            # Drop oldest frame
            try:
                _ = self.tx_q.get_nowait()
            except queue.Empty:
                pass
            # Try again
            try:
                self.tx_q.put_nowait(item)
            except queue.Full:
                # Throttled logging - max once per 2 seconds
                now = time.monotonic()
                if now - self._last_overflow_log > 2.0:
                    logger.warning("⚠️ tx_q full (drop oldest)")
                    self._last_overflow_log = now
    
    def _finalize_speaking(self):
        """סיום דיבור עם חזרה להאזנה"""
        self.speaking = False
        self.long_response = False  # ⚡ BUILD 109: Reset flag
        self.last_tts_end_ts = time.time()
        self.state = STATE_LISTEN
        self.last_voice_ts = 0  # איפוס למערכת VAD
        self.voice_in_row = 0
        logger.info("🎤 SPEAKING_END -> LISTEN STATE | buffer_reset")

    def _send_pcm16_as_mulaw_frames_with_mark(self, pcm16_8k: bytes):
        """שליחת אודיו עם סימון לטוויליו וברג-אין"""
        if not self.stream_sid or not pcm16_8k:
            self._finalize_speaking()
            return
            
        # CLEAR לפני שליחה
        self._ws_send(json.dumps({"event":"clear","streamSid":self.stream_sid}))
        
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        total_frames = len(mulaw) // FR
        
        if DEBUG: logger.debug(f"🔊 TTS_FRAMES: {total_frames} frames ({total_frames * 20}ms)")
        
        for i in range(0, len(mulaw), FR):
            # בדיקת ברג-אין
            if not self.speaking:
                logger.info(f"🚨 BARGE-IN! Stopped at frame {frames_sent}/{total_frames}")
                # IMMEDIATE clear for instant interruption
                self._tx_enqueue({"type": "clear"})
                self._finalize_speaking()
                return
                
            # 🔥 FIX: Use tx_q with backpressure to prevent "Send queue full" overflow!
            # Wait if queue is too full (>810 frames = 90% of maxsize=900)
            HIGH_WATERMARK = 810
            while self.tx_q.qsize() > HIGH_WATERMARK and self.speaking:
                time.sleep(0.005)  # 5ms backpressure wait
            
            # Enqueue frame via tx_q (paced by _tx_loop at 20ms/frame)
            frame = mulaw[i:i+FR].ljust(FR, b'\x00')
            payload = base64.b64encode(frame).decode()
            self._tx_enqueue({
                "type": "media",
                "payload": payload
            })
            frames_sent += 1
        
        # הוסף 200ms שקט בסוף
        silence_frames = 10  # 200ms @ 20ms per frame  
        silence_mulaw = b'\x00' * FR
        for _ in range(silence_frames):
            if not self.speaking:
                break
            payload = base64.b64encode(silence_mulaw).decode()
            self._tx_enqueue({
                "type": "media",
                "payload": payload
            })
        
        # שלח סימון לטוויליו via tx_q
        self.mark_pending = True
        self.mark_sent_ts = time.time()
        self._tx_enqueue({
            "type": "mark",
            "name": "assistant_tts_end"
        })
        self._finalize_speaking()

    def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
        """
        ⚡ BUILD 168.1 FIX: שליחת אודיו דרך tx_q עם תזמון נכון
        הבעיה הישנה: שלחנו ישירות ללא sleep, מה שהציף את Twilio וגרם לנפילות סאונד!
        הפתרון: שליחה דרך tx_q שמנוהל ע"י _tx_loop עם תזמון מדויק של 20ms לפריים
        """
        if not self.stream_sid or not pcm16_8k:
            return
            
        # CLEAR לפני שליחה
        self._tx_enqueue({"type": "clear"})
        
        mulaw = audioop.lin2ulaw(pcm16_8k, 2)
        FR = 160  # 20ms @ 8kHz
        frames_sent = 0
        total_frames = len(mulaw) // FR
        
        # ⚡ Backpressure threshold - wait if queue is >90% full
        HIGH_WATERMARK = 810  # 90% of maxsize=900
        
        for i in range(0, len(mulaw), FR):
            chunk = mulaw[i:i+FR]
            if len(chunk) < FR:
                chunk = chunk.ljust(FR, b'\x00')  # Pad last frame
                
            payload = base64.b64encode(chunk).decode("ascii")
            
            # 🔥 FIX: Backpressure - wait if queue is too full
            while self.tx_q.qsize() > HIGH_WATERMARK and self.speaking:
                time.sleep(0.005)  # 5ms backpressure wait
            
            # Enqueue frame via tx_q (paced by _tx_loop at 20ms/frame)
            self._tx_enqueue({
                "type": "media",
                "payload": payload
            })
            frames_sent += 1
        
        # ⚡ Only log if there was an issue
        if frames_sent < total_frames:
            logger.warning(f"⚠️ Audio incomplete: {frames_sent}/{total_frames} frames sent")

    def _send_beep(self, ms: int):
        """צפצוף פשוט"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        self._send_pcm16_as_mulaw_frames(bytes(out))
    
    def _beep_pcm16_8k(self, ms: int) -> bytes:
        """יצירת צפצוף PCM16 8kHz"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        for n in range(samples):
            val = int(amp * math.sin(2*math.pi*440*n/SR))
            out.extend(val.to_bytes(2, "little", signed=True))
        return bytes(out)
    
    def _process_audio_for_stt(self, pcm16_8k: bytes) -> bytes:
        """🎵 עיבוד אודיו איכותי לפני STT: AGC, פילטרים, resample ל-16kHz"""
        try:
            import numpy as np
            from scipy import signal
        except ImportError:
            # numpy/scipy לא מותקנים - החזר כמו שזה
            logger.warning("⚠️ numpy/scipy not available - using raw audio")
            return pcm16_8k
        
        try:
            
            # המר ל-numpy array
            audio_int16 = np.frombuffer(pcm16_8k, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0  # normalize to [-1, 1]
            
            # ✅ 1. DC-offset removal
            audio_float = audio_float - float(np.mean(audio_float))
            
            # ✅ 2. High-pass filter (100Hz) - מטאטא זמזום
            sos_hp = signal.butter(4, 100, btype='high', fs=8000, output='sos')
            audio_float = np.array(signal.sosfilt(sos_hp, audio_float), dtype=np.float32)
            
            # ✅ 3. Low-pass filter (3.6kHz) - טלפוני רגיל  
            sos_lp = signal.butter(4, 3600, btype='low', fs=8000, output='sos')
            audio_float = np.array(signal.sosfilt(sos_lp, audio_float), dtype=np.float32)
            
            # ✅ 4. AGC עדין - נרמול לטווח מטרה (-20dBFS ≈ 0.1)
            rms_squared = np.mean(audio_float * audio_float)
            rms = float(np.sqrt(rms_squared))
            if rms > 0.001:  # אם יש אודיו אמיתי
                target_rms = 0.1  # -20dBFS
                gain = min(target_rms / rms, 3.0)  # מגביל גיין ל-3x
                audio_float = np.array(audio_float * gain, dtype=np.float32)
            
            # ✅ 5. Clipping protection
            audio_float = np.clip(audio_float, -0.95, 0.95)
            
            # ✅ 6. Resample 8kHz → 16kHz (Whisper עובד טוב יותר ב-16k)
            audio_16k = signal.resample(audio_float, len(audio_float) * 2)
            
            # המר חזרה ל-int16
            audio_16k_int16 = np.array(audio_16k * 32767, dtype=np.int16)
            
            return audio_16k_int16.tobytes()
            
        except ImportError:
            logger.warning(f"⚠️ numpy/scipy not available - using raw audio")
            return pcm16_8k
        except Exception as e:
            logger.error(f"⚠️ Audio processing failed, using raw audio: {e}")
            # Fallback: החזר אודיו כמו שזה
            try:
                import numpy as np
                from scipy import signal
                audio_int16 = np.frombuffer(pcm16_8k, dtype=np.int16)
                audio_float = audio_int16.astype(np.float32) / 32768.0
                audio_16k = signal.resample(audio_float, len(audio_float) * 2)
                audio_16k_int16 = np.array(audio_16k * 32767, dtype=np.int16)
                return audio_16k_int16.tobytes()
            except Exception as e2:
                logger.error(f"⚠️ Even simple resample failed: {e2}")
                # Ultimate fallback: duplicate samples (crude but works)
                return pcm16_8k + pcm16_8k  # Double the data for "16kHz"

    async def _stt_fallback_async(self, audio_data: bytes) -> str:
        """
        ⚡ BUILD 115: Async wrapper for fallback STT
        Runs _hebrew_stt in thread pool without blocking the event loop
        """
        # 🚀 REALTIME API: Skip Google STT completely in Realtime mode
        if USE_REALTIME_API:
            return ""
        
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.exec, self._hebrew_stt, audio_data)
        except Exception as e:
            logger.error(f"❌ [STT_FALLBACK_ASYNC] Failed: {e}")
            return ""
    
    def _stt_fallback_nonblocking(self, audio_data: bytes) -> None:
        """
        ⚡ BUILD 115: Non-blocking wrapper for fallback STT (sync → async)
        Submits work to thread pool and returns immediately.
        Result is delivered via callback to avoid blocking.
        """
        # 🚀 REALTIME API: Skip Google STT completely in Realtime mode
        if USE_REALTIME_API:
            return
        
        # Submit to thread pool
        fut = self.exec.submit(self._hebrew_stt, audio_data)
        
        # When done, deliver result back to event loop safely
        def _on_done(f):
            try:
                text = f.result()
            except Exception as e:
                logger.error(f"❌ [STT_FALLBACK_NB] Failed: {e}")
                text = ""
            
            # If there's a loop and events queue, use it
            if self.loop and self.events_q:
                events_q = self.events_q  # Type hint helper
                self.loop.call_soon_threadsafe(
                    lambda: events_q.put_nowait(("stt_final_text", text))
                )
            else:
                # Fallback: direct callback (sync mode)
                logger.info(f"🎤 [STT_FALLBACK_NB] Result: {text[:50] if text else '(empty)'}")
        
        fut.add_done_callback(_on_done)

    def _hebrew_stt_wrapper(self, pcm16_8k: bytes, on_partial_cb=None) -> str:
        """
        🎯 Smart wrapper: streaming (collects from dispatcher) → fallback to single-request
        """
        session = _get_session(self.call_sid) if self.call_sid else None
        
        if not USE_STREAMING_STT or not session:
            # Single-request mode (existing)
            return self._hebrew_stt(pcm16_8k)
        
        try:
            # Streaming mode: collect results from dispatcher
            # Audio is already being fed to session in WS loop
            # Just collect what's been accumulated
            logger.info(f"⏱️ [STT_STREAM] Calling _utterance_end...")
            utt_start = time.time()
            result = self._utterance_end()
            utt_duration = time.time() - utt_start
            logger.info(f"⏱️ [STT_STREAM] _utterance_end took {utt_duration:.3f}s, result: '{result[:50] if result else '(empty)'}'")
            
            # ✅ FIX: Fallback on empty results
            if not result or not result.strip():
                logger.warning("⚠️ [STT] Streaming returned empty → fallback to single")
                fallback_start = time.time()
                fallback_result = self._hebrew_stt(pcm16_8k)
                fallback_duration = time.time() - fallback_start
                logger.info(f"⏱️ [STT_FALLBACK] Single-request took {fallback_duration:.3f}s, result: '{fallback_result[:50] if fallback_result else '(empty)'}'")
                return fallback_result
                
            return result
            
        except Exception as e:
            # Fallback to single-request on exception
            logger.error(f"⚠️ [STT] Streaming failed → fallback to single. err={e}")
            import traceback
            traceback.print_exc()
            return self._hebrew_stt(pcm16_8k)

    def _hebrew_stt(self, pcm16_8k: bytes) -> str:
        """🔥 BUILD 314: LEGACY CODE - Never used when USE_REALTIME_API=True
        OpenAI Realtime API handles ALL transcription via gpt-4o-transcribe.
        This is kept only for backwards compatibility.
        """
        # 🚀 REALTIME API: Skip Google STT completely - use gpt-4o-transcribe via Realtime API
        if USE_REALTIME_API:
            return ""
        
        try:
            logger.info(f"🎵 STT_PROCEED: Processing {len(pcm16_8k)} bytes with Google STT (audio validated)")
            
            # ✅ FIXED: בדיקת איכות אודיו מתקדמת - מניעת עיבוד של רעש/שקט
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            if DEBUG: logger.debug(f"📊 AUDIO_QUALITY_CHECK: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # 🔥 BUILD 164B: BALANCED NOISE GATE - Filter noise, allow quiet speech
            
            # 1. Basic amplitude check - balanced threshold
            if max_amplitude < 100:  # Back to reasonable threshold for quiet speech
                logger.info(f"🚫 STT_BLOCKED: Audio too quiet (max_amplitude={max_amplitude} < 100)")
                return ""
            
            # 2. RMS energy check - balanced (typical speech is 180-500)
            if rms < 80:  # Allow soft speech while filtering pure noise
                logger.info(f"🚫 STT_BLOCKED: Audio below noise threshold (rms={rms} < 80)")
                return ""
            
            # 3. Duration check - slightly longer minimum
            if duration < 0.18:  # 180ms minimum for meaningful audio
                logger.info(f"🚫 STT_BLOCKED: Audio too short ({duration:.2f}s < 0.18s)")
                return ""
            
            # 4. 🔥 BUILD 164B: BALANCED noise detection with variance/ZCR
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                zero_crossings = np.sum(np.diff(np.sign(pcm_array)) != 0) / len(pcm_array)
                
                # Block pure silence and monotonic sounds (DTMF tones, carrier noise)
                # But allow normal speech variance (200k+)
                if energy_variance < 200000:  # Back to balanced threshold
                    logger.info(f"🚫 STT_BLOCKED: Low energy variance - likely noise (variance={energy_variance:.0f})")
                    return ""
                
                # Block DTMF tones (very low ZCR) but allow speech
                if zero_crossings < 0.01 or zero_crossings > 0.3:  # Relaxed range
                    logger.info(f"🚫 STT_BLOCKED: Abnormal ZCR - likely noise/tone (zcr={zero_crossings:.3f})")
                    return ""
                
                logger.info(f"✅ AUDIO_VALIDATED: amp={max_amplitude}, rms={rms}, var={int(energy_variance)}, zcr={zero_crossings:.3f}")
                
            except ImportError:
                logger.warning("⚠️ numpy not available - skipping advanced audio validation")
            except Exception as numpy_error:
                logger.error(f"⚠️ Advanced audio analysis failed: {numpy_error} - using basic validation")
                # אם נכשלנו בבדיקות מתקדמות - המשך עם בסיסיות
            
            # 🚫 Google STT is DISABLED - use Whisper only
            if DISABLE_GOOGLE:
                logger.info("🚫 Google STT is DISABLED - using Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            # Even if not disabled, warn and use Whisper
            logger.warning("⚠️ Google STT should not be used - using Whisper fallback")
            return self._whisper_fallback(pcm16_8k)
                
        except Exception as e:
            logger.error(f"❌ STT_ERROR: {e}")
            return ""
    
    def _whisper_fallback_validated(self, pcm16_8k: bytes) -> str:
        """🔥 BUILD 314: LEGACY CODE - Never used when USE_REALTIME_API=True
        OpenAI Realtime API handles ALL transcription via gpt-4o-transcribe.
        This is kept only for backwards compatibility if someone sets USE_REALTIME_API=False.
        """
        # 🚀 REALTIME API: Skip Whisper completely - use gpt-4o-transcribe via Realtime API
        if USE_REALTIME_API:
            return ""
        
        try:
            logger.info(f"🔄 WHISPER_VALIDATED: Processing {len(pcm16_8k)} bytes with fabrication prevention")
            
            # ✅ בדיקת איכות אודיו חמורה יותר
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            if DEBUG: logger.debug(f"📊 AUDIO_VALIDATION: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # 🔥 BUILD 164B: BALANCED noise gate for Whisper
            if max_amplitude < 200 or rms < 120:  # Balanced thresholds - allow quiet speech
                logger.info(f"🚫 WHISPER_BLOCKED: Audio too weak (amp={max_amplitude}<200, rms={rms}<120)")
                return ""  # Don't let Whisper hallucinate!
            
            if duration < 0.3:  # Less than 300ms
                logger.info("🚫 WHISPER_BLOCKED: Audio too short - likely noise")
                return ""
            
            # Check for monotonic energy (noise vs speech)
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                if energy_variance < 1000000:  # Balanced threshold
                    logger.info(f"🚫 WHISPER_BLOCKED: Low energy variance ({energy_variance:.0f}) - background noise")
                    return ""
            except:
                pass  # If check fails - continue
            
            from server.services.lazy_services import get_openai_client
            client = get_openai_client()
            if not client:
                logger.error("❌ OpenAI client not available")
                return ""
            
            # Resample to 16kHz for Whisper
            pcm16_16k = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)[0]
            logger.info(f"🔄 RESAMPLED: {len(pcm16_8k)} bytes @ 8kHz → {len(pcm16_16k)} bytes @ 16kHz")
            
            # ✅ Whisper עם פרמטרים חמורים נגד המצאות
            import tempfile
            import wave
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    wav_file.writeframes(pcm16_16k)
                
                with open(temp_wav.name, 'rb') as audio_file:
                    # ✅ FIXED: פרמטרים חמורים נגד המצאה
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he",  # חייב עברית
                        prompt="זוהי שיחת טלפון בעברית. תמלל רק דיבור ברור. אם אין דיבור ברור - החזר ריק.",  # הנחיה חמורה!
                        temperature=0.0  # 🔥 FIX: Temperature 0.0 for maximum accuracy
                    )
            
            import os
            os.unlink(temp_wav.name)
            
            result = transcript.text.strip()
            
            # ✅ FINAL validation - בדיקת תוצאה חשודה
            if not result or len(result) < 2:
                logger.info("✅ WHISPER_VALIDATED: Empty/minimal result - good!")
                return ""
            
            # 🛡️ BUILD 149: ENGLISH HALLUCINATION FILTER (refined)
            # Only block when text is PURELY English (hallucination) - allow mixed Hebrew/English
            import re
            hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', result))
            english_chars = len(re.findall(r'[a-zA-Z]', result))
            total_chars = max(hebrew_chars + english_chars, 1)
            
            # If no Hebrew at all and has English - likely hallucination
            if hebrew_chars == 0 and english_chars > 3:
                logger.info(f"🚫 WHISPER_PURE_ENGLISH: '{result}' has no Hebrew - blocking fabrication")
                return ""
            
            # 🛡️ Block PURE English fabrication phrases (only when no Hebrew present)
            pure_english_hallucinations = [
                "thank you", "i'll take", "pistol", "gun", "little pistol",
                "right here", "just a moment"
            ]
            result_lower = result.lower()
            if hebrew_chars == 0:
                for hallucination in pure_english_hallucinations:
                    if hallucination in result_lower:
                        logger.info(f"🚫 WHISPER_ENGLISH_PHRASE: Found '{hallucination}' in '{result}' - blocking")
                        return ""
            
            # 🔥 BUILD 164: ENHANCED anti-hallucination for Whisper
            # Block ultra-short results (likely noise transcription)
            if len(result) <= 1:
                logger.info(f"🚫 WHISPER_TOO_SHORT: Result '{result}' - blocking")
                return ""
            
            # Block common noise hallucinations (Hebrew + English)
            noise_hallucinations = [
                "uh", "eh", "mmm", "hmm", "אה", "הממ", "אמ", "הא",
                ".", "..", "...", "-", "—", " "
            ]
            if result.lower().strip() in noise_hallucinations:
                logger.info(f"🚫 WHISPER_NOISE_HALLUCINATION: '{result}' - blocking")
                return ""
            
            # Block suspicious single Hebrew words that Whisper invents from noise
            suspicious_single_words = [
                "תודה", "נהדר", "נהדרת", "מעולה", "בראבו",
                "כן", "לא", "אוקיי", "טוב", "סבבה",
                "שלום", "היי", "ביי", "בסדר"
            ]
            words = result.split()
            if len(words) == 1 and result.strip() in suspicious_single_words:
                logger.info(f"🚫 WHISPER_SUSPICIOUS_SINGLE: '{result}' - likely fabrication")
                return ""
            
            logger.info(f"✅ WHISPER_VALIDATED_SUCCESS: '{result}'")
            return result
            
        except Exception as e:
            logger.error(f"❌ WHISPER_VALIDATED_ERROR: {e}")
            return ""
    
    def _whisper_fallback(self, pcm16_8k: bytes) -> str:
        """🔥 BUILD 164: REDIRECT to validated version for all Whisper calls"""
        # Always use the validated version with aggressive noise filtering
        return self._whisper_fallback_validated(pcm16_8k)
    
    def _load_business_prompts(self, channel: str = 'calls') -> str:
        """טוען פרומפטים מהדאטאבייס לפי עסק - לפי ההנחיות המדויקות"""
        try:
            # ✅ CRITICAL: All DB queries need app_context in Cloud Run/ASGI!
            from server.models_sql import Business, BusinessSettings
            
            app = _get_flask_app()  # ✅ Use singleton
            with app.app_context():
                # ✅ BUILD 100 FIX: זיהוי business_id לפי מספר טלפון - שימוש ב-phone_e164
                if not self.business_id and self.phone_number:
                    # חפש עסק לפי מספר הטלפון (phone_e164 = העמודה האמיתית)
                    business = Business.query.filter(
                        Business.phone_e164 == self.phone_number
                    ).first()
                    if business:
                        self.business_id = business.id
                        logger.info(f"✅ זיהוי עסק לפי טלפון {self.phone_number}: {business.name}")
                
                # ✅ BUILD 152: אם אין עדיין business_id, השתמש בfallback דינמי (ללא hardcoded phone)
                if not self.business_id:
                    from server.services.business_resolver import resolve_business_with_fallback
                    # ✅ BUILD 152: Use actual to_number if available, otherwise get first active business
                    lookup_phone = self.to_number or self.phone_number or None
                    self.business_id, status = resolve_business_with_fallback('twilio_voice', lookup_phone)
                    logger.info(f"✅ שימוש בעסק fallback: business_id={self.business_id} ({status})")
                
                if not self.business_id:
                    logger.error("❌ לא נמצא עסק - שימוש בפרומפט ברירת מחדל כללי")
                    return "אתה נציג שירות מקצועי. דבר בעברית, היה קצר ומועיל."
                
                # טען פרומפט מ-BusinessSettings
                settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
                business = Business.query.get(self.business_id)
            
            if settings and settings.ai_prompt:
                try:
                    # נסה לפרסר JSON (פורמט חדש עם calls/whatsapp)
                    import json
                    if settings.ai_prompt.startswith('{'):
                        prompt_data = json.loads(settings.ai_prompt)
                        prompt_text = prompt_data.get(channel, prompt_data.get('calls', ''))
                        if prompt_text:
                            logger.info(f"AI_PROMPT loaded tenant={self.business_id} channel={channel}")
                            return prompt_text
                    else:
                        # פרומפט יחיד (legacy)
                        logger.info(f"✅ טען פרומפט legacy מדאטאבייס לעסק {self.business_id}")
                        return settings.ai_prompt
                except Exception as e:
                    logger.warning(f"⚠️ שגיאה בפרסור פרומפט JSON: {e}")
                    # fallback לפרומפט כטקסט רגיל
                    return settings.ai_prompt
            
            # אם אין ב-BusinessSettings, בדוק את business.system_prompt
            if business and business.system_prompt:
                logger.info(f"✅ טען פרומפט מטבלת businesses לעסק {self.business_id}")
                return business.system_prompt
                
            logger.warning(f"⚠️ לא נמצא פרומפט לעסק {self.business_id} - שימוש בברירת מחדל כללי")
            return "אתה נציג שירות מקצועי. דבר בעברית, היה קצר ומועיל."
            
        except Exception as e:
            logger.error(f"❌ שגיאה בטעינת פרומפט מדאטאבייס: {e}")
            return "אתה נציג שירות מקצועי. דבר בעברית, היה קצר ומועיל."

    def _identify_business_and_get_greeting(self) -> tuple:
        """⚡ זיהוי עסק + ברכה + הגדרות שיחה בשאילתה אחת - חוסך 70% זמן!"""
        try:
            from server.models_sql import Business, BusinessSettings
            from sqlalchemy import or_
            
            to_number = getattr(self, 'to_number', None)
            t_start = time.time()
            
            # 🔒 BUILD 174 SECURITY: For outbound calls, use explicit business_id (NOT phone resolution)
            # This prevents tenant cross-contamination when multiple businesses share same Twilio number
            call_direction = getattr(self, 'call_direction', 'inbound')
            outbound_business_id = getattr(self, 'outbound_business_id', None)
            
            app = _get_flask_app()
            with app.app_context():
                business = None
                
                if call_direction == 'outbound' and outbound_business_id:
                    # 🔒 OUTBOUND CALL: Use explicit business_id (NOT phone-based resolution)
                    logger.info(f"🔒 OUTBOUND CALL: Using explicit business_id={outbound_business_id} (NOT phone-based resolution)")
                    try:
                        business_id_int = int(outbound_business_id)
                        business = Business.query.get(business_id_int)
                        if business:
                            logger.info(f"✅ OUTBOUND: Loaded business {business.name} (id={business.id})")
                        else:
                            logger.error(f"❌ OUTBOUND: Business {outbound_business_id} NOT FOUND - security violation?")
                            return (None, None)
                    except (ValueError, TypeError) as e:
                        logger.error(f"❌ OUTBOUND: Invalid business_id={outbound_business_id}: {e}")
                        return (None, None)
                else:
                    # INBOUND CALL: Use phone-based resolution
                    logger.info(f"⚡ ULTRA-FAST: זיהוי עסק + ברכה + הגדרות בשאילתה אחת: to_number={to_number}")
                    
                    if to_number:
                        normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
                        
                        business = Business.query.filter(
                            or_(
                                Business.phone_e164 == to_number,
                                Business.phone_e164 == normalized_phone
                            )
                        ).first()
                        
                        if business:
                            logger.info(f"✅ מצא עסק: {business.name} (id={business.id})")
                    
                    if not business:
                        from server.services.business_resolver import resolve_business_with_fallback
                        to_num_safe = to_number or ''
                        resolved_id, status = resolve_business_with_fallback('twilio_voice', to_num_safe)
                        logger.warning(f"[CALL-WARN] No business for {to_number}, resolver: biz={resolved_id} ({status})")
                        if resolved_id:
                            business = Business.query.get(resolved_id)
                
                if business:
                    self.business_id = business.id
                    self.business_name = business.name or "העסק שלנו"
                    greeting = business.greeting_message or None
                    business_name = self.business_name
                    
                    # 🎯 MASTER DIRECTIVE 7: CALL DIRECTION VERIFICATION - Log at call start
                    call_direction = getattr(self, 'call_direction', 'inbound')
                    # Use call_config if already loaded (avoids redundant DB query)
                    call_goal = getattr(self.call_config, 'call_goal', 'lead_only') if hasattr(self, 'call_config') else 'lead_only'
                    
                    logger.info(
                        f"[BUILD] SIMPLE_MODE={SIMPLE_MODE} business_id={self.business_id} "
                        f"direction={call_direction} goal={call_goal}"
                    )
                    
                    if greeting:
                        greeting = greeting.replace("{{business_name}}", business_name)
                        greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                        logger.info(f"[CALL-START] biz={self.business_id}, greeting='{greeting[:50]}...'")
                    else:
                        logger.info(f"[CALL-START] biz={self.business_id}, NO GREETING")
                    
                    # 🔥 BUILD 172: Load CallConfig with all settings
                    self.call_config = load_call_config(self.business_id)
                    
                    # 🔥 BUILD 178: OUTBOUND CALLS - Disable all call control settings!
                    # Outbound calls should ONLY follow the AI prompt, not call control settings
                    if call_direction == 'outbound':
                        logger.info(f"📤 [OUTBOUND] Disabling all call control settings - AI follows prompt only!")
                        # Force settings that won't interfere with outbound calls
                        self.bot_speaks_first = True  # AI always speaks first in outbound
                        self.auto_end_after_lead_capture = False  # Don't auto-end
                        self.auto_end_on_goodbye = False  # Don't auto-end on goodbye
                        self.silence_timeout_sec = 20  # 🔥 FIX: 20s timeout (watchdog handles disconnect)
                        self.silence_max_warnings = 0  # 🔥 FIX: No warnings - watchdog only
                        self.smart_hangup_enabled = False  # Disable smart hangup
                        self.required_lead_fields = []  # No required fields
                        self._loop_guard_engaged = False  # Ensure loop guard is off
                        self._max_consecutive_ai_responses = 20  # Very high limit
                        logger.warning(f"   ✓ auto_end=OFF, silence_timeout=20s, max_warnings=0, smart_hangup=OFF")
                    else:
                        # Copy config values to instance variables for backward compatibility (INBOUND only)
                        # 🔥 MASTER FIX: bot_speaks_first is now ALWAYS True (hardcoded) - ignore DB value
                        self.bot_speaks_first = True  # HARDCODED: Always True (deprecated: self.call_config.bot_speaks_first)
                        self.auto_end_after_lead_capture = self.call_config.auto_end_after_lead_capture
                        self.auto_end_on_goodbye = self.call_config.auto_end_on_goodbye
                        self.silence_timeout_sec = self.call_config.silence_timeout_sec
                        self.silence_max_warnings = self.call_config.silence_max_warnings
                        self.smart_hangup_enabled = self.call_config.smart_hangup_enabled
                        self.required_lead_fields = self.call_config.required_lead_fields
                        # 🔥 BUILD 309: SIMPLE_MODE settings
                        self.call_goal = self.call_config.call_goal  # "lead_only" or "appointment"
                        self.confirm_before_hangup = self.call_config.confirm_before_hangup  # Always confirm before disconnect
                    
                    # 🛡️ BUILD 168.5 FIX: Set is_playing_greeting IMMEDIATELY when bot_speaks_first is True
                    if self.bot_speaks_first:
                        self.is_playing_greeting = True
                        logger.info(f"🛡️ [GREETING PROTECT] is_playing_greeting=True (early, blocking audio input)")
                    
                    # 🔥 CRITICAL: Mark settings as loaded to prevent duplicate loading
                    self._call_settings_loaded = True
                    
                    t_end = time.time()
                    logger.info(f"⚡ BUILD 172: CallConfig loaded in {(t_end-t_start)*1000:.0f}ms")
                    logger.info(f"   bot_speaks_first={self.bot_speaks_first}, auto_end_goodbye={self.auto_end_on_goodbye}")
                    logger.info(f"   auto_end_lead={self.auto_end_after_lead_capture}, silence_timeout={self.silence_timeout_sec}s")
                    logger.info(f"🔍 [CONFIG] required_lead_fields={self.required_lead_fields}")
                    logger.info(f"🔍 [CONFIG] smart_hangup_enabled={self.smart_hangup_enabled}")
                    logger.info(f"🔍 [BUILD 309] call_goal={getattr(self, 'call_goal', 'lead_only')}, confirm_before_hangup={getattr(self, 'confirm_before_hangup', True)}")
                    
                    # 🔥 COMPREHENSIVE LOGGING: Show SIMPLE_MODE, direction, and goal at call start
                    call_direction = getattr(self, 'call_direction', 'inbound')
                    logger.info(f"📞 [BUILD] SIMPLE_MODE={SIMPLE_MODE} direction={call_direction} goal={getattr(self, 'call_goal', 'lead_only')}")
                    
                    return (self.business_id, greeting)
                else:
                    logger.error(f"[CALL-ERROR] No business for {to_number}")
                    self.business_id = None
                    return (None, None)
        
        except Exception as e:
            import traceback
            logger.error(f"[CALL-ERROR] Business identification failed: {e}")
            logger.error(f"[CALL-ERROR] Traceback: {traceback.format_exc()}")
            self.business_id = None
            return (None, None)
    
    def _identify_business_from_phone(self):
        """זיהוי business_id לפי to_number (wrapper for backwards compat)"""
        self._identify_business_and_get_greeting()  # קורא לפונקציה החדשה ומתעלם מהברכה

    def _get_business_greeting_cached(self) -> str | None:
        """⚡ טעינת ברכה עם cache - במיוחד מהיר לברכה הראשונה!"""
        # קודם כל - בדוק אם יש business_id
        if not hasattr(self, 'business_id') or not self.business_id:
            logger.warning(f"⚠️ business_id חסר בקריאה ל-_get_business_greeting_cached!")
            return None  # ✅ NO fallback - return None
        
        try:
            # ✅ CRITICAL FIX: Must have app_context for DB query in Cloud Run/ASGI!
            from server.app_factory import create_app
            from server.models_sql import Business
            
            app = _get_flask_app()  # ✅ Use singleton
            with app.app_context():
                # ⚡ שאילתה בודדת - קל ומהיר
                business = Business.query.get(self.business_id)
                
                if business:
                    # קבלת הברכה המותאמת - אם אין, return None (לא fallback!)
                    greeting = business.greeting_message or None
                    
                    if greeting:
                        business_name = business.name or "העסק שלנו"
                        # החלפת placeholder בשם האמיתי
                        greeting = greeting.replace("{{business_name}}", business_name)
                        greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                        logger.info(f"✅ ברכה נטענה: business_id={self.business_id}, greeting='{greeting}' (len={len(greeting)})")
                    else:
                        logger.info(f"✅ No greeting defined for business_id={self.business_id} - AI will speak first!")
                    
                    return greeting
                else:
                    logger.warning(f"⚠️ Business {self.business_id} לא נמצא")
                    return None
        except Exception as e:
            logger.error(f"❌ שגיאה בטעינת ברכה: {e}")
            import traceback
            traceback.print_exc()
            return None  # ✅ NO fallback - return None on error
    
    def _get_business_greeting(self) -> str | None:
        """טעינת ברכה מותאמת אישית מהעסק עם {{business_name}} placeholder"""
        logger.info(f"🔍 _get_business_greeting CALLED! business_id={getattr(self, 'business_id', 'NOT SET')}")
        
        try:
            from server.app_factory import create_app
            from server.models_sql import Business
            
            # זיהוי עסק אם עדיין לא זוהה
            if not hasattr(self, 'business_id') or not self.business_id:
                logger.warning(f"⚠️ business_id לא מוגדר - מזהה עסק עכשיו...")
                app = _get_flask_app()  # ✅ Use singleton
                with app.app_context():
                    self._identify_business_from_phone()
                logger.info(f"🔍 אחרי זיהוי: business_id={getattr(self, 'business_id', 'STILL NOT SET')}")
            
            # טעינת ברכה מה-DB
            app = _get_flask_app()  # ✅ Use singleton
            with app.app_context():
                business = Business.query.get(self.business_id)
                logger.info(f"🔍 שאילתת business: id={self.business_id}, נמצא: {business is not None}")
                
                if business:
                    # קבלת הברכה המותאמת - אם אין, return None (לא fallback!)
                    greeting = business.greeting_message or None
                    business_name = business.name or "העסק שלנו"
                    
                    logger.info(f"🔍 פרטי עסק: name={business_name}, greeting_message={business.greeting_message}")
                    
                    if greeting:
                        # החלפת placeholder בשם האמיתי
                        greeting = greeting.replace("{{business_name}}", business_name)
                        greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                        
                        logger.info(f"✅ Loaded custom greeting for business {self.business_id} ({business_name}): '{greeting}'")
                    else:
                        logger.info(f"✅ No greeting defined for business {self.business_id} - AI will speak first!")
                    
                    return greeting
                else:
                    logger.warning(f"⚠️ Business {self.business_id} not found")
                    return None
        except Exception as e:
            import traceback
            logger.error(f"❌ Error loading business greeting: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None

    # 🔥 BUILD 172 CLEANUP: _load_call_behavior_settings() REMOVED
    # All call settings now loaded via single source of truth: load_call_config(business_id)
    # This function was duplicating the loading logic and has been removed.

    async def _fallback_hangup_after_timeout(self, timeout_seconds: int, trigger_type: str):
        """
        🔥 TIMEOUT HANGUP: Trigger hangup after timeout
        
        This function triggers hangup if the timeout expires and the call hasn't
        already ended. This prevents calls from getting stuck waiting for AI responses.
        
        Args:
            timeout_seconds: How long to wait before triggering hangup
            trigger_type: What triggered this ("user_goodbye", "lead_captured", etc.)
        """
        logger.info(f"⏰ [TIMEOUT] Starting {timeout_seconds}s timer for {trigger_type}...")
        
        await asyncio.sleep(timeout_seconds)
        
        # Check if already disconnected
        if self.hangup_triggered:
            logger.info(f"✅ [TIMEOUT] Call already ended - no action needed")
            return
        
        # Check if pending_hangup was set (AI said closing phrase)
        if self.pending_hangup:
            logger.info(f"✅ [TIMEOUT] pending_hangup already set - normal flow working")
            return
        
        # Timeout expired - trigger hangup
        logger.info(f"📞 [TIMEOUT] {timeout_seconds}s passed - triggering hangup for {trigger_type}")
        logger.info(f"📞 [AUTO_DISCONNECT] Disconnecting due to timeout - prevents wasted minutes")
        
        # Trigger hangup
        await self.request_hangup(
            reason=f"timeout_{trigger_type}",
            source="fallback_timeout",
            transcript_text=f"Timeout after {timeout_seconds}s for {trigger_type}"
        )


    def _immediate_hangup(self, reason: str):
        """
        🚨 IMMEDIATE HANGUP: Force immediate disconnection bypassing all protections
        
        This is used for critical situations like:
        - Voicemail detection (within first 15 seconds)
        - Extended silence (20+ seconds)
        
        Unlike _trigger_auto_hangup, this method:
        - Bypasses greeting protection
        - Bypasses audio queue checks
        - Does NOT send goodbye message
        - Executes hangup immediately via Twilio REST API
        
        Args:
            reason: Why the call is being hung up (for logging)
        """
        # Already hung up?
        if self.hangup_triggered or self.call_state == CallState.ENDED:
            return
        
        # Mark as ended immediately
        self.hangup_triggered = True
        self.call_state = CallState.ENDED
        self.goodbye_message_sent = True  # Prevent normal hangup from sending goodbye
        
        _orig_print(f"🚨 [IMMEDIATE_HANGUP] Forcing immediate disconnect: {reason}", flush=True)
        logger.warning(f"[IMMEDIATE_HANGUP] reason={reason} call_sid={self.call_sid}")
        
        # Execute Twilio hangup in separate thread (non-blocking)
        def do_hangup():
            try:
                from twilio.rest import Client
                import os
                
                client = Client(
                    os.getenv('TWILIO_ACCOUNT_SID'),
                    os.getenv('TWILIO_AUTH_TOKEN')
                )
                
                if self.call_sid:
                    client.calls(self.call_sid).update(status='completed')
                    _orig_print(f"✅ [IMMEDIATE_HANGUP] Twilio call {self.call_sid[:8]}... terminated", flush=True)
                    logger.info(f"[IMMEDIATE_HANGUP] Twilio call terminated: {self.call_sid}")
                    
            except Exception as e:
                _orig_print(f"⚠️ [IMMEDIATE_HANGUP] Error terminating call: {e}", flush=True)
                logger.error(f"[IMMEDIATE_HANGUP] Error: {e}")
        
        # Execute in thread to avoid blocking
        threading.Thread(target=do_hangup, daemon=True).start()


    def _trigger_auto_hangup(self, reason: str):
        """
        🎯 BUILD 163: Trigger automatic call hang-up via Twilio REST API
        
        🔥 BUILD 172 FIX: More robust - less blocking, with retry mechanism
        🔥 BUILD 178: Fixed log spam - limit retries and reduce logging
        
        Args:
            reason: Why the call is being hung up (for logging)
        """
        # 🔴 CRITICAL: If a real hangup was already requested (one-shot),
        # never attempt a second hangup path from the legacy auto-hangup flow.
        if getattr(self, "hangup_requested", False):
            return

        # 🔥 BUILD 178: Track retry count to prevent infinite loops
        if not hasattr(self, '_hangup_retry_count'):
            self._hangup_retry_count = 0
        
        # 🔥 BUILD 178: Stop if already hung up or exceeded max retries (30 retries = 15 seconds)
        if self.hangup_triggered or self.call_state == CallState.ENDED:
            return
        
        if self._hangup_retry_count > 30:
            logger.warning(f"⚠️ [BUILD 178] Max hangup retries exceeded - forcing hangup")
            self.hangup_triggered = True
            self.call_state = CallState.ENDED
            return
        
        # 🔥 BUILD 172: Transition to CLOSING state (only log first time)
        if self.call_state != CallState.ENDED and self.call_state != CallState.CLOSING:
            self.call_state = CallState.CLOSING
            logger.info(f"📞 [STATE] Transitioning to CLOSING (reason: {reason})")
        
        # 🔥🔥 CRITICAL PROTECTION: Don't hangup during greeting
        if self.is_playing_greeting:
            if self._hangup_retry_count == 0:
                logger.info(f"🛡️ [PROTECTION] BLOCKING hangup - greeting still playing")
            self._hangup_retry_count += 1
            threading.Timer(1.0, self._trigger_auto_hangup, args=(reason,)).start()
            return
        
        # 🔥 PROTECTION: Don't hangup within 3 seconds of greeting completion
        if self.greeting_completed_at is not None:
            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                remaining_ms = self.min_call_duration_after_greeting_ms - elapsed_ms
                if self._hangup_retry_count == 0:
                    logger.info(f"🛡️ [PROTECTION] BLOCKING hangup - only {elapsed_ms:.0f}ms since greeting")
                self._hangup_retry_count += 1
                threading.Timer(remaining_ms / 1000.0, self._trigger_auto_hangup, args=(reason,)).start()
                return
        
        # 🔥 BUILD 303: SMART HANGUP - Always send goodbye before disconnect!
        # If we haven't sent a goodbye message yet, schedule it and delay hangup
        if not self.goodbye_message_sent:
            self.goodbye_message_sent = True
            self._hangup_retry_count += 1
            logger.info(f"📞 [BUILD 303] SMART HANGUP - Scheduling goodbye before disconnect...")
            
            # Use closing sentence if available, otherwise use generic goodbye
            goodbye_text = None
            if self.call_config and self.call_config.closing_sentence:
                goodbye_text = self.call_config.closing_sentence
            
            # Send goodbye via separate thread with its own event loop (non-blocking)
            def send_goodbye_thread():
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def do_goodbye():
                        if goodbye_text:
                            await self._send_text_to_ai(f"[SYSTEM] Call ending. Say: {goodbye_text}")
                        else:
                            await self._send_text_to_ai("[SYSTEM] Call ending. Say goodbye per your instructions.")
                    
                    loop.run_until_complete(do_goodbye())
                    loop.close()
                except Exception as e:
                    logger.error(f"⚠️ [BUILD 303] Error sending goodbye: {e}")
            
            # Start goodbye thread and schedule hangup after delay
            threading.Thread(target=send_goodbye_thread, daemon=True).start()
            # Retry hangup after 4 seconds (time for TTS to play)
            threading.Timer(4.0, self._trigger_auto_hangup, args=(reason,)).start()
            return
        
        # 🔥 BUILD 172: Wait for audio to finish, but with timeout
        openai_queue_size = self.realtime_audio_out_queue.qsize()
        tx_queue_size = self.tx_q.qsize()
        is_ai_speaking = self.is_ai_speaking_event.is_set()
        
        if is_ai_speaking or openai_queue_size > 0 or tx_queue_size > 0:
            # 🔥 BUILD 178: Only log every 5th retry to reduce spam
            if self._hangup_retry_count % 10 == 0:
                logger.info(f"🛡️ [PROTECTION] Waiting for audio (ai={is_ai_speaking}, oai_q={openai_queue_size}, tx_q={tx_queue_size}) retry #{self._hangup_retry_count}")
            self._hangup_retry_count += 1
            threading.Timer(0.5, self._trigger_auto_hangup, args=(reason,)).start()
            return
        
        # ✅ All clear - execute hangup
        self.hangup_triggered = True
        self.call_state = CallState.ENDED
        
        # 🎯 SMART HANGUP: Detailed logging for debugging
        logger.info(f"📞 [SMART HANGUP] === CALL ENDING ===")
        logger.info(f"📞 [SMART HANGUP] Reason: {reason}")
        logger.info(f"📞 [SMART HANGUP] Lead captured: {self.lead_captured}")
        logger.info(f"📞 [SMART HANGUP] Goodbye detected: {self.goodbye_detected}")
        logger.info(f"📞 [SMART HANGUP] Lead state: {getattr(self, 'lead_capture_state', {})}")
        logger.info(f"📞 [SMART HANGUP] Required fields: {getattr(self, 'required_lead_fields', [])}")
        crm = getattr(self, 'crm_context', None)
        if crm:
            logger.info(f"📞 [SMART HANGUP] CRM: name={crm.customer_name}, phone={crm.customer_phone}")
        logger.info(f"📞 [SMART HANGUP] ===================")
        
        if not self.call_sid:
            logger.error(f"❌ [BUILD 163] No call_sid - cannot hang up")
            return
        
        try:
            # Centralized Twilio hangup (REST)
            from server.services.twilio_call_control import hangup_call
            hangup_call(self.call_sid)
        except Exception as e:
            logger.error(f"[HANGUP] error call_sid={self.call_sid} err={type(e).__name__}:{str(e)[:200]}")
            logger.exception("[HANGUP] error call_sid=%s", self.call_sid)
    
    # 🔥 MASTER FIX: Greeting SLA validation
    def _validate_greeting_sla(self):
        """
        Validate greeting performance against SLA requirements:
        - Did greeting play?
        - Did it play before first user speech?
        - What was first_greeting_audio_ms?
        - Does it meet SLA? (Inbound <=1600ms; Outbound <=1400ms)
        """
        try:
            from server.stream_state import stream_registry
            
            if not self.call_sid:
                return
            
            # Get metrics
            first_greeting_audio_ms = getattr(self, '_metrics_first_greeting_audio_ms', 0)
            greeting_audio_received = getattr(self, '_greeting_audio_received', False)
            user_has_spoken = getattr(self, 'user_has_spoken', False)
            call_direction = getattr(self, 'call_direction', 'inbound')
            
            # Check 1: Did greeting play?
            greeting_played = greeting_audio_received and first_greeting_audio_ms > 0
            
            # Check 2: Did it play before first user speech?
            # Note: user_has_spoken would be True if they spoke during greeting
            played_before_user_speech = greeting_played  # If played, it played first (by design)
            
            # Check 3: SLA threshold
            sla_threshold_ms = 1400 if call_direction == 'outbound' else 1600
            meets_sla = first_greeting_audio_ms > 0 and first_greeting_audio_ms <= sla_threshold_ms
            
            # Log validation results
            logger.info(
                f"[GREETING_VALIDATE] call_sid={self.call_sid[:8]}..., "
                f"played={greeting_played}, "
                f"played_before_user_speech={played_before_user_speech}, "
                f"first_greeting_audio_ms={first_greeting_audio_ms}, "
                f"direction={call_direction}, "
                f"sla_threshold={sla_threshold_ms}ms, "
                f"meets_sla={meets_sla}"
            )
            
            # If SLA failed, log ERROR with tag
            if not meets_sla:
                if not greeting_played:
                    reason = "greeting_not_played"
                elif first_greeting_audio_ms > sla_threshold_ms:
                    reason = f"exceeded_threshold_{sla_threshold_ms}ms"
                else:
                    reason = "no_audio_received"
                
                logger.error(
                    f"[GREETING_SLA_FAILED] call_sid={self.call_sid[:8]}..., "
                    f"reason={reason}, "
                    f"ms={first_greeting_audio_ms}, "
                    f"threshold={sla_threshold_ms}ms, "
                    f"direction={call_direction}"
                )
                _orig_print(
                    f"❌ [GREETING_SLA_FAILED] {reason}: {first_greeting_audio_ms}ms "
                    f"(threshold={sla_threshold_ms}ms, direction={call_direction})",
                    flush=True
                )
            else:
                _orig_print(
                    f"✅ [GREETING_SLA_MET] {first_greeting_audio_ms}ms "
                    f"(threshold={sla_threshold_ms}ms, direction={call_direction})",
                    flush=True
                )
                
        except Exception as e:
            logger.error(f"[GREETING_VALIDATE] Error during validation: {e}")
    
    # 🔥 BUILD 172: SILENCE MONITORING - Auto-hangup on prolonged silence
    async def _start_silence_monitor(self):
        """
        Start background task to monitor for silence and auto-hangup.
        Called after call setup is complete.
        """
        if self._silence_check_task is not None:
            return  # Already running
        
        self._silence_check_task = asyncio.create_task(self._silence_monitor_loop())
        logger.warning(f"🔇 [SILENCE] Monitor started (timeout={self.silence_timeout_sec}s, max_warnings={self.silence_max_warnings})")
    
    async def _silence_monitor_loop(self):
        """
        Background loop that checks for silence and triggers warnings/hangup.
        🔥 BUILD 312: Only start silence counting AFTER user has spoken!
        🔥 BUILD 339: Comprehensive state checks to prevent action after goodbye
        🔥 BUILD 340: Guard BEFORE sleep to prevent action during sleep window
        """
        try:
            # 🧘 BUILD 345: Wait for post-greeting breathing window before monitoring
            if self._post_greeting_window_open():
                logger.info(f"🧘 [SILENCE] Waiting {self._post_greeting_breath_window_sec:.1f}s breathing window before monitoring")
            while self._post_greeting_window_open():
                # If user already completed one speech cycle, end window immediately
                if self._post_greeting_speech_cycle_complete:
                    self._maybe_release_post_greeting_window("user_spoke")
                    break
                # Timer-based release
                if self._post_greeting_window_started_at:
                    elapsed = time.time() - self._post_greeting_window_started_at
                    if elapsed >= self._post_greeting_breath_window_sec:
                        self._maybe_release_post_greeting_window("timer_elapsed")
                        break
                await asyncio.sleep(0.2)
            # Ensure window marked finished if it expired without explicit release
            if self._post_greeting_window_active and not self._post_greeting_window_finished:
                self._maybe_release_post_greeting_window("monitor_start")
            
            while True:
                # 🔥 CRITICAL: "CALL END = שקט" - Stop ALL periodic loops when call ends
                # Per user requirement: "כל task/loop שמדפיס מחזורית חייב לבדוק"
                if self.closed or self.call_state in (CallState.CLOSING, CallState.ENDED):
                    logger.info(f"🔇 [SILENCE] Monitor exiting - call ended (state={self.call_state.value if hasattr(self, 'call_state') else 'unknown'})")
                    return
                
                # 🔥 BUILD 340 CRITICAL: Check state BEFORE sleeping to exit immediately
                # This prevents AI from speaking during the sleep window after goodbye
                if self.call_state != CallState.ACTIVE:
                    logger.info(f"🔇 [SILENCE] Monitor exiting BEFORE sleep - call state is {self.call_state.value}")
                    return
                if self.hangup_triggered or getattr(self, 'pending_hangup', False):
                    logger.info(f"🔇 [SILENCE] Monitor exiting BEFORE sleep - hangup pending/triggered")
                    return
                
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
                # 🔥 BUILD 339 CRITICAL: Check AGAIN after sleep (state may have changed during sleep)
                if self.closed or self.call_state in (CallState.CLOSING, CallState.ENDED):
                    logger.info(f"🔇 [SILENCE] Monitor exiting - call ended after sleep")
                    return
                if self.call_state != CallState.ACTIVE:
                    logger.info(f"🔇 [SILENCE] Monitor exiting - call state is {self.call_state.value}")
                    return  # Use return, not break, to completely exit
                
                if self.hangup_triggered:
                    logger.info(f"🔇 [SILENCE] Monitor exiting - hangup_triggered=True")
                    return
                
                if getattr(self, 'pending_hangup', False):
                    logger.info(f"🔇 [SILENCE] Monitor exiting - pending_hangup=True")
                    return
                
                # 🔥 FIX: SILENCE FAILSAFE completely removed - proper idle timeout instead
                # Rule: 2 valid states only:
                # 1. User never spoke + silence > 30s → close_session(idle_timeout)
                # 2. User spoke + silence → End-of-utterance → AI must respond
                
                # 🔥 BUILD 312: NEVER count silence until user has spoken at least once!
                # This prevents AI from responding "are you there?" before user says anything
                # ✅ HARD SILENCE WATCHDOG (independent of AI logic)
                # If absolutely no activity (user speech_started OR AI audio.delta) for X seconds → hang up.
                now_ts = time.time()
                try:
                    # 🔥 CRITICAL: Use multiple activity sources - take the MOST RECENT
                    last_user_voice = getattr(self, "_last_user_voice_started_ts", None)
                    last_ai_audio = getattr(self, "last_ai_audio_ts", None)
                    last_general_activity = getattr(self, "_last_activity_ts", None)
                    
                    # Get the most recent activity timestamp from all sources
                    # Fallback to now_ts if all sources are None (shouldn't happen, but defensive)
                    all_timestamps = [t for t in [last_user_voice, last_ai_audio, last_general_activity, self._last_speech_time] if t is not None]
                    last_activity = max(all_timestamps) if all_timestamps else now_ts
                    
                    # 🔥 NEW REQUIREMENT: In SIMPLE_MODE, 20 seconds silence = immediate disconnect (no warnings)
                    hard_timeout = 20.0 if SIMPLE_MODE else float(getattr(self, "_hard_silence_hangup_sec", 20.0))

                    # 🔥 CRITICAL: Check if audio is still in queues FIRST - AI is still speaking!
                    # This prevents false timeouts during long AI responses when audio is buffered
                    tx_queue_size = self.tx_q.qsize()
                    realtime_queue_size = self.realtime_audio_out_queue.qsize()
                    
                    # 🔥 WATCHDOG PROTECTION: If audio in queues, AI is speaking - update activity timestamp!
                    if tx_queue_size > 0 or realtime_queue_size > 0 or self.is_ai_speaking_event.is_set():
                        # AI is actively speaking - reset the watchdog timer!
                        # This gives the customer time to respond after AI finishes
                        self._last_activity_ts = now_ts
                        if _event_loop_rate_limiter.every("watchdog_reset", 3.0):
                            logger.info(f"⏳ [WATCHDOG] AI speaking (tx={tx_queue_size}, realtime={realtime_queue_size}, event={self.is_ai_speaking_event.is_set()}) - timer RESET")
                    
                    # Now check for timeout only after ensuring AI is not speaking
                    if (now_ts - last_activity) >= hard_timeout:
                        # 🔥 AUTO-DISCONNECT: 20 seconds of silence from both bot and customer
                        # This prevents wasted minutes on voicemail or prolonged silence
                        # Only hang up when nothing is actively happening.
                        if (
                            not self.is_ai_speaking_event.is_set()
                            and not self.response_pending_event.is_set()
                            and not getattr(self, "has_pending_ai_response", False)
                            and not getattr(self, "_realtime_speech_active", False)
                            and not getattr(self, "user_speaking", False)
                            and not getattr(self, "waiting_for_dtmf", False)
                            and tx_queue_size == 0  # 🔥 CRITICAL: No audio in TX queue
                            and realtime_queue_size == 0  # 🔥 CRITICAL: No audio in realtime queue
                            and self.call_state == CallState.ACTIVE
                            and not self.hangup_triggered
                            and not getattr(self, "pending_hangup", False)
                        ):
                            logger.info(f"🔇 [HARD_SILENCE] {hard_timeout:.0f}s inactivity detected (last_activity={now_ts - last_activity:.1f}s ago)")
                            logger.info(f"📞 [AUTO_DISCONNECT] Disconnecting due to prolonged silence - prevents wasted minutes")
                            # Trigger immediate hangup - don't wait for goodbye
                            await self.request_hangup(
                                reason="hard_silence_timeout",
                                source="silence_monitor",
                                transcript_text=f"No activity for {hard_timeout:.0f}s"
                            )
                            return
                except Exception as watchdog_err:
                    logger.error(f"⚠️ [HARD_SILENCE] Watchdog error (ignored): {watchdog_err}")

                if not self.user_has_spoken:
                    # User hasn't spoken yet - check for idle timeout
                    # But add a safety limit of 30 seconds to avoid zombie calls
                    if self.greeting_completed_at:
                        time_since_greeting = time.time() - self.greeting_completed_at
                        if time_since_greeting > 30.0:
                            # 30 seconds with no user speech - idle timeout (likely voicemail)
                            if self.call_state == CallState.ACTIVE and not self.hangup_triggered and not getattr(self, 'pending_hangup', False):
                                logger.info(f"🔇 [IDLE_TIMEOUT] 30s+ no user speech detected - likely voicemail")
                                logger.info(f"📞 [AUTO_DISCONNECT] Disconnecting due to no user response - prevents wasted minutes")
                                # Trigger immediate hangup - don't wait for goodbye
                                await self.request_hangup(
                                    reason="idle_timeout_no_user_speech",
                                    source="silence_monitor",
                                    transcript_text="No user speech for 30+ seconds"
                                )
                            return
                    # Still waiting for user to speak - don't count silence
                    continue
                
                # Calculate silence duration
                silence_duration = time.time() - self._last_speech_time
                
                # 🔥 NEW REQUIREMENT: In SIMPLE_MODE, skip warning system entirely
                # After 20 seconds of silence, watchdog will handle disconnect (see above)
                # This section is only for non-SIMPLE_MODE calls
                if SIMPLE_MODE:
                    # Skip warning logic in SIMPLE_MODE - watchdog handles everything
                    await asyncio.sleep(2)  # Same interval as main loop for consistency
                    continue
                
                if silence_duration >= self.silence_timeout_sec:
                    # 🔥 BUILD 339: RE-CHECK state before ANY action (state may have changed during sleep)
                    if self.call_state != CallState.ACTIVE or self.hangup_triggered or getattr(self, 'pending_hangup', False):
                        logger.warning(f"🔇 [SILENCE] State changed before warning - exiting (state={self.call_state.value})")
                        return
                    
                    if self._silence_warning_count < self.silence_max_warnings:
                        # Send "are you there?" warning
                        self._silence_warning_count += 1
                        logger.warning(f"🔇 [SILENCE] Warning {self._silence_warning_count}/{self.silence_max_warnings} after {silence_duration:.1f}s silence")
                        logger.info(f"🔇 [SILENCE] SIMPLE_MODE={SIMPLE_MODE} action=ask_are_you_there")
                        
                        # 🔥 FIX: If user has spoken, ALWAYS trigger AI response (not dependent on SIMPLE_MODE)
                        # This is end-of-utterance - AI must respond
                        if self.user_has_spoken:
                            await self._send_silence_warning()
                        
                        # Reset timer
                        self._last_speech_time = time.time()
                    else:
                        # Max warnings exceeded - check if we can hangup
                        # 🔥 BUILD 339: FINAL state check before taking hangup action
                        if self.call_state != CallState.ACTIVE or self.hangup_triggered or getattr(self, 'pending_hangup', False):
                            logger.warning(f"🔇 [SILENCE] Max warnings - but call already ending, exiting monitor")
                            return
                        
                        # 🔥 BUILD 172 FIX: Don't hangup if lead is captured but not confirmed!
                        fields_collected = self._check_lead_captured() if hasattr(self, '_check_lead_captured') else False
                        if fields_collected and not self.verification_confirmed:
                            # Fields captured but not confirmed - give one more chance
                            # But ONLY if call is still active!
                            if self.call_state != CallState.ACTIVE or getattr(self, 'pending_hangup', False):
                                logger.info(f"🔇 [SILENCE] Can't give final chance - call ending")
                                return
                            
                            logger.warning(f"🔇 [SILENCE] Max warnings exceeded BUT lead not confirmed - sending final prompt")
                            self._silence_warning_count = self.silence_max_warnings - 1  # Allow one more warning
                            await self._send_text_to_ai(
                                "[SYSTEM] Customer is silent and hasn't confirmed. Ask for confirmation one last time."
                            )
                            self._last_speech_time = time.time()
                            # Mark that we gave extra chance - next time really close
                            self._silence_final_chance_given = getattr(self, '_silence_final_chance_given', False)
                            if self._silence_final_chance_given:
                                # Already gave extra chance, now close without confirmation
                                logger.info(f"🔇 [SILENCE] Final chance already given - closing anyway")
                                pass  # Fall through to close
                            else:
                                self._silence_final_chance_given = True
                                continue  # Don't close yet
                        
                        # OK to close - either no lead, or lead confirmed, or final chance given
                        # 🔥 BUILD 339: One more state check before initiating hangup
                        if self.call_state != CallState.ACTIVE or self.hangup_triggered or getattr(self, 'pending_hangup', False):
                            logger.info(f"🔇 [SILENCE] State changed before hangup - exiting")
                            return
                        
                        # 🔥 CRITICAL FIX: SIMPLE_MODE with disconnect exception
                        # SIMPLE_MODE stays active (no flow changes), but we add disconnect exception
                        # User requirement: "אם יש 20 שניות בלי קול לקוח או ai - לנתק מיד!!!"
                        # This prevents wasted minutes on prolonged silence
                        if SIMPLE_MODE:
                            # In SIMPLE_MODE: Skip polite closing message, just disconnect immediately
                            # This is a disconnect-only exception that doesn't affect call flow
                            logger.error(f"🔇 [SILENCE] SIMPLE_MODE - max warnings exceeded, IMMEDIATE DISCONNECT (exception)")
                            logger.warning(f"📞 [AUTO_DISCONNECT] Disconnecting after max silence warnings - prevents wasted minutes")
                            await self.request_hangup(
                                reason="silence_max_warnings_simple_mode",
                                source="silence_monitor",
                                transcript_text="Max silence warnings exceeded - SIMPLE_MODE exception disconnect"
                            )
                            return
                        
                        logger.warning(f"🔇 [SILENCE] Max warnings exceeded - initiating polite hangup")
                        self.call_state = CallState.CLOSING
                        
                        # Send closing message and hangup
                        closing_msg = ""
                        if self.call_config and self.call_config.closing_sentence:
                            closing_msg = self.call_config.closing_sentence
                        elif self.call_config and self.call_config.greeting_text:
                            closing_msg = self.call_config.greeting_text  # Use greeting as fallback
                        
                        if closing_msg:
                            await self._send_text_to_ai(f"[SYSTEM] User silent too long. Say: {closing_msg}")
                        else:
                            await self._send_text_to_ai("[SYSTEM] User silent too long. Say goodbye per your instructions.")
                        
                        # 🔇 AUTO-DISCONNECT: Disconnecting after max silence warnings
                        # This prevents wasted minutes on prolonged silence
                        # User requirement: Must disconnect if there are 20 seconds without voice from customer or AI
                        logger.warning(f"📞 [AUTO_DISCONNECT] Disconnecting after max silence warnings - prevents wasted minutes")
                        await self.request_hangup(
                            reason="silence_max_warnings",
                            source="silence_monitor",
                            transcript_text="Max silence warnings exceeded"
                        )
                        return
                        
        except asyncio.CancelledError:
            logger.info(f"🔇 [SILENCE] Monitor cancelled")
        except Exception as e:
            logger.error(f"❌ [SILENCE] Monitor error: {e}")
    
    async def _send_silence_warning(self):
        """
        Send a gentle prompt to continue the conversation.
        🔥 BUILD 311.1: Made fully dynamic - AI decides based on context, no hardcoded phrases
        🔥 BUILD 339: Added critical state checks to prevent loop after goodbye
        """
        try:
            if self._post_greeting_window_open():
                logger.info(f"🔇 [SILENCE] Breathing window active - skipping prompt")
                return
            if getattr(self, '_awaiting_confirmation_reply', False):
                logger.info(f"🔇 [SILENCE] Awaiting confirmation reply - not sending additional prompt")
                return
            if self._loop_guard_engaged:
                logger.info(f"🔇 [SILENCE] Loop guard engaged - suppressing silence prompt")
                return
            # 🔥 BUILD 339 CRITICAL: Don't send any warnings if call is ending!
            # This prevents the AI from asking questions AFTER saying goodbye
            if self.call_state == CallState.CLOSING or self.call_state == CallState.ENDED:
                logger.warning(f"🔇 [SILENCE] BLOCKED - call is {self.call_state.value}, not sending warning")
                return
            
            if self.hangup_triggered or getattr(self, 'pending_hangup', False):
                logger.warning(f"🔇 [SILENCE] BLOCKED - hangup pending/triggered, not sending warning")
                return
            
            # 🔥 BUILD 172 FIX: If we collected fields but not confirmed, ask for confirmation again
            fields_collected = self._check_lead_captured() if hasattr(self, '_check_lead_captured') else False
            if fields_collected and not self.verification_confirmed:
                warning_prompt = "[SYSTEM] הלקוח שותק. שאל בקצרה אם הפרטים שמסר נכונים."
            else:
                # 🔥 BUILD 311.1: Dynamic - let AI continue naturally based on conversation context
                # Let AI decide based on context and Business Prompt
                warning_prompt = "[SYSTEM] Customer is silent. Continue naturally per your instructions."
            await self._send_text_to_ai(warning_prompt)
        except Exception as e:
            logger.error(f"❌ [SILENCE] Failed to send warning: {e}")
    
    def _update_speech_time(self, is_user_speech: bool = False):
        """Call this whenever user or AI speaks to reset silence timer.
        
        🔥 BUILD 338 FIX: Only reset warning count on USER speech, not AI speech!
        Otherwise AI responding resets the count and silence loop never ends.
        
        Args:
            is_user_speech: True if this is user speech, False if AI speech
        """
        self._last_speech_time = time.time()
        # 🔥 BUILD 338: Only reset warnings when USER speaks, not when AI speaks!
        # This prevents infinite silence loop: AI speaks → count reset → warning 1/2 again
        if is_user_speech:
            self._silence_warning_count = 0
        
        # 🔥 BUILD 172 SAFETY: Ensure we're in ACTIVE state if speech occurs
        # This guards against edge cases where greeting fails but conversation continues
        self._ensure_active_state_sync()
    
    def _ensure_active_state_sync(self):
        """
        🔥 BUILD 172 SAFETY GUARD: Ensure call is in ACTIVE state.
        Called on any speech event to catch edge cases where greeting transition failed.
        """
        if self.call_state == CallState.WARMUP and not self.hangup_triggered:
            self.call_state = CallState.ACTIVE
            logger.info(f"📞 [STATE] Safety guard: Forcing WARMUP → ACTIVE (speech detected)")
            
            # Start silence monitor if not already running
            if self._silence_check_task is None:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._start_silence_monitor())
                    logger.info(f"🔇 [SILENCE] Safety guard: Started monitor (was missing)")
                except RuntimeError:
                    # No running loop - we're in sync context
                    logger.info(f"🔇 [SILENCE] Cannot start monitor from sync context (will start on next async call)")

    def _post_greeting_window_open(self) -> bool:
        """Return True while the breathing window is still protecting the user."""
        return getattr(self, '_post_greeting_window_active', False) and not getattr(self, '_post_greeting_window_finished', False)

    def _maybe_release_post_greeting_window(self, reason: str):
        """
        End the breathing window either because user already spoke or the timer elapsed.
        """
        if getattr(self, '_post_greeting_window_finished', False):
            return
        self._post_greeting_window_finished = True
        self._post_greeting_window_active = False
        logger.info(f"🧘 [GREETING] Breathing window ended ({reason})")

    def _mark_response_cancelled_locally(self, response_id: Optional[str], source: str = ""):
        """
        Remember responses we cancelled so late events can be ignored.
        
        ✅ NEW REQ 4: Added TTL and size cap to prevent memory leaks
        """
        if not response_id:
            return
        
        # ✅ NEW REQ 4: Cleanup old entries before adding new one
        now = time.time()
        
        # Remove entries older than max_age
        expired_ids = [
            rid for rid, ts in self._cancelled_response_timestamps.items()
            if now - ts > self._cancelled_response_max_age_sec
        ]
        for rid in expired_ids:
            self._cancelled_response_ids.discard(rid)
            del self._cancelled_response_timestamps[rid]
        
        if expired_ids:
            logger.info(f"🧹 [CLEANUP] Removed {len(expired_ids)} expired cancelled response IDs (>{self._cancelled_response_max_age_sec}s old)")
        
        # ✅ NEW REQ 4: If at max size, remove oldest entry
        if len(self._cancelled_response_ids) >= self._cancelled_response_max_size:
            # Find oldest entry
            oldest_id = min(self._cancelled_response_timestamps.items(), key=lambda x: x[1])[0]
            self._cancelled_response_ids.discard(oldest_id)
            del self._cancelled_response_timestamps[oldest_id]
            logger.info(f"🧹 [CLEANUP] Removed oldest cancelled response ID (cap={self._cancelled_response_max_size})")
        
        # Add new entry
        self._cancelled_response_ids.add(response_id)
        self._cancelled_response_timestamps[response_id] = now
        if source:
            logger.info(f"🪓 [BARGE-IN] Marked response {response_id[:20]}... as cancelled ({source})")
    
    def _should_send_cancel(self, response_id: Optional[str]) -> bool:
        """
        ✅ NEW REQ: Check if we should send cancel for this response_id
        Returns True if ALL 3 conditions met:
        1. response_id exists (not None)
        2. We haven't already sent cancel for this ID
        3. Response not already completed (not in cancelled_response_ids)
        
        Prevents duplicate cancel events that cause "response_cancel_not_active" errors
        """
        # Condition 1: response_id must exist
        if not response_id:
            return False
        
        # Condition 2: Check if we already sent cancel for this response
        if response_id in self._cancel_sent_for_response_ids:
            logger.info(f"⏭️ [CANCEL_GUARD] Skipping duplicate cancel for response {response_id[:20]}... (already sent)")
            return False
        
        # Condition 3: Check if response already done/cancelled (don't cancel completed responses)
        # If response is in _cancelled_response_ids, we already processed its completion
        if response_id in self._cancelled_response_ids:
            logger.info(f"⏭️ [CANCEL_GUARD] Skipping cancel for completed response {response_id[:20]}... (already done)")
            return False
        
        # All 3 conditions met - mark that we're sending cancel for this ID
        self._cancel_sent_for_response_ids.add(response_id)
        
        # ✅ Simple cleanup: when set grows large, clear it completely
        # Response IDs are short-lived (seconds), so full reset is safe
        # Using 100 threshold (larger than _cancelled_response_max_size to allow for burst scenarios)
        CANCEL_GUARD_MAX_SIZE = 100
        if len(self._cancel_sent_for_response_ids) > CANCEL_GUARD_MAX_SIZE:
            logger.info(f"🧹 [CANCEL_GUARD] Clearing guard set (size={len(self._cancel_sent_for_response_ids)})")
            self._cancel_sent_for_response_ids.clear()
            # Re-add current ID after clear
            self._cancel_sent_for_response_ids.add(response_id)
        
        return True
    
    async def _send_text_to_ai(self, text: str):
        """
        🔥 DISABLED: Sending text as user input violates "transcription is truth"
        
        This function has been disabled because sending [SYSTEM] messages with role="user"
        makes the AI think the customer said these things, causing prompt confusion.
        
        The AI should respond based ONLY on actual customer speech transcripts.
        
        Args:
            text: Text to send - IGNORED
        """
        # 🔥 FIX: Do NOT send synthetic text as user input
        # Block [SYSTEM] and [SERVER] messages from being injected
        if "[SYSTEM]" in text or "[SERVER]" in text:
            # 🔥 REQUIREMENT: Mandatory logging when blocking server events
            logger.warning(f"[AI_INPUT_BLOCKED] kind=server_event reason=never_send_to_model text_preview='{text[:100]}'")
            logger.info(f"🛡️ [PROMPT_FIX] BLOCKED synthetic message from being sent as user input")
            logger.info(f"   └─ Blocked: {text[:100]}")
            return
        
        # If not a system message, log warning but allow (for backward compatibility)
        logger.warning(f"⚠️ [_send_text_to_ai] Called with non-system text: {text[:50]}")
        logger.warning(f"⚠️ [_send_text_to_ai] Called with non-system text: {text[:50]}")
        
        try:
            # 🔥 BUILD 200: Use realtime_client instead of openai_ws
            if not self.realtime_client:
                logger.warning(f"⚠️ [AI] No realtime_client - cannot send text")
                return
            
            # 🔥 REQUIREMENT: Mandatory logging for every AI input
            # Truncate to protect sensitive customer data in logs
            logger.info(f"[AI_INPUT] kind=user_transcript text_preview='{text[:100]}'")
            
            msg = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}]
                }
            }
            await self.realtime_client.send_event(msg)
            
            # 🔥 BUILD 311: Mark this as silence handler response (don't count towards consecutive)
            self._is_silence_handler_response = True
            
            # 🔥 BUILD 200: Use central trigger_response
            await self.trigger_response(f"SILENCE_HANDLER:{text[:30]}")
        except Exception as e:
            logger.error(f"❌ [AI] Failed to send text: {e}")

    async def _inject_verbatim_reply_and_respond(self, client, user_msg: str, reason: str) -> bool:
        """
        Inject a strict system instruction and trigger a response.
        Used by SERVER-FIRST scheduling (no tools; server is source-of-truth).
        """
        if not client:
            return False
        msg = (user_msg or "").strip()
        if not msg:
            return False
        safe = msg.replace('"', '\\"')
        await client.send_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{safe}"',
                        }
                    ],
                },
            }
        )
        await self.trigger_response(reason, client)
        return True

    async def _maybe_server_first_schedule_from_transcript(self, client, transcript: str) -> bool:
        """
        SERVER-FIRST scheduling entrypoint (called after STT_FINAL).
        Returns True if the server handled this turn by injecting a verbatim reply.
        """
        # ✅ CRITICAL: Entry gate #1 — only when call_goal is appointment.
        # No parse/check/schedule/verbatim in lead/sales/service calls.
        if getattr(self, "call_goal", "lead_only") != "appointment":
            return False
        # ✅ Entry gate #2 — feature flag
        if not getattr(self, "_server_first_scheduling_enabled", False):
            return False
        if not transcript or not transcript.strip():
            return False

        # One-call safety: never double-book in the same session.
        if getattr(self, "appointment_confirmed_in_session", False):
            return False
        crm_ctx = getattr(self, "crm_context", None)
        if crm_ctx and getattr(crm_ctx, "has_appointment_created", False):
            return False

        business_id = getattr(self, "business_id", None)
        if not business_id:
            return False

        app = _get_flask_app()
        with app.app_context():
            from server.policy.business_policy import get_business_policy
            import pytz
            from datetime import datetime as _dt, timedelta as _td
            from server.services.hebrew_datetime import (
                resolve_hebrew_date,
                resolve_hebrew_time,
                auto_correct_iso_year,
            )
            from server.agent_tools.tools_calendar import FindSlotsInput, _calendar_find_slots_impl

            policy = get_business_policy(business_id)
            tz = pytz.timezone(getattr(policy, "tz", "Asia/Jerusalem") or "Asia/Jerusalem")
            duration_min = int(getattr(policy, "slot_size_min", 30) or 30)

            # Persisted pending slot (across turns)
            pending = {}
            if crm_ctx and getattr(crm_ctx, "pending_slot", None):
                pending = dict(crm_ctx.pending_slot or {})
            date_iso = (pending.get("date") or "").strip()
            time_hhmm = (pending.get("time") or "").strip()
            time_candidates = list(pending.get("time_candidates") or [])

            # Update from this transcript (deterministic parse).
            date_token = _extract_hebrew_date_token(transcript)
            if date_token:
                dres = resolve_hebrew_date(date_token, tz)
                if dres:
                    normalized_date_iso = dres.date_iso
                    corrected_iso, corrected, _reason = auto_correct_iso_year(normalized_date_iso, tz)
                    date_iso = corrected_iso if corrected else normalized_date_iso

            time_token = _extract_hebrew_time_token(transcript)
            if time_token:
                tres = resolve_hebrew_time(time_token)
                if tres and tres.candidates_hhmm:
                    time_candidates = list(tres.candidates_hhmm)
                    # Keep last explicit time too (first candidate is usually PM-first).
                    time_hhmm = time_candidates[0]

            # Persist pending state back.
            if crm_ctx:
                crm_ctx.pending_slot = {
                    **pending,
                    "date": date_iso or pending.get("date"),
                    "time": time_hhmm or pending.get("time"),
                    "time_candidates": time_candidates or pending.get("time_candidates") or [],
                }

            # Need date + at least one time candidate to proceed.
            if not date_iso:
                return False
            if not time_candidates and not time_hhmm:
                return False
            if not time_candidates:
                time_candidates = [time_hhmm]

            # Need customer name to actually book.
            customer_name = ""
            if crm_ctx and getattr(crm_ctx, "customer_name", None):
                customer_name = (crm_ctx.customer_name or "").strip()
            if not customer_name:
                customer_name = (getattr(self, "pending_customer_name", "") or "").strip()
            if not customer_name:
                return False

            # Reject past dates deterministically.
            today_local = _dt.now(tz).date()
            try:
                y, m, d = map(int, date_iso.split("-"))
                requested_date = _dt(y, m, d, tzinfo=tz).date()
            except Exception:
                requested_date = None
            if requested_date and requested_date < today_local:
                return await self._inject_verbatim_reply_and_respond(
                    client,
                    "זה תאריך שכבר עבר. אפשר תאריך חדש? למשל מחר או שבוע הבא.",
                    "SERVER_FIRST_APPT_PAST_DATE",
                )

            # Check availability near the requested time; try all candidates (PM-first already).
            chosen = None
            alternatives: list[str] = []
            for cand in time_candidates:
                try:
                    slots_res = _calendar_find_slots_impl(
                        FindSlotsInput(
                            business_id=business_id,
                            date_iso=date_iso,
                            duration_min=duration_min,
                            preferred_time=cand,
                        )
                    )
                    alternatives = [s.start_display for s in (slots_res.slots or [])][:2]
                    if slots_res.slots and any(s.start_display == cand for s in slots_res.slots):
                        chosen = cand
                        break
                except Exception:
                    continue

            if not chosen:
                if alternatives:
                    msg = f"השעה שביקשת לא פנויה. יש לי {alternatives[0]}" + (f" או {alternatives[1]}" if len(alternatives) > 1 else "") + " באותו יום. מתאים?"
                else:
                    msg = "השעה שביקשת לא פנויה. תרצה שעה אחרת או תאריך אחר?"
                return await self._inject_verbatim_reply_and_respond(client, msg, "SERVER_FIRST_APPT_UNAVAILABLE")

            # Book.
            start_dt = tz.localize(_dt.strptime(f"{date_iso} {chosen}", "%Y-%m-%d %H:%M"))
            end_dt = start_dt + _td(minutes=duration_min)

            phone = ""
            if crm_ctx and getattr(crm_ctx, "customer_phone", None):
                phone = (crm_ctx.customer_phone or "").strip()
            if not phone:
                phone = (getattr(self, "phone_number", "") or "").strip()

            result = create_appointment_from_realtime(
                business_id=business_id,
                customer_phone=phone,
                customer_name=customer_name,
                treatment_type="Appointment",
                start_iso=start_dt.isoformat(),
                end_iso=end_dt.isoformat(),
                notes="Server-first scheduling (Realtime).",
            )

            if isinstance(result, dict) and result.get("ok"):
                appt_id = result.get("appointment_id")
                if crm_ctx:
                    crm_ctx.has_appointment_created = True
                    crm_ctx.last_appointment_id = appt_id
                self.appointment_confirmed_in_session = True
                user_msg = (result.get("message") or "").strip() or f"מעולה, קבעתי לך תור ל{date_iso} בשעה {chosen}."
                return await self._inject_verbatim_reply_and_respond(client, user_msg, "SERVER_FIRST_APPT_BOOKED")

            fail_msg = "יש בעיה לקבוע את התור כרגע. אפשר לנסות שעה אחרת או תאריך אחר?"
            if isinstance(result, dict) and isinstance(result.get("message"), str) and result.get("message"):
                fail_msg = result.get("message")
            return await self._inject_verbatim_reply_and_respond(client, fail_msg, "SERVER_FIRST_APPT_FAILED")

    # ──────────────────────────────────────────────────────────────────────────
    # 🔴 CRITICAL — Real Hangup (transcript-only)
    # ──────────────────────────────────────────────────────────────────────────
    def _classify_real_hangup_intent(self, transcript_text: str, speaker: str) -> Optional[str]:
        """
        Returns:
        - "hangup": real hangup should be executed now
        - "clarify": ambiguous goodbye ("ביי אבל רגע") → ask clarification once
        - None: no real hangup intent
        """
        if not transcript_text or not transcript_text.strip():
            return None

        tuples = _REAL_HANGUP_USER_TUPLES if speaker == "user" else _REAL_HANGUP_BOT_TUPLES
        if _is_closing_sentence_only(transcript_text, tuples):
            return "hangup"

        if speaker == "user" and _is_ambiguous_goodbye(transcript_text):
            return "clarify"

        return None

    async def maybe_execute_hangup(self, via: str, response_id: str):
        """
        🎯 SINGLE SOURCE OF TRUTH: Execute hangup if ALL conditions are met
        
        This is the ONLY function that executes Twilio hangup.
        Called from both audio.done and transcript.done handlers.
        
        Conditions for execution (ALL must be True):
        1. pending_hangup is True
        2. pending_hangup_response_id matches response_id
        3. active_response_status != "cancelled"
        4. audio_done_by_response_id[response_id] == True
        5. tx_q is empty
        6. realtime_audio_out_queue is empty
        7. hangup_executed is False (idempotent guard)
        8. session not closed (prevent race with close_session)
        
        Args:
            via: Source of the call ("audio.done" or "transcript.done_racefix")
            response_id: Response ID to check
        """
        # Check if session is closed (prevent race with close_session)
        if getattr(self, 'closed', False):
            return
        
        # Idempotent check - prevent duplicate execution
        if self.hangup_executed:
            return
        
        # Check all conditions
        conditions = {
            "pending_hangup": self.pending_hangup,
            "response_id_match": self.pending_hangup_response_id == response_id,
            "not_cancelled": getattr(self, "active_response_status", None) != "cancelled",
            "audio_done": self.audio_done_by_response_id.get(response_id, False),
            "tx_empty": not hasattr(self, 'tx_q') or self.tx_q.empty(),
            "out_q_empty": not hasattr(self, 'realtime_audio_out_queue') or self.realtime_audio_out_queue.empty(),
            "not_triggered": not self.hangup_triggered,
        }
        
        # All conditions must be True
        all_met = all(conditions.values())
        
        if not all_met:
            # Log which condition(s) failed (DEBUG=0 only - verbose mode)
            if not DEBUG:
                failed = [k for k, v in conditions.items() if not v]
                _orig_print(f"[MAYBE_HANGUP] Conditions not met (via={via}): {failed}", flush=True)
            return
        
        # All conditions met - execute hangup
        logger.info(f"[POLITE_HANGUP] via={via} resp_id={response_id[:20] if response_id else 'none'}...")
        logger.info(f"[POLITE_HANGUP] via={via} resp_id={response_id}")
        
        # Mark as executed BEFORE calling Twilio (prevent race)
        self.hangup_executed = True
        self.hangup_executed_at = time.time()
        self.hangup_triggered = True
        self.call_state = CallState.ENDED
        self.pending_hangup = False
        
        call_sid = getattr(self, "call_sid", None)
        if not call_sid:
            logger.error(f"[HANGUP] error missing_call_sid")
            return
        
        # Execute Twilio hangup
        try:
            from server.services.twilio_call_control import hangup_call
            await asyncio.to_thread(hangup_call, call_sid)
            logger.error(f"[HANGUP] executed reason={self.pending_hangup_reason} call_sid={call_sid}")
        except Exception as e:
            logger.error(f"[HANGUP] error call_sid={call_sid} err={type(e).__name__}:{str(e)[:200]}")
            logger.exception("[HANGUP] error call_sid=%s", call_sid)

    async def request_hangup(
        self,
        reason: str,
        source: str,
        transcript_text: str = "",
        speaker: str = "",
        response_id: Optional[str] = None,
    ):
        """
        Polite hangup request (NO immediate cancel/clear/flush/hangup).

        Requirement:
        - Mark pending_hangup=True and hang up ONLY after the bot audio ends
          (response.audio.done, ideally matching response_id).
        """
        # One-shot (pending): do not block other fallback hangup paths by setting hangup_requested here.
        lock = getattr(self, "_hangup_request_lock", None)
        if lock:
            with lock:
                if getattr(self, "hangup_triggered", False) or getattr(self, "pending_hangup", False):
                    return
        else:
            if getattr(self, "hangup_triggered", False) or getattr(self, "pending_hangup", False):
                return

        call_sid = getattr(self, "call_sid", None)
        stream_sid = getattr(self, "stream_sid", None)
        bound_response_id = response_id or getattr(self, "active_response_id", None)

        msg_preview = (transcript_text or "").strip().replace("\n", " ")[:120]
        logger.info(
            f"[HANGUP_REQUEST] {reason} pending=true response_id={bound_response_id} "
            f"call_sid={call_sid} streamSid={stream_sid} text='{msg_preview}'"
        )
        logger.info(
            f"[HANGUP_REQUEST] {reason} pending=true response_id={bound_response_id} "
            f"call_sid={call_sid} streamSid={stream_sid} text='{msg_preview}'"
        )

        if not call_sid:
            logger.error("[HANGUP_REQUEST] error missing_call_sid (cannot hangup)")
            logger.error("[HANGUP_REQUEST] error missing_call_sid (cannot hangup)")
            return

        # Mark pending; actual hangup happens in response.audio.done handler after queues drain.
        try:
            if lock:
                with lock:
                    self.pending_hangup = True
                    self.pending_hangup_reason = reason
                    self.pending_hangup_source = source
                    self.pending_hangup_response_id = bound_response_id
                    self.pending_hangup_set_at = time.time()
            else:
                self.pending_hangup = True
                self.pending_hangup_reason = reason
                self.pending_hangup_source = source
                self.pending_hangup_response_id = bound_response_id
                self.pending_hangup_set_at = time.time()

            # Fallback: if we never get response.audio.done for this response_id (mismatch/cancel/missed event),
            # don't get stuck pending forever. Fire after >=8s (and do not cut bot audio if still playing).
            # 🔥 FIX: Increased from 6s to 8s per expert feedback for safer audio drain
            try:
                # Cancel previous fallback timer (if any)
                prev = getattr(self, "_pending_hangup_fallback_task", None)
                if prev and not prev.done():
                    prev.cancel()
            except Exception:
                pass

            try:
                self._pending_hangup_set_mono = time.monotonic()
            except Exception:
                self._pending_hangup_set_mono = None

            async def _polite_hangup_fallback_timer(expected_response_id: Optional[str], expected_call_sid: Optional[str]):
                try:
                    await asyncio.sleep(15.0)  # 🔥 FIX: Increased from 8s to 15s to allow proper audio drain
                    # Only fire if still pending and still for the same response_id (one-shot)
                    if getattr(self, "hangup_triggered", False):
                        return
                    if not getattr(self, "pending_hangup", False):
                        return
                    if expected_response_id and getattr(self, "pending_hangup_response_id", None) != expected_response_id:
                        return

                    # Never cut bot audio: if AI is still speaking or queues are still draining, wait longer.
                    # 🔥 FIX: Increased grace window from 8s to 15s for safer audio drain
                    try:
                        extra_deadline = time.monotonic() + 15.0  # additional grace window (was 8.0)
                        while time.monotonic() < extra_deadline:
                            ai_speaking = False
                            try:
                                ev = getattr(self, "is_ai_speaking_event", None)
                                ai_speaking = bool(ev and ev.is_set())
                            except Exception:
                                ai_speaking = False

                            oai_q = 0
                            tx_q = 0
                            try:
                                q1 = getattr(self, "realtime_audio_out_queue", None)
                                if q1:
                                    oai_q = q1.qsize()
                            except Exception:
                                oai_q = 0
                            try:
                                q2 = getattr(self, "tx_q", None)
                                if q2:
                                    tx_q = q2.qsize()
                            except Exception:
                                tx_q = 0

                            if ai_speaking or oai_q > 0 or tx_q > 0:
                                _orig_print(f"⏳ [POLITE_HANGUP] Waiting for audio: ai_speaking={ai_speaking}, oai_q={oai_q}, tx_q={tx_q}", flush=True)
                                await asyncio.sleep(0.5)
                                continue
                            break
                    except Exception as e:
                        logger.exception("[POLITE_HANGUP] Error in grace period check")

                    logger.info("[POLITE_HANGUP] fallback timer fired - all audio queues empty")
                    logger.info("[POLITE_HANGUP] fallback timer fired - all audio queues empty")

                    call_sid_local = expected_call_sid or getattr(self, "call_sid", None)
                    if not call_sid_local:
                        logger.error("[HANGUP] error missing_call_sid")
                        return

                    # Trigger hangup now (best-effort). We intentionally skip queue-drain here because
                    # we are already in a missing-audio.done scenario.
                    self.hangup_triggered = True
                    self.call_state = CallState.ENDED
                    try:
                        self.pending_hangup = False
                    except Exception:
                        pass
                    logger.info(
                        f"[HANGUP] executing reason={getattr(self, 'pending_hangup_reason', 'unknown')} "
                        f"response_id={expected_response_id} call_sid={call_sid_local}"
                    )
                    try:
                        from server.services.twilio_call_control import hangup_call
                        await asyncio.to_thread(hangup_call, call_sid_local)
                        logger.error(f"[HANGUP] success call_sid={call_sid_local}")
                    except Exception as e:
                        logger.error(f"[HANGUP] error call_sid={call_sid_local} err={type(e).__name__}:{str(e)[:200]}")
                        logger.exception("[HANGUP] error call_sid=%s", call_sid_local)
                except asyncio.CancelledError:
                    return
                except Exception:
                    # Never crash realtime loop due to fallback timer
                    logger.exception("[POLITE_HANGUP] fallback timer error")

            self._pending_hangup_fallback_task = asyncio.create_task(
                _polite_hangup_fallback_timer(bound_response_id, call_sid)
            )

            # Ensure we don't re-send a goodbye during hangup flows.
            if reason == "bot_goodbye":
                self.goodbye_message_sent = True
            if self.call_state == CallState.ACTIVE:
                self.call_state = CallState.CLOSING
        except Exception:
            pass

    def _looks_like_user_goodbye(self, text: str) -> bool:
        """
        🔧 FIX: Detect USER goodbye phrases (separate from AI polite closing)
        
        User goodbye phrases include:
        - Clear goodbye: "ביי", "להתראות", "bye", "goodbye"
        - Polite endings: "תודה רבה", "אין צורך", "לא צריך", "אפשר לסיים"
        - Combined phrases: "תודה וביי", "תודה להתראות"
        
        This is used to track user_said_goodbye separately from AI polite closing.
        
        Args:
            text: User transcript to check
            
        Returns:
            True if user is ending the call
        """
        intent = self._classify_real_hangup_intent(text, "user")
        return intent in ("hangup", "clarify")
    
    def _check_goodbye_phrases(self, text: str) -> bool:
        """
        🎯 BUILD 163 STRICT: Check if text contains CLEAR goodbye phrases
        
        Logic:
        - ONLY "ביי/להתראות" and combinations trigger hangup
        - "תודה" alone = NOT goodbye
        - "אין צורך/לא צריך" = NOT goodbye (continues conversation)
        - "היי כבי/היי ביי" = IGNORE (not goodbye!)
        
        Args:
            text: User or AI transcribed text to check
            
        Returns:
            True if CLEAR goodbye phrase detected
        """
        text_lower = text.lower().strip()
        
        # 🛡️ IGNORE LIST: Phrases that sound like goodbye but aren't!
        for ignore in GOODBYE_IGNORE_PHRASES:
            if ignore in text_lower:
                logger.info(f"[GOODBYE CHECK] IGNORED phrase (not goodbye): '{text_lower[:30]}...'")
                return False
        
        # 🛡️ FILTER: Exclude greetings that sound like goodbye
        for greeting in GOODBYE_GREETING_WORDS:
            if greeting in text_lower and "ביי" not in text_lower and "להתראות" not in text_lower:
                logger.info(f"[GOODBYE CHECK] Skipping greeting: '{text_lower[:30]}...'")
                return False
        
        # ✅ CLEAR goodbye words - ONLY these trigger hangup! Use shared constant
        has_clear_goodbye = any(word in text_lower for word in CLEAR_GOODBYE_WORDS)
        
        if has_clear_goodbye:
            logger.info(f"[GOODBYE CHECK] Clear goodbye detected: '{text_lower[:30]}...'")
            return True
        
        # ✅ Combined phrases with goodbye words
        combined_goodbye_phrases = [
            "תודה וביי", "תודה להתראות",
            "תודה רבה וביי", "תודה רבה להתראות"
        ]
        
        for phrase in combined_goodbye_phrases:
            if phrase in text_lower:
                logger.info(f"[GOODBYE CHECK] Combined goodbye phrase: '{phrase}'")
                return True
        
        # 🚫 Everything else is NOT goodbye (including "תודה", "אין צורך", "לא צריך")
        logger.info(f"[GOODBYE CHECK] No goodbye phrase: '{text_lower[:30]}...'")
        return False

    def _check_polite_closing(self, text: str) -> bool:
        """
        🎯 STRICT: Check if AI said EXPLICIT goodbye phrases (ביי/להתראות ONLY!)
        
        🔥 CRITICAL RULE: Only disconnect if there's an EXPLICIT goodbye word!
        - "תודה יחזרו אליך" alone = NO DISCONNECT (just callback promise)
        - "תודה ביי" = DISCONNECT (explicit goodbye)
        - "יחזרו אליך ביי" = DISCONNECT (explicit goodbye)
        
        This prevents premature disconnections from polite callback promises.
        
        Args:
            text: AI transcript to check
            
        Returns:
            True ONLY if explicit goodbye word detected (ביי/להתראות/bye/goodbye)
        """
        text_lower = text.lower().strip()
        
        # 🛡️ IGNORE LIST: Phrases that sound like goodbye but aren't!
        for ignore in GOODBYE_IGNORE_PHRASES:
            if ignore in text_lower:
                logger.info(f"[POLITE CLOSING] IGNORED phrase (not goodbye): '{text_lower[:30]}...'")
                return False
        
        # 🛡️ FILTER: Exclude greetings that sound like goodbye
        for greeting in GOODBYE_GREETING_WORDS:
            if greeting in text_lower and "ביי" not in text_lower and "להתראות" not in text_lower:
                logger.info(f"[POLITE CLOSING] Skipping greeting: '{text_lower[:30]}...'")
                return False
        
        # ✅ EXPLICIT GOODBYE WORDS - The ONLY trigger for disconnection!
        explicit_goodbye_words = ["ביי", "להתראות", "bye", "goodbye"]
        
        has_explicit_goodbye = any(word in text_lower for word in explicit_goodbye_words)
        
        if has_explicit_goodbye:
            logger.info(f"[POLITE CLOSING] ✅ EXPLICIT goodbye detected: '{text_lower[:80]}...'")
            return True
        
        # 🚫 NO explicit goodbye = NO disconnect (even with "תודה", "יחזרו אליך", etc.)
        logger.error(f"[POLITE CLOSING] ❌ No explicit goodbye (no ביי/להתראות): '{text_lower[:80]}...'")
        return False

    # ═══════════════════════════════════════════════════════════════════════════
    # 🔥 BUILD 313: SIMPLE LEAD CAPTURE - Let OpenAI do all the understanding!
    # No word lists, no fuzzy matching, no city normalizer - just pure AI
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _build_lead_capture_tool(self):
        """
        🔥 BUILD 313: Build dynamic tool schema based on required_lead_fields
        
        Creates a save_lead_info tool that OpenAI can call when user provides info.
        Schema is generated dynamically from business config - 100% database-driven!
        
        Returns:
            Tool definition dict, or None if no fields required
        """
        required_fields = getattr(self, 'required_lead_fields', [])
        
        # Skip if only phone (always captured from Twilio) or no fields
        fields_to_capture = [f for f in required_fields if f != 'phone']
        if not fields_to_capture:
            return None
        
        # Build properties based on required fields
        properties = {}
        required_props = []
        
        field_descriptions = {
            'name': 'שם הלקוח (כפי שהוא אמר)',
            'city': 'שם העיר שהלקוח אמר (בדיוק כפי שהוא אמר)',
            'service_type': 'סוג השירות שהלקוח צריך',
            'budget': 'תקציב הלקוח (מספר בשקלים)',
            'email': 'כתובת אימייל',
            'preferred_time': 'זמן מועדף לפגישה',
            'notes': 'הערות נוספות או תיאור הבעיה'
        }
        
        for field in fields_to_capture:
            desc = field_descriptions.get(field, f'ערך עבור {field}')
            properties[field] = {
                "type": "string",
                "description": desc
            }
        
        tool = {
            "type": "function",
            "name": "save_lead_info",
            "description": "שמור פרטים שהלקוח מסר בשיחה. קרא לפונקציה הזו כשהלקוח נותן מידע כמו שם, עיר, או סוג שירות.",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": []  # None required - save whatever user provides
            }
        }
        
        logger.info(f"🔧 [BUILD 313] Tool schema built for fields: {fields_to_capture}")
        return tool
    
    async def _handle_function_call(self, event: dict, client):
        """
        🔥 BUILD 313: Handle OpenAI function calls for lead capture
        
        When AI calls save_lead_info, we extract the fields and update lead_capture_state.
        No fuzzy matching, no word lists - just trust what OpenAI extracted!
        
        ⚠️ CRITICAL: ALL response.create calls in this function MUST use trigger_response_from_tool()
        DO NOT use client.send_event({"type": "response.create"}) directly!
        This ensures session gate, user_speaking, hangup checks, and cost tracking apply.
        """
        import json
        
        function_name = event.get("name", "")
        call_id = event.get("call_id", "")
        arguments_str = event.get("arguments", "{}")
        
        logger.info(f"🔧 [BUILD 313] Function call: {function_name}, call_id={call_id[:20] if call_id else 'none'}...")
        
        if function_name == "save_lead_info":
            try:
                args = json.loads(arguments_str)
                logger.info(f"📝 [BUILD 313] Lead info from AI: {args}")
                
                # Update lead_capture_state with each field AI provided
                for field, value in args.items():
                    if value and str(value).strip():
                        self._update_lead_capture_state(field, str(value).strip())
                        logger.info(f"✅ [BUILD 313] Saved {field} = '{value}'")
                
                # Send success response back to AI
                await client.send_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({"success": True, "saved_fields": list(args.keys())})
                    }
                })
                
                # Trigger response to continue conversation - 🔥 USE WRAPPER
                triggered = await self.trigger_response_from_tool(client, "save_lead_info", force=False)
                if not triggered:
                    logger.warning(f"⚠️ [TOOL] save_lead_info response blocked by guard")
                
                # Check if all fields are captured
                self._check_lead_complete()
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ [BUILD 313] Failed to parse function arguments: {e}")
                await client.send_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({"success": False, "error": str(e)})
                    }
                })
                # 🔥 USE WRAPPER - Even on error, need response
                await self.trigger_response_from_tool(client, "save_lead_info_error", force=False)
        
        elif function_name == "check_availability":
            # 🔥 CHECK AVAILABILITY: Must be called before offering times
            try:
                args = json.loads(arguments_str)
                logger.info(f"📅 [CHECK_AVAIL] Request from AI: {args}")
                logger.info(f"[CHECK_AVAIL] Checking availability: {args}")
                
                business_id = getattr(self, 'business_id', None)
                if not business_id:
                    logger.error(f"❌ [CHECK_AVAIL] No business_id available")
                    logger.error("[CHECK_AVAIL] No business_id in session")
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error": "אין גישה למערכת כרגע"
                            })
                        }
                    })
                    await self.trigger_response_from_tool(client, "check_availability_success", force=False)
                    return
                
                # 🔥 CRITICAL: Verify call_goal is appointment
                call_goal = getattr(self, 'call_goal', 'lead_only')
                if call_goal != 'appointment':
                    logger.error(f"❌ [CHECK_AVAIL] call_goal={call_goal} - appointments not enabled")
                    logger.warning(f"[CHECK_AVAIL] Blocked: call_goal={call_goal} (expected 'appointment')")
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error": "תיאום פגישות לא זמין כרגע"
                            }, ensure_ascii=False)
                        }
                    })
                    await self.trigger_response_from_tool(client, "unknown_success", force=False)
                    return
                
                # Extract parameters (may be Hebrew, server will normalize)
                date_str_raw = args.get("date", "").strip()
                preferred_time_raw = args.get("preferred_time", "").strip()
                service_type = args.get("service_type", "").strip()
                
                if not date_str_raw:
                    logger.error(f"❌ [CHECK_AVAIL] Missing date")
                    user_msg = "על איזה תאריך מדובר? למשל היום/מחר/יום ראשון."
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error": "חסר תאריך",
                                "error_code": "missing_date",
                                "user_message": user_msg
                            })
                        }
                    })
                    # ✅ Tool-flow: on failure, speak server-provided user_message (no improvisation).
                    await client.send_event(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "system",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                    }
                                ],
                            },
                        }
                    )
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    return
                
                # Call calendar_find_slots implementation
                try:
                    from server.agent_tools.tools_calendar import FindSlotsInput, _calendar_find_slots_impl
                    from server.policy.business_policy import get_business_policy
                    import pytz
                    from datetime import datetime
                    from server.services.hebrew_datetime import (
                        resolve_hebrew_date,
                        resolve_hebrew_time,
                        pick_best_time_candidate,
                        auto_correct_iso_year,
                    )
                    
                    # Get policy to determine duration
                    policy = get_business_policy(business_id)
                    duration_min = policy.slot_size_min  # Use business slot size
                    business_tz = pytz.timezone(policy.tz)
                    
                    # Normalize date (accepts "היום/מחר/ראשון" etc.)
                    date_res = resolve_hebrew_date(date_str_raw, business_tz)
                    if not date_res:
                        logger.error(f"❌ [CHECK_AVAIL] Invalid date input: '{date_str_raw}'")
                        user_msg = "לא הצלחתי להבין את התאריך. אפשר תאריך אחר? למשל מחר או יום ראשון."
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error": "תאריך לא תקין. בקש תאריך אחר.",
                                    "error_code": "invalid_date",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return
                    
                    normalized_date_iso = date_res.date_iso
                    weekday_he = date_res.weekday_he
                    date_display_he = date_res.date_display_he

                    # 🔥 FIX #1: Auto-correct suspicious ISO year BEFORE past-date guard.
                    # LLMs sometimes send training-data years (e.g., 2023) even when user didn't specify a year.
                    corrected_iso, corrected, reason = auto_correct_iso_year(
                        normalized_date_iso,
                        business_tz,
                    )
                    if corrected:
                        logger.info(f"🔧 [CHECK_AVAIL] Auto-corrected year: {normalized_date_iso} → {corrected_iso} "
                            f"(reason={reason}) raw='{date_str_raw}'")
                        # Re-resolve display/weekday to match corrected date.
                        corrected_res = resolve_hebrew_date(corrected_iso, business_tz)
                        if corrected_res:
                            normalized_date_iso = corrected_res.date_iso
                            weekday_he = corrected_res.weekday_he
                            date_display_he = corrected_res.date_display_he
                        else:
                            normalized_date_iso = corrected_iso

                    # 🛡️ SAFETY: If the resolved date is in the past, DO NOT query availability.
                    # Force the model to ask for a new date instead of looping on a past date.
                    today_local = datetime.now(business_tz).date()
                    try:
                        y, m, d = map(int, normalized_date_iso.split("-"))
                        requested_date = datetime(y, m, d, tzinfo=business_tz).date()
                    except Exception:
                        requested_date = None
                    if requested_date and requested_date < today_local:
                        logger.warning(f"⚠️ [CHECK_AVAIL] Past date rejected: {normalized_date_iso} (today={today_local.isoformat()}) raw='{date_str_raw}'")
                        user_msg = "זה תאריך שכבר עבר. אפשר תאריך חדש? למשל מחר או שבוע הבא."
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "past_date",
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "error": "התאריך שיצא הוא בעבר. חובה לבקש תאריך חדש מהלקוח (היום/מחר/תאריך אחר).",
                                    # ✅ Provide a deterministic phrase the model MUST say (avoid improvisation/stalls)
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return
                    
                    # Normalize preferred time (optional)
                    preferred_time = None
                    if preferred_time_raw:
                        time_res = resolve_hebrew_time(preferred_time_raw)
                        if time_res and time_res.candidates_hhmm:
                            preferred_time = pick_best_time_candidate(time_res.candidates_hhmm)
                    
                    logger.info(f"📅 [CHECK_AVAIL] Checking {normalized_date_iso} ({date_display_he}) preferred_time={preferred_time or '-'} duration={duration_min}min")
                    logger.info(f"[CHECK_AVAIL] business_id={business_id}, date={normalized_date_iso}, preferred_time={preferred_time}")
                    
                    input_data = FindSlotsInput(
                        business_id=business_id,
                        date_iso=normalized_date_iso,
                        duration_min=duration_min,
                        preferred_time=preferred_time if preferred_time else None
                    )
                    
                    # 🔥 CRITICAL: Database queries need app_context in async/WebSocket context
                    app = _get_flask_app()
                    with app.app_context():
                        result = _calendar_find_slots_impl(input_data)
                    
                    # Format response
                    if result.slots and len(result.slots) > 0:
                        slots_display = [slot.start_display for slot in result.slots[:3]]  # Max 3 slots
                        logger.info(f"✅ [CHECK_AVAIL] CAL_AVAIL_OK - Found {len(result.slots)} slots: {slots_display}")
                        logger.info(f"✅ CAL_AVAIL_OK business_id={business_id} date={normalized_date_iso} slots_found={len(result.slots)} slots={slots_display}")
                        
                        # Persist availability context for later booking enforcement
                        try:
                            self._last_availability = {
                                "date_iso": normalized_date_iso,
                                "weekday_he": weekday_he,
                                "date_display_he": date_display_he,
                                "slots": slots_display,
                                "ts": time.time(),
                            }
                            crm_context = getattr(self, "crm_context", None)
                            if crm_context:
                                crm_context.pending_slot = {
                                    "date": normalized_date_iso,
                                    "time": preferred_time or "",
                                    "available": True,
                                }
                        except Exception:
                            pass
                        
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": True,
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "slots": slots_display,
                                    "business_hours": result.business_hours,
                                    "message": f"יש זמנים פנויים ב-{date_display_he}"
                                }, ensure_ascii=False)
                            }
                        })
                    else:
                        logger.warning(f"⚠️ [CHECK_AVAIL] No slots available for {normalized_date_iso}")
                        logger.warning(f"[CHECK_AVAIL] No slots found for business_id={business_id} date={normalized_date_iso}")
                        user_msg = "אין זמנים פנויים בתאריך הזה. אפשר תאריך אחר? למשל מחר או שבוע הבא."
                        
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "error": f"אין זמנים פנויים ב-{date_display_he}. הצע תאריך אחר.",
                                    "error_code": "no_slots",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                    
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    
                except Exception as slots_error:
                    logger.error(f"❌ [CHECK_AVAIL] Failed to check slots: {slots_error}")
                    logger.error(f"[CHECK_AVAIL] Exception: {slots_error}")
                    import traceback
                    traceback.print_exc()
                    user_msg = "יש בעיה לבדוק זמינות כרגע. אפשר תאריך אחר או לנסות שוב עוד מעט?"
                    
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error": "בעיה בבדיקת זמינות. בקש מהלקוח תאריך אחר.",
                                "error_code": "calendar_error",
                                "user_message": user_msg,
                            })
                        }
                    })
                    await client.send_event(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "system",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                    }
                                ],
                            },
                        }
                    )
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ [CHECK_AVAIL] Failed to parse arguments: {e}")
                await client.send_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({"success": False, "error": str(e)})
                    }
                })
                await self.trigger_response_from_tool(client, "unknown_success", force=False)
        
        elif function_name == "schedule_appointment":
            # 🔥 APPOINTMENT SCHEDULING: Goal-based with structured errors
            try:
                args = json.loads(arguments_str)
                logger.info(f"📅 [APPOINTMENT] Request from AI: {args}")
                
                # 🔥 STEP 1: Check call_goal and scheduling enabled
                business_id = getattr(self, 'business_id', None)
                if not business_id:
                    logger.error(f"❌ [APPOINTMENT] No business_id available")
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "no_business_context"
                            })
                        }
                    })
                    await self.trigger_response_from_tool(client, "schedule_appointment_success", force=False)
                    return
                
                # Check if already created appointment in this session
                if getattr(self, '_appointment_created_this_session', False):
                    logger.warning(f"⚠️ [APPOINTMENT] Already created appointment in this session - blocking duplicate")
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "appointment_already_created"
                            })
                        }
                    })
                    await self.trigger_response_from_tool(client, "unknown_success", force=False)
                    return
                
                # 🔥 CRITICAL: Check call_goal is appointment
                call_goal = getattr(self, 'call_goal', 'lead_only')
                if call_goal != 'appointment':
                    logger.error(f"❌ [APPOINTMENT] call_goal={call_goal} - appointments not enabled")
                    logger.warning(f"[APPOINTMENT] Blocked: call_goal={call_goal} (expected 'appointment')")
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "scheduling_disabled",
                                "message": "תיאום פגישות לא זמין. אני יכול לרשום פרטים ובעל העסק יחזור אליך."
                            }, ensure_ascii=False)
                        }
                    })
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    return
                
                # 🔥 STEP 2: Extract and validate fields
                customer_name = args.get("customer_name", "").strip()
                appointment_date_raw = args.get("appointment_date", "").strip()  # YYYY-MM-DD OR Hebrew
                appointment_time_raw = args.get("appointment_time", "").strip()  # HH:MM OR Hebrew
                service_type = args.get("service_type", "").strip()
                
                # 🔥 STEP 3: Use customer_phone from call context
                # Phone is OPTIONAL by default; only required if BusinessPolicy requires it.
                customer_phone = getattr(self, 'phone_number', None) or getattr(self, 'caller_number', None) or None
                
                if not customer_name:
                    logger.error(f"❌ [APPOINTMENT] Missing customer_name")
                    user_msg = "על איזה שם לרשום את הפגישה?"
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "missing_name",
                                "user_message": user_msg
                            })
                        }
                    })
                    await client.send_event(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "system",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                    }
                                ],
                            },
                        }
                    )
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    return
                
                if not appointment_date_raw or not appointment_time_raw:
                    logger.error(f"❌ [APPOINTMENT] Missing date or time")
                    user_msg = "כדי לקבוע תור אני צריכה תאריך ושעה. לאיזה יום ובאיזו שעה?"
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "missing_datetime",
                                "user_message": user_msg
                            })
                        }
                    })
                    await client.send_event(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "system",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                    }
                                ],
                            },
                        }
                    )
                    await self.trigger_response_from_tool(client, "unknown", force=False)
                    return
                
                logger.info(f"📅 [APPOINTMENT] Inputs: name={customer_name}, phone={customer_phone}, date='{appointment_date_raw}', time='{appointment_time_raw}'")
                
                # 🔥 STEP 4: Create appointment using unified implementation
                try:
                    from datetime import datetime, timedelta
                    import pytz
                    from server.agent_tools.tools_calendar import (
                        CreateAppointmentInput,
                        _calendar_create_appointment_impl,
                        FindSlotsInput,
                        _calendar_find_slots_impl,
                    )
                    from server.policy.business_policy import get_business_policy
                    from server.services.hebrew_datetime import (
                        resolve_hebrew_date,
                        resolve_hebrew_time,
                        auto_correct_iso_year,
                    )
                    
                    # Get policy and timezone
                    policy = get_business_policy(business_id)
                    tz = pytz.timezone(policy.tz)
                    
                    # Normalize date/time (server-side; do not rely on the model)
                    date_res = resolve_hebrew_date(appointment_date_raw, tz)
                    if not date_res:
                        logger.error(f"❌ [APPOINTMENT] Invalid date input: '{appointment_date_raw}'")
                        user_msg = "לא הצלחתי להבין את התאריך. אפשר תאריך אחר? למשל מחר או יום ראשון."
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "invalid_date",
                                    "message": "תאריך לא תקין. בקש תאריך אחר.",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return
                    
                    time_res = resolve_hebrew_time(appointment_time_raw)
                    if not time_res or not time_res.candidates_hhmm:
                        logger.error(f"❌ [APPOINTMENT] Invalid time input: '{appointment_time_raw}'")
                        user_msg = "באיזו שעה? אפשר להגיד למשל 15:00 או ארבע."
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "invalid_time",
                                    "message": "שעה לא תקינה. בקש שעה בפורמט HH:MM או שעה ברורה.",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return
                    
                    normalized_date_iso = date_res.date_iso
                    weekday_he = date_res.weekday_he
                    date_display_he = date_res.date_display_he

                    # 🔥 FIX #1: Auto-correct suspicious ISO year BEFORE past-date guard.
                    corrected_iso, corrected, reason = auto_correct_iso_year(
                        normalized_date_iso,
                        tz,
                    )
                    if corrected:
                        logger.info(f"🔧 [APPOINTMENT] Auto-corrected year: {normalized_date_iso} → {corrected_iso} "
                            f"(reason={reason}) raw='{appointment_date_raw}'")
                        corrected_res = resolve_hebrew_date(corrected_iso, tz)
                        if corrected_res:
                            normalized_date_iso = corrected_res.date_iso
                            weekday_he = corrected_res.weekday_he
                            date_display_he = corrected_res.date_display_he
                        else:
                            normalized_date_iso = corrected_iso

                    # 🛡️ SAFETY: Never attempt booking on a past date.
                    today_local = datetime.now(tz).date()
                    try:
                        y, m, d = map(int, normalized_date_iso.split("-"))
                        requested_date = datetime(y, m, d, tzinfo=tz).date()
                    except Exception:
                        requested_date = None
                    if requested_date and requested_date < today_local:
                        logger.warning(f"⚠️ [APPOINTMENT] Past date rejected: {normalized_date_iso} (today={today_local.isoformat()}) raw='{appointment_date_raw}'")
                        user_msg = "זה תאריך שכבר עבר. אפשר תאריך חדש? למשל מחר או שבוע הבא."
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "past_date",
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "message": "התאריך שיצא הוא בעבר. חובה לבקש תאריך חדש (היום/מחר/תאריך אחר).",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return

                    # ✅ SOFT RULE: Prefer prior check_availability, but never hard-block.
                    # If we don't have a recent enough context, we will refresh availability automatically.
                    # This avoids friction for long calls and for "change only the time on the same day".
                    last_av = getattr(self, "_last_availability", None) or {}
                    last_av_date = last_av.get("date_iso")
                    last_av_ts = float(last_av.get("ts") or 0)
                    availability_age_sec = time.time() - last_av_ts if last_av_ts else None
                    # If we have date match and the requested time is within previously returned slots,
                    # we can proceed even if it's old (we still re-check below per candidate).
                    need_refresh = (
                        (not last_av_date) or
                        (last_av_date != normalized_date_iso) or
                        (availability_age_sec is not None and availability_age_sec > 900)
                    )
                    if need_refresh:
                        # Lightweight refresh: run find_slots once so the model stays anchored to server state.
                        try:
                            preferred_for_refresh = time_res.candidates_hhmm[0] if time_res.candidates_hhmm else None
                            # 🔥 CRITICAL: Database queries need app_context in async/WebSocket context
                            app = _get_flask_app()
                            with app.app_context():
                                slots_result = _calendar_find_slots_impl(
                                    FindSlotsInput(
                                        business_id=business_id,
                                        date_iso=normalized_date_iso,
                                        duration_min=policy.slot_size_min,
                                        preferred_time=preferred_for_refresh,
                                    )
                                )
                            refreshed_slots = [s.start_display for s in (slots_result.slots or [])][:3]
                            self._last_availability = {
                                "date_iso": normalized_date_iso,
                                "weekday_he": weekday_he,
                                "date_display_he": date_display_he,
                                "slots": refreshed_slots,
                                "ts": time.time(),
                                "source": "auto_refresh_from_schedule",
                            }
                            logger.info(f"🔄 [APPOINTMENT] Auto-refreshed availability for {normalized_date_iso}: {refreshed_slots}")
                        except Exception as _refresh_err:
                            logger.error(f"⚠️ [APPOINTMENT] Availability auto-refresh failed (continuing): {_refresh_err}")
                    
                    # 🔥 HARD RULE: availability check BEFORE creating appointment
                    duration_min = policy.slot_size_min
                    chosen_time = None
                    alternatives: list[str] = []
                    # 🔥 CRITICAL: Database queries need app_context in async/WebSocket context
                    app = _get_flask_app()
                    with app.app_context():
                        for cand in time_res.candidates_hhmm:
                            try:
                                slots_result = _calendar_find_slots_impl(
                                    FindSlotsInput(
                                        business_id=business_id,
                                        date_iso=normalized_date_iso,
                                        duration_min=duration_min,
                                        preferred_time=cand,
                                    )
                                )
                                alternatives = [s.start_display for s in (slots_result.slots or [])][:2]
                                if slots_result.slots and any(s.start_display == cand for s in slots_result.slots):
                                    chosen_time = cand
                                    break
                            except Exception:
                                continue
                    
                    if not chosen_time:
                        logger.warning(f"⚠️ [APPOINTMENT] Slot not available: date={normalized_date_iso} time_candidates={time_res.candidates_hhmm} alternatives={alternatives}")
                        crm_context = getattr(self, "crm_context", None)
                        if crm_context:
                            crm_context.pending_slot = {
                                "date": normalized_date_iso,
                                "time": appointment_time_raw,
                                "available": False,
                            }
                        user_msg = "השעה שביקשת לא פנויה. מתאים לך אחת מהחלופות, או שתרצה שעה אחרת?"
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "slot_unavailable",
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "requested_time_raw": appointment_time_raw,
                                    "alternative_times": alternatives,
                                    "message": "השעה שביקשת לא פנויה. הצע חלופות מהשרת.",
                                    "user_message": user_msg
                                }, ensure_ascii=False)
                            }
                        })
                        await client.send_event(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                        }
                                    ],
                                },
                            }
                        )
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        return
                    
                    # Parse and localize datetime
                    datetime_str = f"{normalized_date_iso} {chosen_time}"
                    requested_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                    requested_dt = tz.localize(requested_dt)
                    
                    # Calculate end time
                    slot_duration = timedelta(minutes=policy.slot_size_min)
                    end_dt = requested_dt + slot_duration
                    
                    logger.info(f"📅 [APPOINTMENT] Creating: {date_display_he} {chosen_time} ({requested_dt.isoformat()} -> {end_dt.isoformat()})")
                    
                    # 🔥 BUILD 144: Generate call summary and transcript
                    call_summary = None
                    call_transcript = None
                    try:
                        from server.services.summary_service import summarize_conversation
                        from server.models_sql import Business
                        
                        # Build transcript from conversation history
                        conversation_history = getattr(self, 'conversation_history', [])
                        if conversation_history:
                            transcription_parts = []
                            for turn in conversation_history:
                                if isinstance(turn, dict):
                                    speaker = turn.get('speaker', '')
                                    text = turn.get('text', '')
                                    if speaker == 'user' and text:
                                        transcription_parts.append(f"לקוח: {text}")
                                    elif speaker == 'ai' and text:
                                        transcription_parts.append(f"נציג: {text}")
                            
                            call_transcript = "\n".join(transcription_parts)
                            
                            if call_transcript:
                                # Get business info for context
                                business = Business.query.get(business_id)
                                business_name = business.name if business else None
                                
                                # Generate AI summary
                                call_sid = getattr(self, 'call_sid', None)
                                call_summary = summarize_conversation(
                                    transcription=call_transcript,
                                    call_sid=call_sid,
                                    business_name=business_name
                                )
                                logger.info(f"✅ [APPOINTMENT] Call summary and transcript generated ({len(call_transcript)} chars)")
                    except Exception as e:
                        logger.error(f"⚠️ [APPOINTMENT] Failed to generate call summary: {e}")
                        # Continue without summary - not critical
                    
                    # Build context for _calendar_create_appointment_impl
                    # Prefer caller-id/call context phone even if user didn't provide DTMF.
                    caller_id = getattr(self, 'phone_number', None) or getattr(self, 'caller_number', None) or None
                    phone_for_notes = customer_phone or caller_id
                    
                    # 🔥 FIX: Include ALL phone-related keys that tools_calendar.py checks for
                    # tools_calendar.py checks: customer_phone, caller_number, from_number, whatsapp_from
                    context = {
                        "customer_phone": phone_for_notes,
                        "caller_number": phone_for_notes,  # ← Add this key
                        "from_number": phone_for_notes,    # ← Add this key
                        "channel": "phone",
                        "call_sid": getattr(self, 'call_sid', None),  # ← Add call_sid for call_log linking
                    }
                    
                    # Create input
                    input_data = CreateAppointmentInput(
                        business_id=business_id,
                        customer_name=customer_name,
                        customer_phone=phone_for_notes,
                        treatment_type=service_type or "Appointment",
                        start_iso=requested_dt.isoformat(),
                        end_iso=end_dt.isoformat(),
                        notes=(
                            "Scheduled via phone call. "
                            + (f"Caller ID: {caller_id}. " if caller_id else "")
                            + ("Phone not collected (policy optional)." if not phone_for_notes else "")
                        ),
                        source="realtime_phone",
                        call_summary=call_summary,  # 🔥 BUILD 144: Include call summary
                        call_transcript=call_transcript  # 🔥 BUILD 144: Include call transcript
                    )
                    
                    # Call unified implementation
                    # 🔥 CRITICAL: Database queries need app_context in async/WebSocket context
                    app = _get_flask_app()
                    with app.app_context():
                        result = _calendar_create_appointment_impl(input_data, context=context, session=self)
                    
                    # Handle result
                    if hasattr(result, 'appointment_id'):
                        # Success - CreateAppointmentOutput
                        appt_id = result.appointment_id
                        logger.info(f"✅ [APPOINTMENT] CAL_CREATE_OK event_id={appt_id}, status={result.status}")
                        logger.info(f"✅ CAL_CREATE_OK business_id={business_id} event_id={appt_id} customer={customer_name} date={normalized_date_iso} time={chosen_time} service={service_type}")
                        logger.info(f"APPOINTMENT_CREATED appointment_id={appt_id} business_id={business_id} date={normalized_date_iso} time={chosen_time}")
                        
                        # Mark as created to prevent duplicates
                        self._appointment_created_this_session = True
                        crm_context = getattr(self, "crm_context", None)
                        if crm_context:
                            crm_context.has_appointment_created = True
                            crm_context.last_appointment_id = appt_id
                            crm_context.pending_slot = {
                                "date": normalized_date_iso,
                                "time": chosen_time,
                                "available": True,
                            }
                        
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": True,
                                    "appointment_id": appt_id,
                                    "normalized_date": normalized_date_iso,
                                    "weekday_he": weekday_he,
                                    "date_display_he": date_display_he,
                                    "time_hhmm": chosen_time,
                                    "start_time": requested_dt.isoformat(),
                                    "end_time": end_dt.isoformat(),
                                    "customer_name": customer_name
                                }, ensure_ascii=False)
                            }
                        })
                        await self.trigger_response_from_tool(client, "unknown", force=False)
                        
                    elif isinstance(result, dict):
                        # Dict result (error or legacy format)
                        if result.get("ok") or result.get("success"):
                            appt_id = result.get("appointment_id")
                            logger.info(f"✅ [APPOINTMENT] SUCCESS (dict)! ID={appt_id}")
                            logger.info(f"APPOINTMENT_CREATED appointment_id={appt_id} business_id={business_id} date={normalized_date_iso} time={chosen_time}")
                            
                            # Mark as created
                            self._appointment_created_this_session = True
                            crm_context = getattr(self, "crm_context", None)
                            if crm_context and appt_id:
                                crm_context.has_appointment_created = True
                                crm_context.last_appointment_id = appt_id
                            
                            await client.send_event({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": json.dumps({
                                        "success": True,
                                        "appointment_id": appt_id,
                                        "normalized_date": normalized_date_iso,
                                        "weekday_he": weekday_he,
                                        "date_display_he": date_display_he,
                                        "time_hhmm": chosen_time,
                                        "start_time": requested_dt.isoformat(),
                                        "end_time": end_dt.isoformat(),
                                        "customer_name": customer_name
                                    }, ensure_ascii=False)
                                }
                            })
                            await self.trigger_response_from_tool(client, "unknown", force=False)
                        else:
                            # Error in dict
                            error_code = result.get("error", "unknown_error")
                            error_msg = result.get("message", "שגיאה ביצירת פגישה")
                            logger.error(f"❌ [APPOINTMENT] CAL_CREATE_FAILED: {error_code} - {error_msg}")
                            logger.error(f"❌ CAL_CREATE_FAILED business_id={business_id} error={error_code} message={error_msg} date={normalized_date_iso} time={chosen_time}")
                            user_msg = "יש בעיה לקבוע את התור כרגע. אפשר לנסות שעה אחרת או תאריך אחר?"
                            await client.send_event({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": json.dumps({
                                        "success": False,
                                        "error_code": error_code,
                                        "message": error_msg,
                                        "normalized_date": normalized_date_iso,
                                        "weekday_he": weekday_he,
                                        "date_display_he": date_display_he,
                                        "alternative_times": alternatives,
                                        "suggestion": "הצע עד 2 חלופות מהשרת.",
                                        "user_message": user_msg,
                                    }, ensure_ascii=False)
                                }
                            })
                            await client.send_event(
                                {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "system",
                                        "content": [
                                            {
                                                "type": "input_text",
                                                "text": f'SERVER: Reply in Hebrew with EXACTLY this sentence and nothing else: "{user_msg}"',
                                            }
                                        ],
                                    },
                                }
                            )
                            await self.trigger_response_from_tool(client, "unknown", force=False)
                    else:
                        # Unexpected format
                        logger.error(f"❌ [APPOINTMENT] Unexpected result type: {type(result)}")
                        await client.send_event({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({
                                    "success": False,
                                    "error_code": "server_error"
                                })
                            }
                        })
                        await self.trigger_response_from_tool(client, "unknown_success", force=False)
                        
                except (ValueError, AttributeError) as parse_error:
                    logger.error(f"❌ [APPOINTMENT] Error creating appointment: {parse_error}")
                    import traceback
                    traceback.print_exc()
                    await client.send_event({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": False,
                                "error_code": "invalid_datetime"
                            })
                        }
                    })
                    await self.trigger_response_from_tool(client, "unknown_success", force=False)
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ [APPOINTMENT] Failed to parse arguments: {e}")
                await client.send_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps({
                            "success": False,
                            "error_code": "invalid_arguments"
                        })
                    }
                })
                await self.trigger_response_from_tool(client, "unknown_success", force=False)
        
        else:
            logger.warning(f"⚠️ [BUILD 313] Unknown function: {function_name}")
    
    def _check_lead_complete(self):
        """
        🔥 BUILD 313: Check if all required lead fields are captured
        """
        required = set(getattr(self, 'required_lead_fields', []))
        captured = set(self.lead_capture_state.keys())
        
        # Phone is always captured from Twilio
        if 'phone' in required and hasattr(self, 'phone_number') and self.phone_number:
            captured.add('phone')
        
        missing = required - captured
        
        if not missing:
            self.lead_captured = True
            logger.info(f"🎯 [BUILD 313] All lead fields captured! {self.lead_capture_state}")
        else:
            # 🚫 DISABLED: City/service logic disabled via ENABLE_LEGACY_CITY_LOGIC flag
            if ENABLE_LEGACY_CITY_LOGIC:
                logger.info(f"📋 [BUILD 313] Still missing fields: {missing}")
    
    def _check_simple_appointment_keywords(self, ai_text: str):
        """
        ⭐ BUILD 350: SIMPLE KEYWORD-BASED APPOINTMENT DETECTION
        
        Detects when AI mentions appointment-related keywords and triggers scheduling.
        Only runs if appointments are enabled in business settings.
        
        NO NLP, NO Realtime Tools - just simple keyword matching.
        """
        if not ai_text:
            return
        
        # Check if appointments are enabled for this business
        business_settings = getattr(self, 'call_control_settings', None)
        if not business_settings or not getattr(business_settings, 'enable_appointments', False):
            return
        
        # Check if appointment already created
        if getattr(self, 'appointment_confirmed_in_session', False):
            return
        
        # Simple Hebrew appointment keywords
        appointment_keywords = [
            'פגישה', 'לתאם', 'תיאום', 'זמן פנוי', 'מועד', 'ביומן',
            'נקבע', 'קבעתי', 'נרשם', 'רשמתי', 'התור', 'תור'
        ]
        
        # Check if any keyword is present
        text_lower = ai_text.lower()
        found_keyword = None
        for keyword in appointment_keywords:
            if keyword in text_lower:
                found_keyword = keyword
                break
        
        if found_keyword:
            logger.info(f"📅 [BUILD 350] Appointment keyword detected: '{found_keyword}' in AI response")
            logger.info(f"📅 [BUILD 350] AI said: {ai_text[:100]}...")
            
            # TODO: Trigger your existing appointment creation logic here
            # For now, just log that we detected it
            # You can call: self.handle_appointment_request(...)
            # or: create_appointment_from_realtime(...)
            
            logger.info(f"📅 [BUILD 350] Simple appointment detection triggered - integrate with existing appointment logic if needed")
    
    def _extract_city_from_confirmation(self, text: str) -> str:
        """
        🔥 BUILD 313: SIMPLIFIED - Just extract city from pattern
        No city normalizer, no fuzzy matching - trust the AI!
        """
        import re
        
        # Simple patterns for city mention
        patterns = [
            r'ב([א-ת\s\-]{2,20})[,\s]+נכון',  # "בתל אביב, נכון?"
            r'(?:עיר|מ|ל)([א-ת\s\-]{2,20})[,\s]+נכון',  # "עיר חיפה, נכון?"
            r'ב([א-ת\s\-]{2,20})\?',  # "בחיפה?"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _build_confirmation_from_state(self) -> str:
        """
        🔥 BUILD 336: SERVER-SIDE TEMPLATED CONFIRMATION
        
        This ensures AI says the EXACT values from STT, not hallucinated ones.
        Uses lead_capture_state as the SINGLE SOURCE OF TRUTH (from STT).
        
        Returns confirmation template like:
        "רק מוודא — אתה צריך החלפת צילינדר במצפה רמון, נכון?"
        """
        state = self.lead_capture_state
        
        # 🔥 BUILD 336: Log what we're building from
        logger.info(f"📋 [BUILD 336] Building confirmation from STT state: {state}")
        
        # Get service and city - these are the EXACT values from STT
        service = state.get('service_type', '')
        city = state.get('city', '')
        name = state.get('name', '')
        
        # Build natural Hebrew confirmation
        if service and city:
            confirmation = f"רק מוודא — אתה צריך {service} ב{city}, נכון?"
        elif service:
            confirmation = f"רק מוודא — אתה צריך {service}, נכון?"
        elif city:
            confirmation = f"רק מוודא — אתה נמצא ב{city}, נכון?"
        else:
            # No data captured yet
            return ""
        
        # Add name if captured
        if name:
            confirmation = confirmation.replace("נכון?", f"והשם שלך {name}, נכון?")
        
        logger.info(f"🎯 [BUILD 336] SERVER CONFIRMATION: '{confirmation}'")
        logger.info(f"🔒 [BUILD 336] Values from STT: service='{service}', city='{city}', name='{name}'")
        return confirmation
    
    def _get_city_for_ai_response(self) -> str:
        """
        🔥 BUILD 326: Get city value for AI to use in responses
        
        If city is locked, ALWAYS returns the locked value.
        AI must use this instead of inventing its own city.
        """
        if self._city_locked and self._city_raw_from_stt:
            return self._city_raw_from_stt
        return self.lead_capture_state.get('city', '')

    def _extract_lead_fields_from_ai(self, ai_transcript: str, is_user_speech: bool = False):
        """
        🔥 BUILD 313: SIMPLIFIED - OpenAI Tool handles most extraction!
        
        This is now a minimal FALLBACK for basic patterns only.
        The main extraction happens via the save_lead_info Tool that OpenAI calls.
        
        Args:
            ai_transcript: The AI's transcribed speech
            is_user_speech: True if this is user speech, False if AI speech
        """
        import re
        
        text = ai_transcript.strip()
        if not text or len(text) < 3:
            return
        
        # 🔥 BUILD 313: ONLY extract from USER speech - AI speech should NEVER set lead fields!
        if not is_user_speech:
            # Track city mentioned by AI for user "נכון" confirmation
            if 'נכון' in text or 'מאשר' in text:
                # 🚫 DISABLED: City extraction disabled via ENABLE_LEGACY_CITY_LOGIC flag
                if ENABLE_LEGACY_CITY_LOGIC:
                    self._last_ai_mentioned_city = self._extract_city_from_confirmation(text)
            return
        
        # 🔥 BUILD 313: Minimal fallback patterns - OpenAI Tool handles the rest!
        required_fields = getattr(self, 'required_lead_fields', [])
        if not required_fields:
            return
        
        # 📧 EMAIL EXTRACTION: Simple pattern match (email format is universal)
        if 'email' in required_fields and 'email' not in self.lead_capture_state:
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            match = re.search(email_pattern, text)
            if match:
                self._update_lead_capture_state('email', match.group(0))
                logger.info(f"📧 [BUILD 313] Email extracted: {match.group(0)}")
        
        # 💰 BUDGET EXTRACTION: Numbers with currency (universal pattern)
        if 'budget' in required_fields and 'budget' not in self.lead_capture_state:
            budget_patterns = [
                r'(\d[\d,\.]*)\s*(?:שקל|ש"ח|₪)',  # "5000 שקל"
                r'תקציב\s+(?:של\s+)?(\d[\d,\.]*)',  # "תקציב של 5000"
            ]
            for pattern in budget_patterns:
                match = re.search(pattern, text)
                if match:
                    budget = match.group(1).replace(',', '')
                    self._update_lead_capture_state('budget', budget)
                    logger.info(f"💰 [BUILD 313] Budget extracted: {budget}")
                    break
        
        # ⭐ BUILD 350: CITY/SERVICE LOCK DISABLED - No mid-call extraction!
        # All field extraction happens ONLY from summary at end of call.
        if ENABLE_LEGACY_TOOLS:
            # LEGACY: STT TRUTH STORE - Lock ALL values from user utterances
            # OpenAI Tool still extracts, but STT values take precedence for confirmation
            
            # LEGACY: SERVICE LOCK - Detect and lock service from user utterance (FIRST question!)
            if is_user_speech and 'service_type' in required_fields:
                self._try_lock_service_from_utterance(text)
            
            # LEGACY: CITY LOCK - Detect and lock city from user utterance
            if is_user_speech and 'city' in required_fields:
                self._try_lock_city_from_utterance(text)
    
    def _try_lock_service_from_utterance(self, text: str):
        """
        🔥 BUILD 336: SERVICE LOCK MECHANISM
        
        Locks service from ANY user utterance during discovery phase.
        Triggers on: response to greeting, first few messages, or when AI asked for service.
        
        Takes what user said literally - no dictionaries or normalization.
        """
        import re
        
        # Only lock if service is needed and not already locked
        if self._service_locked and 'service_type' in self.lead_capture_state:
            logger.info(f"🔒 [BUILD 336] Service already locked: '{self.lead_capture_state.get('service_type')}'")
            return
        
        # 🔥 BUILD 336 FIX: TRY to lock service on EVERY user transcript!
        # Service can be mentioned at any time, not just in discovery
        
        # Check if last AI message asked for service or is greeting
        last_ai_msg = None
        for msg in reversed(self.conversation_history):
            if msg.get("speaker") == "ai":
                last_ai_msg = msg.get("text", "").lower()
                break
        
        ai_asked_for_service = last_ai_msg and any(
            phrase in last_ai_msg for phrase in [
                "שירות", "צריך", "לעזור", "במה", "מה אפשר", "איזה סוג"
            ]
        )
        
        # 🔥 BUILD 336 FIX: ALWAYS try to lock if in first 5 messages OR AI asked
        # This ensures we capture service even if mentioned casually
        user_msg_count = len([m for m in self.conversation_history if m.get("speaker") == "user"])
        is_early_conversation = user_msg_count <= 5
        
        # Clean the utterance
        cleaned = text.strip()
        cleaned = re.sub(r'[\.!\?:,;]', '', cleaned)
        
        # 🔥 BUILD 336 FIX: Strip ALL trailing punctuation before processing
        cleaned = re.sub(r'[\.!\?:,;"\'\(\)]+$', '', cleaned)
        cleaned = cleaned.strip()
        
        # Skip very short or non-Hebrew
        hebrew_chars = sum(1 for c in cleaned if '\u0590' <= c <= '\u05FF')
        if hebrew_chars < 3:
            return
        
        # Skip confirmation/rejection words - these are NOT service requests
        skip_words = ["כן", "לא", "נכון", "בדיוק", "ממש לא", "תודה", "שלום", "היי", "הי"]
        if cleaned in skip_words:
            return
        
        # 🔥 BUILD 336 FIX: CHECK FOR ACTION VERBS FIRST!
        # If text contains service-related verbs, it's DEFINITELY a service request
        action_verbs = [
            "החלפ", "התקנ", "תיקון", "בדיק", "שירות", "הזמנ", 
            "תיקונ", "החלפת", "התקנת", "בדיקת", "שיפוץ", "נקי", "חידוש"
        ]
        has_action_verb = any(verb in cleaned for verb in action_verbs)
        
        if has_action_verb:
            # Has action verb - this IS a service request, regardless of length
            logger.info(f"🔧 [BUILD 336] Detected action verb in: '{cleaned}' - treating as service")
        else:
            # No action verb - check if it's too short to be a service
            words = cleaned.split()
            if len(words) <= 2:
                # 🚫 DISABLED: City lock logic disabled via ENABLE_LEGACY_CITY_LOGIC flag
                # Short phrase without action verb - might be a city (DISABLED)
                logger.info(f"⏭️ [BUILD 336] Skipping short phrase without verb: '{cleaned}'")
                return
        
        # Clean common prefixes
        service_prefixes = [
            r'^אני צריך\s+', r'^אני רוצה\s+', r'^צריך\s+', r'^רוצה\s+',
            r'^אצטרך\s+', r'^אני אצטרך\s+', r'^בבקשה\s+'
        ]
        
        service_name = cleaned
        for prefix_pattern in service_prefixes:
            service_name = re.sub(prefix_pattern, '', service_name, flags=re.IGNORECASE)
        
        service_name = service_name.strip()
        
        # Must have at least 3 Hebrew characters for service
        if len(service_name) < 3:
            return
        
        # LOCK THE SERVICE!
        self._service_raw_from_stt = service_name
        self._service_locked = True
        self._update_lead_capture_state('service_type', service_name)
        logger.info(f"🔒 [BUILD 336] SERVICE LOCKED from STT: '{service_name}' (raw: '{text}')")
    
    def _try_lock_city_from_utterance(self, text: str):
        """
        🔥 BUILD 326: CITY LOCK MECHANISM (enhanced)
        """
        import re
        
        def _normalize_city_name(name: str) -> str:
            return re.sub(r'\s+', ' ', name.strip()).lower()
        
        def _ensure_city_catalog():
            if self._known_city_names_set is None:
                from server.services.city_normalizer import get_all_city_names
                names = get_all_city_names()
                self._known_city_names_set = {_normalize_city_name(n) for n in names if n}
            return self._known_city_names_set
        
        def _is_known_city(candidate: str) -> bool:
            if not candidate:
                return False
            catalog = _ensure_city_catalog()
            return _normalize_city_name(candidate) in catalog
        
        if not text:
            return
        
        cleaned = text.strip()
        if not cleaned:
            return
        
        city_already_locked = self._city_locked and 'city' in self.lead_capture_state
        is_first_answer = getattr(self, '_current_transcript_is_first_answer', False)
        token_count = getattr(self, '_current_transcript_token_count', 0) or len(cleaned.split())
        stt_confidence = getattr(self, '_current_stt_confidence', None)
        LOW_CONFIDENCE_THRESHOLD = 0.45
        
        # Check if last AI message asked for city
        last_ai_msg = None
        for msg in reversed(self.conversation_history):
            if msg.get("speaker") == "ai":
                last_ai_msg = msg.get("text", "").lower()
                break
        
        ai_asked_for_city = last_ai_msg and any(
            phrase in last_ai_msg for phrase in [
                "עיר", "איפה", "מאיפה", "באיזו עיר", "באיזה אזור", "מאיזה"
            ]
        )
        
        cleaned_no_punct = re.sub(r'[\.!\?:,;]', '', cleaned)
        words = cleaned_no_punct.split()
        
        # Detect strong "<service> ב<city>" mention
        strong_pattern_city = None
        strong_match = re.search(r'\bב([א-ת][א-ת\s\-]{1,20})\b', cleaned_no_punct)
        if strong_match:
            candidate = strong_match.group(1).strip()
            if _is_known_city(candidate):
                strong_pattern_city = candidate
        
        if not ai_asked_for_city and not strong_pattern_city:
            return
        
        if is_first_answer:
            if token_count < 3:
                logger.info(f"⏭️ [CITY LOCK] First utterance too short ({token_count} tokens) - waiting for clearer answer")
                return
            if stt_confidence is not None and stt_confidence < LOW_CONFIDENCE_THRESHOLD:
                logger.info(f"⏭️ [CITY LOCK] First utterance low confidence ({stt_confidence:.2f}) - not locking city")
                return
        
        hebrew_chars = sum(1 for c in cleaned_no_punct if '\u0590' <= c <= '\u05FF')
        if hebrew_chars < 2:
            return
        skip_words = ["כן", "לא", "נכון", "בדיוק", "ממש לא", "תודה", "שלום", "עדיין", "רגע"]
        if cleaned_no_punct in skip_words or any(cleaned_no_punct.startswith(sw) for sw in ["לא ", "כן ", "עדיין"]):
            return
        if len(words) > 4 and not strong_pattern_city:
            return
        
        city_prefixes = [
            r'^בעיר\s+', r'^באזור\s+', r'^עיר\s+', r'^מעיר\s+',
            r'^אני ב', r'^אני מ', r'^אנחנו ב', r'^אנחנו מ',
            r'^ב', r'^מ'
        ]
        
        city_name = cleaned_no_punct
        for prefix_pattern in city_prefixes:
            stripped = re.sub(prefix_pattern, '', city_name, flags=re.IGNORECASE)
            if stripped != city_name:
                city_name = stripped
                break
        
        city_name = city_name.strip()
        if len(city_name) < 2:
            return
        
        candidate_city = strong_pattern_city or city_name
        if not _is_known_city(candidate_city):
            if is_first_answer:
                logger.info(f"⏭️ [CITY LOCK] First utterance '{candidate_city}' not in known city list - waiting for clarification")
            else:
                logger.info(f"⏭️ [CITY LOCK] '{candidate_city}' not recognized as Israeli city - skipping lock")
            return
        
        can_override_locked_city = (
            city_already_locked and
            strong_pattern_city and
            candidate_city != self.lead_capture_state.get('city')
        )
        
        if city_already_locked and not can_override_locked_city:
            logger.info(f"🔒 [CITY LOCK] City already locked as '{self.lead_capture_state.get('city')}' - ignoring '{candidate_city}'")
            return
        
        if can_override_locked_city:
            old_city = self.lead_capture_state.get('city')
            self._city_raw_from_stt = candidate_city
            self._city_source = 'user_utterance'
            self._city_locked = True
            self._update_lead_capture_state('city', candidate_city, source='user_utterance')
            logger.info(f"🔁 [CITY UPDATE] Overriding city from '{old_city}' to '{candidate_city}' based on strong pattern")
            return
        
        self._city_raw_from_stt = candidate_city
        self._city_locked = True
        self._city_source = 'user_utterance'
        self._update_lead_capture_state('city', candidate_city)
        logger.info(f"🔒 [BUILD 326] CITY LOCKED from STT: '{candidate_city}' (raw: '{text}')")
    
    def _unlock_city(self):
        """
        🔥 BUILD 326: Unlock city when user explicitly corrects
        Called when user says "לא", "לא נכון", etc.
        """
        if self._city_locked:
            old_city = self.lead_capture_state.get('city', '')
            self._city_locked = False
            self._city_raw_from_stt = None
            self._city_source = None
            if 'city' in self.lead_capture_state:
                del self.lead_capture_state['city']
            logger.info(f"🔓 [BUILD 326] CITY UNLOCKED (was: '{old_city}') - waiting for new city")
            
            # 🔥 BUILD 336 FIX: Reset confirmation state on unlock
            self._reset_confirmation_state()
    
    def _unlock_service(self):
        """
        🔥 BUILD 336: Unlock service when user explicitly corrects
        """
        if self._service_locked:
            old_service = self.lead_capture_state.get('service_type', '')
            self._service_locked = False
            self._service_raw_from_stt = None
            if 'service_type' in self.lead_capture_state:
                del self.lead_capture_state['service_type']
            logger.info(f"🔓 [BUILD 336] SERVICE UNLOCKED (was: '{old_service}') - waiting for new service")
            
            # 🔥 BUILD 336 FIX: Reset confirmation state on unlock
            self._reset_confirmation_state()
    
    def _reset_confirmation_state(self):
        """
        🔥 BUILD 336: Reset all confirmation-related state
        Called when: user rejects, flow restarts, or new discovery begins
        """
        self._expected_confirmation = None
        self._confirmation_validated = False
        self._speak_exact_resend_count = 0
        self._verification_prompt_sent = False
        self._lead_confirmation_received = False
        self._lead_closing_dispatched = False
        logger.info(f"🔄 [BUILD 336] Confirmation state reset - ready for new flow")
    
    def _update_lead_capture_state(self, field: str, value: str, source: str = 'unknown'):
        """
        🎯 DYNAMIC LEAD CAPTURE: Update lead capture state with a new field value
        
        Called from:
        - _process_dtmf_phone() when phone is captured via DTMF
        - NLP parser when name/service_type/etc. are extracted
        - AI response parsing when fields are mentioned
        
        Args:
            field: Field identifier (e.g., 'name', 'phone', 'city', 'service_type')
            value: The captured value
            source: Where this update came from ('user_utterance', 'ai_extraction', 'dtmf', etc.)
        """
        if not value or not str(value).strip():
            return
        
        value = str(value).strip()
        
        # 🔥 BUILD 336: STT TRUTH LOCK - Block non-STT sources from changing locked values!
        
        is_stt_source = source in ('user_utterance', 'stt', 'dtmf', 'user')
        
        # CITY LOCK - Only STT sources can change locked city
        if field == 'city' and self._city_locked:
            existing_city = self.lead_capture_state.get('city', '')
            if existing_city and value != existing_city:
                if not is_stt_source:
                    logger.info(f"🛡️ [BUILD 336] BLOCKED: Non-STT source '{source}' tried to change locked city '{existing_city}' → '{value}'")
                    logger.info(f"🛡️ [BUILD 336] City remains: '{existing_city}' (locked from STT)")
                    return
                else:
                    # STT source wants to update - this means user corrected themselves
                    logger.info(f"🔓 [BUILD 336] STT source updating locked city '{existing_city}' → '{value}'")
        
        # SERVICE LOCK - Only STT sources can change locked service
        if field == 'service_type' and self._service_locked:
            existing_service = self.lead_capture_state.get('service_type', '')
            if existing_service and value != existing_service:
                if not is_stt_source:
                    logger.info(f"🛡️ [BUILD 336] BLOCKED: Non-STT source '{source}' tried to change locked service '{existing_service}' → '{value}'")
                    logger.info(f"🛡️ [BUILD 336] Service remains: '{existing_service}' (locked from STT)")
                    return
                else:
                    # STT source wants to update - this means user corrected themselves
                    logger.info(f"🔓 [BUILD 336] STT source updating locked service '{existing_service}' → '{value}'")
        
        self.lead_capture_state[field] = value
        logger.info(f"✅ [LEAD STATE] Updated: {field}={value}")
        logger.info(f"📋 [LEAD STATE] Current state: {self.lead_capture_state}")
        
        # Also update CRM context for legacy compatibility (name/phone)
        crm_context = getattr(self, 'crm_context', None)
        if crm_context:
            if field == 'name' and not crm_context.customer_name:
                crm_context.customer_name = value
            elif field == 'phone' and not crm_context.customer_phone:
                crm_context.customer_phone = value
    
    def _check_lead_captured(self) -> bool:
        """
        🎯 SMART HANGUP: Check if all required lead information has been collected
        
        Uses business-specific required_lead_fields if configured.
        Checks BOTH lead_capture_state (dynamic) AND crm_context (legacy).
        
        Returns:
            True if all required lead fields are collected
        """
        # Get required fields from business settings
        required_fields = getattr(self, 'required_lead_fields', None)
        logger.debug(f"🔍 [DEBUG] _check_lead_captured: required_fields from self = {required_fields}")
        
        # 🔥 PROMPT-ONLY MODE: If no required fields configured, never enforce anything
        # The business prompt defines what "enough" means, not the Python code
        if not required_fields:
            logger.info(f"✅ [PROMPT-ONLY] No required_lead_fields configured - letting prompt handle conversation flow")
            return False
        
        # Get current capture state
        lead_state = getattr(self, 'lead_capture_state', {})
        crm_context = getattr(self, 'crm_context', None)
        
        # Map UI field names to CRM context attribute names (for legacy fallback)
        field_to_crm_attr = {
            'name': 'customer_name',
            'phone': 'customer_phone',
            'email': 'customer_email',
        }
        
        # 🔥 BUILD 180: Invalid values that should be rejected as "not captured"
        # These are AI question fragments that got incorrectly extracted
        invalid_values = [
            'אתה צריך', 'צריכים', 'צריך', 'תרצה', 'תרצו', 'רוצה', 'רוצים',
            'תרצה עזרה', 'תרצו עזרה', 'אתם צריכים', 'מה אתה צריך', 'איזה סוג',
            'באיזה תחום', 'מה השירות', 'איך אני יכול', 'במה אוכל'
        ]
        
        # Check which fields are missing
        missing_fields = []
        collected_values = []
        
        for field in required_fields:
            # First check dynamic lead_capture_state
            value = lead_state.get(field)
            
            # Fallback to CRM context for legacy fields (name, phone, email)
            if not value and crm_context:
                crm_attr = field_to_crm_attr.get(field)
                if crm_attr:
                    value = getattr(crm_context, crm_attr, None)
            
            # 🔥 BUILD 180: Validate that value is not an AI question fragment
            if value and field in ['service_type', 'service_category']:
                if value.strip() in invalid_values or len(value.strip()) < 4:
                    logger.warning(f"⚠️ [VALIDATION] Rejecting invalid {field} value: '{value}'")
                    value = None
            
            if value:
                collected_values.append(f"{field}={value}")
            else:
                missing_fields.append(field)
        
        if not missing_fields:
            logger.info(f"✅ [SMART HANGUP] All required fields collected: {', '.join(collected_values)}")
            return True
        
        # 🚫 DISABLED: City/service logic disabled via ENABLE_LEGACY_CITY_LOGIC flag
        if ENABLE_LEGACY_CITY_LOGIC:
            logger.info(f"⏳ [SMART HANGUP] Still missing fields: {missing_fields} | Collected: {collected_values}")
        return False

    def _process_dtmf_skip(self):
        """
        🎯 Process DTMF skip (# pressed with empty buffer)
        Customer chose to skip phone number input
        """
        logger.info(f"⏭️ Processing DTMF skip")
        
        # Create skip message in Hebrew
        skip_text = "אני מעדיף לא לתת את המספר"
        
        # 🚀 REALTIME API: Send via Realtime if enabled, otherwise use AgentKit
        if USE_REALTIME_API:
            logger.info(f"🚀 [REALTIME] Sending DTMF skip via Realtime API")
            # ✅ Queue the user's DTMF skip message (non-blocking, no fallback to AgentKit)
            try:
                self.realtime_text_input_queue.put_nowait(skip_text)
                logger.info(f"✅ [REALTIME] DTMF skip queued for Realtime API")
                
                # Save to conversation history
                self.conversation_history.append({
                    "user": "[DTMF skip]",
                    "bot": "(Realtime API handling)"
                })
            except queue.Full:
                logger.error(f"❌ [REALTIME] CRITICAL: Text input queue full - DTMF skip dropped!")
                # Don't fall back to AgentKit - log the error
            except Exception as e:
                logger.error(f"❌ [REALTIME] Failed to queue DTMF skip: {e}")
                import traceback
                traceback.print_exc()
                # Don't fall back to AgentKit - this could cause dual responses
        else:
            # Legacy: Get AI response via AgentKit (Google STT/TTS mode)
            ai_response = self._ai_response(skip_text)
            
            # Speak the response
            if ai_response:
                self._speak_simple(ai_response)
                
                # Save to conversation history
                self.conversation_history.append({
                    "user": "[DTMF skip]",
                    "bot": ai_response
                })
        
        logger.info(f"✅ DTMF skip processed")
    
    def _process_dtmf_phone(self, phone_number: str):
        """
        ⚡ BUILD 121: Process phone number collected via DTMF
        Inject as conversation input and generate AI response
        """
        logger.info(f"📞 Processing DTMF phone: {phone_number}")
        
        # 🔥 CRITICAL FIX: Normalize phone to E.164 format!
        from server.agent_tools.phone_utils import normalize_il_phone
        
        # Normalize to E.164 (+972...)
        phone_to_show = ""  # 🔥 BUILD 118: Initialize to avoid NameError
        normalized_phone = normalize_il_phone(phone_number)
        
        if not normalized_phone:
            # If normalization failed, try adding 0 prefix
            if not phone_number.startswith("0"):
                phone_number = "0" + phone_number
                normalized_phone = normalize_il_phone(phone_number)
        
        if normalized_phone:
            logger.info(f"✅ Phone normalized: {phone_number} → {normalized_phone}")
            
            # 🎯 DYNAMIC LEAD STATE: Update lead capture state for smart hangup
            self._update_lead_capture_state('phone', normalized_phone)
            
            # 🔥 CRITICAL FIX: Store normalized phone in instance variable!
            # Don't use flask.g - WebSocket runs outside request context
            self.customer_phone_dtmf = normalized_phone
            logger.info(f"✅ Stored customer_phone_dtmf: {normalized_phone}")
            
            # 🔥 CRITICAL FIX: Also update crm_context.customer_phone!
            # This is what the confirm handler checks - if we don't set it, appointment creation fails!
            crm_context = getattr(self, 'crm_context', None)
            if crm_context:
                crm_context.customer_phone = normalized_phone
                logger.info(f"✅ Updated crm_context.customer_phone: {normalized_phone}")
            else:
                logger.warning(f"⚠️ No crm_context found - creating one")
                # Create CRM context if missing
                from server.media_ws_ai import CallCrmContext
                self.crm_context = CallCrmContext(
                    business_id=self.business_id,
                    customer_phone=normalized_phone
                )
                # 🔥 HYDRATION: If we have pending customer name, transfer it to context
                if hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    self.crm_context.customer_name = self.pending_customer_name
                    logger.info(f"✅ [DTMF] Hydrated pending_customer_name → crm_context: {self.pending_customer_name}")
                    self.pending_customer_name = None  # Clear cache
                logger.info(f"✅ Created crm_context with phone: {normalized_phone}")
            
            phone_to_show = normalized_phone
        else:
            logger.error(f"⚠️ Phone normalization failed for: {phone_number}")
            phone_to_show = phone_number
        
        # 🔥 BUILD 186: Send DTMF phone as SYSTEM event (not user message)
        # DTMF is only used when require_phone_before_booking=True
        # Otherwise, Caller ID is used automatically (no verbal/DTMF needed)
        
        # 🚀 REALTIME API: Send via system event (not user message!)
        if USE_REALTIME_API:
            logger.info(f"🚀 [REALTIME] Sending DTMF phone as SYSTEM event: {phone_to_show}")
            # ✅ Send as system event (silent - AI reads but doesn't speak)
            try:
                import asyncio
                import threading
                
                # 🔥 FIX: Run async coroutine in separate thread with its own event loop
                def run_in_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self._send_server_event_to_ai(
                            f"📞 Customer entered phone via DTMF: {phone_to_show}"
                        ))
                        logger.info(f"✅ [REALTIME] DTMF phone sent as system event")
                    except Exception as e:
                        logger.error(f"❌ [REALTIME] Error sending DTMF phone: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        loop.close()
                
                # Launch in background thread
                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()
                
                # Save to conversation history with new format
                self.conversation_history.append({
                    "speaker": "user",
                    "text": f"[DTMF keys pressed: {phone_to_show}]",
                    "ts": time.time()
                })
                
                # 🔥 CRITICAL FIX: After adding DTMF to history, ALWAYS trigger NLP!
                # NLP will extract both date/time AND name from conversation history
                # Don't check for customer_name here - let NLP extract it from history!
                crm_context = getattr(self, 'crm_context', None)
                # ⭐ BUILD 350: NLP disabled - no mid-call appointment logic
                if ENABLE_LEGACY_TOOLS:
                    logger.info(f"🔄 [LEGACY DTMF] Triggering NLP with phone={crm_context.customer_phone if crm_context else None}")
                    logger.debug(f"🔍 [LEGACY DEBUG] Calling NLP after DTMF - conversation has {len(self.conversation_history)} messages")
                    # LEGACY: Trigger NLP check (uses existing conversation history WITH DTMF!)
                    self._check_appointment_confirmation("")  # Empty string - uses history
                
            except queue.Full:
                logger.error(f"❌ [REALTIME] CRITICAL: Text input queue full - DTMF phone dropped!")
                # Don't fall back to AgentKit - log the error
            except Exception as e:
                logger.error(f"❌ [REALTIME] Failed to queue DTMF phone: {e}")
                import traceback
                traceback.print_exc()
                # Don't fall back to AgentKit - this could cause dual responses
        else:
            # Legacy: Get AI response via AgentKit (Google STT/TTS mode)
            hebrew_text = f"המספר שלי הוא {phone_to_show}"
            ai_response = self._ai_response(hebrew_text)
            
            # Speak the response using the correct method
            if ai_response:
                self._speak_simple(ai_response)
                
                # Save to conversation history
                self.conversation_history.append({
                    "user": f"[DTMF] {phone_to_show}",
                    "bot": ai_response
                })
        
        logger.info(f"✅ DTMF phone processed: {phone_to_show}")
    
    def _ai_response(self, hebrew_text: str) -> str:
        """Generate NATURAL Hebrew AI response using AgentKit - REAL ACTIONS!"""
        try:
            # ⚡ Phase 2C: Track turns and optimize first turn
            self.turn_count = getattr(self, 'turn_count', 0) + 1
            is_first_turn = (self.turn_count == 1)
            
            # 🤖 BUILD 119: Use Agent for REAL ACTIONS (appointments, leads, WhatsApp)
            from server.services.ai_service import AIService
            
            # 🔥 BUILD 118: CRITICAL - Initialize customer_phone FIRST to avoid UnboundLocalError
            # Prioritize DTMF phone (E.164 normalized) over caller phone
            customer_phone = getattr(self, 'customer_phone_dtmf', None) or getattr(self, 'phone_number', '') or ''
            
            # Build context for the AI
            context = {
                "phone_number": getattr(self, 'phone_number', ''),
                "channel": "phone",  # 🔥 FIX: "phone" for WhatsApp confirmation detection
                "customer_phone": customer_phone,  # 🔥 BUILD 118: Use computed value (not stale from previous context)
                "previous_messages": []
            }
            
            # 🔥 BUILD 118: Update context with computed customer_phone BEFORE agent call
            # This prevents stale phone numbers from previous turns
            context["customer_phone"] = customer_phone
            
            # Add conversation history for context - ✅ FIXED FORMAT
            if hasattr(self, 'conversation_history') and self.conversation_history:
                formatted_history = []
                for item in self.conversation_history[-6:]:  # Last 6 turns
                    # Handle new format: {"speaker": "user/ai", "text": "..."}
                    if 'speaker' in item and 'text' in item:
                        speaker_label = "לקוח" if item['speaker'] == 'user' else "עוזר"
                        formatted_history.append(f"{speaker_label}: {item['text']}")
                    # Handle old format: {"user": "...", "bot": "..."}
                    elif 'user' in item and 'bot' in item:
                        formatted_history.append(f"לקוח: {item['user']}\nעוזר: {item['bot']}")
                context["previous_messages"] = formatted_history
            
            # ✅ CRITICAL FIX: Use shared Flask app instance (no recreation!)
            business_id = getattr(self, 'business_id', None)
            if not business_id:
                # ❌ CRITICAL: No fallback! Business must be identified from call
                logger.error(f"❌ CRITICAL ERROR: No business_id set! Cannot process without business context")
                raise ValueError("Business ID is required - no fallback allowed")
            
            # Get customer name from conversation if available
            customer_name = None
            lead_info = getattr(self, '_last_lead_analysis', None)
            if lead_info:
                customer_name = lead_info.get('customer_name')
            
            # 🔥 CRITICAL FIX: Also check crm_context for customer name
            if not customer_name:
                crm_context = getattr(self, 'crm_context', None)
                if crm_context and hasattr(crm_context, 'customer_name'):
                    customer_name = crm_context.customer_name
                # Also check pending_customer_name cache
                if not customer_name and hasattr(self, 'pending_customer_name'):
                    customer_name = self.pending_customer_name
            
            # 🔥 CRITICAL FIX: Add customer_name to context so it reaches the AI!
            if customer_name:
                context["customer_name"] = customer_name
                logger.info(f"✅ [AI CONTEXT] Added customer_name to context: '{customer_name}'")
            
            # ⚡ CRITICAL: Measure AI response time
            ai_start = time.time()
            
            # ✅ FIX: Use Flask app singleton (CRITICAL - prevents app restart!)
            app = _get_flask_app()
            
            with app.app_context():
                # 🤖 Use Agent for REAL booking actions!
                ai_service = AIService()
                
                # 🔥 BUILD 118: Use customer_phone (includes DTMF) instead of caller_phone (None)!
                # customer_phone is set in line 2467 and includes DTMF phone if available
                logger.debug(f"\n📞 DEBUG: customer_phone from context = '{customer_phone}'")
                logger.info(f"   phone_number (caller) = '{getattr(self, 'phone_number', 'None')}'")
                logger.info(f"   customer_phone_dtmf = '{getattr(self, 'customer_phone_dtmf', 'None')}'")
                
                ai_response = ai_service.generate_response_with_agent(
                    message=hebrew_text,
                    business_id=int(business_id),
                    customer_phone=customer_phone,  # 🔥 BUILD 118: FIX - Use customer_phone (includes DTMF), not caller_phone (None)!
                    customer_name=customer_name,
                    context=context,
                    channel='calls',  # ✅ Use 'calls' prompt for phone calls
                    is_first_turn=is_first_turn  # ⚡ Phase 2C: Optimize first turn!
                )
            
            # ⚡ CRITICAL: Save AI timing for TOTAL_LATENCY calculation
            self.last_ai_time = time.time() - ai_start
            
            # 🔥 BUILD 118: Normalize ai_response to dict (handle both structured and legacy responses)
            if isinstance(ai_response, str):
                # Legacy string response (FAQ, fallback paths)
                logger.warning(f"⚠️ Got legacy string response: {len(ai_response)} chars")
                ai_response_dict = {
                    "text": ai_response,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "actions": [],  # Empty actions for legacy responses
                    "booking_successful": False,
                    "source": "legacy_string"
                }
            elif isinstance(ai_response, dict):
                # Structured response from AgentKit - ensure all required fields present
                ai_response_dict = {
                    "text": ai_response.get("text", ""),
                    "usage": ai_response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                    "actions": ai_response.get("actions", []),
                    "booking_successful": ai_response.get("booking_successful", False),
                    "error": ai_response.get("error"),
                    "source": ai_response.get("source", "agentkit")
                }
            else:
                # Defensive: shouldn't happen
                logger.error(f"❌ Unexpected response type: {type(ai_response).__name__}")
                ai_response_dict = {
                    "text": "סליחה, לא הבנתי. אפשר לחזור?",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "actions": [],
                    "booking_successful": False,
                    "source": "error_fallback"
                }
            
            # 🔥 BUILD 118: Save structured response for metadata (analytics, transcripts)
            self.last_agent_response_metadata = ai_response_dict
            
            # 🔥 BUILD 118: Extract TTS text separately (don't mutate ai_response!)
            # This preserves metadata for downstream consumers (analytics, transcripts, logging)
            tts_text = ai_response_dict.get('text', '')
            
            if not tts_text or not tts_text.strip():
                logger.error(f"❌ EMPTY TTS TEXT - using fallback")
                tts_text = "סליחה, לא הבנתי. אפשר לחזור?"
            
            logger.info(f"✅ Extracted TTS text: {len(tts_text)} chars")
            logger.info(f"   Metadata: {len(ai_response_dict.get('actions', []))} actions, booking={ai_response_dict.get('booking_successful', False)}")
            
            logger.info(f"🤖 AGENT_RESPONSE: Generated {len(tts_text)} chars in {self.last_ai_time:.3f}s (business {business_id})")
            if DEBUG: logger.debug(f"📊 AI_LATENCY: {self.last_ai_time:.3f}s (target: <1.5s)")
            
            # Return TTS text (string) for _speak_simple
            return tts_text
            
        except Exception as e:
            logger.error(f"❌ AI_SERVICE_ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            logger.warning(f"⚠️ Using fallback response instead of agent")
            return self._fallback_response(hebrew_text)
    
    def _fallback_response(self, hebrew_text: str) -> str:
        """Simple fallback response when AI service fails - uses business settings"""
        try:
            from server.models_sql import Business
            business = Business.query.get(self.business_id)
            if business and business.greeting_message:
                return business.greeting_message
        except:
            pass
        
        # Generic neutral response (no business name exposed)
        return "איך אוכל לעזור?"
    
    
    def _hebrew_tts(self, text: str) -> bytes | None:
        """
        🚫 DISABLED - Google TTS is turned off for production stability
        
        This function should never be called when USE_REALTIME_API=True.
        OpenAI Realtime API handles ALL TTS natively.
        """
        # 🚀 REALTIME API: Skip Google TTS completely - OpenAI Realtime generates audio natively
        if USE_REALTIME_API:
            return None
        
        # 🚫 Google TTS is DISABLED
        if DISABLE_GOOGLE:
            logger.warning("⚠️ _hebrew_tts called but Google TTS is DISABLED")
            return None
        
        logger.error("❌ Google TTS should not be used - DISABLE_GOOGLE flag should be set")
        return None
    
    def _flush_tx_queue(self):
        """
        🔥 BARGE-IN FIX: Flushes BOTH queues to ensure no old audio continues playing
        
        Called when user interrupts AI - clears all queued audio to prevent
        AI voice from continuing after barge-in.
        
        CRITICAL: This is the key to instant barge-in response.
        Flushes:
        1. realtime_audio_out_queue - Audio from OpenAI not yet in TX queue
        2. tx_q - Audio waiting to be sent to Twilio
        """
        realtime_flushed = 0
        tx_flushed = 0
        
        try:
            # Flush OpenAI → TX queue (realtime_audio_out_queue)
            if hasattr(self, 'realtime_audio_out_queue') and self.realtime_audio_out_queue:
                while True:
                    try:
                        self.realtime_audio_out_queue.get_nowait()
                        realtime_flushed += 1
                    except queue.Empty:
                        break
            
            # Flush TX → Twilio queue (tx_q)
            if hasattr(self, 'tx_q') and self.tx_q:
                while True:
                    try:
                        self.tx_q.get_nowait()
                        tx_flushed += 1
                    except queue.Empty:
                        break
            
            total_flushed = realtime_flushed + tx_flushed
            if total_flushed > 0:
                _orig_print(f"🧹 [BARGE-IN FLUSH] Cleared {total_flushed} frames total (realtime_queue={realtime_flushed}, tx_queue={tx_flushed})", flush=True)
            else:
                _orig_print(f"🧹 [BARGE-IN FLUSH] Both queues already empty", flush=True)
        except Exception as e:
            _orig_print(f"⚠️ [BARGE-IN FLUSH] Error flushing queues: {e}", flush=True)
    
    def _tx_loop(self):
        """
        ✅ ZERO LOGS INSIDE: Clean TX loop - take frame, send to Twilio, sleep 20ms
        
        NO LOGS, NO WATCHDOGS, NO STALL RECOVERY, NO FLUSH
        Only: get frame → send → sleep
        """
        call_sid_short = self.call_sid[:8] if hasattr(self, 'call_sid') and self.call_sid else 'unknown'
        _orig_print(f"[AUDIO_TX_LOOP] started (call_sid={call_sid_short}, frame_pacing=20ms)", flush=True)
        
        FRAME_INTERVAL = AUDIO_CONFIG["frame_pacing_ms"] / 1000.0  # 20ms
        next_deadline = time.monotonic()
        frames_sent_total = 0
        _first_frame_sent = False
        
        # Pre-format event templates (outside loop to avoid json.dumps inside)
        clear_event_template = {"event": "clear", "streamSid": self.stream_sid}
        
        try:
            while self.tx_running or not self.tx_q.empty():
                # Get frame
                try:
                    item = self.tx_q.get(timeout=0.5)
                except queue.Empty:
                    if not self.tx_running:
                        break
                    continue
                
                if item.get("type") == "end":
                    break
                
                # Handle "clear" event - send to Twilio (NO LOGS)
                if item.get("type") == "clear" and self.stream_sid:
                    self._ws_send(json.dumps(clear_event_template))
                    continue
                
                # Handle "media" event - send audio to Twilio (NO LOGS)
                if item.get("type") == "media" or item.get("event") == "media":
                    # 🔥 NEW FIX: Skip sending audio if barge-in stop flag is set
                    # This immediately stops all audio transmission when user interrupts
                    if getattr(self, 'barge_in_stop_tx', False):
                        # User is interrupting - drop this frame and continue
                        # Don't send it, don't count it, just skip it
                        continue
                    
                    # Send frame to Twilio WS (item already has correct format from enqueue)
                    if item.get("event") == "media" and "media" in item:
                        success = self._ws_send(json.dumps(item))
                    else:
                        # Old format - convert (pre-build dict to minimize work)
                        payload = {"event": "media", "streamSid": self.stream_sid, "media": {"payload": item["payload"]}}
                        success = self._ws_send(json.dumps(payload))
                    
                    if success:
                        self.tx += 1
                        frames_sent_total += 1
                        if not _first_frame_sent:
                            _first_frame_sent = True
                            self._first_audio_sent = True
                    
                    # ✅ Strict 20ms timing - advance deadline and sleep
                    next_deadline += FRAME_INTERVAL
                    delay = next_deadline - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        # Missed deadline - resync to prevent catch-up bursts
                        next_deadline = time.monotonic()
                    
                    # NO GAP LOGGING INSIDE LOOP - causes micro-blocks
                    continue
                
                # Handle "mark" event (NO LOGS)
                if item.get("type") == "mark" and self.stream_sid:
                    mark_event = {"event": "mark", "streamSid": self.stream_sid, "mark": {"name": item.get("name", "mark")}}
                    self._ws_send(json.dumps(mark_event))
        
        except Exception as tx_loop_error:
            # NO TRACEBACK - just log and re-raise
            _orig_print(f"[TX_CRASH] {tx_loop_error}", flush=True)
            raise
        finally:
            _orig_print(f"[AUDIO_TX_LOOP] exiting (frames_sent={frames_sent_total}, call_sid={call_sid_short})", flush=True)
    
    def _speak_with_breath(self, text: str):
        """דיבור עם נשימה אנושית ו-TX Queue - תמיד משדר משהו"""
        if not text:
            return
        
        # 🔒 HARD-CODED: ALWAYS protected - ZERO barge-in!
        word_count = len(text.split())
        self.long_response = True  # ✅ PERMANENTLY True - NEVER interrupt!
        logger.info(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
        self.speaking = True
        self.state = STATE_SPEAK
        self.speaking_start_ts = time.time()  # ✅ חלון חסד - זמן תחילת TTS
        
        try:
            # נשימה אנושית (220-360ms)
            breath_delay = random.uniform(RESP_MIN_DELAY_MS/1000.0, RESP_MAX_DELAY_MS/1000.0)
            time.sleep(breath_delay)
            
            # clear + שידור אם החיבור תקין
            if self.stream_sid and not self.ws_connection_failed:
                self._tx_enqueue({"type": "clear"})
            elif self.ws_connection_failed:
                logger.error("💔 SKIPPING TTS clear - WebSocket connection failed")
                return None
            
            # נסה TTS אמיתי
            pcm = None
            try:
                pcm = self._hebrew_tts(text)
            except Exception as e:
                logger.info("TTS_ERR:", e)
                
            if not pcm or len(pcm) < 400:
                logger.error("🔊 TTS FAILED - sending beep")
                pcm = self._beep_pcm16_8k(300)  # צפצוף 300ms
            else:
                logger.info(f"🔊 TTS SUCCESS: {len(pcm)} bytes")
            
            # ✅ שלח את האודיו דרך TX Queue (אם החיבור תקין)
            if pcm and self.stream_sid and not self.ws_connection_failed:
                self._send_pcm16_as_mulaw_frames(pcm)
            elif self.ws_connection_failed:
                logger.error("💔 SKIPPING audio clear - WebSocket connection failed")
                return
            
            # ✅ Audio already sent by _send_pcm16_as_mulaw_frames() above
            
        finally:
            # ✅ Clean finalization
            self._finalize_speaking()
    
    def _beep_pcm16_8k_v2(self, ms: int) -> bytes:
        """יצירת צפצוף PCM16 8kHz"""
        samples = int(SR * ms / 1000)
        amp = 9000
        out = bytearray()
        
        for n in range(samples):
            val = int(amp * math.sin(2 * math.pi * 440 * n / SR))
            out.extend(val.to_bytes(2, "little", signed=True))
            
        return bytes(out)
    
    def _detect_area(self, text: str) -> str:
        """BUILD 186: זיהוי אזור מהטקסט - 100% DYNAMIC from JSON!"""
        if not text:
            return ""
        
        text_lower = text.lower()
        
        try:
            from server.services.appointment_parser import _load_dynamic_area_patterns
            area_patterns = _load_dynamic_area_patterns()
            
            for area_name, keywords in area_patterns.items():
                if any(keyword.lower() in text_lower for keyword in keywords):
                    return area_name
        except Exception as e:
            logger.error(f"⚠️ [AREA] Error loading dynamic patterns: {e}")
            
        return ""
    
    # 🔥 BUILD 200: REMOVED _analyze_lead_completeness() function
    # It contained hardcoded business-specific field requirements
    # Lead completeness is now handled 100% by AI prompt - each business defines
    # their own required fields and logic in their custom prompts.
    # This ensures the system works for ANY business type dynamically.
    
    def _finalize_call_on_stop(self):
        """✅ TX_STALL FIX: Minimal finalization - defer heavy tasks to offline worker
        
        RULE 1: NO HEAVY TASKS DURING CALL
        - No AI summary generation (defer to offline worker)
        - No CustomerIntelligence processing (defer to offline worker)
        - No webhook sending (defer to offline worker)
        
        Only lightweight operations:
        - Log call metrics (already in memory)
        - Save basic call_log state
        - Save realtime transcript (already in memory)
        """
        try:
            # 🔥 CALL METRICS: Log comprehensive metrics before finalizing
            self._log_call_metrics()
            
            from server.models_sql import CallLog
            from server.db import db
            import threading
            
            def finalize_in_background():
                """Lightweight finalization - only save what's already in memory"""
                try:
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        # 🔁 IMPORTANT: Load fresh CallLog from DB (not cached)
                        call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if not call_log:
                            logger.warning(f"⚠️ No call_log found for finalization: {self.call_sid}")
                            return
                        
                        # 🔥 TX_STALL FIX: Only save realtime transcript (already in memory)
                        # Do NOT generate AI summary here - that's heavy and runs AFTER call ends
                        full_conversation = ""
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            # ✅ Support both formats: old {'user': X, 'bot': Y} and new {'speaker': X, 'text': Y}
                            conv_lines = []
                            for turn in self.conversation_history:
                                if 'speaker' in turn and 'text' in turn:
                                    # New Realtime API format
                                    speaker_label = "לקוח" if turn['speaker'] == 'user' else "עוזר"
                                    conv_lines.append(f"{speaker_label}: {turn['text']}")
                                elif 'user' in turn and 'bot' in turn:
                                    # Old Google STT/TTS format
                                    conv_lines.append(f"לקוח: {turn['user']}\nעוזר: {turn['bot']}")
                            full_conversation = "\n".join(conv_lines)
                        
                        # ✅ Save lightweight data only (no AI processing!)
                        call_log.status = "completed"
                        call_log.transcription = full_conversation  # Realtime transcript (already in memory)
                        # summary and ai_summary will be filled by offline worker
                        
                        # 🔥 FIX: Save recording_sid if available
                        if hasattr(self, '_recording_sid') and self._recording_sid:
                            call_log.recording_sid = self._recording_sid
                            if DEBUG:
                                logger.info(f"✅ [FINALIZE] Saved recording_sid: {self._recording_sid}")
                        
                        # 🔥 NEW: Update appointment with transcript and summary
                        try:
                            from server.models_sql import Appointment
                            appointment = Appointment.query.filter_by(call_log_id=call_log.id).first()
                            if appointment:
                                # Save full transcript
                                appointment.call_transcript = full_conversation
                                
                                # Generate summary if possible
                                if full_conversation and len(full_conversation) > 50:
                                    try:
                                        from server.services.summary_service import summarize_conversation
                                        from server.services.customer_intelligence import CustomerIntelligence
                                        from server.models_sql import Business
                                        
                                        business = Business.query.get(call_log.business_id)
                                        business_name = business.name if business else None
                                        call_summary = summarize_conversation(
                                            transcription=full_conversation,
                                            call_sid=self.call_sid,
                                            business_name=business_name
                                        )
                                        appointment.call_summary = call_summary
                                        
                                        # Generate dynamic conversation summary
                                        ci = CustomerIntelligence(call_log.business_id)
                                        dynamic_summary_data = ci.generate_conversation_summary(full_conversation)
                                        appointment.dynamic_summary = json.dumps(dynamic_summary_data, ensure_ascii=False)
                                        
                                        # Link to lead if exists
                                        if call_log.lead_id and not appointment.lead_id:
                                            appointment.lead_id = call_log.lead_id
                                        
                                        logger.info(f"✅ [FINALIZE] Appointment #{appointment.id} updated with transcript, summary, and dynamic analysis")
                                    except Exception as sum_err:
                                        logger.warning(f"⚠️ [FINALIZE] Failed to generate summary for appointment: {sum_err}")
                                        # Continue without summary - transcript is saved
                                else:
                                    logger.info(f"✅ [FINALIZE] Appointment #{appointment.id} updated with transcript")
                        except Exception as apt_err:
                            logger.warning(f"⚠️ [FINALIZE] Failed to update appointment: {apt_err}")
                            # Continue - appointment update is not critical
                        
                        db.session.commit()
                        logger.info(f"✅ [FINALIZE] Call metadata saved (realtime only): {self.call_sid}")
                        
                        # 🔥 NEW: Create lead note with call summary/transcript
                        # This ensures the AI has context from previous interactions in future calls
                        if call_log.lead_id and full_conversation and len(full_conversation) > 20:
                            try:
                                from server.models_sql import LeadNote
                                from datetime import datetime
                                
                                # 🔥 NEW: Create a temporary customer-service summary
                                # NOTE: This is a quick summary during the call. The offline worker
                                # will create a better, AI-analyzed summary later.
                                
                                # Try to extract key points from conversation
                                summary_lines = []
                                
                                # Get first 300 chars as quick context
                                quick_summary = full_conversation[:300].strip()
                                if quick_summary:
                                    summary_lines.append(f"💬 {quick_summary}")
                                    if len(full_conversation) > 300:
                                        summary_lines.append("\n📝 (סיכום מפורט יתווסף אוטומטית)")
                                
                                note_content = "\n".join(summary_lines)
                                
                                # Check if note already exists for this call to avoid duplicates
                                existing_note = LeadNote.query.filter_by(
                                    lead_id=call_log.lead_id,
                                    call_id=call_log.id
                                ).first()
                                
                                if not existing_note:
                                    lead_note = LeadNote(
                                        lead_id=call_log.lead_id,
                                        tenant_id=call_log.business_id,
                                        note_type='call_summary',
                                        content=note_content,
                                        call_id=call_log.id,
                                        created_at=datetime.utcnow(),
                                        created_by=None  # AI-generated
                                    )
                                    db.session.add(lead_note)
                                    db.session.commit()
                                    logger.info(f"✅ [FINALIZE] Created quick call summary note for lead_id={call_log.lead_id}")
                                else:
                                    logger.info(f"ℹ️ [FINALIZE] Lead note already exists for this call, skipping duplicate")
                            except Exception as note_err:
                                logger.warning(f"⚠️ [FINALIZE] Failed to create lead note: {note_err}")
                                # Continue - note creation is not critical for call to complete
                                try:
                                    db.session.rollback()
                                except:
                                    pass
                        
                        # 🔥 TX_STALL FIX: Defer ALL heavy processing to offline worker
                        # The offline worker (tasks_recording.py) will handle:
                        #   1. Download recording
                        #   2. Offline Whisper transcription (higher quality than realtime)
                        #   3. AI summary generation
                        #   4. Extract city/service from summary
                        #   5. Update lead with summary
                        #   6. Send webhook call.completed
                        logger.info(f"✅ [TX_STALL_FIX] Call {self.call_sid} closed - offline worker will handle heavy processing")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to finalize call: {e}")
                    import traceback
                    traceback.print_exc()
                    # 🔥 CRITICAL FIX: Rollback on DB errors to prevent InFailedSqlTransaction
                    try:
                        db.session.rollback()
                    except:
                        pass
            
            # רוץ ברקע
            thread = threading.Thread(target=finalize_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            logger.error(f"❌ Call finalization setup failed: {e}")
    
    def _start_call_recording(self):
        """✅ התחל הקלטת שיחה דרך Twilio REST API - מבטיח שכל השיחות מוקלטות
        
        Idempotency: Safe to call multiple times - checks for existing recordings
        Thread-safe: Runs in background thread
        Error handling: Graceful degradation - recording failure doesn't crash the call
        Retry: Resets flag on failure to allow retry later in call
        
        Note: TwiML fallback (<Record>) is the primary mechanism. This is an 
        additional layer to ensure recording starts early in the call.
        """
        try:
            # Idempotency check: Don't start if already succeeded
            if getattr(self, '_recording_succeeded', False):
                return
            
            # Mark attempt in progress
            if hasattr(self, '_recording_attempt_count'):
                self._recording_attempt_count += 1
                if self._recording_attempt_count > 3:
                    # Stop retrying after 3 attempts
                    return
            else:
                self._recording_attempt_count = 1
            
            import threading
            import time as time_module
            
            def start_recording_in_background():
                try:
                    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
                    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
                    
                    if not account_sid or not auth_token:
                        logger.warning(f"⚠️ Missing Twilio credentials - TwiML fallback will handle recording")
                        return
                    
                    if not self.call_sid:
                        logger.warning(f"⚠️ No call_sid - cannot start recording")
                        return
                    
                    from twilio.rest import Client
                    client = Client(account_sid, auth_token)
                    
                    # Small delay to let Twilio establish call state
                    time_module.sleep(0.5)
                    
                    # Idempotency: Check if recording already exists
                    try:
                        existing_recordings = client.recordings.list(call_sid=self.call_sid, limit=1)
                        if existing_recordings:
                            self._recording_succeeded = True
                            self._recording_sid = existing_recordings[0].sid
                            logger.info(f"✅ Recording already active for {self.call_sid}: {self._recording_sid}")
                            return
                    except Exception as list_error:
                        # Failed to check existing recordings - try to create anyway
                        logger.error(f"⚠️ Could not check existing recordings: {list_error}")
                    
                    # Start a new recording via REST API
                    try:
                        recording = client.calls(self.call_sid).recordings.create(
                            recording_channels="dual"  # Record both channels
                        )
                        self._recording_succeeded = True
                        self._recording_sid = recording.sid
                        logger.info(f"✅ Recording started for {self.call_sid}: {recording.sid}")
                        
                    except Exception as rec_error:
                        error_msg = str(rec_error).lower()
                        # These are expected conditions - recording is active
                        if any(phrase in error_msg for phrase in [
                            'recording is already in progress',
                            'already',
                            'duplicate',
                            'cannot be modified'
                        ]):
                            self._recording_succeeded = True
                            logger.info(f"✅ Recording already in progress for {self.call_sid}")
                        elif 'call is not in-progress' in error_msg:
                            # Call hasn't started yet - TwiML fallback will handle
                            logger.warning(f"⚠️ Call {self.call_sid} not in-progress - TwiML fallback will handle recording")
                        else:
                            # Transient failure - allow retry
                            logger.error(f"⚠️ Could not start REST API recording for {self.call_sid}: {rec_error}")
                        
                except Exception as e:
                    # Transient failure - allow retry, TwiML fallback is active
                    logger.error(f"⚠️ Recording start failed (TwiML fallback active): {e}")
            
            # Run in background - don't block call handling
            thread = threading.Thread(
                target=start_recording_in_background, 
                daemon=True,
                name=f"Recording-{self.call_sid[:8] if self.call_sid else 'unknown'}"
            )
            thread.start()
            self.background_threads.append(thread)
            
        except Exception as e:
            # Never crash the call due to recording setup failure
            logger.error(f"⚠️ Recording setup failed (TwiML fallback active): {e}")
    
    def _create_call_log_on_start(self):
        """✅ יצירת call_log מיד בהתחלת שיחה - למניעת 'Call SID not found' errors"""
        try:
            from server.models_sql import CallLog
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def create_in_background():
                try:
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        # ✅ LOG DATABASE CONNECTION (per הנחיות)
                        db_url = os.getenv('DATABASE_URL', 'NOT_SET')
                        db_driver = db_url.split(':')[0] if db_url else 'none'
                        logger.info(f"🔧 DB_URL_AT_WRITE: driver={db_driver}, BIZ={getattr(self, 'business_id', 'N/A')}, SID={self.call_sid}")
                        
                        # בדוק אם כבר קיים
                        existing = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if existing:
                            logger.info(f"✅ Call log already exists for {self.call_sid}")
                            return
                        
                        # צור call_log חדש
                        call_log = CallLog()  # type: ignore[call-arg]
                        business_id = getattr(self, 'business_id', None)
                        if not business_id:
                            logger.error(f"❌ No business_id set - cannot create call_log")
                            return
                        call_log.business_id = business_id
                        call_log.call_sid = self.call_sid
                        call_log.from_number = str(self.phone_number or "")
                        call_log.to_number = str(getattr(self, 'to_number', '') or '')
                        
                        # 🔥 SSOT: Set initial status ONLY on creation
                        # ⚠️ CRITICAL: After creation, NEVER update call_status/status
                        # ✅ OWNER: Webhooks own all status updates after this point
                        call_log.call_status = "in_progress"
                        
                        db.session.add(call_log)
                        
                        # 🔥 יצירת/טעינת CallSession לdeduplication יציב
                        from server.models_sql import CallSession
                        call_session = CallSession.query.filter_by(call_sid=self.call_sid).first()
                        if not call_session:
                            call_session = CallSession()  # type: ignore[call-arg]
                            call_session.call_sid = self.call_sid
                            call_session.business_id = business_id
                            # lead_id will be set later by ensure_lead
                            db.session.add(call_session)
                            logger.info(f"✅ Created CallSession for {self.call_sid}")
                        else:
                            logger.info(f"✅ CallSession already exists for {self.call_sid}")
                        
                        try:
                            db.session.commit()
                            logger.info(f"✅ Created call_log + CallSession on start: call_sid={self.call_sid}, phone={self.phone_number}")
                        except Exception as commit_error:
                            # Handle duplicate key error (race condition)
                            db.session.rollback()
                            error_msg = str(commit_error).lower()
                            if 'unique' in error_msg or 'duplicate' in error_msg:
                                logger.warning(f"⚠️ Call log already exists (race condition): {self.call_sid}")
                            else:
                                raise
                        
                except Exception as e:
                    logger.error(f"❌ Failed to create call_log on start: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע
            thread = threading.Thread(target=create_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            logger.error(f"❌ Call log creation setup failed: {e}")
    
    def _save_conversation_turn(self, user_text: str, bot_reply: str):
        """✅ שמירת תור שיחה במסד נתונים לזיכרון קבוע"""
        try:
            from server.models_sql import ConversationTurn, CallLog
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def save_in_background():
                try:
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        # מצא call_log קיים (אמור להיות כבר נוצר ב-_create_call_log_on_start)
                        call_log = None
                        if hasattr(self, 'call_sid') and self.call_sid:
                            call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        
                        if not call_log:
                            logger.warning(f"⚠️ Call log not found for {self.call_sid} - conversation turn not saved")
                            return
                        
                        # שמור תור משתמש
                        user_turn = ConversationTurn()  # type: ignore[call-arg]
                        user_turn.call_log_id = call_log.id
                        user_turn.call_sid = self.call_sid or f"live_{int(time.time())}"
                        user_turn.speaker = 'user'
                        user_turn.message = user_text
                        user_turn.confidence_score = 1.0
                        db.session.add(user_turn)
                        
                        # שמור תור AI
                        bot_turn = ConversationTurn()  # type: ignore[call-arg]
                        bot_turn.call_log_id = call_log.id
                        bot_turn.call_sid = self.call_sid or f"live_{int(time.time())}"
                        bot_turn.speaker = 'assistant'
                        bot_turn.message = bot_reply
                        bot_turn.confidence_score = 1.0
                        db.session.add(bot_turn)
                        
                        db.session.commit()
                        logger.info(f"✅ Saved conversation turn to DB: call_log_id={call_log.id}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to save conversation turn: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע כדי לא לחסום
            thread = threading.Thread(target=save_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            logger.error(f"❌ Conversation turn save setup failed: {e}")
    
    def _process_customer_intelligence(self, user_text: str, bot_reply: str):
        """
        ✨ TX_STALL FIX: DISABLED - No heavy processing during call
        
        This function previously did heavy AI processing during active calls:
        - generate_conversation_summary (GPT API call)
        - auto_update_lead_status (AI processing)
        
        All of this is now deferred to the offline worker which runs AFTER
        the call ends. See tasks_recording.py:save_call_to_db() for the
        implementation.
        """
        # 🔥 TX_STALL FIX: Disabled - all processing moved to offline worker
        return
    
    def _log_call_metrics(self):
        """
        🔥 CALL METRICS: Log comprehensive metrics for each call
        
        Called at call end to log key performance indicators:
        - Greeting latency
        - First user utterance timing
        - Average turn durations
        - Barge-in events count
        - Silence events count
        - STT hallucinations dropped count
        
        This helps identify patterns and tune thresholds per business.
        """
        try:
            # Calculate greeting latency
            greeting_ms = 0
            if hasattr(self, 'greeting_completed_at') and hasattr(self, 'connection_start_time'):
                if self.greeting_completed_at and self.connection_start_time:
                    greeting_ms = int((self.greeting_completed_at - self.connection_start_time) * 1000)
            
            # Calculate first user utterance timing
            first_user_utterance_ms = 0
            if hasattr(self, 'conversation_history') and self.conversation_history:
                for msg in self.conversation_history:
                    if msg.get('speaker') == 'user' and msg.get('ts'):
                        if hasattr(self, 'connection_start_time') and self.connection_start_time:
                            first_user_utterance_ms = int((msg['ts'] - self.connection_start_time) * 1000)
                        break
            
            # Helper to avoid code duplication
            conversation_history = self.conversation_history if hasattr(self, 'conversation_history') else []
            
            # Calculate average AI turn duration
            ai_turn_durations = []
            for i, msg in enumerate(conversation_history):
                if msg.get('speaker') == 'ai' and msg.get('ts'):
                    # Find next message to calculate duration
                    if i + 1 < len(conversation_history):
                        next_msg = conversation_history[i + 1]
                        if next_msg.get('ts'):
                            duration_ms = int((next_msg['ts'] - msg['ts']) * 1000)
                            ai_turn_durations.append(duration_ms)
            
            avg_ai_turn_ms = int(sum(ai_turn_durations) / len(ai_turn_durations)) if ai_turn_durations else 0
            
            # Calculate average user turn duration
            user_turn_durations = []
            for i, msg in enumerate(conversation_history):
                if msg.get('speaker') == 'user' and msg.get('ts'):
                    # Find next message to calculate duration
                    if i + 1 < len(conversation_history):
                        next_msg = conversation_history[i + 1]
                        if next_msg.get('ts'):
                            duration_ms = int((next_msg['ts'] - msg['ts']) * 1000)
                            user_turn_durations.append(duration_ms)
            
            avg_user_turn_ms = int(sum(user_turn_durations) / len(user_turn_durations)) if user_turn_durations else 0
            
            # Count barge-in events
            barge_in_events = getattr(self, '_barge_in_event_count', 0)
            
            # Count silence events (10s+ gaps)
            silences_10s = getattr(self, '_silence_10s_count', 0)
            
            # Count STT hallucinations dropped
            stt_hallucinations_dropped = getattr(self, '_stt_hallucinations_dropped', 0)
            
            # 🎯 TASK 6.1: STT QUALITY METRICS
            # 🔧 CODE REVIEW FIX: Optimize - single pass instead of multiple list comprehensions
            stt_utterances_total = 0
            stt_empty_count = 0
            stt_very_short_count = 0
            
            for msg in conversation_history:
                if msg.get('speaker') == 'user':
                    stt_utterances_total += 1
                    if msg.get('filtered', False):
                        text_len = len(msg.get('text', '').strip())
                        if text_len == 0:
                            stt_empty_count += 1
                        elif text_len < 5:
                            stt_very_short_count += 1
            
            # Count filler-only utterances
            stt_filler_only_count = getattr(self, '_stt_filler_only_count', 0)
            
            # 🎯 TASK 6.1: AUDIO PIPELINE METRICS - Separate counters for drop diagnosis
            frames_in_from_twilio = getattr(self, 'realtime_audio_in_chunks', 0)
            frames_forwarded_to_realtime = getattr(self, '_stats_audio_sent', 0)
            frames_dropped_total = getattr(self, '_stats_audio_blocked', 0)
            frames_dropped_by_greeting_lock = getattr(self, '_frames_dropped_by_greeting_lock', 0)
            frames_dropped_by_filters = getattr(self, '_frames_dropped_by_filters', 0)
            frames_dropped_by_queue_full = getattr(self, '_frames_dropped_by_queue_full', 0)
            
            # 🎯 TASK 6.1: SIMPLE MODE MONITORING - Log frame drops with detailed breakdown
            # Note: Some drops (echo-gate, echo-decay) may be intentional for call quality
            # The goal is transparency, not zero drops
            if SIMPLE_MODE and frames_dropped_total > 0:
                # Get detailed breakdown from enum-tracked reasons
                reason_breakdown = []
                for reason, count in getattr(self, '_frames_dropped_by_reason', {}).items():
                    if count > 0:
                        reason_breakdown.append(f"{reason.value}={count}")
                
                reason_details = ", ".join(reason_breakdown) if reason_breakdown else "unknown"
                
                logger.warning(
                    f"[CALL_METRICS] ⚠️ SIMPLE_MODE DROPS DETECTED: {frames_dropped_total} frames dropped. "
                    f"greeting_lock={frames_dropped_by_greeting_lock}, "
                    f"filters={frames_dropped_by_filters}, "
                    f"queue_full={frames_dropped_by_queue_full}. "
                    f"Detailed breakdown: {reason_details}. "
                    f"Note: echo-gate/decay drops are often intentional for call quality."
                )
            
            # Log comprehensive metrics
            logger.info(
                "[CALL_METRICS] greeting_ms=%(greeting_ms)d, "
                "first_user_utterance_ms=%(first_user_utterance_ms)d, "
                "avg_ai_turn_ms=%(avg_ai_turn_ms)d, "
                "avg_user_turn_ms=%(avg_user_turn_ms)d, "
                "barge_in_events=%(barge_in_events)d, "
                "silences_10s=%(silences_10s)d, "
                "stt_hallucinations_dropped=%(stt_hallucinations_dropped)d, "
                "stt_utterances_total=%(stt_utterances_total)d, "
                "stt_empty=%(stt_empty)d, "
                "stt_short=%(stt_short)d, "
                "stt_filler_only=%(stt_filler_only)d, "
                "frames_in=%(frames_in)d, "
                "frames_forwarded=%(frames_forwarded)d, "
                "frames_dropped_total=%(frames_dropped_total)d, "
                "frames_dropped_greeting=%(frames_dropped_greeting)d, "
                "frames_dropped_filters=%(frames_dropped_filters)d, "
                "frames_dropped_queue=%(frames_dropped_queue)d",
                {
                    'greeting_ms': greeting_ms,
                    'first_user_utterance_ms': first_user_utterance_ms,
                    'avg_ai_turn_ms': avg_ai_turn_ms,
                    'avg_user_turn_ms': avg_user_turn_ms,
                    'barge_in_events': barge_in_events,
                    'silences_10s': silences_10s,
                    'stt_hallucinations_dropped': stt_hallucinations_dropped,
                    'stt_utterances_total': stt_utterances_total,
                    'stt_empty': stt_empty_count,
                    'stt_short': stt_very_short_count,
                    'stt_filler_only': stt_filler_only_count,
                    'frames_in': frames_in_from_twilio,
                    'frames_forwarded': frames_forwarded_to_realtime,
                    'frames_dropped_total': frames_dropped_total,
                    'frames_dropped_greeting': frames_dropped_by_greeting_lock,
                    'frames_dropped_filters': frames_dropped_by_filters,
                    'frames_dropped_queue': frames_dropped_by_queue_full
                }
            )
            
            # Also print for visibility
            logger.info(f"📊 [CALL_METRICS] Call {self.call_sid[:16] if hasattr(self, 'call_sid') else 'N/A'}")
            logger.info(f"   Greeting: {greeting_ms}ms")
            logger.info(f"   First user utterance: {first_user_utterance_ms}ms")
            logger.info(f"   Avg AI turn: {avg_ai_turn_ms}ms")
            logger.info(f"   Avg user turn: {avg_user_turn_ms}ms")
            logger.info(f"   Barge-in events: {barge_in_events}")
            logger.info(f"   Silences (10s+): {silences_10s}")
            logger.info(f"   STT hallucinations dropped: {stt_hallucinations_dropped}")
            logger.info(f"   STT total: {stt_utterances_total}, empty: {stt_empty_count}, short: {stt_very_short_count}, filler-only: {stt_filler_only_count}")
            logger.info(f"   Audio pipeline: in={frames_in_from_twilio}, forwarded={frames_forwarded_to_realtime}, dropped_total={frames_dropped_total}")
            logger.info(f"   Drop breakdown: greeting_lock={frames_dropped_by_greeting_lock}, filters={frames_dropped_by_filters}, queue_full={frames_dropped_by_queue_full}")
            if SIMPLE_MODE and frames_dropped_total > 0:
                logger.warning(f"   ⚠️ NOTE: SIMPLE_MODE drops detected - {frames_dropped_total} frames (see breakdown above)")
            
            # 🔥 VERIFICATION: Mathematical frame accounting validation
            # Ensure frames_in == frames_forwarded + frames_dropped_total
            expected_total = frames_forwarded_to_realtime + frames_dropped_total
            if frames_in_from_twilio != expected_total:
                accounting_error = frames_in_from_twilio - expected_total
                logger.error(
                    f"[FRAME_ACCOUNTING_ERROR] Mathematical inconsistency detected! "
                    f"frames_in={frames_in_from_twilio}, "
                    f"frames_forwarded={frames_forwarded_to_realtime}, "
                    f"frames_dropped_total={frames_dropped_total}, "
                    f"expected_total={expected_total}, "
                    f"accounting_error={accounting_error}"
                )
                logger.error(f"   🚨 FRAME ACCOUNTING ERROR: Missing/extra {accounting_error} frames!")
                logger.info(f"      frames_in={frames_in_from_twilio} != forwarded({frames_forwarded_to_realtime}) + dropped({frames_dropped_total})")
            else:
                logger.info(f"   ✅ Frame accounting OK: {frames_in_from_twilio} = {frames_forwarded_to_realtime} + {frames_dropped_total}")
            
            # 🔥 VERIFICATION: Validate drop reason sum matches total
            reason_sum = sum(getattr(self, '_frames_dropped_by_reason', {}).values())
            if reason_sum != frames_dropped_total:
                logger.error(
                    f"[DROP_REASON_ERROR] Drop reason sum mismatch! "
                    f"reason_sum={reason_sum}, frames_dropped_total={frames_dropped_total}, "
                    f"difference={frames_dropped_total - reason_sum}"
                )
                logger.error(f"   🚨 DROP REASON ERROR: sum of reasons ({reason_sum}) != total dropped ({frames_dropped_total})")
                # Print all reason counts for debugging
                for reason, count in getattr(self, '_frames_dropped_by_reason', {}).items():
                    if count > 0:
                        logger.info(f"      {reason.value}: {count}")
            else:
                logger.info(f"   ✅ Drop reason accounting OK: sum({reason_sum}) = total({frames_dropped_total})")
            
            # 🔥 VERIFICATION: Validate greeting_lock counters are consistent
            greeting_lock_from_enum = getattr(self, '_frames_dropped_by_reason', {}).get(FrameDropReason.GREETING_LOCK, 0)
            if greeting_lock_from_enum != frames_dropped_by_greeting_lock:
                logger.error(
                    f"[GREETING_LOCK_ERROR] Greeting lock counter mismatch! "
                    f"enum_counter={greeting_lock_from_enum}, aggregate_counter={frames_dropped_by_greeting_lock}, "
                    f"difference={greeting_lock_from_enum - frames_dropped_by_greeting_lock}"
                )
                logger.error(f"   🚨 GREETING LOCK ERROR: enum({greeting_lock_from_enum}) != aggregate({frames_dropped_by_greeting_lock})")
            else:
                logger.info(f"   ✅ Greeting lock accounting OK: {greeting_lock_from_enum} frames")
            
        except Exception as e:
            logger.error(f"[CALL_METRICS] Failed to log metrics: {e}")
            import traceback
            traceback.print_exc()
