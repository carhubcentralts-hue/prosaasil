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

# ⚡ STREAMING STT: דיפולט מופעל בקוד, כדי שלא ניפול לסינגל-ריקווסט אם ENV לא נטען
USE_STREAMING_STT = True
if os.getenv("ENABLE_STREAMING_STT", "").lower() in ("false", "0", "no"):
    USE_STREAMING_STT = False

# 🎯 BARGE-IN: Allow users to interrupt AI mid-sentence
# Enabled by default with smart state tracking (is_ai_speaking + has_pending_ai_response)
ENABLE_BARGE_IN = os.getenv("ENABLE_BARGE_IN", "true").lower() in ("true", "1", "yes")

# 🚀 REALTIME API MODE - OpenAI Realtime API for phone calls
# When enabled, phone calls use OpenAI Realtime API instead of Google STT/TTS
# WhatsApp continues to use AgentKit (not affected by this flag)
# ✅ FIX: Default to TRUE - this is the main feature, should be enabled by default
USE_REALTIME_API = os.getenv("USE_REALTIME_API", "true").lower() in ("true", "1", "yes")

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
# ⚡ BUILD 164B: BALANCED NOISE FILTERING - Filter noise but allow quiet speech
MIN_UTT_SEC = float(os.getenv("MIN_UTT_SEC", "0.6"))        # ⚡ 0.6s - מאפשר תגובות קצרות כמו "כן"
MAX_UTT_SEC = float(os.getenv("MAX_UTT_SEC", "12.0"))       # ✅ 12.0s - זמן מספיק לתיאור נכסים מפורט
VAD_RMS = int(os.getenv("VAD_RMS", "80"))                   # 🔥 BUILD 170.3: 80 - lower threshold for quiet Hebrew
# 🔥 BUILD 170.3: LOWERED THRESHOLDS - Allow quiet Hebrew speech through
RMS_SILENCE_THRESHOLD = int(os.getenv("RMS_SILENCE_THRESHOLD", "40"))       # 🔥 BUILD 170.3: 40 (was 120) - only true silence
MIN_SPEECH_RMS = int(os.getenv("MIN_SPEECH_RMS", "60"))                     # 🔥 BUILD 170.3: 60 (was 200) - Hebrew can be quiet
MIN_SPEECH_DURATION_MS = int(os.getenv("MIN_SPEECH_DURATION_MS", "700"))    # 🔥 BUILD 169: 700ms continuous speech for barge-in
NOISE_HOLD_MS = int(os.getenv("NOISE_HOLD_MS", "150"))                      # Grace period for noise tolerance
VAD_HANGOVER_MS = int(os.getenv("VAD_HANGOVER_MS", "150"))  # 🔥 BUILD 164B: 150ms (balanced)
RESP_MIN_DELAY_MS = int(os.getenv("RESP_MIN_DELAY_MS", "50")) # ⚡ SPEED: 50ms במקום 80ms - תגובה מהירה
RESP_MAX_DELAY_MS = int(os.getenv("RESP_MAX_DELAY_MS", "120")) # ⚡ SPEED: 120ms במקום 200ms - פחות המתנה
REPLY_REFRACTORY_MS = int(os.getenv("REPLY_REFRACTORY_MS", "1100")) # ⚡ BUILD 107: 1100ms - קירור מהיר יותר
BARGE_IN_VOICE_FRAMES = int(os.getenv("BARGE_IN_VOICE_FRAMES","35"))  # 🔥 BUILD 169: 35 frames = ≈700ms continuous speech (20ms per frame)

# 🔥 BUILD 169: STT SEGMENT MERGING - Debounce/merge window for user messages
STT_MERGE_WINDOW_MS = int(os.getenv("STT_MERGE_WINDOW_MS", "800"))  # Merge segments within 800ms
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
        # 🔥 BUILD 170.3: LOWERED noise thresholds for Hebrew
        self.noise_floor = 30.0          # 🔥 BUILD 170.3: 30 (was 80) - lower baseline
        self.vad_threshold = MIN_SPEECH_RMS  # 🔥 BUILD 170.3: Now 60 (was 200) - Hebrew can be quiet
        self.is_calibrated = False       # האם כוילרנו את רמת הרעש
        self.calibration_frames = 0      # מונה פריימים לכיול
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
        # 🔥 FIX: Increased to 900 frames (~18s buffer) to prevent drops for long TTS
        self.tx_q = queue.Queue(maxsize=900)  # Support up to 18s TTS without drops
        self.tx_running = False
        self.tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._last_overflow_log = 0.0  # For throttled logging
        
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
        self._realtime_speech_timeout_sec = 5.0  # Auto-clear after 5 seconds if no speech_stopped
        
        # ⚡ STREAMING STT: Will be initialized after business identification (in "start" event)
        
        # 🎯 APPOINTMENT PARSER: DB-based deduplication via CallSession table
        self.call_sid = None  # Will be set from 'start' event
        self.last_nlp_processed_hash = None  # Hash of last processed conversation for NLP dedup
        self.last_nlp_hash_timestamp = 0  # Timestamp when hash was set (for TTL)
        self.nlp_processing_lock = threading.Lock()  # Prevent concurrent NLP runs
        self.nlp_is_processing = False  # 🛡️ BUILD 149: Flag to prevent concurrent NLP threads
        
        # 🔒 Response collision prevention - thread-safe optimistic lock
        self.response_pending_event = threading.Event()  # Thread-safe flag
        
        # 🎯 SMART CALL CONTROL: Call behavior settings (loaded from BusinessSettings)
        self.bot_speaks_first = False  # If True, bot plays greeting before listening
        self.auto_end_after_lead_capture = False  # If True, hang up after lead details collected
        self.auto_end_on_goodbye = False  # If True, hang up when customer says goodbye
        self.lead_captured = False  # Tracks if all required lead info is collected
        self.goodbye_detected = False  # Tracks if goodbye phrase detected
        self.pending_hangup = False  # Signals that call should end after current TTS
        self.hangup_triggered = False  # Prevents multiple hangup attempts
        self.greeting_completed_at = None  # 🔥 PROTECTION: Timestamp when greeting finished
        self.min_call_duration_after_greeting_ms = 3000  # 🔥 PROTECTION: Don't hangup for 3s after greeting
        # 🎯 SMART HANGUP: Configurable call control (loaded from BusinessSettings)
        self.silence_timeout_sec = 15  # Seconds of silence before "are you there?"
        self.silence_max_warnings = 2  # How many warnings before polite hangup
        self.smart_hangup_enabled = True  # AI-driven hangup based on context, not keywords
        self.required_lead_fields = ['name', 'phone']  # Fields that must be collected
        # 🎯 DYNAMIC LEAD CAPTURE STATE: Tracks ALL captured fields from conversation
        # Updated by _update_lead_capture_state() from AI responses and DTMF
        self.lead_capture_state = {}  # e.g., {'name': 'דני', 'city': 'תל אביב', 'service_type': 'ניקיון'}
        
        # 🛡️ BUILD 168: VERIFICATION GATE - Only disconnect after user confirms
        # Set to True when user says confirmation words: "כן", "נכון", "בדיוק", "כן כן"
        self.verification_confirmed = False  # Must be True before AI-triggered hangup is allowed

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
            has_custom_greeting = greeting_text is not None and len(str(greeting_text).strip()) > 0
            
            if has_custom_greeting:
                if DEBUG: print(f"⏱️ [PARALLEL] Using greeting: '{greeting_text[:50]}...'")
            else:
                if DEBUG: print(f"⏱️ [PARALLEL] No custom greeting - AI will improvise (biz='{biz_name}')")
            
            # Build greeting-only prompt with the actual greeting (or improvise instruction)
            if has_custom_greeting:
                greeting_prompt = f"""אתה נציג טלפוני של {biz_name}. עברית בלבד.

🎤 ברכה (אמור בדיוק!):
"{greeting_text}"

חוקים: קצר מאוד (1-2 משפטים). אם הלקוח שותק - שתוק."""
            else:
                # No custom greeting - AI should improvise a brief intro
                greeting_prompt = f"""אתה נציג טלפוני של {biz_name}. עברית בלבד.

🎤 פתיחה: הזדהה בקצרה כנציג של {biz_name} ושאל במה תוכל לעזור.

חוקים: קצר מאוד (1-2 משפטים). אם הלקוח שותק - שתוק."""
            
            t_before_config = time.time()
            logger.info(f"[CALL DEBUG] PHASE 1: Configure with greeting prompt...")
            
            # 🎯 VOICE CONSISTENCY: Set voice once at call start, use same voice throughout
            # Using 'shimmer' - stable voice for Hebrew TTS
            call_voice = "shimmer"
            self._call_voice = call_voice  # Store for session.update reuse
            print(f"🎤 [VOICE] Using voice={call_voice} for entire call (business={self.business_id})")
            
            # 🔥 FIX: Calculate max_tokens based on greeting length
            # Long greetings (14 seconds = ~280 words in Hebrew) need 500+ tokens
            greeting_length = len(greeting_text) if has_custom_greeting else 0
            greeting_max_tokens = max(200, min(600, greeting_length // 2 + 150))  # Scale with greeting length
            print(f"🎤 [GREETING] max_tokens={greeting_max_tokens} for greeting length={greeting_length} chars")
            
            await client.configure_session(
                instructions=greeting_prompt,
                voice=call_voice,
                input_audio_format="g711_ulaw",
                output_audio_format="g711_ulaw",
                vad_threshold=0.6,
                silence_duration_ms=600,
                temperature=0.6,
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
                                prompt = build_prompt(business_id_safe)
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
                        await client.send_event({
                            "type": "session.update",
                            "session": {
                                "instructions": full_prompt,
                                "voice": voice_to_use,  # 🔒 Must re-send voice to lock it
                                "max_response_output_tokens": 300
                            }
                        })
                        print(f"✅ [PHASE 2] Session updated with full prompt: {len(full_prompt)} chars, voice={voice_to_use} locked")
                    else:
                        print(f"⚠️ [PHASE 2] Keeping minimal prompt - full prompt build failed")
                except Exception as e:
                    print(f"⚠️ [PHASE 2] Session update error: {e}")
            
            # Start prompt update in background (non-blocking)
            asyncio.create_task(_update_session_with_full_prompt())
            
            # 📋 CRM: Initialize context in background (non-blocking for voice)
            # This runs in background thread while AI is already speaking
            customer_phone = getattr(self, 'phone_number', None) or getattr(self, 'customer_phone_dtmf', None)
            if customer_phone:
                # 🚀 Run CRM init in background thread to not block audio
                def _init_crm_background():
                    try:
                        app = _get_flask_app()
                        with app.app_context():
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
                            print(f"✅ [CRM] Context ready (background): lead_id={lead_id}")
                    except Exception as e:
                        print(f"⚠️ [CRM] Background init failed: {e}")
                        self.crm_context = None
                threading.Thread(target=_init_crm_background, daemon=True).start()
            else:
                print(f"⚠️ [CRM] No customer phone - skipping lead creation")
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
                    # 🛡️ FIX: PROTECT GREETING - Don't trigger barge-in while greeting is playing!
                    if self.is_playing_greeting:
                        print(f"🛡️ [PROTECT GREETING] Ignoring speech_started - greeting still playing")
                        continue  # Don't process this event at all
                    print(f"🎤 [REALTIME] User started speaking - setting user_has_spoken=True")
                    self.user_has_spoken = True
                    # 🔥 BUILD 166: BYPASS NOISE GATE while OpenAI is processing speech
                    self._realtime_speech_active = True
                    self._realtime_speech_started_ts = time.time()
                    print(f"🎤 [BUILD 166] Noise gate BYPASSED - sending ALL audio to OpenAI")
                
                # 🔥 BUILD 166: Clear speech active flag when speech ends
                if event_type == "input_audio_buffer.speech_stopped":
                    self._realtime_speech_active = False
                    print(f"🎤 [BUILD 166] Speech ended - noise gate RE-ENABLED")
                
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
                
                # ✅ ONLY handle audio.delta - ignore other audio events!
                # 🔥 FIX: Use response.audio_transcript.delta for is_ai_speaking (reliable text-based flag)
                if event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        # 🛑 BUILD 165: LOOP GUARD - DROP all AI audio when engaged
                        if self._loop_guard_engaged:
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
                    
                    # Don't process - would cause duplicate playback
                    # 🎯 Mark AI response complete
                    if self.is_ai_speaking_event.is_set():
                        print(f"🔇 [REALTIME] AI stopped speaking ({event_type})")
                    self.is_ai_speaking_event.clear()  # Thread-safe: AI stopped speaking
                    self.speaking = False  # 🔥 BUILD 165: SYNC with self.speaking flag
                    self.ai_speaking_start_ts = None  # 🔥 FIX: Clear start timestamp
                    
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
                        should_engage_guard = (
                            (self._consecutive_ai_responses >= self._max_consecutive_ai_responses and user_silent_long_time) or
                            (is_repeating and self._consecutive_ai_responses >= 3) or
                            self._mishearing_count >= 3  # 🔥 BUILD 170.3: Back to 3 for less blocking
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
                        # Settings-based hangup should work when enabled, not blocked by verification gate
                        should_hangup = False
                        hangup_reason = ""
                        
                        # 🔥 BUILD 170.5: Respect business settings for automatic hangup
                        # Priority 1: User explicitly said goodbye - always allow
                        if self.goodbye_detected and ai_polite_closing_detected:
                            hangup_reason = "user_goodbye"
                            should_hangup = True
                            print(f"✅ [HANGUP] User said goodbye - allowing hangup")
                        
                        # Priority 2: auto_end_on_goodbye is ON and AI said goodbye
                        elif self.auto_end_on_goodbye and can_detect_goodbye and ai_polite_closing_detected:
                            hangup_reason = "auto_end_on_goodbye"
                            should_hangup = True
                            print(f"✅ [HANGUP] auto_end_on_goodbye=True, AI said goodbye - allowing hangup")
                        
                        # Priority 3: auto_end_after_lead_capture is ON and lead is captured
                        elif self.auto_end_after_lead_capture and self.lead_captured and ai_polite_closing_detected:
                            hangup_reason = "auto_end_after_lead_capture"
                            should_hangup = True
                            print(f"✅ [HANGUP] auto_end_after_lead_capture=True, lead captured - allowing hangup")
                        
                        # Priority 4: Verification confirmed (user confirmed summary)
                        elif self.verification_confirmed and ai_polite_closing_detected:
                            hangup_reason = "verification_confirmed"
                            should_hangup = True
                            print(f"✅ [HANGUP] User confirmed details - allowing hangup")
                        
                        # Log when hangup is blocked
                        elif ai_polite_closing_detected:
                            print(f"🔒 [HANGUP BLOCKED] AI said closing but conditions not met:")
                            print(f"   goodbye_detected={self.goodbye_detected}")
                            print(f"   auto_end_on_goodbye={self.auto_end_on_goodbye}")
                            print(f"   auto_end_after_lead_capture={self.auto_end_after_lead_capture}")
                            print(f"   lead_captured={self.lead_captured}")
                            print(f"   verification_confirmed={self.verification_confirmed}")
                        
                        if should_hangup:
                            self.goodbye_detected = True
                            self.pending_hangup = True
                            print(f"📞 [BUILD 163] Pending hangup set - will disconnect after audio finishes playing")
                        
                        # 🔥 NOTE: Hangup is now triggered in response.audio.done to let audio finish!
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    raw_text = event.get("transcript", "") or ""
                    text = raw_text.strip()
                    
                    # 🔥 BUILD 170.4: Apply Hebrew normalization
                    text = normalize_hebrew_text(text)
                    
                    now_ms = time.time() * 1000
                    
                    # 🔥 BUILD 170.3: RELAXED LOW-RMS GATE - Only reject truly silent transcripts
                    # Hebrew speech can be quiet - use very low threshold (15 RMS)
                    recent_rms = getattr(self, '_recent_audio_rms', 0)
                    ABSOLUTE_SILENCE_RMS = 15  # 🔥 BUILD 170.3: Only reject near-zero RMS
                    
                    # Only filter if RMS is near zero AND text is pure English hallucination
                    if recent_rms < ABSOLUTE_SILENCE_RMS:
                        hebrew_in_text = len(re.findall(r'[\u0590-\u05FF]', text))
                        if hebrew_in_text == 0:  # Pure English from true silence = hallucination
                            print(f"[SILENCE GATE] ❌ REJECTED (RMS={recent_rms:.0f} < {ABSOLUTE_SILENCE_RMS}): '{text}'")
                            continue
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
                    
                    # 🛡️ Block common Whisper hallucinations (pure English from Hebrew audio)
                    hallucination_phrases = [
                        "bye", "bye.", "bye!", "goodbye", "thank you", "thanks", "ok", "okay",
                        "yes", "no", "hello", "hi", "hey", "sure", "right", "yeah", "yep", "nope",
                        "i see", "i know", "got it", "alright", "fine", "good", "great", "mm", "uh",
                        "hmm", "um", "uh huh", "mhm"
                    ]
                    text_lower = text.lower().strip('.!?')
                    is_hallucination = text_lower in hallucination_phrases
                    
                    # 🔥 BUILD 169.1: Improved gibberish detection (architect feedback)
                    # Only flag as gibberish if: 4+ chars of SAME letter AND not a natural elongation
                    # E.g., "אאאא" = gibberish, but "אמממ" = natural filler (allowed)
                    is_gibberish = False
                    natural_elongations = ["אמממ", "אההה", "אממ", "אהה", "מממ", "ווו"]
                    if hebrew_chars > 0 and text_stripped not in natural_elongations:
                        # Only pure repetition of SAME letter (4+ chars)
                        if len(text_stripped) >= 4 and len(set(text_stripped)) == 1:
                            is_gibberish = True
                            print(f"[GIBBERISH] Detected: '{text_stripped}' (single char x{len(text_stripped)})")
                    
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
                    elif has_meaningful_hebrew and not is_gibberish:
                        # ✅ Has Hebrew characters and not gibberish - probably valid
                        should_filter = False
                        print(f"✅ [NOISE FILTER] ALLOWED (has Hebrew): '{text}'")
                    elif is_hallucination:
                        should_filter = True
                        filter_reason = "hallucination"
                    elif is_gibberish:
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
                        
                        # 🛡️ BUILD 168: Detect user confirmation words
                        confirmation_words = ["כן", "נכון", "בדיוק", "כן כן", "yes", "correct", "exactly", "יופי", "מסכים", "בסדר"]
                        transcript_lower = transcript.strip().lower()
                        if any(word in transcript_lower for word in confirmation_words):
                            print(f"✅ [BUILD 168] User CONFIRMED - verification_confirmed = True")
                            self.verification_confirmed = True
                        
                        # 🛡️ BUILD 168: If user says correction words, reset verification
                        correction_words = ["לא", "רגע", "שנייה", "לא נכון", "טעות", "תתקן", "לשנות"]
                        if any(word in transcript_lower for word in correction_words):
                            print(f"🔄 [BUILD 168] User wants CORRECTION - verification_confirmed = False")
                            self.verification_confirmed = False
                        
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
                        
                        # 🎯 BUILD 163: Detect goodbye phrases in user transcript
                        # ONLY "ביי/להתראות" trigger hangup - NOT "אין צורך/לא צריך"
                        # 🔥 PROTECTION: Only detect goodbye if enough time passed since greeting
                        # ONLY applies if greeting was actually played (greeting_completed_at is not None)
                        can_detect_goodbye = True
                        if self.greeting_completed_at is not None:
                            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
                            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                                can_detect_goodbye = False
                                print(f"🛡️ [PROTECTION] Ignoring user goodbye - only {elapsed_ms:.0f}ms since greeting")
                        # Note: If greeting_completed_at is None (no greeting), allow goodbye detection normally
                        
                        if self.auto_end_on_goodbye and not self.pending_hangup and can_detect_goodbye:
                            if self._check_goodbye_phrases(transcript):
                                print(f"👋 [BUILD 163] User said goodbye - sending polite closing instruction to AI")
                                self.goodbye_detected = True
                                # 🔥 FIX: Send explicit instruction to AI to say polite goodbye
                                asyncio.create_task(self._send_server_event_to_ai(
                                    "[SERVER] הלקוח אמר שלום! סיים בצורה מנומסת - אמור 'תודה שהתקשרת, יום נפלא!' או משהו דומה."
                                ))
                                # 🔥 FALLBACK: If AI doesn't say closing phrase within 10s, disconnect anyway
                                asyncio.create_task(self._fallback_hangup_after_timeout(10, "user_goodbye"))
                        
                        # 🎯 BUILD 163: Check if all lead info is captured
                        if self.auto_end_after_lead_capture and not self.pending_hangup and not self.lead_captured:
                            if self._check_lead_captured():
                                print(f"✅ [BUILD 163] Lead fully captured - sending polite closing instruction")
                                self.lead_captured = True
                                # 🔥 FIX: Send instruction to AI to say polite closing, THEN hang up
                                asyncio.create_task(self._send_server_event_to_ai(
                                    "[SERVER] ✅ כל הפרטים נקלטו! סיים את השיחה בצורה מנומסת - הודה ללקוח ואמור להתראות."
                                ))
                                # 🔥 FALLBACK: If AI doesn't say closing phrase within 10s, disconnect anyway
                                asyncio.create_task(self._fallback_hangup_after_timeout(10, "lead_captured"))
                    
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
            
            # 🔥 BUILD 165: LOOP GUARD - Block if engaged or too many consecutive responses
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
            # Customer phone should be available from call context
            customer_phone = crm_context.customer_phone if crm_context else None
            print(f"📝 [FLOW STEP 5] Checking customer info:")
            print(f"📝 [FLOW STEP 5]   - phone from context: {customer_phone}")
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
            
            # 🔥 STRICT SEQUENCING: Ask for name FIRST, then phone (never both!)
            print(f"📝 [FLOW STEP 6] Checking if all data is complete...")
            if not customer_name or not customer_phone:
                # Missing name or phone - ask AI to collect it IN ORDER
                print(f"📝 [FLOW STEP 6] Missing customer info:")
                print(f"📝 [FLOW STEP 6]   - name: {customer_name or 'MISSING!'}")
                print(f"📝 [FLOW STEP 6]   - phone: {customer_phone or 'MISSING!'}")
                
                # Priority 1: Name (ALWAYS ask for name first!)
                if not customer_name:
                    print(f"❌ [FLOW STEP 6] BLOCKED - Need name first! Sending need_name event")
                    await self._send_server_event_to_ai("need_name - שאל את הלקוח: על איזה שם לרשום את התור?")
                    return
                
                # Priority 2: Phone (only after we have name!)
                if not customer_phone:
                    print(f"❌ [FLOW STEP 6] BLOCKED - Need phone! Sending need_phone event")
                    await self._send_server_event_to_ai("need_phone - שאל את הלקוח: אפשר מספר טלפון? תלחץ עכשיו על הספרות בטלפון ותסיים בכפתור סולמית (#)")
                    return
            
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
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(self.business_id)
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
                            
                            # 🔥 CRITICAL: Send appropriate server event based on error type
                            if error_type == "need_phone":
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
                            
                            # 🔥 BUILD 146: Clear pending_slot ONLY after successful appointment creation
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
                        self.tx_q.put_nowait(twilio_frame)
                        self.realtime_tx_frames += 1
                    except queue.Full:
                        pass  # Drop silently if queue full
                    
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
                        
                        # 🔍 DEBUG: Log phone numbers from customParameters
                        print(f"\n📞 START EVENT (customParameters path):")
                        print(f"   customParams.From: {custom_params.get('From')}")
                        print(f"   customParams.CallFrom: {custom_params.get('CallFrom')}")
                        print(f"   ✅ self.phone_number set to: '{self.phone_number}'")
                        print(f"   ✅ self.to_number set to: '{self.to_number}'")
                        
                        # 🎯 DYNAMIC LEAD STATE: Add caller phone to lead capture state
                        if self.phone_number:
                            self._update_lead_capture_state('phone', self.phone_number)
                    else:
                        # Direct format: {"event": "start", "streamSid": "...", "callSid": "..."}
                        self.stream_sid = evt.get("streamSid")
                        self.call_sid = evt.get("callSid")
                        self.phone_number = evt.get("from") or evt.get("phone_number")
                        self.to_number = evt.get("to") or evt.get("called")
                        
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
                    is_noise = rms < RMS_SILENCE_THRESHOLD and not speech_bypass_active  # 120 RMS = pure noise
                    
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
                        
                        # 🔥 BUILD 165: ONLY send audio above noise threshold AND not music!
                        if not is_noise and not is_music:
                            try:
                                # 🔍 DEBUG: Log first few frames from Twilio
                                if not hasattr(self, '_twilio_audio_chunks_sent'):
                                    self._twilio_audio_chunks_sent = 0
                                self._twilio_audio_chunks_sent += 1
                                
                                if self._twilio_audio_chunks_sent <= 3:
                                    first5_bytes = ' '.join([f'{b:02x}' for b in mulaw[:5]])
                                    print(f"[REALTIME] sending audio TO OpenAI: chunk#{self._twilio_audio_chunks_sent}, μ-law bytes={len(mulaw)}, first5={first5_bytes}, rms={rms:.0f}")
                                
                                self.realtime_audio_in_queue.put_nowait(b64)
                            except queue.Full:
                                pass
                        else:
                            # 🔥 Log noise/music rejection for debugging
                            if not hasattr(self, '_noise_reject_count'):
                                self._noise_reject_count = 0
                            self._noise_reject_count += 1
                            # Log every 100 rejected frames
                            if self._noise_reject_count % 100 == 0:
                                reason = "music" if is_music else "noise"
                                print(f"🔇 [AUDIO GATE] Blocked {self._noise_reject_count} {reason} frames (rms={rms:.0f})")
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
        if self._loop_guard_engaged:
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
                        # 🔥 BUILD 134: EXPANDED for accuracy - same as streaming STT
                        "שלום", "היי", "בוקר טוב", "תודה", "תודה רבה", "בבקשה",
                        "כן", "לא", "בסדר", "מעולה", "נהדר", "מצוין", "אוקיי",
                        "דירה", "משרד", "חדרים", "שכירות", "מכירה", "קניה", "שכר",
                        "מטר", "קומה", "מעלית", "חניה", "מרפסת", "ממד", "מחסן",
                        "תל אביב", "ירושלים", "חיפה", "רמת גן", "פתח תקווה", "רמלה", "לוד", "מודיעין",
                        "שקל", "שקלים", "אלף", "אלפים", "מיליון", "תקציב", "מחיר", "נדלן",
                        "תור", "פגישה", "מחר", "מחרתיים", "יום", "שבוע", "חודש",
                        "אחד", "שניים", "שלוש", "ארבע", "חמש", "שש", "עשר", "עשרים"
                    ], boost=20.0)  # 🔥 Increased boost for better accuracy
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
            
            print(f"⚡ ULTRA-FAST: זיהוי עסק + ברכה + הגדרות בשאילתה אחת: to_number={to_number}")
            
            app = _get_flask_app()
            with app.app_context():
                business = None
                
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
                    
                    # 🚀 COMBINED: Load call behavior settings in same DB context (saves ~50ms!)
                    settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
                    if settings:
                        self.bot_speaks_first = getattr(settings, 'bot_speaks_first', False) or False
                        # 🛡️ BUILD 168.5 FIX: Set is_playing_greeting IMMEDIATELY when bot_speaks_first is True
                        # This prevents audio from being sent to OpenAI before the greeting starts
                        if self.bot_speaks_first:
                            self.is_playing_greeting = True
                            print(f"🛡️ [GREETING PROTECT] is_playing_greeting=True (early, blocking audio input)")
                        self.auto_end_after_lead_capture = getattr(settings, 'auto_end_after_lead_capture', False) or False
                        self.auto_end_on_goodbye = getattr(settings, 'auto_end_on_goodbye', False) or False
                        # 🎯 SMART HANGUP: Load configurable call control settings
                        self.silence_timeout_sec = getattr(settings, 'silence_timeout_sec', 15) or 15
                        self.silence_max_warnings = getattr(settings, 'silence_max_warnings', 2) or 2
                        self.smart_hangup_enabled = getattr(settings, 'smart_hangup_enabled', True)
                        if self.smart_hangup_enabled is None:
                            self.smart_hangup_enabled = True
                        # Load required lead fields - JSON column returns list directly
                        required_fields = getattr(settings, 'required_lead_fields', None)
                        if required_fields and isinstance(required_fields, list):
                            self.required_lead_fields = required_fields
                        else:
                            self.required_lead_fields = ['name', 'phone']
                    else:
                        self.bot_speaks_first = False
                        self.auto_end_after_lead_capture = False
                        self.auto_end_on_goodbye = False
                        self.silence_timeout_sec = 15
                        self.silence_max_warnings = 2
                        self.smart_hangup_enabled = True
                        self.required_lead_fields = ['name', 'phone']
                    
                    # 🔥 CRITICAL: Mark settings as loaded to prevent duplicate loading
                    self._call_settings_loaded = True
                    
                    t_end = time.time()
                    print(f"⚡ COMBINED QUERY: biz+greeting+settings in {(t_end-t_start)*1000:.0f}ms")
                    print(f"   bot_speaks_first={self.bot_speaks_first}, auto_end_goodbye={self.auto_end_on_goodbye}")
                    print(f"🔍 [SETTINGS LOADED] required_lead_fields={self.required_lead_fields}")
                    print(f"🔍 [SETTINGS LOADED] smart_hangup_enabled={self.smart_hangup_enabled}")
                    print(f"🔍 [SETTINGS LOADED] _call_settings_loaded=True (prevents duplicate load)")
                    
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

    def _load_call_behavior_settings(self):
        """
        🎯 SMART CALL CONTROL: Load call behavior settings from BusinessSettings
        - bot_speaks_first: Bot plays greeting before listening
        - auto_end_after_lead_capture: Hang up after all lead details collected
        - auto_end_on_goodbye: Hang up when customer says goodbye
        - silence_timeout_sec: Seconds of silence before asking "are you there?"
        - silence_max_warnings: How many silence warnings before polite hangup
        - smart_hangup_enabled: AI-driven hangup based on context, not keywords
        - required_lead_fields: Which fields must be collected before allowing hangup
        
        🔥 BUILD FIX: Uses _call_settings_loaded flag to prevent duplicate loading
        """
        if not self.business_id:
            print(f"⚠️ [SMART CALL] No business_id - using default call behavior settings")
            return
        
        # 🔥 CHECK: Were settings already loaded by _identify_business_and_get_greeting()?
        if getattr(self, '_call_settings_loaded', False):
            print(f"✅ [SMART CALL] Settings already loaded (_call_settings_loaded=True) - skipping duplicate load")
            print(f"   Current: silence_timeout={self.silence_timeout_sec}s, required_fields={self.required_lead_fields}")
            return
        
        try:
            from server.models_sql import BusinessSettings
            import json
            
            app = _get_flask_app()
            with app.app_context():
                settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
                
                if settings:
                    self.bot_speaks_first = getattr(settings, 'bot_speaks_first', False) or False
                    # 🛡️ BUILD 168.5 FIX: Set is_playing_greeting IMMEDIATELY when bot_speaks_first is True
                    if self.bot_speaks_first:
                        self.is_playing_greeting = True
                        print(f"🛡️ [GREETING PROTECT] is_playing_greeting=True (early, blocking audio input)")
                    self.auto_end_after_lead_capture = getattr(settings, 'auto_end_after_lead_capture', False) or False
                    self.auto_end_on_goodbye = getattr(settings, 'auto_end_on_goodbye', False) or False
                    # 🎯 SMART HANGUP: Load configurable call control settings
                    self.silence_timeout_sec = getattr(settings, 'silence_timeout_sec', 15) or 15
                    self.silence_max_warnings = getattr(settings, 'silence_max_warnings', 2) or 2
                    self.smart_hangup_enabled = getattr(settings, 'smart_hangup_enabled', True)
                    if self.smart_hangup_enabled is None:
                        self.smart_hangup_enabled = True
                    # Load required lead fields - JSON column returns list directly
                    required_fields = getattr(settings, 'required_lead_fields', None)
                    if required_fields and isinstance(required_fields, list):
                        self.required_lead_fields = required_fields
                    # 🔥 FIX: Don't overwrite with default if DB has empty list - empty is valid!
                    # Only use default if truly None/missing
                    elif required_fields is None:
                        self.required_lead_fields = ['name', 'phone']
                    # else: keep whatever was loaded before
                    
                    # 🔥 CRITICAL: Mark settings as loaded to prevent future duplicate loading
                    self._call_settings_loaded = True
                    
                    print(f"✅ [SMART CALL] Call behavior loaded for business {self.business_id}:")
                    print(f"   bot_speaks_first={self.bot_speaks_first}")
                    print(f"   auto_end_after_lead_capture={self.auto_end_after_lead_capture}")
                    print(f"   auto_end_on_goodbye={self.auto_end_on_goodbye}")
                    print(f"   silence_timeout={self.silence_timeout_sec}s, max_warnings={self.silence_max_warnings}")
                    print(f"   smart_hangup_enabled={self.smart_hangup_enabled}")
                    print(f"   required_lead_fields={self.required_lead_fields}")
                else:
                    # 🔥 FIX: Only set defaults if values weren't previously loaded
                    print(f"⚠️ [SMART CALL] No BusinessSettings for business {self.business_id}")
                    # Don't overwrite existing values - keep what __init__ set
        except Exception as e:
            print(f"❌ [SMART CALL] Error loading call behavior settings: {e}")
            import traceback
            traceback.print_exc()

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
        
        Args:
            reason: Why the call is being hung up (for logging)
        """
        if self.hangup_triggered:
            print(f"⚠️ [BUILD 163] Hangup already triggered - skipping")
            return
        
        # 🔥🔥 CRITICAL PROTECTION: Don't hangup during greeting
        if self.is_playing_greeting:
            print(f"🛡️ [PROTECTION] BLOCKING hangup - greeting still playing!")
            self.pending_hangup = False  # Clear pending hangup
            return
        
        # 🔥 PROTECTION: Don't hangup while AI is speaking
        if self.is_ai_speaking_event.is_set():
            print(f"🛡️ [PROTECTION] BLOCKING hangup - AI still speaking!")
            # Don't clear pending_hangup - try again later
            return
        
        # 🔥 PROTECTION: Don't hangup if OpenAI audio queue still has content
        openai_queue_size = self.realtime_audio_out_queue.qsize()
        if openai_queue_size > 0:
            print(f"🛡️ [PROTECTION] BLOCKING hangup - {openai_queue_size} frames in OpenAI queue!")
            # Don't clear pending_hangup - try again later
            return
        
        # 🔥 PROTECTION: Don't hangup if Twilio TX queue still has content
        tx_queue_size = self.tx_q.qsize()
        if tx_queue_size > 0:
            print(f"🛡️ [PROTECTION] BLOCKING hangup - {tx_queue_size} frames in Twilio TX queue!")
            # Don't clear pending_hangup - try again later
            return
        
        # 🔥 PROTECTION: Don't hangup within 3 seconds of greeting completion
        # ONLY applies if greeting was actually played (greeting_completed_at is set)
        if self.greeting_completed_at is not None:
            elapsed_ms = (time.time() - self.greeting_completed_at) * 1000
            if elapsed_ms < self.min_call_duration_after_greeting_ms:
                print(f"🛡️ [PROTECTION] BLOCKING hangup - only {elapsed_ms:.0f}ms since greeting (need {self.min_call_duration_after_greeting_ms}ms)")
                self.pending_hangup = False  # Clear pending hangup
                return
        # Note: If greeting_completed_at is None (no greeting was played), allow hangup normally
        
        self.hangup_triggered = True
        
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
        
        # 🏙️ CITY EXTRACTION: Look for city mentions (comprehensive Israeli city list)
        if 'city' in required_fields and 'city' not in self.lead_capture_state:
            # Comprehensive list of Israeli cities and towns
            israeli_cities = [
                # Major cities
                'תל אביב', 'ירושלים', 'חיפה', 'ראשון לציון', 'פתח תקווה', 'אשדוד', 'נתניה',
                'באר שבע', 'בני ברק', 'חולון', 'רמת גן', 'אשקלון', 'רחובות', 'בת ים',
                'הרצליה', 'כפר סבא', 'רעננה', 'לוד', 'נצרת', 'עכו', 'אילת', 'מודיעין',
                # Gush Dan
                'גבעתיים', 'רמת השרון', 'הוד השרון', 'פתח תקוה', 'ראש העין', 'יהוד',
                'אור יהודה', 'קרית אונו', 'גני תקווה', 'רמלה', 'יבנה', 'נס ציונה',
                # Sharon
                'נתניה', 'רעננה', 'כפר סבא', 'הוד השרון', 'הרצליה', 'רמת השרון',
                # South
                'אשקלון', 'אשדוד', 'שדרות', 'נתיבות', 'אופקים', 'דימונה', 'ערד', 'מצפה רמון',
                'קרית גת', 'קרית מלאכי', 'גדרה', 'באר שבע',
                # North
                'חיפה', 'נהריה', 'עכו', 'כרמיאל', 'נצרת', 'עפולה', 'טבריה', 'צפת',
                'קריית שמונה', 'בית שאן', 'מגדל העמק', 'נצרת עילית', 'קריית אתא',
                'קריית ביאליק', 'קריית מוצקין', 'קריית ים', 'טירת כרמל', 'נשר',
                # Jerusalem area
                'ירושלים', 'בית שמש', 'מעלה אדומים', 'גבעת זאב', 'אריאל', 'מודיעין',
                # Other
                'אלעד', 'ביתר עילית', 'מודיעין עילית', 'בית שאן', 'קצרין', 'חריש'
            ]
            
            # Normalize text for matching
            text_normalized = text.replace('-', ' ').replace('־', ' ')
            
            for city in israeli_cities:
                # Check for city name in text (with word boundaries)
                if city in text_normalized:
                    self._update_lead_capture_state('city', city)
                    break
        
        # 🔧 SERVICE_TYPE EXTRACTION: Look for service mentions
        if 'service_type' in required_fields and 'service_type' not in self.lead_capture_state:
            service_indicators = ['שירות', 'טיפול', 'תחום', 'עבודה', 'פרויקט', 'בעיה']
            service_patterns = [
                r'(?:שירות|טיפול|תחום)\s+(?:של\s+)?([א-ת\s]{2,20})',  # "שירות ניקיון"
                r'ב(?:תחום|נושא)\s+(?:של\s+)?([א-ת\s]{2,20})',  # "בתחום השיפוצים"
            ]
            for pattern in service_patterns:
                match = re.search(pattern, text)
                if match:
                    service = match.group(1).strip()
                    if len(service) > 2:
                        self._update_lead_capture_state('service_type', service)
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
        
        # 🔥 FIX: Send DTMF phone as SYSTEM event (not user message) so AI accepts it!
        # AI is configured to reject verbal phone numbers and only accept DTMF keys
        # By sending as system event, we bypass AI's strict "press keys" validation
        
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
        """Simple fallback response when AI service fails"""
        if "שלום" in hebrew_text or "היי" in hebrew_text:
            return "שלום! איך אני יכולה לעזור?"  # ✅ כללי - לא חושף שם עסק
        elif "תודה" in hebrew_text or "ביי" in hebrew_text:
            return "תודה רבה! אני כאן לכל שאלה."
        else:
            return "איזה אזור מעניין אותך?"  # ✅ כללי - לא מדבר על דירות
    
    
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
                    # Only log if queue is getting full (>400 frames = >50%)
                    if queue_size > 400:
                        print(f"[TX] fps={frames_sent_last_sec} q={queue_size}/800", flush=True)
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
        """זיהוי אזור מהטקסט של הלקוח"""
        text = text.lower()
        
        # מרכז הארץ
        if any(word in text for word in ["תל אביב", "דיזנגוף", "פלורנטין", "נווה צדק"]):
            return "תל אביב"
        elif any(word in text for word in ["רמת גן", "גבעתיים", "הבורסה"]):
            return "רמת גן/גבעתיים"
        elif any(word in text for word in ["הרצליה", "פיתוח"]):
            return "הרצליה"
            
        # מרכז ודרום
        elif any(word in text for word in ["רמלה"]):
            return "רמלה"
        elif any(word in text for word in ["לוד"]):
            return "לוד"
        elif any(word in text for word in ["פתח תקווה", "פתח תקוה"]):
            return "פתח תקווה"
        elif any(word in text for word in ["מודיעין"]):
            return "מודיעין"
        elif any(word in text for word in ["רחובות"]):
            return "רחובות"
            
        # אזור ירושלים
        elif any(word in text for word in ["בית שמש"]):
            return "בית שמש"
        elif any(word in text for word in ["מעלה אדומים"]):
            return "מעלה אדומים"
        elif any(word in text for word in ["ירושלים"]):
            return "ירושלים"
            
        return ""  # Return empty string instead of None
    
    def _analyze_lead_completeness(self) -> dict:
        """✅ ניתוח השלמת מידע ליד לתיאום פגישה"""
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
            
            # זיהוי אזור
            if any(area in full_conversation for area in ['תל אביב', 'רמת גן', 'רמלה', 'לוד', 'בית שמש', 'מודיעין', 'פתח תקווה', 'רחובות', 'הרצליה', 'ירושלים']):
                collected_info['area'] = True
            
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
        """✅ סיכום מלא של השיחה בסיום - עדכון call_log וליד + יצירת פגישות"""
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
                        
                        # בנה סיכום מלא
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
                        
                        # צור סיכום AI
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