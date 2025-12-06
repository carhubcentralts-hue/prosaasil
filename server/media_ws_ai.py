"""
WebSocket Media Stream Handler - AI Mode with Hebrew TTS
ADVANCED VERSION WITH TURN-TAKING, BARGE-IN, AND LOOP PREVENTION
"""
import os, json, time, base64, audioop, math, threading, queue, random, zlib, asyncio, re
import builtins
from dataclasses import dataclass
from typing import Optional
from server.services.mulaw_fast import mulaw_to_pcm16_fast
from server.services.appointment_nlp import extract_appointment_request
from server.services.hebrew_stt_validator import validate_stt_output, is_gibberish, load_hebrew_lexicon

# ⚡ PHASE 1: DEBUG mode - חונק כל print ב-hot path
DEBUG = os.getenv("DEBUG", "0") == "1"
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

# 🔥 BUILD 309: SIMPLE_MODE - Simplified call flow without aggressive filters
try:
    from server.config.calls import SIMPLE_MODE
except ImportError:
    SIMPLE_MODE = True  # Default to SIMPLE_MODE if config not found

# 🎯 BARGE-IN: Allow users to interrupt AI mid-sentence
# Enabled by default with smart state tracking (is_ai_speaking + has_pending_ai_response)
ENABLE_BARGE_IN = os.getenv("ENABLE_BARGE_IN", "true").lower() in ("true", "1", "yes")

# 🚀 REALTIME API MODE - OpenAI Realtime API for phone calls
# 🔥 BUILD 186: ALWAYS enabled - no fallback to Google STT/TTS!
USE_REALTIME_API = True  # FORCED TRUE - OpenAI Realtime API only!

# 🎯 AGENT 3 SPEC: Force gpt-4o-realtime-preview (NOT mini)
# This overrides any environment variable to ensure compliance
OPENAI_REALTIME_MODEL = "gpt-4o-realtime-preview"

# 🔍 VERIFICATION: Log if env var tries to override
_env_model = os.getenv("OPENAI_REALTIME_MODEL")
if _env_model and _env_model != OPENAI_REALTIME_MODEL:
    import logging
    logging.getLogger(__name__).warning(
        f"⚠️ [AGENT 3] OPENAI_REALTIME_MODEL env var='{_env_model}' IGNORED - "
        f"Agent 3 spec requires '{OPENAI_REALTIME_MODEL}'"
    )

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
    bot_speaks_first: bool = False
    greeting_text: str = ""
    
    # Call control settings
    auto_end_after_lead_capture: bool = False
    auto_end_on_goodbye: bool = False
    smart_hangup_enabled: bool = True
    enable_calendar_scheduling: bool = True  # 🔥 BUILD 186: AI can schedule appointments
    
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
            self.required_lead_fields = ['name', 'phone']


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
        
        config = CallConfig(
            business_id=business_id,
            business_name=business.name or "",
            greeting_enabled=True,
            bot_speaks_first=getattr(settings, 'bot_speaks_first', False) if settings else False,
            greeting_text=business.greeting_message or "",
            auto_end_after_lead_capture=getattr(settings, 'auto_end_after_lead_capture', False) if settings else False,
            auto_end_on_goodbye=getattr(settings, 'auto_end_on_goodbye', False) if settings else False,
            smart_hangup_enabled=getattr(settings, 'smart_hangup_enabled', True) if settings else True,
            enable_calendar_scheduling=getattr(settings, 'enable_calendar_scheduling', True) if settings else True,
            call_goal=call_goal,
            confirm_before_hangup=confirm_before_hangup,
            silence_timeout_sec=getattr(settings, 'silence_timeout_sec', 15) if settings else 15,
            silence_max_warnings=getattr(settings, 'silence_max_warnings', 2) if settings else 2,
            required_lead_fields=getattr(settings, 'required_lead_fields', ['name', 'phone']) if settings else ['name', 'phone'],
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
    
    🔥 NEW: has_appointment_created flag - prevents AI from saying "confirmed" before server approval
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
            print(f"🔍 [VALIDATION] Timezone-aware input converted to {policy.tz}: {requested_dt}")
        else:
            # Naive datetime - assume it's in business local time
            print(f"🔍 [VALIDATION] Naive input assumed to be in {policy.tz}: {requested_dt}")
        
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
                print(f"❌ [VALIDATION] Slot {requested_dt} too soon! Minimum {policy.min_notice_min}min notice required (earliest: {min_allowed_time.strftime('%H:%M')})")
                return False
            else:
                print(f"✅ [VALIDATION] Min notice check passed ({policy.min_notice_min}min)")
        
        # Check booking window (max days ahead)
        if policy.booking_window_days > 0:
            max_booking_date = now + timedelta(days=policy.booking_window_days)
            if requested_dt.tzinfo is None:
                requested_dt_aware = business_tz.localize(requested_dt)
            else:
                requested_dt_aware = requested_dt
            
            if requested_dt_aware > max_booking_date:
                print(f"❌ [VALIDATION] Slot {requested_dt.date()} too far ahead! Max {policy.booking_window_days} days allowed (until {max_booking_date.date()})")
                return False
            else:
                print(f"✅ [VALIDATION] Booking window check passed ({policy.booking_window_days} days)")
        
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
                print(f"❌ [VALIDATION] Invalid weekday: {requested_dt.weekday()}")
                return False
            
            # Get opening hours for this day
            day_hours = policy.opening_hours.get(weekday_key, [])
            if not day_hours:
                print(f"❌ [VALIDATION] Business closed on {weekday_key}")
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
                print(f"❌ [VALIDATION] Slot {requested_time} outside business hours {day_hours}")
                return False
            else:
                print(f"✅ [VALIDATION] Slot {requested_time} within business hours")
        else:
            print(f"✅ [VALIDATION] 24/7 business - hours check skipped")
        
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
        
        print(f"🔍 [VALIDATION] Checking calendar: {requested_start_naive.strftime('%Y-%m-%d %H:%M')} - {requested_end_naive.strftime('%H:%M')} (slot_size={slot_duration_min}min)")
        
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
                print(f"❌ [VALIDATION] CONFLICT! Found {overlapping} overlapping appointment(s) in calendar")
                return False
            else:
                print(f"✅ [VALIDATION] Calendar available - no conflicts")
                return True
        
    except Exception as e:
        print(f"❌ [VALIDATION] Error validating slot: {e}")
        import traceback
        traceback.print_exc()
        return False


# 🔧 CRM HELPER FUNCTIONS (Server-side only, no Realtime Tools)
def ensure_lead(business_id: int, customer_phone: str) -> Optional[int]:
    """
    Find or create lead at call start
    
    Args:
        business_id: Business ID
        customer_phone: Customer phone in E.164 format
    
    Returns:
        Lead ID if found/created, None on error
    """
    try:
        from server.models_sql import db, Lead
        from datetime import datetime
        
        app = _get_flask_app()
        with app.app_context():
            # Normalize phone to E.164
            phone = customer_phone.strip()
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = '+972' + phone[1:]
                else:
                    phone = '+972' + phone
            
            # Search for existing lead
            lead = Lead.query.filter_by(
                tenant_id=business_id,
                phone_e164=phone
            ).first()
            
            if lead:
                # Update last contact time
                lead.last_contact_at = datetime.utcnow()
                db.session.commit()
                print(f"✅ [CRM] Found existing lead #{lead.id} for {phone}")
                return lead.id
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
                db.session.add(lead)
                db.session.commit()
                print(f"✅ [CRM] Created new lead #{lead.id} for {phone}")
                return lead.id
                
    except Exception as e:
        print(f"❌ [CRM] ensure_lead error: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_lead_on_call(lead_id: int, summary: Optional[str] = None, 
                        status: Optional[str] = None, notes: Optional[str] = None):
    """
    Update lead at call end with summary/status
    
    Args:
        lead_id: Lead ID to update
        summary: Call summary (optional)
        status: New status (optional)
        notes: Additional notes (optional)
    """
    try:
        from server.models_sql import db, Lead
        from datetime import datetime
        
        app = _get_flask_app()
        with app.app_context():
            lead = Lead.query.get(lead_id)
            if not lead:
                print(f"⚠️ [CRM] Lead #{lead_id} not found")
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
            db.session.commit()
            
            print(f"✅ [CRM] Updated lead #{lead_id}: summary={bool(summary)}, status={status}")
            
    except Exception as e:
        print(f"❌ [CRM] update_lead_on_call error: {e}")
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
    print(f"")
    print(f"🔧 [CREATE_APPT] ========== create_appointment_from_realtime called ==========")
    print(f"🔧 [CREATE_APPT] Input parameters:")
    print(f"🔧 [CREATE_APPT]   - business_id: {business_id}")
    print(f"🔧 [CREATE_APPT]   - customer_name: {customer_name}")
    print(f"🔧 [CREATE_APPT]   - customer_phone: {customer_phone}")
    print(f"🔧 [CREATE_APPT]   - treatment_type: {treatment_type}")
    print(f"🔧 [CREATE_APPT]   - start_iso: {start_iso}")
    print(f"🔧 [CREATE_APPT]   - end_iso: {end_iso}")
    print(f"🔧 [CREATE_APPT]   - notes: {notes}")
    
    try:
        from server.agent_tools.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
        
        app = _get_flask_app()
        with app.app_context():
            print(f"🔧 [CREATE_APPT] Creating CreateAppointmentInput...")
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
            print(f"🔧 [CREATE_APPT] Input created successfully, calling _calendar_create_appointment_impl...")
            
            result = _calendar_create_appointment_impl(input_data, context=None, session=None)
            print(f"🔧 [CREATE_APPT] _calendar_create_appointment_impl returned: {type(result)}")
            
            # 🔥 FIX: Handle CreateAppointmentOutput dataclass (not dict!)
            if hasattr(result, 'appointment_id'):
                # Success - got CreateAppointmentOutput
                appt_id = result.appointment_id
                print(f"✅ [CREATE_APPT] SUCCESS! Appointment #{appt_id} created")
                print(f"✅ [CREATE_APPT]   - status: {result.status}")
                print(f"✅ [CREATE_APPT]   - whatsapp_status: {result.whatsapp_status}")
                print(f"✅ [CREATE_APPT]   - lead_id: {result.lead_id}")
                print(f"✅ [CREATE_APPT]   - message: {result.confirmation_message}")
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
                print(f"🔧 [CREATE_APPT] Got dict result: {result}")
                if result.get("ok"):
                    appt_id = result.get("appointment_id")
                    print(f"✅ [CREATE_APPT] SUCCESS (dict)! Appointment #{appt_id} created")
                else:
                    error_msg = result.get("message", "Unknown error")
                    print(f"❌ [CREATE_APPT] FAILED (dict): {error_msg}")
                return result
            else:
                # Unexpected result format
                print(f"❌ [CREATE_APPT] UNEXPECTED RESULT TYPE: {type(result)}")
                print(f"❌ [CREATE_APPT] Result value: {result}")
                return None
                
    except Exception as e:
        print(f"❌ [CRM] create_appointment_from_realtime error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ⚡ BUILD 168.2: Minimal boot logging (clean startup)
logger.info(f"[BOOT] USE_REALTIME_API={USE_REALTIME_API} MODEL={OPENAI_REALTIME_MODEL}")
if not USE_REALTIME_API:
    logger.warning("[BOOT] USE_REALTIME_API=FALSE - AI will NOT speak during calls!")

# ⚡ THREAD-SAFE SESSION REGISTRY for multi-call support
# Each call_sid has its own session + dispatcher state
_sessions_registry = {}  # call_sid -> {"session": StreamingSTTSession, "utterance": {...}, "tenant": str, "ts": float}
_registry_lock = threading.RLock()
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "50"))

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
        if DEBUG: print(f"✅ [REGISTRY] Registered session for call {call_sid[:8]}... (tenant: {tenant_id}, total: {len(_sessions_registry)})")

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
            if DEBUG: print(f"✅ [REGISTRY] Closed session for call {call_sid[:8]}... (remaining: {len(_sessions_registry)})")
        except Exception as e:
            if DEBUG: print(f"⚠️ [REGISTRY] Error closing session for {call_sid[:8]}...: {e}")

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
                    if DEBUG: print(f"🟡 [PARTIAL] BEST updated: '{text}' ({len(text)} chars) for {call_sid[:8]}...")
                else:
                    if DEBUG: print(f"🟡 [PARTIAL] IGNORED (shorter): '{text}' ({len(text)} chars) vs '{current_best}' ({len(current_best)} chars)")
            
            # ⚡ BUILD 114: Early Finalization - if partial is strong enough, trigger final AND continue
            # This saves 400-600ms by triggering final event early
            if text and len(text) > 15 and text.rstrip().endswith(('.', '?', '!')):
                if DEBUG: print(f"⚡ [EARLY_FINALIZE] Strong partial detected: '{text}' → triggering final event")
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
                    print(f"⚠️ Partial callback error for {call_sid[:8]}...: {e}")
    
    def on_final(text: str):
        utt = _get_utterance_state(call_sid)
        if utt:
            buf = utt.get("final_buf")
            if buf is not None:
                buf.append(text)
                if DEBUG: print(f"✅ [FINAL] '{text}' received for {call_sid[:8]}... (utterance: {utt.get('id', '???')})")
                
                # ⚡ Signal that final has arrived!
                final_event = utt.get("final_received")
                if final_event:
                    final_event.set()
                    if DEBUG: print(f"📢 [FINAL_EVENT] Set for {call_sid[:8]}...")
    
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
        if DEBUG: print(f"🧹 [REAPER] Cleaning stale session: {call_sid[:8]}... (inactive for >{STALE_TIMEOUT}s)")
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
                print(f"⚠️ [REAPER] Error during cleanup: {e}")
    
    reaper_thread = threading.Thread(target=reaper_loop, daemon=True, name="SessionReaper")
    reaper_thread.start()
    print("🧹 [REAPER] Session cleanup thread started")

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
# ⚡ BUILD 301: TRUST OPENAI VAD - Lower local thresholds to let more audio through
# OpenAI's Realtime API has excellent VAD - we should trust it, not block audio locally
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.35"))       # 🔥 BUILD 301: 0.35s (was 0.6s) - allow short words like "כן"
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "12.0"))       # ✅ 12.0s - enough time for detailed descriptions
VAD_RMS = int(os.getenv("VAD_RMS", "80"))                   # 🔥 BUILD 301: 80 (was 180) - trust OpenAI VAD, lower local threshold
# 🔥 BUILD 301: RELAXED THRESHOLDS - Trust OpenAI's superior VAD
RMS_SILENCE_THRESHOLD = int(os.getenv("RMS_SILENCE_THRESHOLD", "40"))       # 🔥 BUILD 301: 40 (was 120) - only true silence
MIN_SPEECH_RMS = int(os.getenv("MIN_SPEECH_RMS", "60"))                     # 🔥 BUILD 301: 60 (was 180) - allow quiet speech through
MIN_SPEECH_DURATION_MS = int(os.getenv("MIN_SPEECH_DURATION_MS", "350"))    # 🔥 BUILD 301: 350ms (was 900ms) - per Watchdog doc
# 🔥 BUILD 301: MINIMAL CONSECUTIVE FRAMES - OpenAI handles VAD better than us
MIN_CONSECUTIVE_VOICE_FRAMES = int(os.getenv("MIN_CONSECUTIVE_VOICE_FRAMES", "3"))  # 🔥 BUILD 301: 3 frames (was 7) = 60ms - let more through
# 🔥 BUILD 171: POST-AI COOLDOWN - Reject transcripts arriving too fast after AI speaks
POST_AI_COOLDOWN_MS = int(os.getenv("POST_AI_COOLDOWN_MS", "800"))           # 🔥 BUILD 301: 800ms (was 1200ms) - reduced for faster response
NOISE_HOLD_MS = int(os.getenv("NOISE_HOLD_MS", "150"))                       # 🔥 BUILD 301: 150ms (was 250ms) - shorter grace
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "150"))  # 🔥 BUILD 301: 150ms (was 250ms) - shorter hangover
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "50")) # ⚡ SPEED: 50ms במקום 80ms - תגובה מהירה
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "120")) # ⚡ SPEED: 120ms במקום 200ms - פחות המתנה
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "1100")) # ⚡ BUILD 107: 1100ms - קירור מהיר יותר
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","25"))  # 🔥 BUILD 301: 25 frames (was 45) = ≈500ms - more responsive barge-in

# 🔥 BUILD 169: STT SEGMENT MERGING - Debounce/merge window for user messages
STT_MERGE_WINDOW_MS = int(os.getenv("STT_MERGE_WINDOW_MS", "600"))  # 🔥 BUILD 186: Reduced from 800ms to 600ms to reduce noise merge
THINKING_HINT_MS = int(os.getenv("THINKING_HINT_MS", "0"))       # בלי "בודקת" - ישירות לעבודה!
THINKING_TEXT_HE = os.getenv("THINKING_TEXT_HE", "")   # אין הודעת חשיבה
DEDUP_WINDOW_SEC = int(os.getenv("DEDUP_WINDOW_SEC", "8"))        # חלון קצר יותר
LLM_NATURAL_STYLE = True  # תגובות טבעיות לפי השיחה

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

class MediaStreamHandler:
    def __init__(self, ws):
        self.ws = ws
        self.mode = "AI"  # תמיד במצב AI
        
        # 🔧 תאימות WebSocket - EventLet vs RFC6455 עם טיפול שגיאות
        if hasattr(ws, 'send'):
            self._ws_send_method = ws.send
        else:
            # אם אין send, נסה send_text או כל שיטה אחרת
            self._ws_send_method = getattr(ws, 'send_text', lambda x: print(f"❌ No send method: {x}"))
        
        # 🛡️ Safe WebSocket send wrapper with connection health
        self.ws_connection_failed = False
        self.failed_send_count = 0
        
        def _safe_ws_send(data):
            if self.ws_connection_failed:
                return False  # Don't spam when connection is dead
                
            try:
                self._ws_send_method(data)
                self.failed_send_count = 0  # Reset on success
                return True
            except Exception as e:
                self.failed_send_count += 1
                if self.failed_send_count <= 3:  # Only log first 3 errors
                    print(f"❌ WebSocket send error #{self.failed_send_count}: {e}")
                
                if self.failed_send_count >= 10:  # Increased threshold - After 10 failures, mark as dead
                    self.ws_connection_failed = True
                    print(f"🚨 WebSocket connection marked as FAILED after {self.failed_send_count} attempts")
                
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
        # 🔥 BUILD 171: STRICTER noise thresholds to prevent hallucinations
        self.noise_floor = 50.0          # 🔥 BUILD 171: 50 (was 30) - higher baseline
        self.vad_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 171: Now 120 (was 60) - require real speech
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
        # 🔥 BUILD 181: Increased to 1500 frames (~30s buffer) to handle OpenAI delays
        # OpenAI Realtime can delay 10-15+ seconds during long text generation
        self.tx_q = queue.Queue(maxsize=1500)  # Support up to 30s without drops
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._last_overflow_log = 0.0  # For throttled logging
        self._audio_gap_recovery_active = False  # 🔥 BUILD 181: Gap recovery state
        
        print("🎯 AI CONVERSATION STARTED")
        
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
        self.min_ai_talk_guard_ms = 150  # 🔥 BUILD 164B: 150ms grace period
        self.barge_in_rms_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 170.3: RMS > 60 now (was 200) - better barge-in
        self.min_voice_duration_ms = MIN_SPEECH_DURATION_MS  # 🔥 BUILD 164B: 220ms continuous speech
        self.barge_in_min_ms = MIN_SPEECH_DURATION_MS  # 🔥 BUILD 164B: Match min_voice_duration_ms
        self.barge_in_cooldown_ms = 500  # 🔥 BUILD 164B: Standard cooldown
        self.last_barge_in_ts = None  # Last time barge-in was triggered
        self.current_user_voice_start_ts = None  # When current user voice started
        self.barge_in_voice_frames = 0  # 🎯 NEW: Count continuous voice frames for 180ms detection
        self.barge_in_enabled_after_greeting = False  # 🎯 FIX: Allow barge-in after greeting without forcing user_has_spoken
        
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
        self._cancelled_response_recovery_delay_sec = 0.8  # Wait 800ms after speech stops before recovery
        self._response_created_ts = 0  # 🔥 BUILD 187: Track when response was created for grace period
        
        # 🔥 BUILD 302: HARD BARGE-IN - When user speaks over AI, we hard-cancel everything
        # During barge-in, ALL audio gates are bypassed so user's full utterance goes through
        self.barge_in_active = False
        self._barge_in_started_ts = None  # When barge-in started (for timeout)
        
        # 🔥 BUILD 303: GREETING FLOW MANAGEMENT - Wait for user answer to greeting question
        # Ensures we don't skip to next question before processing user's response to greeting
        self.awaiting_greeting_answer = False  # True after greeting ends, until first utterance is processed
        self.first_post_greeting_utterance_handled = False  # True after we processed first utterance post-greeting
        self.user_utterance_count = 0  # Count total user utterances in this call (for patience with early STT)
        
        # 🔥 BUILD 303: NEGATIVE ANSWER DETECTION - Don't skip questions when user says "no"
        self.last_ai_question_type = None  # Track what AI asked: 'city', 'service', 'confirmation', etc.
        
        # 🔥 BUILD 303: SMART HANGUP - Always send goodbye before disconnect
        self.goodbye_message_sent = False  # Track if we sent a proper goodbye
        
        # 🔥 BUILD 200: SINGLE PIPELINE LOCKDOWN - Stats for monitoring
        self._stats_audio_sent = 0  # Total audio chunks sent to OpenAI
        self._stats_audio_blocked = 0  # Total audio chunks blocked (greeting, etc.)
        self._stats_last_log_ts = 0  # Last time we logged pipeline status
        self._stats_log_interval_sec = 3.0  # Log every 3 seconds
        
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
        
        # 🔥 BUILD 172 SINGLE SOURCE OF TRUTH: Call behavior settings
        # DEFAULTS only - overwritten by load_call_config(business_id) when business is identified
        # Do NOT modify these directly - always use self.call_config for the authoritative values
        self.bot_speaks_first = False  # Default: wait for user - overwritten by CallConfig
        self.auto_end_after_lead_capture = False  # Default: don't auto-end - overwritten by CallConfig
        self.auto_end_on_goodbye = False  # Default: don't auto-end - overwritten by CallConfig
        self.lead_captured = False  # Runtime state: tracks if all required lead info is collected
        self.goodbye_detected = False  # Runtime state: tracks if goodbye phrase detected
        self.pending_hangup = False  # Runtime state: signals that call should end after current TTS
        self.hangup_triggered = False  # Runtime state: prevents multiple hangup attempts
        self.greeting_completed_at = None  # Runtime state: timestamp when greeting finished
        self.min_call_duration_after_greeting_ms = 3000  # Fixed: don't hangup for 3s after greeting
        self.silence_timeout_sec = 15  # Default - overwritten by CallConfig
        self.silence_max_warnings = 2  # Default - overwritten by CallConfig
        self.smart_hangup_enabled = True  # Default - overwritten by CallConfig
        self.required_lead_fields = ['name', 'phone']  # Default - overwritten by CallConfig
        # 🔥 BUILD 309: SIMPLE_MODE settings
        self.call_goal = 'lead_only'  # Default - "lead_only" or "appointment"
        self.confirm_before_hangup = True  # Default - Always confirm before disconnecting
        # 🎯 DYNAMIC LEAD CAPTURE STATE: Tracks ALL captured fields from conversation
        # Updated by _update_lead_capture_state() from AI responses and DTMF
        self.lead_capture_state = {}  # e.g., {'name': 'דני', 'city': 'תל אביב', 'service_type': 'ניקיון'}
        
        # 🔥 BUILD 185: STT CONSISTENCY FILTER - Tracks last 3 attempts for majority voting
        # Prevents hallucinations like "בית שמש" → "מצפה רמון" by locking after 2/3 match
        from server.services.phonetic_validator import ConsistencyFilter
        self.stt_consistency_filter = ConsistencyFilter(max_attempts=3)
        self.city_raw_attempts = []  # Track raw STT attempts for webhook
        self.name_raw_attempts = []  # Track raw STT attempts for webhook
        self._last_ai_mentioned_city = None  # 🔥 BUILD 307: Track city from AI confirmation for user "נכון" locking
        
        # 🛡️ BUILD 168: VERIFICATION GATE - Only disconnect after user confirms
        # Set to True when user says confirmation words: "כן", "נכון", "בדיוק", "כן כן"
        self.verification_confirmed = False  # Must be True before AI-triggered hangup is allowed
        self._verification_prompt_sent = False  # Tracks if we already asked for verification
        self._silence_final_chance_given = False  # Tracks if we gave extra chance before silence hangup
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

    def _init_streaming_stt(self):
        """
        ⚡ BUILD 114: Initialize streaming STT with retry mechanism
        3 attempts before falling back to single-request mode
        """
        if not USE_STREAMING_STT or not self.call_sid:
            return
        
        from server.services.gcp_stt_stream import StreamingSTTSession
        
        # ⚡ RETRY MECHANISM: 3 attempts before fallback
        for attempt in range(3):
            try:
                # Create dispatcher callbacks for this specific call
                on_partial, on_final = _create_dispatcher_callbacks(self.call_sid)
                
                # Create session
                session = StreamingSTTSession(
                    on_partial=on_partial,
                    on_final=on_final
                )
                
                # Register in thread-safe registry
                _register_session(self.call_sid, session, tenant_id=self.business_id)
                
                self.s1_stream_opened = time.time()  # ⚡ [S1] STT stream opened
                if DEBUG: print(f"✅ [S1={self.s1_stream_opened:.3f}] Streaming session started for call {self.call_sid[:8]}... (business: {self.business_id}, attempt: {attempt+1}, Δ={(self.s1_stream_opened - self.t0_connected)*1000:.0f}ms from T0)")
                return  # Success!
                
            except RuntimeError as e:
                if DEBUG: print(f"🚨 [STT] Over capacity (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(0.2)  # Brief delay before retry
                    continue
                # Don't crash - will use fallback STT
                return
                
            except Exception as e:
                if DEBUG: print(f"⚠️ [STT] Streaming start failed (attempt {attempt+1}/3): {e}", flush=True)
                if attempt < 2:
                    time.sleep(0.2)  # Brief delay before retry
                    continue
                if DEBUG:
                    import traceback
                    traceback.print_exc()
                return
        
        # If we get here, all 3 attempts failed
        if DEBUG: print(f"❌ [STT] All streaming attempts failed for call {self.call_sid[:8]} → using fallback single request", flush=True)
    
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
            
            if DEBUG: print(f"🎤 [{self.call_sid[:8]}] Utterance {utt_state['id']} BEGIN")
    
    def _utterance_end(self, timeout=0.850):
        """
        Mark end of utterance.
        ⚡ BUILD 118: Increased timeout to 850ms - streaming STT needs time for final results
        """
        if not self.call_sid:
            print("⚠️ _utterance_end: No call_sid")
            return ""
        
        utt_state = _get_utterance_state(self.call_sid)
        if utt_state is None:
            print(f"⚠️ _utterance_end: No utterance state for call {self.call_sid[:8]}")
            return ""
        
        utt_id = utt_state.get("id", "???")
        print(f"🎤 [{self.call_sid[:8]}] _utterance_end: Collecting results for utterance {utt_id} (timeout={timeout}s)")
        
        # ⚡ BUILD 118: Wait 850ms for streaming results - allows time for final transcription
        # Streaming STT enabled by default → fast partial results
        wait_start = time.time()
        wait_duration = 0.0
        final_event = utt_state.get("final_received")
        if final_event:
            got_final = final_event.wait(timeout=timeout)  # 850ms wait for streaming
            wait_duration = time.time() - wait_start
            if got_final:
                print(f"✅ [{self.call_sid[:8]}] Got final event in {wait_duration:.3f}s")
            else:
                print(f"⚠️ [{self.call_sid[:8]}] Timeout after {wait_duration:.3f}s - using fallback")  
        
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
                print(f"✅ [{self.call_sid[:8]}] Using partial: '{text[:50]}...' ({len(text)} chars)")
            elif finals_text:
                text = finals_text
                print(f"✅ [{self.call_sid[:8]}] Using final: '{text[:50]}...' ({len(text)} chars)")
            else:
                text = ""
                print(f"⚠️ [{self.call_sid[:8]}] No text available - returning empty")
            
            # Reset dispatcher
            utt_state["id"] = None
            utt_state["partial_cb"] = None
            utt_state["final_buf"] = None
            utt_state["final_received"] = None
            utt_state["last_partial"] = ""
        
        # ⚡ BUILD 114: Detailed latency logging
        print(f"🏁 [{self.call_sid[:8]}] Utterance {utt_id} COMPLETE: returning '{text[:30] if text else '(empty)'}'")
        print(f"[LATENCY] final_wait={wait_duration:.2f}s, utterance_total={time.time() - wait_start:.2f}s")
        
        return text

    def _set_safe_business_defaults(self, force_greeting=False):
        """🔥 SAFETY: Set ONLY MISSING fields with safe defaults. Never overwrite valid data."""
        # Only set if attribute doesn't exist or is explicitly None
        if not hasattr(self, 'business_id') or self.business_id is None:
            self.business_id = 1
            print(f"🔒 [DEFAULTS] Set fallback business_id=1")
        if not hasattr(self, 'business_name') or self.business_name is None:
            self.business_name = "העסק"
        if not hasattr(self, 'bot_speaks_first'):
            self.bot_speaks_first = True
        if not hasattr(self, 'auto_end_after_lead_capture'):
            self.auto_end_after_lead_capture = False
        if not hasattr(self, 'auto_end_on_goodbye'):
            self.auto_end_on_goodbye = False
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
            print(f"🔒 [DEFAULTS] Created fallback CallConfig for business={self.business_id}")
        
        # Force bot_speaks_first on error/timeout paths
        if force_greeting:
            self.bot_speaks_first = True
            print(f"🔒 [DEFAULTS] Forced bot_speaks_first=True for greeting")

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
        """
        call_id = self.call_sid[:8] if self.call_sid else "unknown"
        
        _orig_print(f"🚀 [REALTIME] Thread started for call {call_id} (FRESH SESSION)", flush=True)
        logger.info(f"[CALL DEBUG] Realtime thread started for call {call_id}")
        
        try:
            asyncio.run(self._run_realtime_mode_async())
        except Exception as e:
            print(f"❌ [REALTIME] Thread error: {e}")
            logger.error(f"[CALL DEBUG] Realtime thread error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"🔚 [REALTIME] Thread ended for call {call_id}")
            logger.info(f"[CALL DEBUG] Realtime thread ended for call {call_id}")
    
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
        from server.services.realtime_prompt_builder import build_realtime_system_prompt
        
        _orig_print(f"🚀 [REALTIME] Async loop starting - connecting to OpenAI IMMEDIATELY", flush=True)
        
        client = None
        call_start_time = time.time()
        
        self.realtime_audio_in_chunks = 0
        self.realtime_audio_out_chunks = 0
        self._user_speech_start = None
        self._ai_speech_start = None
        
        try:
            t_start = time.time()
            
            # 🚀 PARALLEL STEP 1: Connect to OpenAI IMMEDIATELY (don't wait for DB!)
            logger.info(f"[CALL DEBUG] Creating OpenAI client with model={OPENAI_REALTIME_MODEL}")
            client = OpenAIRealtimeClient(model=OPENAI_REALTIME_MODEL)
            t_client = time.time()
            if DEBUG: print(f"⏱️ [PARALLEL] Client created in {(t_client-t_start)*1000:.0f}ms")
            
            t_connect_start = time.time()
            await client.connect()
            connect_ms = (time.time() - t_connect_start) * 1000
            t_connected = time.time()
            if DEBUG: print(f"⏱️ [PARALLEL] OpenAI connected in {connect_ms:.0f}ms (T0+{(t_connected-self.t0_connected)*1000:.0f}ms)")
            
            self.realtime_client = client
            
            is_mini = "mini" in OPENAI_REALTIME_MODEL.lower()
            cost_info = "MINI (80% cheaper)" if is_mini else "STANDARD"
            logger.info("[REALTIME] Connected")
            
            # 🚀 PARALLEL STEP 2: Wait for business info from main thread (max 2s)
            print(f"⏳ [PARALLEL] Waiting for business info from DB query...")
            
            # Use asyncio to wait for the threading.Event
            loop = asyncio.get_event_loop()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self.business_info_ready_event.wait(2.0)),
                    timeout=3.0
                )
                t_ready = time.time()
                wait_ms = (t_ready - t_connected) * 1000
                print(f"✅ [PARALLEL] Business info ready! Wait time: {wait_ms:.0f}ms")
            except asyncio.TimeoutError:
                print(f"⚠️ [PARALLEL] Timeout waiting for business info - using defaults")
                # Use helper with force_greeting=True to ensure greeting fires
                self._set_safe_business_defaults(force_greeting=True)
            
            # Now we have business info - get the greeting
            t_before_greeting = time.time()
            greeting_text = getattr(self, 'greeting_text', None)
            biz_name = getattr(self, 'business_name', None) or "העסק"
            # business_id should be set by now (either from DB or defaults)
            business_id_safe = self.business_id if self.business_id is not None else 1
            
            # 🔥 BUILD 178: Check for outbound call - use personalized greeting!
            call_direction = getattr(self, 'call_direction', 'inbound')
            outbound_lead_name = getattr(self, 'outbound_lead_name', None)
            
            if call_direction == 'outbound' and outbound_lead_name:
                # 🎯 OUTBOUND CALL: Use personalized greeting with lead's name
                print(f"📤 [OUTBOUND GREETING] Building greeting for lead: {outbound_lead_name}")
                
                # 🔥 BUILD 182: Use greeting_template from outbound template if available
                outbound_greeting = None
                outbound_template_id = getattr(self, 'outbound_template_id', None)
                if outbound_template_id:
                    try:
                        from server.models_sql import OutboundTemplate
                        template = OutboundTemplate.query.get(outbound_template_id)
                        if template and template.greeting_template:
                            # Replace placeholders with actual values
                            outbound_greeting = template.greeting_template.replace("{{lead_name}}", outbound_lead_name).replace("{{business_name}}", biz_name)
                            print(f"📤 [OUTBOUND GREETING] Using template greeting: '{outbound_greeting[:50]}...'")
                    except Exception as e:
                        print(f"⚠️ [OUTBOUND GREETING] Failed to load template greeting: {e}")
                
                # Fallback to business greeting_message if no template
                if not outbound_greeting:
                    try:
                        from server.models_sql import Business
                        business = Business.query.get(self.business_id)
                        if business and business.greeting_message:
                            # Use greeting_message with lead name substitution
                            outbound_greeting = f"{outbound_lead_name}, " + business.greeting_message
                            print(f"📤 [OUTBOUND GREETING] Using business greeting_message")
                        else:
                            # Minimal fallback (just name + business name, no hardcoded script)
                            outbound_greeting = f"{outbound_lead_name}, {biz_name}"
                            print(f"📤 [OUTBOUND GREETING] Using minimal greeting (no configured template)")
                    except:
                        outbound_greeting = f"{outbound_lead_name}, {biz_name}"
                        print(f"📤 [OUTBOUND GREETING] Using minimal greeting (DB error)")
                
                greeting_prompt = f"""אתה נציג טלפוני של {biz_name}. עברית בלבד.

🎤 ברכה יוצאת (אמור בדיוק!):
"{outbound_greeting}"

זו שיחה יוצאת - אתה מתקשר ללקוח, לא הוא התקשר אליך.
חוקים:
- קצר מאוד (1-2 משפטים)
- המתן לתשובת הלקוח
- אם הלקוח אמר משהו לא ברור או לא קשור - בקש הבהרה: "סליחה, לא שמעתי טוב. במה אוכל לעזור?"
- לא לקפוץ למסקנות לפני שהלקוח ביקש במפורש!"""
                has_custom_greeting = True  # Treat as custom greeting for token calculation
            else:
                # INBOUND CALL: Use regular greeting logic
                has_custom_greeting = greeting_text is not None and len(str(greeting_text).strip()) > 0
                
                if has_custom_greeting:
                    if DEBUG: print(f"⏱️ [PARALLEL] Using greeting: '{greeting_text[:50]}...'")
                else:
                    if DEBUG: print(f"⏱️ [PARALLEL] No custom greeting - AI will improvise (biz='{biz_name}')")
                
                # Build greeting-only prompt with the actual greeting (or improvise instruction)
                # 🔥 BUILD 186: Added contextual coherence rule to prevent hallucination responses
                if has_custom_greeting:
                    greeting_prompt = f"""אתה נציג טלפוני של {biz_name}. עברית בלבד.

🎤 ברכה (אמור בדיוק!):
"{greeting_text}"

חוקים:
- קצר מאוד (1-2 משפטים)
- אם הלקוח שותק - שתוק
- אם הלקוח אמר משהו לא ברור או לא קשור (כמו "תודה" אחרי "איך אוכל לעזור?") - שאל: "במה אוכל לעזור?"
- לא לקפוץ לתהליך קביעת תור עד שהלקוח ביקש במפורש!"""
                else:
                    # No custom greeting - AI should improvise a brief intro
                    greeting_prompt = f"""אתה נציג טלפוני של {biz_name}. עברית בלבד.

🎤 פתיחה: הזדהה בקצרה כנציג של {biz_name} ושאל במה תוכל לעזור.

חוקים:
- קצר מאוד (1-2 משפטים)
- אם הלקוח שותק - שתוק
- אם הלקוח אמר משהו לא ברור או לא קשור - שאל: "במה אוכל לעזור?"
- לא לקפוץ לתהליך קביעת תור עד שהלקוח ביקש במפורש!"""
            
            t_before_config = time.time()
            logger.info(f"[CALL DEBUG] PHASE 1: Configure with greeting prompt...")
            
            # 🎯 VOICE CONSISTENCY: Set voice once at call start, use same voice throughout
            # 🔥 BUILD 304: Changed to 'ash' - conversational male, lower pitch, no jumps
            # User reported coral was too high-pitched and had voice jumps
            # 'ash' = calm conversational male, better for professional calls
            call_voice = "ash"
            self._call_voice = call_voice  # Store for session.update reuse
            print(f"🎤 [VOICE] Using voice={call_voice} for entire call (business={self.business_id})")
            
            # 🔥 FIX: Calculate max_tokens based on greeting length
            # Long greetings (14 seconds = ~280 words in Hebrew) need 500+ tokens
            # 🔥 BUILD 178: For outbound calls, use greeting_prompt length instead of greeting_text
            # 🔥 BUILD 179: Outbound calls need MUCH higher token limits for sales pitches!
            if call_direction == 'outbound':
                greeting_length = len(greeting_prompt) if greeting_prompt else 100
            else:
                greeting_length = len(greeting_text) if (has_custom_greeting and greeting_text) else 0
            
            # 🔥 BUILD 179: max_tokens=4096 for ALL calls (both inbound and outbound)
            # This prevents AI from being cut off mid-sentence
            greeting_max_tokens = 4096
            print(f"🎤 [GREETING] max_tokens={greeting_max_tokens} for greeting length={greeting_length} chars (direction={call_direction})")
            
            # 🔥 BUILD 202: Build MINIMAL transcription prompt for Hebrew STT
            # Keep it short and focused - context + rules, NOT long vocab lists
            # OpenAI docs: prompts should be brief context hints, not dictionaries
            transcription_prompt = ""
            try:
                from server.models_sql import Business, BusinessSettings
                app = _get_flask_app()
                with app.app_context():
                    # 🔥 BUILD 204: Use dynamic STT service for vocabulary-aware transcription prompt
                    try:
                        from server.services.dynamic_stt_service import build_dynamic_stt_prompt
                        transcription_prompt = build_dynamic_stt_prompt(business_id_safe)
                        self._last_stt_prompt = transcription_prompt  # Store for logging
                        print(f"🎤 [BUILD 204] Dynamic STT prompt: '{transcription_prompt}' ({len(transcription_prompt)} chars)")
                    except Exception as stt_err:
                        # Fallback to simpler prompt if dynamic service fails
                        business = Business.query.get(business_id_safe)
                        biz_name_prompt = business.name if business and business.name else "עסק"
                        transcription_prompt = f"שיחה עברית לעסק {biz_name_prompt}. העדף עברית."
                        print(f"⚠️ [BUILD 204] Fallback STT prompt: {stt_err}")
                    
            except Exception as e:
                print(f"⚠️ [BUILD 202] Failed to build transcription prompt: {e}")
                transcription_prompt = "שיחה עברית. תמלל שמות, שעות, מספרים. העדף עברית."
            
            # 🔥 BUILD 206: TELEPHONY-OPTIMIZED VAD settings (expert recommendations)
            # vad_threshold=0.85 - High but not too aggressive (allows soft Hebrew speakers)
            # silence_duration_ms=450 - Sweet spot for telephony (300-500ms range)
            # 🔥 BUILD 200 FIX: Removed prefix_padding_ms - not supported by SDK!
            # 🔥 BUILD 202: Use gpt-4o-transcribe model + dynamic transcription prompt
            await client.configure_session(
                instructions=greeting_prompt,
                voice=call_voice,
                input_audio_format="g711_ulaw",
                output_audio_format="g711_ulaw",
                vad_threshold=0.85,        # 🔥 BUILD 206: 0.85 (was 0.9) - balanced for Hebrew telephony
                silence_duration_ms=450,   # 🔥 BUILD 206: 450ms (was 900) - telephony sweet spot!
                temperature=0.6,           # 🔒 Consistent, focused responses
                max_tokens=greeting_max_tokens,  # 🔥 Dynamic based on greeting length!
                transcription_prompt=transcription_prompt  # 🔥 BUILD 202: Dynamic vocab for Hebrew STT
            )
            t_after_config = time.time()
            config_ms = (t_after_config - t_before_config) * 1000
            total_ms = (t_after_config - t_start) * 1000
            print(f"⏱️ [PHASE 1] Session configured in {config_ms:.0f}ms (total: {total_ms:.0f}ms)")
            print(f"✅ [REALTIME] FAST CONFIG: greeting prompt ready, voice={call_voice}")
            
            # 🚀 Start audio/text bridges FIRST (before CRM)
            audio_in_task = asyncio.create_task(self._realtime_audio_sender(client))
            audio_out_task = asyncio.create_task(self._realtime_audio_receiver(client))
            text_in_task = asyncio.create_task(self._realtime_text_sender(client))
            
            # 🎯 BUILD 163 SPEED FIX: Bot speaks first - trigger IMMEDIATELY after session config
            # No waiting for CRM, no 0.2s delay - just speak!
            if self.bot_speaks_first:
                greeting_start_ts = time.time()
                print(f"🎤 [GREETING] Bot speaks first - triggering greeting at {greeting_start_ts:.3f}")
                self.greeting_sent = True  # Mark greeting as sent to allow audio through
                self.is_playing_greeting = True
                self._greeting_start_ts = greeting_start_ts  # Store for duration logging
                # 🔥 BUILD 200: Use trigger_response for greeting (with is_greeting=True to skip loop guard)
                triggered = await self.trigger_response("GREETING", client, is_greeting=True)
                if triggered:
                    t_speak = time.time()
                    total_openai_ms = (t_speak - t_start) * 1000
                    print(f"🎯 [BUILD 200] GREETING response.create sent! OpenAI time: {total_openai_ms:.0f}ms")
                else:
                    print(f"❌ [BUILD 200] Failed to trigger greeting via trigger_response")
                    # Reset flags since greeting failed
                    self.greeting_sent = False
                    self.is_playing_greeting = False
            else:
                # Standard flow - AI waits for user speech first
                print(f"ℹ️ [BUILD 163] Bot speaks first disabled - waiting for user speech")
                
                # 🔥 BUILD 172: Start warmup timer - transition to ACTIVE after 800ms
                async def warmup_to_active():
                    await asyncio.sleep(0.8)  # 800ms warmup
                    if self.call_state == CallState.WARMUP and not self.hangup_triggered:
                        self.call_state = CallState.ACTIVE
                        print(f"📞 [STATE] Transitioned WARMUP → ACTIVE (800ms timer)")
                        await self._start_silence_monitor()
                
                asyncio.create_task(warmup_to_active())
            
            # 🚀 PHASE 2: Build full prompt in background and update session
            # 🔥 CRITICAL FIX: Wait for greeting to FINISH before sending session.update!
            # Sending session.update during greeting causes OpenAI to abort the greeting mid-sentence.
            async def _update_session_with_full_prompt():
                try:
                    loop = asyncio.get_event_loop()
                    
                    def _build_in_thread():
                        try:
                            from server.services.realtime_prompt_builder import build_realtime_system_prompt as build_prompt
                            app = _get_flask_app()
                            with app.app_context():
                                # 🔥 BUILD 174: Check for outbound call with custom template
                                call_direction = getattr(self, 'call_direction', 'inbound')
                                outbound_template_id = getattr(self, 'outbound_template_id', None)
                                outbound_lead_name = getattr(self, 'outbound_lead_name', None)
                                outbound_business_name = getattr(self, 'outbound_business_name', None)
                                
                                # 🔥 BUILD 174: Use dedicated outbound_ai_prompt from BusinessSettings
                                # The prompt builder now handles outbound vs inbound prompts!
                                prompt = build_prompt(business_id_safe, call_direction=call_direction)
                                
                                # 🔥 BUILD 177/182: For outbound calls, add personalized greeting with lead name
                                if call_direction == 'outbound' and outbound_lead_name:
                                    # 🔥 BUILD 182: Get greeting from template if available
                                    custom_greeting = None
                                    if outbound_template_id:
                                        try:
                                            from server.models_sql import OutboundTemplate
                                            tmpl = OutboundTemplate.query.get(outbound_template_id)
                                            if tmpl and tmpl.greeting_template:
                                                custom_greeting = tmpl.greeting_template.replace("{{lead_name}}", outbound_lead_name).replace("{{business_name}}", outbound_business_name or "")
                                        except:
                                            pass
                                    
                                    # Fallback to business greeting or minimal greeting
                                    if not custom_greeting:
                                        try:
                                            from server.models_sql import Business
                                            biz = Business.query.get(business_id_safe)
                                            if biz and biz.greeting_message:
                                                custom_greeting = f"{outbound_lead_name}, " + biz.greeting_message
                                            else:
                                                custom_greeting = f"{outbound_lead_name}, {outbound_business_name or ''}"
                                        except:
                                            custom_greeting = f"{outbound_lead_name}, {outbound_business_name or ''}"
                                    
                                    # Add lead-specific context and greeting instruction at the START
                                    lead_greeting_context = f"""🎯 OUTBOUND CALL - CRITICAL INSTRUCTIONS:
You are CALLING the customer, not receiving a call.
The customer's name is: {outbound_lead_name}

FIRST MESSAGE (MANDATORY):
Start with a personalized greeting using the customer's name:
"{custom_greeting}"

NEVER use generic greetings without the customer's name.
ALWAYS mention their name in the first sentence.

---

"""
                                    prompt = lead_greeting_context + prompt
                                    print(f"📤 [OUTBOUND] Using outbound prompt with greeting for: {outbound_lead_name}")
                                
                                if prompt and len(prompt) > 100:
                                    return prompt
                                return None
                        except Exception as e:
                            print(f"⚠️ [PHASE 2] Prompt build failed: {e}")
                            return None
                    
                    full_prompt = await loop.run_in_executor(None, _build_in_thread)
                    
                    if full_prompt:
                        # 🔥 CRITICAL: Wait for greeting to FINISH before session.update
                        # The previous 0.5s wait was causing greeting truncation!
                        wait_start = time.time()
                        max_wait_seconds = 15  # Max 15 seconds for greeting
                        check_interval = 0.2  # Check every 200ms
                        
                        print(f"⏳ [PHASE 2] Waiting for greeting to finish before session.update...")
                        
                        while self.is_playing_greeting and (time.time() - wait_start) < max_wait_seconds:
                            await asyncio.sleep(check_interval)
                        
                        wait_duration = time.time() - wait_start
                        if self.is_playing_greeting:
                            print(f"⚠️ [PHASE 2] Greeting still playing after {wait_duration:.1f}s - proceeding anyway")
                        else:
                            print(f"✅ [PHASE 2] Greeting finished after {wait_duration:.1f}s - now updating session")
                        
                        # Add small buffer after greeting ends to ensure clean transition
                        await asyncio.sleep(0.3)
                        
                        # Update session with full prompt (session.update event)
                        # 🎯 VOICE CONSISTENCY: Explicitly re-send voice to ensure it doesn't reset
                        voice_to_use = getattr(self, '_call_voice', 'coral')
                        
                        # 🔥 BUILD 179: max_tokens=4096 for BOTH inbound and outbound
                        # This prevents AI from being cut off mid-sentence
                        session_max_tokens = 4096
                        current_call_direction = getattr(self, 'call_direction', 'inbound')
                        print(f"📞 [{current_call_direction.upper()}] session.update with max_tokens={session_max_tokens}")
                        
                        # 🔥 BUILD 204: CRITICAL - Preserve Hebrew transcription config with gpt-4o-transcribe!
                        # Without this, STT defaults to English and transcribes Hebrew as "Thank you", "Good luck"
                        
                        # 🔥 BUILD 204: Rebuild dynamic STT prompt for session.update
                        stt_prompt_for_update = ""
                        try:
                            from server.services.dynamic_stt_service import build_dynamic_stt_prompt
                            app_for_stt = _get_flask_app()
                            with app_for_stt.app_context():
                                stt_prompt_for_update = build_dynamic_stt_prompt(business_id_safe)
                        except Exception as stt_err:
                            print(f"⚠️ [BUILD 204] Could not rebuild STT prompt for session.update: {stt_err}")
                        
                        # Build transcription config with gpt-4o-transcribe (better than whisper-1)
                        transcription_config = {
                            "model": "gpt-4o-transcribe",  # 🔥 BUILD 204: Best model for Hebrew!
                            "language": "he"  # 🔒 Force Hebrew - prevents "Thank you" hallucinations
                        }
                        if stt_prompt_for_update:
                            transcription_config["prompt"] = stt_prompt_for_update
                        
                        await client.send_event({
                            "type": "session.update",
                            "session": {
                                "instructions": full_prompt,
                                "voice": voice_to_use,  # 🔒 Must re-send voice to lock it
                                "max_response_output_tokens": session_max_tokens,
                                "input_audio_transcription": transcription_config
                            }
                        })
                        print(f"✅ [PHASE 2] Session updated: {len(full_prompt)} chars, voice={voice_to_use}, max_tokens={session_max_tokens}, stt=gpt-4o-transcribe+Hebrew")
                    else:
                        print(f"⚠️ [PHASE 2] Keeping minimal prompt - full prompt build failed")
                except Exception as e:
                    print(f"⚠️ [PHASE 2] Session update error: {e}")
            
            # Start prompt update in background (non-blocking)
            asyncio.create_task(_update_session_with_full_prompt())
            
            # 📋 CRM: Initialize context in background (non-blocking for voice)
            # This runs in background thread while AI is already speaking
            customer_phone = getattr(self, 'phone_number', None) or getattr(self, 'customer_phone_dtmf', None)
            
            # 🔥 BUILD 174: For outbound calls, use the pre-existing lead_id
            outbound_lead_id = getattr(self, 'outbound_lead_id', None)
            call_direction = getattr(self, 'call_direction', 'inbound')
            
            if customer_phone or outbound_lead_id:
                # 🚀 Run CRM init in background thread to not block audio
                def _init_crm_background():
                    try:
                        app = _get_flask_app()
                        with app.app_context():
                            # 🔥 BUILD 174: Use existing lead_id for outbound calls
                            if call_direction == 'outbound' and outbound_lead_id:
                                lead_id = int(outbound_lead_id)
                                print(f"📤 [OUTBOUND CRM] Using existing lead_id={lead_id}")
                            else:
                                lead_id = ensure_lead(business_id_safe, customer_phone)
                            
                            self.crm_context = CallCrmContext(
                                business_id=business_id_safe,
                                customer_phone=customer_phone,
                                lead_id=lead_id
                            )
                            # 🔥 HYDRATION: Transfer pending customer name
                            if hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                                self.crm_context.customer_name = self.pending_customer_name
                                self.pending_customer_name = None
                            print(f"✅ [CRM] Context ready (background): lead_id={lead_id}, direction={call_direction}")
                    except Exception as e:
                        print(f"⚠️ [CRM] Background init failed: {e}")
                        self.crm_context = None
                threading.Thread(target=_init_crm_background, daemon=True).start()
            else:
                print(f"⚠️ [CRM] No customer phone or lead_id - skipping lead creation")
                self.crm_context = None
            
            await asyncio.gather(audio_in_task, audio_out_task, text_in_task)
            
        except Exception as e:
            print(f"❌ [REALTIME] Async error: {e}")
            logger.error(f"[CALL DEBUG] ❌ Realtime async error: {e}")
            import traceback
            tb_str = traceback.format_exc()
            traceback.print_exc()
            logger.error(f"[CALL DEBUG] Traceback: {tb_str}")
        finally:
            # 💰 COST TRACKING: Use centralized cost calculation
            self._calculate_and_log_cost()
            
            if client:
                await client.disconnect()
                print(f"🔌 [REALTIME] Disconnected")
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
        print(f"[PIPELINE] LIVE AUDIO PIPELINE ACTIVE: Twilio → realtime_audio_in_queue → send_audio_chunk (single path)")
        
        # 🛡️ BUILD 168.5: Track if we've logged the greeting block message
        _greeting_block_logged = False
        _greeting_resumed_logged = False
        
        while not self.realtime_stop_flag:
            try:
                if not hasattr(self, 'realtime_audio_in_queue'):
                    await asyncio.sleep(0.01)
                    continue
                
                try:
                    audio_chunk = self.realtime_audio_in_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                
                if audio_chunk is None:
                    print(f"📤 [REALTIME] Stop signal received")
                    break
                
                # 🛡️ BUILD 168.5 FIX: Block audio input during greeting to prevent turn_detected cancellation!
                # OpenAI's server-side VAD detects incoming audio as "user speech" and cancels the greeting.
                # Solution: Don't send audio to OpenAI until greeting finishes playing.
                if self.is_playing_greeting:
                    if not _greeting_block_logged:
                        print(f"🛡️ [GREETING PROTECT] Blocking audio input to OpenAI - greeting in progress")
                        _greeting_block_logged = True
                    # 🔥 BUILD 200: Track blocked audio stats
                    self._stats_audio_blocked += 1
                    # Drop the audio chunk - don't send to OpenAI during greeting
                    continue
                else:
                    # Greeting finished - resume sending audio
                    if _greeting_block_logged and not _greeting_resumed_logged:
                        print(f"✅ [GREETING PROTECT] Greeting done - resuming audio to OpenAI")
                        _greeting_resumed_logged = True
                
                # 💰 COST TRACKING: Count user audio chunks being sent to OpenAI
                # Start timer on first chunk
                if not hasattr(self, '_user_speech_start') or self._user_speech_start is None:
                    self._user_speech_start = time.time()
                self.realtime_audio_in_chunks += 1
                
                # 🔥 BUILD 200: Track audio sent stats
                self._stats_audio_sent += 1
                
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
                            print(f"🔧 [BUILD 301] STUCK RESPONSE DETECTED! Clearing active_response_id after {response_age:.1f}s")
                            print(f"   Was: {self.active_response_id[:20]}...")
                            self.active_response_id = None
                            self.response_pending_event.clear()
                            self.is_ai_speaking_event.clear()
                            self._stuck_check_first_seen_ts = None  # Reset for next response
                            print(f"   ✅ Response guards cleared - AI can respond again")
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
                                print(f"🔧 [BUILD 302] BARGE-IN TIMEOUT! Clearing after {barge_age:.1f}s (speech_stopped never received)")
                                self.barge_in_active = False
                                self._barge_in_started_ts = None
                    
                    print(
                        f"[PIPELINE STATUS] sent={self._stats_audio_sent} blocked={self._stats_audio_blocked} | "
                        f"active_response={self.active_response_id[:15] if self.active_response_id else 'None'}... | "
                        f"ai_speaking={self.is_ai_speaking_event.is_set()} | barge_in={self.barge_in_active}"
                    )
                
            except Exception as e:
                print(f"❌ [REALTIME] Audio sender error: {e}")
                break
        
        print(f"📤 [REALTIME] Audio sender ended")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 BUILD 302: FLUSH TX QUEUE - Stop old audio from playing on barge-in
    # ═══════════════════════════════════════════════════════════════════════════════
    def _flush_twilio_tx_queue(self, reason: str = ""):
        """
        Flush all pending audio from the TX queue to Twilio.
        Called on barge-in to immediately stop AI audio playback.
        """
        queue_size_before = self.tx_q.qsize()
        flushed = 0
        try:
            while not self.tx_q.empty():
                _ = self.tx_q.get_nowait()
                flushed += 1
        except Exception:
            pass
        
        print(f"🧹 [TX_FLUSH] Flushed {flushed} frames (was {queue_size_before}, reason={reason or 'UNKNOWN'})")
        return flushed
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 BUILD 200: SINGLE RESPONSE TRIGGER - Central function for ALL response.create
    # ═══════════════════════════════════════════════════════════════════════════════
    async def trigger_response(self, reason: str, client=None, is_greeting: bool = False) -> bool:
        """
        🎯 BUILD 200: Central function for triggering response.create
        
        ALL response.create calls MUST go through this function!
        This ensures:
        1. Only ONE response is active at a time
        2. Proper lifecycle tracking of active_response_id
        3. Loop guard protection
        4. Consistent logging
        
        Args:
            reason: Why we're creating a response (for logging)
            client: The realtime client (uses self.realtime_client if not provided)
            is_greeting: If True, this is the initial greeting - skip loop guard (first response)
            
        Returns:
            True if response was triggered, False if blocked
        """
        # Use stored client if not provided
        _client = client or self.realtime_client
        if not _client:
            print(f"⚠️ [RESPONSE GUARD] No client available - cannot trigger ({reason})")
            return False
        
        # 🛡️ GUARD 0: BUILD 303 - Wait for first user utterance after greeting
        # Don't let AI auto-respond before user answers the greeting question
        if self.awaiting_greeting_answer and not is_greeting:
            print(f"⏸️ [RESPONSE GUARD] Waiting for first user utterance after greeting - skipping ({reason})")
            return False
        
        # 🛡️ GUARD 0.25: BUILD 310 - Block new AI responses when hangup is pending
        # Don't let AI start new conversation loops after call should end
        if getattr(self, 'pending_hangup', False):
            print(f"⏸️ [RESPONSE GUARD] Hangup pending - blocking new responses ({reason})")
            return False
        
        # 🛡️ GUARD 0.5: BUILD 308 - POST-REJECTION TRACKING
        # After user says "לא", city is cleared so AI will naturally ask for it again
        # No artificial delay - the city clearing is the main fix
        # AI will dynamically ask for whatever field is missing based on business settings
        if getattr(self, '_awaiting_user_correction', False):
            # Clear the flag - AI can respond (but city is empty so it will ask dynamically)
            self._awaiting_user_correction = False
            print(f"🔄 [BUILD 308] User rejected - city cleared, AI will ask dynamically")
        
        # 🛡️ GUARD 1: Check if response is already active
        if self.active_response_id is not None:
            print(f"⏸️ [RESPONSE GUARD] Active response in progress ({self.active_response_id[:20]}...) - skipping ({reason})")
            return False
        
        # 🛡️ GUARD 2: Check if response is pending (race condition prevention)
        if self.response_pending_event.is_set():
            print(f"⏸️ [RESPONSE GUARD] Response pending - skipping ({reason})")
            return False
        
        # 🛡️ GUARD 3: Loop guard check (inbound calls only, skip for greeting)
        if not is_greeting:
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if not is_outbound:
                if self._loop_guard_engaged:
                    print(f"🛑 [RESPONSE GUARD] Loop guard engaged - blocking ({reason})")
                    return False
                if self._consecutive_ai_responses >= self._max_consecutive_ai_responses:
                    print(f"🛑 [RESPONSE GUARD] Too many consecutive responses ({self._consecutive_ai_responses}) - blocking ({reason})")
                    return False
        
        # ✅ All guards passed - trigger response
        try:
            self.response_pending_event.set()  # 🔒 Lock BEFORE sending (thread-safe)
            await _client.send_event({"type": "response.create"})
            print(f"🎯 [BUILD 200] response.create triggered ({reason})")
            return True
        except Exception as e:
            # 🔓 CRITICAL: Clear lock immediately on failure
            self.response_pending_event.clear()
            print(f"❌ [RESPONSE GUARD] Failed to trigger ({reason}): {e}")
            return False
    
    async def _realtime_text_sender(self, client):
        """
        Send text input (e.g., DTMF) from queue to Realtime API
        ✅ Resilient: Retries on failure, never drops DTMF input silently
        """
        print(f"📝 [REALTIME] Text sender started")
        
        while not self.realtime_stop_flag:
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
                    print(f"📝 [REALTIME] Stop signal received")
                    break
                
                # ✅ Resilient send with retry
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        print(f"📝 [REALTIME] Sending user message (attempt {attempt+1}/{max_retries}): '{text_message[:50]}...'")
                        await client.send_user_message(text_message)
                        print(f"✅ [REALTIME] User message sent successfully")
                        break  # Success - exit retry loop
                    except Exception as send_error:
                        if attempt < max_retries - 1:
                            print(f"⚠️ [REALTIME] Send failed (attempt {attempt+1}), retrying: {send_error}")
                            await asyncio.sleep(0.1)  # Brief delay before retry
                        else:
                            # All retries exhausted - log critical error
                            print(f"❌ [REALTIME] CRITICAL: Failed to send DTMF input after {max_retries} attempts: {send_error}")
                            print(f"❌ [REALTIME] Lost message: '{text_message[:100]}'")
                            import traceback
                            traceback.print_exc()
                            # Don't re-raise - continue processing queue
                
            except Exception as e:
                print(f"❌ [REALTIME] Text sender error: {e}")
                import traceback
                traceback.print_exc()
                # Don't stop the loop - keep trying to process messages
        
        print(f"📝 [REALTIME] Text sender ended")
    
    async def _realtime_audio_receiver(self, client):
        """Receive audio and events from Realtime API"""
        print(f"📥 [REALTIME] Audio receiver started")
        
        try:
            async for event in client.recv_events():
                event_type = event.get("type", "")
                
                # 🔥 DEBUG BUILD 168.5: Log ALL events to diagnose missing audio
                if event_type.startswith("response."):
                    # Log all response-related events with details
                    if event_type == "response.audio.delta":
                        delta = event.get("delta", "")
                        _orig_print(f"🔊 [REALTIME] response.audio.delta: {len(delta)} bytes", flush=True)
                    elif event_type == "response.done":
                        response = event.get("response", {})
                        status = response.get("status", "?")
                        output = response.get("output", [])
                        status_details = response.get("status_details", {})
                        _orig_print(f"🔊 [REALTIME] response.done: status={status}, output_count={len(output)}, details={status_details}", flush=True)
                        # Log output items to see if audio was included
                        for i, item in enumerate(output[:3]):  # First 3 items
                            item_type = item.get("type", "?")
                            content = item.get("content", [])
                            content_types = [c.get("type", "?") for c in content] if content else []
                            _orig_print(f"   output[{i}]: type={item_type}, content_types={content_types}", flush=True)
                        
                        # 🔥 BUILD 200: Clear active_response_id when response is done (completed or cancelled)
                        # This is the ONLY place where active_response_id should be cleared!
                        resp_id = response.get("id", "")
                        if resp_id and self.active_response_id == resp_id:
                            self.active_response_id = None
                            _orig_print(f"✅ [BUILD 200] Response lifecycle complete: {resp_id[:20]}... -> None (status={status})", flush=True)
                        elif self.active_response_id:
                            # Mismatch - log but still clear to prevent deadlock
                            _orig_print(f"⚠️ [BUILD 200] Response ID mismatch: active={self.active_response_id[:20] if self.active_response_id else 'None'}... done={resp_id[:20] if resp_id else 'None'}...", flush=True)
                            self.active_response_id = None
                        
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
                        
                        # 🔥 BUILD 187: RECOVERY for cancelled responses with NO audio!
                        # When user speaks/noise triggers turn_detected BEFORE AI sends any audio,
                        # the response gets cancelled and no new one is created = silence.
                        # Solution: Schedule a recovery response.create after short delay
                        if status == "cancelled" and len(output) == 0 and self.user_has_spoken:
                            _orig_print(f"🔄 [BUILD 187] Response cancelled with NO audio! Scheduling recovery...", flush=True)
                            self._cancelled_response_needs_recovery = True
                            self._cancelled_response_recovery_ts = time.time()
                    elif event_type == "response.created":
                        resp_id = event.get("response", {}).get("id", "?")
                        _orig_print(f"🔊 [REALTIME] response.created: id={resp_id[:20]}...", flush=True)
                    else:
                        _orig_print(f"🔊 [REALTIME] {event_type}", flush=True)
                
                # 🔥 DEBUG: Log errors and cancellations
                if event_type == "error":
                    error = event.get("error", {})
                    _orig_print(f"❌ [REALTIME] ERROR: {error}", flush=True)
                if event_type == "response.cancelled":
                    _orig_print(f"❌ [REALTIME] RESPONSE CANCELLED: {event}", flush=True)
                
                # 🚨 COST SAFETY: Log transcription failures but DO NOT retry
                if event_type == "conversation.item.input_audio_transcription.failed":
                    self.transcription_failed_count += 1
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    print(f"[SAFETY] Transcription failed (#{self.transcription_failed_count}): {error_msg}")
                    print(f"[SAFETY] NO RETRY - continuing conversation without transcription")
                    # ✅ Continue processing - don't retry, don't crash, just log and move on
                    continue
                
                # 🔍 DEBUG: Log all event types to catch duplicates
                if not event_type.endswith(".delta") and not event_type.startswith("session") and not event_type.startswith("response."):
                    print(f"[REALTIME] event: {event_type}")
                
                # 🔥 CRITICAL FIX: Mark user as speaking when speech starts (before transcription completes!)
                # This prevents the GUARD from blocking AI response audio
                if event_type == "input_audio_buffer.speech_started":
                    # 🔥 BUILD 303: BARGE-IN ON GREETING - User wants to talk over greeting
                    # Instead of ignoring, treat this as valid input and stop the greeting
                    if self.is_playing_greeting:
                        print(f"⛔ [BARGE-IN GREETING] User started talking during greeting - stopping greeting!")
                        self.is_playing_greeting = False
                        self.barge_in_active = True
                        self._barge_in_started_ts = time.time()
                        
                        # 🔥 BUILD 303: User is answering the greeting question
                        self.awaiting_greeting_answer = True
                        self.greeting_completed_at = time.time()  # Mark greeting as done
                        
                        # Flush TX queue to stop greeting audio
                        try:
                            self._flush_twilio_tx_queue(reason="GREETING_BARGE_IN")
                        except Exception as e:
                            print(f"   ⚠️ Error flushing TX queue: {e}")
                        
                        # Cancel any pending response
                        try:
                            if self.realtime_client and self.active_response_id:
                                await asyncio.wait_for(
                                    self.realtime_client.cancel_response(),
                                    timeout=0.5
                                )
                        except Exception:
                            pass
                        
                        self.active_response_id = None
                        self.response_pending_event.clear()
                        self.is_ai_speaking_event.clear()
                        
                        # Enable barge-in for rest of call
                        self.barge_in_enabled_after_greeting = True
                        print(f"   ✅ [BARGE-IN GREETING] Greeting stopped, listening to user...")
                    
                    # 🔥 BUILD 187: RESPONSE GRACE PERIOD - Ignore speech_started within 500ms of response.created
                    # This prevents echo/noise from cancelling the response before audio starts
                    RESPONSE_GRACE_PERIOD_MS = 500
                    response_created_ts = getattr(self, '_response_created_ts', 0)
                    time_since_response = (time.time() - response_created_ts) * 1000 if response_created_ts else 99999
                    if time_since_response < RESPONSE_GRACE_PERIOD_MS and self.active_response_id:
                        print(f"🛡️ [BUILD 187 GRACE] Ignoring speech_started - only {time_since_response:.0f}ms since response.created (grace={RESPONSE_GRACE_PERIOD_MS}ms)")
                        # Don't mark user_has_spoken, don't bypass noise gate - just ignore this event
                        continue
                    
                    print(f"🎤 [REALTIME] User started speaking - setting user_has_spoken=True")
                    self.user_has_spoken = True
                    # 🔥 BUILD 182: IMMEDIATE LOOP GUARD RESET - Don't wait for transcription!
                    # This prevents loop guard from triggering when user IS speaking
                    if self._consecutive_ai_responses > 0:
                        print(f"✅ [LOOP GUARD] User started speaking - resetting consecutive counter ({self._consecutive_ai_responses} -> 0)")
                        self._consecutive_ai_responses = 0
                    if self._loop_guard_engaged:
                        print(f"✅ [LOOP GUARD] User started speaking - disengaging loop guard EARLY")
                        self._loop_guard_engaged = False
                    
                    # ═══════════════════════════════════════════════════════════════════════
                    # 🔥 BUILD 302: HARD BARGE-IN - If AI is speaking, KILL the response NOW!
                    # ═══════════════════════════════════════════════════════════════════════
                    # Goal: Any time user starts speaking while AI is speaking, we do a hard barge-in:
                    #   1. Cancel the current OpenAI response
                    #   2. Stop sending its audio to Twilio
                    #   3. Clear guards/flags
                    #   4. Let the new user utterance lead the next response
                    if self.is_ai_speaking_event.is_set() or self.active_response_id is not None:
                        print(f"⛔ [BARGE-IN] User started talking while AI speaking - HARD CANCEL!")
                        print(f"   active_response_id={self.active_response_id[:20] if self.active_response_id else 'None'}...")
                        print(f"   is_ai_speaking={self.is_ai_speaking_event.is_set()}")
                        
                        # Set barge-in flag - ALL audio gates will be bypassed!
                        self.barge_in_active = True
                        self._barge_in_started_ts = time.time()  # Track for failsafe timeout
                        
                        # 1) Cancel response on OpenAI side (with timeout protection)
                        try:
                            if self.realtime_client:
                                # Use asyncio.wait_for with 0.5s timeout to avoid blocking
                                await asyncio.wait_for(
                                    self.realtime_client.cancel_response(),
                                    timeout=0.5
                                )
                                print(f"   ✅ Sent response.cancel to OpenAI")
                        except asyncio.TimeoutError:
                            print(f"   ⚠️ OpenAI cancel timed out (continuing anyway)")
                        except Exception as e:
                            print(f"   ⚠️ Error cancelling response: {e}")
                        
                        # 2) Clear local guards (ALWAYS, even if cancel failed)
                        self.active_response_id = None
                        self.response_pending_event.clear()
                        self.is_ai_speaking_event.clear()
                        self.speaking = False
                        self.has_pending_ai_response = False
                        
                        # 3) Flush TX audio queue so Twilio stops playing old audio
                        try:
                            self._flush_twilio_tx_queue(reason="BARGE_IN")
                        except Exception as e:
                            print(f"   ⚠️ Error flushing TX queue: {e}")
                        
                        print(f"   ✅ [BARGE-IN] Response cancelled, guards cleared, queue flushed")
                    
                    # 🔥 BUILD 166: BYPASS NOISE GATE while OpenAI is processing speech
                    self._realtime_speech_active = True
                    self._realtime_speech_started_ts = time.time()
                    print(f"🎤 [BUILD 166] Noise gate BYPASSED - sending ALL audio to OpenAI")
                
                # 🔥 BUILD 166: Clear speech active flag when speech ends
                if event_type == "input_audio_buffer.speech_stopped":
                    self._realtime_speech_active = False
                    print(f"🎤 [BUILD 166] Speech ended - noise gate RE-ENABLED")
                    
                    # 🔥 BUILD 302: Clear barge-in flag when user finishes speaking
                    if self.barge_in_active:
                        barge_duration = time.time() - getattr(self, '_barge_in_started_ts', time.time())
                        print(f"✅ [BARGE-IN] User utterance completed - barge-in ended (duration={barge_duration:.1f}s)")
                        self.barge_in_active = False
                        self._barge_in_started_ts = None
                    
                    # 🔥 BUILD 187: Check if we need recovery after cancelled response
                    if self._cancelled_response_needs_recovery:
                        print(f"🔄 [BUILD 187] Speech stopped - waiting {self._cancelled_response_recovery_delay_sec}s for OpenAI...")
                        # Schedule a delayed recovery check in a separate task
                        async def _recovery_check():
                            await asyncio.sleep(self._cancelled_response_recovery_delay_sec)
                            # 🛡️ BUILD 187 HARDENED: Multiple guards to prevent double triggers
                            # Guard 1: Check if recovery is still needed
                            if not self._cancelled_response_needs_recovery:
                                print(f"🔄 [BUILD 187] Recovery cancelled - flag cleared")
                                return
                            # Guard 2: Check if AI is already speaking
                            if self.is_ai_speaking_event.is_set():
                                self._cancelled_response_needs_recovery = False
                                print(f"🔄 [BUILD 187] Recovery skipped - AI already speaking")
                                return
                            # Guard 3: Check if there's a pending response
                            if self.response_pending_event.is_set():
                                self._cancelled_response_needs_recovery = False
                                print(f"🔄 [BUILD 187] Recovery skipped - response pending")
                                return
                            # Guard 4: Check if speech is active (user still talking)
                            if self._realtime_speech_active:
                                self._cancelled_response_needs_recovery = False
                                print(f"🔄 [BUILD 187] Recovery skipped - user still speaking")
                                return
                            
                            # All guards passed - trigger recovery via central function
                            # 🔥 BUILD 200: Use trigger_response for consistent response management
                            self._cancelled_response_needs_recovery = False  # Clear BEFORE triggering
                            triggered = await self.trigger_response("BUILD_187_RECOVERY", client)
                            if not triggered:
                                print(f"⚠️ [BUILD 187] Recovery was blocked by trigger_response guards")
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
                        self.active_response_id = response_id
                        self.response_pending_event.clear()  # 🔒 Clear thread-safe lock
                        # 🔥 BUILD 187: Response grace period - track when response started
                        # This prevents false turn_detected from echo/noise in first 500ms
                        self._response_created_ts = time.time()
                        # 🔥 BUILD 187: Clear recovery flag - new response was created!
                        if self._cancelled_response_needs_recovery:
                            print(f"🔄 [BUILD 187] New response created - cancelling recovery")
                            self._cancelled_response_needs_recovery = False
                        # 🔥 BUILD 305: Reset gap detector for new response
                        # This prevents false "AUDIO GAP" warnings between responses
                        self._last_audio_chunk_ts = time.time()
                        self._openai_audio_chunks_received = 0
                
                # ✅ ONLY handle audio.delta - ignore other audio events!
                # 🔥 FIX: Use response.audio_transcript.delta for is_ai_speaking (reliable text-based flag)
                if event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        # 🛑 BUILD 165: LOOP GUARD - DROP all AI audio when engaged
                        # 🔥 BUILD 178: Disabled for outbound calls
                        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
                        if self._loop_guard_engaged and not is_outbound:
                            # Silently drop audio - don't even log each frame
                            continue
                        
                        # 🎤 GREETING PRIORITY: If greeting sent but user hasn't spoken yet, ALWAYS allow
                        if self.greeting_sent and not self.user_has_spoken:
                            print(f"[GREETING] Passing greeting audio to caller (greeting_sent={self.greeting_sent}, user_has_spoken={self.user_has_spoken})")
                            # Enqueue greeting audio - NO guards, NO cancellation
                            # Track AI speaking state for barge-in
                            now = time.time()
                            if not self.is_ai_speaking_event.is_set():
                                self.ai_speaking_start_ts = now
                                self.speaking_start_ts = now
                            self.is_ai_speaking_event.set()
                            self.is_playing_greeting = True
                            try:
                                self.realtime_audio_out_queue.put_nowait(audio_b64)
                            except queue.Full:
                                pass
                            continue
                        
                        # 🛡️ GUARD: Block AI audio before first real user utterance (non-greeting)
                        if not self.user_has_spoken:
                            # User never spoke, and greeting not sent yet – block it
                            print(f"[GUARD] Blocking AI audio response before first real user utterance (greeting_sent={getattr(self, 'greeting_sent', False)}, user_has_spoken={self.user_has_spoken})")
                            # If there is a response_id in the event, send response.cancel once
                            response_id = event.get("response_id")
                            if response_id:
                                try:
                                    await client.send_event({
                                        "type": "response.cancel",
                                        "response_id": response_id,
                                    })
                                except Exception:
                                    print("[GUARD] Failed to send response.cancel for pre-user-response")
                            continue  # do NOT enqueue audio for TTS
                        
                        # 🎯 Track AI speaking state for ALL AI audio (not just greeting)
                        now = time.time()
                        
                        # 🔥 BUILD 165: ONLY set timestamps on FIRST chunk per utterance
                        # This prevents grace period from constantly resetting
                        if not self.is_ai_speaking_event.is_set():
                            print(f"🔊 [REALTIME] AI started speaking (audio.delta)")
                            self.ai_speaking_start_ts = now
                            self.speaking_start_ts = now
                            self.speaking = True  # 🔥 SYNC: Unify with self.speaking flag
                            self.is_ai_speaking_event.set()  # Thread-safe: AI is speaking
                            # 🔥 BUILD 187: Clear recovery flag - AI is actually speaking!
                            if self._cancelled_response_needs_recovery:
                                print(f"🔄 [BUILD 187] Audio started - cancelling recovery")
                                self._cancelled_response_needs_recovery = False
                        # Don't reset timestamps on subsequent chunks!
                        self.has_pending_ai_response = True  # AI is generating response
                        self.last_ai_audio_ts = now
                        
                        # 💰 COST TRACKING: Count AI audio chunks
                        # μ-law 8kHz: ~160 bytes per 20ms chunk = 50 chunks/second
                        if not hasattr(self, '_ai_speech_start') or self._ai_speech_start is None:
                            self._ai_speech_start = now
                        self.realtime_audio_out_chunks += 1
                        
                        # 🔍 DEBUG: Verify μ-law format from OpenAI + GAP DETECTION
                        if not hasattr(self, '_openai_audio_chunks_received'):
                            self._openai_audio_chunks_received = 0
                            self._last_audio_chunk_ts = now
                        self._openai_audio_chunks_received += 1
                        
                        # 🔍 GAP DETECTION: Log if >500ms between chunks (potential pause source)
                        gap_ms = (now - getattr(self, '_last_audio_chunk_ts', now)) * 1000
                        if gap_ms > 500 and self._openai_audio_chunks_received > 3:
                            print(f"⚠️ [AUDIO GAP] {gap_ms:.0f}ms gap between chunks #{self._openai_audio_chunks_received-1} and #{self._openai_audio_chunks_received} - OpenAI delay!")
                            
                            # 🔥 BUILD 181: GAP RECOVERY - Insert silence frames for gaps >3 seconds
                            # This prevents audio distortion by maintaining continuous playback
                            if gap_ms > 3000:
                                # Calculate how many silence frames needed to smooth transition
                                # Don't add full gap - just 500ms transition buffer
                                silence_frames_needed = min(25, int(gap_ms / 100))  # 25 frames max = 500ms
                                import base64
                                # Generate 160-byte μ-law silence frames (0xFF = silence in μ-law)
                                silence_frame = base64.b64encode(bytes([0xFF] * 160)).decode('utf-8')
                                for _ in range(silence_frames_needed):
                                    try:
                                        self.realtime_audio_out_queue.put_nowait(silence_frame)
                                    except queue.Full:
                                        break
                                print(f"🔧 [GAP RECOVERY] Inserted {silence_frames_needed} silence frames ({silence_frames_needed * 20}ms)")
                        self._last_audio_chunk_ts = now
                        
                        if self._openai_audio_chunks_received <= 3:
                            import base64
                            chunk_bytes = base64.b64decode(audio_b64)
                            first5_bytes = ' '.join([f'{b:02x}' for b in chunk_bytes[:5]])
                            print(f"[REALTIME] got audio chunk from OpenAI: chunk#{self._openai_audio_chunks_received}, bytes={len(chunk_bytes)}, first5={first5_bytes}")
                        
                        try:
                            self.realtime_audio_out_queue.put_nowait(audio_b64)
                        except queue.Full:
                            pass
                
                # ❌ IGNORE these audio events - they contain duplicate/complete audio buffers:
                elif event_type in ("response.audio.done", "response.output_item.done"):
                    # When audio finishes and we were in greeting mode, unset the flag
                    if self.is_playing_greeting:
                        greeting_end_ts = time.time()
                        greeting_duration = 0
                        if hasattr(self, '_greeting_start_ts') and self._greeting_start_ts:
                            greeting_duration = (greeting_end_ts - self._greeting_start_ts) * 1000
                        print(f"🎤 [GREETING] Greeting finished at {greeting_end_ts:.3f} (duration: {greeting_duration:.0f}ms)")
                        self.is_playing_greeting = False
                        # 🎯 FIX: Enable barge-in after greeting completes
                        # Use dedicated flag instead of user_has_spoken to preserve guards
                        self.barge_in_enabled_after_greeting = True
                        print(f"✅ [GREETING] Barge-in now ENABLED for rest of call")
                        # 🔥 PROTECTION: Mark greeting completion time for hangup protection
                        self.greeting_completed_at = time.time()
                        print(f"🛡️ [PROTECTION] Greeting completed - hangup blocked for {self.min_call_duration_after_greeting_ms}ms")
                        
                        # 🔥 BUILD 303: GREETING FLOW - Now waiting for first user utterance
                        # Don't let AI create new response until user answers the greeting question
                        self.awaiting_greeting_answer = True
                        self.first_post_greeting_utterance_handled = False
                        print(f"⏳ [BUILD 303] Waiting for user's first response to greeting...")
                        
                        # 🔥 BUILD 172: Transition to ACTIVE state and start silence monitor
                        if self.call_state == CallState.WARMUP:
                            self.call_state = CallState.ACTIVE
                            print(f"📞 [STATE] Transitioned WARMUP → ACTIVE (greeting done)")
                            asyncio.create_task(self._start_silence_monitor())
                    
                    # Don't process - would cause duplicate playback
                    # 🎯 Mark AI response complete
                    if self.is_ai_speaking_event.is_set():
                        print(f"🔇 [REALTIME] AI stopped speaking ({event_type})")
                    self.is_ai_speaking_event.clear()  # Thread-safe: AI stopped speaking
                    self.speaking = False  # 🔥 BUILD 165: SYNC with self.speaking flag
                    self.ai_speaking_start_ts = None  # 🔥 FIX: Clear start timestamp
                    
                    # 🔥 BUILD 171: Track when AI finished speaking for cooldown check
                    self._ai_finished_speaking_ts = time.time()
                    print(f"🔥 [BUILD 171] AI finished speaking - cooldown started ({POST_AI_COOLDOWN_MS}ms)")
                    
                    # 🔥 BUILD 172: Update speech time for silence detection
                    self._update_speech_time()
                    
                    # 🔥🔥 CRITICAL FIX: Do NOT clear audio queue here!
                    # The queue may still have audio chunks that need to be sent to Twilio.
                    # Clearing prematurely causes greeting/response truncation!
                    # Let the audio bridge naturally drain the queue.
                    queue_size = self.realtime_audio_out_queue.qsize()
                    if queue_size > 0:
                        print(f"⏳ [AUDIO] {queue_size} frames still in queue - letting them play (NO TRUNCATION)")
                    
                    self.has_pending_ai_response = False
                    self.active_response_id = None  # Clear response ID
                    self.response_pending_event.clear()  # 🔒 Clear thread-safe lock
                    
                    # 🎯 BUILD 163: Check for polite hangup AFTER audio finishes
                    # This ensures AI finishes speaking before we disconnect
                    if self.pending_hangup and not self.hangup_triggered:
                        # Wait for audio to fully play before disconnecting
                        async def delayed_hangup():
                            print(f"⏳ [POLITE HANGUP] Starting wait for audio to finish...")
                            
                            # STEP 1: Wait for OpenAI queue to drain (max 5 seconds)
                            for i in range(50):  # 50 * 100ms = 5 seconds max
                                q1_size = self.realtime_audio_out_queue.qsize()
                                if q1_size == 0:
                                    print(f"✅ [POLITE HANGUP] OpenAI queue empty after {i*100}ms")
                                    break
                                await asyncio.sleep(0.1)
                            
                            # STEP 2: Wait for Twilio TX queue to drain (max 10 seconds)
                            # Each frame is 20ms, so 500 frames = 10 seconds of audio
                            for i in range(100):  # 100 * 100ms = 10 seconds max
                                tx_size = self.tx_q.qsize()
                                if tx_size == 0:
                                    print(f"✅ [POLITE HANGUP] Twilio TX queue empty after {i*100}ms")
                                    break
                                if i % 10 == 0:  # Log every second
                                    print(f"⏳ [POLITE HANGUP] TX queue still has {tx_size} frames...")
                                await asyncio.sleep(0.1)
                            
                            # STEP 3: Extra buffer for network latency
                            # Audio still needs to travel from Twilio servers to phone
                            print(f"⏳ [POLITE HANGUP] Queues empty, waiting 2s for network...")
                            await asyncio.sleep(2.0)
                            
                            if not self.hangup_triggered:
                                print(f"📞 [BUILD 163] Audio playback complete - triggering polite hangup now")
                                import threading
                                threading.Thread(
                                    target=self._trigger_auto_hangup,
                                    args=("AI finished speaking politely",),
                                    daemon=True
                                ).start()
                        
                        asyncio.create_task(delayed_hangup())
                
                elif event_type == "response.audio_transcript.done":
                    transcript = event.get("transcript", "")
                    if transcript:
                        print(f"🤖 [REALTIME] AI said: {transcript}")
                        
                        # 🔥 BUILD 169.1: IMPROVED SEMANTIC LOOP DETECTION (Architect-reviewed)
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
                        is_repeating = False
                        if len(self._last_ai_responses) >= 2 and len(transcript) >= MIN_LENGTH_FOR_SIMILARITY:
                            for prev_response in self._last_ai_responses[:-1]:
                                if len(prev_response) < MIN_LENGTH_FOR_SIMILARITY:
                                    continue  # Skip short responses
                                similarity = _text_similarity(transcript, prev_response)
                                if similarity > 0.70:
                                    is_repeating = True
                                    print(f"⚠️ [LOOP DETECT] AI repeating! Similarity={similarity:.0%} with: '{prev_response[:50]}...'")
                                    break
                        
                        # 🔥 BUILD 169.1: MISHEARING DETECTION (Architect: reduced to 2 for better UX)
                        confusion_phrases = ["לא הבנתי", "לא שמעתי", "אפשר לחזור", "מה אמרת", "לא הצלחתי", "בבקשה חזור"]
                        is_confused = any(phrase in transcript for phrase in confusion_phrases)
                        if is_confused:
                            self._mishearing_count += 1
                            print(f"❓ [MISHEARING] AI confused ({self._mishearing_count} times): '{transcript[:50]}...'")
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
                            print(f"📢 [BUILD 311] SILENCE_HANDLER response - NOT counting towards consecutive")
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
                        
                        # 🔥 BUILD 182: Check if appointment was recently created/scheduled
                        crm_ctx = getattr(self, 'crm_context', None)
                        has_appointment = crm_ctx and getattr(crm_ctx, 'has_appointment_created', False)
                        # Also check if AI is discussing appointment (keywords in recent response)
                        appointment_keywords = ['תור', 'פגישה', 'לקבוע', 'זמינות', 'אשר', 'מאשר']
                        is_scheduling = any(kw in transcript for kw in appointment_keywords) if transcript else False
                        
                        if in_post_greeting_grace:
                            # 🔥 BUILD 311: NEVER engage loop guard during grace period - give customer time to respond!
                            should_engage_guard = False
                            print(f"⏳ [BUILD 311] Post-greeting grace period ({time_since_greeting:.1f}s/{grace_period}s) - LOOP GUARD DISABLED")
                        elif is_outbound:
                            # 🔥 OUTBOUND: Never engage loop guard - let AI talk freely
                            should_engage_guard = False
                        elif is_closing or is_hanging_up:
                            # 🔥 BUILD 179: Never engage loop guard during call ending
                            should_engage_guard = False
                            print(f"⏭️ [LOOP GUARD] Skipped - call is ending (closing={is_closing}, hangup={is_hanging_up})")
                        elif has_appointment or is_scheduling:
                            # 🔥 BUILD 182: Never engage loop guard during appointment scheduling
                            should_engage_guard = False
                            print(f"⏭️ [LOOP GUARD] Skipped - appointment flow (has_appointment={has_appointment}, is_scheduling={is_scheduling})")
                        else:
                            # INBOUND: Normal loop guard logic
                            max_consecutive = self._max_consecutive_ai_responses
                            should_engage_guard = (
                                (self._consecutive_ai_responses >= max_consecutive and user_silent_long_time) or
                                (is_repeating and self._consecutive_ai_responses >= 3) or
                                self._mishearing_count >= 3
                            )
                        
                        if should_engage_guard:
                            guard_reason = "consecutive_responses" if self._consecutive_ai_responses >= self._max_consecutive_ai_responses else \
                                          "semantic_repetition" if is_repeating else "mishearing_loop"
                            print(f"⚠️ [LOOP GUARD] Triggered by {guard_reason}!")
                            print(f"🛑 [LOOP GUARD] BLOCKING further responses until user speaks!")
                            # 🛑 ENGAGE GUARD FIRST - before any other operations to prevent race conditions
                            self._loop_guard_engaged = True
                            
                            # Send clarification request to AI before blocking
                            clarification_text = "[SERVER] זיהיתי שאתה חוזר על עצמך. אמור: 'לא שמעתי טוב, אפשר לחזור?' ותמתין בשקט."
                            asyncio.create_task(self._send_server_event_to_ai(clarification_text))
                            
                            # 🔥 BUILD 305: DON'T clear TX queue - causes choppy mid-sentence audio!
                            # Instead: just block NEW audio from being added via _tx_enqueue guard
                            # Let existing audio in queue play out naturally for smooth transition
                            
                            # Only cancel if there's actually an active response
                            if self.active_response_id and self.realtime_client and self.is_ai_speaking_event.is_set():
                                try:
                                    await client.send_event({"type": "response.cancel"})
                                    print(f"🛑 [LOOP GUARD] Cancelled active AI response (id={self.active_response_id})")
                                except:
                                    pass
                            else:
                                print(f"⏭️ [LOOP GUARD] Skipped cancel - no active response (id={self.active_response_id}, speaking={self.is_ai_speaking_event.is_set()})")
                            
                            # 🔥 BUILD 305: DON'T clear queues - this causes choppy audio!
                            # The _tx_enqueue function already blocks audio when _loop_guard_engaged=True
                            # Old code cleared TX queue here, causing mid-sentence cuts
                            print(f"✅ [LOOP GUARD] Engaged - blocking new audio (existing queue: {self.tx_q.qsize()} frames will play)")
                            # Mark AI as not speaking
                            self.is_ai_speaking_event.clear()
                            self.speaking = False
                        
                        # 💰 COST TRACKING: AI finished speaking - stop timer
                        if hasattr(self, '_ai_speech_start') and self._ai_speech_start is not None:
                            ai_duration = time.time() - self._ai_speech_start
                            print(f"💰 [COST] AI utterance: {ai_duration:.2f}s ({self.realtime_audio_out_chunks} chunks)")
                            self._ai_speech_start = None  # Reset for next utterance
                        
                        # 🔥 POST-FILTER: Detect if AI said "confirmed" without server approval
                        crm_context = getattr(self, 'crm_context', None)
                        forbidden_words = ["קבעתי", "קבענו", "שריינתי", "התור נקבע", "התור שלך נקבע", "הפגישה נקבעה"]
                        said_forbidden = any(word in transcript for word in forbidden_words)
                        
                        if said_forbidden and (not crm_context or not crm_context.has_appointment_created):
                            print(f"⚠️ [GUARD] AI said '{transcript}' WITHOUT server approval!")
                            print(f"🛡️ [GUARD] Sending immediate correction to AI...")
                            # 🔥 BUILD 182: Block hangup if AI confirmed but system didn't
                            # This prevents the call from ending before appointment is actually created
                            self._ai_said_confirmed_without_approval = True
                            # 🔥 BUILD 182: Trigger NLP immediately to try to create the appointment
                            # This runs in background thread and may create the appointment
                            print(f"🔥 [GUARD] Triggering immediate NLP check to create appointment...")
                            self._check_appointment_confirmation(transcript)
                            # Send immediate correction event
                            asyncio.create_task(self._send_server_event_to_ai(
                                "⚠️ תיקון: התור עדיין לא אושר על ידי המערכת! אל תאשר עד שתקבל הודעה שהתור נקבע"
                            ))
                        
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
                                print(f"🛡️ [PROTECTION] Ignoring AI goodbye - only {elapsed_ms:.0f}ms since greeting")
                        # Note: If greeting_completed_at is None (no greeting), allow goodbye detection normally
                        
                        # 🔥 FIX: Also detect polite closing phrases (not just "ביי")
                        ai_polite_closing_detected = self._check_goodbye_phrases(transcript) or self._check_polite_closing(transcript)
                        
                        # 🎯 BUILD 170.5: FIXED HANGUP LOGIC
                        # Settings-based hangup respects business configuration
                        # Hangup requires EITHER:
                        # - User said goodbye (goodbye_detected=True), OR
                        # - Lead captured with auto_end_after_lead_capture=True, OR
                        # - User confirmed summary (verification_confirmed=True)
                        should_hangup = False
                        hangup_reason = ""
                        
                        # 🔥 BUILD 182: Block hangup if AI confirmed appointment but system hasn't
                        ai_said_without_approval = getattr(self, '_ai_said_confirmed_without_approval', False)
                        crm_ctx = getattr(self, 'crm_context', None)
                        hangup_blocked_for_appointment = False
                        if ai_said_without_approval and (not crm_ctx or not crm_ctx.has_appointment_created):
                            print(f"🛑 [GUARD] Blocking hangup - AI confirmed but appointment not yet created!")
                            hangup_blocked_for_appointment = True
                        
                        # 🔥 BUILD 309: Check confirm_before_hangup setting from call config
                        # If False, allow hangup without user confirmation (just goodbye)
                        confirm_required = getattr(self, 'confirm_before_hangup', True)
                        
                        # 🔥 BUILD 170.5: Hangup only when proper conditions are met
                        # Skip all hangup logic if appointment guard is active
                        if hangup_blocked_for_appointment:
                            print(f"🛑 [HANGUP] Skipping all hangup checks - waiting for appointment creation")
                        # Case 1: User explicitly said goodbye - always allow hangup after AI responds
                        elif self.goodbye_detected and ai_polite_closing_detected:
                            hangup_reason = "user_goodbye"
                            should_hangup = True
                            print(f"✅ [HANGUP] User said goodbye, AI responded politely - disconnecting")
                        
                        # Case 2: Lead fully captured AND setting enabled
                        # 🔥 BUILD 309: respect confirm_before_hangup setting!
                        elif self.auto_end_after_lead_capture and self.lead_captured and ai_polite_closing_detected:
                            if confirm_required and not self.verification_confirmed:
                                # Confirmation required but not received yet - AI should ask
                                print(f"⏳ [HANGUP] Lead captured but confirm_before_hangup=True - waiting for user confirmation")
                            else:
                                hangup_reason = "lead_captured_confirmed" if self.verification_confirmed else "lead_captured_auto"
                                should_hangup = True
                                print(f"✅ [HANGUP] Lead captured + {'confirmed' if self.verification_confirmed else 'auto (no confirm required)'} - disconnecting")
                        
                        # Case 3: User explicitly confirmed details in summary
                        elif self.verification_confirmed and ai_polite_closing_detected:
                            hangup_reason = "user_verified"
                            should_hangup = True
                            print(f"✅ [HANGUP] User confirmed all details - disconnecting")
                        
                        # Case 4: BUILD 176 - auto_end_on_goodbye enabled AND AI said closing
                        # SAFETY: Only trigger if user has spoken (user_has_spoken=True) to avoid premature hangups
                        # Also requires either: user confirmed, lead captured, OR meaningful conversation happened
                        elif self.auto_end_on_goodbye and ai_polite_closing_detected and self.user_has_spoken:
                            # Additional guard: must have some interaction (user spoken + either confirmed or lead info)
                            has_meaningful_interaction = (
                                self.verification_confirmed or 
                                self.lead_captured or 
                                len(self.conversation_history) >= 4  # At least 2 exchanges
                            )
                            if has_meaningful_interaction:
                                hangup_reason = "ai_goodbye_auto_end"
                                should_hangup = True
                                print(f"✅ [HANGUP BUILD 176] AI said goodbye with auto_end_on_goodbye=True + user interaction - disconnecting")
                        
                        # Log when AI says closing but we're blocking hangup
                        elif ai_polite_closing_detected:
                            print(f"🔒 [HANGUP BLOCKED] AI said closing phrase but conditions not met:")
                            print(f"   goodbye_detected={self.goodbye_detected}")
                            print(f"   auto_end_on_goodbye={self.auto_end_on_goodbye}")
                            print(f"   auto_end_after_lead_capture={self.auto_end_after_lead_capture}, lead_captured={self.lead_captured}")
                            print(f"   verification_confirmed={self.verification_confirmed}")
                        
                        if should_hangup:
                            self.goodbye_detected = True
                            self.pending_hangup = True
                            # 🔥 BUILD 172: Transition to CLOSING state
                            if self.call_state == CallState.ACTIVE:
                                self.call_state = CallState.CLOSING
                                print(f"📞 [STATE] Transitioning ACTIVE → CLOSING (reason: {hangup_reason})")
                            print(f"📞 [BUILD 163] Pending hangup set - will disconnect after audio finishes playing")
                        
                        # 🔥 NOTE: Hangup is now triggered in response.audio.done to let audio finish!
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    raw_text = event.get("transcript", "") or ""
                    text = raw_text.strip()
                    
                    # 🔥 BUILD 300: UNIFIED STT LOGGING - Step 1: Log raw transcript
                    print(f"[STT_RAW] '{raw_text}' (len={len(raw_text)})")
                    
                    # 🔥 BUILD 170.4: Apply Hebrew normalization
                    text = normalize_hebrew_text(text)
                    
                    # 🔥 BUILD 204: Apply business vocabulary corrections (fast fuzzy matching)
                    # This corrects domain-specific terms BEFORE other filters
                    vocab_corrections = {}
                    try:
                        from server.services.dynamic_stt_service import apply_vocabulary_corrections, semantic_repair, should_apply_semantic_repair
                        text_before = text
                        text, vocab_corrections = apply_vocabulary_corrections(text, self.business_id)
                        if vocab_corrections:
                            print(f"🔧 [BUILD 204] Vocabulary fix: '{text_before}' → '{text}' (corrections: {vocab_corrections})")
                        
                        # 🔥 BUILD 300: SEMANTIC REPAIR for short/unclear transcriptions
                        if should_apply_semantic_repair(text):
                            try:
                                text_before_repair = text
                                text = await semantic_repair(text, self.business_id)
                                if text != text_before_repair:
                                    print(f"[STT_REPAIRED] '{text_before_repair}' → '{text}'")
                            except Exception as repair_err:
                                print(f"⚠️ [BUILD 300] Semantic repair skipped: {repair_err}")
                    except Exception as vocab_err:
                        print(f"⚠️ [BUILD 204] Vocabulary correction skipped: {vocab_err}")
                    
                    now_ms = time.time() * 1000
                    now_sec = now_ms / 1000
                    
                    # 🔥 BUILD 300: REMOVED POST_AI_COOLDOWN GATE
                    # The guide says: "אסור לזרוק טקסט בגלל pause ארוך" and "המודל תמיד יודע טוב יותר"
                    # OpenAI's VAD/STT is authoritative - if it transcribed something, it's valid
                    # Old code rejected transcripts arriving <1200ms after AI spoke - this blocked valid responses!
                    if self._ai_finished_speaking_ts > 0:
                        time_since_ai_finished = (now_sec - self._ai_finished_speaking_ts) * 1000
                        # 🔥 BUILD 300: Only LOG, don't reject! OpenAI knows better than local timing
                        if time_since_ai_finished < 500:  # Very fast response - just log for debugging
                            print(f"⚡ [BUILD 300] Fast response: {time_since_ai_finished:.0f}ms after AI (trusting OpenAI)")
                    
                    # 🔥 BUILD 202 FIX: TRUST OPENAI STT OVER LOCAL RMS
                    # If OpenAI Realtime API transcribed the speech, it detected valid audio.
                    # Our local RMS measurement can be stale or wrong (race condition).
                    # Only apply silence gate to very short/empty transcriptions.
                    recent_rms = getattr(self, '_recent_audio_rms', 0)
                    consec_frames = getattr(self, '_consecutive_voice_frames', 0)
                    ABSOLUTE_SILENCE_RMS = 30
                    
                    # 🔥 BUILD 202: Only reject if BOTH conditions are met:
                    # 1. Very low RMS (< 10, not 30 - true silence)
                    # 2. Very short text (< 3 chars - likely noise artifact)
                    # OpenAI's VAD is more reliable than our local measurement!
                    if recent_rms < 10 and len(text.strip()) < 3:
                        print(f"[SILENCE GATE] ❌ REJECTED (RMS={recent_rms:.0f} < 10, text too short): '{text}'")
                        continue
                    elif recent_rms < ABSOLUTE_SILENCE_RMS and len(text.strip()) >= 3:
                        # 🔥 BUILD 202: Trust OpenAI - it heard something valid!
                        print(f"[SILENCE GATE] ✅ TRUSTED (OpenAI heard '{text[:30]}...' despite low RMS={recent_rms:.0f})")
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
                            print(f"🚫 [BUILD 186] ENGLISH HALLUCINATION: '{text}' (all words are common English)")
                    
                    # 🔥 BUILD 303: INCREMENT USER UTTERANCE COUNT
                    self.user_utterance_count += 1
                    
                    # 🔥 BUILD 309: SIMPLE_MODE - Bypass ALL noise/gibberish filters!
                    # In SIMPLE_MODE, trust OpenAI + Twilio completely - all text passes through
                    is_gibberish_detected = False
                    should_filter = False
                    filter_reason = ""
                    
                    if SIMPLE_MODE:
                        print(f"✅ [SIMPLE_MODE] Bypassing all filters - accepting: '{text}'")
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
                            print(f"✅ [BUILD 303 PATIENCE] Bypassing gibberish check for utterance #{self.user_utterance_count}: '{text_stripped}' (hebrew_chars={hebrew_chars})")
                        elif hebrew_chars > 0 and text_stripped not in natural_elongations:
                            # Use the generic Hebrew STT validator (no hardcoded patterns)
                            is_gib, gib_reason, gib_confidence = is_gibberish(text_stripped)
                            if is_gib and gib_confidence >= 0.5:
                                is_gibberish_detected = True
                                print(f"[GIBBERISH] Detected: '{text_stripped}' | Reason: {gib_reason} | Confidence: {gib_confidence:.0%}")
                        
                        # 🛡️ Check if pure English with no Hebrew - likely Whisper hallucination
                        is_pure_english = hebrew_chars == 0 and english_chars >= 2 and len(text) < 20
                        
                        # 🔥 BUILD 170.4: IMPROVED FILTER LOGIC
                        # Priority: Allow Hebrew > Block hallucinations > Block gibberish
                        
                        # First check: If has Hebrew characters and meaningful length, probably valid
                        has_meaningful_hebrew = hebrew_chars >= 2 and len(text) >= 3
                        
                        if is_valid_short_hebrew or starts_with_valid:
                            # ✅ ALWAYS allow valid short Hebrew words or phrases starting with them
                            should_filter = False
                            print(f"✅ [NOISE FILTER] ALLOWED Hebrew: '{text}'")
                        elif has_meaningful_hebrew and not is_gibberish_detected:
                            # ✅ Has Hebrew characters and not gibberish - probably valid
                            should_filter = False
                            print(f"✅ [NOISE FILTER] ALLOWED (has Hebrew): '{text}'")
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
                            print(f"[NOISE FILTER] ❌ REJECTED ({filter_reason}): '{text}'")
                            print(f"[SAFETY] Transcription successful (total failures: {self.transcription_failed_count})")
                            # 🔥 BUILD 182: STILL record filtered transcripts for webhook/transcript purposes!
                            # Only skip AI processing, not conversation history
                            if len(text) >= 2 and filter_reason not in ["gibberish", "too_short_or_punctuation"]:
                                self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                                print(f"📝 [TRANSCRIPT] Recorded filtered user speech for webhook: '{text}'")
                            continue
                        
                        # ✅ PASSED FILTER
                        print(f"[NOISE FILTER] ✅ ACCEPTED: '{text}' (hebrew={hebrew_chars}, english={english_chars})")
                    
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
                            print(f"🔄 [BUILD 308 DEDUPE] Skipping duplicate segment: '{text}'")
                    
                    if self._stt_last_segment_ts > 0:
                        time_since_last = now_ms - self._stt_last_segment_ts
                        buffer_len = sum(len(s) for s in self._stt_merge_buffer) if self._stt_merge_buffer else 0
                        
                        # Check flush conditions (architect feedback)
                        if time_since_last >= LONG_PAUSE_MS:
                            # Long pause = distinct intent, flush buffer first
                            should_flush = True
                            print(f"📝 [SEGMENT MERGE] FLUSH - long pause ({time_since_last:.0f}ms)")
                        elif buffer_len >= MAX_MERGE_LENGTH:
                            # Buffer too long, flush to avoid over-merging
                            should_flush = True
                            print(f"📝 [SEGMENT MERGE] FLUSH - max length ({buffer_len} chars)")
                        elif time_since_last < STT_MERGE_WINDOW_MS:
                            # Within merge window, continue buffering
                            should_merge = True
                    
                    # Process any pending buffer if flush needed
                    if should_flush and self._stt_merge_buffer:
                        flushed_text = " ".join(self._stt_merge_buffer)
                        print(f"📝 [SEGMENT MERGE] Flushed buffer: '{flushed_text}'")
                        self._stt_merge_buffer = []
                        # Process flushed text separately - let it flow through
                        # Current text will be processed as new segment
                    
                    if should_merge and not is_duplicate:
                        # Merge with previous segment (but skip duplicates!)
                        self._stt_merge_buffer.append(text)
                        self._stt_last_segment_ts = now_ms
                        print(f"📝 [SEGMENT MERGE] Buffering: '{text}' (wait for more)")
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
                                print(f"🔄 [BUILD 308 DEDUPE] Removed duplicate half: '{second_half}'")
                        
                        print(f"📝 [SEGMENT MERGE] Combined {len(self._stt_merge_buffer)} segments: '{text}'")
                        self._stt_merge_buffer = []
                    
                    self._stt_last_segment_ts = now_ms
                    transcript = text
                    
                    # 🔥 BUILD 300: UNIFIED STT LOGGING - Step 3: Log final transcript
                    # Format: [STT_FINAL] → what goes into Lead State / AI processing
                    print(f"[STT_FINAL] '{transcript}' (from raw: '{raw_text[:30]}...')")
                    
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
                    
                    # Mark that the user really spoke at least once
                    self.user_has_spoken = True
                    
                    # 🔥 BUILD 170.3: LOOP PREVENTION - Reset counter when user speaks
                    self._consecutive_ai_responses = 0
                    self._last_user_transcript_ts = time.time()
                    self._last_user_speech_ts = time.time()  # 🔥 BUILD 170.3: Track for time-based guard
                    
                    # 🔥 BUILD 172: Update speech time for silence detection
                    self._update_speech_time()
                    # 🛑 DISENGAGE LOOP GUARD - user spoke, allow AI to respond again
                    if self._loop_guard_engaged:
                        print(f"✅ [LOOP GUARD] User spoke - disengaging loop guard")
                        self._loop_guard_engaged = False
                    
                    # 💰 COST TRACKING: User finished speaking - stop timer  
                    if hasattr(self, '_user_speech_start') and self._user_speech_start is not None:
                        user_duration = time.time() - self._user_speech_start
                        print(f"💰 [COST] User utterance: {user_duration:.2f}s ({self.realtime_audio_in_chunks} chunks total)")
                        self._user_speech_start = None  # Reset for next utterance
                    
                    if transcript:
                        print(f"👤 [REALTIME] User said: {transcript}")
                        
                        # ═══════════════════════════════════════════════════════════════════════════
                        # 🔥 BUILD 303: FIRST POST-GREETING UTTERANCE HANDLING
                        # ═══════════════════════════════════════════════════════════════════════════
                        # If we're waiting for the first response after greeting, mark it as handled
                        if self.awaiting_greeting_answer and not self.first_post_greeting_utterance_handled:
                            self.first_post_greeting_utterance_handled = True
                            self.awaiting_greeting_answer = False
                            print(f"✅ [BUILD 303] First post-greeting utterance: '{transcript[:50]}...' - processing as answer to greeting question")
                        
                        # ═══════════════════════════════════════════════════════════════════════════
                        # 🔥 BUILD 303: NEGATIVE ANSWER DETECTION - Don't skip questions when user says "no"
                        # ═══════════════════════════════════════════════════════════════════════════
                        transcript_clean_neg = transcript.strip().lower().replace(".", "").replace("!", "").replace("?", "")
                        negative_answers = ["לא", "ממש לא", "חד משמעית לא", "לא צריך", "אין צורך", "לא לא", "לא נכון", "טעות"]
                        is_negative_answer = any(transcript_clean_neg.startswith(neg) for neg in negative_answers)
                        
                        if is_negative_answer:
                            print(f"⚠️ [BUILD 303] NEGATIVE ANSWER detected: '{transcript}' - user is rejecting/correcting")
                            # Mark that we need to handle this as a correction, not move forward
                            self.user_rejected_confirmation = True
                            # If we're tracking what AI asked, mark it for retry
                            if self.last_ai_question_type:
                                print(f"   Last AI question type: {self.last_ai_question_type} - needs retry")
                        else:
                            # 🔥 BUILD 308: User provided meaningful content (not just rejection)
                            # Clear the cool-off flag so AI can respond normally
                            if getattr(self, '_awaiting_user_correction', False):
                                self._awaiting_user_correction = False
                                print(f"✅ [BUILD 308] User provided content - clearing cool-off flag")
                        
                        # ═══════════════════════════════════════════════════════════════════════════
                        # 🔥 BUILD 303: CITY CORRECTION DETECTION
                        # Handle patterns like: "לא, לא תל אביב - קריית אתא"
                        # ═══════════════════════════════════════════════════════════════════════════
                        if is_negative_answer and hasattr(self, 'stt_consistency_filter'):
                            # Check if this is a city correction
                            cities_set, _, _ = load_hebrew_lexicon()
                            
                            # Find all cities mentioned in the transcript
                            cities_mentioned = []
                            for city in cities_set:
                                if city in transcript_clean_neg and len(city) > 2:
                                    cities_mentioned.append(city)
                            
                            if len(cities_mentioned) >= 1:
                                # User mentioned at least one city after "לא" - this is a correction!
                                # Take the LAST city mentioned (the correction)
                                new_city = cities_mentioned[-1]
                                
                                # Check if city is currently locked to something different
                                current_city = self.lead_capture_state.get('city', '')
                                
                                if current_city and current_city != new_city:
                                    print(f"🔧 [BUILD 303 CITY CORRECTION] User correcting city: '{current_city}' → '{new_city}'")
                                    
                                    # Unlock the city in consistency filter
                                    if self.stt_consistency_filter.is_city_locked():
                                        self.stt_consistency_filter.unlock_city()
                                        print(f"   🔓 Unlocked city in consistency filter")
                                    
                                    # Update lead capture state with new city
                                    self._update_lead_capture_state('city', new_city)
                                    self._update_lead_capture_state('city_corrected_by_user', True)
                                    print(f"   ✅ Updated city to: {new_city}")
                        
                        # 🔥 BUILD 186: SEMANTIC COHERENCE GUARD
                        # Check if user's response makes sense given the last AI question
                        is_first_response = len([m for m in self.conversation_history if m.get("speaker") == "user"]) == 0
                        transcript_clean = transcript.strip().lower().replace(".", "").replace("!", "").replace("?", "")
                        
                        # Get last AI message for context check
                        last_ai_msg = None
                        for msg in reversed(self.conversation_history):
                            if msg.get("speaker") == "ai":
                                last_ai_msg = msg.get("text", "").lower()
                                break
                        
                        is_incoherent_response = False
                        
                        # Check 1: First response after greeting should be a request, not "thank you"
                        if is_first_response and self.greeting_completed_at:
                            nonsense_first_responses = [
                                "תודה רבה", "תודה", "שלום", "היי", "ביי", "להתראות",
                                "okay", "ok", "yes", "no", "bye", "hello", "hi"
                            ]
                            if transcript_clean in nonsense_first_responses:
                                is_incoherent_response = True
                                print(f"⚠️ [BUILD 186] INCOHERENT: First response '{transcript}' doesn't make sense after greeting")
                        
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
                                    print(f"⚠️ [BUILD 186] INCOHERENT: Response '{transcript}' doesn't match city question")
                        
                        # Check 3: If AI asked for name, response should be a name-like pattern
                        if last_ai_msg and ("שם" in last_ai_msg or "איך קוראים" in last_ai_msg):
                            # Response should be name-like (not just "thank you")
                            if transcript_clean in ["תודה רבה", "תודה", "שלום", "ביי"]:
                                is_incoherent_response = True
                                print(f"⚠️ [BUILD 186] INCOHERENT: Response '{transcript}' doesn't match name question")
                        
                        # If incoherent, mark for AI to handle with clarification
                        if is_incoherent_response:
                            # Add marker to transcript so AI knows to ask for clarification
                            print(f"🔄 [BUILD 186] Marked incoherent response - AI will ask for clarification")
                        
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
                            print(f"✅ [BUILD 176] User CONFIRMED with '{transcript[:30]}' - verification_confirmed = True")
                            self.verification_confirmed = True
                            # 🔥 BUILD 203: Clear rejection flag when user confirms
                            self.user_rejected_confirmation = False
                        
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
                            print(f"🔄 [BUILD 310] User CORRECTION detected: strong={is_strong_rejection}, weak={is_weak_rejection}, ai_verify={ai_asked_verification}")
                            self.verification_confirmed = False
                            # 🔥 FIX: Also reset the prompt flag so we can send a new verification request
                            self._verification_prompt_sent = False
                            # 🔥 BUILD 203: Cancel any pending hangup - user rejected!
                            self.user_rejected_confirmation = True
                            self.goodbye_detected = False  # Clear goodbye flag
                            if self.call_state == CallState.CLOSING:
                                self.call_state = CallState.ACTIVE
                                print(f"📞 [BUILD 203] CLOSING → ACTIVE (user rejected confirmation)")
                            # 🔥 BUILD 201: Unlock city when user says correction words
                            if hasattr(self, 'stt_consistency_filter') and self.stt_consistency_filter.is_city_locked():
                                self.stt_consistency_filter.unlock_city(reason="user_correction_word")
                            
                            # 🔥 BUILD 308: CRITICAL FIX - Also CLEAR city from lead_capture_state
                            # Previously only unlocking from consistency filter, but AI still thought city was captured
                            # This caused the bot to keep confirming the wrong city after user said "לא"
                            if 'city' in self.lead_capture_state:
                                old_city = self.lead_capture_state.get('city')
                                del self.lead_capture_state['city']
                                # Also clear related city fields
                                self.lead_capture_state.pop('raw_city', None)
                                self.lead_capture_state.pop('city_confidence', None)
                                self.lead_capture_state.pop('city_needs_confirmation', None)
                                self.lead_capture_state.pop('city_needs_retry', None)
                                self.lead_capture_state.pop('city_autocorrected', None)
                                self.lead_capture_state.pop('city_corrected_by_user', None)
                                # Clear the last AI mentioned city so it doesn't get locked again
                                self._last_ai_mentioned_city = None
                                print(f"🗑️ [BUILD 308] CLEARED city from lead_capture_state: was '{old_city}'")
                                # Clear city_raw_attempts for fresh start
                                self.city_raw_attempts = []
                            
                            # 🔥 BUILD 308: POST-REJECTION COOL-OFF
                            # Set flag to make AI WAIT before speaking - give user time to provide correction
                            self._awaiting_user_correction = True
                            self._rejection_timestamp = time.time()
                            print(f"⏳ [BUILD 308] POST-REJECTION COOL-OFF - AI will wait for user to speak")
                        elif "לא" in transcript_stripped:
                            # Incidental "לא" - just log it, don't reset
                            print(f"ℹ️ [BUILD 310] Incidental 'לא' in '{transcript[:30]}' - NOT resetting verification")
                        
                        # Track conversation
                        self.conversation_history.append({"speaker": "user", "text": transcript, "ts": time.time()})
                        
                        # 🎯 SMART HANGUP: Extract lead fields from user speech as well
                        # 🔥 BUILD 307: Pass is_user_speech=True for proper city extraction
                        self._extract_lead_fields_from_ai(transcript, is_user_speech=True)
                        
                        # 🔥 BUILD 307: Handle user confirmation with "נכון" - lock city from AI's previous statement
                        confirmation_words = ["כן", "נכון", "בדיוק", "כן כן", "יופי", "מסכים"]
                        if any(word in transcript_lower for word in confirmation_words):
                            last_ai_city = getattr(self, '_last_ai_mentioned_city', None)
                            if last_ai_city and 'city' in getattr(self, 'required_lead_fields', []):
                                # User confirmed - lock the city!
                                if hasattr(self, 'stt_consistency_filter'):
                                    self.stt_consistency_filter.locked_city = last_ai_city
                                    self._update_lead_capture_state('city', last_ai_city)
                                    self._update_lead_capture_state('city_confidence', 100.0)
                                    print(f"🔒 [BUILD 307] User confirmed city with '{transcript[:20]}' → locked '{last_ai_city}'")
                        
                        # 🎯 Mark that we have pending AI response (AI will respond to this)
                        self.has_pending_ai_response = True
                        
                        # 🛡️ CHECK: Don't run NLP twice for same appointment
                        already_confirmed = getattr(self, 'appointment_confirmed_in_session', False)
                        if already_confirmed:
                            print(f"🛡️ [NLP] SKIP - Appointment already confirmed in this session")
                        else:
                            # Check for appointment confirmation after user speaks
                            print(f"🔍 [DEBUG] Calling NLP after user transcript: '{transcript[:50]}...'")
                            self._check_appointment_confirmation(transcript)
                        
                        # 🎯 BUILD 170.5: ALWAYS detect goodbye phrases in user transcript
                        # User saying goodbye should ALWAYS allow call to end
                        # 🔥 PROTECTION: Only detect goodbye if enough time passed since greeting
                        can_detect_goodbye = True
                        if self.greeting_completed_at is not None:
                            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
                            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                                can_detect_goodbye = False
                                print(f"🛡️ [PROTECTION] Ignoring user goodbye - only {elapsed_ms:.0f}ms since greeting")
                        
                        # 🔥 BUILD 170.5: ALWAYS set goodbye_detected when user says bye (no setting gate!)
                        if not self.pending_hangup and can_detect_goodbye:
                            if self._check_goodbye_phrases(transcript):
                                print(f"👋 [BUILD 170.5] User said goodbye - setting goodbye_detected=True")
                                self.goodbye_detected = True
                                
                                # 🔥 BUILD 172: Transition to CLOSING state when auto_end_on_goodbye is enabled
                                if self.auto_end_on_goodbye and self.call_state == CallState.ACTIVE:
                                    self.call_state = CallState.CLOSING
                                    print(f"📞 [STATE] Transitioning ACTIVE → CLOSING (user_goodbye, auto_end=True)")
                                
                                # If auto_end_on_goodbye is ON, send explicit instruction to AI
                                if self.auto_end_on_goodbye:
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        "[SERVER] הלקוח אמר שלום! סיים בצורה מנומסת - אמור 'תודה שהתקשרת, יום נפלא!' או משהו דומה."
                                    ))
                                
                                # 🔥 FALLBACK: If AI doesn't say closing phrase within 10s, disconnect anyway
                                asyncio.create_task(self._fallback_hangup_after_timeout(10, "user_goodbye"))
                        
                        # 🎯 BUILD 163: Check if all lead info is captured
                        # 🔥 BUILD 172 FIX: Only close after customer CONFIRMS the details!
                        if self.auto_end_after_lead_capture and not self.pending_hangup and not self.lead_captured:
                            if self._check_lead_captured():
                                # 🔥 CRITICAL: Check if customer already confirmed the details
                                if self.verification_confirmed:
                                    # ✅ Customer confirmed - NOW we can close
                                    print(f"✅ [BUILD 163] Lead captured AND confirmed - closing call")
                                    self.lead_captured = True
                                    
                                    # 🔥 BUILD 172: Transition to CLOSING state
                                    if self.call_state == CallState.ACTIVE:
                                        self.call_state = CallState.CLOSING
                                        print(f"📞 [STATE] Transitioning ACTIVE → CLOSING (lead_captured + confirmed)")
                                    
                                    # Send polite closing instruction
                                    asyncio.create_task(self._send_server_event_to_ai(
                                        "[SERVER] ✅ הלקוח אישר את הפרטים! סיים בצורה מנומסת - הודה ללקוח ואמור להתראות."
                                    ))
                                    asyncio.create_task(self._fallback_hangup_after_timeout(10, "lead_captured_confirmed"))
                                else:
                                    # ⏳ Fields collected but NOT confirmed yet - ask for verification
                                    # Only ask once (track with a flag)
                                    if not getattr(self, '_verification_prompt_sent', False):
                                        self._verification_prompt_sent = True
                                        print(f"⏳ [BUILD 172] Lead fields collected - waiting for customer confirmation")
                                        # AI should verify the details - don't close yet!
                                        asyncio.create_task(self._send_server_event_to_ai(
                                            "[SYSTEM] פרטים נאספו אבל הלקוח עדיין לא אישר! חזור על הפרטים ושאל 'האם הפרטים נכונים?' - המתן לאישור לפני סיום."
                                        ))
                    
                    # ✅ COST SAFETY: Transcription completed successfully
                    print(f"[SAFETY] Transcription successful (total failures: {self.transcription_failed_count})")
                
                elif event_type.startswith("error"):
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    print(f"❌ [REALTIME] Error event: {error_msg}")
                    # 🔒 Clear locks on error to prevent permanent stall
                    self.response_pending_event.clear()
                    self.active_response_id = None
                    # 🔥 CRITICAL: Reset greeting state on error to prevent hangup block
                    if self.is_playing_greeting:
                        print(f"🛡️ [ERROR CLEANUP] Resetting is_playing_greeting due to error")
                        self.is_playing_greeting = False
                        self.greeting_completed_at = time.time()  # Mark greeting as done
                
        except Exception as e:
            print(f"❌ [REALTIME] Audio receiver error: {e}")
            import traceback
            traceback.print_exc()
            # 🔥 CRITICAL: Reset greeting state on exception to prevent hangup block
            if self.is_playing_greeting:
                print(f"🛡️ [EXCEPTION CLEANUP] Resetting is_playing_greeting due to exception")
                self.is_playing_greeting = False
                self.greeting_completed_at = time.time()
        
        # 🔥 CRITICAL: Always reset greeting state when receiver ends
        if self.is_playing_greeting:
            print(f"🛡️ [EXIT CLEANUP] Resetting is_playing_greeting on receiver exit")
            self.is_playing_greeting = False
            if self.greeting_completed_at is None:
                self.greeting_completed_at = time.time()
        
        print(f"📥 [REALTIME] Audio receiver ended")
    
    async def _send_server_event_to_ai(self, message_text: str):
        """
        🔥 Send server-side message to AI via conversation.item.create
        Used for appointment validation feedback, calendar availability, etc.
        
        Args:
            message_text: Message to send to AI (in Hebrew)
        """
        if not self.realtime_client:
            print(f"⚠️ [SERVER_EVENT] No Realtime client - cannot send message")
            return
        
        try:
            # 🔥 BUILD 148 FIX: OpenAI Realtime API only accepts "input_text" type for conversation.item.create
            # System/assistant messages need special handling - use "user" role with special marker
            # The AI will understand this is server feedback and respond appropriately
            event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",  # 🔥 Must be "user" for conversation.item.create
                    "content": [
                        {
                            "type": "input_text",  # 🔥 Must be "input_text" (not "text"!)
                            "text": f"[SERVER] {message_text}"  # Prefix to distinguish from real user
                        }
                    ]
                }
            }
            
            await self.realtime_client.send_event(event)
            print(f"🔇 [SERVER_EVENT] Sent SILENTLY to AI: {message_text[:100]}")
            
            # 🎯 DEBUG: Track appointment_created messages
            if "appointment_created" in message_text:
                print(f"🔔 [APPOINTMENT] appointment_created message sent to AI!")
                print(f"🔔 [APPOINTMENT] Message content: {message_text}")
            
            # 🔥 BUILD 302: DON'T trigger response during barge-in!
            # If user just interrupted AI, don't let server_events revive old context
            if self.barge_in_active:
                print(f"⏸️ [SERVER_EVENT] Skipping trigger - barge-in active (message logged but no response)")
                return
            
            # 🔥 BUILD 200: Use central trigger_response for ALL response.create calls
            # The trigger_response function handles:
            # - Active response ID check (prevents "already has active response" errors)
            # - Response pending check (race condition prevention)
            # - Loop guard check (for inbound calls)
            is_appointment_msg = "appointment" in message_text.lower() or "תור" in message_text or "זמינות" in message_text
            reason = f"SERVER_EVENT:{message_text[:30]}"
            if is_appointment_msg:
                reason = f"APPOINTMENT:{message_text[:30]}"
            
            triggered = await self.trigger_response(reason)
            if not triggered:
                print(f"⏸️ [SERVER_EVENT] Response blocked by trigger_response guards")
            
        except Exception as e:
            print(f"❌ [SERVER_EVENT] Failed to send: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_realtime_barge_in(self):
        """
        🔥 ENHANCED BARGE-IN: Stop AI generation + playback when user speaks
        Sends response.cancel to Realtime API to stop text generation (not just audio!)
        """
        # 🛡️ FIX: PROTECT GREETING - Never cancel during greeting playback!
        if self.is_playing_greeting:
            print(f"🛡️ [PROTECT GREETING] Ignoring barge-in - greeting still playing")
            return
        
        print("[REALTIME] BARGE-IN triggered – user started speaking, CANCELING AI response")
        
        # 🔥 CRITICAL: Cancel active AI response generation (not just playback!)
        if self.active_response_id and self.realtime_client:
            try:
                import asyncio
                # Create event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Send response.cancel event
                cancel_event = {"type": "response.cancel"}
                future = asyncio.run_coroutine_threadsafe(
                    self.realtime_client.send_event(cancel_event),
                    loop
                )
                future.result(timeout=0.5)  # Wait max 0.5s
                print(f"✅ [BARGE-IN] Cancelled response {self.active_response_id}")
                self.active_response_id = None
            except Exception as e:
                print(f"⚠️ [BARGE-IN] Failed to cancel response: {e}")
        
        # Stop AI speaking flag (checked in audio output bridge)
        self.is_ai_speaking_event.clear()  # Thread-safe: AI stopped due to barge-in
        self.speaking = False  # 🔥 BUILD 165: SYNC with self.speaking flag
        self.last_ai_audio_ts = None
        self.ai_speaking_start_ts = None  # 🔥 FIX: Clear start timestamp
        
        # Clear any queued AI audio that hasn't been sent yet
        try:
            while not self.realtime_audio_out_queue.empty():
                self.realtime_audio_out_queue.get_nowait()
        except:
            pass
        
        # Send clear to Twilio to stop any audio in flight
        if not self.ws_connection_failed:
            try:
                self._tx_enqueue({"type": "clear"})
            except:
                pass
        
        # Reset barge-in state
        self.current_user_voice_start_ts = None
        
        print("🎤 [REALTIME] BARGE-IN complete – AI FULLY STOPPED, user can speak")
    
    async def _check_appointment_confirmation_async(self):
        """
        Check for appointment requests using GPT-4o-mini NLP parser
        Runs continuously in background thread, triggered after each message
        """
        # Skip if business_id not set yet
        if not self.business_id:
            print(f"⚠️ [NLP] No business_id - skipping")
            return
        
        # Skip if no conversation history
        if not self.conversation_history:
            print(f"⚠️ [NLP] No conversation history - skipping")
            return
        
        print(f"🔍 [NLP] ▶️ Analyzing conversation for appointment intent...")
        print(f"🔍 [NLP] Conversation history has {len(self.conversation_history)} messages")
        print(f"🔍 [NLP] Last 3 messages: {self.conversation_history[-3:]}")
        
        # Call GPT-4o-mini NLP parser
        result = await extract_appointment_request(
            self.conversation_history,
            self.business_id
        )
        
        print(f"🔍 [NLP] ◀️ NLP result: {result}")
        
        if not result or result.get("action") == "none":
            print(f"📭 [NLP] No appointment action detected (action={result.get('action') if result else 'None'})")
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
            
            crm_context = getattr(self, 'crm_context', None)
            if crm_context:
                # Context exists - save there
                if not crm_context.customer_name:
                    crm_context.customer_name = customer_name
                    print(f"✅ [NLP] Saved customer name to crm_context: {customer_name}")
            else:
                # Context doesn't exist yet - save to temporary cache
                self.pending_customer_name = customer_name
                print(f"✅ [NLP] Saved customer name to temporary cache: {customer_name}")
        
        # Fall back to saved name if NLP returns None
        if not customer_name:
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and crm_context.customer_name:
                customer_name = crm_context.customer_name
                print(f"🔄 [NLP] Retrieved customer name from crm_context: {customer_name}")
            elif hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                customer_name = self.pending_customer_name
                print(f"🔄 [NLP] Retrieved customer name from temporary cache: {customer_name}")
        
        print(f"🎯 [NLP] ✅ Detected action={action}, date={date_iso}, time={time_str}, name={customer_name}, confidence={confidence}")
        
        # 🔍 DEBUG: Check CRM context state
        crm_context = getattr(self, 'crm_context', None)
        if crm_context:
            print(f"🔍 [DEBUG] CRM context - name: '{crm_context.customer_name}', phone: '{crm_context.customer_phone}'")
        else:
            print(f"🔍 [DEBUG] No CRM context exists yet")
        
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
                    print(f"💾 [NLP] Saved date to pending_slot: {date_iso}")
                if time_str:
                    crm_context.pending_slot['time'] = time_str
                    print(f"💾 [NLP] Saved time to pending_slot: {time_str}")
        
        # 🔥 NEW: Handle "hours_info" action (user asking about business hours, NOT appointment!)
        if action == "hours_info":
            print(f"📋 [NLP] User asking for business hours info - responding with policy")
            try:
                # Load business hours from policy
                from server.policy.business_policy import get_business_policy
                policy = get_business_policy(self.business_id)
                
                if DEBUG: print(f"📊 [DEBUG] Policy loaded: allow_24_7={policy.allow_24_7}, opening_hours={policy.opening_hours}")
                
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
                    print(f"✅ [DEBUG] Sending hours to AI: {hours_text[:100]}...")
                    await self._send_server_event_to_ai(f"hours_info - {hours_text}")
                else:
                    print(f"⚠️ [DEBUG] No opening_hours in policy!")
                    await self._send_server_event_to_ai("hours_info - שעות הפעילות לא הוגדרו במערכת.")
            except Exception as e:
                print(f"❌ [ERROR] Failed to load business policy: {e}")
                import traceback
                traceback.print_exc()
                await self._send_server_event_to_ai("hours_info - לא הצלחתי לטעון את שעות הפעילות. אפשר ליצור קשר ישירות.")
            return
        
        # 🔥 NEW: Handle "ask" action (user asking for availability for specific date/time)
        if action == "ask":
            print(f"❓ [NLP] User asking for availability - checking slot...")
            
            # 🔥 BUILD 186: OUTBOUND CALLS - Skip scheduling entirely!
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if is_outbound:
                print(f"⚠️ [NLP] OUTBOUND call - skipping availability check (outbound follows prompt only)")
                return
            
            # 🔥 BUILD 186: CHECK IF CALENDAR SCHEDULING IS ENABLED
            call_config = getattr(self, 'call_config', None)
            if call_config and not call_config.enable_calendar_scheduling:
                print(f"⚠️ [NLP] Calendar scheduling is DISABLED - not checking availability")
                await self._send_server_event_to_ai("⚠️ קביעת תורים מושבתת כרגע. הסבר ללקוח שנציג יחזור אליו בהקדם.")
                return
            
            if not date_iso or not time_str:
                # User wants appointment but didn't specify date/time
                print(f"⚠️ [NLP] User wants appointment but no date/time - asking for it")
                await self._send_server_event_to_ai("need_datetime - שאל את הלקוח: באיזה תאריך ושעה היית רוצה לקבוע?")
                return
            
            # 🛡️ BUILD 149 FIX: Check if this slot was already marked as busy (prevent loop)
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and hasattr(crm_context, 'busy_slots'):
                busy_key = f"{date_iso}_{time_str}"
                if busy_key in crm_context.busy_slots:
                    print(f"🛡️ [GUARD] Slot {busy_key} already marked busy - skipping re-check to prevent loop")
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
                    print(f"✅ [NLP] Slot {date_iso} {time_str} is AVAILABLE!")
                    if crm_context:
                        crm_context.pending_slot = {
                            "date": date_iso,
                            "time": time_str,
                            "available": True
                        }
                    await self._send_server_event_to_ai(f"✅ פנוי! {date_iso} {time_str}")
                else:
                    # ❌ SLOT TAKEN - Find alternatives and inform AI
                    print(f"❌ [NLP] Slot {date_iso} {time_str} is TAKEN - finding alternatives...")
                    
                    # 🛡️ BUILD 149 FIX: Clear pending_slot and track busy slots to prevent loop
                    if crm_context:
                        crm_context.pending_slot = None  # Clear stale pending slot
                        # Track this slot as busy to prevent re-checking
                        if not hasattr(crm_context, 'busy_slots'):
                            crm_context.busy_slots = set()
                        busy_key = f"{date_iso}_{time_str}"
                        crm_context.busy_slots.add(busy_key)
                        print(f"🛡️ [GUARD] Marked slot {busy_key} as busy - will not recheck")
                    
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
                print(f"❌ [NLP] Error checking availability: {e}")
                import traceback
                traceback.print_exc()
                await self._send_server_event_to_ai("need_datetime - לא הצלחתי לבדוק זמינות. באיזה תאריך ושעה?")
            
            return
        
        # 🔥 NEW: Handle "confirm" action (user confirmed appointment)
        if action == "confirm":
            print(f"")
            print(f"=" * 80)
            print(f"🎯 [APPOINTMENT FLOW] ========== CONFIRM ACTION TRIGGERED ==========")
            print(f"=" * 80)
            
            # 🔥 BUILD 186: OUTBOUND CALLS - Skip scheduling entirely!
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            if is_outbound:
                print(f"⚠️ [APPOINTMENT FLOW] BLOCKED - OUTBOUND call (outbound follows prompt only)")
                return
            
            # 🔥 BUILD 186: CHECK IF CALENDAR SCHEDULING IS ENABLED
            # If disabled, do NOT attempt to create appointments - only collect leads
            call_config = getattr(self, 'call_config', None)
            if call_config and not call_config.enable_calendar_scheduling:
                print(f"⚠️ [APPOINTMENT FLOW] BLOCKED - Calendar scheduling is DISABLED for this business!")
                print(f"⚠️ [APPOINTMENT FLOW] Informing AI to redirect customer to human representative")
                await self._send_server_event_to_ai("⚠️ קביעת תורים מושבתת. הסבר ללקוח שנציג יחזור אליו בהקדם לקביעת פגישה.")
                return
            
            # 🛡️ CRITICAL GUARD: Check if appointment was already created in this session
            # This prevents the loop where NLP keeps detecting "confirm" from AI's confirmation message
            if getattr(self, 'appointment_confirmed_in_session', False):
                print(f"⚠️ [APPOINTMENT FLOW] BLOCKED - Appointment already created in this session!")
                print(f"⚠️ [APPOINTMENT FLOW] Ignoring duplicate confirm action to prevent loop")
                return
            
            # 🛡️ Also check CRM context flag
            crm_context = getattr(self, 'crm_context', None)
            if crm_context and crm_context.has_appointment_created:
                print(f"⚠️ [APPOINTMENT FLOW] BLOCKED - CRM context shows appointment already created!")
                print(f"⚠️ [APPOINTMENT FLOW] Ignoring duplicate confirm action to prevent loop")
                return
            
            print(f"📝 [FLOW STEP 1] NLP returned: action={action}, date={date_iso}, time={time_str}, name={customer_name}")
            print(f"📝 [FLOW STEP 1] confidence={confidence}")
            
            print(f"📝 [FLOW STEP 2] CRM context exists: {crm_context is not None}")
            
            # ✅ BUILD 145: FALLBACK - Use pending_slot if NLP didn't return date/time
            # This handles cases where user confirmed but NLP missed the time from earlier messages
            if crm_context and hasattr(crm_context, 'pending_slot') and crm_context.pending_slot:
                pending = crm_context.pending_slot
                print(f"📝 [FLOW STEP 3] pending_slot found: {pending}")
                
                # Use pending_slot values if NLP values are missing
                if not date_iso and pending.get('date'):
                    date_iso = pending['date']
                    print(f"📝 [FLOW STEP 3] Using date from pending_slot: {date_iso}")
                if not time_str and pending.get('time'):
                    time_str = pending['time']
                    print(f"📝 [FLOW STEP 3] Using time from pending_slot: {time_str}")
            else:
                print(f"📝 [FLOW STEP 3] No pending_slot available")
            
            # ✅ STEP 1: Validate we have date and time
            print(f"📝 [FLOW STEP 4] Checking date/time: date={date_iso}, time={time_str}")
            if not date_iso or not time_str:
                print(f"❌ [FLOW STEP 4] FAILED - Missing date/time! Asking AI to clarify")
                # Clear stale pending_slot to avoid loops
                if crm_context and hasattr(crm_context, 'pending_slot'):
                    crm_context.pending_slot = None
                    print(f"🧹 [FLOW STEP 4] Cleared stale pending_slot")
                # Ask AI to clarify the time
                await self._send_server_event_to_ai("need_datetime - חסרים פרטים לקביעת התור. שאל את הלקוח: לאיזה יום ושעה תרצה לקבוע?")
                return
            
            print(f"✅ [FLOW STEP 4] OK - Date/time valid: {date_iso} {time_str}")
            
            # ✅ STEP 2: Check if we have customer name and phone
            # 🔥 BUILD 182: Phone priority: 1) crm_context, 2) DTMF, 3) Caller ID
            customer_phone = None
            if crm_context and crm_context.customer_phone:
                customer_phone = crm_context.customer_phone
                print(f"📝 [FLOW STEP 5] Phone from crm_context: {customer_phone}")
            elif hasattr(self, 'customer_phone_dtmf') and self.customer_phone_dtmf:
                customer_phone = self.customer_phone_dtmf
                print(f"📝 [FLOW STEP 5] Phone from DTMF: {customer_phone}")
            elif hasattr(self, 'phone_number') and self.phone_number:
                # 🔥 BUILD 182: Use Caller ID as fallback!
                customer_phone = self.phone_number
                print(f"📝 [FLOW STEP 5] Phone from Caller ID: {customer_phone}")
            
            print(f"📝 [FLOW STEP 5] Checking customer info:")
            print(f"📝 [FLOW STEP 5]   - phone: {customer_phone}")
            print(f"📝 [FLOW STEP 5]   - name from NLP: {customer_name}")
            
            # 🔥 FALLBACK: If NLP didn't extract name, check temp cache and crm_context
            if not customer_name:
                if crm_context and crm_context.customer_name:
                    customer_name = crm_context.customer_name
                    print(f"📝 [FLOW STEP 5]   - name from crm_context: {customer_name}")
                elif hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    customer_name = self.pending_customer_name
                    print(f"📝 [FLOW STEP 5]   - name from temp cache: {customer_name}")
                    # CRITICAL: Write name back to crm_context so it's persisted!
                    if crm_context:
                        crm_context.customer_name = customer_name
                        print(f"📝 [FLOW STEP 5]   - hydrated temp cache → crm_context")
            
            # 🔥 BUILD 182: Check if business requires phone verification via DTMF
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(self.business_id)
            require_phone_verification = getattr(policy, 'require_phone_before_booking', False)
            print(f"📝 [FLOW STEP 5.5] Business setting require_phone_before_booking: {require_phone_verification}")
            
            # 🔥 BUILD 182: If we have caller ID and phone verification is NOT required, use it!
            if not customer_phone and hasattr(self, 'phone_number') and self.phone_number and not require_phone_verification:
                customer_phone = self.phone_number
                print(f"📝 [FLOW STEP 5.5] Using Caller ID (no phone verification required): {customer_phone}")
            
            # 🔥 Check if all required data is complete
            print(f"📝 [FLOW STEP 6] Checking if all data is complete...")
            
            # Priority 1: Name (ALWAYS ask for name first!)
            if not customer_name:
                print(f"❌ [FLOW STEP 6] BLOCKED - Need name first! Sending need_name event")
                await self._send_server_event_to_ai("need_name - שאל את הלקוח: על איזה שם לרשום את התור?")
                return
            
            # Priority 2: Phone - ONLY ask if require_phone_before_booking is True AND no phone available
            # 🔥 BUILD 186: Ask for DTMF (keypad) only when require_phone_before_booking=True
            # Otherwise, use Caller ID automatically - no verbal phone extraction needed!
            if not customer_phone:
                if require_phone_verification:
                    print(f"❌ [FLOW STEP 6] BLOCKED - Need phone (require_phone_before_booking=True)! Asking via DTMF")
                    await self._send_server_event_to_ai("need_phone_dtmf - בקש מהלקוח להקליד את מספר הטלפון שלו על המקשים ולסיים בסולמית (#).")
                    return
                else:
                    # 🔥 BUILD 182: Try to use caller ID one more time
                    if hasattr(self, 'phone_number') and self.phone_number:
                        customer_phone = self.phone_number
                        print(f"📝 [FLOW STEP 6] Using Caller ID as phone: {customer_phone}")
                    else:
                        print(f"⚠️ [FLOW STEP 6] No phone available but require_phone_before_booking=False")
                        print(f"⚠️ [FLOW STEP 6] Proceeding without phone (will use empty string)")
                        customer_phone = ""
            
            print(f"")
            print(f"✅ [FLOW STEP 6] ALL DATA COMPLETE!")
            print(f"✅ [FLOW STEP 6]   - name: {customer_name}")
            print(f"✅ [FLOW STEP 6]   - phone: {customer_phone}")
            print(f"✅ [FLOW STEP 6]   - date: {date_iso}")
            print(f"✅ [FLOW STEP 6]   - time: {time_str}")
            
            # 🛡️ BUILD 149 FIX: Set guard IMMEDIATELY when confirm action starts processing
            # This prevents barge-in from allowing re-entry into the confirm flow
            # The guard must be set BEFORE any awaits, as barge-in can happen at any time
            self.appointment_confirmed_in_session = True
            print(f"🛡️ [GUARD] Set appointment_confirmed_in_session=True EARLY to prevent re-entry")
            
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
            
            print(f"📝 [FLOW STEP 7] Calculated times:")
            print(f"📝 [FLOW STEP 7]   - start_dt: {start_dt.isoformat()}")
            print(f"📝 [FLOW STEP 7]   - duration: {slot_duration_min} minutes (from DB policy)")
            print(f"📝 [FLOW STEP 7]   - end_dt: {end_dt.isoformat()}")
            
            # ✅ STEP 1: Validate slot is within business hours AND check calendar availability
            print(f"📝 [FLOW STEP 8] Validating slot availability...")
            is_valid = validate_appointment_slot(self.business_id, start_dt)
            print(f"📝 [FLOW STEP 8] Slot validation result: {is_valid}")
            
            if not is_valid:
                print(f"❌ [FLOW STEP 8] FAILED - Slot outside business hours or taken!")
                # 🔥 Send feedback to AI
                await self._send_server_event_to_ai(f"השעה {time_str} ביום {date_iso} תפוסה או מחוץ לשעות העבודה. תציע שעה אחרת ללקוח.")
                return
            
            print(f"✅ [FLOW STEP 8] OK - Slot is available!")
            
            # 🛡️ STEP 2: DB-BASED DEDUPLICATION - Check CallSession table
            appt_hash = start_dt.isoformat()
            print(f"📝 [FLOW STEP 9] Checking for duplicate appointments...")
            print(f"📝 [FLOW STEP 9]   - appt_hash: {appt_hash}")
            print(f"📝 [FLOW STEP 9]   - call_sid: {self.call_sid}")
            
            # Check DB for duplicate
            try:
                from server.models_sql import CallSession
                app = _get_flask_app()
                with app.app_context():
                    call_session = CallSession.query.filter_by(call_sid=self.call_sid).first()
                    print(f"📝 [FLOW STEP 9]   - call_session exists: {call_session is not None}")
                    
                    if call_session and call_session.last_confirmed_slot == appt_hash:
                        print(f"⚠️ [FLOW STEP 9] SKIPPED - Duplicate detected! Appointment for {appt_hash} already created")
                        return
                    
                    print(f"✅ [FLOW STEP 9] OK - No duplicate found")
                    
                    # 🛡️ CRITICAL: customer_phone is guaranteed valid from previous checks
                    print(f"")
                    print(f"🚀 [FLOW STEP 10] ========== CREATING APPOINTMENT IN DATABASE ==========")
                    print(f"🚀 [FLOW STEP 10] Parameters:")
                    print(f"🚀 [FLOW STEP 10]   - business_id: {self.business_id}")
                    print(f"🚀 [FLOW STEP 10]   - customer_name: {customer_name}")
                    print(f"🚀 [FLOW STEP 10]   - customer_phone: {customer_phone}")
                    print(f"🚀 [FLOW STEP 10]   - start_iso: {start_dt.isoformat()}")
                    print(f"🚀 [FLOW STEP 10]   - end_iso: {end_dt.isoformat()}")
                    
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
                    
                    print(f"🚀 [FLOW STEP 10] create_appointment_from_realtime returned: {result}")
                    
                    # 🔥 ENHANCED: Handle appointment creation result with proper error handling
                    if result and isinstance(result, dict):
                        # Check if this is an error response
                        if not result.get("ok", True):
                            error_type = result.get("error", "unknown")
                            error_msg = result.get("message", "שגיאה לא ידועה")
                            
                            print(f"❌ [FLOW STEP 10] FAILED - {error_type}: {error_msg}")
                            
                            # 🔥 BUILD 182: Check if AI already said confirmation
                            ai_already_confirmed = getattr(self, '_ai_said_confirmed_without_approval', False)
                            
                            # 🔥 CRITICAL: Send appropriate server event based on error type
                            if error_type == "need_phone":
                                if ai_already_confirmed:
                                    # 🔥 BUILD 182: AI already said "קבעתי" - don't ask for DTMF!
                                    # Just apologize and try to proceed with Caller ID
                                    print(f"⚠️ [BUILD 182] AI already confirmed - NOT asking for DTMF!")
                                    caller_id = getattr(self, 'phone_number', None) or getattr(self, 'caller_number', None)
                                    if caller_id:
                                        print(f"📞 [BUILD 182] Using Caller ID as fallback: {caller_id}")
                                        # Retry with Caller ID
                                        customer_phone = caller_id
                                    else:
                                        # Proceed without phone - appointment already "confirmed" to customer
                                        await self._send_server_event_to_ai("✅ התור נקבע. הפרטים יישלחו אליך בהמשך.")
                                        return
                                else:
                                    logger.info(f"📞 [DTMF VERIFICATION] Requesting phone via DTMF - AI will ask user to press digits")
                                    await self._send_server_event_to_ai("חסר מספר טלפון. שאל: 'אפשר מספר טלפון? תלחץ עכשיו על הספרות בטלפון ותסיים בכפתור סולמית (#)'")
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
                        # ✅ Mark as created in DB to prevent duplicates
                        if call_session:
                            call_session.last_confirmed_slot = appt_hash
                            from server.db import db
                            db.session.commit()
                        
                        print(f"")
                        print(f"=" * 80)
                        print(f"✅✅✅ [FLOW STEP 11] APPOINTMENT CREATED SUCCESSFULLY! ✅✅✅")
                        print(f"=" * 80)
                        print(f"✅ [FLOW STEP 11]   - appointment_id: {appt_id}")
                        print(f"✅ [FLOW STEP 11]   - customer: {customer_name}")
                        print(f"✅ [FLOW STEP 11]   - phone: {customer_phone}")
                        print(f"✅ [FLOW STEP 11]   - datetime: {date_iso} {time_str}")
                        print(f"=" * 80)
                        print(f"")
                        
                        # 🛡️ BUILD 149 FIX: Set ALL guards BEFORE sending any message to AI
                        # This prevents race condition where NLP triggers from AI's response
                        self.appointment_confirmed_in_session = True
                        print(f"🔒 [GUARD] Set appointment_confirmed_in_session=True BEFORE AI event")
                        
                        # Update CRM context with appointment ID
                        if crm_context:
                            crm_context.last_appointment_id = appt_id
                            # 🔥 CRITICAL: Set flag - NOW AI is allowed to say "התור נקבע!"
                            crm_context.has_appointment_created = True
                            logger.info(f"✅ [APPOINTMENT VERIFICATION] Created appointment #{appt_id} in DB - has_appointment_created=True")
                            print(f"🔓 [GUARD] Appointment created - AI can now confirm to customer")
                        
                        # 🔥 BUILD 182: Clear the "AI confirmed without approval" flag
                        # Now appointment is created, hangup can proceed normally
                        if hasattr(self, '_ai_said_confirmed_without_approval'):
                            self._ai_said_confirmed_without_approval = False
                            print(f"✅ [BUILD 182] Cleared _ai_said_confirmed_without_approval - hangup allowed")
                            
                        # 🔥 BUILD 146: Clear pending_slot ONLY after successful appointment creation
                        if crm_context:
                            crm_context.pending_slot = None
                            print(f"🧹 [CONFIRM] Cleared pending_slot after successful creation")
                        
                        # 🔥 BUILD 149 FIX: Simplified confirmation message - don't instruct AI to "notify"
                        # Just state the fact. The system prompt already tells AI what to say.
                        await self._send_server_event_to_ai(f"✅ appointment_created: {customer_name}, {date_iso}, {time_str}")
                    else:
                        print(f"")
                        print(f"❌❌❌ [FLOW STEP 11] FAILED TO CREATE APPOINTMENT! ❌❌❌")
                        print(f"❌ [FLOW STEP 11] Result was None or had no appointment_id")
                        # 🔥 Send failure to AI
                        await self._send_server_event_to_ai("❌ שגיאה ביצירת התור. נסה שעה אחרת.")
            except Exception as e:
                print(f"")
                print(f"❌❌❌ [FLOW STEP 10] EXCEPTION DURING APPOINTMENT CREATION! ❌❌❌")
                print(f"❌ [FLOW STEP 10] Error: {e}")
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
        
        print(f"🔍 [DEBUG] _check_appointment_confirmation called with transcript: '{ai_transcript[:50] if ai_transcript else 'EMPTY'}...'")
        print(f"🔍 [DEBUG] Conversation history length: {len(self.conversation_history)}")
        
        # 🛡️ BUILD 149 FIX: Check guard FIRST - if appointment already confirmed, skip NLP entirely
        if getattr(self, 'appointment_confirmed_in_session', False):
            print(f"🛡️ [NLP] GUARD ACTIVE - appointment_confirmed_in_session=True, skipping NLP")
            return
        
        # 🛡️ Also check CRM context guard
        crm_context = getattr(self, 'crm_context', None)
        if crm_context and crm_context.has_appointment_created:
            print(f"🛡️ [NLP] GUARD ACTIVE - crm_context.has_appointment_created=True, skipping NLP")
            return
        
        # 🔥 CRITICAL: Create hash of conversation to prevent duplicate NLP runs
        # ⚠️ FIX #1: Remove timestamps from hash - only text matters!
        # ⚠️ FIX #2: Hash ONLY user messages (not AI/system) - prevents re-triggering when AI responds!
        user_messages_only = [
            msg.get("text", "") 
            for msg in self.conversation_history[-10:]  # Last 10 messages
            if msg.get("speaker") == "user"
        ]
        print(f"🔍 [DEBUG] User messages for hash: {user_messages_only}")
        conversation_str = json.dumps(user_messages_only, sort_keys=True)
        current_hash = hashlib.md5(conversation_str.encode()).hexdigest()
        print(f"🔍 [DEBUG] Current conversation hash: {current_hash[:8]}...")
        
        # Skip if already processed this exact conversation state (with 30s TTL)
        should_process = False
        with self.nlp_processing_lock:
            now = time.time()
            
            # 🛡️ BUILD 149 FIX: Check if another NLP thread is still running
            if self.nlp_is_processing:
                print(f"⏭️ [NLP] BLOCKED - Another NLP thread is still processing")
                return
            
            # Check if we should process (new hash OR expired TTL)
            if self.last_nlp_processed_hash is None:
                # First run
                print(f"🔍 [DEBUG] First NLP run - processing")
                should_process = True
            elif current_hash != self.last_nlp_processed_hash:
                # Different hash - always process
                print(f"🔍 [DEBUG] Hash changed ({self.last_nlp_processed_hash[:8] if self.last_nlp_processed_hash else 'None'} → {current_hash[:8]}) - processing")
                should_process = True
            elif (now - self.last_nlp_hash_timestamp) >= 30:
                # Same hash but TTL expired - reprocess
                print(f"🔄 [NLP] TTL expired - reprocessing same hash")
                should_process = True
            else:
                # Same hash within TTL - skip
                hash_age = now - self.last_nlp_hash_timestamp
                print(f"⏭️ [NLP] Skipping duplicate (hash={current_hash[:8]}..., age={hash_age:.1f}s)")
                return
            
            # 🛡️ Mark as processing BEFORE releasing lock to prevent race
            if should_process:
                self.nlp_is_processing = True
        
        if not should_process:
            print(f"🔍 [DEBUG] should_process=False - returning early")
            return
        
        print(f"🔍 [NLP] ✅ WILL PROCESS new conversation state (hash={current_hash[:8]}...)")
        print(f"🔍 [DEBUG] CRM context exists: {hasattr(self, 'crm_context') and self.crm_context is not None}")
        if hasattr(self, 'crm_context') and self.crm_context:
            print(f"🔍 [DEBUG] CRM data - name: '{self.crm_context.customer_name}', phone: '{self.crm_context.customer_phone}'")
        
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
        """⚡ BUILD 168.2: Optimized audio bridge - minimal logging"""
        if not hasattr(self, 'realtime_tx_frames'):
            self.realtime_tx_frames = 0
        if not hasattr(self, 'realtime_tx_bytes'):
            self.realtime_tx_bytes = 0
        
        TWILIO_FRAME_SIZE = 160  # 20ms at 8kHz μ-law
        audio_buffer = b''  # Rolling buffer for incomplete frames
        
        while not self.realtime_stop_flag:
            try:
                audio_b64 = self.realtime_audio_out_queue.get(timeout=0.1)
                if audio_b64 is None:
                    break
                
                import base64
                chunk_bytes = base64.b64decode(audio_b64)
                self.realtime_tx_bytes += len(chunk_bytes)
                
                if not self.stream_sid:
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
                    
                    try:
                        # 🔥 BUILD 181: Queue overflow protection
                        queue_size = self.tx_q.qsize()
                        if queue_size >= 1400:  # Near max (1500)
                            # Log overflow warning (throttled)
                            now = time.time()
                            if not hasattr(self, '_last_overflow_warning') or now - self._last_overflow_warning > 5:
                                print(f"⚠️ [AUDIO OVERFLOW] TX queue at {queue_size}/1500 - dropping oldest frames")
                                self._last_overflow_warning = now
                            # Drop 100 oldest frames to make room
                            for _ in range(100):
                                try:
                                    self.tx_q.get_nowait()
                                except queue.Empty:
                                    break
                        
                        self.tx_q.put_nowait(twilio_frame)
                        self.realtime_tx_frames += 1
                    except queue.Full:
                        # 🔥 BUILD 181: If still full after cleanup, drop oldest and retry
                        try:
                            self.tx_q.get_nowait()  # Remove oldest
                            self.tx_q.put_nowait(twilio_frame)  # Add new
                            self.realtime_tx_frames += 1
                        except (queue.Empty, queue.Full):
                            pass  # Last resort: skip this frame
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[AUDIO] Bridge error: {e}")
                break

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
            
            # ⚡ BUILD 168.2: Compact cost log (single line)
            logger.info(f"[COST] {call_duration:.0f}s ${total_cost:.4f} (₪{total_cost_nis:.2f})")
            
            return total_cost
            
        except Exception as e:
            print(f"❌ [COST] Error calculating cost: {e}")
            return 0.0
    
    def run(self):
        """⚡ BUILD 168.2: Streamlined main loop - minimal logging"""
        import json
        
        self.call_start_time = time.time()
        self.rx_frames = 0
        self.tx_frames = 0
        
        # ✅ FIX: stream_sid is None until START event - safe logging
        _orig_print(f"🔵 [CALL] run() started - waiting for START event...", flush=True)
        logger.info("[CALL] run() started - waiting for START event")
        
        try:
            while True:
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
                            print(f"⚠️ Unknown WebSocket type: {type(self.ws)}, available methods: {[m for m in dir(self.ws) if not m.startswith('_')]}", flush=True)
                            raise Exception(f"No compatible receive method found for {type(self.ws)}")
                        
                    if raw is None or raw == '':
                        print("📞 WebSocket connection closed normally", flush=True)
                        break
                        
                    # Handle both string and bytes
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8')
                        
                    evt = json.loads(raw)
                    et = evt.get("event")
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid JSON received: {str(raw)[:100] if raw else 'None'}... Error: {e}", flush=True)
                    continue
                except Exception as e:
                    print(f"⚠️ WebSocket receive error: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Try to continue, might be temporary - don't crash the connection
                    continue

                if et == "start":
                    # 🔥 BUILD 169: Generate unique session ID for logging
                    import uuid
                    self._call_session_id = f"SES-{uuid.uuid4().hex[:8]}"
                    
                    # 🔥 CRITICAL: Force print to bypass DEBUG override
                    _orig_print(f"🎯 [CALL DEBUG] START EVENT RECEIVED! session={self._call_session_id}", flush=True)
                    logger.info(f"[{self._call_session_id}] START EVENT RECEIVED - entering start handler")
                    
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
                        self.call_direction = custom_params.get("direction", "inbound")
                        self.outbound_lead_id = custom_params.get("lead_id")
                        self.outbound_lead_name = custom_params.get("lead_name")
                        self.outbound_template_id = custom_params.get("template_id")
                        self.outbound_business_id = custom_params.get("business_id")  # 🔒 SECURITY: Explicit business_id for outbound
                        self.outbound_business_name = custom_params.get("business_name")
                        
                        # 🔍 DEBUG: Log phone numbers and outbound params
                        print(f"\n📞 START EVENT (customParameters path):")
                        print(f"   customParams.From: {custom_params.get('From')}")
                        print(f"   customParams.CallFrom: {custom_params.get('CallFrom')}")
                        print(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        print(f"   ✅ self.to_number set to: '{self.to_number}'")
                        if self.call_direction == "outbound":
                            print(f"   📤 OUTBOUND CALL: lead={self.outbound_lead_name}, template={self.outbound_template_id}")
                        
                        # 🎯 DYNAMIC LEAD STATE: Add caller phone to lead capture state
                        if self.phone_number:
                            self._update_lead_capture_state('phone', self.phone_number)
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                        self.phone_number = evt.get("from") or evt.get("phone_number")
                        self.to_number = evt.get("to") or evt.get("called")
                        
                        # 🔥 BUILD 174: Outbound call parameters (direct format)
                        self.call_direction = evt.get("direction", "inbound")
                        self.outbound_lead_id = evt.get("lead_id")
                        self.outbound_lead_name = evt.get("lead_name")
                        self.outbound_template_id = evt.get("template_id")
                        self.outbound_business_id = evt.get("business_id")  # 🔒 SECURITY: Explicit business_id for outbound
                        self.outbound_business_name = evt.get("business_name")
                        
                        # 🔍 DEBUG: Log phone number on start
                        print(f"\n📞 START EVENT - Phone numbers:")
                        print(f"   from field: {evt.get('from')}")
                        print(f"   phone_number field: {evt.get('phone_number')}")
                        print(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        
                        # 🎯 DYNAMIC LEAD STATE: Add caller phone to lead capture state
                        if self.phone_number:
                            self._update_lead_capture_state('phone', self.phone_number)
                        
                    self.last_rx_ts = time.time()
                    self.last_keepalive_ts = time.time()  # ✅ התחל keepalive
                    self.t0_connected = time.time()  # ⚡ [T0] WebSocket connected
                    print(f"🎯 [T0={time.time():.3f}] WS_START sid={self.stream_sid} call_sid={self.call_sid} from={self.phone_number} to={getattr(self, 'to_number', 'N/A')} mode={self.mode}")
                    if self.call_sid:
                        stream_registry.mark_start(self.call_sid)
                    
                    # 🚀 PARALLEL STARTUP: Start OpenAI connection AND DB query simultaneously!
                    logger.info(f"[CALL DEBUG] START event received: call_sid={self.call_sid}, to_number={getattr(self, 'to_number', 'N/A')}")
                    
                    # 🔥 STEP 1: Start OpenAI thread IMMEDIATELY (connects while DB runs)
                    if USE_REALTIME_API and not self.realtime_thread:
                        t_realtime_start = time.time()
                        delta_from_t0 = (t_realtime_start - self.t0_connected) * 1000
                        _orig_print(f"🚀 [PARALLEL] Starting OpenAI at T0+{delta_from_t0:.0f}ms (BEFORE DB query!)", flush=True)
                        
                        self.realtime_thread = threading.Thread(
                            target=self._run_realtime_mode_thread,
                            daemon=True
                        )
                        self.realtime_thread.start()
                        self.background_threads.append(self.realtime_thread)
                        
                        realtime_out_thread = threading.Thread(
                            target=self._realtime_audio_out_loop,
                            daemon=True
                        )
                        realtime_out_thread.start()
                        self.background_threads.append(realtime_out_thread)
                    
                    # 🔥 STEP 2: DB query runs IN PARALLEL with OpenAI connection
                    t_biz_start = time.time()
                    try:
                        app = _get_flask_app()
                        with app.app_context():
                            business_id, greet = self._identify_business_and_get_greeting()
                            
                        t_biz_end = time.time()
                        print(f"⚡ DB QUERY: business_id={business_id} in {(t_biz_end-t_biz_start)*1000:.0f}ms")
                        logger.info(f"[CALL DEBUG] Business ready in {(t_biz_end-t_biz_start)*1000:.0f}ms")
                        
                        # 🔥 SAFETY: Only set defaults if fields are truly None (preserve valid 0 or empty)
                        if self.business_id is None:
                            self.business_id = 1
                            self.business_name = "העסק"
                            print(f"🔒 [DEFAULTS] No business_id from DB - using fallback=1")
                        if not hasattr(self, 'bot_speaks_first'):
                            self.bot_speaks_first = True
                        
                    except Exception as e:
                        import traceback
                        logger.error(f"[CALL-ERROR] Business identification failed: {e}")
                        # Use helper with force_greeting=True to ensure greeting fires
                        self._set_safe_business_defaults(force_greeting=True)
                        greet = None  # AI will improvise
                    
                    # ⚡ STREAMING STT: Initialize ONLY if NOT using Realtime API
                    if not USE_REALTIME_API:
                        self._init_streaming_stt()
                        print("✅ Google STT initialized (USE_REALTIME_API=False)")
                    
                    # 🚀 DEFERRED: Call log + recording run in background thread (non-blocking)
                    def _deferred_call_setup():
                        try:
                            app = _get_flask_app()
                            with app.app_context():
                                if self.call_sid and not getattr(self, '_call_log_created', False):
                                    self._create_call_log_on_start()
                                    self._call_log_created = True
                                    self._start_call_recording()
                        except Exception as e:
                            print(f"⚠️ Deferred call setup failed: {e}")
                    
                    # Start deferred setup in background (doesn't block greeting)
                    threading.Thread(target=_deferred_call_setup, daemon=True).start()
                    
                    # ✅ ברכה מיידית - בלי השהיה!
                    if not self.tx_running:
                        self.tx_running = True
                        self.tx_thread.start()
                    
                    # 🔥 STEP 3: Store greeting and signal event (OpenAI thread is waiting!)
                    if not self.greeting_sent and USE_REALTIME_API:
                        self.t1_greeting_start = time.time()
                        if greet:
                            print(f"🎯 [T1={self.t1_greeting_start:.3f}] STORING GREETING FOR REALTIME!")
                            self.greeting_text = greet
                            if not hasattr(self, 'greeting_sent'):
                                self.greeting_sent = False
                            print(f"✅ [REALTIME] Greeting stored: '{greet[:50]}...' (len={len(greet)})")
                        else:
                            print(f"🎯 [T1={self.t1_greeting_start:.3f}] NO GREETING - AI will speak first!")
                            self.greeting_text = None
                            self.greeting_sent = True
                    
                    # 🚀 SIGNAL: Tell OpenAI thread that business info is ready!
                    total_startup_ms = (time.time() - self.t0_connected) * 1000
                    print(f"🚀 [PARALLEL] Signaling business info ready at T0+{total_startup_ms:.0f}ms")
                    self.business_info_ready_event.set()
                    
                    # Note: Realtime thread was already started above (BEFORE DB query)
                    
                    # 🎵 GOOGLE TTS: Send greeting via Google TTS if NOT using Realtime
                    if not self.greeting_sent and not USE_REALTIME_API:
                        self.t1_greeting_start = time.time()  # ⚡ [T1] Greeting start
                        print(f"🎯 [T1={self.t1_greeting_start:.3f}] SENDING IMMEDIATE GREETING! (Δ={(self.t1_greeting_start - self.t0_connected)*1000:.0f}ms from T0)")
                        try:
                            self._speak_greeting(greet)  # ✅ פונקציה מיוחדת לברכה ללא sleep!
                            self.t2_greeting_end = time.time()  # ⚡ [T2] Greeting end
                            print(f"🎯 [T2={self.t2_greeting_end:.3f}] GREETING_COMPLETE! (Duration={(self.t2_greeting_end - self.t1_greeting_start)*1000:.0f}ms)")
                            self.greeting_sent = True
                        except Exception as e:
                            print(f"❌ CRITICAL ERROR sending greeting: {e}")
                            import traceback
                            traceback.print_exc()
                    continue

                if et == "media":
                    self.rx += 1
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
                            print(f"⏱️ [BUILD 166] Speech timeout after {elapsed:.1f}s - noise gate RE-ENABLED")
                    
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
                                self.vad_threshold = 180.0  # Hebrew speech baseline
                                logger.warning(f"🎛️ [VAD] TIMEOUT - using baseline threshold=180")
                                print(f"🎛️ VAD TIMEOUT - using baseline threshold=180")
                            else:
                                # Adaptive: noise + 100, capped at 200 for quiet speakers
                                self.vad_threshold = min(200.0, self.noise_floor + 100.0)
                                logger.info(f"✅ [VAD] Calibrated: noise={self.noise_floor:.1f}, threshold={self.vad_threshold:.1f}")
                                print(f"🎛️ VAD CALIBRATED (noise={self.noise_floor:.1f}, threshold={self.vad_threshold:.1f})")
                            self.is_calibrated = True
                    
                    # 🚀 REALTIME API: Route audio to Realtime if enabled
                    if USE_REALTIME_API and self.realtime_thread and self.realtime_thread.is_alive():
                        # 🛡️ BUILD 168.5 FIX: Block audio enqueue during greeting!
                        # OpenAI's server-side VAD detects incoming audio and cancels the greeting.
                        # Block audio until greeting finishes OR user has already spoken.
                        if self.is_playing_greeting and not self.user_has_spoken:
                            # Log once
                            if not hasattr(self, '_greeting_enqueue_block_logged'):
                                print(f"🛡️ [GREETING PROTECT] Blocking audio ENQUEUE - greeting in progress")
                                self._greeting_enqueue_block_logged = True
                            continue  # Don't enqueue audio during greeting
                        
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
                        # Speech threshold = 3x noise floor, minimum 300 RMS (filters quiet echo)
                        rms_speech_threshold = max(noise_floor_rms * 3.0, 300.0)
                        is_above_speech = rms > rms_speech_threshold
                        
                        # Count consecutive frames above RMS speech threshold
                        if is_above_speech:
                            self._echo_gate_consec_frames += 1
                        else:
                            # Reset quickly when audio drops - echo is intermittent
                            self._echo_gate_consec_frames = 0
                        
                        # STRICT barge-in detection: 5+ consecutive frames (100ms) = real speech
                        # Echo spikes are typically 1-3 frames, real speech is sustained
                        ECHO_GATE_MIN_FRAMES = 5
                        is_likely_real_speech = self._echo_gate_consec_frames >= ECHO_GATE_MIN_FRAMES
                        
                        if self.is_ai_speaking_event.is_set():
                            # AI is actively speaking - block ALL audio UNLESS proven barge-in
                            if not is_likely_real_speech and not self.barge_in_active and not self._realtime_speech_active:
                                # Block - this is echo or noise
                                if not hasattr(self, '_echo_gate_logged') or not self._echo_gate_logged:
                                    print(f"🛡️ [ECHO GATE] Blocking audio - AI speaking (rms={rms:.0f}, frames={self._echo_gate_consec_frames}/{ECHO_GATE_MIN_FRAMES})")
                                    self._echo_gate_logged = True
                                continue
                            elif is_likely_real_speech:
                                # 5+ frames = real barge-in, let it through
                                if not hasattr(self, '_echo_barge_logged'):
                                    print(f"🎤 [ECHO GATE] BARGE-IN detected: {self._echo_gate_consec_frames} sustained frames (rms={rms:.0f})")
                                    self._echo_barge_logged = True
                        
                        # Check echo decay period (800ms after AI stops speaking)
                        if hasattr(self, '_ai_finished_speaking_ts') and self._ai_finished_speaking_ts:
                            echo_decay_ms = (time.time() - self._ai_finished_speaking_ts) * 1000
                            if echo_decay_ms < POST_AI_COOLDOWN_MS:
                                # Still in echo decay period - block unless proven real speech
                                if not is_likely_real_speech and not self._realtime_speech_active and not self.barge_in_active:
                                    if not hasattr(self, '_echo_decay_logged') or not self._echo_decay_logged:
                                        print(f"🛡️ [ECHO GATE] Blocking - echo decay ({echo_decay_ms:.0f}ms, frames={self._echo_gate_consec_frames})")
                                        self._echo_decay_logged = True
                                    continue
                            else:
                                # Echo decay complete - reset log flags for next AI response
                                self._echo_gate_logged = False
                                self._echo_decay_logged = False
                                self._echo_barge_logged = False
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
                        
                        # 🔥 BUILD 309: SIMPLE_MODE - Trust Twilio + OpenAI completely
                        # 🔥 BUILD 303: During barge-in, BYPASS ALL FILTERS - trust OpenAI's VAD
                        # Also bypass during _realtime_speech_active (OpenAI VAD detected speech)
                        if SIMPLE_MODE:
                            should_send_audio = True  # SIMPLE_MODE: always send audio to OpenAI
                            is_noise = False  # Trust OpenAI's VAD
                        elif self.barge_in_active or self._realtime_speech_active:
                            should_send_audio = True  # Send EVERYTHING during barge-in or active speech
                            is_noise = False  # Force override noise flag too
                        else:
                            should_send_audio = (has_sustained_speech or speech_bypass_active) and not is_noise
                        
                        # 🔥 BUILD 165: ONLY send audio above noise threshold AND sustained speech!
                        if should_send_audio:
                            try:
                                # 🔍 DEBUG: Log first few frames from Twilio
                                if not hasattr(self, '_twilio_audio_chunks_sent'):
                                    self._twilio_audio_chunks_sent = 0
                                self._twilio_audio_chunks_sent += 1
                                
                                if self._twilio_audio_chunks_sent <= 3:
                                    first5_bytes = ' '.join([f'{b:02x}' for b in mulaw[:5]])
                                    print(f"[REALTIME] sending audio TO OpenAI: chunk#{self._twilio_audio_chunks_sent}, μ-law bytes={len(mulaw)}, first5={first5_bytes}, rms={rms:.0f}, consec_frames={self._consecutive_voice_frames}")
                                
                                self.realtime_audio_in_queue.put_nowait(b64)
                            except queue.Full:
                                pass
                        else:
                            # 🔥 BUILD 171: Enhanced logging for debugging
                            if not hasattr(self, '_noise_reject_count'):
                                self._noise_reject_count = 0
                            self._noise_reject_count += 1
                            # Log every 100 rejected frames with more detail
                            if self._noise_reject_count % 100 == 0:
                                reason = "noise" if is_noise else f"insufficient_consec_frames({self._consecutive_voice_frames}/{MIN_CONSECUTIVE_VOICE_FRAMES})"
                                print(f"🔇 [AUDIO GATE] Blocked {self._noise_reject_count} frames (rms={rms:.0f}, reason={reason})")
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
                                print(f"⚠️ [STT] No streaming session for {self.call_sid[:8]} - using fallback")
                                self._session_warning_logged = True
                    
                    # 🔥 BUILD 165: RMS already calculated above at line 2937 (before noise gate)
                    # No need to recalculate - reuse the 'rms' variable
                    
                    # 🔥 BUILD 165: BALANCED BARGE-IN - Filter noise while allowing speech
                    if USE_REALTIME_API and self.realtime_thread and self.realtime_thread.is_alive():
                        # 🔍 DEBUG: Log AI speaking state every 50 frames (~1 second)
                        if not hasattr(self, '_barge_in_debug_counter'):
                            self._barge_in_debug_counter = 0
                        self._barge_in_debug_counter += 1
                        
                        if self._barge_in_debug_counter % 50 == 0:
                            print(f"🔍 [BARGE-IN DEBUG] is_ai_speaking={self.is_ai_speaking_event.is_set()}, "
                                  f"user_has_spoken={self.user_has_spoken}, waiting_for_dtmf={self.waiting_for_dtmf}, "
                                  f"rms={rms:.0f}, voice_frames={self.barge_in_voice_frames}")
                        
                        # 🔥 BUILD 165: NOISE GATE - already checked via is_noise flag
                        # 🔥 BUILD 302: Skip noise check during barge-in - trust OpenAI's VAD
                        if is_noise and not self.barge_in_active:
                            # Pure noise - don't count for barge-in
                            self.barge_in_voice_frames = max(0, self.barge_in_voice_frames - 1)
                            continue
                        
                        # Only allow barge-in if AI is speaking
                        if self.is_ai_speaking_event.is_set() and not self.waiting_for_dtmf:
                            # 🎯 FIX: Allow barge-in if user has spoken OR greeting finished
                            can_barge = self.user_has_spoken or self.barge_in_enabled_after_greeting
                            if not can_barge:
                                self.barge_in_voice_frames = 0
                                continue
                            
                            # 🛡️ PROTECT GREETING: Never barge-in during greeting!
                            if self.is_playing_greeting:
                                self.barge_in_voice_frames = 0
                                continue
                            
                            current_time = time.monotonic()
                            time_since_tts_start = current_time - self.speaking_start_ts if hasattr(self, 'speaking_start_ts') and self.speaking_start_ts else 999
                            
                            # 🔥 BUILD 164B: 150ms grace period
                            grace_period = 0.15  # 150ms grace period
                            if time_since_tts_start < grace_period:
                                self.barge_in_voice_frames = 0
                                continue
                            
                            # 🔥 BUILD 164B: RMS > 200 for speech detection (typical speech is 180-500)
                            speech_threshold = MIN_SPEECH_RMS  # 200
                            
                            # 🔥 BUILD 169: Require 700ms continuous speech (35 frames @ 20ms)
                            # Per architect: Increased from 220ms to prevent AI cutoff on background noise
                            if rms >= speech_threshold:
                                self.barge_in_voice_frames += 1
                                # 🔥 ARCHITECT FIX: Use BARGE_IN_VOICE_FRAMES constant, not hardcoded 11
                                if self.barge_in_voice_frames >= BARGE_IN_VOICE_FRAMES:
                                    print(f"🔥 [BARGE-IN] TRIGGERED! rms={rms:.0f} >= {speech_threshold:.0f}, "
                                          f"continuous={self.barge_in_voice_frames} frames ({BARGE_IN_VOICE_FRAMES*20}ms)")
                                    logger.info(f"[BARGE-IN] User speech detected while AI speaking "
                                              f"(rms={rms:.1f}, frames={self.barge_in_voice_frames})")
                                    self._handle_realtime_barge_in()
                                    self.barge_in_voice_frames = 0
                                    continue
                            else:
                                # Voice dropped below threshold - gradual reset
                                self.barge_in_voice_frames = max(0, self.barge_in_voice_frames - 2)
                    
                    # 🔥 BUILD 165: Calibration already done above (before audio routing)
                    # No duplicate calibration needed here
                    
                    # 🔥 BUILD 165: Voice detection with balanced threshold
                    if self.is_calibrated:
                        is_strong_voice = rms > self.vad_threshold
                    else:
                        # Before calibration - use 180 RMS baseline (Hebrew speech)
                        is_strong_voice = rms > 180.0
                    
                    # ✅ FIXED: Update last_voice_ts only with VERY strong voice
                    current_time = time.time()
                    # ✅ EXTRA CHECK: Only if RMS is significantly above threshold
                    if is_strong_voice and rms > (getattr(self, 'vad_threshold', 200) * 1.2):
                        self.last_voice_ts = current_time
                        # 🔧 Reduced logging spam - max once per 3 seconds
                        if not hasattr(self, 'last_debug_ts') or (current_time - self.last_debug_ts) > 3.0:
                            print(f"🎙️ REAL_VOICE: rms={rms:.1f} > threshold={getattr(self, 'vad_threshold', 'uncalibrated'):.1f}")
                            self.last_debug_ts = current_time
                    
                    # חישוב דממה אמיתי - מאז הקול האחרון! 
                    # אם אין קול בכלל, דממה = 0 (כדי שלא נתקע)
                    silence_time = (current_time - self.last_voice_ts) if self.last_voice_ts > 0 else 0
                    
                    # ✅ לוגים נקיים - רק אירועים חשובים (לא כל frame)  
                    
                    # 🔒 CRITICAL FIX: אם המערכת מדברת - לא להאזין בכלל!
                    # אל תעבד אודיו, אל תאסוף, אל תבדוק VAD - SKIP COMPLETELY!
                    # 🔥 BUILD 165: Only skip for Realtime API (which handles barge-in above)
                    # Fallback mode needs to continue to process barge-in below
                    if self.speaking and USE_REALTIME_API:
                        self.buf.clear()
                        self.voice_in_row = 0  # Reset barge-in counter
                        continue  # ← SKIP EVERYTHING - Realtime barge-in handled above
                    
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
                                print(f"[BARGE-IN FALLBACK] User speech detected (rms={rms:.1f}, threshold={speech_threshold:.1f})")
                                
                                # Stop AI speaking
                                self.speaking = False
                                
                                # Clean up state
                                self.state = STATE_LISTEN
                                self.processing = False
                                self.buf.clear()
                                self.last_voice_ts = current_time
                                self.voice_in_row = 0
                                
                                print("🎤 BARGE-IN -> LISTENING (user can speak now)")
                                
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
                                        print(f"🔊 PARTIAL (best): '{text}' ({len(text)} chars)")
                                    else:
                                        print(f"🔊 PARTIAL (ignored): '{text}' ({len(text)} chars) - keeping '{current_best}' ({len(current_best)} chars)")
                                
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
                                print(f"⚡⚡⚡ EARLY EOU on strong partial: '{last_partial}' ({dur:.1f}s, {silence_time:.2f}s silence)")
                                # קפיצה מיידית לעיבוד!
                                silent = True
                                buffer_big_enough = True
                            
                            # סוף מבע: דממה מספקת OR זמן יותר מדי OR באפר גדול עם שקט
                            if ((silent and buffer_big_enough) or too_long) and dur >= min_duration:
                                print(f"🎤 END OF UTTERANCE: {dur:.1f}s audio, conversation #{self.conversation_id}")
                                
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
                                
                                print(f"🧠 STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                                
                                try:
                                    self._process_utterance_safe(utt_pcm, current_id)
                                except Exception as proc_err:
                                    print(f"❌ Audio processing failed for conversation #{current_id}: {proc_err}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continue without crashing WebSocket
                                finally:
                                    self.processing = False
                                    if self.state == STATE_THINK:
                                        self.state = STATE_LISTEN
                                    print(f"✅ Processing complete for conversation #{current_id}")
                    
                    # ✅ WebSocket Keepalive - מונע נפילות אחרי 5 דקות
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
                                    print(f"💓 WS_KEEPALIVE #{self.heartbeat_counter} (prevents 5min timeout)")
                            except Exception as e:
                                print(f"⚠️ Keepalive failed: {e}")
                        else:
                            print(f"💔 SKIPPING keepalive - WebSocket connection failed")
                    
                    # ✅ Watchdog: וודא שלא תקועים במצב + EOU כפויה
                    if self.processing and (current_time - self.processing_start_ts) > 2.5:
                        print("⚠️ PROCESSING TIMEOUT - forcing reset")
                        self.processing = False
                        self.state = STATE_LISTEN
                        self.buf.clear()
                    
                    # ✅ LONGER speaking timeout to prevent cutoff mid-sentence
                    if self.speaking and (current_time - self.speaking_start_ts) > 15.0:
                        print("⚠️ SPEAKING TIMEOUT - forcing reset after 15s")  
                        self.speaking = False
                        self.state = STATE_LISTEN
                    
                    # ✅ EOU חירום: מכריח עיבוד אם הבאפר גדול מדי
                    if (not self.processing and self.state == STATE_LISTEN and 
                        len(self.buf) > 96000 and  # ✅ FIX: 6.0s של אודיו (לא קוטע משפטים ארוכים!)
                        silence_time > 2.0):      # ✅ FIX: 2.0s שקט לחירום - שקט אמיתי!
                        print(f"🚨 EMERGENCY EOU: {len(self.buf)/(2*SR):.1f}s audio, silence={silence_time:.2f}s")
                        # כפה EOU
                        self.processing = True
                        self.processing_start_ts = current_time
                        self.state = STATE_THINK
                        current_id = self.conversation_id
                        self.conversation_id += 1
                        
                        utt_pcm = bytes(self.buf)
                        self.buf.clear()
                        self.last_voice_ts = 0
                        
                        print(f"🧠 EMERGENCY STATE -> PROCESSING | len={len(utt_pcm)} | silence_ms={silence_time*1000:.0f}")
                        
                        try:
                            self._process_utterance_safe(utt_pcm, current_id)
                        except Exception as proc_err:
                            print(f"❌ Emergency audio processing failed for conversation #{current_id}: {proc_err}")
                            import traceback
                            traceback.print_exc()
                            # Continue without crashing WebSocket
                        finally:
                            self.processing = False
                            if self.state == STATE_THINK:
                                self.state = STATE_LISTEN
                            print(f"✅ Emergency processing complete for conversation #{current_id}")
                    
                    continue
                
                if et == "dtmf":
                    # ⚡ BUILD 121: DTMF digit collection for phone number input
                    digit = evt.get("dtmf", {}).get("digit", "")
                    print(f"📞 DTMF pressed: {digit} (buffer={self.dtmf_buffer})")
                    
                    if digit == "#":
                        # End of input - process collected digits
                        if not self.dtmf_buffer:
                            # 🎯 תרחיש 1: סולמית בלבד = דילוג
                            print(f"⏭️ DTMF skip: empty buffer, user skipped phone input")
                            self.waiting_for_dtmf = False
                            
                            # Inject skip message to AI
                            skip_text = "אני מדלג על מתן המספר"
                            print(f"🎯 DTMF skip -> AI: '{skip_text}'")
                            
                            try:
                                self._process_dtmf_skip()
                            except Exception as e:
                                print(f"❌ DTMF skip processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        elif len(self.dtmf_buffer) >= 9:
                            # 🎯 תרחיש 2: ספרות + # = שליחה
                            phone_number = self.dtmf_buffer
                            print(f"✅ DTMF phone collected: {phone_number}")
                            
                            # Clear buffer
                            self.dtmf_buffer = ""
                            self.waiting_for_dtmf = False
                            
                            # Inject as if customer said the number
                            hebrew_text = f"המספר שלי הוא {phone_number}"
                            print(f"🎯 DTMF -> AI: '{hebrew_text}'")
                            
                            # Process as normal utterance (trigger AI response)
                            try:
                                self._process_dtmf_phone(phone_number)
                            except Exception as e:
                                print(f"❌ DTMF processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            # Buffer too short
                            print(f"⚠️ DTMF input too short: {self.dtmf_buffer} (need 9+ digits)")
                            # Speak error message
                            self._speak_tts("המספר קצר מדי, נא להקיש 9 ספרות לפחות או לחץ סולמית כדי לדלג")
                        
                        # Reset buffer anyway
                        self.dtmf_buffer = ""
                        self.waiting_for_dtmf = False
                        
                    elif digit == "*":
                        # Clear/restart input
                        print(f"🔄 DTMF cleared (was: {self.dtmf_buffer})")
                        self.dtmf_buffer = ""
                        # Don't speak - just clear buffer
                        
                    elif digit.isdigit():
                        # Append digit
                        self.dtmf_buffer += digit
                        print(f"📝 DTMF buffer: {self.dtmf_buffer}")
                        
                        # 🔥 AUTO-SUBMIT: If we have 10 digits (Israeli mobile), auto-process without waiting for #
                        if len(self.dtmf_buffer) == 10:
                            phone_number = self.dtmf_buffer
                            print(f"✅ DTMF auto-submit (10 digits): {phone_number}")
                            
                            # Clear buffer
                            self.dtmf_buffer = ""
                            self.waiting_for_dtmf = False
                            
                            # Process the phone number
                            try:
                                self._process_dtmf_phone(phone_number)
                            except Exception as e:
                                print(f"❌ DTMF auto-submit processing failed: {e}")
                                import traceback
                                traceback.print_exc()
                    
                    continue

                if et == "mark":
                    # ✅ סימון TTS הושלם - חזור להאזנה
                    mark_name = evt.get("mark", {}).get("name", "")
                    if mark_name == "assistant_tts_end":
                        print("🎯 TTS_MARK_ACK: assistant_tts_end -> LISTENING")
                        self.speaking = False
                        self.state = STATE_LISTEN
                        self.mark_pending = False
                        self.last_tts_end_ts = time.time()
                        # איפוס חשוב למערכת VAD
                        self.last_voice_ts = 0
                        self.voice_in_row = 0
                        print("🎤 STATE -> LISTENING | buffer_reset")
                    elif mark_name.startswith("heartbeat_"):
                        # אישור keepalive - התעלם
                        pass
                    continue

                if et == "stop":
                    print(f"WS_STOP sid={self.stream_sid} rx={self.rx} tx={self.tx}")
                    # ✅ CRITICAL: סיכום שיחה בסיום
                    self._finalize_call_on_stop()
                    # Send close frame properly
                    try:
                        if hasattr(self.ws, 'close'):
                            self.ws.close()
                    except:
                        pass
                    break

        except ConnectionClosed as e:
            print(f"📞 WS_CLOSED sid={self.stream_sid} rx={self.rx} tx={self.tx} reason=ConnectionClosed")
            # ✅ ניסיון התאוששות אם השיחה עדיין פעילה
            if self.call_sid:
                print(f"🔄 WS connection lost for active call {self.call_sid} - recovery might be possible via Twilio REST API")
        except Exception as e:
            print(f"❌ WS_ERROR sid={self.stream_sid}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 🔥 BUILD 169: Enhanced disconnect logging
            session_id = getattr(self, '_call_session_id', 'N/A')
            call_duration = time.time() - getattr(self, 'call_start_time', time.time())
            business_id = getattr(self, 'business_id', 'N/A')
            print(f"📞 [{session_id}] CALL ENDED - duration={call_duration:.1f}s, business_id={business_id}, rx={self.rx}, tx={self.tx}")
            logger.info(f"[{session_id}] DISCONNECT - duration={call_duration:.1f}s, business={business_id}")
            
            # ⚡ STREAMING STT: Close session at end of call
            self._close_streaming_stt()
            
            # 🚀 REALTIME API: Signal threads to stop
            self.realtime_stop_flag = True
            if self.realtime_audio_in_queue:
                try:
                    self.realtime_audio_in_queue.put_nowait(None)
                except:
                    pass
            if self.realtime_audio_out_queue:
                try:
                    self.realtime_audio_out_queue.put_nowait(None)
                except:
                    pass
            
            # Clean up TX thread
            if hasattr(self, 'tx_thread') and self.tx_thread.is_alive():
                self.tx_running = False
                try:
                    self.tx_thread.join(timeout=1.0)
                except:
                    pass
            
            # ✅ CRITICAL: Wait for all background threads to complete
            # This prevents crashes when threads access DB after WebSocket closes
            if hasattr(self, 'background_threads') and self.background_threads:
                print(f"🧹 Waiting for {len(self.background_threads)} background threads...")
                for i, thread in enumerate(self.background_threads):
                    if thread.is_alive():
                        try:
                            thread.join(timeout=3.0)  # Max 3 seconds per thread
                            if thread.is_alive():
                                print(f"⚠️ Background thread {i} still running after timeout")
                            else:
                                print(f"✅ Background thread {i} completed")
                        except Exception as e:
                            print(f"❌ Error joining thread {i}: {e}")
                print(f"✅ All background threads cleanup complete")
            
            # 💰 CALCULATE AND LOG CALL COST
            if USE_REALTIME_API:
                self._calculate_and_log_cost()
            
            try: 
                self.ws.close()
            except: 
                pass
            # Mark as ended
            if hasattr(self, 'call_sid') and self.call_sid:
                stream_registry.clear(self.call_sid)
        
        # Final cleanup
        print(f"WS_DONE sid={self.stream_sid} rx={self.rx} tx={self.tx}")

    def _interrupt_speaking(self):
        """✅ FIXED: עצירה מיידית של דיבור הבוט - סדר פעולות נכון"""
        print("🚨 INTERRUPT_START: Beginning full interrupt sequence")
        
        # ✅ STEP 1: שלח clear לטוויליו ראשון
        if not self.ws_connection_failed:
            try:
                self._tx_enqueue({"type": "clear"})
                print("✅ CLEAR_SENT: Twilio clear command sent")
            except Exception as e:
                print(f"⚠️ CLEAR_FAILED: {e}")
        
        # ✅ STEP 2: נקה את תור השידור אחר clear
        try:
            cleared_count = 0
            while not self.tx_q.empty():
                self.tx_q.get_nowait()
                cleared_count += 1
            if cleared_count > 0:
                print(f"✅ TX_QUEUE_CLEARED: Removed {cleared_count} pending audio frames")
        except Exception as e:
            print(f"⚠️ TX_CLEAR_FAILED: {e}")
        
        # ✅ STEP 3: עדכן מצבים
        self.state = STATE_LISTEN
        self.mark_pending = False
        self.last_voice_ts = 0
        self.voice_in_row = 0
        self.processing = False
        
        # ✅ STEP 4: רק בסוף - עדכן speaking=False
        self.speaking = False
        
        print("✅ INTERRUPT_COMPLETE: Full interrupt sequence finished - ready to listen")

    # 🎯 עיבוד מבע פשוט וביטוח (ללא כפילויות)
    def _process_utterance_safe(self, pcm16_8k: bytes, conversation_id: int):
        """עיבוד מבע עם הגנה כפולה מפני לולאות"""
        # 🚀 REALTIME API: Skip Google STT/TTS completely in Realtime mode
        if USE_REALTIME_API:
            print(f"⏭️ [REALTIME] Skipping Google STT/TTS - using Realtime API only")
            # Reset buffer and state to prevent accumulation
            if hasattr(self, 'buf'):
                self.buf.clear()
            self.processing = False
            self.state = STATE_LISTEN
            return
        
        # וודא שלא מעבדים את אותו ID פעמיים
        if conversation_id <= self.last_processing_id:
            print(f"🚫 DUPLICATE processing ID {conversation_id} (last: {self.last_processing_id}) - SKIP")
            return
        
        self.last_processing_id = conversation_id
        
        # וודא שהמערכת לא מדברת כרגע
        if self.speaking:
            print("🚫 Still speaking - cannot process new utterance")
            return
            
        print(f"🎤 SAFE PROCESSING: conversation #{conversation_id}")
        self.state = STATE_THINK  # מעבר למצב חשיבה
        
        text = ""  # initialize to avoid unbound variable
        try:
            # PATCH 6: Safe ASR - never leaves empty
            try:
                # ⚡ PHASE 2: Use smart wrapper (streaming or single-request)
                text = self._hebrew_stt_wrapper(pcm16_8k) or ""
                print(f"🎤 USER: {text}")
                
                # ✅ מדידת ASR Latency
                if hasattr(self, 'eou_timestamp'):
                    asr_latency = time.time() - self.eou_timestamp
                    self.last_stt_time = asr_latency  # ⚡ CRITICAL: Save for TOTAL_LATENCY calculation
                    if DEBUG: print(f"📊 ASR_LATENCY: {asr_latency:.3f}s (target: <0.7s)")
                    
            except Exception as e:
                print(f"❌ STT ERROR: {e}")
                text = ""
            
            # ✅ SMART HANDLING: כשלא מבין - בשקט או "לא הבנתי" אחרי כמה ניסיונות
            if not text.strip():
                # ספירת כישלונות רצופים
                if not hasattr(self, 'consecutive_empty_stt'):
                    self.consecutive_empty_stt = 0
                self.consecutive_empty_stt += 1
                
                # אם 2 כישלונות ברצף - תגיד "לא הבנתי"
                if self.consecutive_empty_stt >= 2:
                    print("🚫 MULTIPLE_EMPTY_STT: Saying 'didn't understand'")
                    self.consecutive_empty_stt = 0  # איפוס
                    try:
                        self._speak_simple("לא הבנתי, אפשר לחזור?")
                    except:
                        pass
                else:
                    print("🚫 NO_SPEECH_DETECTED: Staying silent (attempt 1)")
                
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
                print(f"🚫 VERY_SHORT_TEXT: '{text}' (≤1 char) - likely noise")
                self.state = STATE_LISTEN
                self.processing = False
                return
            
            # PATCH 6: Anti-duplication on user text (14s window) - WITH DEBUG
            uh = zlib.crc32(text.strip().encode("utf-8"))
            if (self.last_user_hash == uh and 
                (time.time() - self.last_user_hash_ts) <= DEDUP_WINDOW_SEC):
                print("🚫 DUPLICATE USER INPUT (ignored)")
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
                    force_print(f"⚠️ [FAQ_ERROR] {e}")
            
            # If FAQ matched - respond immediately and skip AgentKit!
            if faq_match:
                faq_ms = (time.time() - faq_start_time) * 1000
                force_print(f"🚀 [FAQ_HIT] biz={getattr(self, 'business_id', '?')} intent={faq_match['intent_key']} score={faq_match['score']:.3f} method={faq_match['method']} ms={faq_ms:.0f}ms")
                reply = faq_match['answer']
                
                # Track as FAQ turn (no Agent SDK call)
                force_print(f"🤖 [FAQ_RESPONSE] {reply[:100]}... (skipped Agent)")
                
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
                force_print(f"✅ [FAQ_COMPLETE] Returned to LISTEN (total: {(time.time() - faq_start_time)*1000:.0f}ms)")
                return
            else:
                # FAQ miss - proceed to AgentKit
                faq_ms = (time.time() - faq_start_time) * 1000
                force_print(f"⏭️ [FAQ_MISS] No match found (search took {faq_ms:.0f}ms) → proceeding to AgentKit")
            
            # No FAQ match - proceed with AgentKit (normal flow)
            ai_processing_start = time.time()
            
            # ✅ השתמש בפונקציה המתקדמת עם מתמחה והמאגר הכולל!
            reply = self._ai_response(text)
            
            # ✅ FIXED: אם AI החזיר None (אין טקסט אמיתי) - אל תגיב!
            if reply is None:
                print("🚫 AI_RETURNED_NONE: No response needed - returning to listen mode")
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
                print(f"⚠️ AgentKit returned dict - extracted: '{reply[:50]}...'")
            reply_trimmed = reply.strip() if reply else ""
            exact_duplicates = [r for r in self.recent_replies if r == reply_trimmed]
            if len(exact_duplicates) >= 3:  # ✅ FIXED: רק אחרי 3 כפילויות מדויקות
                print("🚫 EXACT DUPLICATE detected (3+ times) - adding variation")
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
                print(f"🤖 BOT: {reply}")
                
                # ✅ מדידת AI Processing Time
                ai_processing_time = time.time() - ai_processing_start
                if DEBUG: print(f"📊 AI_PROCESSING: {ai_processing_time:.3f}s")
                
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
                print("🚫 NO_VALID_RESPONSE: AI returned empty/None - staying silent")
                # לא דופסים, לא שומרים בהיסטוריה, לא מדברים
            
            # ✅ CRITICAL: חזור למצב האזנה אחרי כל תגובה!
            self.state = STATE_LISTEN
            print(f"✅ RETURNED TO LISTEN STATE after conversation #{conversation_id}")
            
        except Exception as e:
            print(f"❌ CRITICAL Processing error: {e}")
            print(f"   Text was: '{text}' ({len(text)} chars)")
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
                print(f"✅ RETURNED TO LISTEN STATE after error in conversation #{conversation_id}")
            except Exception as emergency_err:
                print(f"❌ EMERGENCY RESPONSE FAILED: {emergency_err}")
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
        print(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        
        # 🚀 REALTIME API: Send greeting via Realtime API if enabled
        if USE_REALTIME_API:
            print(f"🚀 [REALTIME] Sending greeting via Realtime API: '{text[:50]}...'")
            try:
                # ✅ FIX: Queue greeting text to be sent via Realtime API (non-blocking)
                # Queue is initialized in __init__ to avoid AttributeError
                try:
                    self.realtime_greeting_queue.put_nowait(text)
                    print(f"✅ [REALTIME] Greeting queued for Realtime API")
                except queue.Full:
                    # Queue full - replace old greeting with new one
                    print(f"⚠️ [REALTIME] Greeting queue full, replacing...")
                    try:
                        self.realtime_greeting_queue.get_nowait()
                        self.realtime_greeting_queue.put_nowait(text)
                        print(f"✅ [REALTIME] Greeting replaced in queue")
                    except:
                        print(f"❌ [REALTIME] Failed to replace greeting - will fallback")
                        # Don't raise - fall through to Google TTS
                        pass
                except Exception as e:
                    print(f"❌ [REALTIME] Failed to queue greeting: {e}")
                    # Don't raise - will try again on next attempt
                    pass
                else:
                    # Successfully queued - exit early
                    return
            except Exception as e:
                print(f"❌ [REALTIME] Greeting queueing error: {e}")
                import traceback
                traceback.print_exc()
            
            # ✅ Realtime mode: Greeting will be sent by async loop, no Google TTS fallback
            print(f"📭 [REALTIME] Greeting queued or will be retried by async loop")
            return
        
        # Google TTS (only when USE_REALTIME_API=False)
        print(f"🔊 GREETING_TTS_START (Google): '{text[:50]}...'")
        
        try:
            # ⚡ בלי sleep - ברכה מיידית!
            tts_audio = self._hebrew_tts(text)
            if tts_audio and len(tts_audio) > 1000:
                print(f"✅ GREETING_TTS_SUCCESS: {len(tts_audio)} bytes")
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
            else:
                print("❌ GREETING_TTS_FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            print(f"❌ GREETING_TTS_ERROR: {e}")
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
            print(f"⚠️ DICT STILL HERE! Should have been normalized in _ai_response: {text}")
            if 'text' in text:
                text = text['text']
                print(f"✅ Extracted text field: '{text}'")
            else:
                print(f"❌ No 'text' field in dict - using fallback")
                text = "סליחה, לא הבנתי. אפשר לחזור?"
            
        if self.speaking:
            print("🚫 Already speaking - stopping current and starting new")
            try:
                # ✅ FIXED: בצע interrupt מלא לפני התחלת TTS חדש
                self._interrupt_speaking()
                time.sleep(0.05)  # המתנה קצרה
            except Exception as e:
                print(f"⚠️ Interrupt error (non-critical): {e}")
        
        # 🔒 HARD-CODED: ALWAYS protected - ZERO barge-in!
        word_count = len(text.split())
        self.long_response = True  # ✅ PERMANENTLY True - NEVER interrupt!
        print(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
        self.speaking = True
        self.speaking_start_ts = time.time()
        self.state = STATE_SPEAK
        print(f"🔊 TTS_START: '{text}'")
        
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
                        print(f"🔪 TTS_SAFETY_CUT (sentence): {text}")
                        break
                else:
                    # Keep original text - don't cut!
                    print(f"⚠️ TTS_LONG_RESPONSE: {len(text)} chars (no cut)")
            
            # ⏱️ TTS timing instrumentation
            tts_start = time.time()
            
            # 🚀 TTS (blocking mode - Hebrew doesn't support streaming API yet)
            from server.services.gcp_tts_live import maybe_warmup
            
            # ⚡ Pre-warm TTS
            maybe_warmup()
            
            tts_audio = self._hebrew_tts(text)
            tts_generation_time = time.time() - tts_start
            if DEBUG: print(f"📊 TTS_GENERATION: {tts_generation_time:.3f}s")
            
            if tts_audio and len(tts_audio) > 1000:
                print(f"🔊 TTS SUCCESS: {len(tts_audio)} bytes")
                send_start = time.time()
                self._send_pcm16_as_mulaw_frames_with_mark(tts_audio)
                send_time = time.time() - send_start
                if DEBUG: print(f"📊 TTS_SEND: {send_time:.3f}s (audio transmission)")
                
                # ⚡ BUILD 114: Detailed latency breakdown (EOU→first audio sent)
                if eou_saved:
                    turn_latency = send_start - eou_saved
                    total_latency = time.time() - eou_saved
                    stt_time = getattr(self, 'last_stt_time', 0.0)
                    ai_time = getattr(self, 'last_ai_time', 0.0)
                    
                    if DEBUG: print(f"📊 TURN_LATENCY: {turn_latency:.3f}s (EOU→TTS start, target: <1.2s)")
                    if DEBUG: print(f"📊 🎯 TOTAL_LATENCY: {total_latency:.3f}s (EOU→Audio sent, target: <2.0s)")
                    print(f"[LATENCY] stt={stt_time:.2f}s, ai={ai_time:.2f}s, tts={tts_generation_time:.2f}s, total={total_latency:.2f}s")
                    
                    # Clear for next measurement
                    if hasattr(self, 'eou_timestamp'):
                        delattr(self, 'eou_timestamp')
            else:
                print("🔊 TTS FAILED - sending beep")
                self._send_beep(800)
                self._finalize_speaking()
        except Exception as e:
            print(f"❌ TTS_ERROR: {e}")
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
        """
        # 🛑 BUILD 165: LOOP GUARD - Block all audio except "clear" when engaged
        # 🔥 BUILD 178: Disabled for outbound calls
        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
        if self._loop_guard_engaged and not is_outbound:
            if isinstance(item, dict) and item.get("type") == "clear":
                pass  # Allow clear commands through
            else:
                return  # Silently drop all other audio
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
                    print("⚠️ tx_q full (drop oldest)", flush=True)
                    self._last_overflow_log = now
    
    def _finalize_speaking(self):
        """סיום דיבור עם חזרה להאזנה"""
        self.speaking = False
        self.long_response = False  # ⚡ BUILD 109: Reset flag
        self.last_tts_end_ts = time.time()
        self.state = STATE_LISTEN
        self.last_voice_ts = 0  # איפוס למערכת VAD
        self.voice_in_row = 0
        print("🎤 SPEAKING_END -> LISTEN STATE | buffer_reset")

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
        
        if DEBUG: print(f"🔊 TTS_FRAMES: {total_frames} frames ({total_frames * 20}ms)")
        
        for i in range(0, len(mulaw), FR):
            # בדיקת ברג-אין
            if not self.speaking:
                print(f"🚨 BARGE-IN! Stopped at frame {frames_sent}/{total_frames}")
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
            print(f"⚠️ Audio incomplete: {frames_sent}/{total_frames} frames sent")

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
            print("⚠️ numpy/scipy not available - using raw audio")
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
            print(f"⚠️ numpy/scipy not available - using raw audio")
            return pcm16_8k
        except Exception as e:
            print(f"⚠️ Audio processing failed, using raw audio: {e}")
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
                print(f"⚠️ Even simple resample failed: {e2}")
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
            print(f"❌ [STT_FALLBACK_ASYNC] Failed: {e}", flush=True)
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
                print(f"❌ [STT_FALLBACK_NB] Failed: {e}", flush=True)
                text = ""
            
            # If there's a loop and events queue, use it
            if self.loop and self.events_q:
                events_q = self.events_q  # Type hint helper
                self.loop.call_soon_threadsafe(
                    lambda: events_q.put_nowait(("stt_final_text", text))
                )
            else:
                # Fallback: direct callback (sync mode)
                print(f"🎤 [STT_FALLBACK_NB] Result: {text[:50] if text else '(empty)'}", flush=True)
        
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
            print(f"⏱️ [STT_STREAM] Calling _utterance_end...")
            utt_start = time.time()
            result = self._utterance_end()
            utt_duration = time.time() - utt_start
            print(f"⏱️ [STT_STREAM] _utterance_end took {utt_duration:.3f}s, result: '{result[:50] if result else '(empty)'}'")
            
            # ✅ FIX: Fallback on empty results
            if not result or not result.strip():
                print("⚠️ [STT] Streaming returned empty → fallback to single")
                fallback_start = time.time()
                fallback_result = self._hebrew_stt(pcm16_8k)
                fallback_duration = time.time() - fallback_start
                print(f"⏱️ [STT_FALLBACK] Single-request took {fallback_duration:.3f}s, result: '{fallback_result[:50] if fallback_result else '(empty)'}'")
                return fallback_result
                
            return result
            
        except Exception as e:
            # Fallback to single-request on exception
            print(f"⚠️ [STT] Streaming failed → fallback to single. err={e}")
            import traceback
            traceback.print_exc()
            return self._hebrew_stt(pcm16_8k)

    def _hebrew_stt(self, pcm16_8k: bytes) -> str:
        """Hebrew STT using Google STT Streaming with speech contexts (לפי ההנחיות)"""
        try:
            print(f"🎵 STT_PROCEED: Processing {len(pcm16_8k)} bytes with Google STT (audio validated)")
            
            # ✅ FIXED: בדיקת איכות אודיו מתקדמת - מניעת עיבוד של רעש/שקט
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            if DEBUG: print(f"📊 AUDIO_QUALITY_CHECK: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # 🔥 BUILD 164B: BALANCED NOISE GATE - Filter noise, allow quiet speech
            
            # 1. Basic amplitude check - balanced threshold
            if max_amplitude < 100:  # Back to reasonable threshold for quiet speech
                print(f"🚫 STT_BLOCKED: Audio too quiet (max_amplitude={max_amplitude} < 100)")
                return ""
            
            # 2. RMS energy check - balanced (typical speech is 180-500)
            if rms < 80:  # Allow soft speech while filtering pure noise
                print(f"🚫 STT_BLOCKED: Audio below noise threshold (rms={rms} < 80)")
                return ""
            
            # 3. Duration check - slightly longer minimum
            if duration < 0.18:  # 180ms minimum for meaningful audio
                print(f"🚫 STT_BLOCKED: Audio too short ({duration:.2f}s < 0.18s)")
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
                    print(f"🚫 STT_BLOCKED: Low energy variance - likely noise (variance={energy_variance:.0f})")
                    return ""
                
                # Block DTMF tones (very low ZCR) but allow speech
                if zero_crossings < 0.01 or zero_crossings > 0.3:  # Relaxed range
                    print(f"🚫 STT_BLOCKED: Abnormal ZCR - likely noise/tone (zcr={zero_crossings:.3f})")
                    return ""
                
                print(f"✅ AUDIO_VALIDATED: amp={max_amplitude}, rms={rms}, var={int(energy_variance)}, zcr={zero_crossings:.3f}")
                
            except ImportError:
                print("⚠️ numpy not available - skipping advanced audio validation")
            except Exception as numpy_error:
                print(f"⚠️ Advanced audio analysis failed: {numpy_error} - using basic validation")
                # אם נכשלנו בבדיקות מתקדמות - המשך עם בסיסיות
            
            try:
                from server.services.lazy_services import get_stt_client
                from google.cloud import speech
            except ImportError as import_error:
                print(f"⚠️ Google Speech library not available: {import_error} - using Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            client = get_stt_client()
            if not client:
                print("❌ Google STT client not available - fallback to Whisper")
                return self._whisper_fallback(pcm16_8k)
            
            # ⚡ BUILD 117: FORCE default model - phone_call NOT supported for Hebrew!
            # Google returns error: "The phone_call model is currently not supported for language : iw-IL"
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,  
                language_code="he-IL",   # עברית ישראל
                model="default",         # ⚡ FORCED: phone_call crashes for Hebrew!
                use_enhanced=True,       # ✅ ENHANCED model for better Hebrew accuracy!
                enable_automatic_punctuation=False,  # מניעת הפרעות
                # קונטקסט קל - רק לרמז
                speech_contexts=[
                    speech.SpeechContext(phrases=[
                        # 🔥 BUILD 186: GENERIC Hebrew phrases only - NO hardcoded cities!
                        # Cities should come from business settings, not hardcoded here
                        "שלום", "היי", "בוקר טוב", "תודה", "תודה רבה", "בבקשה",
                        "כן", "לא", "בסדר", "מעולה", "נהדר", "מצוין", "אוקיי",
                        "תור", "פגישה", "מחר", "מחרתיים", "יום", "שבוע", "חודש",
                        "אחד", "שניים", "שלוש", "ארבע", "חמש", "שש", "עשר", "עשרים"
                    ], boost=15.0)  # Reduced boost - let Whisper do the heavy lifting
                ]
            )
            
            # Single request recognition (לא streaming למבע קצר)
            audio = speech.RecognitionAudio(content=pcm16_8k)
            
            # ⚡ AGGRESSIVE TIMEOUT: 1.5s for speed (Hebrew usually < 1s)
            try:
                response = client.recognize(
                    config=recognition_config,
                    audio=audio,
                    timeout=1.5  # ✅ FAST: 1.5s timeout (was 3s)
                )
            except Exception as timeout_error:
                # Timeout = likely empty audio, return empty
                print(f"⚠️ STT_TIMEOUT ({timeout_error}) - likely silence")
                return ""
            
            if DEBUG: print(f"📊 GOOGLE_STT_ENHANCED: Processed {len(pcm16_8k)} bytes")
            
            if response.results and response.results[0].alternatives:
                hebrew_text = response.results[0].alternatives[0].transcript.strip()
                confidence = response.results[0].alternatives[0].confidence
                if DEBUG: print(f"📊 GOOGLE_STT_RESULT: '{hebrew_text}' (confidence: {confidence:.2f})")
                
                # ⚡ ACCURACY FIX: LOWER confidence thresholds to accept more valid Hebrew
                # Hebrew speech often has lower confidence scores than English
                if confidence < 0.25:  # ⚡ LOWERED: 0.25 instead of 0.4 - accept more valid Hebrew
                    print(f"🚫 VERY_LOW_CONFIDENCE: {confidence:.2f} < 0.25 - rejecting result")
                    return ""  # Return empty instead of nonsense
                
                # ⚡ ACCURACY FIX: Accept short phrases with lower confidence
                # "חמישים אפשר" might have 0.5-0.6 confidence but is valid!
                word_count = len(hebrew_text.split())
                if word_count <= 2 and confidence < 0.2:  # 🔥 BUILD 114: LOWERED 0.4 → 0.2 for Hebrew names
                    print(f"🚫 SHORT_LOW_CONFIDENCE: {word_count} words, confidence {confidence:.2f} < 0.2 - likely noise")
                    return ""
                
                # 🔥 BUILD 134: Log alternative transcripts for debugging
                if len(response.results[0].alternatives) > 1:
                    alt_text = response.results[0].alternatives[1].transcript
                    print(f"   📝 Alternative: '{alt_text}'")
                
                print(f"✅ GOOGLE_STT_SUCCESS: '{hebrew_text}' ({word_count} words, confidence: {confidence:.2f})")
                return hebrew_text
            else:
                # No results = silence
                print("⚠️ STT_NO_RESULTS - likely silence")
                return ""
                
        except Exception as e:
            print(f"❌ GOOGLE_STT_ERROR: {e}")
            return ""
    
    def _whisper_fallback_validated(self, pcm16_8k: bytes) -> str:
        """✅ FIXED: Whisper fallback with smart validation - לא ימציא מילים!"""
        try:
            print(f"🔄 WHISPER_VALIDATED: Processing {len(pcm16_8k)} bytes with fabrication prevention")
            
            # ✅ בדיקת איכות אודיו חמורה יותר
            import audioop
            max_amplitude = audioop.max(pcm16_8k, 2)
            rms = audioop.rms(pcm16_8k, 2)
            duration = len(pcm16_8k) / (2 * 8000)
            if DEBUG: print(f"📊 AUDIO_VALIDATION: max_amplitude={max_amplitude}, rms={rms}, duration={duration:.1f}s")
            
            # 🔥 BUILD 164B: BALANCED noise gate for Whisper
            if max_amplitude < 200 or rms < 120:  # Balanced thresholds - allow quiet speech
                print(f"🚫 WHISPER_BLOCKED: Audio too weak (amp={max_amplitude}<200, rms={rms}<120)")
                return ""  # Don't let Whisper hallucinate!
            
            if duration < 0.3:  # Less than 300ms
                print("🚫 WHISPER_BLOCKED: Audio too short - likely noise")
                return ""
            
            # Check for monotonic energy (noise vs speech)
            try:
                import numpy as np
                pcm_array = np.frombuffer(pcm16_8k, dtype=np.int16)
                energy_variance = np.var(pcm_array.astype(np.float32))
                if energy_variance < 1000000:  # Balanced threshold
                    print(f"🚫 WHISPER_BLOCKED: Low energy variance ({energy_variance:.0f}) - background noise")
                    return ""
            except:
                pass  # If check fails - continue
            
            from server.services.lazy_services import get_openai_client
            client = get_openai_client()
            if not client:
                print("❌ OpenAI client not available")
                return ""
            
            # Resample to 16kHz for Whisper
            pcm16_16k = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)[0]
            print(f"🔄 RESAMPLED: {len(pcm16_8k)} bytes @ 8kHz → {len(pcm16_16k)} bytes @ 16kHz")
            
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
                        temperature=0.1  # נמוך מאוד - פחות יצירתיות
                    )
            
            import os
            os.unlink(temp_wav.name)
            
            result = transcript.text.strip()
            
            # ✅ FINAL validation - בדיקת תוצאה חשודה
            if not result or len(result) < 2:
                print("✅ WHISPER_VALIDATED: Empty/minimal result - good!")
                return ""
            
            # 🛡️ BUILD 149: ENGLISH HALLUCINATION FILTER (refined)
            # Only block when text is PURELY English (hallucination) - allow mixed Hebrew/English
            import re
            hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', result))
            english_chars = len(re.findall(r'[a-zA-Z]', result))
            total_chars = max(hebrew_chars + english_chars, 1)
            
            # If no Hebrew at all and has English - likely hallucination
            if hebrew_chars == 0 and english_chars > 3:
                print(f"🚫 WHISPER_PURE_ENGLISH: '{result}' has no Hebrew - blocking fabrication")
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
                        print(f"🚫 WHISPER_ENGLISH_PHRASE: Found '{hallucination}' in '{result}' - blocking")
                        return ""
            
            # 🔥 BUILD 164: ENHANCED anti-hallucination for Whisper
            # Block ultra-short results (likely noise transcription)
            if len(result) <= 1:
                print(f"🚫 WHISPER_TOO_SHORT: Result '{result}' - blocking")
                return ""
            
            # Block common noise hallucinations (Hebrew + English)
            noise_hallucinations = [
                "uh", "eh", "mmm", "hmm", "אה", "הממ", "אמ", "הא",
                ".", "..", "...", "-", "—", " "
            ]
            if result.lower().strip() in noise_hallucinations:
                print(f"🚫 WHISPER_NOISE_HALLUCINATION: '{result}' - blocking")
                return ""
            
            # Block suspicious single Hebrew words that Whisper invents from noise
            suspicious_single_words = [
                "תודה", "נהדר", "נהדרת", "מעולה", "בראבו",
                "כן", "לא", "אוקיי", "טוב", "סבבה",
                "שלום", "היי", "ביי", "בסדר"
            ]
            words = result.split()
            if len(words) == 1 and result.strip() in suspicious_single_words:
                print(f"🚫 WHISPER_SUSPICIOUS_SINGLE: '{result}' - likely fabrication")
                return ""
            
            print(f"✅ WHISPER_VALIDATED_SUCCESS: '{result}'")
            return result
            
        except Exception as e:
            print(f"❌ WHISPER_VALIDATED_ERROR: {e}")
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
                        print(f"✅ זיהוי עסק לפי טלפון {self.phone_number}: {business.name}")
                
                # ✅ BUILD 152: אם אין עדיין business_id, השתמש בfallback דינמי (ללא hardcoded phone)
                if not self.business_id:
                    from server.services.business_resolver import resolve_business_with_fallback
                    # ✅ BUILD 152: Use actual to_number if available, otherwise get first active business
                    lookup_phone = self.to_number or self.phone_number or None
                    self.business_id, status = resolve_business_with_fallback('twilio_voice', lookup_phone)
                    print(f"✅ שימוש בעסק fallback: business_id={self.business_id} ({status})")
                
                if not self.business_id:
                    print("❌ לא נמצא עסק - שימוש בפרומפט ברירת מחדל כללי")
                    return "אתה נציג שירות מקצועי. עזור ללקוח במה שהוא צריך בצורה אדיבה וידידותית."
                
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
                            print(f"AI_PROMPT loaded tenant={self.business_id} channel={channel}")
                            return prompt_text
                    else:
                        # פרומפט יחיד (legacy)
                        print(f"✅ טען פרומפט legacy מדאטאבייס לעסק {self.business_id}")
                        return settings.ai_prompt
                except Exception as e:
                    print(f"⚠️ שגיאה בפרסור פרומפט JSON: {e}")
                    # fallback לפרומפט כטקסט רגיל
                    return settings.ai_prompt
            
            # אם אין ב-BusinessSettings, בדוק את business.system_prompt
            if business and business.system_prompt:
                print(f"✅ טען פרומפט מטבלת businesses לעסק {self.business_id}")
                return business.system_prompt
                
            print(f"⚠️ לא נמצא פרומפט לעסק {self.business_id} - שימוש בברירת מחדל כללי")
            return "אתה נציג שירות מקצועי. עזור ללקוח במה שהוא צריך בצורה אדיבה וידידותית."
            
        except Exception as e:
            print(f"❌ שגיאה בטעינת פרומפט מדאטאבייס: {e}")
            return "אתה נציג שירות מקצועי. עזור ללקוח במה שהוא צריך בצורה אדיבה וידידותית."

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
                    print(f"🔒 OUTBOUND CALL: Using explicit business_id={outbound_business_id} (NOT phone-based resolution)")
                    try:
                        business_id_int = int(outbound_business_id)
                        business = Business.query.get(business_id_int)
                        if business:
                            print(f"✅ OUTBOUND: Loaded business {business.name} (id={business.id})")
                        else:
                            logger.error(f"❌ OUTBOUND: Business {outbound_business_id} NOT FOUND - security violation?")
                            return (None, None)
                    except (ValueError, TypeError) as e:
                        logger.error(f"❌ OUTBOUND: Invalid business_id={outbound_business_id}: {e}")
                        return (None, None)
                else:
                    # INBOUND CALL: Use phone-based resolution
                    print(f"⚡ ULTRA-FAST: זיהוי עסק + ברכה + הגדרות בשאילתה אחת: to_number={to_number}")
                    
                    if to_number:
                        normalized_phone = to_number.strip().replace('-', '').replace(' ', '')
                        
                        business = Business.query.filter(
                            or_(
                                Business.phone_e164 == to_number,
                                Business.phone_e164 == normalized_phone
                            )
                        ).first()
                        
                        if business:
                            print(f"✅ מצא עסק: {business.name} (id={business.id})")
                    
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
                        print(f"📤 [OUTBOUND] Disabling all call control settings - AI follows prompt only!")
                        # Force settings that won't interfere with outbound calls
                        self.bot_speaks_first = True  # AI always speaks first in outbound
                        self.auto_end_after_lead_capture = False  # Don't auto-end
                        self.auto_end_on_goodbye = False  # Don't auto-end on goodbye
                        self.silence_timeout_sec = 120  # Very long timeout (2 min)
                        self.silence_max_warnings = 0  # No silence warnings
                        self.smart_hangup_enabled = False  # Disable smart hangup
                        self.required_lead_fields = []  # No required fields
                        self._loop_guard_engaged = False  # Ensure loop guard is off
                        self._max_consecutive_ai_responses = 20  # Very high limit
                        print(f"   ✓ auto_end=OFF, silence_timeout=120s, smart_hangup=OFF, loop_guard_max=20")
                    else:
                        # Copy config values to instance variables for backward compatibility (INBOUND only)
                        self.bot_speaks_first = self.call_config.bot_speaks_first
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
                        print(f"🛡️ [GREETING PROTECT] is_playing_greeting=True (early, blocking audio input)")
                    
                    # 🔥 CRITICAL: Mark settings as loaded to prevent duplicate loading
                    self._call_settings_loaded = True
                    
                    t_end = time.time()
                    print(f"⚡ BUILD 172: CallConfig loaded in {(t_end-t_start)*1000:.0f}ms")
                    print(f"   bot_speaks_first={self.bot_speaks_first}, auto_end_goodbye={self.auto_end_on_goodbye}")
                    print(f"   auto_end_lead={self.auto_end_after_lead_capture}, silence_timeout={self.silence_timeout_sec}s")
                    print(f"🔍 [CONFIG] required_lead_fields={self.required_lead_fields}")
                    print(f"🔍 [CONFIG] smart_hangup_enabled={self.smart_hangup_enabled}")
                    print(f"🔍 [BUILD 309] call_goal={getattr(self, 'call_goal', 'lead_only')}, confirm_before_hangup={getattr(self, 'confirm_before_hangup', True)}")
                    
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
            print(f"⚠️ business_id חסר בקריאה ל-_get_business_greeting_cached!")
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
                        print(f"✅ ברכה נטענה: business_id={self.business_id}, greeting='{greeting}' (len={len(greeting)})")
                    else:
                        print(f"✅ No greeting defined for business_id={self.business_id} - AI will speak first!")
                    
                    return greeting
                else:
                    print(f"⚠️ Business {self.business_id} לא נמצא")
                    return None
        except Exception as e:
            print(f"❌ שגיאה בטעינת ברכה: {e}")
            import traceback
            traceback.print_exc()
            return None  # ✅ NO fallback - return None on error
    
    def _get_business_greeting(self) -> str | None:
        """טעינת ברכה מותאמת אישית מהעסק עם {{business_name}} placeholder"""
        print(f"🔍 _get_business_greeting CALLED! business_id={getattr(self, 'business_id', 'NOT SET')}")
        
        try:
            from server.app_factory import create_app
            from server.models_sql import Business
            
            # זיהוי עסק אם עדיין לא זוהה
            if not hasattr(self, 'business_id') or not self.business_id:
                print(f"⚠️ business_id לא מוגדר - מזהה עסק עכשיו...")
                app = _get_flask_app()  # ✅ Use singleton
                with app.app_context():
                    self._identify_business_from_phone()
                print(f"🔍 אחרי זיהוי: business_id={getattr(self, 'business_id', 'STILL NOT SET')}")
            
            # טעינת ברכה מה-DB
            app = _get_flask_app()  # ✅ Use singleton
            with app.app_context():
                business = Business.query.get(self.business_id)
                print(f"🔍 שאילתת business: id={self.business_id}, נמצא: {business is not None}")
                
                if business:
                    # קבלת הברכה המותאמת - אם אין, return None (לא fallback!)
                    greeting = business.greeting_message or None
                    business_name = business.name or "העסק שלנו"
                    
                    print(f"🔍 פרטי עסק: name={business_name}, greeting_message={business.greeting_message}")
                    
                    if greeting:
                        # החלפת placeholder בשם האמיתי
                        greeting = greeting.replace("{{business_name}}", business_name)
                        greeting = greeting.replace("{{BUSINESS_NAME}}", business_name)
                        
                        print(f"✅ Loaded custom greeting for business {self.business_id} ({business_name}): '{greeting}'")
                    else:
                        print(f"✅ No greeting defined for business {self.business_id} - AI will speak first!")
                    
                    return greeting
                else:
                    print(f"⚠️ Business {self.business_id} not found")
                    return None
        except Exception as e:
            import traceback
            print(f"❌ Error loading business greeting: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return None

    # 🔥 BUILD 172 CLEANUP: _load_call_behavior_settings() REMOVED
    # All call settings now loaded via single source of truth: load_call_config(business_id)
    # This function was duplicating the loading logic and has been removed.

    async def _fallback_hangup_after_timeout(self, timeout_seconds: int, trigger_type: str):
        """
        🔥 FALLBACK: Disconnect call after timeout if AI didn't say closing phrase
        
        This ensures calls always end gracefully even if AI's response
        doesn't contain a recognized closing phrase.
        
        🔥 BUILD 203: Cancel hangup if user rejected confirmation!
        
        Args:
            timeout_seconds: How long to wait before forcing disconnect
            trigger_type: What triggered this ("user_goodbye" or "lead_captured")
        """
        print(f"⏰ [FALLBACK] Starting {timeout_seconds}s timer for {trigger_type}...")
        
        await asyncio.sleep(timeout_seconds)
        
        # Check if already disconnected
        if self.hangup_triggered:
            print(f"✅ [FALLBACK] Call already ended - no fallback needed")
            return
        
        # Check if pending_hangup was set (AI said closing phrase)
        if self.pending_hangup:
            print(f"✅ [FALLBACK] pending_hangup already set - normal flow working")
            return
        
        # 🔥 BUILD 203: CRITICAL - If user rejected confirmation, DO NOT hangup!
        if getattr(self, 'user_rejected_confirmation', False):
            print(f"🛡️ [BUILD 203] BLOCKING hangup - user rejected confirmation, conversation must continue!")
            # Reset the flag for next attempt
            self.user_rejected_confirmation = False
            return
        
        # 🔥 BUILD 203: Only hangup if user explicitly confirmed
        if not self.verification_confirmed and trigger_type != "user_goodbye":
            print(f"🛡️ [BUILD 203] BLOCKING hangup - no user confirmation received!")
            return
        
        # AI didn't say a recognized closing phrase - force polite disconnect
        print(f"⚠️ [FALLBACK] {timeout_seconds}s passed, AI didn't say closing phrase - forcing polite disconnect")
        
        # Wait for any audio to finish
        for _ in range(50):  # 5 seconds max
            if self.realtime_audio_out_queue.qsize() == 0 and self.tx_q.qsize() == 0:
                break
            await asyncio.sleep(0.1)
        
        # Extra buffer
        await asyncio.sleep(2.0)
        
        if not self.hangup_triggered:
            print(f"📞 [FALLBACK] Triggering hangup after {trigger_type} timeout")
            import threading
            threading.Thread(
                target=self._trigger_auto_hangup,
                args=(f"Fallback after {trigger_type}",),
                daemon=True
            ).start()

    def _trigger_auto_hangup(self, reason: str):
        """
        🎯 BUILD 163: Trigger automatic call hang-up via Twilio REST API
        
        🔥 BUILD 172 FIX: More robust - less blocking, with retry mechanism
        🔥 BUILD 178: Fixed log spam - limit retries and reduce logging
        
        Args:
            reason: Why the call is being hung up (for logging)
        """
        # 🔥 BUILD 178: Track retry count to prevent infinite loops
        if not hasattr(self, '_hangup_retry_count'):
            self._hangup_retry_count = 0
        
        # 🔥 BUILD 178: Stop if already hung up or exceeded max retries (30 retries = 15 seconds)
        if self.hangup_triggered or self.call_state == CallState.ENDED:
            return
        
        if self._hangup_retry_count > 30:
            print(f"⚠️ [BUILD 178] Max hangup retries exceeded - forcing hangup")
            self.hangup_triggered = True
            self.call_state = CallState.ENDED
            return
        
        # 🔥 BUILD 172: Transition to CLOSING state (only log first time)
        if self.call_state != CallState.ENDED and self.call_state != CallState.CLOSING:
            self.call_state = CallState.CLOSING
            print(f"📞 [STATE] Transitioning to CLOSING (reason: {reason})")
        
        # 🔥🔥 CRITICAL PROTECTION: Don't hangup during greeting
        if self.is_playing_greeting:
            if self._hangup_retry_count == 0:
                print(f"🛡️ [PROTECTION] BLOCKING hangup - greeting still playing")
            self._hangup_retry_count += 1
            threading.Timer(1.0, self._trigger_auto_hangup, args=(reason,)).start()
            return
        
        # 🔥 PROTECTION: Don't hangup within 3 seconds of greeting completion
        if self.greeting_completed_at is not None:
            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                remaining_ms = self.min_call_duration_after_greeting_ms - elapsed_ms
                if self._hangup_retry_count == 0:
                    print(f"🛡️ [PROTECTION] BLOCKING hangup - only {elapsed_ms:.0f}ms since greeting")
                self._hangup_retry_count += 1
                threading.Timer(remaining_ms / 1000.0, self._trigger_auto_hangup, args=(reason,)).start()
                return
        
        # 🔥 BUILD 303: SMART HANGUP - Always send goodbye before disconnect!
        # If we haven't sent a goodbye message yet, schedule it and delay hangup
        if not self.goodbye_message_sent:
            self.goodbye_message_sent = True
            self._hangup_retry_count += 1
            print(f"📞 [BUILD 303] SMART HANGUP - Scheduling goodbye before disconnect...")
            
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
                            await self._send_text_to_ai(f"[SYSTEM] השיחה מסתיימת. אמור: {goodbye_text}")
                        else:
                            await self._send_text_to_ai("[SYSTEM] השיחה מסתיימת. אמור משפט סיום קצר ומנומס בעברית, כמו 'תודה שהתקשרת, בעל המקצוע יחזור אליך בהקדם. להתראות!'")
                    
                    loop.run_until_complete(do_goodbye())
                    loop.close()
                except Exception as e:
                    print(f"⚠️ [BUILD 303] Error sending goodbye: {e}")
            
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
                print(f"🛡️ [PROTECTION] Waiting for audio (ai={is_ai_speaking}, oai_q={openai_queue_size}, tx_q={tx_queue_size}) retry #{self._hangup_retry_count}")
            self._hangup_retry_count += 1
            threading.Timer(0.5, self._trigger_auto_hangup, args=(reason,)).start()
            return
        
        # ✅ All clear - execute hangup
        self.hangup_triggered = True
        self.call_state = CallState.ENDED
        
        # 🎯 SMART HANGUP: Detailed logging for debugging
        print(f"📞 [SMART HANGUP] === CALL ENDING ===")
        print(f"📞 [SMART HANGUP] Reason: {reason}")
        print(f"📞 [SMART HANGUP] Lead captured: {self.lead_captured}")
        print(f"📞 [SMART HANGUP] Goodbye detected: {self.goodbye_detected}")
        print(f"📞 [SMART HANGUP] Lead state: {getattr(self, 'lead_capture_state', {})}")
        print(f"📞 [SMART HANGUP] Required fields: {getattr(self, 'required_lead_fields', ['name', 'phone'])}")
        crm = getattr(self, 'crm_context', None)
        if crm:
            print(f"📞 [SMART HANGUP] CRM: name={crm.customer_name}, phone={crm.customer_phone}")
        print(f"📞 [SMART HANGUP] ===================")
        
        if not self.call_sid:
            print(f"❌ [BUILD 163] No call_sid - cannot hang up")
            return
        
        try:
            import os
            from twilio.rest import Client
            
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                print(f"❌ [BUILD 163] Missing Twilio credentials - cannot hang up")
                return
            
            client = Client(account_sid, auth_token)
            
            client.calls(self.call_sid).update(status='completed')
            
            print(f"✅ [BUILD 163] Call {self.call_sid[:8]}... hung up successfully: {reason}")
            logger.info(f"[BUILD 163] Auto hang-up: call={self.call_sid[:8]}, reason={reason}")
            
        except Exception as e:
            print(f"❌ [BUILD 163] Failed to hang up call: {e}")
            import traceback
            traceback.print_exc()
    
    # 🔥 BUILD 172: SILENCE MONITORING - Auto-hangup on prolonged silence
    async def _start_silence_monitor(self):
        """
        Start background task to monitor for silence and auto-hangup.
        Called after call setup is complete.
        """
        if self._silence_check_task is not None:
            return  # Already running
        
        self._silence_check_task = asyncio.create_task(self._silence_monitor_loop())
        print(f"🔇 [SILENCE] Monitor started (timeout={self.silence_timeout_sec}s, max_warnings={self.silence_max_warnings})")
    
    async def _silence_monitor_loop(self):
        """
        Background loop that checks for silence and triggers warnings/hangup.
        🔥 BUILD 311: Added post-greeting grace period
        """
        try:
            while self.call_state == CallState.ACTIVE and not self.hangup_triggered:
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
                # Skip if call is ending
                if self.call_state in (CallState.CLOSING, CallState.ENDED):
                    break
                
                # 🔥 BUILD 311.1: Smart grace period - ends early when user speaks!
                # Only apply grace if user hasn't spoken yet
                if self.greeting_completed_at and not self.user_has_spoken:
                    time_since_greeting = time.time() - self.greeting_completed_at
                    grace_period = getattr(self, '_post_greeting_grace_period_sec', 5.0)
                    if time_since_greeting < grace_period:
                        # Still in grace period AND user hasn't spoken - don't count silence yet
                        continue
                # If user has spoken, proceed normally (no grace period)
                
                # Calculate silence duration
                silence_duration = time.time() - self._last_speech_time
                
                if silence_duration >= self.silence_timeout_sec:
                    if self._silence_warning_count < self.silence_max_warnings:
                        # Send "are you there?" warning
                        self._silence_warning_count += 1
                        print(f"🔇 [SILENCE] Warning {self._silence_warning_count}/{self.silence_max_warnings} after {silence_duration:.1f}s silence")
                        
                        # Send prompt to AI to ask if user is there
                        await self._send_silence_warning()
                        
                        # Reset timer
                        self._last_speech_time = time.time()
                    else:
                        # Max warnings exceeded - check if we can hangup
                        # 🔥 BUILD 172 FIX: Don't hangup if lead is captured but not confirmed!
                        fields_collected = self._check_lead_captured() if hasattr(self, '_check_lead_captured') else False
                        if fields_collected and not self.verification_confirmed:
                            # Fields captured but not confirmed - give one more chance
                            print(f"🔇 [SILENCE] Max warnings exceeded BUT lead not confirmed - sending final confirmation request")
                            self._silence_warning_count = self.silence_max_warnings - 1  # Allow one more warning
                            await self._send_text_to_ai(
                                "[SYSTEM] הלקוח שותק וטרם אישר את הפרטים. שאל בפעם אחרונה: 'אני רק צריך שתאשר את הפרטים - הכל נכון?'"
                            )
                            self._last_speech_time = time.time()
                            # Mark that we gave extra chance - next time really close
                            self._silence_final_chance_given = getattr(self, '_silence_final_chance_given', False)
                            if self._silence_final_chance_given:
                                # Already gave extra chance, now close without confirmation
                                print(f"🔇 [SILENCE] Final chance already given - closing anyway")
                                pass  # Fall through to close
                            else:
                                self._silence_final_chance_given = True
                                continue  # Don't close yet
                        
                        # OK to close - either no lead, or lead confirmed, or final chance given
                        print(f"🔇 [SILENCE] Max warnings exceeded - initiating polite hangup")
                        self.call_state = CallState.CLOSING
                        
                        # Send closing message and hangup
                        closing_msg = ""
                        if self.call_config and self.call_config.closing_sentence:
                            closing_msg = self.call_config.closing_sentence
                        elif self.call_config and self.call_config.greeting_text:
                            closing_msg = self.call_config.greeting_text  # Use greeting as fallback
                        
                        if closing_msg:
                            await self._send_text_to_ai(f"[SYSTEM] User has been silent for too long. Say goodbye: {closing_msg}")
                        else:
                            await self._send_text_to_ai("[SYSTEM] User has been silent for too long. Say a brief goodbye in Hebrew.")
                        
                        # Schedule hangup after TTS
                        await asyncio.sleep(3.0)
                        self._trigger_auto_hangup("silence_timeout")
                        break
                        
        except asyncio.CancelledError:
            print(f"🔇 [SILENCE] Monitor cancelled")
        except Exception as e:
            print(f"❌ [SILENCE] Monitor error: {e}")
    
    async def _send_silence_warning(self):
        """
        Send a gentle prompt to continue the conversation.
        🔥 BUILD 311.1: Made fully dynamic - AI decides based on context, no hardcoded phrases
        """
        try:
            # 🔥 BUILD 172 FIX: If we collected fields but not confirmed, ask for confirmation again
            fields_collected = self._check_lead_captured() if hasattr(self, '_check_lead_captured') else False
            if fields_collected and not self.verification_confirmed:
                warning_prompt = "[SYSTEM] הלקוח שותק. שאל בקצרה אם הפרטים שמסר נכונים."
            else:
                # 🔥 BUILD 311.1: Dynamic - let AI continue naturally based on conversation context
                # Don't hardcode "אתה עדיין איתי?" - let AI decide what makes sense
                warning_prompt = "[SYSTEM] הלקוח שותק. המשך את השיחה בטבעיות - שאל שוב את השאלה האחרונה בניסוח אחר או בדוק אם הלקוח שם."
            await self._send_text_to_ai(warning_prompt)
        except Exception as e:
            print(f"❌ [SILENCE] Failed to send warning: {e}")
    
    def _update_speech_time(self):
        """Call this whenever user or AI speaks to reset silence timer."""
        self._last_speech_time = time.time()
        self._silence_warning_count = 0  # Reset warnings on any speech
        
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
            print(f"📞 [STATE] Safety guard: Forcing WARMUP → ACTIVE (speech detected)")
            
            # Start silence monitor if not already running
            if self._silence_check_task is None:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._start_silence_monitor())
                    print(f"🔇 [SILENCE] Safety guard: Started monitor (was missing)")
                except RuntimeError:
                    # No running loop - we're in sync context
                    print(f"🔇 [SILENCE] Cannot start monitor from sync context (will start on next async call)")
    
    async def _send_text_to_ai(self, text: str):
        """
        Send a text message to OpenAI Realtime for processing.
        Used for system prompts and silence handling.
        
        🔥 BUILD 200: Updated to use realtime_client and trigger_response
        🔥 BUILD 311: Mark SILENCE_HANDLER responses - shouldn't count towards LOOP GUARD
        """
        try:
            # 🔥 BUILD 200: Use realtime_client instead of openai_ws
            if not self.realtime_client:
                print(f"⚠️ [AI] No realtime_client - cannot send text")
                return
            
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
            print(f"❌ [AI] Failed to send text: {e}")

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
        ignore_phrases = ["היי כבי", "היי ביי", "הי כבי", "הי ביי"]
        for ignore in ignore_phrases:
            if ignore in text_lower:
                print(f"[GOODBYE CHECK] IGNORED phrase (not goodbye): '{text_lower[:30]}...'")
                return False
        
        # 🛡️ FILTER: Exclude greetings that sound like goodbye
        greeting_words = ["היי", "הי", "שלום וברכה", "בוקר טוב", "צהריים טובים", "ערב טוב"]
        for greeting in greeting_words:
            if greeting in text_lower and "ביי" not in text_lower and "להתראות" not in text_lower:
                print(f"[GOODBYE CHECK] Skipping greeting: '{text_lower[:30]}...'")
                return False
        
        # ✅ CLEAR goodbye words - ONLY these trigger hangup!
        # Must contain "ביי" or "להתראות" or English equivalents
        clear_goodbye_words = [
            "להתראות", "ביי", "bye", "bye bye", "goodbye",
            "יאללה ביי", "יאללה להתראות"
        ]
        
        has_clear_goodbye = any(word in text_lower for word in clear_goodbye_words)
        
        if has_clear_goodbye:
            print(f"[GOODBYE CHECK] Clear goodbye detected: '{text_lower[:30]}...'")
            return True
        
        # ✅ Combined phrases with goodbye words
        combined_goodbye_phrases = [
            "תודה וביי", "תודה להתראות",
            "תודה רבה וביי", "תודה רבה להתראות"
        ]
        
        for phrase in combined_goodbye_phrases:
            if phrase in text_lower:
                print(f"[GOODBYE CHECK] Combined goodbye phrase: '{phrase}'")
                return True
        
        # 🚫 Everything else is NOT goodbye (including "תודה", "אין צורך", "לא צריך")
        print(f"[GOODBYE CHECK] No goodbye phrase: '{text_lower[:30]}...'")
        return False

    def _check_polite_closing(self, text: str) -> bool:
        """
        🎯 Check if AI said polite closing phrases (for graceful call ending)
        
        These phrases indicate AI is ending the conversation politely:
        - "תודה שהתקשרת" - Thank you for calling
        - "יום נפלא/נעים" - Have a great day
        - "נשמח לעזור שוב" - Happy to help again
        - "נציג יחזור אליך" - A rep will call you back
        
        Args:
            text: AI transcript to check
            
        Returns:
            True if polite closing phrase detected
        """
        text_lower = text.lower().strip()
        
        polite_closing_phrases = [
            "תודה שהתקשרת", "תודה על הפנייה", "תודה על השיחה",
            "יום נפלא", "יום נעים", "יום טוב", "ערב נעים", "ערב טוב",
            "נשמח לעזור", "נשמח לעמוד לשירותך",
            "נציג יחזור אליך", "נחזור אליך", "ניצור קשר",
            "שמח שיכולתי לעזור", "שמחתי לעזור",
            "אם תצטרך משהו נוסף", "אם יש שאלות נוספות"
        ]
        
        for phrase in polite_closing_phrases:
            if phrase in text_lower:
                print(f"[POLITE CLOSING] Detected: '{phrase}'")
                return True
        
        return False

    def _extract_city_from_confirmation(self, text: str) -> str:
        """
        🔥 BUILD 307: Extract city from AI confirmation pattern
        
        Parses AI confirmations like:
        - "בתל אביב, נכון?" → "תל אביב"
        - "בקריית אתא, נכון?" → "קריית אתא"
        - "עיר עפולה, נכון?" → "עפולה"
        
        Returns:
            City name or empty string if not found
        """
        import re
        
        # Common patterns for city mention in confirmations
        patterns = [
            r'ב([א-ת\s\-]{2,20})[,\s]+נכון',  # "בתל אביב, נכון?"
            r'(?:עיר|מ|ל)([א-ת\s\-]{2,20})[,\s]+נכון',  # "עיר חיפה, נכון?"
            r'ב([א-ת\s\-]{2,20})\?',  # "בחיפה?"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                city = match.group(1).strip()
                # Validate it's a real city
                try:
                    from server.services.city_normalizer import normalize_city, get_all_city_names
                    from server.services.phonetic_validator import validate_hebrew_word
                    
                    all_cities = get_all_city_names()
                    result = validate_hebrew_word(city, all_cities, auto_accept_threshold=70.0)
                    if result.confidence >= 70:
                        normalized = normalize_city(result.best_match or city)
                        return normalized.canonical or city
                except Exception as e:
                    print(f"⚠️ [BUILD 307] City extraction error: {e}")
                    return city
        
        return ""

    def _extract_lead_fields_from_ai(self, ai_transcript: str, is_user_speech: bool = False):
        """
        🎯 SMART HANGUP: Extract lead fields from AI confirmation patterns
        
        Parses AI responses to identify confirmed information:
        - "אתה מתל אביב" → city=תל אביב
        - "שירות ניקיון" → service_type=ניקיון
        - "תקציב של X שקל" → budget=X
        
        Args:
            ai_transcript: The AI's transcribed speech
            is_user_speech: True if this is user speech, False if AI speech
        """
        import re
        
        text = ai_transcript.strip()
        if not text or len(text) < 5:
            return
        
        # Get required fields to know what we're looking for
        required_fields = getattr(self, 'required_lead_fields', [])
        if not required_fields:
            return
        
        # 🔥 BUILD 307: Skip city extraction for AI questions and silence prompts
        # These should NEVER be treated as city mentions
        if not is_user_speech:
            ai_question_patterns = [
                'באיזו עיר', 'באיזה עיר', 'מאיפה אתה', 'איפה אתה',
                'מאיזה עיר', 'מאיזו עיר', 'איזו עיר', 'איזה עיר'
            ]
            silence_prompt_patterns = [
                'אתה עדיין שם', 'אתה שם', 'שומע אותי', 'עדיין בקו',
                'יש מישהו', 'הלו', 'שומעים אותי'
            ]
            text_lower = text.lower()
            
            # Skip city extraction for AI questions about city
            if any(pattern in text_lower for pattern in ai_question_patterns):
                print(f"⏭️ [BUILD 307] Skipping city extraction - AI asking about city")
                # Skip to service extraction
                pass
            # Skip city extraction for silence prompts
            elif any(pattern in text_lower for pattern in silence_prompt_patterns):
                print(f"⏭️ [BUILD 307] Skipping city extraction - silence prompt")
                # Skip to service extraction
                pass
            # For AI confirmations, extract city only from confirmation patterns
            elif 'נכון' in text or 'מאשר' in text or 'בסדר' in text:
                # This is an AI confirmation - extract city from it
                # Store this city for when user confirms with "נכון"
                self._last_ai_mentioned_city = self._extract_city_from_confirmation(text)
                if self._last_ai_mentioned_city:
                    print(f"📍 [BUILD 307] AI mentioned city in confirmation: '{self._last_ai_mentioned_city}'")
                return  # Let user confirmation handle the locking
            else:
                # Not a question, not a confirmation - skip city extraction from AI
                print(f"⏭️ [BUILD 307] Skipping city extraction - AI speech not confirmation")
                return
        
        # 🏙️ CITY EXTRACTION: Use 3-layer validation system
        # 🔥 BUILD 185: Phonetic validator + Consistency filter + RapidFuzz
        # 🔥 BUILD 201: User correction detection - don't ignore locked if user explicitly corrects
        if 'city' in required_fields:
            try:
                from server.services.city_normalizer import normalize_city, get_all_city_names
                from server.services.phonetic_validator import (
                    validate_hebrew_word, phonetic_similarity, normalize_for_comparison
                )
                
                # 🔥 BUILD 201: ALWAYS process city extraction - let ConsistencyFilter handle corrections
                # The filter will detect if user is correcting and unlock if needed
                if True:
                    # Normalize text for matching
                    text_normalized = text.replace('-', ' ').replace('־', ' ')
                    
                    # Try to extract city mentions using patterns
                    city_patterns = [
                        r'(?:מ|ב|ל)([א-ת\s\-]{3,20})',  # "מתל אביב", "בירושלים"
                        r'(?:גר\s+ב|נמצא\s+ב|מגיע\s+מ)([א-ת\s\-]{3,20})',  # "גר בחיפה"
                        r'עיר[:\s]+([א-ת\s\-]{3,20})',  # "עיר: תל אביב"
                    ]
                    
                    city_candidates = []
                    for pattern in city_patterns:
                        matches = re.findall(pattern, text_normalized)
                        city_candidates.extend(matches)
                    
                    # Also try the full text as potential city name
                    # 🔥 BUILD 306: Skip common words that are clearly NOT cities
                    non_city_words = {
                        'שלום', 'היי', 'הלו', 'צריך', 'צריכים', 'צריכה', 'רוצה', 'רוצים',
                        'אני', 'אנחנו', 'אתה', 'את', 'אתם', 'הוא', 'היא', 'הם', 'הן',
                        'כן', 'לא', 'אוקיי', 'בסדר', 'טוב', 'תודה', 'בבקשה', 'סליחה',
                        'עיר', 'שירות', 'מנעולן', 'מנעול', 'דלת', 'דלתות', 'רכב', 'חכם',
                        'פורץ', 'פריצה', 'פריצת', 'מפתח', 'מפתחות', 'סיוע', 'עזרה',
                        'בוקר', 'צהריים', 'ערב', 'לילה', 'היום', 'מחר', 'עכשיו',
                        'כמה', 'מתי', 'איפה', 'למה', 'מה', 'איך', 'מי', 'זה', 'זאת',
                        'שריות', 'שריית', 'אתר', 'קליבר'  # Common mishearings
                    }
                    words = text_normalized.split()
                    for i in range(len(words)):
                        for j in range(i+1, min(i+4, len(words)+1)):
                            candidate = ' '.join(words[i:j])
                            # Skip if candidate is a single non-city word
                            if len(words[i:j]) == 1 and words[i].replace('!', '').replace(',', '').replace('.', '') in non_city_words:
                                continue
                            if 2 < len(candidate) < 25:
                                city_candidates.append(candidate)
                    
                    # 🔥 LAYER 2: Phonetic validation with confidence thresholds
                    all_cities = get_all_city_names()
                    best_result = None
                    best_combined_score = 0
                    
                    for candidate in city_candidates:
                        candidate = candidate.strip()
                        if not candidate:
                            continue
                        
                        # Phonetic validation
                        # 🔥 BUILD 306: Relaxed thresholds to match phonetic_validator defaults
                        phonetic_result = validate_hebrew_word(
                            candidate, all_cities,
                            auto_accept_threshold=90.0,  # Was 93, now 90 (BUILD 306)
                            confirm_threshold=82.0,       # Was 85, now 82 (BUILD 306)
                            reject_threshold=82.0         # Was 85, now 82 (BUILD 306)
                        )
                        
                        if phonetic_result.confidence > best_combined_score:
                            best_combined_score = phonetic_result.confidence
                            best_result = phonetic_result
                    
                    if best_result:
                        raw_city = best_result.raw_input
                        
                        # 🔥 LAYER 3: Add to consistency filter and check majority
                        self.city_raw_attempts.append(raw_city)
                        locked = self.stt_consistency_filter.add_city_attempt(raw_city)
                        
                        if locked:
                            # Majority achieved - use locked value
                            canonical = normalize_city(locked).canonical or locked
                            self._update_lead_capture_state('city', canonical)
                            self._update_lead_capture_state('raw_city', raw_city)
                            self._update_lead_capture_state('city_confidence', 100.0)
                            self._update_lead_capture_state('city_autocorrected', True)
                            print(f"🔒 [CITY] Majority locked: '{canonical}' from {self.city_raw_attempts}")
                        elif best_result.should_reject:
                            # 🔥 BUILD 306: Below 82% - ask user to repeat
                            self._update_lead_capture_state('city_needs_retry', True)
                            print(f"❌ [CITY] Rejected '{raw_city}' (confidence={best_result.confidence:.0f}%) - ask to repeat")
                        elif best_result.needs_confirmation:
                            # 🔥 BUILD 306: 82-90% - needs confirmation
                            canonical = normalize_city(best_result.best_match or raw_city).canonical or raw_city
                            self._update_lead_capture_state('city', canonical)
                            self._update_lead_capture_state('raw_city', raw_city)
                            self._update_lead_capture_state('city_confidence', best_result.confidence)
                            self._update_lead_capture_state('city_needs_confirmation', True)
                            print(f"⚠️ [CITY] Needs confirmation: '{canonical}' (confidence={best_result.confidence:.0f}%)")
                        else:
                            # 🔥 BUILD 306: ≥90% - auto-accept AND lock immediately
                            canonical = normalize_city(best_result.best_match or raw_city).canonical or raw_city
                            self._update_lead_capture_state('city', canonical)
                            self._update_lead_capture_state('raw_city', raw_city)
                            self._update_lead_capture_state('city_confidence', best_result.confidence)
                            # 🔒 BUILD 306: Lock city immediately on high-confidence match
                            # This prevents subsequent lower-confidence matches from overriding
                            self.stt_consistency_filter.locked_city = canonical
                            print(f"✅ [CITY] Auto-accepted AND locked: '{canonical}' (confidence={best_result.confidence:.0f}%)")
                        
            except Exception as e:
                print(f"⚠️ [CITY] Phonetic validator error, falling back to basic: {e}")
                import traceback
                traceback.print_exc()
        
        # 🔧 SERVICE_TYPE EXTRACTION: Look for service mentions
        # 🔥 BUILD 179: ALWAYS extract - update to LAST mentioned service (user may change mind)
        # 🔥 BUILD 180: Filter out AI question fragments to prevent false extraction
        if 'service_type' in required_fields:
            # Skip if this looks like an AI question (contains question indicators)
            ai_question_indicators = [
                'איזה סוג שירות', 'מה השירות', 'באיזה תחום', 'מה אתה צריך',
                'איך אני יכול לעזור', 'במה אוכל לעזור', 'מה הבעיה', 'איזה שירות אתה'
            ]
            is_ai_question = any(indicator in text for indicator in ai_question_indicators)
            
            if not is_ai_question:
                # 🔥 BUILD 180: Look for AI CONFIRMATION patterns like "אתה צריך X, נכון?"
                confirmation_patterns = [
                    r'(?:אתה צריך|צריך|צריכים)\s+([א-ת\s]{3,25})(?:[\s,]+נכון|[\s,]+בעיר|[\s,]+ב)',  # "אתה צריך קיצור דלתות, נכון?"
                    r'(?:שירות|טיפול)\s+(?:של\s+)?([א-ת\s]{3,25})(?:[\s,]+נכון|[\s,]+בעיר|[\s,]+ב)',  # "שירות ניקיון, נכון?"
                    r'ב(?:תחום|נושא)\s+(?:של\s+)?([א-ת\s]{3,25})',  # "בתחום השיפוצים"
                ]
                for pattern in confirmation_patterns:
                    match = re.search(pattern, text)
                    if match:
                        service = match.group(1).strip()
                        # 🔥 Filter out question fragments and generic words
                        question_fragments = ['אתה צריך', 'צריכים', 'צריך', 'תרצה', 'תרצו', 'רוצה', 'רוצים']
                        if len(service) > 3 and service not in question_fragments:
                            self._update_lead_capture_state('service_type', service)
                            print(f"✅ [LEAD STATE] Extracted service_type from confirmation: {service}")
                            break
        
        # 💰 BUDGET EXTRACTION: Look for budget/price mentions
        if 'budget' in required_fields and 'budget' not in self.lead_capture_state:
            budget_patterns = [
                r'תקציב\s+(?:של\s+)?(\d[\d,\.]*)\s*(?:שקל|ש"ח|₪)?',  # "תקציב של 5000 שקל"
                r'(\d[\d,\.]*)\s*(?:שקל|ש"ח|₪)',  # "5000 שקל"
            ]
            for pattern in budget_patterns:
                match = re.search(pattern, text)
                if match:
                    budget = match.group(1).replace(',', '')
                    self._update_lead_capture_state('budget', budget)
                    break
        
        # 📧 EMAIL EXTRACTION: Look for email mentions
        if 'email' in required_fields and 'email' not in self.lead_capture_state:
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            match = re.search(email_pattern, text)
            if match:
                self._update_lead_capture_state('email', match.group(0))
        
        # ⏰ PREFERRED_TIME EXTRACTION: Look for time preferences
        if 'preferred_time' in required_fields and 'preferred_time' not in self.lead_capture_state:
            time_indicators = ['בוקר', 'צהריים', 'ערב', 'לילה', 'בשעה', 'ביום']
            for indicator in time_indicators:
                if indicator in text:
                    # Extract nearby text as time preference
                    idx = text.find(indicator)
                    time_context = text[max(0, idx-10):min(len(text), idx+20)]
                    self._update_lead_capture_state('preferred_time', time_context.strip())
                    break
        
        # 📝 NOTES EXTRACTION: If AI confirms problem description
        if 'notes' in required_fields and 'notes' not in self.lead_capture_state:
            notes_indicators = ['הבנתי', 'בסדר אז', 'אני מבין', 'הבעיה היא', 'תיאור הבעיה']
            for indicator in notes_indicators:
                if indicator in text and len(text) > 20:
                    self._update_lead_capture_state('notes', text[:100])
                    break
    
    def _update_lead_capture_state(self, field: str, value: str):
        """
        🎯 DYNAMIC LEAD CAPTURE: Update lead capture state with a new field value
        
        Called from:
        - _process_dtmf_phone() when phone is captured via DTMF
        - NLP parser when name/service_type/etc. are extracted
        - AI response parsing when fields are mentioned
        
        Args:
            field: Field identifier (e.g., 'name', 'phone', 'city', 'service_type')
            value: The captured value
        """
        if not value or not str(value).strip():
            return
        
        value = str(value).strip()
        self.lead_capture_state[field] = value
        print(f"✅ [LEAD STATE] Updated: {field}={value}")
        print(f"📋 [LEAD STATE] Current state: {self.lead_capture_state}")
        
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
        print(f"🔍 [DEBUG] _check_lead_captured: required_fields from self = {required_fields}")
        if not required_fields:
            required_fields = ['name', 'phone']  # Default for backward compatibility
            print(f"⚠️ [DEBUG] Using default required_fields (no custom config found)")
        
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
                    print(f"⚠️ [VALIDATION] Rejecting invalid {field} value: '{value}'")
                    value = None
            
            if value:
                collected_values.append(f"{field}={value}")
            else:
                missing_fields.append(field)
        
        if not missing_fields:
            print(f"✅ [SMART HANGUP] All required fields collected: {', '.join(collected_values)}")
            return True
        
        print(f"⏳ [SMART HANGUP] Still missing fields: {missing_fields} | Collected: {collected_values}")
        return False

    def _process_dtmf_skip(self):
        """
        🎯 Process DTMF skip (# pressed with empty buffer)
        Customer chose to skip phone number input
        """
        print(f"⏭️ Processing DTMF skip")
        
        # Create skip message in Hebrew
        skip_text = "אני מעדיף לא לתת את המספר"
        
        # 🚀 REALTIME API: Send via Realtime if enabled, otherwise use AgentKit
        if USE_REALTIME_API:
            print(f"🚀 [REALTIME] Sending DTMF skip via Realtime API")
            # ✅ Queue the user's DTMF skip message (non-blocking, no fallback to AgentKit)
            try:
                self.realtime_text_input_queue.put_nowait(skip_text)
                print(f"✅ [REALTIME] DTMF skip queued for Realtime API")
                
                # Save to conversation history
                self.conversation_history.append({
                    "user": "[DTMF skip]",
                    "bot": "(Realtime API handling)"
                })
            except queue.Full:
                print(f"❌ [REALTIME] CRITICAL: Text input queue full - DTMF skip dropped!")
                # Don't fall back to AgentKit - log the error
            except Exception as e:
                print(f"❌ [REALTIME] Failed to queue DTMF skip: {e}")
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
        
        print(f"✅ DTMF skip processed")
    
    def _process_dtmf_phone(self, phone_number: str):
        """
        ⚡ BUILD 121: Process phone number collected via DTMF
        Inject as conversation input and generate AI response
        """
        print(f"📞 Processing DTMF phone: {phone_number}")
        
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
            print(f"✅ Phone normalized: {phone_number} → {normalized_phone}")
            
            # 🎯 DYNAMIC LEAD STATE: Update lead capture state for smart hangup
            self._update_lead_capture_state('phone', normalized_phone)
            
            # 🔥 CRITICAL FIX: Store normalized phone in instance variable!
            # Don't use flask.g - WebSocket runs outside request context
            self.customer_phone_dtmf = normalized_phone
            print(f"✅ Stored customer_phone_dtmf: {normalized_phone}")
            
            # 🔥 CRITICAL FIX: Also update crm_context.customer_phone!
            # This is what the confirm handler checks - if we don't set it, appointment creation fails!
            crm_context = getattr(self, 'crm_context', None)
            if crm_context:
                crm_context.customer_phone = normalized_phone
                print(f"✅ Updated crm_context.customer_phone: {normalized_phone}")
            else:
                print(f"⚠️ No crm_context found - creating one")
                # Create CRM context if missing
                from server.media_ws_ai import CallCrmContext
                self.crm_context = CallCrmContext(
                    business_id=self.business_id,
                    customer_phone=normalized_phone
                )
                # 🔥 HYDRATION: If we have pending customer name, transfer it to context
                if hasattr(self, 'pending_customer_name') and self.pending_customer_name:
                    self.crm_context.customer_name = self.pending_customer_name
                    print(f"✅ [DTMF] Hydrated pending_customer_name → crm_context: {self.pending_customer_name}")
                    self.pending_customer_name = None  # Clear cache
                print(f"✅ Created crm_context with phone: {normalized_phone}")
            
            phone_to_show = normalized_phone
        else:
            print(f"⚠️ Phone normalization failed for: {phone_number}")
            phone_to_show = phone_number
        
        # 🔥 BUILD 186: Send DTMF phone as SYSTEM event (not user message)
        # DTMF is only used when require_phone_before_booking=True
        # Otherwise, Caller ID is used automatically (no verbal/DTMF needed)
        
        # 🚀 REALTIME API: Send via system event (not user message!)
        if USE_REALTIME_API:
            print(f"🚀 [REALTIME] Sending DTMF phone as SYSTEM event: {phone_to_show}")
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
                            f"📞 הלקוח הקליד מספר טלפון ב-DTMF: {phone_to_show}. שמור את המספר ותאשר ללקוח שקיבלת אותו."
                        ))
                        print(f"✅ [REALTIME] DTMF phone sent as system event")
                    except Exception as e:
                        print(f"❌ [REALTIME] Error sending DTMF phone: {e}")
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
                print(f"🔄 [DTMF] Triggering NLP with phone={crm_context.customer_phone if crm_context else None}")
                print(f"🔍 [DEBUG] Calling NLP after DTMF - conversation has {len(self.conversation_history)} messages")
                # Trigger NLP check (uses existing conversation history WITH DTMF!)
                self._check_appointment_confirmation("")  # Empty string - uses history
                
            except queue.Full:
                print(f"❌ [REALTIME] CRITICAL: Text input queue full - DTMF phone dropped!")
                # Don't fall back to AgentKit - log the error
            except Exception as e:
                print(f"❌ [REALTIME] Failed to queue DTMF phone: {e}")
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
        
        print(f"✅ DTMF phone processed: {phone_to_show}")
    
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
                print(f"❌ CRITICAL ERROR: No business_id set! Cannot process without business context")
                raise ValueError("Business ID is required - no fallback allowed")
            
            # Get customer name from conversation if available
            customer_name = None
            lead_info = getattr(self, '_last_lead_analysis', None)
            if lead_info:
                customer_name = lead_info.get('customer_name')
            
            # ⚡ CRITICAL: Measure AI response time
            ai_start = time.time()
            
            # ✅ FIX: Use Flask app singleton (CRITICAL - prevents app restart!)
            app = _get_flask_app()
            
            with app.app_context():
                # 🤖 Use Agent for REAL booking actions!
                ai_service = AIService()
                
                # 🔥 BUILD 118: Use customer_phone (includes DTMF) instead of caller_phone (None)!
                # customer_phone is set in line 2467 and includes DTMF phone if available
                print(f"\n📞 DEBUG: customer_phone from context = '{customer_phone}'")
                print(f"   phone_number (caller) = '{getattr(self, 'phone_number', 'None')}'")
                print(f"   customer_phone_dtmf = '{getattr(self, 'customer_phone_dtmf', 'None')}'")
                
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
                print(f"⚠️ Got legacy string response: {len(ai_response)} chars")
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
                print(f"❌ Unexpected response type: {type(ai_response).__name__}")
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
                print(f"❌ EMPTY TTS TEXT - using fallback")
                tts_text = "סליחה, לא הבנתי. אפשר לחזור?"
            
            print(f"✅ Extracted TTS text: {len(tts_text)} chars")
            print(f"   Metadata: {len(ai_response_dict.get('actions', []))} actions, booking={ai_response_dict.get('booking_successful', False)}")
            
            print(f"🤖 AGENT_RESPONSE: Generated {len(tts_text)} chars in {self.last_ai_time:.3f}s (business {business_id})")
            if DEBUG: print(f"📊 AI_LATENCY: {self.last_ai_time:.3f}s (target: <1.5s)")
            
            # Return TTS text (string) for _speak_simple
            return tts_text
            
        except Exception as e:
            print(f"❌ AI_SERVICE_ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            print(f"⚠️ Using fallback response instead of agent")
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
        ✅ UPGRADED Hebrew TTS with natural voice, SSML, and smart pronunciation
        Uses gcp_tts_live.py with all professional enhancements
        """
        try:
            print(f"🔊 TTS_START: Generating Natural Hebrew TTS for '{text[:50]}...' ({len(text)} chars)")
            
            # ✅ OPTION 1: Use punctuation polish if enabled
            try:
                from server.services.punctuation_polish import polish_hebrew_text
                text = polish_hebrew_text(text)
                print(f"✅ Punctuation polished: '{text[:40]}...'")
            except Exception as e:
                print(f"⚠️ Punctuation polish unavailable: {e}")
            
            # ✅ OPTION 2: Use upgraded TTS with SSML, natural voice, telephony profile
            try:
                from server.services.gcp_tts_live import get_hebrew_tts, maybe_warmup
                
                # ⚡ Phase 2: Pre-warm TTS (כל 8 דקות)
                maybe_warmup()
                
                tts_service = get_hebrew_tts()
                audio_bytes = tts_service.synthesize_hebrew_pcm16_8k(text)
                
                if audio_bytes and len(audio_bytes) > 1000:
                    duration_seconds = len(audio_bytes) / (8000 * 2)
                    print(f"✅ TTS_SUCCESS: {len(audio_bytes)} bytes Natural Wavenet ({duration_seconds:.1f}s)")
                    return audio_bytes
                else:
                    print("⚠️ TTS returned empty or too short")
                    return None
                    
            except ImportError as ie:
                print(f"⚠️ Upgraded TTS unavailable ({ie}), using fallback...")
                
                # ✅ FALLBACK: Basic Google TTS (if upgraded version fails)
                from server.services.lazy_services import get_tts_client
                from google.cloud import texttospeech
                
                client = get_tts_client()
                if not client:
                    print("❌ Google TTS client not available")
                    return None
                
                # ✅ קבלת הגדרות מ-ENV - לא מקודד!
                voice_name = os.getenv("TTS_VOICE", "he-IL-Wavenet-D")
                speaking_rate = float(os.getenv("TTS_RATE", "0.96"))
                pitch = float(os.getenv("TTS_PITCH", "-2.0"))
                
                synthesis_input = texttospeech.SynthesisInput(text=text)
                voice = texttospeech.VoiceSelectionParams(language_code="he-IL", name=voice_name)
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=8000,
                    speaking_rate=speaking_rate,
                    pitch=pitch,
                    effects_profile_id=["telephony-class-application"]
                )
                
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                duration_seconds = len(response.audio_content) / (8000 * 2)
                print(f"✅ TTS_FALLBACK_SUCCESS: {len(response.audio_content)} bytes (voice={voice_name}, rate={speaking_rate}, pitch={pitch}, {duration_seconds:.1f}s)")
                return response.audio_content
            
        except Exception as e:
            print(f"❌ TTS_CRITICAL_ERROR: {e}")
            print(f"   Text was: '{text}'")
            import traceback
            traceback.print_exc()
            return None
    
    def _tx_loop(self):
        """
        ⚡ BUILD 115.1 FINAL: Production-grade TX loop
        - Precise 20ms/frame timing with next_deadline
        - Back-pressure at 90% threshold
        - Real-time telemetry (fps/q/drops)
        """
        print("🔊 TX_LOOP_START: Audio transmission thread started")
        
        FRAME_INTERVAL = 0.02  # 20 ms per frame expected by Twilio
        next_deadline = time.monotonic()
        tx_count = 0
        
        # Telemetry
        frames_sent_last_sec = 0
        drops_last_sec = 0
        last_telemetry_time = time.monotonic()
        
        while self.tx_running:
            try:
                item = self.tx_q.get(timeout=0.5)
            except queue.Empty:
                continue
            
            if item.get("type") == "end":
                print("🔚 TX_LOOP_END: End signal received")
                break
            
            # Handle "clear" event
            if item.get("type") == "clear" and self.stream_sid:
                success = self._ws_send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
                print(f"🧹 TX_CLEAR: {'SUCCESS' if success else 'FAILED'}")
                continue
            
            # Handle "media" event (both old format and new Realtime format)
            if item.get("type") == "media" or item.get("event") == "media":
                # 🔥 Support both formats:
                # Old: {"type": "media", "payload": "..."}
                # New Realtime: {"event": "media", "streamSid": "...", "media": {"payload": "..."}}
                queue_size = self.tx_q.qsize()
                
                # 🔍 DEBUG: Log what format we received
                if tx_count < 3:
                    print(f"[TX_LOOP] Frame {tx_count}: type={item.get('type')}, event={item.get('event')}, has_media={('media' in item)}")
                
                # If already has correct format (from Realtime), send as-is
                if item.get("event") == "media" and "media" in item:
                    success = self._ws_send(json.dumps(item))
                    if tx_count < 3:
                        print(f"[TX_LOOP] Sent Realtime format: success={success}")
                    if success:
                        self.tx += 1  # ✅ Increment tx counter!
                else:
                    # Old format - convert
                    success = self._ws_send(json.dumps({
                        "event": "media", 
                        "streamSid": self.stream_sid,
                        "media": {"payload": item["payload"]}
                    }))
                    if tx_count < 3:
                        print(f"[TX_LOOP] Sent old format (converted): success={success}")
                    if success:
                        self.tx += 1  # ✅ Increment tx counter!
                
                tx_count += 1
                frames_sent_last_sec += 1
                
                # ⚡ Precise timing with next_deadline
                next_deadline += FRAME_INTERVAL
                delay = next_deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    # Missed deadline - resync
                    next_deadline = time.monotonic()
                
                # ⚡ Telemetry: Print stats every second (only if issues)
                now = time.monotonic()
                if now - last_telemetry_time >= 1.0:
                    queue_size = self.tx_q.qsize()
                    # 🔥 BUILD 181: Updated threshold to 750 frames (50% of 1500)
                    if queue_size > 750:
                        print(f"[TX] fps={frames_sent_last_sec} q={queue_size}/1500", flush=True)
                    frames_sent_last_sec = 0
                    drops_last_sec = 0
                    last_telemetry_time = now
                
                continue
            
            # Handle "mark" event
            if item.get("type") == "mark":
                success = self._ws_send(json.dumps({
                    "event": "mark", 
                    "streamSid": self.stream_sid,
                    "mark": {"name": item.get("name", "mark")}
                }))
                print(f"📍 TX_MARK: {item.get('name', 'mark')} {'SUCCESS' if success else 'FAILED'}")
        
        # ⚡ Removed flooding log - TX loop ended naturally
    
    def _speak_with_breath(self, text: str):
        """דיבור עם נשימה אנושית ו-TX Queue - תמיד משדר משהו"""
        if not text:
            return
        
        # 🔒 HARD-CODED: ALWAYS protected - ZERO barge-in!
        word_count = len(text.split())
        self.long_response = True  # ✅ PERMANENTLY True - NEVER interrupt!
        print(f"🔒 PROTECTED_RESPONSE ({word_count} words) - BARGE-IN IMPOSSIBLE")
            
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
                print("💔 SKIPPING TTS clear - WebSocket connection failed")
                return None
            
            # נסה TTS אמיתי
            pcm = None
            try:
                pcm = self._hebrew_tts(text)
            except Exception as e:
                print("TTS_ERR:", e)
                
            if not pcm or len(pcm) < 400:
                print("🔊 TTS FAILED - sending beep")
                pcm = self._beep_pcm16_8k(300)  # צפצוף 300ms
            else:
                print(f"🔊 TTS SUCCESS: {len(pcm)} bytes")
            
            # ✅ שלח את האודיו דרך TX Queue (אם החיבור תקין)
            if pcm and self.stream_sid and not self.ws_connection_failed:
                self._send_pcm16_as_mulaw_frames(pcm)
            elif self.ws_connection_failed:
                print("💔 SKIPPING audio clear - WebSocket connection failed")
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
            print(f"⚠️ [AREA] Error loading dynamic patterns: {e}")
            
        return ""
    
    # 🔥 BUILD 200: REMOVED _analyze_lead_completeness() function
    # It contained hardcoded real estate terms (דירה, חדרים, נכס, תקציב)
    # Lead completeness is now handled 100% by AI prompt - each business defines
    # their own required fields and logic in their custom prompts.
    # This ensures the system works for ANY business type, not just real estate.
    
    def _finalize_call_on_stop(self):
        """✅ סיכום מלא של השיחה בסיום - עדכון call_log וליד + יצירת פגישות
        🔥 BUILD 183: Only generate summary if USER actually spoke!
        """
        try:
            from server.models_sql import CallLog
            from server.services.customer_intelligence import CustomerIntelligence
            from server.app_factory import create_app
            from server.db import db
            import threading
            
            def finalize_in_background():
                try:
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        # מצא call_log
                        call_log = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if not call_log:
                            print(f"⚠️ No call_log found for final summary: {self.call_sid}")
                            return
                        
                        # 🔥 BUILD 183: Check if user actually spoke before building summary
                        user_spoke = False
                        user_content_length = 0
                        
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            for turn in self.conversation_history:
                                speaker = turn.get('speaker', '')
                                text = turn.get('text', '') or turn.get('user', '')
                                if speaker == 'user' or 'user' in turn:
                                    content = text.strip() if text else ""
                                    # Filter out noise
                                    noise_patterns = ['...', '(שקט)', '(silence)', '(noise)']
                                    if content and len(content) > 2:
                                        is_noise = any(n in content.lower() for n in noise_patterns)
                                        if not is_noise:
                                            user_spoke = True
                                            user_content_length += len(content)
                        
                        # 🔥 BUILD 183: If no user speech, mark as completed but DON'T generate summary
                        if not user_spoke or user_content_length < 5:
                            print(f"📊 [FINALIZE] NO USER SPEECH - skipping summary generation for {self.call_sid}")
                            call_log.status = "completed"
                            call_log.transcription = ""  # Empty transcription
                            call_log.summary = ""  # Empty summary - DO NOT HALLUCINATE!
                            call_log.ai_summary = ""
                            db.session.commit()
                            print(f"✅ CALL FINALIZED (no conversation): {self.call_sid}")
                            return  # Exit early - no webhook, no lead update
                        
                        # בנה סיכום מלא - only if user spoke
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
                        
                        # צור סיכום AI - only if we have actual conversation
                        business_id = getattr(self, 'business_id', None)
                        if not business_id:
                            print(f"❌ No business_id set for call summary - skipping")
                            return
                        ci = CustomerIntelligence(business_id)
                        summary_data = ci.generate_conversation_summary(
                            full_conversation,
                            {'conversation_history': self.conversation_history}
                        )
                        
                        # עדכן call_log
                        call_log.status = "completed"
                        call_log.transcription = full_conversation  # ✅ FIX: transcription not transcript!
                        call_log.summary = summary_data.get('summary', '')
                        call_log.ai_summary = summary_data.get('detailed_summary', '')
                        
                        db.session.commit()
                        
                        print(f"✅ CALL FINALIZED: {self.call_sid}")
                        print(f"📝 Summary: {summary_data.get('summary', 'N/A')}")
                        print(f"🎯 Intent: {summary_data.get('intent', 'N/A')}")
                        if DEBUG: print(f"📊 Next Action: {summary_data.get('next_action', 'N/A')}")
                        
                        # 📋 CRM: Update lead with call summary (Realtime mode only)
                        if USE_REALTIME_API and hasattr(self, 'crm_context') and self.crm_context and self.crm_context.lead_id:
                            update_lead_on_call(
                                lead_id=self.crm_context.lead_id,
                                summary=summary_data.get('summary', ''),
                                notes=f"Call {self.call_sid}: {summary_data.get('intent', 'general_inquiry')}"
                            )
                            print(f"✅ [CRM] Lead #{self.crm_context.lead_id} updated with call summary")
                        
                        # 📅 UPDATE APPOINTMENT with call summary (if appointment was created during call)
                        if hasattr(self, 'crm_context') and self.crm_context and hasattr(self.crm_context, 'last_appointment_id') and self.crm_context.last_appointment_id:
                            from server.models_sql import Appointment
                            appt_id = self.crm_context.last_appointment_id
                            appointment = Appointment.query.get(appt_id)
                            if appointment:
                                # Update appointment with call summary and link to call log
                                appointment.call_summary = summary_data.get('summary', '')
                                appointment.call_log_id = call_log.id
                                db.session.commit()
                                print(f"✅ [CALENDAR] Appointment #{appt_id} updated with call summary")
                            else:
                                print(f"⚠️ [CALENDAR] Appointment #{appt_id} not found for summary update")
                        
                        # 🤖 BUILD 119: Agent handles appointments during conversation!
                        # AUTO-APPOINTMENT disabled - Agent creates appointments in real-time
                        print(f"ℹ️ Appointment handling: Managed by Agent during call (BUILD 119)")
                        
                        # 🔥 BUILD 177 Enhanced: Send Generic Webhook with phone, city, service_category
                        try:
                            from server.services.generic_webhook_service import send_call_completed_webhook
                            from server.models_sql import Lead
                            
                            lead_id = None
                            city = None
                            service_category = None
                            
                            # 📱 Phone extraction - fallback chain with detailed logging
                            phone = None
                            print(f"📱 [WEBHOOK] Phone extraction debug:")
                            print(f"   - self.phone_number: {getattr(self, 'phone_number', 'NOT_SET')}")
                            print(f"   - self.customer_phone_dtmf: {getattr(self, 'customer_phone_dtmf', 'NOT_SET')}")
                            print(f"   - call_log.from_number: {call_log.from_number if call_log else 'NO_CALL_LOG'}")
                            crm = getattr(self, 'crm_context', None)
                            print(f"   - crm_context.customer_phone: {crm.customer_phone if crm else 'NO_CRM'}")
                            
                            # 1) From CRM context (collected during call)
                            if hasattr(self, 'crm_context') and self.crm_context and getattr(self.crm_context, 'customer_phone', None):
                                phone = self.crm_context.customer_phone
                                print(f"   ✓ Using CRM phone: {phone}")
                            # 2) From DTMF input (customer entered phone manually)
                            elif getattr(self, 'customer_phone_dtmf', None):
                                phone = self.customer_phone_dtmf
                                print(f"   ✓ Using DTMF phone: {phone}")
                            # 3) From handler phone_number (Twilio caller ID)
                            elif getattr(self, 'phone_number', None):
                                phone = self.phone_number
                                print(f"   ✓ Using Twilio caller ID: {phone}")
                            # 4) From CallLog (saved on call creation)
                            elif call_log and call_log.from_number:
                                phone = call_log.from_number
                                print(f"   ✓ Using CallLog from_number: {phone}")
                            else:
                                print(f"   ⚠️ No phone found in any source!")
                            
                            # 🏠 Extract lead_id, city, service_category from multiple sources
                            
                            # 🔍 FIRST: Extract service from AI CONFIRMATION patterns in transcript
                            # Pattern: "אתה צריך X בעיר Y" or "רק מוודא – אתה צריך X בעיר Y"
                            # This extracts the SPECIFIC service requested, not just generic professional type
                            # 🔥 BUILD 180: Priority to AI confirmation patterns for accurate service extraction
                            import re
                            
                            if full_conversation:
                                # Look for AI confirmation patterns - get LAST occurrence
                                confirmation_patterns = [
                                    r'(?:אתה צריך|צריך|צריכים)\s+([א-ת\s]{3,30})(?:\s+בעיר|\s+ב)',  # "אתה צריך קיצור דלתות בעיר"
                                    r'(?:אתה צריך|צריך|צריכים)\s+([א-ת\s]{3,30})(?:,?\s+נכון)',  # "אתה צריך קיצור דלתות, נכון?"
                                    r'שירות(?:\s+של)?\s+([א-ת\s]{3,30})(?:\s+בעיר|\s+ב)',  # "שירות קיצור דלתות בעיר"
                                ]
                                
                                for pattern in confirmation_patterns:
                                    matches = list(re.finditer(pattern, full_conversation))
                                    if matches:
                                        last_match = matches[-1]  # Get LAST occurrence
                                        extracted_service = last_match.group(1).strip()
                                        # Filter out question fragments
                                        question_fragments = ['אתה צריך', 'צריכים', 'צריך', 'תרצה', 'תרצו', 'רוצה', 'רוצים']
                                        if extracted_service and len(extracted_service) > 3 and extracted_service not in question_fragments:
                                            service_category = extracted_service
                                            print(f"🎯 [WEBHOOK] Extracted SPECIFIC service from AI confirmation: '{service_category}'")
                                            break
                            
                            # FALLBACK: Extract service from known professionals list
                            # 🔥 BUILD 179: Find the LAST mentioned professional (user may change mind)
                            if not service_category and full_conversation:
                                known_professionals = ['חשמלאי', 'אינסטלטור', 'שיפוצניק', 'מנקה', 'הובלות', 'מנעולן',
                                                       'טכנאי מזגנים', 'גנן', 'צבעי', 'רצף', 'נגר', 'אלומיניום',
                                                       'טכנאי מכשירי חשמל', 'מזגנים', 'דוד שמש', 'אנטנאי',
                                                       'שיפוצים', 'ניקיון', 'גינון', 'צביעה', 'ריצוף', 'נגרות',
                                                       'קיצור דלתות', 'החלפת מנעול', 'פתיחת דלת', 'התקנת דלת']
                                # Find LAST occurrence of any professional
                                last_prof_pos = -1
                                last_prof = None
                                for prof in known_professionals:
                                    pos = full_conversation.rfind(prof)  # rfind = LAST occurrence
                                    if pos > last_prof_pos:
                                        last_prof_pos = pos
                                        last_prof = prof
                                if last_prof:
                                    service_category = last_prof
                                    print(f"🎯 [WEBHOOK] Found LAST professional in transcript: {last_prof} (pos={last_prof_pos})")
                            
                            # Source 1: lead_capture_state (collected during conversation) - for city/phone only
                            lead_state = getattr(self, 'lead_capture_state', {}) or {}
                            raw_city = None
                            city_confidence = None
                            if lead_state:
                                print(f"📋 [WEBHOOK] Lead capture state: {lead_state}")
                                if not city:
                                    city = lead_state.get('city') or lead_state.get('עיר')
                                # 🔥 BUILD 184: Get raw_city and confidence from city normalizer
                                raw_city = lead_state.get('raw_city')
                                city_confidence = lead_state.get('city_confidence')
                                # Only use service from lead_state if we didn't find a known professional
                                if not service_category:
                                    raw_service = lead_state.get('service_category') or lead_state.get('service_type') or lead_state.get('professional') or lead_state.get('תחום') or lead_state.get('מקצוע')
                                    # Filter out AI question fragments
                                    if raw_service and raw_service not in ['תרצה עזרה', 'תרצו עזרה', 'אתה צריך', 'אתם צריכים']:
                                        service_category = raw_service
                                if not phone:
                                    phone = lead_state.get('phone') or lead_state.get('טלפון')
                            
                            # Source 2: CRM context
                            if hasattr(self, 'crm_context') and self.crm_context:
                                lead_id = self.crm_context.lead_id
                                
                                # Try to get city/service from CRM context attributes
                                if not city and hasattr(self.crm_context, 'city'):
                                    city = self.crm_context.city
                                if not service_category:
                                    if hasattr(self.crm_context, 'service_category'):
                                        service_category = self.crm_context.service_category
                                    elif hasattr(self.crm_context, 'professional'):
                                        service_category = self.crm_context.professional
                                
                                # Fallback: Load from Lead model if we have lead_id
                                if lead_id and (not city or not service_category or not phone):
                                    try:
                                        lead = Lead.query.get(lead_id)
                                        if lead:
                                            print(f"📋 [WEBHOOK] Enriching from Lead #{lead_id}")
                                            # Phone fallback from Lead
                                            if not phone and lead.phone_e164:
                                                phone = lead.phone_e164
                                                print(f"   └─ Phone from Lead: {phone}")
                                            
                                            # Try to extract city/service from Lead tags (JSON)
                                            if lead.tags and isinstance(lead.tags, dict):
                                                if not city:
                                                    city = lead.tags.get('city') or lead.tags.get('עיר')
                                                    if city:
                                                        print(f"   └─ City from Lead tags: {city}")
                                                if not service_category:
                                                    service_category = lead.tags.get('service_category') or lead.tags.get('professional') or lead.tags.get('תחום') or lead.tags.get('מקצוע')
                                                    if service_category:
                                                        print(f"   └─ Service from Lead tags: {service_category}")
                                        else:
                                            print(f"⚠️ [WEBHOOK] Lead #{lead_id} not found in DB")
                                    except Exception as lead_err:
                                        import traceback
                                        print(f"⚠️ [WEBHOOK] Could not load lead data: {lead_err}")
                                        traceback.print_exc()
                            
                            # 🔍 Last resort: Extract city and service from transcript if still missing
                            if (not city or not service_category) and full_conversation:
                                import re
                                transcript_text = full_conversation.replace('\n', ' ')
                                
                                # Extract city from transcript using fuzzy matching
                                # 🔥 BUILD 184: Use city normalizer with RapidFuzz
                                if not city:
                                    try:
                                        from server.services.city_normalizer import normalize_city
                                        # Extract potential city mentions from transcript
                                        city_patterns = [
                                            r'(?:מ|ב|ל)([א-ת\s\-]{3,20})',
                                            r'(?:גר\s+ב|נמצא\s+ב|מגיע\s+מ)([א-ת\s\-]{3,20})',
                                        ]
                                        city_candidates = []
                                        for pattern in city_patterns:
                                            matches = re.findall(pattern, transcript_text)
                                            city_candidates.extend(matches)
                                        
                                        # Find best match
                                        best_match = None
                                        best_confidence = 0
                                        for candidate in city_candidates:
                                            result = normalize_city(candidate.strip())
                                            if result.canonical and result.confidence > best_confidence:
                                                best_match = result
                                                best_confidence = result.confidence
                                        
                                        if best_match and best_match.canonical:
                                            city = best_match.canonical
                                            raw_city = best_match.raw_input
                                            city_confidence = best_match.confidence
                                            print(f"   └─ City from transcript (fuzzy): {city} (confidence={city_confidence:.0f}%)")
                                    except Exception as e:
                                        print(f"   └─ City normalizer error: {e}")
                                
                                # Extract service/professional from transcript
                                # 🔥 BUILD 179: Find the LAST mentioned service (user may change mind)
                                if not service_category:
                                    services = ['חשמלאי', 'אינסטלטור', 'שיפוצים', 'ניקיון', 'הובלות', 'מנעולן',
                                                'מיזוג', 'גינון', 'צביעה', 'ריצוף', 'נגרות', 'אלומיניום',
                                                'תיקון מכשירי חשמל', 'מזגנים', 'דוד שמש', 'אנטנות']
                                    last_service_pos = -1
                                    last_service = None
                                    for service in services:
                                        pos = transcript_text.rfind(service)  # rfind = LAST occurrence
                                        if pos > last_service_pos:
                                            last_service_pos = pos
                                            last_service = service
                                    if last_service:
                                        service_category = last_service
                                        print(f"   └─ LAST service from transcript: {service_category} (pos={last_service_pos})")
                            
                            # 🔥 BUILD 185: Pass consistency filter data to webhook
                            city_raw_attempts = getattr(self, 'city_raw_attempts', [])
                            name_raw_attempts = getattr(self, 'name_raw_attempts', [])
                            city_autocorrected = lead_state.get('city_autocorrected', False) if lead_state else False
                            
                            send_call_completed_webhook(
                                business_id=business_id,
                                call_id=self.call_sid,
                                lead_id=lead_id,
                                phone=phone or '',
                                started_at=call_log.created_at,
                                ended_at=call_log.updated_at,
                                duration_sec=call_log.duration or 0,
                                transcript=full_conversation,
                                summary=summary_data.get('summary', ''),
                                agent_name=getattr(self, 'bot_name', 'Assistant'),
                                direction=getattr(self, 'call_direction', 'inbound'),
                                city=city,
                                service_category=service_category,
                                raw_city=raw_city,
                                city_confidence=city_confidence,
                                city_raw_attempts=city_raw_attempts,
                                city_autocorrected=city_autocorrected,
                                name_raw_attempts=name_raw_attempts
                            )
                            print(f"✅ [WEBHOOK] Call completed webhook queued: phone={phone or 'N/A'}, city={city or 'N/A'}, service={service_category or 'N/A'}")
                        except Exception as webhook_err:
                            print(f"⚠️ [WEBHOOK] Webhook error (non-blocking): {webhook_err}")
                        
                except Exception as e:
                    print(f"❌ Failed to finalize call: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע
            thread = threading.Thread(target=finalize_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Call finalization setup failed: {e}")
    
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
                        print(f"⚠️ Missing Twilio credentials - TwiML fallback will handle recording")
                        return
                    
                    if not self.call_sid:
                        print(f"⚠️ No call_sid - cannot start recording")
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
                            print(f"✅ Recording already active for {self.call_sid}: {self._recording_sid}")
                            return
                    except Exception as list_error:
                        # Failed to check existing recordings - try to create anyway
                        print(f"⚠️ Could not check existing recordings: {list_error}")
                    
                    # Start a new recording via REST API
                    try:
                        recording = client.calls(self.call_sid).recordings.create(
                            recording_channels="dual"  # Record both channels
                        )
                        self._recording_succeeded = True
                        self._recording_sid = recording.sid
                        print(f"✅ Recording started for {self.call_sid}: {recording.sid}")
                        
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
                            print(f"✅ Recording already in progress for {self.call_sid}")
                        elif 'call is not in-progress' in error_msg:
                            # Call hasn't started yet - TwiML fallback will handle
                            print(f"⚠️ Call {self.call_sid} not in-progress - TwiML fallback will handle recording")
                        else:
                            # Transient failure - allow retry
                            print(f"⚠️ Could not start REST API recording for {self.call_sid}: {rec_error}")
                        
                except Exception as e:
                    # Transient failure - allow retry, TwiML fallback is active
                    print(f"⚠️ Recording start failed (TwiML fallback active): {e}")
            
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
            print(f"⚠️ Recording setup failed (TwiML fallback active): {e}")
    
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
                        print(f"🔧 DB_URL_AT_WRITE: driver={db_driver}, BIZ={getattr(self, 'business_id', 'N/A')}, SID={self.call_sid}", flush=True)
                        
                        # בדוק אם כבר קיים
                        existing = CallLog.query.filter_by(call_sid=self.call_sid).first()
                        if existing:
                            print(f"✅ Call log already exists for {self.call_sid}")
                            return
                        
                        # צור call_log חדש
                        call_log = CallLog()  # type: ignore[call-arg]
                        business_id = getattr(self, 'business_id', None)
                        if not business_id:
                            print(f"❌ No business_id set - cannot create call_log")
                            return
                        call_log.business_id = business_id
                        call_log.call_sid = self.call_sid
                        call_log.from_number = str(self.phone_number or "")
                        call_log.to_number = str(getattr(self, 'to_number', '') or '')
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
                            print(f"✅ Created CallSession for {self.call_sid}")
                        else:
                            print(f"✅ CallSession already exists for {self.call_sid}")
                        
                        try:
                            db.session.commit()
                            print(f"✅ Created call_log + CallSession on start: call_sid={self.call_sid}, phone={self.phone_number}")
                        except Exception as commit_error:
                            # Handle duplicate key error (race condition)
                            db.session.rollback()
                            error_msg = str(commit_error).lower()
                            if 'unique' in error_msg or 'duplicate' in error_msg:
                                print(f"⚠️ Call log already exists (race condition): {self.call_sid}")
                            else:
                                raise
                        
                except Exception as e:
                    print(f"❌ Failed to create call_log on start: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע
            thread = threading.Thread(target=create_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Call log creation setup failed: {e}")
    
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
                            print(f"⚠️ Call log not found for {self.call_sid} - conversation turn not saved")
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
                        print(f"✅ Saved conversation turn to DB: call_log_id={call_log.id}")
                        
                except Exception as e:
                    print(f"❌ Failed to save conversation turn: {e}")
                    import traceback
                    traceback.print_exc()
            
            # רוץ ברקע כדי לא לחסום
            thread = threading.Thread(target=save_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Conversation turn save setup failed: {e}")
    
    def _process_customer_intelligence(self, user_text: str, bot_reply: str):
        """
        ✨ עיבוד חכם של השיחה עם זיהוי/יצירת לקוח וליד אוטומטית
        """
        try:
            # וודא שיש מספר טלפון ו-business_id
            if not self.phone_number or not hasattr(self, 'business_id'):
                print("⚠️ Missing phone_number or business_id for customer intelligence")
                return
            
            # Import only when needed to avoid circular imports
            from server.services.customer_intelligence import CustomerIntelligence
            from server.app_factory import create_app
            from server.db import db
            
            # הרצה אסינכרונית כדי לא לחסום את השיחה
            import threading
            
            def process_in_background():
                try:
                    app = _get_flask_app()  # ✅ Use singleton
                    with app.app_context():
                        business_id = getattr(self, 'business_id', None)
                        if not business_id:
                            print(f"❌ No business_id for customer intelligence - skipping")
                            return
                        ci = CustomerIntelligence(business_id)
                        
                        # יצירת טקסט מלא מההיסטוריה הנוכחית
                        full_conversation = ""
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            full_conversation = " ".join([
                                f"{turn['user']} {turn['bot']}" 
                                for turn in self.conversation_history[-5:]  # רק 5 אחרונות
                            ])
                        
                        # זיהוי/יצירת לקוח וליד עם התמלול הנוכחי
                        customer, lead, was_created = ci.find_or_create_customer_from_call(
                            str(self.phone_number or ""),
                            self.call_sid or f"live_{int(time.time())}",
                            full_conversation,
                            conversation_data={'conversation_history': self.conversation_history}
                        )
                        
                        # סיכום חכם של השיחה
                        conversation_summary = ci.generate_conversation_summary(
                            full_conversation,
                            {'conversation_history': self.conversation_history}
                        )
                        
                        # עדכון סטטוס אוטומטי
                        new_status = ci.auto_update_lead_status(lead, conversation_summary)
                        
                        # עדכון פתקיות הליד עם התקדמות השיחה הנוכחית
                        if lead.notes:
                            lead.notes += f"\n[Live Call]: {user_text[:100]}... → {bot_reply[:50]}..."
                        else:
                            lead.notes = f"[Live Call]: {user_text[:100]}... → {bot_reply[:50]}..."
                        
                        db.session.commit()
                        
                        # רישום לוגים מפורטים
                        print(f"🎯 Live Call AI Processing: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'})")
                        print(f"📋 Live Summary: {conversation_summary.get('summary', 'N/A')}")
                        print(f"🎭 Live Intent: {conversation_summary.get('intent', 'N/A')}")
                        if DEBUG: print(f"📊 Live Status: {new_status}")
                        print(f"⚡ Live Next Action: {conversation_summary.get('next_action', 'N/A')}")
                        
                except Exception as e:
                    print(f"❌ Customer Intelligence background processing failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # הרץ ברקע כדי לא לחסום את השיחה
            thread = threading.Thread(target=process_in_background, daemon=True)
            thread.start()
            self.background_threads.append(thread)  # ✅ Track for cleanup
            
        except Exception as e:
            print(f"❌ Customer Intelligence setup failed: {e}")
            # אל תקריס את השיחה - המשך רגיל