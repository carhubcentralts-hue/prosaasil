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
        
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"⚠️ [CALL CONFIG] Business {business_id} not found - using defaults")
            return CallConfig(business_id=business_id)
        
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
# ═══════════════════════════════════════════════════════════════
# 🔥 BUILD 191: OPTIMIZED VAD FOR NORMAL HEBREW SPEECH
# Goal: Detect normal conversation volume without requiring shouting
# ═══════════════════════════════════════════════════════════════
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.5"))        # 🔥 BUILD 191: 0.5s - faster response to short words like "כן"
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "12.0"))       # ✅ 12.0s - זמן מספיק לתיאור מפורט
VAD_RMS = int(os.getenv("VAD_RMS", "120"))                  # 🔥 BUILD 191: 120 (was 180) - detect normal speech volume
# 🔥 BUILD 191: BALANCED THRESHOLDS - Detect real speech, filter pure noise
RMS_SILENCE_THRESHOLD = int(os.getenv("RMS_SILENCE_THRESHOLD", "80"))       # 🔥 BUILD 191: 80 (was 120) - lower silence threshold  
MIN_SPEECH_RMS = int(os.getenv("MIN_SPEECH_RMS", "130"))                    # 🔥 BUILD 191: 130 (was 180) - normal speech volume
MIN_SPEECH_DURATION_MS = int(os.getenv("MIN_SPEECH_DURATION_MS", "600"))    # 🔥 BUILD 191: 600ms (was 900) - faster detection
# 🔥 BUILD 191: REDUCED FRAME REQUIREMENT - Detect speech faster
MIN_CONSECUTIVE_VOICE_FRAMES = int(os.getenv("MIN_CONSECUTIVE_VOICE_FRAMES", "4"))  # 🔥 BUILD 191: 4 frames (was 7) = 80ms continuous speech
# 🔥 BUILD 191: SHORTER COOLDOWNS - Faster response after AI speaks
POST_AI_COOLDOWN_MS = int(os.getenv("POST_AI_COOLDOWN_MS", "700"))           # 🔥 BUILD 191: 700ms (was 1200) - faster response
NOISE_HOLD_MS = int(os.getenv("NOISE_HOLD_MS", "150"))                      # 🔥 BUILD 191: 150ms (was 250) - faster noise gate
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "180"))  # 🔥 BUILD 191: 180ms (was 250) - shorter hangover
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "50")) # ⚡ SPEED: 50ms - תגובה מהירה
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "120")) # ⚡ SPEED: 120ms - פחות המתנה
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "1100")) # ⚡ BUILD 107: 1100ms - קירור
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","25"))  # 🔥 BUILD 191: 25 frames (was 45) = ~500ms - easier barge-in

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

# 🔥 BUILD 189: COMPREHENSIVE HEBREW STT DICTIONARY
# המילון הכי מקיף לתיקון טעויות Whisper בעברית
# מכסה: ערים, שירותים, מקצועות, מילים יומיומיות, שמות, ביטויים
HEBREW_NORMALIZATION = {
    # ═══════════════════════════════════════════════════════════════
    # 🔢 מספרים - NUMBERS (כל הווריאציות)
    # ═══════════════════════════════════════════════════════════════
    "אחת": "אחד", "אחאד": "אחד", "אאחד": "אחד", "אחט": "אחד",
    "שתים": "שתיים", "שטיים": "שתיים", "שתאיים": "שתיים", "שתים": "שתיים",
    "שלש": "שלוש", "שלאוש": "שלוש", "שלושש": "שלוש", "שאלוש": "שלוש",
    "ארבה": "ארבע", "ארבאע": "ארבע", "ארבעה": "ארבע", "אארבע": "ארבע",
    "חמישה": "חמש", "חאמש": "חמש", "חמשש": "חמש", "חאמישה": "חמישה",
    "שישה": "שש", "שאש": "שש", "ששש": "שש", "שישש": "שישה",
    "שבעה": "שבע", "שאבע": "שבע", "שבאע": "שבע", "שאבעה": "שבעה",
    "שמנה": "שמונה", "שמאונה": "שמונה", "שמואנה": "שמונה", "שאמונה": "שמונה",
    "תשעה": "תשע", "תאשע": "תשע", "תשאע": "תשע", "תאשעה": "תשעה",
    "עשרה": "עשר", "עאשר": "עשר", "עשאר": "עשר", "אשר": "עשר",
    "אחד עשרה": "אחד עשרה", "שתים עשרה": "שתים עשרה",
    "עשרים": "עשרים", "עאשרים": "עשרים", "עסרים": "עשרים",
    "שלושים": "שלושים", "שאלושים": "שלושים", "שלושאים": "שלושים",
    "ארבעים": "ארבעים", "ארבאעים": "ארבעים", "אארבעים": "ארבעים",
    "חמישים": "חמישים", "חאמישים": "חמישים", "חמישאים": "חמישים",
    "שישים": "שישים", "שאשים": "שישים", "שישאים": "שישים",
    "שבעים": "שבעים", "שאבעים": "שבעים", "שבעאים": "שבעים",
    "שמונים": "שמונים", "שאמונים": "שמונים", "שמונאים": "שמונים",
    "תשעים": "תשעים", "תאשעים": "תשעים", "תשעאים": "תשעים",
    "מאה": "מאה", "מיאה": "מאה", "מאא": "מאה",
    "מאתיים": "מאתיים", "מאטיים": "מאתיים",
    "אלף": "אלף", "אאלף": "אלף", "אלאף": "אלף",
    "אלפיים": "אלפיים", "אלפאיים": "אלפיים",
    
    # ═══════════════════════════════════════════════════════════════
    # 👋 ברכות ופרידות - GREETINGS
    # ═══════════════════════════════════════════════════════════════
    "שלומ": "שלום", "שאלום": "שלום", "שלים": "שלום", "שאלום": "שלום", "שלאום": "שלום",
    "היי יי": "היי", "היייי": "היי", "האיי": "היי", "הייי": "היי",
    "הלוו": "הלו", "הלוא": "הלו", "האלו": "הלו", "הלאו": "הלו",
    "בוקר טוב": "בוקר טוב", "בואקר טוב": "בוקר טוב", "בוקאר טוב": "בוקר טוב",
    "ערב טוב": "ערב טוב", "עארב טוב": "ערב טוב", "ערב טאוב": "ערב טוב",
    "לילה טוב": "לילה טוב", "ליילה טוב": "לילה טוב", "לאילה טוב": "לילה טוב",
    "מה נשמע": "מה נשמע", "מא נשמע": "מה נשמע", "מה נאשמע": "מה נשמע",
    "מה קורה": "מה קורה", "מא קורה": "מה קורה", "מה קאורה": "מה קורה",
    "מה העניינים": "מה העניינים", "מא העניינים": "מה העניינים",
    "ביי יי": "ביי", "ביייי": "ביי", "באיי": "ביי", "ביאי": "ביי",
    "להיתראות": "להתראות", "להתאאות": "להתראות", "להאתראות": "להתראות",
    "שיהיה טוב": "שיהיה טוב", "שאיהיה טוב": "שיהיה טוב",
    "יום טוב": "יום טוב", "יאום טוב": "יום טוב",
    "שבוע טוב": "שבוע טוב", "שאבוע טוב": "שבוע טוב",
    "שבת שלום": "שבת שלום", "שאבת שלום": "שבת שלום",
    "חג שמח": "חג שמח", "חאג שמח": "חג שמח",
    
    # ═══════════════════════════════════════════════════════════════
    # ✅ אישורים והסכמות - CONFIRMATIONS
    # ═══════════════════════════════════════════════════════════════
    "קן": "כן", "קאן": "כן", "יאן": "כן", "כאן": "כן", "קען": "כן",
    "נקון": "נכון", "נכונ": "נכון", "נאכון": "נכון", "נכאון": "נכון",
    "בסדור": "בסדר", "בסדור גמור": "בסדר גמור", "באסדר": "בסדר", "בסאדר": "בסדר",
    "ביידיוק": "בדיוק", "בידיוק": "בדיוק", "באדיוק": "בדיוק", "בדיאוק": "בדיוק",
    "יופיי": "יופי", "יאפי": "יופי", "יואפי": "יופי", "יופאי": "יופי",
    "מעולא": "מעולה", "מאעולה": "מעולה", "מעאולה": "מעולה",
    "מצויין": "מצוין", "מאצוין": "מצוין", "מצואין": "מצוין",
    "מושלאם": "מושלם", "מאושלם": "מושלם", "מושאלם": "מושלם",
    "סבאבה": "סבבה", "סאבאבה": "סבבה", "סאבבה": "סבבה", "סבאבא": "סבבה",
    "אחלא": "אחלה", "אאחלה": "אחלה", "אחאלה": "אחלה", "אחלאה": "אחלה",
    "בטוח": "בטוח", "באטוח": "בטוח", "בטאוח": "בטוח",
    "ברור": "ברור", "בארור": "ברור", "ברואר": "ברור",
    "וודאי": "ודאי", "ואדאי": "ודאי", "וודאאי": "ודאי",
    "כמובן": "כמובן", "כאמובן": "כמובן", "כמואבן": "כמובן",
    "בהחלט": "בהחלט", "באהחלט": "בהחלט", "בהאחלט": "בהחלט",
    "בוודאי": "בוודאי", "באוודאי": "בוודאי", "בוואדאי": "בוודאי",
    
    # ═══════════════════════════════════════════════════════════════
    # ❌ שלילות וסירובים - NEGATIONS
    # ═══════════════════════════════════════════════════════════════
    "לאא": "לא", "לוא": "לא", "לאו": "לא", "לאה": "לא",
    "אף פעם": "אף פעם", "אאף פעם": "אף פעם", "אף פאעם": "אף פעם",
    "בכלל לא": "בכלל לא", "באכלל לא": "בכלל לא",
    "ממש לא": "ממש לא", "מאמש לא": "ממש לא",
    "חס וחלילה": "חס וחלילה", "חאס וחלילה": "חס וחלילה",
    "בשום פנים": "בשום פנים", "באשום פנים": "בשום פנים",
    "לא בטוח": "לא בטוח", "לא באטוח": "לא בטוח",
    "לא יודע": "לא יודע", "לא יואדע": "לא יודע",
    "לא צריך": "לא צריך", "לא צאריך": "לא צריך",
    "לא רוצה": "לא רוצה", "לא רואצה": "לא רוצה",
    "לא עכשיו": "לא עכשיו", "לא עאכשיו": "לא עכשיו",
    "אי אפשר": "אי אפשר", "אאי אפשר": "אי אפשר",
    
    # ═══════════════════════════════════════════════════════════════
    # 🙏 בקשות ונימוסים - REQUESTS & POLITENESS
    # ═══════════════════════════════════════════════════════════════
    "טודה": "תודה", "טודא": "תודה", "תודא": "תודה", "תאודה": "תודה",
    "תודה רבה": "תודה רבה", "תאודה רבה": "תודה רבה", "תודא רבה": "תודה רבה",
    "בבקשא": "בבקשה", "בבאקשה": "בבקשה", "בואקשה": "בבקשה", "באבקשה": "בבקשה",
    "סליחא": "סליחה", "סאליחה": "סליחה", "סליאחה": "סליחה",
    "מצטער": "מצטער", "מאצטער": "מצטער", "מצטאער": "מצטער",
    "מצטערת": "מצטערת", "מאצטערת": "מצטערת",
    "רגאע": "רגע", "רגאה": "רגע", "ראגע": "רגע", "רגאא": "רגע",
    "שניה": "שנייה", "שניא": "שנייה", "שאנייה": "שנייה", "שניאה": "שנייה",
    "דקה": "דקה", "דאקה": "דקה", "דקאה": "דקה",
    "אוקי": "אוקיי", "או קי": "אוקיי", "אוו קי": "אוקיי", "אואקי": "אוקיי",
    "יאללה": "יאללה", "יאלא": "יאללה", "יאלאה": "יאללה", "יאלה": "יאללה",
    "בשמחה": "בשמחה", "באשמחה": "בשמחה", "בשמאחה": "בשמחה",
    "אין בעיה": "אין בעיה", "אאין בעיה": "אין בעיה",
    "בכיף": "בכיף", "באכיף": "בכיף", "בכאיף": "בכיף",
    "עם תענוג": "עם תענוג", "עאם תענוג": "עם תענוג",
    
    # ═══════════════════════════════════════════════════════════════
    # ❓ שאלות - QUESTIONS
    # ═══════════════════════════════════════════════════════════════
    "למא": "למה", "לאמה": "למה", "לאמא": "למה", "למאה": "למה",
    "מאתי": "מתי", "מאתיי": "מתי", "מאתאי": "מתי", "מטי": "מתי",
    "אייפה": "איפה", "אייפא": "איפה", "אאיפה": "איפה", "איפאה": "איפה",
    "כאמה": "כמה", "קאמה": "כמה", "כאמא": "כמה", "כמאה": "כמה",
    "מאה": "מה", "מאא": "מה", "מאע": "מה",
    "איך": "איך", "אאיך": "איך", "אייך": "איך", "איאך": "איך",
    "מי": "מי", "מאי": "מי", "מיי": "מי",
    "מי זה": "מי זה", "מאי זה": "מי זה", "מי זאה": "מי זה",
    "מה זה": "מה זה", "מא זה": "מה זה", "מה זאה": "מה זה",
    "למה לא": "למה לא", "לאמה לא": "למה לא",
    "איזה": "איזה", "אאיזה": "איזה", "איזאה": "איזה",
    "איזו": "איזו", "אאיזו": "איזו", "איזואו": "איזו",
    "האם": "האם", "האאם": "האם", "הא אם": "האם",
    "מדוע": "מדוע", "מאדוע": "מדוע", "מדואע": "מדוע",
    "לאן": "לאן", "לאאן": "לאן", "לאען": "לאן",
    "מאין": "מאין", "מאאין": "מאין", "מאאין": "מאין",
    "באיזה": "באיזה", "באאיזה": "באיזה",
    
    # ═══════════════════════════════════════════════════════════════
    # 📅 ימים בשבוע - DAYS OF WEEK
    # ═══════════════════════════════════════════════════════════════
    "ראאשון": "ראשון", "ראשאון": "ראשון", "ראאשאון": "ראשון",
    "יום ראשון": "יום ראשון", "יאום ראשון": "יום ראשון",
    "שאני": "שני", "שאנאי": "שני", "שניי": "שני",
    "יום שני": "יום שני", "יאום שני": "יום שני",
    "שאלישי": "שלישי", "שלאישי": "שלישי", "שליאשי": "שלישי",
    "יום שלישי": "יום שלישי", "יאום שלישי": "יום שלישי",
    "רביאעי": "רביעי", "ראביעי": "רביעי", "רביעאי": "רביעי",
    "יום רביעי": "יום רביעי", "יאום רביעי": "יום רביעי",
    "חאמישי": "חמישי", "חמאישי": "חמישי", "חמישאי": "חמישי",
    "יום חמישי": "יום חמישי", "יאום חמישי": "יום חמישי",
    "שיאשי": "שישי", "שישאי": "שישי", "שאישי": "שישי",
    "יום שישי": "יום שישי", "יאום שישי": "יום שישי",
    "שאבת": "שבת", "שבאת": "שבת", "שאבאת": "שבת",
    
    # ═══════════════════════════════════════════════════════════════
    # ⏰ זמן ושעות - TIME
    # ═══════════════════════════════════════════════════════════════
    "דאקה": "דקה", "דאקות": "דקות", "דקאות": "דקות", "דאקאות": "דקות",
    "שאעה": "שעה", "שאעות": "שעות", "שעאות": "שעות", "שאעאות": "שעות",
    "יאום": "יום", "יאומים": "ימים", "יומאים": "ימים", "יאמים": "ימים",
    "שאבוע": "שבוע", "שבואע": "שבוע", "שאבועות": "שבועות",
    "חאודש": "חודש", "חודאש": "חודש", "חאדש": "חודש", "חודשים": "חודשים",
    "שאנה": "שנה", "שנאה": "שנה", "שאנים": "שנים",
    "בוקר": "בוקר", "בואקר": "בוקר", "בוקאר": "בוקר",
    "צהריים": "צהריים", "צאהריים": "צהריים", "צהרייאם": "צהריים",
    "אחר הצהריים": "אחר הצהריים", "אאחר הצהריים": "אחר הצהריים",
    "ערב": "ערב", "עארב": "ערב", "ערעב": "ערב",
    "לילה": "לילה", "ליילה": "לילה", "לאילה": "לילה",
    "חצי": "חצי", "חאצי": "חצי", "חצאי": "חצי",
    "רבע": "רבע", "ראבע": "רבע", "רבאע": "רבע",
    "עכשיו": "עכשיו", "עאכשיו": "עכשיו", "עכשאיו": "עכשיו",
    "היום": "היום", "היאום": "היום", "האיום": "היום",
    "מחר": "מחר", "מאחר": "מחר", "מחאר": "מחר",
    "מחרתיים": "מחרתיים", "מאחרתיים": "מחרתיים",
    "אתמול": "אתמול", "אאתמול": "אתמול", "אתמאול": "אתמול",
    "שלשום": "שלשום", "שאלשום": "שלשום",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏙️ ערים גדולות - MAJOR CITIES
    # ═══════════════════════════════════════════════════════════════
    "תאל אביב": "תל אביב", "תאל-אביב": "תל אביב", "תלביב": "תל אביב",
    "תל-אביב": "תל אביב", "תלאביב": "תל אביב", "טל אביב": "תל אביב",
    "תלאביביפו": "תל אביב יפו", "תל אביב-יפו": "תל אביב יפו",
    
    "יארושלים": "ירושלים", "יארושאלים": "ירושלים", "ירושלי": "ירושלים",
    "ירושלם": "ירושלים", "יארושלם": "ירושלים", "ירואשלים": "ירושלים",
    "ירושאלים": "ירושלים", "יראושלים": "ירושלים",
    
    "חאיפה": "חיפה", "כיפה": "חיפה", "קיפה": "חיפה", "היפה": "חיפה",
    "חייפה": "חיפה", "חיאפה": "חיפה", "כייפה": "חיפה", "חאפה": "חיפה",
    
    "באר שאבע": "באר שבע", "באאר שבע": "באר שבע", "בארשבע": "באר שבע",
    "באר שע": "באר שבע", "באר שאבע": "באר שבע", "באר-שבע": "באר שבע",
    "באר שבה": "באר שבע", "ביר שבע": "באר שבע",
    
    "ראמת גן": "רמת גן", "ראמאת גן": "רמת גן", "רמתגן": "רמת גן",
    "רמת גאן": "רמת גן", "רמאת גן": "רמת גן", "ראמת גאן": "רמת גן",
    
    "פאתח תקווה": "פתח תקווה", "פאתח תיקווה": "פתח תקווה",
    "פתחתקווה": "פתח תקווה", "פתח תקוה": "פתח תקווה",
    "פאתח תקוה": "פתח תקווה", "פתח-תקווה": "פתח תקווה",
    
    "נאתניה": "נתניה", "נאתאניה": "נתניה", "נתני": "נתניה",
    "נתניא": "נתניה", "נאתניא": "נתניה", "נתנייה": "נתניה",
    
    "אאשדוד": "אשדוד", "אשדד": "אשדוד", "אאשדד": "אשדוד",
    "אשדואד": "אשדוד", "אסדוד": "אשדוד",
    
    "אאשקלון": "אשקלון", "אשקלו": "אשקלון", "אשקאלון": "אשקלון",
    "אסקלון": "אשקלון", "אשקלאון": "אשקלון",
    
    "חאדרה": "חדרה", "חדארה": "חדרה", "חאדארה": "חדרה",
    "קאריות": "קריות", "קריאות": "קריות",
    
    "ראשון לצי": "ראשון לציון", "ראשלצ": "ראשון לציון",
    "ראשון לציאון": "ראשון לציון", "ראשאון לציון": "ראשון לציון",
    "ראשון-לציון": "ראשון לציון", "רשלצ": "ראשון לציון",
    
    "חולו": "חולון", "חלון": "חולון", "חואלון": "חולון",
    "חולאון": "חולון", "חאולון": "חולון",
    
    "הרצלי": "הרצליה", "הרצליא": "הרצליה", "הארצליה": "הרצליה",
    "הרצאליה": "הרצליה", "הרצליאה": "הרצליה",
    
    "רחבות": "רחובות", "רחאובות": "רחובות", "רחובאות": "רחובות",
    
    "בניברק": "בני ברק", "בני-ברק": "בני ברק", "באני ברק": "בני ברק",
    "בני בראק": "בני ברק", "בניי ברק": "בני ברק",
    
    "בת יאם": "בת ים", "בת-ים": "בת ים", "באת ים": "בת ים",
    "בתים": "בת ים", "בת יאים": "בת ים",
    
    "גבעתיים": "גבעתיים", "גבעתים": "גבעתיים", "גאבעתיים": "גבעתיים",
    "גבעאתיים": "גבעתיים", "גבעת-יים": "גבעתיים",
    
    "כפר סאבא": "כפר סבא", "כפר-סבא": "כפר סבא", "כאפר סבא": "כפר סבא",
    "כפרסבא": "כפר סבא", "כפר סאבה": "כפר סבא",
    
    "רעננא": "רעננה", "ראעננה": "רעננה", "רעאננה": "רעננה",
    "רעננאה": "רעננה", "ראענה": "רעננה",
    
    "הוד השארון": "הוד השרון", "הודהשרון": "הוד השרון",
    "הוד-השרון": "הוד השרון", "הואד השרון": "הוד השרון",
    
    "נס ציואנה": "נס ציונה", "נס-ציונה": "נס ציונה",
    "נאס ציונה": "נס ציונה", "נסציונה": "נס ציונה",
    
    "ראמת השרון": "רמת השרון", "רמת-השרון": "רמת השרון",
    "רמאת השרון": "רמת השרון", "רמתהשרון": "רמת השרון",
    
    "ראש העאין": "ראש העין", "ראש-העין": "ראש העין",
    "ראאש העין": "ראש העין", "ראש העיין": "ראש העין",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏘️ ערים נוספות - MORE CITIES
    # ═══════════════════════════════════════════════════════════════
    "נצארת": "נצרת", "נאצרת": "נצרת", "נצראת": "נצרת",
    "עפואלה": "עפולה", "עאפולה": "עפולה", "עפולאה": "עפולה",
    "טבאריה": "טבריה", "טבריא": "טבריה", "טבאריא": "טבריה",
    "כארמיאל": "כרמיאל", "כרמיעל": "כרמיאל", "כרמיאאל": "כרמיאל",
    "צאפת": "צפת", "צפאת": "צפת", "סאפד": "צפת", "סאפת": "צפת",
    "עאכו": "עכו", "עכא": "עכו", "עאכא": "עכו",
    "נאהריה": "נהריה", "נהארייה": "נהריה", "נהריאה": "נהריה",
    "אאילת": "אילת", "איילת": "אילת", "אילאת": "אילת", "אלת": "אילת",
    "דאימונה": "דימונה", "דימונא": "דימונה", "דימאונה": "דימונה",
    "ערד": "ערד", "עאראד": "ערד", "ערראד": "ערד",
    "מצפה רממון": "מצפה רמון", "מצפה-רמון": "מצפה רמון",
    "מאצפה רמון": "מצפה רמון", "מצפה ראמון": "מצפה רמון",
    "ירוחאם": "ירוחם", "יאירוחם": "ירוחם",
    "נטיבות": "נתיבות", "נתיבאות": "נתיבות", "נאתיבות": "נתיבות",
    "שדאירות": "שדרות", "שדרואת": "שדרות",
    "אופאקים": "אופקים", "אואפקים": "אופקים",
    "קריאת גת": "קריית גת", "קריית-גת": "קריית גת",
    "קריאת שמונה": "קריית שמונה", "קריית-שמונה": "קריית שמונה",
    "קריאת ים": "קריית ים", "קריית-ים": "קריית ים",
    "קריאת אתא": "קריית אתא", "קריית-אתא": "קריית אתא",
    "קריאת ביאליק": "קריית ביאליק", "קריית-ביאליק": "קריית ביאליק",
    "קריאת מוצקין": "קריית מוצקין", "קריית-מוצקין": "קריית מוצקין",
    "קריאת אונו": "קריית אונו", "קריית-אונו": "קריית אונו",
    "מעאלות": "מעלות", "מעלואת": "מעלות",
    "מעלות-תרשיחא": "מעלות תרשיחא", "מעאלות תרשיחא": "מעלות תרשיחא",
    "יאבנה": "יבנה", "יבנא": "יבנה", "יבאנה": "יבנה",
    "לאוד": "לוד", "לואד": "לוד",
    "ראמלה": "רמלה", "רמלא": "רמלה", "ראמלא": "רמלה",
    "גאדרה": "גדרה", "גדירה": "גדרה", "גאדירה": "גדרה",
    "מאודיעין": "מודיעין", "מודעין": "מודיעין", "מודאיעין": "מודיעין",
    "ביית שמש": "בית שמש", "בית-שמש": "בית שמש",
    "באית שמש": "בית שמש", "בית שמס": "בית שמש",
    "ביית שאן": "בית שאן", "בית-שאן": "בית שאן",
    "באית שאן": "בית שאן", "ביתשאן": "בית שאן",
    "אלעאד": "אלעד", "אאלעד": "אלעד",
    "נאשר": "נשר", "נשאר": "נשר",
    "טאירת הכרמל": "טירת הכרמל", "טירת-הכרמל": "טירת הכרמל",
    "מגדאל העמק": "מגדל העמק", "מגדל-העמק": "מגדל העמק",
    "זאיכרון יעקב": "זכרון יעקב", "זכרון-יעקב": "זכרון יעקב",
    "בנאימינה": "בנימינה", "בנימינא": "בנימינה",
    "מבשארת ציון": "מבשרת ציון", "מבשרת-ציון": "מבשרת ציון",
    "אבו גאוש": "אבו גוש", "אבו-גוש": "אבו גוש",
    
    # ═══════════════════════════════════════════════════════════════
    # 👷 מקצועות ושירותים - PROFESSIONS & SERVICES
    # ═══════════════════════════════════════════════════════════════
    # שירותי בית
    "זלטות": "דלתות", "לתות": "דלתות", "דלות": "דלתות",
    "דאלתות": "דלתות", "דלתאות": "דלתות", "תלתות": "דלתות",
    "מנעולי": "מנעולן", "מנאולן": "מנעולן", "מאנעולן": "מנעולן",
    "מנעאולן": "מנעולן", "מנעולאן": "מנעולן", "מנאעולן": "מנעולן",
    "אינסטלטר": "אינסטלטור", "אינסטלציה": "אינסטלטור",
    "אאינסטלטור": "אינסטלטור", "אינסטלאטור": "אינסטלטור",
    "אינסטלאציה": "אינסטלציה", "אאינסטלציה": "אינסטלציה",
    "חשמלי": "חשמלאי", "חאשמלאי": "חשמלאי", "חשמאלאי": "חשמלאי",
    "חשמאל": "חשמל", "חאשמל": "חשמל",
    "שרבוב": "שרברב", "שארברב": "שרברב", "שרבראב": "שרברב",
    "מזגני": "מזגנים", "מאזגנים": "מזגנים", "מזגאנים": "מזגנים",
    "מיזוג": "מיזוג אוויר", "מאיזוג": "מיזוג", "מיזאוג": "מיזוג",
    "מיזוג אויר": "מיזוג אוויר", "מאיזוג אוויר": "מיזוג אוויר",
    "צביעא": "צביעה", "צאביעה": "צביעה", "צביאעה": "צביעה",
    "צבאע": "צבע", "צאבע": "צבע",
    "אילומינציה": "אלומיניום", "אלומיניאום": "אלומיניום",
    "גיפסון": "גבס", "גאבס": "גבס", "גבאס": "גבס",
    "ריצפאות": "ריצפות", "ריצאפות": "ריצפות",
    "גראניט": "גרניט", "גרניאט": "גרניט",
    "שאיש": "שיש", "שיאש": "שיש",
    "פארקט": "פרקט", "פרקאט": "פרקט",
    "קאבלן": "קבלן", "קבלאן": "קבלן",
    "שיפוצאים": "שיפוצים", "שאיפוצים": "שיפוצים", "שיפאוצים": "שיפוצים",
    "בנאי": "בנאי", "בנאאי": "בנאי", "באנאי": "בנאי",
    "נגארות": "נגרות", "נאגרות": "נגרות",
    "נגאר": "נגר", "נאגר": "נגר",
    "רהיאטים": "רהיטים", "ראהיטים": "רהיטים",
    "אריחאים": "אריחים", "ארייחים": "אריחים",
    "סניטארי": "סניטרי", "סאניטרי": "סניטרי",
    "ברזאים": "ברזים", "בארזים": "ברזים",
    
    # שירותי רכב
    "מכאונאי": "מכונאי", "מאכונאי": "מכונאי", "מכונאאי": "מכונאי",
    "מוסאך": "מוסך", "מאוסך": "מוסך", "מוסאך": "מוסך",
    "פחאח": "פחחות", "פאחחות": "פחחות", "פחאחות": "פחחות",
    "צמיגאים": "צמיגים", "צאמיגים": "צמיגים",
    "גאררר": "גרר", "גארר": "גרר",
    "גרירא": "גרירה", "גארירה": "גרירה",
    "רכאב": "רכב", "ראכב": "רכב",
    "אאוטו": "אוטו", "אוטאו": "אוטו",
    
    # שירותי בריאות
    "רופאא": "רופא", "ראופא": "רופא",
    "דוקאטור": "דוקטור", "דאוקטור": "דוקטור",
    "מארפאה": "מרפאה", "מרפאאה": "מרפאה",
    "בית חואלים": "בית חולים", "ביתחולים": "בית חולים",
    "שינאיים": "שיניים", "שאיניים": "שיניים",
    "רופא שיניים": "רופא שיניים", "רופאא שיניים": "רופא שיניים",
    "עיינים": "עיניים", "עאיניים": "עיניים",
    "רואפא עיניים": "רופא עיניים",
    "אחאות": "אחות", "אאחות": "אחות",
    "מאחלקה": "מחלקה", "מחאלקה": "מחלקה",
    "טיפאול": "טיפול", "טאיפול": "טיפול",
    "בדיקא": "בדיקה", "באדיקה": "בדיקה",
    "תרופאות": "תרופות", "תארופות": "תרופות",
    "בית מרקאחת": "בית מרקחת", "ביתמרקחת": "בית מרקחת",
    "מרקאחת": "מרקחת", "מארקחת": "מרקחת",
    
    # שירותים משפטיים ופיננסיים
    "עורך דאין": "עורך דין", "עוארך דין": "עורך דין",
    "רואה חאשבון": "רואה חשבון", "רואאה חשבון": "רואה חשבון",
    "בנאק": "בנק", "באנק": "בנק",
    "ביטואח": "ביטוח", "באיטוח": "ביטוח",
    "סואכן": "סוכן", "סוכאן": "סוכן",
    "מתווך": "מתווך", "מאתווך": "מתווך", "מתואוך": "מתווך",
    "נדלאן": "נדל\"ן", "נדלן": "נדל\"ן",
    "משכאנתא": "משכנתא", "מאשכנתא": "משכנתא",
    "הלוואה": "הלוואה", "הלואאה": "הלוואה", "האלוואה": "הלוואה",
    "אאשראי": "אשראי", "אשראאי": "אשראי",
    
    # חינוך
    "מאורה": "מורה", "מורא": "מורה",
    "גנאנת": "גננת", "גאננת": "גננת",
    "בית סאפר": "בית ספר", "ביתספר": "בית ספר",
    "גאן": "גן", "גאן ילדים": "גן ילדים",
    "תלמאיד": "תלמיד", "תאלמיד": "תלמיד",
    "מנאהל": "מנהל", "מאנהל": "מנהל",
    "לאימוד": "לימוד", "לימאוד": "לימוד",
    "שאיעור": "שיעור", "שיעאור": "שיעור",
    
    # מזון ומסעדות
    "מסעאדה": "מסעדה", "מאסעדה": "מסעדה",
    "קייטארינג": "קייטרינג", "קאייטרינג": "קייטרינג",
    "שאף": "שף", "שאף": "שף",
    "טבאח": "טבח", "טאבח": "טבח",
    "מאפייא": "מאפייה", "מאאפייה": "מאפייה",
    "קונדיטאוריה": "קונדיטוריה", "קאונדיטוריה": "קונדיטוריה",
    
    # יופי וטיפוח
    "ספאר": "ספר", "סאפר": "ספר",
    "מספארה": "מספרה", "מאספרה": "מספרה",
    "מאניקור": "מניקור", "מנאיקור": "מניקור",
    "פדיקאור": "פדיקור", "פאדיקור": "פדיקור",
    "איפאור": "איפור", "אאיפור": "איפור",
    "קוסמטאיקה": "קוסמטיקה", "קאוסמטיקה": "קוסמטיקה",
    
    # הובלות וניקיון
    "הובלאות": "הובלות", "האובלות": "הובלות",
    "נאיקיון": "ניקיון", "ניקיאון": "ניקיון",
    "מאנקה": "מנקה", "מנאקה": "מנקה",
    "עובאד": "עובד", "עאובד": "עובד",
    "אאריזה": "אריזה", "אריזא": "אריזה",
    "הובאלה": "הובלה", "האובלה": "הובלה",
    "מעאבר דירה": "מעבר דירה", "מאעבר דירה": "מעבר דירה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔧 שירותי בית נוספים - MORE HOME SERVICES
    # ═══════════════════════════════════════════════════════════════
    "גזאם": "גזם", "גאזם": "גזם", "גיזום": "גיזום", "גאיזום": "גיזום",
    "גנאן": "גנן", "גאנן": "גנן", "גננאות": "גננות", "גנאנות": "גננות",
    "ספאה": "ספה", "סאפה": "ספה", "ספות": "ספות", "סאפות": "ספות",
    "ריפאוד": "ריפוד", "ראיפוד": "ריפוד", "רפאד": "רפד", "ראפד": "רפד",
    "וילאונות": "וילונות", "ואילונות": "וילונות",
    "פארגולה": "פרגולה", "פרגאולה": "פרגולה", "פארגולות": "פרגולות",
    "סאככה": "סככה", "סכאכה": "סככה", "סאככות": "סככות",
    "גאראז": "גראז'", "גאראז'": "גראז'",
    "תאריס": "תריס", "תריאס": "תריס", "תאריסים": "תריסים",
    "ראשת": "רשת", "רשאת": "רשת", "ראשתות": "רשתות",
    "סאורגים": "סורגים", "סורגאים": "סורגים",
    "מעאקה": "מעקה", "מעקאה": "מעקה", "מעאקות": "מעקות",
    "פאיסול": "פיסול", "פיסאול": "פיסול",
    "זיגאוג": "זיגוג", "זאיגוג": "זיגוג", "זגאג": "זגג", "זאגג": "זגג",
    "מראאות": "מראות", "מאראות": "מראות",
    "אינטארקום": "אינטרקום", "אאינטרקום": "אינטרקום",
    "מאנעול": "מנעול", "מנעאול": "מנעול", "מאנעולים": "מנעולים",
    "קאודח": "קודח", "קודאח": "קודח", "קאדיחה": "קדיחה",
    "שלאט": "שלט", "שלאט רחוק": "שלט רחוק",
    "אאזעקה": "אזעקה", "אזעאקה": "אזעקה", "אזאעקות": "אזעקות",
    "מאצלמה": "מצלמה", "מצלאמה": "מצלמה", "מאצלמות": "מצלמות",
    "אאבטחה": "אבטחה", "אבטאחה": "אבטחה",
    "מיגאון": "מיגון", "מאיגון": "מיגון",
    "כספאת": "כספת", "כאספת": "כספת", "כאספות": "כספות",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏗️ בנייה ושיפוצים - CONSTRUCTION & RENOVATION
    # ═══════════════════════════════════════════════════════════════
    "אדריכאל": "אדריכל", "אאדריכל": "אדריכל", "אדריכאלות": "אדריכלות",
    "מהנדאס": "מהנדס", "מאהנדס": "מהנדס", "הנדאסה": "הנדסה",
    "שארטט": "שרטט", "שרטאט": "שרטט", "שארטוט": "שרטוט",
    "מאודד": "מודד", "מודאד": "מודד", "מאדידה": "מדידה",
    "פאיקוח": "פיקוח", "פיקאוח": "פיקוח", "מאפקח": "מפקח",
    "יאזם": "יזם", "יזאם": "יזם", "יאזמות": "יזמות",
    "טאפסן": "טפסן", "טפסאן": "טפסן", "טאפסנות": "טפסנות",
    "ברזאל": "ברזל", "באריזל": "ברזל",
    "ריתאוך": "ריתוך", "ראיתוך": "ריתוך", "ראתך": "רתך",
    "מאסגרייה": "מסגרייה", "מסגראייה": "מסגרייה", "מאסגר": "מסגר",
    "פאח": "פח", "פאחחות": "פחחות",
    "סאבך": "סבך", "סבאך": "סבך",
    "עאופר": "עופר", "עופאר": "עופר",
    "חאפירה": "חפירה", "חפיראה": "חפירה", "חאופר": "חופר",
    "מאחפרון": "מחפרון", "מחפראון": "מחפרון",
    "טארקטור": "טרקטור", "טרקטאור": "טרקטור",
    "מאנוף": "מנוף", "מנואף": "מנוף", "מאנופאי": "מנופאי",
    "עאגורן": "עגורן", "עגוראן": "עגורן",
    "פאיגומים": "פיגומים", "פיגומאים": "פיגומים",
    "באטון": "בטון", "בטאון": "בטון", "באטונאדה": "בטונדה",
    "יאציקה": "יציקה", "יציקאה": "יציקה",
    "זאפת": "זפת", "זפאת": "זפת", "זיאפות": "זיפות",
    "אאיטום": "איטום", "איטאום": "איטום",
    "באידוד": "בידוד", "בידאוד": "בידוד",
    "טאיח": "טיח", "טיאח": "טיח", "טאייח": "טייח",
    "שאפכטל": "שפכטל", "שפכטאל": "שפכטל",
    
    # ═══════════════════════════════════════════════════════════════
    # 🚰 אינסטלציה מורחב - EXTENDED PLUMBING
    # ═══════════════════════════════════════════════════════════════
    "צאנרת": "צנרת", "צנראת": "צנרת", "צאנרות": "צנרות",
    "ברזאים": "ברזים", "בארזים": "ברזים",
    "דאוד שמש": "דוד שמש", "דואד שמש": "דוד שמש",
    "בויאלר": "בוילר", "בואילר": "בוילר",
    "מאזגון": "מזגון", "מזגאון": "מזגון",
    "קאולט": "קולט", "קולאט": "קולט",
    "ניקאוז": "ניקוז", "נאיקוז": "ניקוז",
    "בואר": "בור", "בוארות": "בורות", "בור ספיאגה": "בור ספיגה",
    "שאפכים": "שפכים", "שפכאים": "שפכים",
    "באיוב": "ביוב", "ביואב": "ביוב",
    "פאתיחה": "פתיחה", "פתיחאה": "פתיחה",
    "סאתימה": "סתימה", "סתימאה": "סתימה",
    "הצאפה": "הצפה", "הצפאה": "הצפה",
    "נאזילה": "נזילה", "נזילאה": "נזילה",
    "איתאור נזילות": "איתור נזילות", "אאיתור נזילות": "איתור נזילות",
    "חאימום": "חימום", "חימאום": "חימום",
    "רדיאאטור": "רדיאטור", "רדיאטאור": "רדיאטור",
    
    # ═══════════════════════════════════════════════════════════════
    # ⚡ חשמל מורחב - EXTENDED ELECTRICAL
    # ═══════════════════════════════════════════════════════════════
    "לאוח חשמל": "לוח חשמל", "לואח חשמל": "לוח חשמל",
    "שאקע": "שקע", "שקאע": "שקע", "שאקעים": "שקעים",
    "מאפסק": "מפסק", "מפסאק": "מפסק", "מאפסקים": "מפסקים",
    "נאורה": "נורה", "נוראה": "נורה", "נאורות": "נורות",
    "מאנורה": "מנורה", "מנוראה": "מנורה", "מאנורות": "מנורות",
    "נאברשת": "נברשת", "נברשאת": "נברשת",
    "לאד": "לד", "לאדים": "לדים", "תאאורה": "תאורה",
    "סאפוט": "ספוט", "ספואט": "ספוט", "סאפוטים": "ספוטים",
    "כאבל": "כבל", "כבאל": "כבל", "כאבלים": "כבלים",
    "חאוט": "חוט", "חואט": "חוט", "חאוטים": "חוטים",
    "הארקה": "הארקה", "האארקה": "הארקה",
    "פאיוז": "פיוז", "פיוזאים": "פיוזים",
    "שנאאי": "שנאי", "שאנאי": "שנאי",
    "גנאראטור": "גנרטור", "גנרטאור": "גנרטור",
    "אאל פסק": "אל פסק", "אל-פסק": "אל פסק",
    "סאולרי": "סולרי", "סולארי": "סולרי", "פאנלים סולריים": "פאנלים סולריים",
    
    # ═══════════════════════════════════════════════════════════════
    # 🛠️ כלי עבודה - TOOLS
    # ═══════════════════════════════════════════════════════════════
    "מאקדחה": "מקדחה", "מקדאחה": "מקדחה",
    "מאברג": "מברג", "מבראג": "מברג", "מאברגים": "מברגים",
    "פאטיש": "פטיש", "פטיאש": "פטיש", "פאטישים": "פטישים",
    "מאסור": "מסור", "מסואר": "מסור", "מאסורים": "מסורים",
    "מאשור": "משור", "משואר": "משור",
    "צאבת": "צבת", "צבאת": "צבת", "צאבתות": "צבתות",
    "מאפתח": "מפתח", "מפתאח": "מפתח", "מאפתחות": "מפתחות",
    "סאלם": "סלם", "סלאם": "סלם", "סאולם": "סולם",
    "מאדרגה": "מדרגה", "מדרגאה": "מדרגה",
    "עאגלה": "עגלה", "עגלאה": "עגלה",
    "דאלי": "דלי", "דליי": "דלי", "דאליים": "דליים",
    "מאברשת": "מברשת", "מברשאת": "מברשת",
    "מאגב": "מגב", "מגאב": "מגב",
    "סאמרטוט": "סמרטוט", "סמרטואט": "סמרטוט",
    
    # ═══════════════════════════════════════════════════════════════
    # 🚙 רכב מורחב - EXTENDED AUTOMOTIVE
    # ═══════════════════════════════════════════════════════════════
    "מאנוע": "מנוע", "מנואע": "מנוע", "מאנועים": "מנועים",
    "גאיר": "גיר", "גיאר": "גיר", "תאיבת הילוכים": "תיבת הילוכים",
    "באלמים": "בלמים", "בלאמים": "בלמים", "באלם": "בלם",
    "מאתלה": "מתלה", "מתלאה": "מתלה", "מאתלים": "מתלים",
    "אאמורטיזטור": "אמורטיזטור", "אמורטיזאטור": "אמורטיזטור",
    "סאפוג": "ספוג", "ספואג": "ספוג",
    "רדיאאטור": "רדיאטור", "רדיאטאור": "רדיאטור",
    "מאזגן לרכב": "מזגן לרכב", "מזגאן לרכב": "מזגן לרכב",
    "שאמשה": "שמשה", "שמשאה": "שמשה", "שאמשות": "שמשות",
    "מאגב שמשה": "מגב שמשה", "מגאב שמשה": "מגב שמשה",
    "פאנס": "פנס", "פנאס": "פנס", "פאנסים": "פנסים",
    "פאר קדמי": "פר קדמי", "פאר אחורי": "פר אחורי",
    "כאנפיים": "כנפיים", "כנפייאם": "כנפיים",
    "מאכסה מנוע": "מכסה מנוע", "מכסאה מנוע": "מכסה מנוע",
    "תאא מטען": "תא מטען", "תאא באגאז'": "תא בגאז'",
    "צאמיג": "צמיג", "צמיאג": "צמיג", "צאמיגים": "צמיגים",
    "גאלגל": "גלגל", "גלגאל": "גלגל", "גאלגלים": "גלגלים",
    "חאילוף גלגל": "חילוף גלגל", "חילאוף גלגל": "חילוף גלגל",
    "ניפאוח": "ניפוח", "נאיפוח": "ניפוח",
    "אאיזון": "איזון", "איזאון": "איזון",
    "פאינצ'ר": "פנצ'ר", "פאנצר": "פנצ'ר", "פאנצ'ריה": "פנצ'ריה",
    
    # ═══════════════════════════════════════════════════════════════
    # 👨‍⚕️ רפואה מורחב - EXTENDED MEDICAL
    # ═══════════════════════════════════════════════════════════════
    "פאיזיותרפיה": "פיזיותרפיה", "פיזיותראפיה": "פיזיותרפיה",
    "פיזיותארפיסט": "פיזיותרפיסט", "פאיזיותרפיסט": "פיזיותרפיסט",
    "קאירופרקט": "כירופרקט", "כירופראקט": "כירופרקט",
    "אאוסטאופת": "אוסטאופת", "אוסטאופאת": "אוסטאופת",
    "נאטורופת": "נטורופת", "נטורופאת": "נטורופת",
    "דיאטאן": "דיאטן", "דיאטאנית": "דיאטנית",
    "תזאונאי": "תזונאי", "תזונאאי": "תזונאי",
    "פאסיכולוג": "פסיכולוג", "פסיכאולוג": "פסיכולוג",
    "פאסיכיאטר": "פסיכיאטר", "פסיכיאאטר": "פסיכיאטר",
    "לאוגופד": "לוגופד", "לוגופאד": "לוגופד",
    "ריפאוי בעיסוק": "ריפוי בעיסוק", "ראיפוי בעיסוק": "ריפוי בעיסוק",
    "מאעסה": "מעסה", "מעסאה": "מעסה", "עאיסוי": "עיסוי",
    "אאקופונקטורה": "אקופונקטורה", "אקופאונקטורה": "אקופונקטורה",
    "רפלאקסולוגיה": "רפלקסולוגיה", "רפלקסאולוגיה": "רפלקסולוגיה",
    "שיאאצו": "שיאצו", "שאיאצו": "שיאצו",
    "אאורתופד": "אורתופד", "אורתופאד": "אורתופד",
    "קארדיולוג": "קרדיולוג", "קרדיאולוג": "קרדיולוג",
    "נאוירולוג": "נוירולוג", "נוירולאוג": "נוירולוג",
    "אאונקולוג": "אונקולוג", "אונקולאוג": "אונקולוג",
    "גינאקולוג": "גינקולוג", "גינקולאוג": "גינקולוג",
    "אאורולוג": "אורולוג", "אורולאוג": "אורולוג",
    "דארמטולוג": "דרמטולוג", "דרמטולאוג": "דרמטולוג",
    "אאף אוזן גרון": "אף אוזן גרון", "אף-אוזן-גרון": "אף אוזן גרון",
    "ראנטגן": "רנטגן", "רנטגאן": "רנטגן",
    "אאולטרסאונד": "אולטרסאונד", "אולטראסאונד": "אולטרסאונד",
    "אםארטי": "MRI", "סיטי": "CT",
    "בדיקאת דם": "בדיקת דם", "באדיקת דם": "בדיקת דם",
    "בדיקאת שתן": "בדיקת שתן", "באדיקת שתן": "בדיקת שתן",
    
    # ═══════════════════════════════════════════════════════════════
    # 💈 יופי וטיפוח מורחב - EXTENDED BEAUTY
    # ═══════════════════════════════════════════════════════════════
    "צאבע": "צבע", "צבאע": "צבע", "צאביעה": "צביעה",
    "האילייטס": "הייליטס", "היילאייטס": "הייליטס",
    "באלאיאז'": "בלאיאז'", "בלאייאז'": "בלאיאז'",
    "אאומברה": "אומברה", "אומבראה": "אומברה",
    "תאספורת": "תספורת", "תספאורת": "תספורת",
    "פאן": "פן", "פאן לשיער": "פן לשיער",
    "מאחליק": "מחליק", "מחליאק": "מחליק",
    "סאלסול": "סלסול", "סלסאול": "סלסול",
    "תאלתלים": "תלתלים", "תלתאלים": "תלתלים",
    "קארטין": "קרטין", "קרטאין": "קרטין",
    "החאלקה": "החלקה", "החלאקה": "החלקה",
    "האארכות שיער": "הארכות שיער", "הארכאות שיער": "הארכות שיער",
    "פאאה": "פאה", "פאאות": "פאות",
    "גבאות": "גבות", "עאיצוב גבות": "עיצוב גבות",
    "הסארת שיער": "הסרת שיער", "הסראת שיער": "הסרת שיער",
    "לאייזר": "לייזר", "לייזאר": "לייזר",
    "שאעווה": "שעווה", "שעוואה": "שעווה",
    "פאילינג": "פילינג", "פילאינג": "פילינג",
    "באוטוקס": "בוטוקס", "בוטאוקס": "בוטוקס",
    "חאומצה היאלורונית": "חומצה היאלורונית",
    "מאזותרפיה": "מזותרפיה", "מזותראפיה": "מזותרפיה",
    "טאיפוח פנים": "טיפוח פנים", "טיפאוח פנים": "טיפוח פנים",
    "ניקאוי פנים": "ניקוי פנים", "נאיקוי פנים": "ניקוי פנים",
    "מאסכה": "מסכה", "מסכאה": "מסכה", "מאסכות": "מסכות",
    
    # ═══════════════════════════════════════════════════════════════
    # 👔 אופנה וביגוד - FASHION & CLOTHING
    # ═══════════════════════════════════════════════════════════════
    "חאייט": "חייט", "חייאט": "חייט", "חאייטות": "חייטות",
    "תאפירה": "תפירה", "תפיראה": "תפירה",
    "עאיצוב אופנה": "עיצוב אופנה", "עיצאוב אופנה": "עיצוב אופנה",
    "מאעצב": "מעצב", "מעצאב": "מעצב", "מאעצבת": "מעצבת",
    "באד": "בד", "באדים": "בדים",
    "חאוט תפירה": "חוט תפירה", "חואט תפירה": "חוט תפירה",
    "כאפתור": "כפתור", "כפתאור": "כפתור", "כאפתורים": "כפתורים",
    "ראוכסן": "רוכסן", "רוכסאן": "רוכסן",
    "תאיקון בגדים": "תיקון בגדים", "תיקאון בגדים": "תיקון בגדים",
    "קאיצור": "קיצור", "קיצאור": "קיצור",
    "האארכה": "הארכה", "הארכאה": "הארכה",
    "האצרה": "הצרה", "הצראה": "הצרה",
    "הארחאבה": "הרחבה", "הרחבאה": "הרחבה",
    "מאכבסה": "מכבסה", "מכבסאה": "מכבסה",
    "ניקאוי יבש": "ניקוי יבש", "נאיקוי יבש": "ניקוי יבש",
    "גאיהוץ": "גיהוץ", "גיהאוץ": "גיהוץ",
    "כאביסה": "כביסה", "כביסאה": "כביסה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎨 אמנות ויצירה - ART & CRAFTS
    # ═══════════════════════════════════════════════════════════════
    "צאייר": "צייר", "צייאר": "צייר", "צאיירת": "ציירת",
    "פאסל": "פסל", "פסאל": "פסל", "פאסלת": "פסלת",
    "צאילום": "צילום", "צילאום": "צילום", "צאלם": "צלם",
    "וידאאו": "וידאו", "וידיאו": "וידאו", "צאלם וידאו": "צלם וידאו",
    "עאריכה": "עריכה", "עריכאה": "עריכה", "עאורך": "עורך",
    "גארפיקה": "גרפיקה", "גרפיקאה": "גרפיקה",
    "עאיצוב גרפי": "עיצוב גרפי", "עיצאוב גרפי": "עיצוב גרפי",
    "אאילוסטרציה": "אילוסטרציה", "אילוסטראציה": "אילוסטרציה",
    "אאנימציה": "אנימציה", "אנימאציה": "אנימציה",
    "מאוזיקאי": "מוזיקאי", "מוזיקאאי": "מוזיקאי",
    "זאמר": "זמר", "זמאר": "זמר", "זאמרת": "זמרת",
    "נאגן": "נגן", "נגאן": "נגן", "נאגנית": "נגנית",
    "מאלחין": "מלחין", "מלחאין": "מלחין",
    "מאפיק": "מפיק", "מפיאק": "מפיק",
    "דאי ג'יי": "די ג'יי", "דאי-ג'יי": "די ג'יי",
    "סאאונד": "סאונד", "סאאונדמן": "סאונדמן",
    "תאאורן": "תאורן", "תאוראן": "תאורן",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎭 אירועים ובידור - EVENTS & ENTERTAINMENT
    # ═══════════════════════════════════════════════════════════════
    "אאולם אירועים": "אולם אירועים", "אולאם אירועים": "אולם אירועים",
    "גאן אירועים": "גן אירועים", "גאן איראועים": "גן אירועים",
    "חאתונה": "חתונה", "חתונאה": "חתונה", "חאתונות": "חתונות",
    "באר מצווה": "בר מצווה", "באר-מצווה": "בר מצווה",
    "באת מצווה": "בת מצווה", "באת-מצווה": "בת מצווה",
    "בראית": "ברית", "בריאת": "ברית", "בראית מילה": "ברית מילה",
    "יום האולדת": "יום הולדת", "יום הולאדת": "יום הולדת",
    "מאסיבה": "מסיבה", "מסיבאה": "מסיבה",
    "אאירוע": "אירוע", "אירואע": "אירוע",
    "הפאקה": "הפקה", "הפקאה": "הפקה", "מאפיק אירועים": "מפיק אירועים",
    "צאלם אירועים": "צלם אירועים", "צלאם אירועים": "צלם אירועים",
    "וידאאוגרף": "וידאוגרף", "וידיאוגראף": "וידאוגרף",
    "לאהקה": "להקה", "להקאה": "להקה",
    "זאמר לאירועים": "זמר לאירועים", "זמאר לאירועים": "זמר לאירועים",
    "קאוסם": "קוסם", "קוסאם": "קוסם",
    "לאיצן": "ליצן", "ליצאן": "ליצן",
    "עאמדת צילום": "עמדת צילום", "עמדאת צילום": "עמדת צילום",
    "פאוטובוט": "פוטובוט", "פוטובואט": "פוטובוט",
    "עאיצוב אירועים": "עיצוב אירועים", "עיצאוב אירועים": "עיצוב אירועים",
    "פארחים": "פרחים", "פרחאים": "פרחים", "פאלורית": "פלוריסט",
    "באלונים": "בלונים", "בלונאים": "בלונים",
    "קאישוט": "קישוט", "קישואט": "קישוט",
    
    # ═══════════════════════════════════════════════════════════════
    # 🐕 חיות מחמד - PETS
    # ═══════════════════════════════════════════════════════════════
    "ואטרינר": "וטרינר", "וטרינאר": "וטרינר",
    "מארפאת חיות": "מרפאת חיות", "מרפאאת חיות": "מרפאת חיות",
    "פאנסיון לכלבים": "פנסיון לכלבים", "פנסיאון לכלבים": "פנסיון לכלבים",
    "דאייסיטר": "דייסיטר", "דייסיטאר": "דייסיטר",
    "דאוג ווקר": "דוג ווקר", "הוליכאת כלבים": "הולכת כלבים",
    "מאאלף": "מאלף", "מאלאף": "מאלף", "אאילוף": "אילוף",
    "גראומר": "גרומר", "גרומאר": "גרומר",
    "טאיפוח כלבים": "טיפוח כלבים", "טיפאוח כלבים": "טיפוח כלבים",
    "רחאיצה": "רחיצה", "רחיצאה": "רחיצה",
    "תספאורת לכלב": "תספורת לכלב", "תסאפורת לכלב": "תספורת לכלב",
    "מאזון לחיות": "מזון לחיות", "מזאון לחיות": "מזון לחיות",
    "חנאות חיות": "חנות חיות", "חנואת חיות": "חנות חיות",
    
    # ═══════════════════════════════════════════════════════════════
    # 💻 טכנולוגיה ומחשבים - TECHNOLOGY
    # ═══════════════════════════════════════════════════════════════
    "מאתכנת": "מתכנת", "מתכנאת": "מתכנת", "תאכנות": "תכנות",
    "מאפתח": "מפתח", "מפתאח": "מפתח", "פאיתוח": "פיתוח",
    "עאיצוב אתרים": "עיצוב אתרים", "עיצאוב אתרים": "עיצוב אתרים",
    "באניית אתרים": "בניית אתרים", "בנייאת אתרים": "בניית אתרים",
    "אאפליקציה": "אפליקציה", "אפליקאציה": "אפליקציה",
    "סאייבר": "סייבר", "סיבאר": "סייבר",
    "אאבטחת מידע": "אבטחת מידע", "אבטאחת מידע": "אבטחת מידע",
    "ראשת": "רשת", "רשאת": "רשת", "ראשתות": "רשתות",
    "שארת": "שרת", "שרתאים": "שרתים",
    "ענאן": "ענן", "ענאנים": "עננים", "קאלאוד": "קלאוד",
    "גיבאוי": "גיבוי", "גיבואי": "גיבוי",
    "שאחזור": "שחזור", "שחזאור": "שחזור",
    "תאיקון מחשבים": "תיקון מחשבים", "תיקאון מחשבים": "תיקון מחשבים",
    "שאדרוג": "שדרוג", "שדראוג": "שדרוג",
    "האתקנה": "התקנה", "התקנאה": "התקנה",
    "ואירוסים": "וירוסים", "וירוסאים": "וירוסים",
    "אאנטי וירוס": "אנטי וירוס", "אנטי-וירוס": "אנטי וירוס",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔬 הנדסה מורחב - EXTENDED ENGINEERING
    # ═══════════════════════════════════════════════════════════════
    "הנדאסת תוכנה": "הנדסת תוכנה", "הנדסאת תוכנה": "הנדסת תוכנה",
    "הנדאסת חשמל": "הנדסת חשמל", "הנדסאת חשמל": "הנדסת חשמל",
    "הנדאסת מכונות": "הנדסת מכונות", "הנדסאת מכונות": "הנדסת מכונות",
    "הנדאסת תעשייה": "הנדסת תעשייה וניהול", "הנדסאת תעשייה וניהול": "הנדסת תעשייה וניהול",
    "הנדאסה אזרחית": "הנדסה אזרחית", "הנדסאה אזרחית": "הנדסה אזרחית",
    "הנדאסת כימיה": "הנדסת כימיה", "הנדסאת כימיה": "הנדסת כימיה",
    "הנדאסת ביוטכנולוגיה": "הנדסת ביוטכנולוגיה", "הנדסאת ביוטכנולוגיה": "הנדסת ביוטכנולוגיה",
    "הנדאסת מזון": "הנדסת מזון", "הנדסאת מזון": "הנדסת מזון",
    "הנדאסת סביבה": "הנדסת סביבה", "הנדסאת סביבה": "הנדסת סביבה",
    "הנדאסת חומרים": "הנדסת חומרים", "הנדסאת חומרים": "הנדסת חומרים",
    "הנדאסת מים": "הנדסת מים", "הנדסאת מים": "הנדסת מים",
    "הנדאסת קונסטרוקציה": "הנדסת קונסטרוקציה", "קונסטראוקציה": "קונסטרוקציה",
    "הנדאסת אלקטרוניקה": "הנדסת אלקטרוניקה", "אלקטראוניקה": "אלקטרוניקה",
    "הנדאסת תקשורת": "הנדסת תקשורת", "הנדסאת תקשורת": "הנדסת תקשורת",
    "הנדאסת רובוטיקה": "הנדסת רובוטיקה", "רובואטיקה": "רובוטיקה",
    "הנדאסת אווירונאוטיקה": "הנדסת אווירונאוטיקה", "אווירונאאוטיקה": "אווירונאוטיקה",
    "הנדאסת ימית": "הנדסת ימית", "הנדסאת ימית": "הנדסת ימית",
    "טאכנאי": "טכנאי", "טכנאאי": "טכנאי", "טאכנאים": "טכנאים",
    "הנדאסאי": "הנדסאי", "הנדסאאי": "הנדסאי",
    
    # ═══════════════════════════════════════════════════════════════
    # 🤖 מדעי הנתונים ובינה מלאכותית - DATA SCIENCE & AI
    # ═══════════════════════════════════════════════════════════════
    "דאטה סאיינס": "דאטה סיינס", "דאטא סיינס": "דאטה סיינס",
    "מאדען נתונים": "מדען נתונים", "מדעאן נתונים": "מדען נתונים",
    "אאנליסט": "אנליסט", "אנליסאט": "אנליסט", "אאנליזה": "אנליזה",
    "בינאה מלאכותית": "בינה מלאכותית", "בינה מלאכאותית": "בינה מלאכותית",
    "מאשין לרנינג": "מכונה לומדת", "מאכונה לומדת": "מכונה לומדת",
    "דאיפ לרנינג": "דיפ לרנינג", "למידאה עמוקה": "למידה עמוקה",
    "אאלגוריתם": "אלגוריתם", "אלגוריתאם": "אלגוריתם",
    "נאוירון": "נוירון", "נוירואן": "נוירון", "ראשת נוירונים": "רשת נוירונים",
    "ביאג דאטה": "ביג דאטה", "ביג דאאטה": "ביג דאטה",
    "אאוטומציה": "אוטומציה", "אוטומאציה": "אוטומציה",
    "באוט": "בוט", "צ'אטבאוט": "צ'אטבוט", "רואבוט": "רובוט",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏥 סיעוד ובריאות מורחב - EXTENDED NURSING & HEALTH
    # ═══════════════════════════════════════════════════════════════
    "אאחות": "אחות", "אחואת": "אחות", "סאיעוד": "סיעוד",
    "אאח": "אח", "אאחים": "אחים", "מאטפל": "מטפל",
    "סאייעת": "סייעת", "סייעאת": "סייעת", "סאייע": "סייע",
    "מאטפלת": "מטפלת", "מטפלאת": "מטפלת",
    "חאובש": "חובש", "חובאש": "חובש", "פאראמדיק": "פראמדיק",
    "נאטלית": "נטלית", "נטלאית": "נטלית",
    "פארמאצבט": "פרמצבט", "פרמאצבט": "פרמצבט",
    "טאכנאי רנטגן": "טכנאי רנטגן", "טכנאאי רנטגן": "טכנאי רנטגן",
    "טאכנאי מעבדה": "טכנאי מעבדה", "טכנאאי מעבדה": "טכנאי מעבדה",
    "מאיילדת": "מיילדת", "מיילדאת": "מיילדת",
    "הארדמה": "הרדמה", "מארדים": "מרדים", "אאנסתזיולוג": "אנסתזיולוג",
    "כאירורג": "כירורג", "כירוראג": "כירורג", "כאירורגיה": "כירורגיה",
    "רדיאולוג": "רדיולוג", "רדיולאוג": "רדיולוג",
    "פאתולוג": "פתולוג", "פתולאוג": "פתולוג",
    "אאנדוקרינולוג": "אנדוקרינולוג", "אנדוקרינולאוג": "אנדוקרינולוג",
    "ראומטולוג": "ראומטולוג", "ראומטולאוג": "ראומטולוג",
    "גאסטרואנטרולוג": "גסטרואנטרולוג", "גסטרואנטרולאוג": "גסטרואנטרולוג",
    "נאפרולוג": "נפרולוג", "נפרולאוג": "נפרולוג",
    "האמטולוג": "המטולוג", "המטולאוג": "המטולוג",
    "פאולמונולוג": "פולמונולוג", "פולמונולאוג": "פולמונולוג",
    "אאימונולוג": "אימונולוג", "אימונולאוג": "אימונולוג",
    "גאריאטריה": "גריאטריה", "גריאטארייה": "גריאטריה",
    "פאדיאטר": "פדיאטר", "פדיאאטר": "פדיאטר", "ראופא ילדים": "רופא ילדים",
    "נאיאונטולוג": "ניאונטולוג", "ניאונטולאוג": "ניאונטולוג",
    "אאורתודונט": "אורתודונט", "אורתודאונט": "אורתודונט",
    "אאנדודונט": "אנדודונט", "אנדודאונט": "אנדודונט",
    "פאריודונט": "פריודונט", "פריודאונט": "פריודונט",
    "פארוסטטיקה": "פרוסטטיקה", "פרוסטאטיקה": "פרוסטטיקה",
    "האיגייניסטית": "היגייניסטית", "היגייניסאטית": "היגייניסטית",
    
    # ═══════════════════════════════════════════════════════════════
    # 🧠 בריאות הנפש - MENTAL HEALTH
    # ═══════════════════════════════════════════════════════════════
    "פאסיכותרפיה": "פסיכותרפיה", "פסיכותראפיה": "פסיכותרפיה",
    "מאטפל רגשי": "מטפל רגשי", "מטפאל רגשי": "מטפל רגשי",
    "יאועץ": "יועץ", "יועאץ": "יועץ", "יאיעוץ": "ייעוץ",
    "מאאבחן": "מאבחן", "מאבחאן": "מאבחן", "אאיבחון": "אבחון",
    "תאראפיסט": "תרפיסט", "תרפיסאט": "תרפיסט",
    "מאטפל בדרמה": "מטפל בדרמה", "דארמה תרפיה": "דרמה תרפיה",
    "מאטפל באמנות": "מטפל באמנות", "אארט תרפיה": "ארט תרפיה",
    "מאטפל בתנועה": "מטפל בתנועה", "תאנועה תרפיה": "תנועה תרפיה",
    "מאטפל במוזיקה": "מטפל במוזיקה", "מוזיקאה תרפיה": "מוזיקה תרפיה",
    "היפנואזה": "היפנוזה", "היפנואטרפיה": "היפנותרפיה",
    "אאנליטיקאי": "אנליטיקאי", "אנליטיקאאי": "אנליטיקאי",
    "יאונגיאני": "יונגיאני", "יונגיאאני": "יונגיאני",
    "גאשטלט": "גשטלט", "גשטאלט": "גשטלט",
    "קואגניטיבי": "קוגניטיבי", "קוגניטאיבי": "קוגניטיבי",
    "התנהגאותי": "התנהגותי", "התנהגותאי": "התנהגותי",
    "CBT": "טיפול קוגניטיבי התנהגותי", "סיבאיטי": "CBT",
    "DBT": "טיפול דיאלקטי התנהגותי", "דיבאיטי": "DBT",
    "EMDR": "טיפול EMDR", "אימדאר": "EMDR",
    "טאראומה": "טראומה", "טראומאה": "טראומה",
    "חארדה": "חרדה", "חרדאה": "חרדה",
    "דאיכאון": "דיכאון", "דיכאאון": "דיכאון",
    "הפארעה": "הפרעה", "הפרעאה": "הפרעה",
    
    # ═══════════════════════════════════════════════════════════════
    # 👥 עבודה סוציאלית ושירותים חברתיים - SOCIAL WORK
    # ═══════════════════════════════════════════════════════════════
    "עואבד סוציאלי": "עובד סוציאלי", "עובאד סוציאלי": "עובד סוציאלי",
    "עואבדת סוציאלית": "עובדת סוציאלית", "עובדאת סוציאלית": "עובדת סוציאלית",
    "רוואחה": "רווחה", "רווחאה": "רווחה",
    "מאשפחתון": "משפחתון", "משפחאתון": "משפחתון",
    "באית יתומים": "בית יתומים", "ביאת יתומים": "בית יתומים",
    "מאעון": "מעון", "מעואן": "מעון",
    "פאנימייה": "פנימייה", "פנימייאה": "פנימייה",
    "דאייר בית": "דייר בית", "דייאר בית": "דייר בית",
    "נאוער בסיכון": "נוער בסיכון", "נועאר בסיכון": "נוער בסיכון",
    "קאשיש": "קשיש", "קשישאים": "קשישים",
    "מאוגבלות": "מוגבלות", "מוגבלאות": "מוגבלות",
    "שאיקום": "שיקום", "שיקאום": "שיקום",
    "סאיוע": "סיוע", "סיואע": "סיוע",
    "מאתנדב": "מתנדב", "מתנדאב": "מתנדב",
    "עאמותה": "עמותה", "עמותאה": "עמותה",
    "מאלכר": "מלכ\"ר", "מאלכ\"ר": "מלכ\"ר",
    
    # ═══════════════════════════════════════════════════════════════
    # 📚 חינוך מורחב - EXTENDED EDUCATION
    # ═══════════════════════════════════════════════════════════════
    "מאורה לחינוך מיוחד": "מורה לחינוך מיוחד", "חינואך מיוחד": "חינוך מיוחד",
    "סאייעת לחינוך מיוחד": "סייעת לחינוך מיוחד",
    "מאדריך": "מדריך", "מדריאך": "מדריך", "מאדריכה": "מדריכה",
    "מארצה": "מרצה", "מרצאה": "מרצה", "מארצים": "מרצים",
    "פארופסור": "פרופסור", "פרופסאור": "פרופסור",
    "דאוקטור": "דוקטור", "דוקטאור": "דוקטור",
    "חאוקר": "חוקר", "חוקאר": "חוקר", "מאחקר": "מחקר",
    "אאקדמיה": "אקדמיה", "אקדמייאה": "אקדמיה",
    "אאוניברסיטה": "אוניברסיטה", "אוניברסיטאה": "אוניברסיטה",
    "מאכללה": "מכללה", "מכללאה": "מכללה",
    "טאכניון": "טכניון", "טכניאון": "טכניון",
    "סאמינר": "סמינר", "סמינאר": "סמינר",
    "יאשיבה": "ישיבה", "ישיבאה": "ישיבה",
    "אאולפן": "אולפן", "אולפאן": "אולפן",
    "קאורס": "קורס", "קורסאים": "קורסים",
    "סאדנה": "סדנה", "סדנאה": "סדנה",
    "הארצאה": "הרצאה", "הרצאאה": "הרצאה",
    "תאואר": "תואר", "תוארראשון": "תואר ראשון",
    "תאואר שני": "תואר שני", "תאואר שלישי": "תואר שלישי",
    "מאסטר": "מאסטר", "דאוקטורט": "דוקטורט",
    "דאיפלומה": "דיפלומה", "דיפלומאה": "דיפלומה",
    "תאעודה": "תעודה", "תעודאה": "תעודה",
    "הואראה": "הוראה", "הוראאה": "הוראה",
    "פאדגוגיה": "פדגוגיה", "פדגוגייאה": "פדגוגיה",
    "דידאקטיקה": "דידקטיקה", "דידקטיקאה": "דידקטיקה",
    
    # ═══════════════════════════════════════════════════════════════
    # 📊 שיווק ומכירות - MARKETING & SALES
    # ═══════════════════════════════════════════════════════════════
    "שיוואוק": "שיווק", "שאיווק": "שיווק", "מאשווק": "משווק",
    "מאכירות": "מכירות", "מכיראות": "מכירות", "מואכר": "מוכר",
    "נאציג מכירות": "נציג מכירות", "נציאג מכירות": "נציג מכירות",
    "סואכן מכירות": "סוכן מכירות", "סוכאן מכירות": "סוכן מכירות",
    "מאנהל מכירות": "מנהל מכירות", "מנהאל מכירות": "מנהל מכירות",
    "דיאגיטל": "דיגיטל", "דיגיטאל": "דיגיטל",
    "שיוואוק דיגיטלי": "שיווק דיגיטלי", "שיוואוק דיגיטאלי": "שיווק דיגיטלי",
    "סואושיאל מדיה": "סושיאל מדיה", "סושיאאל מדיה": "סושיאל מדיה",
    "קאמפיין": "קמפיין", "קמפייאן": "קמפיין",
    "פארסום": "פרסום", "פרסאום": "פרסום", "פארסומת": "פרסומת",
    "יאחסי ציבור": "יחסי ציבור", "יחסאי ציבור": "יחסי ציבור",
    "דאובר": "דובר", "דוברר": "דובר",
    "מאיתוג": "מיתוג", "מיתאוג": "מיתוג", "באראנד": "בראנד",
    "קאופירייטר": "קופירייטר", "קופיראייטר": "קופירייטר",
    "קאונטנט": "קונטנט", "קונטאנט": "קונטנט", "תואכן": "תוכן",
    "SEO": "קידום אתרים", "אס-אי-או": "SEO",
    "PPC": "פרסום ממומן", "פיפיסי": "PPC",
    "אאנליטיקס": "אנליטיקס", "אנליטיאקס": "אנליטיקס",
    "קאונברסיה": "קונברסיה", "קונברסייאה": "קונברסיה",
    "לאידים": "לידים", "ליאדים": "לידים", "לאיד": "ליד",
    "פאנל": "פאנל", "פאניל": "פאנל",
    "סאקר": "סקר", "סקאר": "סקר", "סאקרים": "סקרים",
    
    # ═══════════════════════════════════════════════════════════════
    # 👔 משאבי אנוש וניהול - HR & MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    "מאשאבי אנוש": "משאבי אנוש", "משאבאי אנוש": "משאבי אנוש",
    "HR": "משאבי אנוש", "אייצ'אר": "HR",
    "גאיוס": "גיוס", "גיואס": "גיוס", "מאגייס": "מגייס",
    "ראיון עבודה": "ראיון עבודה", "ראייאון עבודה": "ראיון עבודה",
    "קאליטה": "קליטה", "קליטאה": "קליטה",
    "האכשרה": "הכשרה", "הכשראה": "הכשרה", "האדרכה": "הדרכה",
    "פאיתוח ארגוני": "פיתוח ארגוני", "פיתואח ארגוני": "פיתוח ארגוני",
    "תארבות ארגונית": "תרבות ארגונית", "תרבאות ארגונית": "תרבות ארגונית",
    "שאכר": "שכר", "שכאר": "שכר", "מאשכורת": "משכורת",
    "תאגמול": "תגמול", "תגמאול": "תגמול",
    "בואנוס": "בונוס", "בונאוס": "בונוס",
    "האערכת עובדים": "הערכת עובדים", "הערכאת עובדים": "הערכת עובדים",
    "פאיטורים": "פיטורים", "פיטאורים": "פיטורים",
    "פאנסיה": "פנסיה", "פנסייאה": "פנסיה",
    "קארן השתלמות": "קרן השתלמות", "קרן השתלמאות": "קרן השתלמות",
    "תאנאי סוציאליים": "תנאים סוציאליים", "תנאאים סוציאליים": "תנאים סוציאליים",
    "חאוזה": "חוזה", "חוזאה": "חוזה", "האסכם": "הסכם",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔬 מדעים מדויקים ומדעי הטבע - EXACT & NATURAL SCIENCES
    # ═══════════════════════════════════════════════════════════════
    "מאתמטיקה": "מתמטיקה", "מתמטיקאה": "מתמטיקה", "מאתמטיקאי": "מתמטיקאי",
    "פאיזיקה": "פיזיקה", "פיזיקאה": "פיזיקה", "פאיזיקאי": "פיזיקאי",
    "כאימיה": "כימיה", "כימייאה": "כימיה", "כאימאי": "כימאי",
    "ביואולוגיה": "ביולוגיה", "ביולוגייאה": "ביולוגיה", "ביואולוג": "ביולוג",
    "גאיאולוגיה": "גיאולוגיה", "גיאולוגייאה": "גיאולוגיה",
    "אאסטרונומיה": "אסטרונומיה", "אסטרונומייאה": "אסטרונומיה",
    "אאסטרופיזיקה": "אסטרופיזיקה", "אסטרופיזיקאה": "אסטרופיזיקה",
    "אאקולוגיה": "אקולוגיה", "אקולוגייאה": "אקולוגיה",
    "בואוטניקה": "בוטניקה", "בוטניקאה": "בוטניקה",
    "זואולוגיה": "זואולוגיה", "זואולוגייאה": "זואולוגיה",
    "מאיקרוביולוגיה": "מיקרוביולוגיה", "מיקרוביולוגייאה": "מיקרוביולוגיה",
    "גאנטיקה": "גנטיקה", "גנטיקאה": "גנטיקה",
    "ביואוכימיה": "ביוכימיה", "ביוכימייאה": "ביוכימיה",
    "ביואוטכנולוגיה": "ביוטכנולוגיה", "ביוטכנולוגייאה": "ביוטכנולוגיה",
    "נאנוטכנולוגיה": "ננוטכנולוגיה", "ננוטכנולוגייאה": "ננוטכנולוגיה",
    "סאטטיסטיקה": "סטטיסטיקה", "סטטיסטיקאה": "סטטיסטיקה",
    "אאקטואריה": "אקטואריה", "אקטואארייה": "אקטואריה",
    "מאעבדה": "מעבדה", "מעבדאה": "מעבדה",
    "מאחקר": "מחקר", "מחקאר": "מחקר",
    "ניסאוי": "ניסוי", "ניסויאים": "ניסויים",
    
    # ═══════════════════════════════════════════════════════════════
    # 🚚 לוגיסטיקה ותובלה - LOGISTICS & TRANSPORTATION
    # ═══════════════════════════════════════════════════════════════
    "לוגיאסטיקה": "לוגיסטיקה", "לוגיסטיקאה": "לוגיסטיקה",
    "שארשרת אספקה": "שרשרת אספקה", "שרשראת אספקה": "שרשרת אספקה",
    "מאחסן": "מחסן", "מחסאן": "מחסן", "מאחסנאות": "מחסנאות",
    "הפאצה": "הפצה", "הפצאה": "הפצה", "מאפיץ": "מפיץ",
    "מאשלוח": "משלוח", "משלאוח": "משלוח", "משלאוחים": "משלוחים",
    "שאליח": "שליח", "שליאח": "שליח", "שאליחים": "שליחים",
    "נאהג": "נהג", "נהאג": "נהג", "נאהגים": "נהגים",
    "נאהג משאית": "נהג משאית", "נהאג משאית": "נהג משאית",
    "נאהג אוטובוס": "נהג אוטובוס", "נהאג אוטובוס": "נהג אוטובוס",
    "נאהג מונית": "נהג מונית", "נהאג מונית": "נהג מונית",
    "מאוניות": "מוניות", "מונייאות": "מוניות",
    "האסעות": "הסעות", "הסעאות": "הסעות",
    "מאעבורת": "מעבורת", "מעבאורת": "מעבורת",
    "אאווירה": "אוויר", "תאעופה": "תעופה", "טאיסה": "טיסה",
    "טאייס": "טייס", "טייאס": "טייס", "דאיילת": "דיילת",
    "נאמל": "נמל", "נמאל": "נמל", "נאמל תעופה": "נמל תעופה",
    "מאכולה": "מכולה", "מכולאות": "מכולות",
    "אאוניה": "אונייה", "אונייאה": "אונייה", "סאפינה": "ספינה",
    "יאבוא": "יבוא", "יבואא": "יבוא", "יאבואן": "יבואן",
    "יאיצוא": "יצוא", "יצואא": "יצוא", "יאצואן": "יצואן",
    "מאכס": "מכס", "מכאס": "מכס",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎭 תיאטרון ובמה - THEATER & STAGE
    # ═══════════════════════════════════════════════════════════════
    "שאחקן": "שחקן", "שחקאן": "שחקן", "שאחקנית": "שחקנית",
    "במאאי": "במאי", "באמאי": "במאי",
    "תאיאטרון": "תיאטרון", "תיאטראון": "תיאטרון",
    "האצגה": "הצגה", "הצגאה": "הצגה", "מאחזה": "מחזה",
    "מאחזמר": "מחזמר", "מחזמאר": "מחזמר",
    "דאראמה": "דרמה", "דרמאה": "דרמה",
    "קואמדיה": "קומדיה", "קומדייאה": "קומדיה",
    "טאראגדיה": "טרגדיה", "טרגדייאה": "טרגדיה",
    "באמה": "במה", "במאה": "במה",
    "תאפאורה": "תפאורה", "תפאוראה": "תפאורה",
    "תאלבושות": "תלבושות", "תלבושאות": "תלבושות",
    "מאאפר": "מאפר", "מאפאר": "מאפר",
    "רואקד": "רוקד", "רוקאד": "רוקד", "ראקדן": "רקדן",
    "מאחול": "מחול", "מחואל": "מחול", "באלט": "בלט",
    "כאוריאוגרף": "כוריאוגרף", "כוריאוגראף": "כוריאוגרף",
    "אאופרה": "אופרה", "אופראה": "אופרה",
    "מאימה": "מימה", "מימאה": "מימה", "פאנטומימה": "פנטומימה",
    "אאימפרוב": "אימפרוב", "אימפרואב": "אימפרוב",
    "סאטנדאפ": "סטנדאפ", "סטנדאאפ": "סטנדאפ",
    "קאברט": "קברט", "קבראט": "קברט",
    
    # ═══════════════════════════════════════════════════════════════
    # 🛡️ ביטחון ואכיפה - SECURITY & LAW ENFORCEMENT
    # ═══════════════════════════════════════════════════════════════
    "שאוטר": "שוטר", "שוטאר": "שוטר", "מאשטרה": "משטרה",
    "קאצין": "קצין", "קציאן": "קצין",
    "באלש": "בלש", "בלאש": "בלש", "חאוקר פרטי": "חוקר פרטי",
    "פאקח": "פקח", "פקאח": "פקח", "פאקחים": "פקחים",
    "שאומר": "שומר", "שומאר": "שומר", "שאמירה": "שמירה",
    "מאבטח": "מבטח", "מבטאח": "מבטח", "מאאבטח": "מאבטח",
    "צאה\"ל": "צה\"ל", "צאבא": "צבא",
    "חאייל": "חייל", "חייאל": "חייל", "חאיילים": "חיילים",
    "קאומנדו": "קומנדו", "קומנדאו": "קומנדו",
    "לואוחם": "לוחם", "לוחאם": "לוחם",
    "טאייס קרבי": "טייס קרבי", "טייאס קרבי": "טייס קרבי",
    "צאלף": "צלף", "צלאף": "צלף",
    "חאבלן": "חבלן", "חבלאן": "חבלן",
    "מאודיעין": "מודיעין", "מודיעאין": "מודיעין",
    "שאבכ": "שב\"כ", "מואסד": "מוסד",
    "כאבאי": "כבאי", "כבאאי": "כבאי", "כאיבוי": "כיבוי",
    "מאציל": "מציל", "מצילאים": "מצילים",
    "אאמבולנס": "אמבולנס", "אמבולאנס": "אמבולנס",
    "מאדא": "מד\"א", "נאטלן": "נטלן",
    
    # ═══════════════════════════════════════════════════════════════
    # ⚖️ משפט מורחב - EXTENDED LAW
    # ═══════════════════════════════════════════════════════════════
    "שואפט": "שופט", "שופאט": "שופט", "שאופטים": "שופטים",
    "עאורכת דין": "עורכת דין", "עורכאת דין": "עורכת דין",
    "פארקליט": "פרקליט", "פרקליאט": "פרקליט",
    "תואבע": "תובע", "תובאע": "תובע",
    "סאניגור": "סניגור", "סניגאור": "סניגור",
    "פארקליטות": "פרקליטות", "פרקליטאות": "פרקליטות",
    "באית משפט": "בית משפט", "ביאת משפט": "בית משפט",
    "באית דין": "בית דין", "ביאת דין": "בית דין",
    "מאושבעים": "מושבעים", "מושבעאים": "מושבעים",
    "עאדות": "עדות", "עדואת": "עדות", "עאד": "עד",
    "תאביעה": "תביעה", "תביעאה": "תביעה",
    "האגנה": "הגנה", "הגנאה": "הגנה",
    "פאסק דין": "פסק דין", "פסאק דין": "פסק דין",
    "עאונש": "עונש", "עונאש": "עונש",
    "קאנס": "קנס", "קנאס": "קנס",
    "מאאסר": "מאסר", "מאסאר": "מאסר",
    "שאחרור": "שחרור", "שחראור": "שחרור",
    "עאירעור": "עירעור", "עירעאור": "עירעור",
    "תאקנון": "תקנון", "תקנאון": "תקנון",
    "חאוק": "חוק", "חוקאים": "חוקים",
    "חאוקה": "חוקה", "חוקאה": "חוקה",
    "רוגאולציה": "רגולציה", "רגולאציה": "רגולציה",
    "ליאטיגציה": "ליטיגציה", "ליטיגאציה": "ליטיגציה",
    "מאדיאציה": "מדיאציה", "מדיאאציה": "מדיאציה",
    "באוררות": "בוררות", "בוראורת": "בוררות",
    "נאוטריון": "נוטריון", "נוטריאון": "נוטריון",
    "פאטנטים": "פטנטים", "פטנטאים": "פטנטים",
    "זאכויות יוצרים": "זכויות יוצרים", "זכויאות יוצרים": "זכויות יוצרים",
    "סאימן מסחרי": "סימן מסחרי", "סימאן מסחרי": "סימן מסחרי",
    
    # ═══════════════════════════════════════════════════════════════
    # ✈️ תיירות ומלונאות - TOURISM & HOSPITALITY
    # ═══════════════════════════════════════════════════════════════
    "תאיירות": "תיירות", "תייראות": "תיירות", "תאייר": "תייר",
    "מאלון": "מלון", "מלאון": "מלון", "מאלונאות": "מלונאות",
    "מאלונאי": "מלונאי", "מלונאאי": "מלונאי",
    "קאבלה": "קבלה", "קבלאה": "קבלה", "רסאפשן": "רסאפשן",
    "פאקידת קבלה": "פקידת קבלה", "פקידאת קבלה": "פקידת קבלה",
    "חאדרן": "חדרן", "חדראן": "חדרן",
    "מאנקה חדרים": "מנקה חדרים", "מנקאה חדרים": "מנקה חדרים",
    "קאונסיירז'": "קונסיירז'", "קונסיאירז'": "קונסיירז'",
    "באלדר": "בלדר", "בלדאר": "בלדר",
    "סואוויס": "סוויטה", "סוויטאה": "סוויטה",
    "חאדר אוכל": "חדר אוכל", "חדאר אוכל": "חדר אוכל",
    "לאובי": "לובי", "לובאי": "לובי",
    "סאפא": "ספא", "ספאא": "ספא",
    "באריכה": "בריכה", "בריכאה": "בריכה",
    "חאוף": "חוף", "חופאים": "חופים",
    "אאתר נופש": "אתר נופש", "אתאר נופש": "אתר נופש",
    "צאימר": "צימר", "צימאר": "צימר", "צאימרים": "צימרים",
    "אאכסניה": "אכסניה", "אכסנייאה": "אכסניה",
    "האוסטל": "הוסטל", "הוסטאל": "הוסטל",
    "מאדריך תיירים": "מדריך תיירים", "מדריאך תיירים": "מדריך תיירים",
    "סואכן נסיעות": "סוכן נסיעות", "סוכאן נסיעות": "סוכן נסיעות",
    "פאספורט": "פספורט", "פספאורט": "פספורט", "דארכון": "דרכון",
    "ואיזה": "ויזה", "ויזאה": "ויזה",
    "טאיול": "טיול", "טיואל": "טיול", "טאיולים": "טיולים",
    "האפלגה": "הפלגה", "הפלגאה": "הפלגה", "קארוז": "קרוז",
    
    # ═══════════════════════════════════════════════════════════════
    # 🍳 בישול ומסעדנות מורחב - EXTENDED CULINARY
    # ═══════════════════════════════════════════════════════════════
    "שאף אישי": "שף אישי", "שאף פרטי": "שף פרטי",
    "שאף סושי": "שף סושי", "שאף קונדיטור": "שף קונדיטור",
    "סואו שף": "סו שף", "סוא שף": "סו שף",
    "מאלצר": "מלצר", "מלצאר": "מלצר", "מאלצרית": "מלצרית",
    "באריסטה": "בריסטה", "בריסטאה": "בריסטה",
    "באר טנדר": "ברמן", "בארמן": "ברמן",
    "סואומלייה": "סומלייה", "סומליאיה": "סומלייה",
    "האשגחה": "השגחה", "השגחאה": "השגחה", "כאשרות": "כשרות",
    "מאשגיח": "משגיח", "משגיאח": "משגיח",
    "באשרי": "בשרי", "חאלבי": "חלבי", "פאארווה": "פרווה",
    "טאבעוני": "טבעוני", "טבעאוני": "טבעוני", "ואיגן": "ויגן",
    "צאמחוני": "צמחוני", "צמחאוני": "צמחוני",
    "גאלוטן פרי": "ללא גלוטן", "לאא גלוטן": "ללא גלוטן",
    "פאסטרי": "פסטרי", "פסטראי": "פסטרי",
    "קאוק": "קוק", "קוקינג": "בישול", "שאפ": "שף",
    "גאורמה": "גורמה", "גורמאה": "גורמה",
    "מאטבח מקצועי": "מטבח מקצועי", "מטבאח מקצועי": "מטבח מקצועי",
    "פאוד סטיילינג": "פוד סטיילינג", "סטייליאנג": "סטיילינג",
    "קאייטרינג לאירועים": "קייטרינג לאירועים",
    "פואוד טראק": "פוד טראק", "פוד טראאק": "פוד טראק",
    "שאוארמה": "שווארמה", "שווארמאה": "שווארמה",
    "פאלאפל": "פלאפל", "פלאפאל": "פלאפל",
    "חאומוס": "חומוס", "חומאוס": "חומוס",
    "שאקשוקה": "שקשוקה", "שקשוקאה": "שקשוקה",
    "סאבייח": "סביח", "סביאח": "סביח",
    
    # ═══════════════════════════════════════════════════════════════
    # 🌾 חקלאות וטבע - AGRICULTURE & NATURE
    # ═══════════════════════════════════════════════════════════════
    "חאקלאות": "חקלאות", "חקלאאות": "חקלאות", "חאקלאי": "חקלאי",
    "מאושב": "מושב", "מושאב": "מושב", "קאיבוץ": "קיבוץ",
    "שאדה": "שדה", "שדאה": "שדה", "שאדות": "שדות",
    "מאטע": "מטע", "מטאע": "מטע", "פארדס": "פרדס",
    "כאירם": "כרם", "כראם": "כרם", "יאקב": "יקב",
    "זאית": "זית", "זייאת": "זית", "זאיתים": "זיתים",
    "תאמרים": "תמרים", "תמארים": "תמרים",
    "אאבוקדו": "אבוקדו", "אבוקאדו": "אבוקדו",
    "הדאר": "הדר", "הדארים": "הדרים",
    "עאגבנייה": "עגבנייה", "עגבנייאה": "עגבנייה",
    "מאלפפון": "מלפפון", "מלפפאון": "מלפפון",
    "חאסה": "חסה", "חסאה": "חסה",
    "גאזר": "גזר", "גזאר": "גזר",
    "תאפוח אדמה": "תפוח אדמה", "תפאוח אדמה": "תפוח אדמה",
    "באצל": "בצל", "בצאל": "בצל",
    "שאום": "שום", "שומאים": "שומים",
    "פאילטרציה": "השקייה", "האשקייה": "השקייה",
    "טאפטוף": "טפטוף", "טפטאוף": "טפטוף",
    "חאממה": "חממה", "חממאה": "חממה", "חאממות": "חממות",
    "האידרופוניקה": "הידרופוניקה", "הידרופוניקאה": "הידרופוניקה",
    "אאורגני": "אורגני", "אורגאני": "אורגני",
    "דאישון": "דישון", "דישאון": "דישון",
    "קאציר": "קציר", "קציאר": "קציר", "קאוצר": "קוצר",
    "טארקטור": "טרקטור", "טרקטאור": "טרקטור",
    "קאומביין": "קומביין", "קומביאין": "קומביין",
    "לאול": "לול", "לולאים": "לולים", "תארנגולות": "תרנגולות",
    "רפאת": "רפת", "רפאת חלב": "רפת חלב",
    "כאבש": "כבש", "כבשאים": "כבשים",
    "עאז": "עז", "עזאים": "עזים",
    "פארה": "פרה", "פראות": "פרות",
    "דאבורים": "דבורים", "דבוראים": "דבורים", "כאוורת": "כוורת",
    
    # ═══════════════════════════════════════════════════════════════
    # ⚽ ספורט וכושר - SPORTS & FITNESS
    # ═══════════════════════════════════════════════════════════════
    "ספאורט": "ספורט", "ספורטאאי": "ספורטאי",
    "מאאמן": "מאמן", "מאמאן": "מאמן", "אאימון": "אימון",
    "מאאמן כושר": "מאמן כושר", "מאמאן כושר": "מאמן כושר",
    "מאאמן אישי": "מאמן אישי", "מאמאן אישי": "מאמן אישי",
    "פאיזיותרפיסט ספורט": "פיזיותרפיסט ספורט",
    "מאטפל בספורט": "מטפל בספורט", "טאיפול ספורט": "טיפול ספורט",
    "כאושר": "כושר", "כושאר": "כושר",
    "חאדר כושר": "חדר כושר", "גאים": "ג'ים",
    "יואוגה": "יוגה", "יוגאה": "יוגה",
    "פאילאטיס": "פילאטיס", "פילאטאיס": "פילאטיס",
    "אאירובי": "אירובי", "אירובאיק": "אירובי",
    "קארוספיט": "קרוספיט", "קרוספאיט": "קרוספיט",
    "שאחייה": "שחייה", "שחייאה": "שחייה", "מאאמן שחייה": "מאמן שחייה",
    "כאדורגל": "כדורגל", "כדורגאל": "כדורגל",
    "כאדורסל": "כדורסל", "כדורסאל": "כדורסל",
    "כאדורעף": "כדורעף", "כדורעאף": "כדורעף",
    "טאניס": "טניס", "טניאס": "טניס",
    "באדמינטון": "בדמינטון", "בדמינטאון": "בדמינטון",
    "אאיגרוף": "איגרוף", "איגראוף": "איגרוף", "באוקס": "בוקס",
    "קאראטה": "קראטה", "קראטאה": "קראטה",
    "ג'אודו": "ג'ודו", "ג'ודאו": "ג'ודו",
    "טאקוונדו": "טאקוונדו", "טקוואנדו": "טאקוונדו",
    "קאראב מגע": "קרב מגע", "קראב מגע": "קרב מגע",
    "אאתלטיקה": "אתלטיקה", "אתלטיקאה": "אתלטיקה",
    "מאראתון": "מרתון", "מרתאון": "מרתון",
    "טאריאתלון": "טריאתלון", "טריאתלאון": "טריאתלון",
    "ראכיבה": "רכיבה", "רכיבאה": "רכיבה", "ראוכב": "רוכב",
    "סאוס": "סוס", "סוסאים": "סוסים", "פאראשות": "פרשות",
    "גאולף": "גולף", "גולאף": "גולף",
    "באולינג": "באולינג", "באוליאנג": "באולינג",
    "סאנוקר": "סנוקר", "סנוקאר": "סנוקר",
    "דאייג": "דייג", "דייאג": "דייג", "דאיג": "דיג",
    "צאלילה": "צלילה", "צלילאה": "צלילה",
    "גאלישה": "גלישה", "גלישאה": "גלישה", "סארף": "סרף",
    "סאקי": "סקי", "סקאי": "סקי",
    "סאנובורד": "סנובורד", "סנובארד": "סנובורד",
    
    # ═══════════════════════════════════════════════════════════════
    # 🕍 דת ורוחניות - RELIGION & SPIRITUALITY
    # ═══════════════════════════════════════════════════════════════
    "רב": "רב", "ראב": "רב", "רבאנות": "רבנות",
    "רבאנית": "רבנית", "רבאניות": "רבנות",
    "חאזן": "חזן", "חזאן": "חזן", "חאזנות": "חזנות",
    "מאוהל": "מוהל", "מוהאל": "מוהל",
    "שואוחט": "שוחט", "שוחאט": "שוחט",
    "סאופר סתם": "סופר סת\"ם", "סופאר סתם": "סופר סת\"ם",
    "גאבאי": "גבאי", "גבאאי": "גבאי",
    "שאמש": "שמש", "שמאש": "שמש",
    "מאשגיח כשרות": "משגיח כשרות", "משגיאח כשרות": "משגיח כשרות",
    "באית כנסת": "בית כנסת", "ביאת כנסת": "בית כנסת",
    "יאשיבה": "ישיבה", "ישיבאה": "ישיבה",
    "כואלל": "כולל", "כולאל": "כולל",
    "באית מדרש": "בית מדרש", "ביאת מדרש": "בית מדרש",
    "תפילאה": "תפילה", "תאפילה": "תפילה",
    "שאחרית": "שחרית", "שחריאת": "שחרית",
    "מאנחה": "מנחה", "מנחאה": "מנחה",
    "עארבית": "ערבית", "ערביאת": "ערבית",
    "שאבת": "שבת", "שבאת": "שבת",
    "חאג": "חג", "חגאים": "חגים",
    "תאפילין": "תפילין", "תפילאין": "תפילין",
    "מאזוזה": "מזוזה", "מזוזאה": "מזוזה",
    "ציאצית": "ציצית", "ציציאת": "ציצית",
    "טאלית": "טלית", "טליאת": "טלית",
    "מאדיטציה": "מדיטציה", "מדיטאציה": "מדיטציה",
    "מאיינדפולנס": "מיינדפולנס", "מינדפולנאס": "מיינדפולנס",
    "רייאיקי": "רייקי", "רייקאי": "רייקי",
    "צ'אאקרות": "צ'אקרות", "צאקרות": "צ'אקרות",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎮 גיימינג ובידור דיגיטלי - GAMING & DIGITAL ENTERTAINMENT
    # ═══════════════════════════════════════════════════════════════
    "גאיימר": "גיימר", "גיימאר": "גיימר", "גאיימינג": "גיימינג",
    "סאטרימר": "סטרימר", "סטרימאר": "סטרימר",
    "יואוטיובר": "יוטיובר", "יוטיובאר": "יוטיובר",
    "אאינפלואנסר": "אינפלואנסר", "אינפלואנסאר": "אינפלואנסר",
    "בלאוגר": "בלוגר", "בלוגאר": "בלוגר",
    "פואדקאסטר": "פודקאסטר", "פודקאסטאר": "פודקאסטר",
    "טאיקטוקר": "טיקטוקר", "טיקטוקאר": "טיקטוקר",
    "אאיספורטס": "איספורטס", "איספורטאס": "איספורטס",
    "מאפתח משחקים": "מפתח משחקים", "מפתאח משחקים": "מפתח משחקים",
    "עאיצוב משחקים": "עיצוב משחקים", "עיצאוב משחקים": "עיצוב משחקים",
    "מאנג'ה": "מנג'ה", "מנגאה": "מנג'ה",
    "אאנימה": "אנימה", "אנימאה": "אנימה",
    "קאוספליי": "קוספליי", "קוספלאיי": "קוספליי",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏦 פיננסים מורחב - EXTENDED FINANCE
    # ═══════════════════════════════════════════════════════════════
    "בנקאאי": "בנקאי", "בנאקאי": "בנקאי", "בנאקאות": "בנקאות",
    "פאיננסים": "פיננסים", "פינאנסים": "פיננסים",
    "האשקעות": "השקעות", "השקעאות": "השקעות", "מאשקיע": "משקיע",
    "תאיק השקעות": "תיק השקעות", "תיאק השקעות": "תיק השקעות",
    "באורסה": "בורסה", "בורסאה": "בורסה",
    "מאניה": "מניה", "מניאות": "מניות",
    "אאגרת חוב": "אגרת חוב", "אגראת חוב": "אגרת חוב",
    "קארן נאמנות": "קרן נאמנות", "קרן נאמאנות": "קרן נאמנות",
    "פאנסיה": "פנסיה", "פנסייאה": "פנסיה",
    "גאמל": "גמל", "גמאל": "גמל", "קאופת גמל": "קופת גמל",
    "ביטואח חיים": "ביטוח חיים", "ביטאוח חיים": "ביטוח חיים",
    "ביטואח בריאות": "ביטוח בריאות", "ביטאוח בריאות": "ביטוח בריאות",
    "ביטואח רכב": "ביטוח רכב", "ביטאוח רכב": "ביטוח רכב",
    "ביטואח דירה": "ביטוח דירה", "ביטאוח דירה": "ביטוח דירה",
    "סואכן ביטוח": "סוכן ביטוח", "סוכאן ביטוח": "סוכן ביטוח",
    "שאמאי": "שמאי", "שמאאי": "שמאי", "שאמאות": "שמאות",
    "אאקטואר": "אקטואר", "אקטואאר": "אקטואר",
    "יאועץ פיננסי": "יועץ פיננסי", "יועאץ פיננסי": "יועץ פיננסי",
    "מאתכנן פיננסי": "מתכנן פיננסי", "מתכנאן פיננסי": "מתכנן פיננסי",
    "קאריפטו": "קריפטו", "קריפטאו": "קריפטו",
    "באיטקוין": "ביטקוין", "ביטקויאן": "ביטקוין",
    "באלוקצ'יין": "בלוקצ'יין", "בלוקצ'ייאן": "בלוקצ'יין",
    "טארייד": "טרייד", "טרייאד": "טרייד", "טאריידר": "טריידר",
    "פאורקס": "פורקס", "פורקאס": "פורקס",
    "CFD": "חוזה הפרשים", "סיאפדי": "CFD",
    
    # ═══════════════════════════════════════════════════════════════
    # 😊 רגשות ומצבי רוח - EMOTIONS & MOODS
    # ═══════════════════════════════════════════════════════════════
    "שאמח": "שמח", "שמאח": "שמח", "שאמחה": "שמחה",
    "עאצוב": "עצוב", "עצאוב": "עצוב", "עאצובה": "עצובה",
    "כאועס": "כועס", "כועאס": "כועס", "כאעסנית": "כעסנית",
    "מאפחד": "מפחד", "מפחאד": "מפחד", "פאחד": "פחד",
    "מאופתע": "מופתע", "מופתאע": "מופתע", "האפתעה": "הפתעה",
    "מאתרגש": "מתרגש", "מתרגאש": "מתרגש", "האתרגשות": "התרגשות",
    "מאאוהב": "מאוהב", "מאוהאב": "מאוהב", "אאהבה": "אהבה",
    "מאתוסכל": "מתוסכל", "מתוסכאל": "מתוסכל", "תאיסכול": "תיסכול",
    "מאודאג": "מודאג", "מודאאג": "מודאג", "דאאגה": "דאגה",
    "לאחוץ": "לחוץ", "לחאוץ": "לחוץ", "לאחץ": "לחץ",
    "רגאוע": "רגוע", "רגועאה": "רגועה", "שאלווה": "שלווה",
    "עאייף": "עייף", "עייאף": "עייף", "עאייפות": "עייפות",
    "מאלא אנרגיה": "מלא אנרגיה", "אאנרגטי": "אנרגטי",
    "נארבז": "נרבז", "נרבאז": "נרבז",
    "מאבואס": "מבואס", "מבואאס": "מבואס",
    "מאאושר": "מאושר", "מאושאר": "מאושר", "אאושר": "אושר",
    "גאאה": "גאה", "גאאאה": "גאה", "גאאווה": "גאווה",
    "נאלהב": "נלהב", "נלהאב": "נלהב", "לאהט": "להט",
    "מאיואש": "מיואש", "מיואאש": "מיואש", "יאאוש": "ייאוש",
    "אאופטימי": "אופטימי", "אופטימאי": "אופטימי",
    "פאסימי": "פסימי", "פסימאי": "פסימי",
    "מאבולבל": "מבולבל", "מבולבאל": "מבולבל", "באילבול": "בילבול",
    "מארוצה": "מרוצה", "מרוצאה": "מרוצה", "שאביעות רצון": "שביעות רצון",
    "מאאכזב": "מאוכזב", "מאוכזאב": "מאוכזב", "אאכזבה": "אכזבה",
    "נאעלב": "נעלב", "נעלאב": "נעלב", "עאלבון": "עלבון",
    "מאקנא": "מקנא", "מקנאא": "מקנא", "קאינאה": "קינאה",
    "מאתגעגע": "מתגעגע", "מתגעגאע": "מתגעגע", "געאגוע": "געגוע",
    "באודד": "בודד", "בודאד": "בודד", "באדידות": "בדידות",
    "סאקרן": "סקרן", "סקראן": "סקרן", "סאקרנות": "סקרנות",
    "מאשועמם": "משועמם", "משועמאם": "משועמם", "שאיעמום": "שיעמום",
    
    # ═══════════════════════════════════════════════════════════════
    # 🍎 מזון ואוכל יומיומי - EVERYDAY FOOD
    # ═══════════════════════════════════════════════════════════════
    "לאחם": "לחם", "לחאם": "לחם", "לאחמניה": "לחמניה",
    "חאלב": "חלב", "חלאב": "חלב",
    "באיצה": "ביצה", "ביצאה": "ביצה", "באיצים": "ביצים",
    "גאבינה": "גבינה", "גבינאה": "גבינה",
    "חאמאה": "חמאה", "חמאאה": "חמאה",
    "יואוגורט": "יוגורט", "יוגוראט": "יוגורט",
    "באשר": "בשר", "בשאר": "בשר",
    "עאוף": "עוף", "עופאות": "עופות",
    "דאג": "דג", "דגאים": "דגים",
    "יארק": "ירק", "ירקאות": "ירקות",
    "פארי": "פרי", "פירואת": "פירות",
    "תאפוח": "תפוח", "תפוחאים": "תפוחים",
    "באננה": "בננה", "בננאות": "בננות",
    "תאפוז": "תפוז", "תפוזאים": "תפוזים",
    "עאנבים": "ענבים", "ענבאים": "ענבים",
    "אאבטיח": "אבטיח", "אבטיאח": "אבטיח",
    "מאלון": "מלון", "מלואנים": "מלונים",
    "אאורז": "אורז", "אורזז": "אורז",
    "פאסטה": "פסטה", "פסטאה": "פסטה",
    "אאטריות": "אטריות", "אטריואת": "אטריות",
    "סאלט": "סלט", "סלאט": "סלט", "סאלטים": "סלטים",
    "מארק": "מרק", "מראק": "מרק", "מארקים": "מרקים",
    "שאניצל": "שניצל", "שניצאל": "שניצל",
    "האמבורגר": "המבורגר", "המבורגאר": "המבורגר",
    "פאיצה": "פיצה", "פיצאה": "פיצה",
    "סאושי": "סושי", "סושאי": "סושי",
    "סאנדוויץ'": "סנדוויץ'", "סנדוויאץ'": "סנדוויץ'",
    "עאוגה": "עוגה", "עוגאה": "עוגה", "עאוגות": "עוגות",
    "עאוגייה": "עוגייה", "עוגייאה": "עוגייה",
    "שאוקולד": "שוקולד", "שוקולאד": "שוקולד",
    "גאלידה": "גלידה", "גלידאה": "גלידה",
    "מאיץ": "מיץ", "מיאץ": "מיץ", "מאיצים": "מיצים",
    "קאפה": "קפה", "קפאה": "קפה",
    "תאה": "תה", "תאהה": "תה",
    "מאים": "מים", "מיאם": "מים",
    "שאתייה": "שתייה", "שתייאה": "שתייה",
    "באירה": "בירה", "בירא": "בירה",
    "יאיין": "יין", "ייאן": "יין",
    "אאלכוהול": "אלכוהול", "אלכוהאול": "אלכוהול",
    "קאמח": "קמח", "קמאח": "קמח",
    "סאוכר": "סוכר", "סוכאר": "סוכר",
    "מאלח": "מלח", "מלאח": "מלח",
    "פאלפל": "פלפל", "פלפאל": "פלפל",
    "שאמן": "שמן", "שמאן": "שמן",
    "חאומץ": "חומץ", "חומאץ": "חומץ",
    "ראוטב": "רוטב", "רוטאב": "רוטב",
    "קאטשופ": "קטשופ", "קטשאופ": "קטשופ",
    "מאיונז": "מיונז", "מיונאז": "מיונז",
    "חארדל": "חרדל", "חרדאל": "חרדל",
    "טאחינה": "טחינה", "טחינאה": "טחינה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🌤️ מזג אוויר וטבע - WEATHER & NATURE
    # ═══════════════════════════════════════════════════════════════
    "מאזג אוויר": "מזג אוויר", "מזאג אוויר": "מזג אוויר",
    "שאמש": "שמש", "שמאש": "שמש", "שאמשי": "שמשי",
    "עאננים": "עננים", "עננאים": "עננים", "מאעונן": "מעונן",
    "גאשם": "גשם", "גשאם": "גשם", "גאשום": "גשום",
    "שאלג": "שלג", "שלאג": "שלג", "מאושלג": "מושלג",
    "באארד": "ברד", "ברדאד": "ברד",
    "סאופה": "סופה", "סופאה": "סופה",
    "ראעם": "רעם", "רעאם": "רעם", "ראעמים": "רעמים",
    "באארק": "ברק", "ברקאים": "ברקים",
    "רואח": "רוח", "רוחאות": "רוחות",
    "שאטפון": "שטפון", "שטפאון": "שטפון",
    "באצורת": "בצורת", "בצוראת": "בצורת",
    "לאחות": "לחות", "לחואת": "לחות",
    "טאמפרטורה": "טמפרטורה", "טמפרטוראה": "טמפרטורה",
    "מאעלות": "מעלות", "מעלאות": "מעלות",
    "קאור": "קור", "קוראר": "קור", "קאר": "קר",
    "חאום": "חום", "חומאם": "חום", "חאם": "חם",
    "נאעים": "נעים", "נעיאם": "נעים",
    "טאל": "טל", "טאלל": "טל",
    "עאירפל": "ערפל", "ערפאל": "ערפל", "עארפילי": "ערפילי",
    "יארח": "ירח", "ירחאי": "ירח",
    "כואכב": "כוכב", "כוכבאים": "כוכבים",
    "שאמיים": "שמיים", "שמייאם": "שמיים",
    "אאופק": "אופק", "אופאק": "אופק",
    "זאריחה": "זריחה", "זריחאה": "זריחה",
    "שאקיעה": "שקיעה", "שקיעאה": "שקיעה",
    "האר": "הר", "הארים": "הרים",
    "גאבעה": "גבעה", "גבעאה": "גבעה",
    "עאמק": "עמק", "עמאק": "עמק",
    "נאהר": "נהר", "נהאר": "נהר", "נאהרות": "נהרות",
    "נאחל": "נחל", "נחאל": "נחל", "נאחלים": "נחלים",
    "מאעיין": "מעיין", "מעייאן": "מעיין",
    "אאגם": "אגם", "אגאם": "אגם",
    "יאם": "ים", "יאמים": "ימים",
    "חאוף הים": "חוף הים", "חואף הים": "חוף הים",
    "מאדבר": "מדבר", "מדבאר": "מדבר",
    "יאער": "יער", "יערואת": "יערות",
    "עאץ": "עץ", "עצאים": "עצים",
    "פארח": "פרח", "פרחאים": "פרחים",
    "דאשא": "דשא", "דשאא": "דשא",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎨 צבעים - COLORS
    # ═══════════════════════════════════════════════════════════════
    "אאדום": "אדום", "אדואם": "אדום",
    "כאתום": "כתום", "כתואם": "כתום",
    "צאהוב": "צהוב", "צהואב": "צהוב",
    "יאורק": "ירוק", "ירואק": "ירוק",
    "כאחול": "כחול", "כחואל": "כחול",
    "סאגול": "סגול", "סגואל": "סגול",
    "וארוד": "ורוד", "ורואד": "ורוד",
    "חאום": "חום", "חומאם": "חום",
    "שאחור": "שחור", "שחואר": "שחור",
    "לאבן": "לבן", "לבאן": "לבן",
    "אאפור": "אפור", "אפואר": "אפור",
    "באז'": "בז'", "באז": "בז'",
    "זאהב": "זהב", "זהאב": "זהב", "זאהוב": "זהוב",
    "כאסף": "כסף", "כסאף": "כסף", "כאסוף": "כסוף",
    "טוראקיז": "טורקיז", "טורקאיז": "טורקיז",
    "באורדו": "בורדו", "בורדאו": "בורדו",
    "נאייבי": "נייבי", "נייבאי": "נייבי",
    "קארם": "קרם", "קראם": "קרם",
    
    # ═══════════════════════════════════════════════════════════════
    # 👪 משפחה ויחסים - FAMILY & RELATIONSHIPS
    # ═══════════════════════════════════════════════════════════════
    "אאבא": "אבא", "אבאא": "אבא",
    "אאימא": "אמא", "אמאא": "אמא",
    "האורים": "הורים", "הוריאם": "הורים",
    "באן": "בן", "בנאים": "בנים",
    "באת": "בת", "בנאות": "בנות",
    "יאלד": "ילד", "ילאד": "ילד", "יאלדים": "ילדים",
    "יאלדה": "ילדה", "ילדאה": "ילדה", "יאלדות": "ילדות",
    "תאינוק": "תינוק", "תינואק": "תינוק", "תאינוקות": "תינוקות",
    "אאח": "אח", "אחאים": "אחים",
    "אאחות": "אחות", "אחואת": "אחות", "אאחיות": "אחיות",
    "סאבא": "סבא", "סבאא": "סבא",
    "סאבתא": "סבתא", "סבתאא": "סבתא",
    "דאוד": "דוד", "דודאים": "דודים",
    "דאודה": "דודה", "דודאות": "דודות",
    "באן דוד": "בן דוד", "באת דודה": "בת דודה",
    "נאכד": "נכד", "נכדאים": "נכדים",
    "נאכדה": "נכדה", "נכדאות": "נכדות",
    "באעל": "בעל", "בעאל": "בעל",
    "אאישה": "אישה", "אישאה": "אישה",
    "באן זוג": "בן זוג", "באת זוג": "בת זוג",
    "חאתן": "חתן", "חתנאים": "חתנים",
    "כאלה": "כלה", "כלאות": "כלות",
    "חאותן": "חותן", "חותאן": "חותן",
    "חאותנת": "חותנת", "חותנאת": "חותנת",
    "גאיס": "גיס", "גיסאים": "גיסים",
    "גאיסה": "גיסה", "גיסאות": "גיסות",
    "חאבר": "חבר", "חברא": "חבר", "חאברים": "חברים",
    "חאברה": "חברה", "חברא": "חברה", "חאברות": "חברות",
    "שאכן": "שכן", "שכנאים": "שכנים",
    "שאכנה": "שכנה", "שכנאות": "שכנות",
    
    # ═══════════════════════════════════════════════════════════════
    # 🦴 גוף אדם - HUMAN BODY
    # ═══════════════════════════════════════════════════════════════
    "ראאש": "ראש", "ראשאים": "ראשים",
    "פאנים": "פנים", "פניאם": "פנים",
    "מאצח": "מצח", "מצאח": "מצח",
    "עאין": "עין", "עיניאם": "עיניים",
    "אאוזן": "אוזן", "אוזנאיים": "אוזניים",
    "אאף": "אף", "אפאים": "אפיים",
    "פאה": "פה", "פייאות": "פיות",
    "שאן": "שן", "שיניאם": "שיניים",
    "לאשון": "לשון", "לשואן": "לשון",
    "סאנטר": "סנטר", "סנטאר": "סנטר",
    "צאוואר": "צוואר", "צווארא": "צוואר",
    "כאתף": "כתף", "כתפאיים": "כתפיים",
    "זארוע": "זרוע", "זרועאות": "זרועות",
    "יאד": "יד", "ידאיים": "ידיים",
    "מארפק": "מרפק", "מרפקאים": "מרפקים",
    "כאף יד": "כף יד", "כפאות ידיים": "כפות ידיים",
    "אאצבע": "אצבע", "אצבעאות": "אצבעות",
    "ציפאורן": "ציפורן", "ציפורניאם": "ציפורניים",
    "גאב": "גב", "גבאות": "גבות",
    "חאזה": "חזה", "חזאה": "חזה",
    "באטן": "בטן", "בטנאות": "בטנות",
    "מאותן": "מותן", "מותנאיים": "מותניים",
    "יארך": "ירך", "ירכאיים": "ירכיים",
    "בארך": "ברך", "ברכאיים": "ברכיים",
    "רארגל": "רגל", "רגליאם": "רגליים",
    "כאף רגל": "כף רגל", "כפאות רגליים": "כפות רגליים",
    "אאגודל": "אגודל", "אגודלאות": "אגודלות",
    "עאקב": "עקב", "עקבאים": "עקבים",
    "לאב": "לב", "לבאבות": "לבבות",
    "מאוח": "מוח", "מוחאות": "מוחות",
    "ראיאה": "ריאה", "ריאאות": "ריאות",
    "כאבד": "כבד", "כבדאים": "כבדים",
    "כאליות": "כליות", "כליאות": "כליות",
    "קאיבה": "קיבה", "קיבאות": "קיבות",
    "עאור": "עור", "עוראות": "עורות",
    "שאריר": "שריר", "שריריאם": "שרירים",
    "עאצם": "עצם", "עצמאות": "עצמות",
    "דאם": "דם", "דמאים": "דמים",
    
    # ═══════════════════════════════════════════════════════════════
    # 🛒 קניות וחנויות - SHOPPING & STORES
    # ═══════════════════════════════════════════════════════════════
    "חאנות": "חנות", "חנויאת": "חנות", "חאנויות": "חנויות",
    "סואופר": "סופר", "סופארמרקט": "סופרמרקט",
    "מאכולת": "מכולת", "מכולאת": "מכולת",
    "שאוק": "שוק", "שווקאים": "שווקים",
    "קאניון": "קניון", "קניונאים": "קניונים",
    "מארכז מסחרי": "מרכז מסחרי", "מרכאז מסחרי": "מרכז מסחרי",
    "קאופה": "קופה", "קופאות": "קופות",
    "קאופאי": "קופאי", "קופאאית": "קופאית",
    "עאגלת קניות": "עגלת קניות", "עגלאת קניות": "עגלת קניות",
    "סאל": "סל", "סלאים": "סלים",
    "שאקית": "שקית", "שקיאת": "שקית", "שאקיות": "שקיות",
    "חאשבונית": "חשבונית", "חשבוניאת": "חשבונית",
    "קאבלה": "קבלה", "קבלאה": "קבלה",
    "מאזומן": "מזומן", "מזומאן": "מזומן",
    "כארטיס אשראי": "כרטיס אשראי", "כרטיאס אשראי": "כרטיס אשראי",
    "תאשלום": "תשלום", "תשלאום": "תשלום", "תאשלומים": "תשלומים",
    "מאבצע": "מבצע", "מבצאע": "מבצע", "מאבצעים": "מבצעים",
    "האנחה": "הנחה", "הנחאה": "הנחה", "האנחות": "הנחות",
    "קאופון": "קופון", "קופונאים": "קופונים",
    "האחזרה": "החזרה", "החזראה": "החזרה",
    "החאלפה": "החלפה", "החלפאה": "החלפה",
    "מאידה": "מידה", "מידאה": "מידה", "מאידות": "מידות",
    "מאלאי": "מלאי", "מלאאי": "מלאי",
    "הזמאנה": "הזמנה", "הזמנאה": "הזמנה",
    "מאשלוח": "משלוח", "משלאוח": "משלוח",
    "חאינם": "חינם", "חינאם": "חינם",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏃 פעולות יומיומיות - DAILY ACTIONS
    # ═══════════════════════════════════════════════════════════════
    "לאקום": "לקום", "קאם": "קם", "קאמה": "קמה",
    "לאשון": "לישון", "יאשן": "ישן", "יאשנה": "ישנה",
    "לאאכול": "לאכול", "אאוכל": "אוכל", "אאוכלת": "אוכלת",
    "לאשתות": "לשתות", "שאותה": "שותה", "שאותים": "שותים",
    "לאהתלבש": "להתלבש", "מאתלבש": "מתלבש",
    "לאהתרחץ": "להתרחץ", "מאתרחץ": "מתרחץ",
    "לאהצחצח שיניים": "להצחצח שיניים",
    "לאהסתרק": "להסתרק", "מאסתרק": "מסתרק",
    "לאעבוד": "לעבוד", "עאובד": "עובד", "עאובדת": "עובדת",
    "לאלמוד": "ללמוד", "לאומד": "לומד", "לאומדת": "לומדת",
    "לאנוח": "לנוח", "נאח": "נח", "נאחה": "נחה",
    "לאהליך": "ללכת", "האולך": "הולך", "האולכת": "הולכת",
    "לארוץ": "לרוץ", "ראץ": "רץ", "ראצה": "רצה",
    "לאנסוע": "לנסוע", "נאוסע": "נוסע", "נאוסעת": "נוסעת",
    "לאטוס": "לטוס", "טאס": "טס", "טאסה": "טסה",
    "לאחזור": "לחזור", "חאוזר": "חוזר", "חאוזרת": "חוזרת",
    "לאהגיע": "להגיע", "מאגיע": "מגיע", "מאגיעה": "מגיעה",
    "לאצאת": "לצאת", "יאוצא": "יוצא", "יאוצאת": "יוצאת",
    "לאהיכנס": "להיכנס", "נאכנס": "נכנס", "נאכנסת": "נכנסת",
    "לאפתוח": "לפתוח", "פאותח": "פותח",
    "לאסגור": "לסגור", "סאוגר": "סוגר",
    "לאהדליק": "להדליק", "מאדליק": "מדליק",
    "לאכבות": "לכבות", "מאכבה": "מכבה",
    "לאנקות": "לנקות", "מאנקה": "מנקה",
    "לאכבס": "לכבס", "מאכבס": "מכבס",
    "לאבשל": "לבשל", "מאבשל": "מבשל",
    "לאאפות": "לאפות", "אאופה": "אופה",
    "לאקנות": "לקנות", "קאונה": "קונה",
    "לאמכור": "למכור", "מאוכר": "מוכר",
    "לאשלם": "לשלם", "מאשלם": "משלם",
    "לאחפש": "לחפש", "מאחפש": "מחפש",
    "לאמצוא": "למצוא", "מאוצא": "מוצא",
    "לאאבד": "לאבד", "מאאבד": "מאבד",
    "לאשכוח": "לשכוח", "שאוכח": "שוכח",
    "לאזכור": "לזכור", "זאוכר": "זוכר",
    "לאחשוב": "לחשוב", "חאושב": "חושב",
    "לאהבין": "להבין", "מאבין": "מבין",
    "לאדעת": "לדעת", "יאודע": "יודע",
    "לאהאמין": "להאמין", "מאאמין": "מאמין",
    "לארצות": "לרצות", "רואצה": "רוצה",
    "לאאהוב": "לאהוב", "אאוהב": "אוהב",
    "לאשנוא": "לשנוא", "שאונא": "שונא",
    "לאפחד": "לפחד", "מאפחד": "מפחד",
    "לאשמוח": "לשמוח", "שאמח": "שמח",
    "לאבכות": "לבכות", "באוכה": "בוכה",
    "לאצחוק": "לצחוק", "צאוחק": "צוחק",
    "לאחייך": "לחייך", "מאחייך": "מחייך",
    
    # ═══════════════════════════════════════════════════════════════
    # 💬 סלנג ישראלי - ISRAELI SLANG
    # ═══════════════════════════════════════════════════════════════
    "יאאללה": "יאללה", "יאלא": "יאללה",
    "סאבבה": "סבבה", "סבאבה": "סבבה",
    "אאחלה": "אחלה", "אחלאה": "אחלה",
    "וואאלה": "וואלה", "וואלאה": "וואלה",
    "באאסה": "באסה", "באסאה": "באסה",
    "חאראה": "חארה", "חארא": "חארה",
    "חאבל על הזמן": "חבל על הזמן", "חבאל על הזמן": "חבל על הזמן",
    "לאעוף על זה": "לעוף על זה", "עאף על זה": "עף על זה",
    "מאגניב": "מגניב", "מגניאב": "מגניב",
    "מאטורף": "מטורף", "מטוראף": "מטורף",
    "מאשוגע": "משוגע", "משוגאע": "משוגע",
    "עאנק": "ענק", "ענאק": "ענק",
    "אאש": "אש", "אאאש": "אש",
    "סאותם": "סותם", "סותאם": "סותם",
    "סאותם פה": "סותם פה", "סותאם פה": "סותם פה",
    "לאך": "לך", "לאך מפה": "לך מפה",
    "דאפוק": "דפוק", "דפואק": "דפוק",
    "מאכוער": "מכוער", "מכואער": "מכוער",
    "חאמוד": "חמוד", "חמואד": "חמוד",
    "מאתוק": "מתוק", "מתואק": "מתוק",
    "נאהנה": "נהנה", "נהנאה": "נהנה",
    "מאחפיר": "מחפיר", "מחפיאר": "מחפיר",
    "ביאזיון": "ביזיון", "ביזיאון": "ביזיון",
    "כאיף": "כיף", "כייאף": "כיף", "כאייפי": "כייפי",
    "מאעפן": "מעפן", "מעפאן": "מעפן",
    "לאחפור": "לחפור", "חאופר": "חופר",
    "פאראייר": "פראייר", "פרייאר": "פראייר",
    "שואוב": "שווב", "שובאב": "שווב",
    "מאסריח": "מסריח", "מסריאח": "מסריח",
    "לאהשתולל": "להשתולל", "מאשתולל": "משתולל",
    "לאהתפרע": "להתפרע", "מאתפרע": "מתפרע",
    "פאצצה": "פצצה", "פצצאה": "פצצה",
    "מאדהים": "מדהים", "מדהיאם": "מדהים",
    "נאורא": "נורא", "נוראא": "נורא",
    "מאמש": "ממש", "ממאש": "ממש",
    "רצאינו": "רצינו", "רציאנו": "רצינו",
    "באמת": "באמת", "באאמת": "באמת",
    "כאילו": "כאילו", "כאאילו": "כאילו",
    "פאשוט": "פשוט", "פשואט": "פשוט",
    "בטאח": "בטח", "בטחא": "בטח",
    "ואודאי": "ודאי", "ודאאי": "ודאי",
    "כאנראה": "כנראה", "כנראאה": "כנראה",
    "אאולי": "אולי", "אולאי": "אולי",
    "באטוח": "בטוח", "בטואח": "בטוח",
    
    # ═══════════════════════════════════════════════════════════════
    # 🕐 זמן ותאריכים מורחב - EXTENDED TIME & DATES
    # ═══════════════════════════════════════════════════════════════
    "עאכשיו": "עכשיו", "עכשיאו": "עכשיו",
    "הייאום": "היום", "היואם": "היום",
    "מאחר": "מחר", "מחאר": "מחר",
    "מאחרתיים": "מחרתיים", "מחרתייאם": "מחרתיים",
    "אאתמול": "אתמול", "אתמאול": "אתמול",
    "שאלשום": "שלשום", "שלשואם": "שלשום",
    "האשבוע": "השבוע", "השבואע": "השבוע",
    "שאבוע הבא": "שבוע הבא", "שבואע הבא": "שבוע הבא",
    "שאבוע שעבר": "שבוע שעבר", "שבואע שעבר": "שבוע שעבר",
    "האחודש": "החודש", "החודאש": "החודש",
    "חאודש הבא": "חודש הבא", "חודאש הבא": "חודש הבא",
    "השאנה": "השנה", "השנאה": "השנה",
    "שאנה הבאה": "שנה הבאה", "שנאה הבאה": "שנה הבאה",
    "באוקר": "בוקר", "בוקאר": "בוקר",
    "צאהריים": "צהריים", "צהרייאם": "צהריים",
    "אאחר הצהריים": "אחר הצהריים", "אחאר הצהריים": "אחר הצהריים",
    "עארב": "ערב", "ערבאים": "ערבים",
    "לאילה": "לילה", "לילאה": "לילה",
    "חאצי": "חצי", "חציאי": "חצי",
    "ראבע": "רבע", "רבאע": "רבע",
    "שאלוש רבעי": "שלושה רבעים", "שלושאה רבעים": "שלושה רבעים",
    "דאקה": "דקה", "דקאות": "דקות",
    "שאנייה": "שנייה", "שניאות": "שניות",
    "רוגאע": "רגע", "רגעאים": "רגעים",
    "שאעה": "שעה", "שעאות": "שעות",
    "יאנואר": "ינואר", "ינואאר": "ינואר",
    "פאברואר": "פברואר", "פברואאר": "פברואר",
    "מארס": "מרץ", "מראץ": "מרץ",
    "אאפריל": "אפריל", "אפריאל": "אפריל",
    "מאאי": "מאי", "מאאי": "מאי",
    "יאוני": "יוני", "יוניא": "יוני",
    "יאולי": "יולי", "יוליא": "יולי",
    "אאוגוסט": "אוגוסט", "אוגוסאט": "אוגוסט",
    "סאפטמבר": "ספטמבר", "ספטמבאר": "ספטמבר",
    "אאוקטובר": "אוקטובר", "אוקטובאר": "אוקטובר",
    "נאובמבר": "נובמבר", "נובמבאר": "נובמבר",
    "דאצמבר": "דצמבר", "דצמבאר": "דצמבר",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎓 לימודים וחינוך יומיומי - EVERYDAY EDUCATION
    # ═══════════════════════════════════════════════════════════════
    "שאיעורי בית": "שיעורי בית", "שיעוראי בית": "שיעורי בית",
    "מאבחן": "מבחן", "מבחאן": "מבחן", "מאבחנים": "מבחנים",
    "באחינה": "בחינה", "בחינאה": "בחינה",
    "ציאון": "ציון", "ציונאים": "ציונים",
    "תאעודה": "תעודה", "תעודאה": "תעודה",
    "סאפר": "ספר", "ספראים": "ספרים",
    "מאחברת": "מחברת", "מחברואת": "מחברות",
    "עאט": "עט", "עטאים": "עטים",
    "עאיפרון": "עיפרון", "עיפרונאות": "עיפרונות",
    "מאחק": "מחק", "מחקאים": "מחקים",
    "מאחדד": "מחדד", "מחדדאים": "מחדדים",
    "סארגל": "סרגל", "סרגלאים": "סרגלים",
    "תאיק": "תיק", "תיקאים": "תיקים",
    "כאיתה": "כיתה", "כיתאות": "כיתות",
    "לאוח": "לוח", "לוחאות": "לוחות",
    "האפסקה": "הפסקה", "הפסקאות": "הפסקות",
    "צאלצול": "צלצול", "צלצולאים": "צלצולים",
    "חאופש": "חופש", "חופשאות": "חופשות",
    "חאופש גדול": "חופש גדול", "חופאש גדול": "חופש גדול",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏡 חפצים יומיומיים - EVERYDAY OBJECTS
    # ═══════════════════════════════════════════════════════════════
    "מאפתחות": "מפתחות", "מפתחאות": "מפתחות",
    "אארנק": "ארנק", "ארנקאים": "ארנקים",
    "תאיק": "תיק", "תיקאים": "תיקים",
    "טאלפון": "טלפון", "טלפואן": "טלפון",
    "מאחשב": "מחשב", "מחשאב": "מחשב",
    "טאבלט": "טאבלט", "טבלאט": "טאבלט",
    "שאעון": "שעון", "שעונאים": "שעונים",
    "מאשקפיים": "משקפיים", "משקפייאם": "משקפיים",
    "מאטרייה": "מטרייה", "מטריאות": "מטריות",
    "כאובע": "כובע", "כובעאים": "כובעים",
    "מאעיל": "מעיל", "מעילאים": "מעילים",
    "נאעליים": "נעליים", "נעלייאם": "נעליים",
    "גארביים": "גרביים", "גרבייאם": "גרביים",
    "חאולצה": "חולצה", "חולצאות": "חולצות",
    "מאכנסיים": "מכנסיים", "מכנסייאם": "מכנסיים",
    "שאמלה": "שמלה", "שמלאות": "שמלות",
    "חאגורה": "חגורה", "חגוראות": "חגורות",
    "סאפל": "ספל", "ספלאים": "ספלים",
    "צאלחת": "צלחת", "צלחואת": "צלחות",
    "כאף": "כף", "כפאות": "כפות",
    "מאזלג": "מזלג", "מזלגאות": "מזלגות",
    "סאכין": "סכין", "סכינאים": "סכינים",
    "כואס": "כוס", "כוסאות": "כוסות",
    "באקבוק": "בקבוק", "בקבוקאים": "בקבוקים",
    "מאגבת": "מגבת", "מגבואת": "מגבות",
    "סאבון": "סבון", "סבונאים": "סבונים",
    "מאברשת שיניים": "מברשת שיניים", "מברשאת שיניים": "מברשת שיניים",
    "מאשחת שיניים": "משחת שיניים", "משחאת שיניים": "משחת שיניים",
    "שאמפו": "שמפו", "שמפואו": "שמפו",
    "מאראה": "מראה", "מראאות": "מראות",
    "כארית": "כרית", "כריתאות": "כריות",
    "שאמיכה": "שמיכה", "שמיכאות": "שמיכות",
    "סאדין": "סדין", "סדינאים": "סדינים",
    "מאזרן": "מזרן", "מזרנאים": "מזרנים",
    
    # ═══════════════════════════════════════════════════════════════
    # 📱 פגישות ותורים - APPOINTMENTS
    # ═══════════════════════════════════════════════════════════════
    "פאגישה": "פגישה", "פגישא": "פגישה", "פאגישא": "פגישה",
    "פגאישה": "פגישה", "פגישאה": "פגישה",
    "טורר": "תור", "תאור": "תור", "טאור": "תור",
    "תוארים": "תורים", "טאורים": "תורים",
    "לקבאוע": "לקבוע", "לאקבוע": "לקבוע",
    "זמאן פנוי": "זמן פנוי", "זאמן פנוי": "זמן פנוי",
    "זאמינות": "זמינות", "זמיאנות": "זמינות",
    "פאנוי": "פנוי", "פנואי": "פנוי",
    "תאפוס": "תפוס", "תפאוס": "תפוס",
    "מאועד": "מועד", "מועאד": "מועד",
    "הזמאנה": "הזמנה", "האזמנה": "הזמנה",
    "ביטאול": "ביטול", "באיטול": "ביטול",
    "שינאוי": "שינוי", "שאינוי": "שינוי",
    "דאחייה": "דחייה", "דחייא": "דחייה",
    "אישאור": "אישור", "אאישור": "אישור",
    "תאזכורת": "תזכורת", "תזכארת": "תזכורת",
    
    # ═══════════════════════════════════════════════════════════════
    # 👤 שמות נפוצים - COMMON NAMES
    # ═══════════════════════════════════════════════════════════════
    "משא": "משה", "מאושה": "משה", "מושא": "משה",
    "יאוסי": "יוסי", "יוסאי": "יוסי", "יואסי": "יוסי",
    "יאוסף": "יוסף", "יוסאף": "יוסף", "יואסף": "יוסף",
    "דאני": "דני", "דניי": "דני", "דאניי": "דני",
    "דאניאל": "דניאל", "דניאאל": "דניאל", "דאניעל": "דניאל",
    "מיכאאל": "מיכאל", "מיכעל": "מיכאל", "מיקעל": "מיכאל",
    "אאלי": "אלי", "אליי": "אלי", "עלי": "אלי",
    "שאי": "שי", "שאיי": "שי",
    "אאבי": "אבי", "אביי": "אבי",
    "איתאי": "איתי", "אאיתי": "איתי",
    "יואב": "יואב", "יוואב": "יואב",
    "ראון": "רון", "רואן": "רון",
    "גאיל": "גיל", "גילל": "גיל",
    "עאומר": "עומר", "עומאר": "עומר",
    "נאועם": "נועם", "נועאם": "נועם",
    "יונאתן": "יונתן", "יואנתן": "יונתן",
    "אאריאל": "אריאל", "אריעל": "אריאל",
    "שארה": "שרה", "שארא": "שרה",
    "רחאל": "רחל", "רחאל": "רחל",
    "מיראי": "מירי", "מיריי": "מירי",
    "דאנה": "דנה", "דנאה": "דנה",
    "יאעל": "יעל", "יעאל": "יעל",
    "נואעה": "נועה", "נאועה": "נועה",
    "שיארה": "שירה", "שירא": "שירה",
    "לאיאל": "ליאל", "ליעל": "ליאל",
    "מאיה": "מאיה", "מאייה": "מאיה",
    "תמאר": "תמר", "תאמר": "תמר",
    "אדאם": "אדם", "אאדם": "אדם",
    "רואי": "רועי", "רועאי": "רועי",
    "עאידו": "עידו", "עידאו": "עידו",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏠 בית ומגורים - HOME & LIVING
    # ═══════════════════════════════════════════════════════════════
    "דיארה": "דירה", "דיראה": "דירה",
    "באית": "בית", "ביית": "בית",
    "חאדר": "חדר", "חדאר": "חדר",
    "מאטבח": "מטבח", "מטבאח": "מטבח",
    "סאלון": "סלון", "סלאון": "סלון",
    "שירותאים": "שירותים", "שאירותים": "שירותים",
    "אמבאטיה": "אמבטיה", "אאמבטיה": "אמבטיה",
    "מארפסת": "מרפסת", "מרפאסת": "מרפסת",
    "גאג": "גג", "גאאג": "גג",
    "חאניה": "חניה", "חנייא": "חניה",
    "מאחסן": "מחסן", "מחסאן": "מחסן",
    "גינאה": "גינה", "גינאא": "גינה",
    "חאצר": "חצר", "חצאר": "חצר",
    "שאער": "שער", "שעאר": "שער",
    "גאדר": "גדר", "גדאר": "גדר",
    "קאומה": "קומה", "קומאה": "קומה",
    "מעאלית": "מעלית", "מאעלית": "מעלית",
    "מאדרגות": "מדרגות", "מדרגאות": "מדרגות",
    "כאניסה": "כניסה", "כניסאה": "כניסה",
    "דאלת": "דלת", "דלאת": "דלת",
    "חלאון": "חלון", "חאלון": "חלון",
    "קאיר": "קיר", "קירר": "קיר",
    "ראיצפה": "ריצפה", "ריצפאה": "ריצפה",
    "תאקרה": "תקרה", "תקראה": "תקרה",
    
    # ═══════════════════════════════════════════════════════════════
    # 💼 עסקים וכלכלה - BUSINESS
    # ═══════════════════════════════════════════════════════════════
    "עאסק": "עסק", "עסאק": "עסק",
    "חאברה": "חברה", "חברא": "חברה",
    "לאקוח": "לקוח", "לקאוח": "לקוח",
    "מאכירה": "מכירה", "מכיראה": "מכירה",
    "קניאה": "קנייה", "קנייא": "קנייה",
    "מאחיר": "מחיר", "מחיאר": "מחיר",
    "הנאחה": "הנחה", "הנחא": "הנחה",
    "חאשבון": "חשבון", "חשבאון": "חשבון",
    "תשלאום": "תשלום", "תאשלום": "תשלום",
    "מזומאן": "מזומן", "מאזומן": "מזומן",
    "אאשראי": "אשראי", "אשראאי": "אשראי",
    "עאובדים": "עובדים", "עובאדים": "עובדים",
    "מאנהל": "מנהל", "מנאהל": "מנהל",
    "באעלים": "בעלים", "בעאלים": "בעלים",
    "שאותף": "שותף", "שותאף": "שותף",
    "משארד": "משרד", "מאשרד": "משרד",
    "חאנות": "חנות", "חנאות": "חנות",
    "מסחאר": "מסחר", "מאסחר": "מסחר",
    "יבאוא": "יבוא", "יאבוא": "יבוא",
    "יאצוא": "יצוא", "יצאוא": "יצוא",
    
    # ═══════════════════════════════════════════════════════════════
    # 📞 תקשורת - COMMUNICATION
    # ═══════════════════════════════════════════════════════════════
    "טאלפון": "טלפון", "טלפאון": "טלפון",
    "נאייד": "נייד", "ניייד": "נייד",
    "פאלאפון": "פלאפון", "פלאפאון": "פלאפון",
    "סאלולרי": "סלולרי", "סלאולרי": "סלולרי",
    "הואדעה": "הודעה", "הודאעה": "הודעה",
    "מאסרון": "מסרון", "מסראון": "מסרון",
    "ואטסאפ": "וואטסאפ", "ווטסאפ": "וואטסאפ", "ווטסאאפ": "וואטסאפ",
    "אאימייל": "אימייל", "אימאייל": "אימייל",
    "מייאל": "מייל", "מאייל": "מייל",
    "פאקס": "פקס", "פקאס": "פקס",
    "שיאחה": "שיחה", "שאיחה": "שיחה",
    "קאו": "קו", "קאוו": "קו",
    "מאספר": "מספר", "מספאר": "מספר",
    "חייאג": "חייג", "חאייג": "חייג",
    "האתקשר": "התקשר", "התקאשר": "התקשר",
    
    # ═══════════════════════════════════════════════════════════════
    # 🚗 תחבורה - TRANSPORTATION
    # ═══════════════════════════════════════════════════════════════
    "רכאב": "רכב", "ראכב": "רכב",
    "אאוטו": "אוטו", "אוטאו": "אוטו",
    "מאכונית": "מכונית", "מכונאית": "מכונית",
    "אאוטובוס": "אוטובוס", "אוטאובוס": "אוטובוס",
    "ראכבת": "רכבת", "רכבאת": "רכבת",
    "מאונית": "מונית", "מונאית": "מונית",
    "טאקסי": "טקסי", "טקאסי": "טקסי",
    "אאופנוע": "אופנוע", "אופנאוע": "אופנוע",
    "אאופניים": "אופניים", "אופנאיים": "אופניים",
    "נאסיעה": "נסיעה", "נסיעא": "נסיעה",
    "נאהיגה": "נהיגה", "נהיגא": "נהיגה",
    "חאנייה": "חנייה", "חניייא": "חנייה",
    "כאביש": "כביש", "כבאיש": "כביש",
    "רחאוב": "רחוב", "ראחוב": "רחוב",
    "כאתובת": "כתובת", "כתואבת": "כתובת",
    "תאחנה": "תחנה", "תחנאה": "תחנה",
    "דאלק": "דלק", "דלאק": "דלק",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎯 פעולות נפוצות - COMMON ACTIONS
    # ═══════════════════════════════════════════════════════════════
    "לאהגיד": "להגיד", "להגאיד": "להגיד",
    "לאדבר": "לדבר", "לדבאר": "לדבר",
    "לאשמוע": "לשמוע", "לשמאוע": "לשמוע",
    "לאראות": "לראות", "לראאות": "לראות",
    "לאעזור": "לעזור", "לעזאור": "לעזור",
    "לאקנות": "לקנות", "לקנאות": "לקנות",
    "לאמכור": "למכור", "למכאור": "למכור",
    "לאשלם": "לשלם", "לשלאם": "לשלם",
    "לאחכות": "לחכות", "לחכאות": "לחכות",
    "לאהזמין": "להזמין", "להזמאין": "להזמין",
    "לאבטל": "לבטל", "לבטאל": "לבטל",
    "לאשנות": "לשנות", "לשנאות": "לשנות",
    "לאהסביר": "להסביר", "להסבאיר": "להסביר",
    "לאהבין": "להבין", "להבאין": "להבין",
    "לאחפש": "לחפש", "לחפאש": "לחפש",
    "לאמצוא": "למצוא", "למצאוא": "למצוא",
    "לאתת": "לתת", "לתאת": "לתת",
    "לאקבל": "לקבל", "לקבאל": "לקבל",
    "לאשלוח": "לשלוח", "לשלאוח": "לשלוח",
    "לאהביא": "להביא", "להבאיא": "להביא",
    "לאקחת": "לקחת", "לקחאת": "לקחת",
    "לאבדוק": "לבדוק", "לבדאוק": "לבדוק",
    "לאתאם": "לתאם", "לתאאם": "לתאם",
    "לאקבוע": "לקבוע", "לקבאוע": "לקבוע",
    
    # ═══════════════════════════════════════════════════════════════
    # 📦 מוצרים נפוצים - COMMON PRODUCTS
    # ═══════════════════════════════════════════════════════════════
    "מאחשב": "מחשב", "מחשאב": "מחשב",
    "לאפטופ": "לפטופ", "לפטאופ": "לפטופ",
    "טאבלט": "טאבלט", "טבאלט": "טאבלט",
    "סמאארטפון": "סמארטפון", "סמרטפון": "סמארטפון",
    "טלויאזיה": "טלוויזיה", "טאלוויזיה": "טלוויזיה",
    "מאקרר": "מקרר", "מקארר": "מקרר",
    "מאכונת כביסה": "מכונת כביסה",
    "מאייבש": "מייבש", "מיאבש": "מייבש",
    "מאדיח": "מדיח", "מדאיח": "מדיח",
    "תאנור": "תנור", "תנאור": "תנור",
    "מאיקרוגל": "מיקרוגל", "מיקראוגל": "מיקרוגל",
    "שאואב": "שואב", "שואאב": "שואב",
    "מאזגן": "מזגן", "מזאגן": "מזגן",
    
    # ═══════════════════════════════════════════════════════════════
    # ⚽ ספורט ופעילות גופנית - SPORTS & FITNESS
    # ═══════════════════════════════════════════════════════════════
    "כאדורגל": "כדורגל", "כדורגאל": "כדורגל",
    "כאדורסל": "כדורסל", "כדורסאל": "כדורסל",
    "כאדורעף": "כדורעף", "כדורעאף": "כדורעף",
    "טאניס": "טניס", "טנאיס": "טניס",
    "שאחייה": "שחייה", "שחייאה": "שחייה",
    "ראיצה": "ריצה", "ריצאה": "ריצה",
    "הליאכה": "הליכה", "האליכה": "הליכה",
    "אאימון": "אימון", "אימאון": "אימון", "אאימונים": "אימונים",
    "חאדר כושר": "חדר כושר", "חדאר כושר": "חדר כושר",
    "מאאמן": "מאמן", "מאמאן": "מאמן",
    "שאחקן": "שחקן", "שחקאן": "שחקן", "שאחקנים": "שחקנים",
    "קאבוצה": "קבוצה", "קבוצאה": "קבוצה",
    "מאשחק": "משחק", "משחאק": "משחק", "מאשחקים": "משחקים",
    "תאחרות": "תחרות", "תחראות": "תחרות",
    "אאליפות": "אליפות", "אליפאות": "אליפות",
    "גאמר": "גמר", "גמאר": "גמר",
    "חאצי גמר": "חצי גמר", "חציא גמר": "חצי גמר",
    "נאיצחון": "ניצחון", "ניצחאון": "ניצחון",
    "האפסד": "הפסד", "הפסאד": "הפסד",
    "תאיקו": "תיקו", "תיקאו": "תיקו",
    "שאער": "שער", "שעאר": "שער", "שאערים": "שערים",
    "נאקודה": "נקודה", "נקודאה": "נקודה",
    "יאוגה": "יוגה", "יוגאה": "יוגה",
    "פאילאטיס": "פילאטיס", "פילאטאיס": "פילאטיס",
    "אאירובי": "אירובי", "אירובאי": "אירובי",
    "הארמת משקולות": "הרמת משקולות", "הרמאת משקולות": "הרמת משקולות",
    "מאשקולות": "משקולות", "משקולאות": "משקולות",
    "האליכון": "הליכון", "הליכאון": "הליכון",
    "אאופני כושר": "אופני כושר", "אופנאי כושר": "אופני כושר",
    "קארדיו": "קרדיו", "קרדיאו": "קרדיו",
    "מאתיחות": "מתיחות", "מתיחאות": "מתיחות",
    "חאימום": "חימום", "חימאום": "חימום",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏥 בריאות ורפואה יומיומית - EVERYDAY HEALTH
    # ═══════════════════════════════════════════════════════════════
    "ראופא": "רופא", "רופאא": "רופא", "ראופאים": "רופאים",
    "ראופאה": "רופאה", "רופאאה": "רופאה",
    "מארפאה": "מרפאה", "מרפאאה": "מרפאה",
    "באית חולים": "בית חולים", "ביאת חולים": "בית חולים",
    "קאופת חולים": "קופת חולים", "קופאת חולים": "קופת חולים",
    "באיטוח בריאות": "ביטוח בריאות", "ביטאוח בריאות": "ביטוח בריאות",
    "כאאב": "כאב", "כאאב ראש": "כאב ראש",
    "כאאב בטן": "כאב בטן", "כאאב גרון": "כאב גרון",
    "חאום": "חום", "חומאא": "חום",
    "שאיעול": "שיעול", "שיעאול": "שיעול",
    "האצטננות": "הצטננות", "הצטננאות": "הצטננות",
    "שאפעת": "שפעת", "שפעאת": "שפעת",
    "אאלרגיה": "אלרגיה", "אלרגיאה": "אלרגיה",
    "תארופה": "תרופה", "תרופאה": "תרופה", "תארופות": "תרופות",
    "כאדור": "כדור", "כדואר": "כדור", "כאדורים": "כדורים",
    "מארשם": "מרשם", "מרשאם": "מרשם",
    "באית מרקחת": "בית מרקחת", "ביאת מרקחת": "בית מרקחת",
    "חאיסון": "חיסון", "חיסאון": "חיסון",
    "באדיקה": "בדיקה", "בדיקאה": "בדיקה", "באדיקות": "בדיקות",
    "באדיקת דם": "בדיקת דם", "בדיקאת דם": "בדיקת דם",
    "צאילום": "צילום", "צילאום": "צילום",
    "אאולטרסאונד": "אולטרסאונד", "אולטראסאונד": "אולטרסאונד",
    "נאיתוח": "ניתוח", "ניתאוח": "ניתוח",
    "הארדמה": "הרדמה", "הרדמאה": "הרדמה",
    "האחלמה": "החלמה", "החלמאה": "החלמה",
    "שאיקום": "שיקום", "שיקאום": "שיקום",
    "פאיזיותרפיה": "פיזיותרפיה", "פיזיאותרפיה": "פיזיותרפיה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎵 מוזיקה ואמנות - MUSIC & ART
    # ═══════════════════════════════════════════════════════════════
    "מאוזיקה": "מוזיקה", "מוזיקאה": "מוזיקה",
    "שאיר": "שיר", "שיאר": "שיר", "שאירים": "שירים",
    "זאמר": "זמר", "זמאר": "זמר", "זאמרים": "זמרים",
    "זאמרת": "זמרת", "זמראת": "זמרת",
    "נאגן": "נגן", "נגאן": "נגן", "נאגנים": "נגנים",
    "גאיטרה": "גיטרה", "גיטאראה": "גיטרה",
    "פאסנתר": "פסנתר", "פסנתאר": "פסנתר",
    "כאינור": "כינור", "כינואר": "כינור",
    "תאופים": "תופים", "תופאים": "תופים",
    "פאלוט": "פלוט", "פלואט": "פלוט",
    "מאהקה": "להקה", "להקאה": "להקה",
    "קאונצרט": "קונצרט", "קונצאירט": "קונצרט",
    "האופעה": "הופעה", "הופעאה": "הופעה",
    "באמה": "במה", "במאה": "במה",
    "צאייר": "צייר", "ציאייר": "צייר",
    "ציאור": "ציור", "ציאור": "ציור",
    "פאיסול": "פיסול", "פיסאול": "פיסול",
    "תאיאטרון": "תיאטרון", "תיאטראון": "תיאטרון",
    "שאחקן": "שחקן", "שחקאן": "שחקן",
    "שאחקנית": "שחקנית", "שחקנאית": "שחקנית",
    "בימאאי": "במאי", "בימאי": "במאי",
    "סארט": "סרט", "סראט": "סרט", "סארטים": "סרטים",
    "קאולנוע": "קולנוע", "קולנאוע": "קולנוע",
    "סאדרה": "סדרה", "סדראה": "סדרה",
    "תאוכנית": "תוכנית", "תוכניאת": "תוכנית",
    "ריאקוד": "ריקוד", "ריקאוד": "ריקוד",
    "מאחול": "מחול", "מחאול": "מחול",
    "באלט": "בלט", "בלאט": "בלט",
    
    # ═══════════════════════════════════════════════════════════════
    # 📚 ביטויים ושאלות נפוצות - COMMON PHRASES & QUESTIONS
    # ═══════════════════════════════════════════════════════════════
    "מאה זה": "מה זה", "מאה זאה": "מה זה",
    "מאה קורה": "מה קורה", "מאה קאורה": "מה קורה",
    "מאה נשמע": "מה נשמע", "מאה נאשמע": "מה נשמע",
    "אאיך אתה": "איך אתה", "איאך אתה": "איך אתה",
    "אאיפה זה": "איפה זה", "איפאה זה": "איפה זה",
    "מאתי זה": "מתי זה", "מאתי זאה": "מתי זה",
    "למאה": "למה", "לאמה": "למה",
    "כאמה עולה": "כמה עולה", "כמאה עולה": "כמה עולה",
    "כאמה זמן": "כמה זמן", "כמאה זמן": "כמה זמן",
    "מאי אמר": "מי אמר", "מאי אמאר": "מי אמר",
    "מאה אתה רוצה": "מה אתה רוצה", "מאה את רוצה": "מה את רוצה",
    "אאני רוצה": "אני רוצה", "אנאי רוצה": "אני רוצה",
    "אאני צריך": "אני צריך", "אנאי צריך": "אני צריך",
    "אאפשר לדבר": "אפשר לדבר", "אאפשר לאדבר": "אפשר לדבר",
    "סאליחה": "סליחה", "סליאחה": "סליחה",
    "באבקשה": "בבקשה", "בבקאשה": "בבקשה",
    "תאודה רבה": "תודה רבה", "תודאה רבה": "תודה רבה",
    "באסדר": "בסדר", "בסאדר": "בסדר",
    "האיום": "היום", "היאום": "היום",
    "מאחר": "מחר", "מחאר": "מחר",
    "אאתמול": "אתמול", "אתמאול": "אתמול",
    "עאכשיו": "עכשיו", "עכשאיו": "עכשיו",
    "באקרוב": "בקרוב", "בקראוב": "בקרוב",
    "מאאוחר": "מאוחר", "מאוחאר": "מאוחר",
    "מאוקדם": "מוקדם", "מוקאדם": "מוקדם",
    "תאמיד": "תמיד", "תמיאד": "תמיד",
    "לאפעמים": "לפעמים", "לפעמאים": "לפעמים",
    "אאף פעם": "אף פעם", "אף פאעם": "אף פעם",
    "כאל כך": "כל כך", "כאל כאך": "כל כך",
    "קאצת": "קצת", "קצאת": "קצת",
    "הארבה": "הרבה", "הרבאה": "הרבה",
    "מאספיק": "מספיק", "מספאיק": "מספיק",
    "יאותר מדי": "יותר מדי", "יותאר מדי": "יותר מדי",
    "פאחות": "פחות", "פחאות": "פחות",
    
    # ═══════════════════════════════════════════════════════════════
    # 🐾 חיות ובעלי חיים - ANIMALS
    # ═══════════════════════════════════════════════════════════════
    "כאלב": "כלב", "כלאב": "כלב", "כאלבים": "כלבים",
    "חאתול": "חתול", "חתאול": "חתול", "חאתולים": "חתולים",
    "ציפאור": "ציפור", "ציפוראים": "ציפורים",
    "דאג": "דג", "דגאים": "דגים",
    "פארה": "פרה", "פראות": "פרות",
    "סאוס": "סוס", "סוסאים": "סוסים",
    "חאמור": "חמור", "חמוראים": "חמורים",
    "כאבש": "כבש", "כבשאים": "כבשים",
    "עאז": "עז", "עזאים": "עזים",
    "תארנגול": "תרנגול", "תרנגולאים": "תרנגולים",
    "באט": "בט", "עטלאף": "עטלף",
    "נאחש": "נחש", "נחשאים": "נחשים",
    "צאב": "צב", "צבאים": "צבים",
    "אאריה": "אריה", "אריאות": "אריות",
    "פאיל": "פיל", "פילאים": "פילים",
    "גאמל": "גמל", "גמלאים": "גמלים",
    "זאברה": "זברה", "זבראות": "זברות",
    "קאוף": "קוף", "קופאים": "קופים",
    "דאוב": "דוב", "דובאים": "דובים",
    "זאאב": "זאב", "זאבאים": "זאבים",
    "שאועל": "שועל", "שועלאים": "שועלים",
    "אאילים": "אילים", "צאבי": "צבי", "צבאיים": "צביים",
    "דאולפין": "דולפין", "דולפינאים": "דולפינים",
    "לאויתן": "לוויתן", "לווייתאן": "לוויתן",
    "כאריש": "כריש", "כרישאים": "כרישים",
    "פארפר": "פרפר", "פרפראים": "פרפרים",
    "דאבורה": "דבורה", "דבוראות": "דבורות",
    "נאמלה": "נמלה", "נמלאות": "נמלות",
    
    # ═══════════════════════════════════════════════════════════════
    # 💻 טכנולוגיה ואינטרנט - TECHNOLOGY & INTERNET
    # ═══════════════════════════════════════════════════════════════
    "אאינטרנט": "אינטרנט", "אינטרנאט": "אינטרנט",
    "ואיי פיי": "וויי פיי", "וייא פיי": "וויי פיי",
    "אאתר": "אתר", "אתאר": "אתר", "אאתרים": "אתרים",
    "עאמוד": "עמוד", "עמאוד": "עמוד",
    "לאינק": "לינק", "לינאק": "לינק", "קאישור": "קישור",
    "להאוריד": "להוריד", "להורייד": "להוריד",
    "להאעלות": "להעלות", "להעלאות": "להעלות",
    "לאהתחבר": "להתחבר", "להתחאבר": "להתחבר",
    "לאהתנתק": "להתנתק", "להתנאתק": "להתנתק",
    "סאיסמה": "סיסמה", "סיסמאה": "סיסמה",
    "שאם משתמש": "שם משתמש", "שאם משתאמש": "שם משתמש",
    "לאהיכנס": "להיכנס", "להיכאנס": "להיכנס",
    "לאהירשם": "להירשם", "להירשאם": "להירשם",
    "אאפליקציה": "אפליקציה", "אפליקציאה": "אפליקציה",
    "תאוכנה": "תוכנה", "תוכנאה": "תוכנה",
    "עאדכון": "עדכון", "עדכאון": "עדכון",
    "להאתקין": "להתקין", "להתקאין": "להתקין",
    "לאמחוק": "למחוק", "למחאוק": "למחוק",
    "קאובץ": "קובץ", "קובאץ": "קובץ", "קאבצים": "קבצים",
    "תאיקייה": "תיקייה", "תיקייאה": "תיקייה",
    "גאיבוי": "גיבוי", "גיבאוי": "גיבוי",
    "שאיתוף": "שיתוף", "שיתאוף": "שיתוף",
    "לאשלוח": "לשלוח", "לשלאוח": "לשלוח",
    "לאקבל": "לקבל", "לקבאל": "לקבל",
    "האתראה": "התראה", "התראאה": "התראה",
    "הואדעה": "הודעה", "הודעאה": "הודעה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔢 מספרים והכמויות - NUMBERS & QUANTITIES
    # ═══════════════════════════════════════════════════════════════
    "אאחת": "אחת", "אחאת": "אחת",
    "שאתיים": "שתיים", "שתייאם": "שתיים",
    "שאלוש": "שלוש", "שלאוש": "שלוש",
    "אארבע": "ארבע", "ארבאע": "ארבע",
    "חאמש": "חמש", "חמאש": "חמש",
    "שאש": "שש", "ששאש": "שש",
    "שאבע": "שבע", "שבאע": "שבע",
    "שאמונה": "שמונה", "שמונאה": "שמונה",
    "תאשע": "תשע", "תשאע": "תשע",
    "עאשר": "עשר", "עשאר": "עשר",
    "עאשרים": "עשרים", "עשריאם": "עשרים",
    "שאלושים": "שלושים", "שלושאים": "שלושים",
    "אארבעים": "ארבעים", "ארבעיאם": "ארבעים",
    "חאמישים": "חמישים", "חמישאים": "חמישים",
    "שאישים": "שישים", "שישאים": "שישים",
    "שאיבעים": "שבעים", "שבעיאם": "שבעים",
    "שאמונים": "שמונים", "שמונאים": "שמונים",
    "תאישעים": "תשעים", "תשעאים": "תשעים",
    "מאאה": "מאה", "מאאאה": "מאה",
    "מאאתיים": "מאתיים", "מאתייאם": "מאתיים",
    "אאלף": "אלף", "אלאף": "אלף",
    "ראאשון": "ראשון", "ראשאון": "ראשון",
    "שאני": "שני", "שנאי": "שני",
    "שאלישי": "שלישי", "שלישאי": "שלישי",
    "ראביעי": "רביעי", "רביעאי": "רביעי",
    "חאמישי": "חמישי", "חמישאי": "חמישי",
    "שאישי": "שישי", "שישאי": "שישי",
    "שאביעי": "שביעי", "שביעאי": "שביעי",
    
    # ═══════════════════════════════════════════════════════════════
    # 📰 חברה ופוליטיקה - SOCIETY & POLITICS
    # ═══════════════════════════════════════════════════════════════
    "מאדינה": "מדינה", "מדינאה": "מדינה",
    "מאמשלה": "ממשלה", "ממשלאה": "ממשלה",
    "ראאש ממשלה": "ראש ממשלה", "ראאש מאמשלה": "ראש ממשלה",
    "שאר": "שר", "שראים": "שרים",
    "כאנסת": "כנסת", "כנאסת": "כנסת",
    "חאבר כנסת": "חבר כנסת", "חאבר כאנסת": "חבר כנסת",
    "באחירות": "בחירות", "בחיראות": "בחירות",
    "להאצביע": "להצביע", "להצביאע": "להצביע",
    "מאפלגה": "מפלגה", "מפלגאה": "מפלגה",
    "חאוק": "חוק", "חוקאים": "חוקים",
    "זאכויות": "זכויות", "זכויאות": "זכויות",
    "חאובה": "חובה", "חובאות": "חובות",
    "מאס": "מס", "מסאים": "מסים",
    "ביטואח לאומי": "ביטוח לאומי", "ביטאוח לאומי": "ביטוח לאומי",
    "שאירות": "שירות", "שירואת": "שירות",
    "צאבא": "צבא", "צבאאא": "צבא",
    "שואטר": "שוטר", "שוטראים": "שוטרים",
    "משאטרה": "משטרה", "משטראה": "משטרה",
    "באית משפט": "בית משפט", "ביאת משפט": "בית משפט",
    "עאורך דין": "עורך דין", "עוראך דין": "עורך דין",
    "שאופט": "שופט", "שופאט": "שופט",
    "עאיתון": "עיתון", "עיתאון": "עיתון",
    "חאדשות": "חדשות", "חדשאות": "חדשות",
    "תאקשורת": "תקשורת", "תקשוראת": "תקשורת",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎉 חגים ואירועים - HOLIDAYS & EVENTS
    # ═══════════════════════════════════════════════════════════════
    "חאג": "חג", "חגאים": "חגים",
    "ראאש השנה": "ראש השנה", "ראאש האשנה": "ראש השנה",
    "יאום כיפור": "יום כיפור", "יאום כיפאור": "יום כיפור",
    "סאוכות": "סוכות", "סוכאות": "סוכות",
    "סאוכה": "סוכה", "סוכאה": "סוכה",
    "חאנוכה": "חנוכה", "חנוכאה": "חנוכה",
    "חאנוכייה": "חנוכייה", "חנוכייאה": "חנוכייה",
    "פאורים": "פורים", "פוריאם": "פורים",
    "פאסח": "פסח", "פסאח": "פסח",
    "מאצות": "מצות", "מצאות": "מצות",
    "שאבועות": "שבועות", "שבועאות": "שבועות",
    "יאום העצמאות": "יום העצמאות", "יאום האעצמאות": "יום העצמאות",
    "יאום הזיכרון": "יום הזיכרון", "יאום האזיכרון": "יום הזיכרון",
    "יאום הולדת": "יום הולדת", "יאום האולדת": "יום הולדת",
    "מאסיבה": "מסיבה", "מסיבאה": "מסיבה",
    "חאגיגה": "חגיגה", "חגיגאה": "חגיגה",
    "חאתונה": "חתונה", "חתונאה": "חתונה",
    "באר מצווה": "בר מצווה", "באר מצוואה": "בר מצווה",
    "באת מצווה": "בת מצווה", "באת מצוואה": "בת מצווה",
    "באריתה": "בריתה", "ברית מאילה": "ברית מילה",
    "הלאווייה": "הלוויה", "הלוויאה": "הלוויה",
    "שאבעה": "שבעה", "שבעאה": "שבעה",
    "מאתנה": "מתנה", "מתנאה": "מתנה", "מאתנות": "מתנות",
    "זאר פרחים": "זר פרחים", "זאר פארחים": "זר פרחים",
    "באלונים": "בלונים", "בלונאים": "בלונים",
    "עאוגת יום הולדת": "עוגת יום הולדת",
    "נארות": "נרות", "נרואת": "נרות",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏢 מקומות ציבוריים - PUBLIC PLACES
    # ═══════════════════════════════════════════════════════════════
    "באנק": "בנק", "בנקאים": "בנקים",
    "דאואר": "דואר", "דואאר": "דואר",
    "סאופרמרקט": "סופרמרקט", "סופראמרקט": "סופרמרקט",
    "מאכולת": "מכולת", "מכולאת": "מכולת",
    "קאניון": "קניון", "קניונאים": "קניונים",
    "באית קפה": "בית קפה", "ביאת קפה": "בית קפה",
    "מאסעדה": "מסעדה", "מסעדאה": "מסעדה",
    "באר": "בר", "בראים": "ברים",
    "מאועדון": "מועדון", "מועדאון": "מועדון",
    "באית ספר": "בית ספר", "ביאת ספר": "בית ספר",
    "גאן ילדים": "גן ילדים", "גאן יאלדים": "גן ילדים",
    "אאוניברסיטה": "אוניברסיטה", "אוניברסיטאה": "אוניברסיטה",
    "מאכללה": "מכללה", "מכללאה": "מכללה",
    "ספאריה": "ספרייה", "ספריאה": "ספרייה",
    "מאוזיאון": "מוזיאון", "מוזיאאון": "מוזיאון",
    "תאיאטרון": "תיאטרון", "תיאטראון": "תיאטרון",
    "קאולנוע": "קולנוע", "קולנאוע": "קולנוע",
    "באריכה": "בריכה", "בריכאה": "בריכה",
    "גאימנסיה": "גימנסיה", "גימנסיאה": "גימנסיה",
    "פאארק": "פארק", "פארקאים": "פארקים",
    "גאן ציבורי": "גן ציבורי", "גאן ציבאורי": "גן ציבורי",
    "מאגרש משחקים": "מגרש משחקים", "מגראש משחקים": "מגרש משחקים",
    "תאחנת דלק": "תחנת דלק", "תחנאת דלק": "תחנת דלק",
    "תאחנת אוטובוס": "תחנת אוטובוס", "תחנאת אוטובוס": "תחנת אוטובוס",
    "תאחנת רכבת": "תחנת רכבת", "תחנאת רכבת": "תחנת רכבת",
    "נאמל תעופה": "נמל תעופה", "נמאל תעופה": "נמל תעופה",
    "שאדה תעופה": "שדה תעופה", "שדאה תעופה": "שדה תעופה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🤝 יחסים חברתיים - SOCIAL INTERACTIONS
    # ═══════════════════════════════════════════════════════════════
    "שאלום": "שלום", "שלאום": "שלום",
    "להאתראות": "להתראות", "להתראאות": "להתראות",
    "מאה שלומך": "מה שלומך", "מאה שלאומך": "מה שלומך",
    "נאעים מאוד": "נעים מאוד", "נעיאם מאוד": "נעים מאוד",
    "לאהכיר": "להכיר", "להכאיר": "להכיר",
    "להאפגש": "להיפגש", "להיפגאש": "להיפגש",
    "לאהזמין": "להזמין", "להזמאין": "להזמין",
    "לאבקר": "לבקר", "לבקאר": "לבקר",
    "לאארח": "לארח", "לאראח": "לארח",
    "אאורח": "אורח", "אורחאים": "אורחים",
    "מאארח": "מארח", "מארחאים": "מארחים",
    "פאגישה": "פגישה", "פגישאה": "פגישה",
    "באילוי": "בילוי", "בילאוי": "בילוי",
    "לאבלות": "לבלות", "לבלאות": "לבלות",
    "לאצאת": "לצאת", "לצאאת": "לצאת",
    "לאהיכנס": "להיכנס", "להיכנאס": "להיכנס",
    "לאבוא": "לבוא", "לבואא": "לבוא",
    "לאהגיע": "להגיע", "להגיאע": "להגיע",
    "לאעזוב": "לעזוב", "לעזאוב": "לעזוב",
    "לאחזור": "לחזור", "לחזאור": "לחזור",
    "לאהישאר": "להישאר", "להישאאר": "להישאר",
    
    # ═══════════════════════════════════════════════════════════════
    # 💭 תיאורים ותארים - DESCRIPTIONS & ADJECTIVES
    # ═══════════════════════════════════════════════════════════════
    "גאדול": "גדול", "גדאול": "גדול",
    "קאטן": "קטן", "קטאן": "קטן",
    "יאפה": "יפה", "יפאה": "יפה",
    "מאכוער": "מכוער", "מכואער": "מכוער",
    "טאוב": "טוב", "טובא": "טוב",
    "ראע": "רע", "רעאא": "רע",
    "חאזק": "חזק", "חזאק": "חזק",
    "חאלש": "חלש", "חלאש": "חלש",
    "מאהיר": "מהיר", "מהיאר": "מהיר",
    "אאיטי": "איטי", "איטאי": "איטי",
    "קאשה": "קשה", "קשאה": "קשה",
    "קאל": "קל", "קאלל": "קל",
    "חאדש": "חדש", "חדאש": "חדש",
    "יאשן": "ישן", "ישאן": "ישן",
    "צאעיר": "צעיר", "צעיאר": "צעיר",
    "מאבוגר": "מבוגר", "מבוגאר": "מבוגר",
    "גאבוה": "גבוה", "גבוהאה": "גבוה",
    "נאמוך": "נמוך", "נמאוך": "נמוך",
    "עאשיר": "עשיר", "עשיאר": "עשיר",
    "עאני": "עני", "ענאי": "עני",
    "חאכם": "חכם", "חכאם": "חכם",
    "טאיפש": "טיפש", "טיפאש": "טיפש",
    "נאחמד": "נחמד", "נחמאד": "נחמד",
    "מארגיז": "מרגיז", "מרגיאז": "מרגיז",
    "מאעניין": "מעניין", "מענייאן": "מעניין",
    "מאשעמם": "משעמם", "משעמאם": "משעמם",
    "מאסוכן": "מסוכן", "מסוכאן": "מסוכן",
    "באטוח": "בטוח", "בטואח": "בטוח",
    "מאבהיל": "מבהיל", "מבהיאל": "מבהיל",
    "מארגיע": "מרגיע", "מרגיאע": "מרגיע",
    
    # ═══════════════════════════════════════════════════════════════
    # 🧹 עבודות בית וניקיון - HOUSEWORK & CLEANING
    # ═══════════════════════════════════════════════════════════════
    "לאנקות": "לנקות", "לנקאות": "לנקות",
    "לאכבס": "לכבס", "לכבאס": "לכבס",
    "לאגהץ": "לגהץ", "לגהאץ": "לגהץ",
    "לאקפל": "לקפל", "לקפאל": "לקפל",
    "לאשטוף כלים": "לשטוף כלים", "לשטאוף כלים": "לשטוף כלים",
    "לאשאוב": "לשאוב", "לשאואב": "לשאוב",
    "לאספוג": "לספוג", "לספאוג": "לספוג",
    "לאסדר": "לסדר", "לסדאר": "לסדר",
    "לאארגן": "לארגן", "לארגאן": "לארגן",
    "לאנגב": "לנגב", "לנגאב": "לנגב",
    "לאהציע מיטה": "להציע מיטה", "להציאע מיטה": "להציע מיטה",
    "לאהוציא זבל": "להוציא זבל", "להוציאא זבל": "להוציא זבל",
    "לאקנות מצרכים": "לקנות מצרכים", "לקנאות מצרכים": "לקנות מצרכים",
    "מאגב": "מגב", "מגאב": "מגב",
    "סאחבה": "סחבה", "סחבאה": "סחבה",
    "סאמרטוט": "סמרטוט", "סמרטואט": "סמרטוט",
    "דאלי": "דלי", "דליא": "דלי",
    "מאטאטא": "מטאטא", "מטאטאא": "מטאטא",
    "שאואב אבק": "שואב אבק", "שואאב אבק": "שואב אבק",
    "חאומרי ניקוי": "חומרי ניקוי", "חומראי ניקוי": "חומרי ניקוי",
    "אאבקה": "אבקה", "אבקאה": "אבקה",
    "מארכך כביסה": "מרכך כביסה", "מרככא כביסה": "מרכך כביסה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🚿 היגיינה אישית - PERSONAL HYGIENE
    # ═══════════════════════════════════════════════════════════════
    "להאתרחץ": "להתרחץ", "להתרחאץ": "להתרחץ",
    "להאתקלח": "להתקלח", "להתקלאח": "להתקלח",
    "לאהצחצח": "להצחצח", "להצחצאח": "להצחצח",
    "לאהסתרק": "להסתרק", "להסתראק": "להסתרק",
    "לאהתגלח": "להתגלח", "להתגלאח": "להתגלח",
    "מאברשת": "מברשת", "מברשאת": "מברשת",
    "מאסרק": "מסרק", "מסראק": "מסרק",
    "סאכין גילוח": "סכין גילוח", "סכיאן גילוח": "סכין גילוח",
    "תאער": "תער", "תעאר": "תער",
    "מאגלח": "מגלח", "מגלאח": "מגלח",
    "דאאודורנט": "דיאודורנט", "דיאודורנאט": "דיאודורנט",
    "באושם": "בושם", "בושאם": "בושם",
    "קארם לחות": "קרם לחות", "קראם לחות": "קרם לחות",
    "סאבון": "סבון", "סבואן": "סבון",
    "ג'אל רחצה": "ג'ל רחצה", "ג'אל רחאצה": "ג'ל רחצה",
    "מארכך": "מרכך", "מרכאך": "מרכך",
    "מאסיכה": "מסיכה", "מסיכאה": "מסיכה",
    "מאייבש שיער": "מייבש שיער", "מייבאש שיער": "מייבש שיער",
    "מאחליק שיער": "מחליק שיער", "מחליאק שיער": "מחליק שיער",
    
    # ═══════════════════════════════════════════════════════════════
    # 👶 ילדים ותינוקות - CHILDREN & BABIES
    # ═══════════════════════════════════════════════════════════════
    "תאינוק": "תינוק", "תינואק": "תינוק",
    "תאינוקת": "תינוקת", "תינוקאת": "תינוקת",
    "פאעוט": "פעוט", "פעואט": "פעוט",
    "יאלד": "ילד", "ילאד": "ילד",
    "יאלדה": "ילדה", "ילדאה": "ילדה",
    "חאיתול": "חיתול", "חיתאול": "חיתול", "חאיתולים": "חיתולים",
    "מאוצץ": "מוצץ", "מוצאץ": "מוצץ",
    "באקבוק": "בקבוק", "בקבואק": "בקבוק",
    "עאגלה": "עגלה", "עגלאה": "עגלה",
    "כאיסא בטיחות": "כיסא בטיחות", "כיסאא בטיחות": "כיסא בטיחות",
    "מאיטה לתינוק": "מיטה לתינוק", "מיטאה לתינוק": "מיטה לתינוק",
    "לאהאכיל": "להאכיל", "להאכיאל": "להאכיל",
    "לאהחליף חיתול": "להחליף חיתול", "להחליאף חיתול": "להחליף חיתול",
    "לאהרדים": "להרדים", "להרדיאם": "להרדים",
    "לאהעיר": "להעיר", "להעיאר": "להעיר",
    "גאן ילדים": "גן ילדים", "גאן יאלדים": "גן ילדים",
    "גאננת": "גננת", "גננאת": "גננת",
    "מאטפלת": "מטפלת", "מטפלאת": "מטפלת",
    "באייביסיטר": "בייביסיטר", "בייביסיטאר": "בייביסיטר",
    "מאשחק": "משחק", "משחאק": "משחק",
    "צאעצוע": "צעצוע", "צעצואע": "צעצוע",
    "באובה": "בובה", "בובאה": "בובה",
    "כאדור": "כדור", "כדואר": "כדור",
    
    # ═══════════════════════════════════════════════════════════════
    # 🍴 ארוחות ואכילה - MEALS & EATING
    # ═══════════════════════════════════════════════════════════════
    "אארוחת בוקר": "ארוחת בוקר", "ארוחאת בוקר": "ארוחת בוקר",
    "אארוחת צהריים": "ארוחת צהריים", "ארוחאת צהריים": "ארוחת צהריים",
    "אארוחת ערב": "ארוחת ערב", "ארוחאת ערב": "ארוחת ערב",
    "חאטיף": "חטיף", "חטיאף": "חטיף",
    "קאינוח": "קינוח", "קינואח": "קינוח",
    "ראעב": "רעב", "רעאב": "רעב",
    "שאבע": "שבע", "שבאע": "שבע",
    "צאמא": "צמא", "צמאא": "צמא",
    "טאעים": "טעים", "טעיאם": "טעים",
    "לאא טעים": "לא טעים", "לאא טאעים": "לא טעים",
    "מאלוח": "מלוח", "מלואח": "מלוח",
    "מאתוק": "מתוק", "מתואק": "מתוק",
    "חאמוץ": "חמוץ", "חמואץ": "חמוץ",
    "מאר": "מר", "מאאר": "מר",
    "חאריף": "חריף", "חריאף": "חריף",
    "עאסיסי": "עסיסי", "עסיסאי": "עסיסי",
    "פאריך": "פריך", "פריאך": "פריך",
    "ראך": "רך", "רכאך": "רך",
    "קאשה": "קשה", "קשאה": "קשה",
    "מאנה": "מנה", "מנאה": "מנה",
    "תאפריט": "תפריט", "תפריאט": "תפריט",
    "מאלצר": "מלצר", "מלצאר": "מלצר",
    "חאשבון": "חשבון", "חשבואן": "חשבון",
    "טאיפ": "טיפ", "טיאפ": "טיפ",
    "לאהזמין": "להזמין", "להזמיאן": "להזמין",
    
    # ═══════════════════════════════════════════════════════════════
    # 💤 שינה ומנוחה - SLEEP & REST
    # ═══════════════════════════════════════════════════════════════
    "לאישון": "לישון", "לישואן": "לישון",
    "לאהתעורר": "להתעורר", "להתעוראר": "להתעורר",
    "עאייף": "עייף", "עייאף": "עייף",
    "עאייפות": "עייפות", "עייפאות": "עייפות",
    "נאמנום": "נמנום", "נמנאום": "נמנום",
    "לאהירדם": "להירדם", "להירדאם": "להירדם",
    "חאלום": "חלום", "חלואם": "חלום",
    "סאיוט לילה": "סיוט לילה", "סיואט לילה": "סיוט לילה",
    "מאיטה": "מיטה", "מיטאה": "מיטה",
    "כארית": "כרית", "כריאת": "כרית",
    "שאמיכה": "שמיכה", "שמיכאה": "שמיכה",
    "סאדין": "סדין", "סדיאן": "סדין",
    "מאתרון": "מזרון", "מזרואן": "מזרון",
    "שאעון מעורר": "שעון מעורר", "שעאון מעורר": "שעון מעורר",
    "לאהפעיל אזעקה": "להפעיל אזעקה", "להפעיאל אזעקה": "להפעיל אזעקה",
    "לאכבות אזעקה": "לכבות אזעקה", "לכבאות אזעקה": "לכבות אזעקה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎭 תכונות אופי - CHARACTER TRAITS
    # ═══════════════════════════════════════════════════════════════
    "נאחמד": "נחמד", "נחמאד": "נחמד",
    "נאעים": "נעים", "נעיאם": "נעים",
    "אאדיב": "אדיב", "אדיאב": "אדיב",
    "מאנומס": "מנומס", "מנומאס": "מנומס",
    "חאמוד": "חמוד", "חמואד": "חמוד",
    "מאקסים": "מקסים", "מקסיאם": "מקסים",
    "מאעצבן": "מעצבן", "מעצבאן": "מעצבן",
    "גאס": "גס", "גסאא": "גס",
    "עאצלן": "עצלן", "עצלאן": "עצלן",
    "חארוץ": "חרוץ", "חרואץ": "חרוץ",
    "מאסודר": "מסודר", "מסודאר": "מסודר",
    "מאבולגן": "מבולגן", "מבולגאן": "מבולגן",
    "שאקט": "שקט", "שקאט": "שקט",
    "ראעשני": "רעשני", "רעשנאי": "רעשני",
    "סאבלני": "סבלני", "סבלנאי": "סבלני",
    "חאסר סבלנות": "חסר סבלנות", "חסאר סבלנות": "חסר סבלנות",
    "עאדין": "עדין", "עדיאן": "עדין",
    "גאס רוח": "גס רוח", "גאס רואח": "גס רוח",
    "יאהיר": "יהיר", "יהיאר": "יהיר",
    "עאנוותן": "ענוותן", "ענוותאן": "ענוותן",
    "אאמיץ": "אמיץ", "אמיאץ": "אמיץ",
    "פאחדן": "פחדן", "פחדאן": "פחדן",
    "כאנה": "כנה", "כנאה": "כנה",
    "שאקרן": "שקרן", "שקראן": "שקרן",
    
    # ═══════════════════════════════════════════════════════════════
    # 🌐 אינטרנט ורשתות חברתיות - INTERNET & SOCIAL MEDIA
    # ═══════════════════════════════════════════════════════════════
    "פאייסבוק": "פייסבוק", "פייסבואק": "פייסבוק",
    "אאינסטגרם": "אינסטגרם", "אינסטגראם": "אינסטגרם",
    "טאיקטוק": "טיקטוק", "טיקטואק": "טיקטוק",
    "יאוטיוב": "יוטיוב", "יוטיואב": "יוטיוב",
    "טאוויטר": "טוויטר", "טוויטאר": "טוויטר",
    "ואואצאפ": "וואצאפ", "וואצאאפ": "וואצאפ",
    "טאלגרם": "טלגרם", "טלגראם": "טלגרם",
    "לאייק": "לייק", "לייאק": "לייק",
    "שאיתוף": "שיתוף", "שיתאוף": "שיתוף",
    "תאגובה": "תגובה", "תגובאה": "תגובה",
    "עאוקבים": "עוקבים", "עוקביאם": "עוקבים",
    "לאעקוב": "לעקוב", "לעקאוב": "לעקוב",
    "פאוסט": "פוסט", "פוסאט": "פוסט",
    "סאטורי": "סטורי", "סטוריא": "סטורי",
    "ראילס": "רילס", "רילאס": "רילס",
    "האודעה": "הודעה", "הודעאה": "הודעה",
    "הואדעות": "הודעות", "הודעאות": "הודעות",
    "צ'אאט": "צ'אט", "צאאט": "צ'אט",
    "וידאיאו": "וידיאו", "ווידיאו": "וידיאו",
    "סאלפי": "סלפי", "סלפאי": "סלפי",
    "תאמונה": "תמונה", "תמונאה": "תמונה",
    "אאמוג'י": "אמוג'י", "אמוג'אי": "אמוג'י",
    "האאשטאג": "האשטאג", "האשטאאג": "האשטאג",
    "נאוטיפיקציה": "נוטיפיקציה", "נוטיפיקציאה": "נוטיפיקציה",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔧 כלי עבודה ותיקונים - TOOLS & REPAIRS
    # ═══════════════════════════════════════════════════════════════
    "פאטיש": "פטיש", "פטיאש": "פטיש",
    "מאברג": "מברג", "מבראג": "מברג",
    "מאקדחה": "מקדחה", "מקדחאה": "מקדחה",
    "מאסור": "מסור", "מסואר": "מסור",
    "צאבת": "צבת", "צבאת": "צבת",
    "מאפתח": "מפתח", "מפתאח": "מפתח",
    "בארגים": "ברגים", "ברגיאם": "ברגים",
    "מאסמרים": "מסמרים", "מסמריאם": "מסמרים",
    "דאבק": "דבק", "דבאק": "דבק",
    "סארט מידה": "סרט מידה", "סראט מידה": "סרט מידה",
    "פאלס": "פלס", "פלאס": "פלס",
    "סאולם": "סולם", "סולאם": "סולם",
    "צאבע": "צבע", "צבאע": "צבע",
    "מאברשת צבע": "מברשת צבע", "מברשאת צבע": "מברשת צבע",
    "ראולר": "רולר", "רולאר": "רולר",
    "ניאילון": "ניילון", "ניילאון": "ניילון",
    "טאייפ": "טייפ", "טייאפ": "טייפ",
    "לאתקן": "לתקן", "לתקאן": "לתקן",
    "לאשפץ": "לשפץ", "לשפאץ": "לשפץ",
    "לאהרכיב": "להרכיב", "להרכיאב": "להרכיב",
    "לאפרק": "לפרק", "לפראק": "לפרק",
    
    # ═══════════════════════════════════════════════════════════════
    # 🎲 משחקים והנאות - GAMES & FUN
    # ═══════════════════════════════════════════════════════════════
    "מאשחק לוח": "משחק לוח", "משחאק לוח": "משחק לוח",
    "קאלפים": "קלפים", "קלפיאם": "קלפים",
    "שאח": "שח", "שאאח": "שח",
    "שאחמט": "שחמט", "שחמאט": "שחמט",
    "פאזל": "פאזל", "פזאל": "פאזל",
    "דאומינו": "דומינו", "דומינאו": "דומינו",
    "באקגמון": "שש בש", "שאש באש": "שש בש",
    "ראמי": "רמי", "רמאי": "רמי",
    "לאשחק": "לשחק", "לשחאק": "לשחק",
    "לאנצח": "לנצח", "לנצאח": "לנצח",
    "לאהפסיד": "להפסיד", "להפסיאד": "להפסיד",
    "תאור": "תור", "תואר": "תור",
    "לאהמר": "להמר", "להמאר": "להמר",
    "לאותרי": "לוטו", "לאוטו": "לוטו",
    "הארחקה": "הגרלה", "הגרלאה": "הגרלה",
    "פארס": "פרס", "פראס": "פרס",
    "לאזכות": "לזכות", "לזכאות": "לזכות",
    
    # ═══════════════════════════════════════════════════════════════
    # 💼 עבודה וקריירה - WORK & CAREER
    # ═══════════════════════════════════════════════════════════════
    "ראיון עבודה": "ריאיון עבודה", "ריאיון עאבודה": "ריאיון עבודה",
    "קאורות חיים": "קורות חיים", "קורואת חיים": "קורות חיים",
    "מאשכורת": "משכורת", "משכוראת": "משכורת",
    "שאכר": "שכר", "שכאר": "שכר",
    "באונוס": "בונוס", "בונואס": "בונוס",
    "האעלאה": "העלאה", "העלאאה": "העלאה",
    "קאידום": "קידום", "קידואם": "קידום",
    "פאיטורים": "פיטורים", "פיטוריאם": "פיטורים",
    "התפאטרות": "התפטרות", "התפטראות": "התפטרות",
    "חאופשה": "חופשה", "חופשאה": "חופשה",
    "מאחלה": "מחלה", "מחלאה": "מחלה",
    "יאום מחלה": "יום מחלה", "יאום מאחלה": "יום מחלה",
    "פאנסיה": "פנסיה", "פנסיאה": "פנסיה",
    "פארישה": "פרישה", "פרישאה": "פרישה",
    "משאמרת": "משמרת", "משמראת": "משמרת",
    "שאעות נוספות": "שעות נוספות", "שעאות נוספות": "שעות נוספות",
    "חאוזה": "חוזה", "חוזאה": "חוזה",
    "הסכאם עבודה": "הסכם עבודה", "הסאכם עבודה": "הסכם עבודה",
    "באוס": "בוס", "בואס": "בוס",
    "מאנהל ישיר": "מנהל ישיר", "מנהאל ישיר": "מנהל ישיר",
    "צאוות": "צוות", "צוואת": "צוות",
    "עאמיתים לעבודה": "עמיתים לעבודה", "עמיתיאם לעבודה": "עמיתים לעבודה",
    
    # ═══════════════════════════════════════════════════════════════
    # 📐 צורות ומושגים מתמטיים - SHAPES & MATH
    # ═══════════════════════════════════════════════════════════════
    "עאיגול": "עיגול", "עיגאול": "עיגול",
    "ראיבוע": "ריבוע", "ריבואע": "ריבוע",
    "מאשולש": "משולש", "משולאש": "משולש",
    "מאלבן": "מלבן", "מלבאן": "מלבן",
    "קאו": "קו", "קאוו": "קו",
    "נאקודה": "נקודה", "נקודאה": "נקודה",
    "זאווית": "זווית", "זוויאת": "זווית",
    "קאוטר": "קוטר", "קוטאר": "קוטר",
    "ראדיוס": "רדיוס", "רדיואס": "רדיוס",
    "האיקף": "היקף", "היקאף": "היקף",
    "שאטח": "שטח", "שטאח": "שטח",
    "נאפח": "נפח", "נפאח": "נפח",
    "חאיבור": "חיבור", "חיבאור": "חיבור",
    "חאיסור": "חיסור", "חיסאור": "חיסור",
    "כאפל": "כפל", "כפאל": "כפל",
    "חאילוק": "חילוק", "חילאוק": "חילוק",
    "אאחוז": "אחוז", "אחואז": "אחוז",
    "מאספר": "מספר", "מספאר": "מספר",
    "חאשבון": "חשבון", "חשבאון": "חשבון",
    
    # ═══════════════════════════════════════════════════════════════
    # 🗣️ ביטויים יומיומיים נוספים - MORE EVERYDAY EXPRESSIONS
    # ═══════════════════════════════════════════════════════════════
    "מאה הולך": "מה הולך", "מאה האולך": "מה הולך",
    "מאה העניינים": "מה העניינים", "מאה העאניינים": "מה העניינים",
    "אאין בעיה": "אין בעיה", "איאן בעיה": "אין בעיה",
    "לאא נורא": "לא נורא", "לאא נאורא": "לא נורא",
    "מאזל טוב": "מזל טוב", "מזאל טוב": "מזל טוב",
    "בהאצלחה": "בהצלחה", "בהצלאחה": "בהצלחה",
    "כאל הכבוד": "כל הכבוד", "כאל האכבוד": "כל הכבוד",
    "באסדר גמור": "בסדר גמור", "בסאדר גמור": "בסדר גמור",
    "מאעולה": "מעולה", "מעולאה": "מעולה",
    "נאהדר": "נהדר", "נהדאר": "נהדר",
    "מאצוין": "מצוין", "מצויאן": "מצוין",
    "נאפלא": "נפלא", "נפלאא": "נפלא",
    "אאדיר": "אדיר", "אדיאר": "אדיר",
    "מאושלם": "מושלם", "מושלאם": "מושלם",
    "לאא רע": "לא רע", "לאא ראע": "לא רע",
    "סאבבלבס": "סבבלבס", "סבבלאבס": "סבבלבס",
    "באכיף": "בכיף", "בכייאף": "בכיף",
    "באראק": "ברק", "בראאק": "ברק",
    "באטח": "בטח", "בטאח": "בטח",
    "וואדאי": "ודאי", "ודאאי": "ודאי",
    "כאנראה": "כנראה", "כנראאה": "כנראה",
    "אאפשר": "אפשר", "אפשאר": "אפשר",
    "אאי אפשר": "אי אפשר", "איא אפשר": "אי אפשר",
    "מאותר": "מאוחר", "מאוחאר": "מאוחר",
    "מאוקדם": "מוקדם", "מוקאדם": "מוקדם",
    "באזמן": "בזמן", "בזמאן": "בזמן",
    "בדאיוק": "בדיוק", "בדיואק": "בדיוק",
    "באערך": "בערך", "בעראך": "בערך",
    "כאמעט": "כמעט", "כמעאט": "כמעט",
    
    # ═══════════════════════════════════════════════════════════════
    # 🏋️ כושר ובריאות מורחב - EXTENDED FITNESS & HEALTH
    # ═══════════════════════════════════════════════════════════════
    "דאיאטה": "דיאטה", "דיאטאה": "דיאטה",
    "קאלוריות": "קלוריות", "קלוריאות": "קלוריות",
    "חאלבון": "חלבון", "חלבואן": "חלבון",
    "פאחמימות": "פחמימות", "פחמימאות": "פחמימות",
    "שאומן": "שומן", "שומאן": "שומן",
    "סאיבים": "סיבים", "סיביאם": "סיבים",
    "ואיטמינים": "ויטמינים", "ויטמיניאם": "ויטמינים",
    "מאינרלים": "מינרלים", "מינרליאם": "מינרלים",
    "תאוסף תזונה": "תוסף תזונה", "תוסאף תזונה": "תוסף תזונה",
    "מאשקל": "משקל", "משקאל": "משקל",
    "לאהשמין": "להשמין", "להשמיאן": "להשמין",
    "לארזות": "לרזות", "לרזאות": "לרזות",
    "לאהתאמן": "להתאמן", "להתאמאן": "להתאמן",
    "שארירים": "שרירים", "שריריאם": "שרירים",
    "מאתיחות": "מתיחות", "מתיחאות": "מתיחות",
    "כאושר": "כושר", "כושאר": "כושר",
    "גאמישות": "גמישות", "גמישאות": "גמישות",
    "כאוח": "כוח", "כואח": "כוח",
    "סאיבולת": "סיבולת", "סיבולאת": "סיבולת",
    
    # ═══════════════════════════════════════════════════════════════
    # 🔥 BUILD 196: תיקון אותיות כפולות מרעשי רקע - DOUBLED LETTER FIXES
    # Whisper sometimes doubles consonants when hearing noise
    # ═══════════════════════════════════════════════════════════════
    "דדלתות": "דלתות", "ננעילה": "נעילה", "ממנעולים": "מנעולים",
    "פפורץ": "פורץ", "ככספות": "כספות", "ששירות": "שירות",
    "ממפתחות": "מפתחות", "ררכב": "רכב", "ממכונית": "מכונית",
    "בביתי": "ביתי", "ממקצועי": "מקצועי", "חחירום": "חירום",
    "זזמין": "זמין", "ממהיר": "מהיר", "זזול": "זול",
}

# 🔥 BUILD 196: Known gibberish words that Whisper hallucinates from noise
# These should be REMOVED from transcripts, not corrected
GIBBERISH_WORDS_TO_REMOVE = {
    "ידועל", "בלתי", "ווהו", "הההה", "אאא", "אההה", "אממם",
    "מממ", "חחח", "קקק", "ררר", "שששש", "נננ", "ללל", "יייי",
    "טטט", "ססס", "עעע", "פפפ", "צצצ", "דדד", "גגג", "בבב",
    "ווו", "זזזז", "אאאא", "ממממ", "בלבל", "גלגל", "מלמל",
    "בייי", "אוווו", "ווואו", "יייאה", "נאאא",
}

def normalize_hebrew_text(text: str) -> str:
    """
    BUILD 170.4: Normalize Hebrew STT output using dictionary
    BUILD 196: Also removes gibberish words caused by noise
    """
    if not text:
        return text
    
    result = text
    
    # 🔥 BUILD 196: First, remove known gibberish words
    words = result.split()
    cleaned_words = []
    removed_gibberish = []
    for word in words:
        # Strip punctuation for comparison
        word_clean = word.strip('.,!?;:')
        if word_clean in GIBBERISH_WORDS_TO_REMOVE:
            removed_gibberish.append(word_clean)
            continue  # Skip this word
        cleaned_words.append(word)
    
    if removed_gibberish:
        print(f"🧹 [BUILD 196] Removed gibberish words: {removed_gibberish}")
    
    result = ' '.join(cleaned_words)
    
    # Then apply dictionary corrections
    for wrong, correct in HEBREW_NORMALIZATION.items():
        # Case insensitive replace (Hebrew doesn't have case, but for mixed text)
        if wrong in result.lower():
            result = result.replace(wrong, correct)
    
    return result.strip()

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
        self.user_speech_seen = False  # 🔥 BUILD 193: True if ANY user speech was detected (even if filtered)
        self.is_playing_greeting = False  # True only while greeting audio is playing
        self.state = STATE_LISTEN        # מצב נוכחי
        
        # ✅ תיקון קריטי: מעקב נפרד אחר קול ושקט
        self.last_voice_ts = 0.0         # זמן הקול האחרון - לחישוב דממה אמיתי
        # 🔥 BUILD 171: STRICTER noise thresholds to prevent hallucinations
        self.noise_floor = 50.0          # 🔥 BUILD 171: 50 (was 30) - higher baseline
        self.vad_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 191: Uses MIN_SPEECH_RMS (130) - normal speech
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
        self.barge_in_rms_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 191: Uses MIN_SPEECH_RMS (130) for barge-in
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
        self.closing_sent = False  # 🔥 BUILD 194: True after closing message sent - blocks new transcripts
        self.greeting_completed_at = None  # Runtime state: timestamp when greeting finished
        self.min_call_duration_after_greeting_ms = 3000  # Fixed: don't hangup for 3s after greeting
        self.silence_timeout_sec = 15  # Default - overwritten by CallConfig
        self.silence_max_warnings = 2  # Default - overwritten by CallConfig
        self.smart_hangup_enabled = True  # Default - overwritten by CallConfig
        self.required_lead_fields = ['name', 'phone']  # Default - overwritten by CallConfig
        # 🎯 DYNAMIC LEAD CAPTURE STATE: Tracks ALL captured fields from conversation
        # Updated by _update_lead_capture_state() from AI responses and DTMF
        self.lead_capture_state = {}  # e.g., {'name': 'דני', 'city': 'תל אביב', 'service_type': 'ניקיון'}
        
        # 🔥 BUILD 185: STT CONSISTENCY FILTER - Tracks last 3 attempts for majority voting
        # Prevents hallucinations like "בית שמש" → "מצפה רמון" by locking after 2/3 match
        from server.services.phonetic_validator import ConsistencyFilter
        self.stt_consistency_filter = ConsistencyFilter(max_attempts=3)
        self.city_raw_attempts = []  # Track raw STT attempts for webhook
        self.name_raw_attempts = []  # Track raw STT attempts for webhook
        
        # 🛡️ BUILD 168: VERIFICATION GATE - Only disconnect after user confirms
        # Set to True when user says confirmation words: "כן", "נכון", "בדיוק", "כן כן"
        self.verification_confirmed = False  # Must be True before AI-triggered hangup is allowed
        self._verification_prompt_sent = False  # Tracks if we already asked for verification
        self._silence_final_chance_given = False  # Tracks if we gave extra chance before silence hangup
        # 🔥 BUILD 194: PENDING CONFIRMATION GATE - AI must ask verification question first
        # Only set verification_confirmed when pending_confirmation is True
        self.pending_confirmation = False  # True when AI asked "נכון?/הפרטים נכונים?"

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
            # Using 'shimmer' - stable voice for Hebrew TTS
            call_voice = "shimmer"
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
            
            # 🔥 BUILD 191: OPTIMIZED VAD FOR NORMAL HEBREW SPEECH
            # vad_threshold=0.55 - lower threshold to detect normal/quiet speech
            # silence_duration_ms=700 - slightly longer to avoid premature turn_detected
            # prefix_padding_ms=500 - include 500ms before speech detection
            await client.configure_session(
                instructions=greeting_prompt,
                voice=call_voice,
                input_audio_format="g711_ulaw",
                output_audio_format="g711_ulaw",
                vad_threshold=0.55,        # 🔥 BUILD 191: 0.55 (was 0.65) - detect normal/quiet speech
                silence_duration_ms=700,   # 🔥 BUILD 191: 700ms (was 600) - avoid premature turn_detected
                prefix_padding_ms=500,     # 🔥 BUILD 187: Include 500ms before speech
                temperature=0.6,           # 🔒 Consistent, focused responses
                max_tokens=greeting_max_tokens  # 🔥 Dynamic based on greeting length!
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
                # 🔥 BUILD 194: CLOSING FENCE - Don't send greeting if already closing
                if getattr(self, 'closing_sent', False):
                    print(f"🔒 [BUILD 194] Skipping greeting - closing already sent")
                else:
                    greeting_start_ts = time.time()
                    print(f"🎤 [GREETING] Bot speaks first - triggering greeting at {greeting_start_ts:.3f}")
                    self.greeting_sent = True  # Mark greeting as sent to allow audio through
                    self.is_playing_greeting = True
                    self._greeting_start_ts = greeting_start_ts  # Store for duration logging
                    try:
                        await client.send_event({"type": "response.create"})
                        t_speak = time.time()
                        # 📊 Total time from OpenAI init to response.create
                        total_openai_ms = (t_speak - t_start) * 1000
                        # Also log from T0 if available
                        if hasattr(self, 't0_connected'):
                            total_from_t0 = (t_speak - self.t0_connected) * 1000
                            print(f"✅ [BUILD 163] response.create sent! OpenAI={total_openai_ms:.0f}ms, T0→speak={total_from_t0:.0f}ms")
                        else:
                            print(f"✅ [BUILD 163] response.create sent! OpenAI time: {total_openai_ms:.0f}ms")
                    except Exception as e:
                        print(f"❌ [BUILD 163] Failed to trigger bot speaks first: {e}")
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
                        voice_to_use = getattr(self, '_call_voice', 'shimmer')
                        
                        # 🔥 BUILD 179: max_tokens=4096 for BOTH inbound and outbound
                        # This prevents AI from being cut off mid-sentence
                        session_max_tokens = 4096
                        current_call_direction = getattr(self, 'call_direction', 'inbound')
                        print(f"📞 [{current_call_direction.upper()}] session.update with max_tokens={session_max_tokens}")
                        
                        # 🔥 BUILD 186: CRITICAL - Preserve Hebrew transcription config!
                        # Without this, STT defaults to English and transcribes Hebrew as "Thank you", "Good luck"
                        await client.send_event({
                            "type": "session.update",
                            "session": {
                                "instructions": full_prompt,
                                "voice": voice_to_use,  # 🔒 Must re-send voice to lock it
                                "max_response_output_tokens": session_max_tokens,
                                # 🔥 BUILD 186 FIX: MUST preserve Hebrew transcription config!
                                "input_audio_transcription": {
                                    "model": "whisper-1",
                                    "language": "he"  # 🔒 Force Hebrew - prevents "Thank you" hallucinations
                                }
                            }
                        })
                        print(f"✅ [PHASE 2] Session updated with full prompt: {len(full_prompt)} chars, voice={voice_to_use} locked, max_tokens={session_max_tokens}, transcription=Hebrew")
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
        """Send audio from Twilio to Realtime API"""
        print(f"📤 [REALTIME] Audio sender started")
        
        # 🛡️ BUILD 168.5: Track if we've logged the greeting block message
        _greeting_block_logged = False
        _greeting_resumed_logged = False
        
        # 🔥 BUILD 196.1: PRODUCTION-GRADE AUDIO PREPROCESSING
        # Full implementation per developer spec for noisy environments
        import struct
        import audioop
        import collections
        
        # ════════════════════════════════════════════════════════════════
        # 📐 CONFIGURABLE THRESHOLDS (via env vars for easy tuning)
        # ════════════════════════════════════════════════════════════════
        FRAME_SIZE_MS = int(os.getenv("AUDIO_FRAME_SIZE_MS", "20"))  # 20ms frames
        NOISE_CALIBRATION_MS = int(os.getenv("NOISE_CALIBRATION_MS", "600"))  # First 600ms for calibration
        PREROLL_MS = int(os.getenv("AUDIO_PREROLL_MS", "200"))  # 200ms pre-roll buffer
        HANGOVER_FRAMES = int(os.getenv("AUDIO_HANGOVER_FRAMES", "4"))  # 4 frames (~80ms) hangover
        
        # SNR thresholds with separate start/stop for hysteresis
        SNR_START_NORMAL = float(os.getenv("SNR_START_NORMAL", "8"))   # Start speech at 8dB
        SNR_STOP_NORMAL = float(os.getenv("SNR_STOP_NORMAL", "5"))    # Stop speech at 5dB
        SNR_START_MUSIC = float(os.getenv("SNR_START_MUSIC", "12"))   # Start speech at 12dB in music
        SNR_STOP_MUSIC = float(os.getenv("SNR_STOP_MUSIC", "8"))      # Stop speech at 8dB in music
        
        # Music detection thresholds
        MUSIC_ENTER_THRESHOLD = float(os.getenv("MUSIC_ENTER_THRESHOLD", "0.6"))
        MUSIC_EXIT_THRESHOLD = float(os.getenv("MUSIC_EXIT_THRESHOLD", "0.45"))
        
        # Filter coefficients (for 8kHz sample rate)
        HPF_ALPHA = float(os.getenv("AUDIO_HPF_ALPHA", "0.96"))   # ~100Hz high-pass cutoff
        LPF_ALPHA = float(os.getenv("AUDIO_LPF_ALPHA", "0.75"))   # ~3400Hz low-pass cutoff
        
        # AGC (Automatic Gain Control) parameters
        TARGET_RMS = int(os.getenv("AUDIO_TARGET_RMS", "2000"))  # Target RMS level (~-20dBFS)
        AGC_ALPHA = float(os.getenv("AUDIO_AGC_ALPHA", "0.1"))   # How fast to adapt
        AGC_MAX_GAIN = float(os.getenv("AUDIO_AGC_MAX_GAIN", "4.0"))  # Max amplification (12dB)
        AGC_MIN_GAIN = float(os.getenv("AUDIO_AGC_MIN_GAIN", "0.5"))  # Min amplification (-6dB)
        
        # State machine thresholds
        MAYBE_SPEECH_THRESHOLD = int(os.getenv("AUDIO_MAYBE_SPEECH_FRAMES", "3"))  # Frames to confirm speech
        MUSIC_CONFIRM_FRAMES = int(os.getenv("AUDIO_MUSIC_CONFIRM_FRAMES", "5"))   # Frames to confirm music
        
        # ════════════════════════════════════════════════════════════════
        # 🎤 STATE MACHINE: SILENCE → MAYBE_SPEECH → SPEECH
        # ════════════════════════════════════════════════════════════════
        STATE_SILENCE = "SILENCE"
        STATE_MAYBE_SPEECH = "MAYBE_SPEECH"
        STATE_SPEECH = "SPEECH"
        
        current_state = STATE_SILENCE
        maybe_speech_count = 0  # Consecutive high-SNR frames in MAYBE_SPEECH
        hangover_counter = 0  # Frames remaining in hangover
        
        # ════════════════════════════════════════════════════════════════
        # 🔊 NOISE CALIBRATION (first 600ms of call)
        # ════════════════════════════════════════════════════════════════
        calibration_frames = []
        CALIBRATION_FRAMES_NEEDED = NOISE_CALIBRATION_MS // FRAME_SIZE_MS  # ~30 frames
        is_calibrated = False
        noise_rms = 50  # Initial estimate, will be updated after calibration
        noise_rms_slow_alpha = 0.01  # Very slow adaptation after calibration
        
        # ════════════════════════════════════════════════════════════════
        # 📼 PRE-ROLL BUFFER (to capture start of words)
        # ════════════════════════════════════════════════════════════════
        preroll_size = PREROLL_MS // FRAME_SIZE_MS  # ~10 frames for 200ms
        preroll_buffer = collections.deque(maxlen=preroll_size)
        preroll_sent = False  # Track if we sent preroll for current speech segment
        
        # ════════════════════════════════════════════════════════════════
        # 🔊 AGC (Automatic Gain Control) runtime state
        # ════════════════════════════════════════════════════════════════
        caller_rms_slow = 0  # Exponential moving average of caller speech RMS
        
        # ════════════════════════════════════════════════════════════════
        # 🎵 MUSIC DETECTION runtime state
        # ════════════════════════════════════════════════════════════════
        music_detected = False
        music_score_history = collections.deque(maxlen=25)  # ~500ms window
        energy_history = collections.deque(maxlen=50)  # ~1 second for analysis
        music_consecutive_count = 0  # For hysteresis
        
        # Counters for logging
        frames_sent = 0
        frames_blocked = 0
        last_log_time = 0
        total_frames = 0
        
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
                    # Drop the audio chunk - don't send to OpenAI during greeting
                    continue
                else:
                    # Greeting finished - resume sending audio
                    if _greeting_block_logged and not _greeting_resumed_logged:
                        print(f"✅ [GREETING PROTECT] Greeting done - resuming audio to OpenAI")
                        _greeting_resumed_logged = True
                
                # 🔥 BUILD 196.2: PRODUCTION-GRADE AUDIO PREPROCESSING
                # CORRECTED Pipeline: μ-law → PCM16 → bandpass → SNR (pre-AGC) → state machine → AGC (SPEECH only) → send
                # Key fix: SNR computed on pre-AGC audio; AGC only applied to SPEECH frames
                total_frames += 1
                
                try:
                    import base64
                    import math
                    import statistics
                    
                    audio_bytes = base64.b64decode(audio_chunk)
                    pcm_data = audioop.ulaw2lin(audio_bytes, 2)  # 16-bit PCM
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 1: SPEECH BAND FILTER (100Hz - 3400Hz)
                    # ════════════════════════════════════════════════════════════════
                    if not hasattr(self, '_hpf_prev_in'):
                        self._hpf_prev_in = 0
                        self._hpf_prev_out = 0
                        self._lpf_prev_out = 0
                    
                    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
                    filtered_samples = []
                    
                    for sample in samples:
                        hp_out = HPF_ALPHA * (self._hpf_prev_out + sample - self._hpf_prev_in)
                        self._hpf_prev_in = sample
                        self._hpf_prev_out = hp_out
                        lp_out = LPF_ALPHA * self._lpf_prev_out + (1 - LPF_ALPHA) * hp_out
                        self._lpf_prev_out = lp_out
                        filtered_samples.append(int(max(-32768, min(32767, lp_out))))
                    
                    filtered_pcm = struct.pack(f'<{len(filtered_samples)}h', *filtered_samples)
                    frame_rms = audioop.rms(filtered_pcm, 2)  # PRE-AGC RMS for SNR!
                    
                    # Pre-encode filtered audio for preroll (before AGC)
                    filtered_ulaw = audioop.lin2ulaw(filtered_pcm, 2)
                    filtered_chunk = base64.b64encode(filtered_ulaw).decode('ascii')
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 2: NOISE CALIBRATION (first 600ms) - USING PRE-AGC RMS!
                    # Calibrate on raw signal, not AGC-boosted
                    # ════════════════════════════════════════════════════════════════
                    if not is_calibrated:
                        calibration_frames.append(frame_rms)  # Pre-AGC RMS
                        if len(calibration_frames) >= CALIBRATION_FRAMES_NEEDED:
                            sorted_rms = sorted(calibration_frames)
                            percentile_20 = sorted_rms[len(sorted_rms) // 5]
                            noise_rms = max(30, percentile_20)
                            is_calibrated = True
                            print(f"🎚️ [BUILD 196.2] NOISE CALIBRATED: noise_rms={noise_rms:.0f} (from {len(calibration_frames)} frames)")
                        # Store filtered PCM for preroll (before AGC)
                        preroll_buffer.append(filtered_chunk)
                        continue
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 3: SNR CALCULATION (using PRE-AGC RMS!)
                    # This gives true SNR without AGC boosting noise
                    # ════════════════════════════════════════════════════════════════
                    snr_db = 10 * math.log10((frame_rms ** 2) / (noise_rms ** 2 + 1e-10)) if noise_rms > 0 and frame_rms > 0 else 0
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 4: MUSIC DETECTION (with hysteresis) - uses PRE-AGC RMS
                    # ════════════════════════════════════════════════════════════════
                    energy_history.append(frame_rms)
                    
                    if len(energy_history) >= 20:
                        try:
                            mean_energy = statistics.mean(energy_history)
                            std_energy = statistics.stdev(energy_history) if len(energy_history) > 1 else 0
                            cv = std_energy / mean_energy if mean_energy > 0 else 1.0
                            
                            periodicity = 0.5
                            if len(energy_history) >= 40:
                                e_list = list(energy_history)
                                first_mean = statistics.mean(e_list[:20])
                                second_mean = statistics.mean(e_list[20:40])
                                periodicity = 1.0 - abs(first_mean - second_mean) / max(first_mean, second_mean, 1)
                            
                            high_energy_ratio = sum(1 for e in energy_history if e > mean_energy * 0.5) / len(energy_history)
                            
                            music_score = 0
                            if cv < 0.5: music_score += 0.4
                            if periodicity > 0.7: music_score += 0.3
                            if high_energy_ratio > 0.7: music_score += 0.3
                            
                            music_score_history.append(music_score)
                            avg_music_score = statistics.mean(music_score_history) if music_score_history else 0
                            
                            if music_detected:
                                if avg_music_score < MUSIC_EXIT_THRESHOLD:
                                    music_consecutive_count += 1
                                    if music_consecutive_count >= MUSIC_CONFIRM_FRAMES:
                                        music_detected = False
                                        music_consecutive_count = 0
                                        print(f"🎤 [BUILD 196.2] Music stopped - thresholds: start={SNR_START_NORMAL}dB, stop={SNR_STOP_NORMAL}dB")
                                else:
                                    music_consecutive_count = 0
                            else:
                                if avg_music_score > MUSIC_ENTER_THRESHOLD:
                                    music_consecutive_count += 1
                                    if music_consecutive_count >= MUSIC_CONFIRM_FRAMES:
                                        music_detected = True
                                        music_consecutive_count = 0
                                        print(f"🎵 [BUILD 196.2] MUSIC DETECTED - thresholds: start={SNR_START_MUSIC}dB, stop={SNR_STOP_MUSIC}dB")
                                else:
                                    music_consecutive_count = 0
                        except Exception:
                            pass
                    
                    # Select SNR thresholds based on music detection
                    if music_detected:
                        snr_start = SNR_START_MUSIC
                        snr_stop = SNR_STOP_MUSIC
                    else:
                        snr_start = SNR_START_NORMAL
                        snr_stop = SNR_STOP_NORMAL
                    
                    # Slowly adapt noise floor (only in SILENCE, using PRE-AGC RMS)
                    if current_state == STATE_SILENCE and frame_rms < noise_rms * 2:
                        noise_rms = noise_rms_slow_alpha * frame_rms + (1 - noise_rms_slow_alpha) * noise_rms
                        noise_rms = max(30, noise_rms)
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 5: STATE MACHINE (SILENCE → MAYBE_SPEECH → SPEECH)
                    # STRICT: NEVER send in SILENCE or MAYBE_SPEECH!
                    # 🔥 BUILD 196.3: ECHO PROTECTION - Block audio during AI + cooldown
                    # ════════════════════════════════════════════════════════════════
                    prev_state = current_state
                    is_ai_speaking = self.is_ai_speaking_event.is_set()
                    
                    # 🔥 BUILD 196.4: Calculate time since AI stopped speaking
                    # REDUCED from 500ms to 400ms - allow faster user responses
                    ai_finished_ts = getattr(self, '_ai_finished_speaking_ts', 0)
                    echo_cooldown_ms = 400  # 400ms echo rejection window (was 500)
                    in_echo_cooldown = False
                    time_since_ai_ms = 0
                    if ai_finished_ts > 0:
                        time_since_ai_ms = (time.time() - ai_finished_ts) * 1000
                        in_echo_cooldown = time_since_ai_ms < echo_cooldown_ms
                    
                    # 🔥 BUILD 196.4: Echo blocking - ONLY when AI is ACTUALLY speaking
                    # CRITICAL: echo_blocked should NOT be true for music detection!
                    # Music detection is for adjusting SNR thresholds, NOT for blocking user speech
                    echo_blocked = is_ai_speaking or in_echo_cooldown
                    
                    # Buffer in SILENCE and MAYBE_SPEECH (pre-AGC filtered audio)
                    if current_state in (STATE_SILENCE, STATE_MAYBE_SPEECH):
                        preroll_buffer.append(filtered_chunk)
                    
                    if current_state == STATE_SILENCE:
                        if snr_db >= snr_start:
                            current_state = STATE_MAYBE_SPEECH
                            maybe_speech_count = 1
                    
                    elif current_state == STATE_MAYBE_SPEECH:
                        if snr_db >= snr_start:
                            maybe_speech_count += 1
                            if maybe_speech_count >= MAYBE_SPEECH_THRESHOLD:
                                current_state = STATE_SPEECH
                                preroll_sent = False
                                hangover_counter = HANGOVER_FRAMES
                                # 🔥 BUILD 196.3: Track utterance start time for duration check
                                utterance_start_ms = time.time() * 1000
                                print(f"🎤 [BUILD 196.2] SPEECH STARTED (SNR={snr_db:.1f}dB) echo_blocked={echo_blocked}")
                        else:
                            maybe_speech_count = 0
                            current_state = STATE_SILENCE
                    
                    elif current_state == STATE_SPEECH:
                        if snr_db >= snr_stop:
                            hangover_counter = HANGOVER_FRAMES  # Reset hangover
                        else:
                            hangover_counter -= 1
                            if hangover_counter <= 0:
                                current_state = STATE_SILENCE
                                maybe_speech_count = 0
                                preroll_buffer.clear()  # Clear stale preroll on speech end
                                
                                # 🔥 BUILD 196.4: Calculate utterance duration
                                # REDUCED from 300ms to 150ms - don't skip short Hebrew words like "כן", "לא", city names
                                MIN_UTTERANCE_MS = 150
                                utterance_end_ms = time.time() * 1000
                                duration_ms = utterance_end_ms - utterance_start_ms
                                
                                print(f"🔇 [BUILD 196.4] SPEECH ENDED (SNR={snr_db:.1f}dB) duration={duration_ms:.0f}ms echo_blocked={echo_blocked} is_ai={is_ai_speaking}")
                                
                                # 🔥 BUILD 196.4: END OF UTTERANCE - RELAXED conditions
                                # Audio is ALWAYS sent to OpenAI (they hear everything)
                                # We only skip the MANUAL TRIGGER for very short speech
                                if duration_ms < MIN_UTTERANCE_MS:
                                    # Short speech - still sent to OpenAI but no manual trigger
                                    print(f"⏭️ [BUILD 196.4] SHORT but SENT to OpenAI: duration={duration_ms:.0f}ms (no manual trigger)")
                                elif echo_blocked:
                                    # Echo protection - log reason clearly
                                    print(f"🔇 [BUILD 196.4] SPEECH→SILENCE during echo (is_ai={is_ai_speaking}, cooldown={in_echo_cooldown}) - NOT triggering")
                                elif getattr(self, 'closing_sent', False):
                                    print(f"🔒 [BUILD 196.4] SPEECH→SILENCE during closing - NOT triggering")
                                else:
                                    # Valid utterance - trigger AI response!
                                    print(f"🎤 END OF UTTERANCE: {duration_ms/1000:.1f}s echo_blocked=False")
                                    print(f"🎯 [BUILD 196.4] SPEECH→SILENCE: Triggering AI response...")
                                    if hasattr(self, 'realtime_text_input_queue'):
                                        try:
                                            self.realtime_text_input_queue.put("[TRIGGER_RESPONSE]")
                                            print(f"✅ [BUILD 196.4] response.create queued (end of speech)")
                                        except Exception as e:
                                            print(f"⚠️ [BUILD 196.4] Failed to queue trigger: {e}")
                    
                    if prev_state != current_state:
                        print(f"📊 [BUILD 196.2] State: {prev_state} → {current_state} | SNR={snr_db:.1f}dB | noise={noise_rms:.0f} | music={music_detected} | echo_blocked={echo_blocked}")
                    
                    # ════════════════════════════════════════════════════════════════
                    # STEP 6: DECIDE WHETHER TO SEND
                    # 🔥 BUILD 196.4: ALWAYS send audio in SPEECH state!
                    # Echo protection only affects TRIGGER_RESPONSE, NOT audio transmission
                    # OpenAI needs to hear everything to understand the user!
                    # ════════════════════════════════════════════════════════════════
                    should_send = False
                    chunk_to_send = None
                    
                    # 🔥 BUILD 196.4: REMOVED audio blocking during echo!
                    # We ALWAYS send audio to OpenAI when in SPEECH state
                    # Echo protection only blocks the manual response.create trigger
                    # This ensures OpenAI hears short words like "כן", "לא", city names
                    
                    if current_state == STATE_SPEECH:
                        should_send = True
                        
                        # ════════════════════════════════════════════════════════════════
                        # STEP 7: AGC - ONLY ON SPEECH FRAMES!
                        # This normalizes speech volume without boosting noise
                        # ════════════════════════════════════════════════════════════════
                        if frame_rms > 0:
                            # Track caller's speech level (only during speech)
                            if caller_rms_slow == 0:
                                caller_rms_slow = frame_rms
                            else:
                                caller_rms_slow = AGC_ALPHA * frame_rms + (1 - AGC_ALPHA) * caller_rms_slow
                            
                            gain = TARGET_RMS / caller_rms_slow if caller_rms_slow > 0 else 1.0
                            gain = max(AGC_MIN_GAIN, min(AGC_MAX_GAIN, gain))
                            
                            # Apply AGC to current frame
                            agc_samples = [int(max(-32768, min(32767, s * gain))) for s in filtered_samples]
                            agc_pcm = struct.pack(f'<{len(agc_samples)}h', *agc_samples)
                            agc_ulaw = audioop.lin2ulaw(agc_pcm, 2)
                            chunk_to_send = base64.b64encode(agc_ulaw).decode('ascii')
                        else:
                            chunk_to_send = filtered_chunk
                            gain = 1.0
                        
                        # Flush pre-roll buffer on entering SPEECH
                        if not preroll_sent and len(preroll_buffer) > 0:
                            print(f"📼 [BUILD 196.2] Sending {len(preroll_buffer)} pre-roll frames (with AGC gain={gain:.2f}x)")
                            for preroll_chunk_raw in preroll_buffer:
                                # Apply AGC to preroll frames too (for consistent volume)
                                if gain != 1.0:
                                    try:
                                        pr_bytes = base64.b64decode(preroll_chunk_raw)
                                        pr_pcm = audioop.ulaw2lin(pr_bytes, 2)
                                        pr_samples = struct.unpack(f'<{len(pr_pcm)//2}h', pr_pcm)
                                        pr_agc = [int(max(-32768, min(32767, s * gain))) for s in pr_samples]
                                        pr_agc_pcm = struct.pack(f'<{len(pr_agc)}h', *pr_agc)
                                        pr_agc_ulaw = audioop.lin2ulaw(pr_agc_pcm, 2)
                                        preroll_chunk_agc = base64.b64encode(pr_agc_ulaw).decode('ascii')
                                        await client.send_audio_chunk(preroll_chunk_agc)
                                    except:
                                        await client.send_audio_chunk(preroll_chunk_raw)
                                else:
                                    await client.send_audio_chunk(preroll_chunk_raw)
                                frames_sent += 1
                            preroll_buffer.clear()
                            preroll_sent = True
                    
                    # 🔥 BUILD 196.3: Removed is_ai_speaking path - we now block audio entirely during AI speech
                    # Barge-in detection is handled by OpenAI's input_audio_buffer.speech_started event
                    # when user speaks loudly enough to overcome the echo
                    
                    # Note: SILENCE and MAYBE_SPEECH NEVER send - prevents noise leaks
                    
                    if not should_send:
                        frames_blocked += 1
                        now = time.time()
                        if now - last_log_time > 10:
                            mode = "🎵MUSIC" if music_detected else "🎤NORMAL"
                            print(f"📊 [BUILD 196.2] Stats: sent={frames_sent} blocked={frames_blocked} | {mode} | noise={noise_rms:.0f} | state={current_state}")
                            last_log_time = now
                        continue
                    
                    frames_sent += 1
                    audio_chunk = chunk_to_send
                    
                except Exception as e:
                    import traceback
                    print(f"⚠️ [BUILD 196.2] Processing error: {e}")
                    traceback.print_exc()
                
                # 💰 COST TRACKING: Count user audio chunks being sent to OpenAI
                # Start timer on first chunk
                if not hasattr(self, '_user_speech_start') or self._user_speech_start is None:
                    self._user_speech_start = time.time()
                self.realtime_audio_in_chunks += 1
                
                await client.send_audio_chunk(audio_chunk)
                
            except Exception as e:
                print(f"❌ [REALTIME] Audio sender error: {e}")
                break
        
        print(f"📤 [REALTIME] Audio sender ended")
    
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
                
                # 🔥 BUILD 196.3: Handle special trigger command with active response check
                if text_message == "[TRIGGER_RESPONSE]":
                    try:
                        # 🔥 BUILD 196.3: Check if there's already an active response
                        has_active_response = getattr(self, 'active_response_id', None) is not None
                        is_closing = getattr(self, 'closing_sent', False)
                        
                        if has_active_response:
                            print(f"⏭️ [BUILD 196.3] Active response in progress ({self.active_response_id[:15]}...) - NOT creating new one")
                        elif is_closing:
                            print(f"🔒 [BUILD 196.3] Call closing - NOT creating response")
                        else:
                            # 🔥 CRITICAL: Send response.create to trigger AI response
                            await client.send_event({"type": "response.create"})
                            print(f"✅ [BUILD 196.3] response.create sent (manual trigger)")
                    except Exception as e:
                        print(f"⚠️ [BUILD 196.3] Failed to send response.create: {e}")
                    continue
                
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
                        
                        # 🔥 BUILD 193: IMMEDIATE RECOVERY for ANY cancelled response!
                        # When turn_detected cancels response, AI may go silent.
                        # OLD BUG: Only triggered recovery for output_count=0, but AI can also
                        # get stuck after partial speech (output_count=1 with cancelled).
                        # FIX: Trigger recovery for ANY cancelled response to keep conversation flowing
                        # 🔥 BUILD 194: But NEVER recover after closing_sent - call is ending!
                        if status == "cancelled" and self.user_has_spoken and not getattr(self, 'closing_sent', False):
                            _orig_print(f"🔄 [BUILD 193] Response cancelled (output={len(output)})! Triggering IMMEDIATE recovery...", flush=True)
                            
                            # 🔥 BUILD 192: IMMEDIATE recovery - don't wait for speech_stopped!
                            async def _immediate_recovery():
                                # Short delay to let any pending events settle
                                await asyncio.sleep(0.8)  # 800ms delay
                                
                                # Guard 1: Check if AI is already speaking
                                if self.is_ai_speaking_event.is_set():
                                    _orig_print(f"🔄 [BUILD 192] Recovery skipped - AI already speaking", flush=True)
                                    return
                                # Guard 2: Check if there's a pending response
                                if self.response_pending_event.is_set():
                                    _orig_print(f"🔄 [BUILD 192] Recovery skipped - response pending", flush=True)
                                    return
                                # Guard 3: Check if speech is active (user still talking)
                                if getattr(self, '_realtime_speech_active', False):
                                    _orig_print(f"🔄 [BUILD 192] Recovery skipped - user still speaking", flush=True)
                                    return
                                
                                # All guards passed - trigger recovery
                                _orig_print(f"🔄 [BUILD 192] RECOVERY: Triggering response.create NOW!", flush=True)
                                try:
                                    await client.send_event({"type": "response.create"})
                                    _orig_print(f"✅ [BUILD 192] RECOVERY SUCCESS: response.create sent!", flush=True)
                                except Exception as e:
                                    _orig_print(f"⚠️ [BUILD 192] Recovery failed: {e}", flush=True)
                            
                            asyncio.create_task(_immediate_recovery())
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
                    # 🔥 BUILD 194: CLOSING FENCE - Don't trigger barge-in after closing message
                    if getattr(self, 'closing_sent', False):
                        print(f"🔒 [BUILD 194] Ignoring speech_started - closing already sent")
                        continue  # Don't process - prevents AI interruption during closing
                    
                    # 🛡️ FIX: PROTECT GREETING - Don't trigger barge-in while greeting is playing!
                    if self.is_playing_greeting:
                        print(f"🛡️ [PROTECT GREETING] Ignoring speech_started - greeting still playing")
                        continue  # Don't process this event at all
                    
                    # 🔥 BUILD 194: RESPONSE GRACE PERIOD - Ignore speech_started within 1000ms of response.created
                    # This prevents echo/noise from cancelling the response before audio starts
                    # 🔥 BUILD 194: Increased to 1000ms - choppy speech fix
                    RESPONSE_GRACE_PERIOD_MS = 1000  # 🔥 BUILD 194: 1000ms (was 750) - prevent choppy interruptions
                    response_created_ts = getattr(self, '_response_created_ts', 0)
                    time_since_response = (time.time() - response_created_ts) * 1000 if response_created_ts else 99999
                    if time_since_response < RESPONSE_GRACE_PERIOD_MS and self.active_response_id:
                        print(f"🛡️ [BUILD 187 GRACE] Ignoring speech_started - only {time_since_response:.0f}ms since response.created (grace={RESPONSE_GRACE_PERIOD_MS}ms)")
                        # Don't mark user_has_spoken, don't bypass noise gate - just ignore this event
                        continue
                    
                    print(f"🎤 [REALTIME] User started speaking - setting user_has_spoken=True")
                    self.user_has_spoken = True
                    self.user_speech_seen = True  # 🔥 BUILD 193: Flag for finalize (even if transcripts are filtered)
                    # 🔥 BUILD 182: IMMEDIATE LOOP GUARD RESET - Don't wait for transcription!
                    # This prevents loop guard from triggering when user IS speaking
                    if self._consecutive_ai_responses > 0:
                        print(f"✅ [LOOP GUARD] User started speaking - resetting consecutive counter ({self._consecutive_ai_responses} -> 0)")
                        self._consecutive_ai_responses = 0
                    if self._loop_guard_engaged:
                        print(f"✅ [LOOP GUARD] User started speaking - disengaging loop guard EARLY")
                        self._loop_guard_engaged = False
                    
                    # 🔥 BUILD 195: SUSTAINED SPEECH REQUIREMENT
                    # Don't trigger barge-in immediately - wait 600ms to confirm it's real speech
                    # This prevents choppy audio from short noise bursts
                    self._speech_started_at = time.time()
                    self._sustained_speech_confirmed = False  # Will be set True after 600ms
                    print(f"⏳ [BUILD 195] Speech detected - will confirm after 600ms sustained speech...")
                    
                    # 🔥 BUILD 196.3: REMOVED noise gate bypass!
                    # The bypass was causing echo to be sent to OpenAI, making the AI talk to itself.
                    # Now BUILD 196.3 blocks ALL audio during AI speech and cooldown period.
                    # User speech is still captured by the pre-filter state machine when appropriate.
                    self._realtime_speech_active = False  # 🔥 BUILD 196.3: Disabled bypass
                    print(f"🛡️ [BUILD 196.3] Speech detected - echo protection active (no bypass)")
                
                # 🔥 BUILD 166: Clear speech active flag when speech ends
                if event_type == "input_audio_buffer.speech_stopped":
                    self._realtime_speech_active = False
                    
                    # 🔥 BUILD 195: Check if speech was sustained (600ms+) for valid input
                    SUSTAINED_SPEECH_MS = 600
                    speech_started_at = getattr(self, '_speech_started_at', 0)
                    if speech_started_at:
                        speech_duration_ms = (time.time() - speech_started_at) * 1000
                        if speech_duration_ms < SUSTAINED_SPEECH_MS:
                            print(f"⚡ [BUILD 195] SHORT speech ({speech_duration_ms:.0f}ms < {SUSTAINED_SPEECH_MS}ms) - likely noise, NOT valid input")
                            self._sustained_speech_confirmed = False
                        else:
                            print(f"✅ [BUILD 195] SUSTAINED speech ({speech_duration_ms:.0f}ms >= {SUSTAINED_SPEECH_MS}ms) - valid user input")
                            self._sustained_speech_confirmed = True
                    
                    # Reset timestamps
                    self._speech_started_at = 0
                    print(f"🎤 [BUILD 166] Speech ended - noise gate RE-ENABLED")
                    # 🔥 BUILD 192: Recovery now triggered IMMEDIATELY from response.done
                    # No longer waiting for speech_stopped (which might never come if speech_started was blocked)
                
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
                        
                        # 🔥 BUILD 196.5: CRITICAL - Save AI transcript to conversation_history!
                        # This was MISSING - AI transcripts were only printed, never stored
                        self.conversation_history.append({
                            "speaker": "assistant",
                            "text": transcript,
                            "ts": time.time()
                        })
                        print(f"💾 [BUILD 196.5] AI transcript saved to conversation_history (total: {len(self.conversation_history)} messages)")
                        
                        # 🔥 BUILD 196.4: DEBUG mode for Calliber (business_id=10)
                        calliber_debug = getattr(self, 'business_id', None) == 10
                        if calliber_debug:
                            display_transcript = transcript[:80] + '...' if len(transcript) > 80 else transcript
                            print(f"🔍 [DEBUG CALLIBER] AI_REPLY: '{display_transcript}'")
                        
                        # 🔥 BUILD 195: Detect FINAL verification question (END OF CALL ONLY!)
                        # Only set pending_confirmation when lead already captured AND AI asks for confirmation
                        # This prevents casual "כן" mid-call from triggering confirmation
                        verification_phrases = [
                            "נכון?", "הפרטים נכונים", "מוודאת", "מוודא",
                            "רק לוודא", "רק מוודאת", "לוודא שהבנתי", "נכון שהבנתי"
                        ]
                        is_verification_question = any(phrase in transcript for phrase in verification_phrases)
                        
                        # 🔥 BUILD 195: CRITICAL - Only activate pending_confirmation at END of call
                        # Requires: lead_captured=True (we have all the info we need)
                        if is_verification_question and getattr(self, 'lead_captured', False):
                            self.pending_confirmation = True
                            print(f"🔔 [BUILD 195] FINAL verification question (lead_captured=True) - waiting for user confirmation")
                        elif is_verification_question:
                            print(f"ℹ️ [BUILD 195] Verification phrase detected but lead NOT captured yet - NOT setting pending_confirmation")
                        
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
                        is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
                        is_closing = getattr(self, 'call_state', None) == CallState.CLOSING
                        is_hanging_up = getattr(self, 'hangup_triggered', False)
                        
                        # 🔥 BUILD 182: Check if appointment was recently created/scheduled
                        crm_ctx = getattr(self, 'crm_context', None)
                        has_appointment = crm_ctx and getattr(crm_ctx, 'has_appointment_created', False)
                        # Also check if AI is discussing appointment (keywords in recent response)
                        appointment_keywords = ['תור', 'פגישה', 'לקבוע', 'זמינות', 'אשר', 'מאשר']
                        is_scheduling = any(kw in transcript for kw in appointment_keywords) if transcript else False
                        
                        if is_outbound:
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
                            
                            # Cancel any pending response
                            if self.active_response_id and self.realtime_client:
                                try:
                                    await client.send_event({"type": "response.cancel"})
                                    print(f"🛑 [LOOP GUARD] Cancelled pending AI response")
                                except:
                                    pass
                            # Clear OpenAI audio queue
                            try:
                                while not self.realtime_audio_out_queue.empty():
                                    self.realtime_audio_out_queue.get_nowait()
                            except:
                                pass
                            # 🔥 CRITICAL: Also clear Twilio TX queue to stop any audio in flight!
                            try:
                                while not self.tx_q.empty():
                                    self.tx_q.get_nowait()
                                print(f"🛑 [LOOP GUARD] Cleared TX queue")
                            except:
                                pass
                            # Send clear to Twilio to stop playback (allowed through guard)
                            try:
                                # Temporarily disengage to send clear, then re-engage
                                self._loop_guard_engaged = False
                                self._tx_enqueue({"type": "clear"})
                                self._loop_guard_engaged = True
                                print(f"🛑 [LOOP GUARD] Sent clear to Twilio")
                            except:
                                self._loop_guard_engaged = True  # Ensure guard remains engaged
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
                        
                        # 🔥 BUILD 170.5: Hangup only when proper conditions are met
                        # Skip all hangup logic if appointment guard is active
                        if hangup_blocked_for_appointment:
                            print(f"🛑 [HANGUP] Skipping all hangup checks - waiting for appointment creation")
                        # Case 1: User explicitly said goodbye - always allow hangup after AI responds
                        elif self.goodbye_detected and ai_polite_closing_detected:
                            hangup_reason = "user_goodbye"
                            should_hangup = True
                            print(f"✅ [HANGUP] User said goodbye, AI responded politely - disconnecting")
                        
                        # Case 2: Lead fully captured AND setting enabled AND customer CONFIRMED AND AI confirmed
                        # 🔥 BUILD 172 FIX: Added verification_confirmed check!
                        elif self.auto_end_after_lead_capture and self.lead_captured and self.verification_confirmed and ai_polite_closing_detected:
                            hangup_reason = "lead_captured_confirmed"
                            should_hangup = True
                            print(f"✅ [HANGUP] Lead captured + confirmed + auto_end=True - disconnecting")
                        
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
                            # 🔥 BUILD 194: Set closing fence + clear buffer
                            self.closing_sent = True
                            print(f"🔒 [BUILD 194] Hangup triggered - blocking future transcripts")
                            if self.realtime_client:
                                asyncio.create_task(self.realtime_client.clear_audio_buffer())
                                print(f"🔇 [BUILD 194] Cleared audio input buffer")
                            # 🔥 BUILD 172: Transition to CLOSING state
                            if self.call_state == CallState.ACTIVE:
                                self.call_state = CallState.CLOSING
                                print(f"📞 [STATE] Transitioning ACTIVE → CLOSING (reason: {hangup_reason})")
                            print(f"📞 [BUILD 163] Pending hangup set - will disconnect after audio finishes playing")
                        
                        # 🔥 NOTE: Hangup is now triggered in response.audio.done to let audio finish!
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # 🔥 BUILD 194: CLOSING FENCE - Block all new transcripts after closing message
                    if getattr(self, 'closing_sent', False):
                        print(f"🔒 [BUILD 194] ❌ BLOCKED: Transcript after closing - '{event.get('transcript', '')[:30]}...'")
                        continue  # Ignore all transcripts after closing - prevents loops!
                    
                    raw_text = event.get("transcript", "") or ""
                    text = raw_text.strip()
                    
                    # 🔥 BUILD 170.4: Apply Hebrew normalization
                    text = normalize_hebrew_text(text)
                    
                    now_ms = time.time() * 1000
                    now_sec = now_ms / 1000
                    
                    # 🔥 BUILD 193: SMART POST-AI COOLDOWN
                    # OLD BUG: Rejected transcripts arriving fast after AI, but this dropped
                    # valid user speech that was spoken DURING AI talking (barge-in).
                    # FIX: Allow transcripts within OVERLAP_GRACE_MS (user likely spoke during AI)
                    OVERLAP_GRACE_MS = 300  # 🔥 BUILD 193: Grace period for overlapping speech
                    if self._ai_finished_speaking_ts > 0:
                        time_since_ai_finished = (now_sec - self._ai_finished_speaking_ts) * 1000
                        if time_since_ai_finished < POST_AI_COOLDOWN_MS:
                            # 🔥 BUILD 193: Allow very fast transcripts (likely overlap)
                            if time_since_ai_finished < OVERLAP_GRACE_MS:
                                print(f"✅ [BUILD 193] ALLOWED: Transcript {time_since_ai_finished:.0f}ms after AI (within {OVERLAP_GRACE_MS}ms overlap grace)")
                                # Don't continue - process this transcript!
                            else:
                                print(f"🔥 [BUILD 171 COOLDOWN] ❌ REJECTED: Transcript arrived {time_since_ai_finished:.0f}ms after AI finished (min: {POST_AI_COOLDOWN_MS}ms)")
                                print(f"   Rejected text: '{text[:50]}...' (likely hallucination)")
                                # 🔥 BUILD 182: Still record for transcript (with filtered flag)
                                if len(text) >= 3:
                                    self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                                continue
                    
                    # 🔥 BUILD 171: STRICTER RMS GATE - Reject if no sustained speech detected
                    recent_rms = getattr(self, '_recent_audio_rms', 0)
                    consec_frames = getattr(self, '_consecutive_voice_frames', 0)
                    ABSOLUTE_SILENCE_RMS = 30  # 🔥 BUILD 171: Raised from 15 to 30
                    
                    # Reject if: low RMS AND not enough consecutive frames
                    if recent_rms < ABSOLUTE_SILENCE_RMS and consec_frames < MIN_CONSECUTIVE_VOICE_FRAMES:
                        print(f"[SILENCE GATE] ❌ REJECTED (RMS={recent_rms:.0f} < {ABSOLUTE_SILENCE_RMS}, frames={consec_frames}): '{text}'")
                        # 🔥 BUILD 182: Still record for transcript (with filtered flag)
                        if len(text) >= 3:
                            self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                        continue
                    # 🔥 BUILD 170.3: REMOVED short text rejection - Hebrew can have short valid responses
                    
                    # 🔥 BUILD 194: DURATION/LENGTH RATIO CHECK
                    # Background noise gets transcribed as short Hebrew words like "כן"
                    # Example: 14 seconds audio → "כן." (2 chars) = SUSPICIOUS!
                    # Real "כן" is spoken in ~0.5-1 second, not 14 seconds
                    user_duration = 0
                    if hasattr(self, '_user_speech_start') and self._user_speech_start is not None:
                        user_duration = time.time() - self._user_speech_start
                    
                    text_hebrew_len = len(re.findall(r'[\u0590-\u05FF]', text))
                    suspicious_noise_words = ["כן", "לא", "אה", "אהה", "אמ", "הא", "מה"]
                    text_clean = text.strip().replace(".", "").replace(",", "").replace("!", "").replace("?", "")
                    
                    # Rule 1: Very long duration (>5s) with very short text (<4 Hebrew chars) = noise
                    if user_duration > 5.0 and text_hebrew_len < 4:
                        print(f"🔇 [BUILD 194] ❌ NOISE REJECTED: {user_duration:.1f}s audio → '{text}' ({text_hebrew_len} chars) - ratio too extreme!")
                        if len(text) >= 3:
                            self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                        continue
                    
                    # Rule 2: Long duration (>3s) for single-word suspicious noise words = noise
                    if user_duration > 3.0 and text_clean in suspicious_noise_words:
                        print(f"🔇 [BUILD 194] ❌ NOISE REJECTED: {user_duration:.1f}s audio → '{text}' - single word noise pattern!")
                        if len(text) >= 3:
                            self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                        continue
                    
                    # Rule 3: Long duration (>10s) with short text (<10 chars) = background noise
                    if user_duration > 10.0 and text_hebrew_len < 10:
                        print(f"🔇 [BUILD 194] ❌ NOISE REJECTED: {user_duration:.1f}s audio → '{text}' ({text_hebrew_len} chars) - too short for duration!")
                        if len(text) >= 3:
                            self.conversation_history.append({"speaker": "user", "text": text, "ts": time.time(), "filtered": True})
                        continue
                    
                    # Log when allowed despite being suspicious (for debugging)
                    if user_duration > 2.0 and text_hebrew_len < 5:
                        print(f"⚠️ [BUILD 194] Allowing borderline: {user_duration:.1f}s → '{text}' ({text_hebrew_len} chars)")
                    
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
                    
                    # 🔥 BUILD 186: GENERIC STT VALIDATION - No hardcoded patterns!
                    # Uses linguistic rules from hebrew_stt_validator service
                    natural_elongations = ["אמממ", "אההה", "אממ", "אהה", "מממ", "ווו", "אה", "אם", "אוקי", "היי"]
                    
                    is_gibberish_detected = False
                    if hebrew_chars > 0 and text_stripped not in natural_elongations:
                        # Use the generic Hebrew STT validator (no hardcoded patterns)
                        is_gib, gib_reason, gib_confidence = is_gibberish(text_stripped)
                        if is_gib and gib_confidence >= 0.5:
                            is_gibberish_detected = True
                            print(f"[GIBBERISH] Detected: '{text_stripped}' | Reason: {gib_reason} | Confidence: {gib_confidence:.0%}")
                    
                    # 🛡️ Check if pure English with no Hebrew - likely Whisper hallucination
                    is_pure_english = hebrew_chars == 0 and english_chars >= 2 and len(text) < 20
                    
                    # 🔥 BUILD 170.4: IMPROVED FILTER LOGIC
                    # Priority: Allow Hebrew > Block hallucinations > Block gibberish
                    should_filter = False
                    filter_reason = ""
                    
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
                    MAX_MERGE_LENGTH = 100  # Max characters before forced flush
                    LONG_PAUSE_MS = 1500  # Flush if pause > 1.5 seconds (distinct intents)
                    
                    should_merge = False
                    should_flush = False
                    
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
                    
                    if should_merge:
                        # Merge with previous segment
                        self._stt_merge_buffer.append(text)
                        self._stt_last_segment_ts = now_ms
                        print(f"📝 [SEGMENT MERGE] Buffering: '{text}' (wait for more)")
                        continue  # Wait for more segments
                    
                    # Either first segment or timeout - process now
                    if self._stt_merge_buffer:
                        # Combine buffered segments with current
                        self._stt_merge_buffer.append(text)
                        text = " ".join(self._stt_merge_buffer)
                        print(f"📝 [SEGMENT MERGE] Combined {len(self._stt_merge_buffer)} segments: '{text}'")
                        self._stt_merge_buffer = []
                    
                    self._stt_last_segment_ts = now_ms
                    transcript = text
                    
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
                        
                        # 🔥 BUILD 196.4: DEBUG mode for Calliber (business_id=10)
                        calliber_debug = getattr(self, 'business_id', None) == 10
                        if calliber_debug:
                            print(f"🔍 [DEBUG CALLIBER] USER_UTTERANCE: text='{transcript}' echo_blocked={getattr(self, '_last_echo_blocked', False)}")
                        
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
                        # 🔥 BUILD 194: ONLY set verification_confirmed if pending_confirmation is True!
                        # This prevents false positives when user says "כן" to other questions
                        confirmation_words = [
                            "כן", "נכון", "בדיוק", "כן כן", "yes", "correct", "exactly", 
                            "יופי", "מסכים", "בסדר", "מאה אחוז", "אוקיי", "אוקי", "ok",
                            "בטח", "סבבה", "מעולה", "הכל נכון",
                            "זה נכון", "כן הכל", "כן כן כן", "אישור", "מאשר", "מאשרת",
                            "נכון מאוד", "אכן"
                        ]
                        transcript_lower = transcript.strip().lower()
                        is_confirmation = any(word in transcript_lower for word in confirmation_words)
                        
                        if is_confirmation:
                            # 🔥 BUILD 194: ONLY confirm if we were waiting for confirmation!
                            if getattr(self, 'pending_confirmation', False):
                                print(f"✅ [BUILD 194] User CONFIRMED after verification question - verification_confirmed = True")
                                self.verification_confirmed = True
                                self.pending_confirmation = False  # Reset - confirmation received
                            else:
                                # User said "כן" but we weren't asking for confirmation
                                print(f"⚠️ [BUILD 194] User said '{transcript[:20]}' but no verification question was asked - IGNORED")
                        else:
                            # 🔥 BUILD 194: Any non-confirmation response resets pending_confirmation
                            # This prevents later unrelated "כן" from triggering false confirmation
                            if getattr(self, 'pending_confirmation', False):
                                print(f"🔄 [BUILD 194] Non-confirmation response - resetting pending_confirmation")
                                self.pending_confirmation = False
                        
                        # 🛡️ BUILD 168: If user says correction words, reset verification
                        correction_words = ["לא", "רגע", "שנייה", "לא נכון", "טעות", "תתקן", "לשנות"]
                        if any(word in transcript_lower for word in correction_words):
                            print(f"🔄 [BUILD 168] User wants CORRECTION - resetting verification state")
                            self.verification_confirmed = False
                            # 🔥 FIX: Also reset the prompt flag so we can send a new verification request
                            self._verification_prompt_sent = False
                        
                        # Track conversation
                        self.conversation_history.append({"speaker": "user", "text": transcript, "ts": time.time()})
                        
                        # 🎯 SMART HANGUP: Extract lead fields from user speech as well
                        self._extract_lead_fields_from_ai(transcript)
                        
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
                                    self.closing_sent = True  # 🔥 BUILD 194: Block future transcripts
                                    print(f"🔒 [BUILD 194] Closing message sent - blocking future transcripts")
                                    # 🔥 BUILD 194: Clear audio buffer to stop noise from being transcribed
                                    if self.realtime_client:
                                        asyncio.create_task(self.realtime_client.clear_audio_buffer())
                                        print(f"🔇 [BUILD 194] Cleared audio input buffer")
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
                                    self.closing_sent = True  # 🔥 BUILD 194: Block future transcripts
                                    print(f"🔒 [BUILD 194] Closing message sent - blocking future transcripts")
                                    # 🔥 BUILD 194: Clear audio buffer to stop noise from being transcribed
                                    if self.realtime_client:
                                        asyncio.create_task(self.realtime_client.clear_audio_buffer())
                                        print(f"🔇 [BUILD 194] Cleared audio input buffer")
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
        
        # 🔥 BUILD 194: Block new AI responses after closing (allow closing messages through)
        is_closing_message = "סיים בצורה מנומסת" in message_text or "אישר את הפרטים" in message_text or "להתראות" in message_text
        if getattr(self, 'closing_sent', False) and not is_closing_message:
            print(f"🔒 [BUILD 194] Blocking server event - closing already sent: '{message_text[:50]}...'")
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
            
            # 🔥 BUILD 194: CLOSING FENCE - Never send response.create after closing
            if getattr(self, 'closing_sent', False):
                print(f"🔒 [BUILD 194] Blocking response.create - closing already sent")
                return
            
            # 🔥 BUILD 165: LOOP GUARD - Block if engaged or too many consecutive responses
            # 🔥 BUILD 178: COMPLETELY DISABLED for outbound calls!
            # 🔥 BUILD 182: Also allow appointment-related messages through
            is_outbound = getattr(self, 'call_direction', 'inbound') == 'outbound'
            is_appointment_msg = "appointment" in message_text.lower() or "תור" in message_text or "זמינות" in message_text
            if not is_outbound and not is_appointment_msg:
                # INBOUND only: Check loop guard (unless appointment-related)
                if self._loop_guard_engaged or self._consecutive_ai_responses >= self._max_consecutive_ai_responses:
                    print(f"🛑 [LOOP GUARD] Blocking response.create (engaged={self._loop_guard_engaged}, consecutive={self._consecutive_ai_responses})")
                    return
            
            # 🎯 Thread-safe optimistic lock: Prevent response collision race condition
            if not self.active_response_id and not self.response_pending_event.is_set():
                try:
                    self.response_pending_event.set()  # 🔒 Lock BEFORE sending (thread-safe)
                    await self.realtime_client.send_event({"type": "response.create"})
                    print(f"🎯 [SERVER_EVENT] Triggered response.create (lock will be cleared by response.created)")
                except Exception as send_error:
                    # 🔓 CRITICAL: Clear lock immediately on send failure
                    # Prevents deadlock when network errors occur
                    self.response_pending_event.clear()
                    print(f"❌ [SERVER_EVENT] Send failed, lock cleared: {send_error}")
                    raise  # Re-raise to outer handler
            else:
                print(f"⏸️ [SERVER_EVENT] Skipping response.create - active: {self.active_response_id}, pending: {self.response_pending_event.is_set()}")
            
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
                    
                    result = create_appointment_from_realtime(
                        business_id=self.business_id,
                        customer_phone=customer_phone,
                        customer_name=customer_name,
                        treatment_type="פגישה",
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
                    is_noise = rms < RMS_SILENCE_THRESHOLD and not speech_bypass_active  # 🔥 BUILD 191: 80 RMS = pure noise
                    
                    # 🔥 BUILD 167: MUSIC GATE DISABLED - Hebrew speech was being blocked!
                    # Hebrew has sustained consonant clusters with RMS 200-350 which matched "music" pattern
                    # 🔥 BUILD 191: Noise gate uses RMS_SILENCE_THRESHOLD (80)
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
                                # 🔥 BUILD 191: Lower baseline for normal speech
                                self.vad_threshold = 130.0  # BUILD 191: 130 (was 180) - normal Hebrew speech
                                logger.warning(f"🎛️ [VAD] TIMEOUT - using baseline threshold=130")
                                print(f"🎛️ VAD TIMEOUT - using baseline threshold=130")
                            else:
                                # 🔥 BUILD 191: noise × 3.0, capped at 180 for quiet speakers
                                # Old: noise + 100, cap 200 → Too strict!
                                # New: noise × 3.0, cap 180 → Detects normal speech
                                self.vad_threshold = min(180.0, max(80.0, self.noise_floor * 3.0))
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
                        
                        # 🔥 BUILD 196.1: BYPASS ALL LEGACY GATING - let new pipeline handle everything!
                        # The new AGC/SNR/state machine in _realtime_audio_sender does:
                        # - Bandpass filter (100-3400Hz)
                        # - AGC normalization for quiet/loud callers
                        # - Calibrated noise floor (first 600ms)
                        # - SNR-based state machine (SILENCE→MAYBE→SPEECH)
                        # - Music detection with hysteresis
                        # - Pre-roll buffer for word starts
                        # This is more sophisticated than the old RMS threshold gate!
                        
                        # Just enqueue ALL audio - BUILD 196.1 will filter properly
                        try:
                            if not hasattr(self, '_twilio_audio_chunks_sent'):
                                self._twilio_audio_chunks_sent = 0
                            self._twilio_audio_chunks_sent += 1
                            
                            if self._twilio_audio_chunks_sent <= 3:
                                first5_bytes = ' '.join([f'{b:02x}' for b in mulaw[:5]])
                                print(f"[REALTIME] sending audio TO queue: chunk#{self._twilio_audio_chunks_sent}, μ-law bytes={len(mulaw)}, first5={first5_bytes}, rms={rms:.0f}")
                            
                            self.realtime_audio_in_queue.put_nowait(b64)
                        except queue.Full:
                            pass
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
                        if is_noise:
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
                            
                            # 🔥 BUILD 191: Use MIN_SPEECH_RMS for speech detection (130 for normal speech)
                            speech_threshold = MIN_SPEECH_RMS  # 130 - normal conversation volume
                            
                            # 🔥 BUILD 169: Require 700ms continuous speech (35 frames @ 20ms)
                            # Per architect: Increased from 220ms to prevent AI cutoff on background noise
                            if rms >= speech_threshold:
                                self.barge_in_voice_frames += 1
                                
                                # 🔥 BUILD 195: Update _sustained_speech_confirmed in real-time
                                # Check duration and set flag if >=600ms
                                speech_started_at = getattr(self, '_speech_started_at', 0)
                                if speech_started_at:
                                    speech_duration_ms = (time.time() - speech_started_at) * 1000
                                    if speech_duration_ms >= 600 and not getattr(self, '_sustained_speech_confirmed', False):
                                        self._sustained_speech_confirmed = True
                                        print(f"✅ [BUILD 195] Sustained speech CONFIRMED after {speech_duration_ms:.0f}ms")
                                
                                # 🔥 ARCHITECT FIX: Use BARGE_IN_VOICE_FRAMES constant, not hardcoded 11
                                if self.barge_in_voice_frames >= BARGE_IN_VOICE_FRAMES:
                                    # 🔥 BUILD 195: REQUIRE _sustained_speech_confirmed before barge-in
                                    # This ensures we only interrupt AI for REAL speech (600ms+)
                                    if not getattr(self, '_sustained_speech_confirmed', False):
                                        # Not confirmed yet - check duration directly as fallback
                                        if not speech_started_at or (time.time() - speech_started_at) * 1000 < 600:
                                            print(f"🛡️ [BUILD 195] Barge-in BLOCKED - speech not confirmed (sustained_speech_confirmed=False)")
                                            self.barge_in_voice_frames = 0
                                            continue
                                    
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
                                # 🔥 BUILD 195: Also reset sustained speech on silence
                                if getattr(self, '_sustained_speech_confirmed', False):
                                    self._sustained_speech_confirmed = False
                                    self._speech_started_at = 0
                                    print(f"🔄 [BUILD 195] Voice dropped - resetting sustained speech flag")
                    
                    # 🔥 BUILD 165: Calibration already done above (before audio routing)
                    # No duplicate calibration needed here
                    
                    # 🔥 BUILD 191: Voice detection with balanced threshold
                    if self.is_calibrated:
                        is_strong_voice = rms > self.vad_threshold
                    else:
                        # 🔥 BUILD 191: Before calibration - use MIN_SPEECH_RMS (130) baseline
                        is_strong_voice = rms > MIN_SPEECH_RMS
                    
                    # ✅ FIXED: Update last_voice_ts only with VERY strong voice
                    current_time = time.time()
                    # ✅ EXTRA CHECK: Only if RMS is significantly above threshold
                    # 🔥 BUILD 191: Default to MIN_SPEECH_RMS (130) if vad_threshold not set
                    if is_strong_voice and rms > (getattr(self, 'vad_threshold', MIN_SPEECH_RMS) * 1.2):
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
        # 🚀 REALTIME API: Skip Google STT/TTS - OpenAI handles everything
        # 🔥 BUILD 196.2 FIX: We need to trigger response.create if server_vad didn't!
        if USE_REALTIME_API:
            print(f"⏭️ [REALTIME] END OF UTTERANCE detected - triggering AI response")
            # Reset buffer and state
            if hasattr(self, 'buf'):
                self.buf.clear()
            self.processing = False
            self.state = STATE_LISTEN
            
            # 🔥 CRITICAL FIX: Send response.create to OpenAI!
            # Server-side VAD may not have detected end-of-speech because we filtered audio
            # So we manually trigger the response here
            if hasattr(self, 'realtime_text_input_queue'):
                try:
                    # Use special command to trigger response.create
                    self.realtime_text_input_queue.put("[TRIGGER_RESPONSE]")
                    print(f"✅ [REALTIME] response.create triggered via queue")
                except Exception as e:
                    print(f"⚠️ [REALTIME] Failed to trigger response: {e}")
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
                emergency_response = "מצטערת, לא שמעתי טוב בגלל החיבור. בואו נתחיל מחדש - איזה סוג נכס אתה מחפש ובאיזה אזור?"
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
            
            # 🔥 BUILD 191: BALANCED noise gate for Whisper - uses global constants
            if max_amplitude < 150 or rms < MIN_SPEECH_RMS:  # 🔥 BUILD 191: Allow quieter speech
                print(f"🚫 WHISPER_BLOCKED: Audio too weak (amp={max_amplitude}<150, rms={rms}<{MIN_SPEECH_RMS})")
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
            # 🔥 BUILD 194: Set closing fence when entering CLOSING
            if not getattr(self, 'closing_sent', False):
                self.closing_sent = True
                print(f"🔒 [BUILD 194] Closing state - blocking future transcripts")
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
        """
        try:
            while self.call_state == CallState.ACTIVE and not self.hangup_triggered:
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
                # Skip if call is ending
                if self.call_state in (CallState.CLOSING, CallState.ENDED):
                    break
                
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
                        # 🔥 BUILD 194: Set closing fence
                        if not getattr(self, 'closing_sent', False):
                            self.closing_sent = True
                            print(f"🔒 [BUILD 194] Silence closing - blocking future transcripts")
                        
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
        """Send a gentle 'are you there?' prompt to the AI."""
        try:
            # 🔥 BUILD 172 FIX: If we collected fields but not confirmed, ask for confirmation again
            fields_collected = self._check_lead_captured() if hasattr(self, '_check_lead_captured') else False
            if fields_collected and not self.verification_confirmed:
                warning_prompt = "[SYSTEM] פרטים נאספו אבל הלקוח לא אישר. שאל: 'אתה עדיין שם? רק רציתי לוודא - הפרטים שמסרת נכונים?'"
            else:
                warning_prompt = "[SYSTEM] User has been silent. Gently ask if they are still there: 'אתה עדיין איתי?'"
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
        """
        # 🔥 BUILD 194: CLOSING FENCE - Never send response.create after closing
        if getattr(self, 'closing_sent', False):
            print(f"🔒 [BUILD 194] Blocking _send_text_to_ai - closing already sent")
            return
            
        try:
            if hasattr(self, 'openai_ws') and self.openai_ws:
                msg = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}]
                    }
                }
                await self.openai_ws.send(json.dumps(msg))
                
                # Trigger response
                await self.openai_ws.send(json.dumps({"type": "response.create"}))
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

    def _extract_lead_fields_from_ai(self, ai_transcript: str):
        """
        🎯 SMART HANGUP: Extract lead fields from AI confirmation patterns
        
        Parses AI responses to identify confirmed information:
        - "אתה מתל אביב" → city=תל אביב
        - "שירות ניקיון" → service_type=ניקיון
        - "תקציב של X שקל" → budget=X
        
        Args:
            ai_transcript: The AI's transcribed speech
        """
        import re
        
        text = ai_transcript.strip()
        if not text or len(text) < 5:
            return
        
        # Get required fields to know what we're looking for
        required_fields = getattr(self, 'required_lead_fields', [])
        if not required_fields:
            return
        
        # 🏙️ CITY EXTRACTION: Use 3-layer validation system
        # 🔥 BUILD 185: Phonetic validator + Consistency filter + RapidFuzz
        if 'city' in required_fields:
            try:
                from server.services.city_normalizer import normalize_city, get_all_city_names
                from server.services.phonetic_validator import (
                    validate_hebrew_word, phonetic_similarity, normalize_for_comparison
                )
                
                # 🔒 LAYER 3: Check if city is already locked by consistency filter
                if self.stt_consistency_filter.is_city_locked():
                    locked_city = self.stt_consistency_filter.locked_city
                    print(f"🔒 [CITY] Already locked to '{locked_city}' - ignoring new input")
                else:
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
                    words = text_normalized.split()
                    for i in range(len(words)):
                        for j in range(i+1, min(i+4, len(words)+1)):
                            candidate = ' '.join(words[i:j])
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
                        phonetic_result = validate_hebrew_word(
                            candidate, all_cities,
                            auto_accept_threshold=93.0,
                            confirm_threshold=85.0,
                            reject_threshold=85.0
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
                            # Below 85% - ask user to repeat
                            self._update_lead_capture_state('city_needs_retry', True)
                            print(f"❌ [CITY] Rejected '{raw_city}' (confidence={best_result.confidence:.0f}%) - ask to repeat")
                        elif best_result.needs_confirmation:
                            # 85-92% - needs confirmation
                            canonical = normalize_city(best_result.best_match or raw_city).canonical or raw_city
                            self._update_lead_capture_state('city', canonical)
                            self._update_lead_capture_state('raw_city', raw_city)
                            self._update_lead_capture_state('city_confidence', best_result.confidence)
                            self._update_lead_capture_state('city_needs_confirmation', True)
                            print(f"⚠️ [CITY] Needs confirmation: '{canonical}' (confidence={best_result.confidence:.0f}%)")
                        else:
                            # ≥93% - auto-accept
                            canonical = normalize_city(best_result.best_match or raw_city).canonical or raw_city
                            self._update_lead_capture_state('city', canonical)
                            self._update_lead_capture_state('raw_city', raw_city)
                            self._update_lead_capture_state('city_confidence', best_result.confidence)
                            print(f"✅ [CITY] Auto-accepted: '{canonical}' (confidence={best_result.confidence:.0f}%)")
                        
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
        
        # 🔥 BUILD 196.4: DEBUG mode for Calliber (business_id=10)
        calliber_debug = getattr(self, 'business_id', None) == 10
        if calliber_debug:
            source = "user_input" if getattr(self, '_last_update_source', '') == 'user' else "ai_confirmation"
            print(f"🔍 [DEBUG CALLIBER] LEAD_STATE_UPDATE: {field}={value} source={source}")
        
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
    
    def _analyze_lead_completeness(self) -> dict:
        """BUILD 186: ניתוח השלמת מידע ליד לתיאום פגישה - 100% DYNAMIC!"""
        collected_info = {
            'area': False,
            'property_type': False, 
            'budget': False,
            'timing': False,
            'contact': False
        }
        
        meeting_ready = False
        
        # בדוק היסטוריה לאיסוף מידע
        if hasattr(self, 'conversation_history') and self.conversation_history:
            full_conversation = ' '.join([turn['user'] + ' ' + turn['bot'] for turn in self.conversation_history])
            
            # 🔥 BUILD 186: זיהוי אזור DYNAMIC from JSON!
            try:
                from server.services.appointment_parser import _load_dynamic_area_patterns
                area_patterns = _load_dynamic_area_patterns()
                if any(area.lower() in full_conversation.lower() for area in area_patterns.keys()):
                    collected_info['area'] = True
            except:
                pass
            
            # זיהוי סוג נכס
            if any(prop_type in full_conversation for prop_type in ['דירה', 'חדרים', '2 חדרים', '3 חדרים', '4 חדרים', 'משרד', 'דופלקס']):
                collected_info['property_type'] = True
            
            # זיהוי תקציב
            if any(budget_word in full_conversation for budget_word in ['שקל', 'אלף', 'תקציב', '₪', 'אלפים', 'מיליון']):
                collected_info['budget'] = True
            
            # זיהוי זמן כניסה
            if any(timing in full_conversation for timing in ['מיידי', 'דחוף', 'חודש', 'שבועיים', 'בקרוב', 'עכשיו']):
                collected_info['timing'] = True
            
            # זיהוי פרטי קשר
            if any(contact in full_conversation for contact in ['טלפון', 'וואטסאפ', 'נייד', 'מספר', 'פרטים']):
                collected_info['contact'] = True
        
        # ספירת מידע שנאסף
        completed_fields = sum(collected_info.values())
        
        # ✅ FIX: תיאום פגישה אם יש לפחות 3 שדות (אזור + סוג נכס + טלפון)
        # לא צריך תקציב ו-timing בהכרח!
        meeting_ready = completed_fields >= 3
        
        # יצירת סיכום
        summary_parts = []
        if collected_info['area']: summary_parts.append('אזור')
        if collected_info['property_type']: summary_parts.append('סוג נכס')
        if collected_info['budget']: summary_parts.append('תקציב')
        if collected_info['timing']: summary_parts.append('זמן')
        if collected_info['contact']: summary_parts.append('קשר')
        
        summary = f"{len(summary_parts)}/5 שדות: {', '.join(summary_parts) if summary_parts else 'אין'}"
        
        # הודעה לתיאום פגישה או הצגת אופציות
        meeting_prompt = ""
        if meeting_ready:
            meeting_prompt = f"""
זמן לתיאום פגישה! יש מספיק מידע ({completed_fields}/5 שדות).

**חשוב**: כשהלקוח מסכים לזמן ספציפי (לדוגמה "מחר ב-10" או "יום רביעי בערב"):
1. חזור על הזמן המדויק שסוכם: "מצוין! נקבע פגישה ל[יום] בשעה [שעה מדויקת]"
2. תן סיכום קצר: "נפגש ב[מיקום/נכס] ונראה [פרטי הנכס]"
3. אשר: "אראה אותך ב[תאריך ושעה מדויקים]!"

הצע 2-3 אפשרויות זמן ספציפיות, שמע מה הלקוח בוחר, וחזור על הזמן המדויק שהוסכם."""
        elif completed_fields == 3:
            meeting_prompt = """
יש מידע בסיסי טוב! עכשיו תן דוגמה אחת ספציפית מתאימה ושאל שאלה ממוקדת לפני קביעת פגישה."""
        else:
            missing = 4 - completed_fields
            meeting_prompt = f"צריך עוד {missing} שדות מידע לפני הצגת אופציות. המשך שיחה טבעית ותן פרטים נוספים על השוק והאזור."
        
        return {
            'collected': collected_info,
            'completed_count': completed_fields,
            'meeting_ready': meeting_ready,
            'summary': summary,
            'meeting_prompt': meeting_prompt
        }
    
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
                        
                        # 🔥 BUILD 193: Check if user actually spoke before building summary
                        # Use user_speech_seen flag as PRIMARY check (set on speech_started event)
                        user_speech_detected = getattr(self, 'user_speech_seen', False)
                        user_content_length = 0
                        has_filtered_transcripts = False
                        
                        if hasattr(self, 'conversation_history') and self.conversation_history:
                            for turn in self.conversation_history:
                                speaker = turn.get('speaker', '')
                                text = turn.get('text', '') or turn.get('user', '')
                                is_filtered = turn.get('filtered', False)
                                
                                # 🔥 BUILD 193: Include filtered transcripts in length calculation
                                # They were real speech even if rejected by cooldown
                                if speaker == 'user' or 'user' in turn:
                                    content = text.strip() if text else ""
                                    if is_filtered:
                                        has_filtered_transcripts = True
                                        user_content_length += len(content)  # Count filtered too!
                                    else:
                                        # Filter out noise
                                        noise_patterns = ['...', '(שקט)', '(silence)', '(noise)']
                                        if content and len(content) > 2:
                                            is_noise = any(n in content.lower() for n in noise_patterns)
                                            if not is_noise:
                                                user_content_length += len(content)
                        
                        # 🔥 BUILD 193: user_speech_seen is PRIMARY indicator
                        # If user spoke (detected via speech_started event), ALWAYS generate summary
                        # Only skip if user NEVER spoke (no speech_started event received)
                        if not user_speech_detected:
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
                            # 🔥 BUILD 193: Include filtered transcripts too (they were real speech)
                            conv_lines = []
                            for turn in self.conversation_history:
                                if 'speaker' in turn and 'text' in turn:
                                    # New Realtime API format
                                    speaker_label = "לקוח" if turn['speaker'] == 'user' else "עוזר"
                                    is_filtered = turn.get('filtered', False)
                                    text = turn['text']
                                    if is_filtered:
                                        conv_lines.append(f"{speaker_label}: {text} (audio unclear)")
                                    else:
                                        conv_lines.append(f"{speaker_label}: {text}")
                                elif 'user' in turn and 'bot' in turn:
                                    # Old Google STT/TTS format
                                    conv_lines.append(f"לקוח: {turn['user']}\nעוזר: {turn['bot']}")
                            full_conversation = "\n".join(conv_lines)
                        
                        # 🔥 BUILD 193: If user spoke but no transcription, create minimal record
                        if not full_conversation and user_speech_detected:
                            print(f"📊 [FINALIZE] User spoke but no clear transcription - creating minimal record")
                            call_log.status = "completed"
                            call_log.transcription = "(שיחה עם דיבור לקוח - תמליל לא נקלט)"
                            call_log.summary = "הלקוח דיבר אך התמליל לא נקלט בבירור. יש לחזור ללקוח."
                            call_log.ai_summary = ""
                            db.session.commit()
                            print(f"✅ CALL FINALIZED (unclear speech): {self.call_sid}")
                            return
                        
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