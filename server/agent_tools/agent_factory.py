"""
Agent Factory - Create and configure AI agents with tools
Integrates with OpenAI Agents SDK for production-ready agent capabilities

🔥 CRITICAL FIX (Phase 2): SINGLETON PATTERN with LOCK
- Agents are created ONCE per business+channel and cached for 30min
- Prevents app crashes from repeated agent initialization
- Thread-safe with Lock to prevent race conditions
"""
import os
from datetime import datetime, timedelta
import pytz
import threading
from typing import Dict, Tuple, Optional

# 🔥 CRITICAL FIX: Import OpenAI Agents SDK directly (server/agents/__init__.py is now empty)
from agents import Agent, ModelSettings
from server.agent_tools.tools_calendar import calendar_find_slots, calendar_create_appointment
from server.agent_tools.tools_leads import leads_upsert, leads_search
from server.agent_tools.tools_whatsapp import whatsapp_send
from server.agent_tools.tools_invoices import invoices_create, payments_link
from server.agent_tools.tools_contracts import contracts_generate_and_send
from server.agent_tools.tools_summarize import summarize_thread
from server.agent_tools.tools_crm_context import (
    find_lead_by_phone, get_lead_context, create_lead_note, update_lead_fields
)
import logging

logger = logging.getLogger(__name__)

# Check if agents are enabled
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "1") == "1"

# 🔥 SINGLETON CACHE: Store agents by (business_id, channel) key
_AGENT_CACHE: Dict[Tuple[int, str], Tuple[Agent, datetime]] = {}
_AGENT_LOCK = threading.Lock()
_CACHE_TTL_MINUTES = 30  # 🔥 FIX: Increased to 30 minutes to maintain conversation context across messages

# 🔥 NEW: Track conversation statistics for debugging
_CONVERSATION_STATS: Dict[str, Dict] = {}
_STATS_LOCK = threading.Lock()

# 🔥 Configuration: Repetitive response detection threshold
MAX_UNIQUE_RESPONSES_THRESHOLD = 2  # If only 1-2 unique responses in last 5 turns, warn about repetition

def get_conversation_stats(conversation_id: str = None) -> Dict:
    """
    🔥 NEW: Get conversation statistics for debugging
    
    Returns:
        Dict with conversation statistics or all stats if conversation_id is None
    """
    with _STATS_LOCK:
        if conversation_id:
            return _CONVERSATION_STATS.get(conversation_id, {})
        return _CONVERSATION_STATS.copy()

def track_conversation_turn(conversation_id: str, message: str, response: str):
    """
    🔥 NEW: Track conversation turns for debugging
    
    This helps identify when conversations lose context or start repeating
    """
    with _STATS_LOCK:
        if conversation_id not in _CONVERSATION_STATS:
            _CONVERSATION_STATS[conversation_id] = {
                'turn_count': 0,
                'last_updated': datetime.now(tz=pytz.UTC),
                'created_at': datetime.now(tz=pytz.UTC),
                'last_message_preview': '',
                'last_response_preview': ''
            }
        
        stats = _CONVERSATION_STATS[conversation_id]
        stats['turn_count'] += 1
        stats['last_updated'] = datetime.now(tz=pytz.UTC)
        stats['last_message_preview'] = message[:50] if message else ''
        stats['last_response_preview'] = response[:50] if response else ''
        
        # Log warning if same response is repeated
        if stats['turn_count'] > 3 and response:
            # Check if this response is very similar to recent ones
            if 'recent_responses' not in stats:
                stats['recent_responses'] = []
            
            stats['recent_responses'].append(response[:100])
            if len(stats['recent_responses']) > 5:
                stats['recent_responses'] = stats['recent_responses'][-5:]
            
            # Check for repeated responses
            if len(set(stats['recent_responses'])) <= MAX_UNIQUE_RESPONSES_THRESHOLD:
                logger.warning(f"⚠️ [CONVERSATION] Possible repetitive responses detected: "
                             f"conversation_id={conversation_id}, turn_count={stats['turn_count']}, "
                             f"unique_responses={len(set(stats['recent_responses']))}")

def clear_conversation_stats(conversation_id: str = None):
    """
    🔥 NEW: Clear conversation statistics
    
    Args:
        conversation_id: Specific conversation to clear, or None to clear all
    """
    with _STATS_LOCK:
        if conversation_id:
            if conversation_id in _CONVERSATION_STATS:
                del _CONVERSATION_STATS[conversation_id]
                logger.info(f"♻️  Cleared stats for conversation: {conversation_id}")
        else:
            _CONVERSATION_STATS.clear()
            logger.info(f"♻️  Cleared all conversation stats")

def invalidate_agent_cache(business_id: int):
    """
    🔥 CRITICAL: Invalidate agent cache for specific business
    Called after prompt updates to ensure new conversations use updated prompts
    """
    with _AGENT_LOCK:
        keys_to_remove = [k for k in _AGENT_CACHE.keys() if k[0] == business_id]
        for key in keys_to_remove:
            del _AGENT_CACHE[key]
            logger.info(f"✅ Agent cache invalidated: business={key[0]}, channel={key[1]}")
        if keys_to_remove:
            logger.info(f"♻️  Cleared {len(keys_to_remove)} cached agents for business {business_id}")
        else:
            logger.info(f"♻️  No cached agents found for business {business_id}")

# 🎯 Model settings for all agents - matching AgentKit best practices
# 🔥 CRITICAL: Use OpenAI with timeout to prevent 10s silence!
from openai import OpenAI as OpenAIClient

# ⚡ PERFORMANCE FIX: 4s timeout + max_retries=1 prevents long silences
_openai_client = OpenAIClient(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=4.0,  # ⚡ 4s timeout (prevents 6-8s hangs!)
    max_retries=1  # ⚡ Fast fail instead of retry loops
)

AGENT_MODEL_SETTINGS = ModelSettings(
    # 🔥 NOTE: ModelSettings is a dataclass - only accepts declared fields!
    # We'll pass the OpenAI client to Runner.run() instead
    temperature=0.3,       # 🔥 FIX: Temperature 0.3 for varied responses while maintaining consistency
    max_tokens=150,        # 🔥 FIX: Increased to 150 tokens (~40 words in Hebrew) to prevent truncated/repetitive responses
    tool_choice="auto",    # 🔥 FIX: Let AI decide when to use tools (was "required" - caused spam!)
    parallel_tool_calls=True  # Enable parallel tool execution for speed
)

# 🔥 Export the client so ai_service.py can pass it to Runner
def get_openai_client():
    """Get the pre-configured OpenAI client with timeout"""
    return _openai_client

def get_or_create_agent(business_id: int, channel: str, business_name: str = "העסק", custom_instructions: str = None) -> Optional[Agent]:
    """
    🔥 SINGLETON PATTERN: Get cached agent or create new one
    
    Thread-safe singleton that caches agents per (business_id, channel).
    Agents live for 30 minutes to preserve conversation context while
    allowing prompt updates to take effect after timeout.
    
    Args:
        business_id: Business ID (required for cache key)
        channel: Channel type ("phone", "whatsapp")
        business_name: Business name for personalized responses
        custom_instructions: Custom instructions from database
    
    Returns:
        Cached or newly created Agent instance
    """
    if not AGENTS_ENABLED:
        logger.warning("Agents are disabled (AGENTS_ENABLED=0)")
        return None
    
    if not business_id:
        logger.error("❌ Cannot create agent without business_id")
        return None
    
    cache_key = (business_id, channel)
    now = datetime.now(tz=pytz.UTC)
    
    # 🔒 THREAD-SAFE: Acquire lock for cache access
    with _AGENT_LOCK:
        # Check if we have a valid cached agent
        if cache_key in _AGENT_CACHE:
            cached_agent, cached_time = _AGENT_CACHE[cache_key]
            age_minutes = (now - cached_time).total_seconds() / 60
            
            if age_minutes < _CACHE_TTL_MINUTES:
                # Using cached agent silently
                return cached_agent
            else:
                # Cache expired, remove it
                del _AGENT_CACHE[cache_key]
        
        # No valid cache - create new agent
        
        try:
            import time
            agent_start = time.time()
            
            # 🔥 CRITICAL FIX: Load DB prompt if not provided
            if not custom_instructions or not isinstance(custom_instructions, str) or not custom_instructions.strip():
                try:
                    from server.models_sql import Business
                    from sqlalchemy import text
                    from server.db import db
                    
                    business = Business.query.filter_by(id=business_id).first()
                    
                    # 🔥 FIX #1: For WhatsApp, prioritize business.whatsapp_system_prompt
                    if channel == "whatsapp" and business and business.whatsapp_system_prompt:
                        custom_instructions = business.whatsapp_system_prompt
                        logger.info(f"✅ Using dedicated WhatsApp prompt for business={business_id}")
                    else:
                        # Fallback to BusinessSettings.ai_prompt (JSON format)
                        # 🔥 BUILD 309: Use raw SQL to avoid ORM column mapping issues
                        # This prevents errors when new columns are added to model but not yet in DB
                        settings_row = None
                        try:
                            result = db.session.execute(text(
                                "SELECT ai_prompt FROM business_settings WHERE tenant_id = :bid LIMIT 1"
                            ), {"bid": business_id})
                            row = result.fetchone()
                            if row:
                                settings_row = {"ai_prompt": row[0]}
                        except Exception as sql_err:
                            logger.warning(f"⚠️ [BUILD 309] Raw SQL fallback for prompt: {sql_err}")
                        
                        if settings_row and settings_row.get("ai_prompt"):
                            import json
                            try:
                                prompt_data = json.loads(settings_row["ai_prompt"])
                                if isinstance(prompt_data, dict):
                                    # Extract channel-specific prompt
                                    if channel == "whatsapp":
                                        custom_instructions = prompt_data.get('whatsapp', '')
                                    else:
                                        custom_instructions = prompt_data.get('calls', '')
                                else:
                                    # Legacy single prompt
                                    custom_instructions = settings_row["ai_prompt"]
                            except json.JSONDecodeError:
                                # Legacy single prompt
                                custom_instructions = settings_row["ai_prompt"]
                        else:
                            logger.warning(f"⚠️ NO SETTINGS or NO AI_PROMPT for business={business_id}! settings_row={settings_row is not None}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load DB prompt for business={business_id}: {e}")
                    custom_instructions = None
            
            new_agent = create_booking_agent(
                business_name=business_name,
                custom_instructions=custom_instructions,
                business_id=business_id,
                channel=channel
            )
            
            agent_creation_time = (time.time() - agent_start) * 1000
            
            if agent_creation_time > 2000:
                logger.warning(f"⚠️  SLOW AGENT CREATION: {agent_creation_time:.0f}ms > 2000ms!")
            
            if new_agent:
                # Cache the new agent
                _AGENT_CACHE[cache_key] = (new_agent, now)
            
            return new_agent
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent for business={business_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

def create_booking_agent(business_name: str = "העסק", custom_instructions: str = None, business_id: int = None, channel: str = "phone") -> Agent:
    """
    Create an agent specialized in appointment booking and customer management
    
    ⚠️ INTERNAL USE: Call get_or_create_agent() instead for singleton behavior
    
    Tools available:
    - calendar.find_slots: Find available appointment times
    - calendar.create_appointment: Book appointments
    - leads.upsert: Create or update customer leads
    - leads.search: Find existing customer records
    - whatsapp.send: Send confirmations and reminders
    
    Args:
        business_name: Name of the business for personalized responses
        custom_instructions: Custom instructions from database (if None, uses default)
        business_id: Business ID
        channel: Channel type ("phone", "whatsapp")
    
    Returns:
        Configured Agent ready to handle booking requests
    """
    if not AGENTS_ENABLED:
        logger.warning("Agents are disabled (AGENTS_ENABLED=0)")
        return None
    
    # 🎯 Create tools with business_id pre-injected
    from agents import function_tool
    from functools import partial
    
    # 🎧 CRM Context-Aware Support: Default to disabled
    customer_service_enabled = False
    
    # If business_id provided, create wrapper tools that inject it
    if business_id:
        # ============================================================================
        # ✅ WhatsApp/AgentKit MUST use the SAME appointment tools as Realtime:
        # - check_availability
        # - schedule_appointment
        # These return structured {success,error_code,user_message,...} and server-side date normalization.
        # ============================================================================
        @function_tool
        def check_availability(date: str, preferred_time: str = "", service_type: str = ""):
            """
            Check available appointment slots for a specific date.

            Args:
                date: Date to check. Accepts YYYY-MM-DD OR Hebrew like 'היום'/'מחר'/'ראשון' etc.
                preferred_time: Optional preferred time (HH:MM or Hebrew like 'שלוש')
                service_type: Optional service type (can affect duration in some businesses)

            Returns:
                dict with:
                - success: bool
                - error_code: optional string
                - user_message: optional string (MUST be sent to the customer verbatim on WhatsApp)
                - normalized_date/date_display_he/weekday_he/slots
            """
            import time as _time
            from datetime import datetime as _dt
            import pytz as _pytz
            from flask import g as _g
            from server.models_sql import BusinessSettings
            from server.policy.business_policy import get_business_policy
            from server.services.hebrew_datetime import (
                resolve_hebrew_date,
                resolve_hebrew_time,
                pick_best_time_candidate,
                auto_correct_iso_year,
            )
            from server.agent_tools.tools_calendar import FindSlotsInput, _calendar_find_slots_impl

            tool_start = _time.time()

            context = getattr(_g, "agent_context", None) or {}

            # ✅ CRITICAL: Only allow in appointment flow (prevents accidental scheduling in sales/service agents).
            try:
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                call_goal = getattr(settings, "call_goal", "lead_only") if settings else "lead_only"
            except Exception:
                call_goal = "lead_only"
            if call_goal != "appointment":
                return {
                    "success": False,
                    "error_code": "appointments_disabled",
                    "user_message": "תיאום פגישות לא זמין כרגע.",
                }

            policy = get_business_policy(business_id, prompt_text=(context.get("business_prompt") or custom_instructions))
            business_tz = _pytz.timezone(policy.tz)

            date_raw = (date or "").strip()
            if not date_raw:
                return {
                    "success": False,
                    "error_code": "missing_date",
                    "user_message": "על איזה תאריך מדובר? למשל היום/מחר/יום ראשון.",
                }

            date_res = resolve_hebrew_date(date_raw, business_tz)
            if not date_res:
                return {
                    "success": False,
                    "error_code": "invalid_date",
                    "user_message": "לא הצלחתי להבין את התאריך. אפשר תאריך אחר? למשל מחר או יום ראשון.",
                }

            normalized_date_iso = date_res.date_iso
            weekday_he = date_res.weekday_he
            date_display_he = date_res.date_display_he

            # 🔥 FIX #1: Auto-correct suspicious ISO year BEFORE past-date guard.
            corrected_iso, corrected, _reason = auto_correct_iso_year(normalized_date_iso, business_tz)
            if corrected:
                corrected_res = resolve_hebrew_date(corrected_iso, business_tz)
                if corrected_res:
                    normalized_date_iso = corrected_res.date_iso
                    weekday_he = corrected_res.weekday_he
                    date_display_he = corrected_res.date_display_he
                else:
                    normalized_date_iso = corrected_iso

            # Past date hard-stop
            today_local = _dt.now(business_tz).date()
            try:
                y, m, d = map(int, normalized_date_iso.split("-"))
                requested_date = _dt(y, m, d, tzinfo=business_tz).date()
            except Exception:
                requested_date = None

            if requested_date and requested_date < today_local:
                return {
                    "success": False,
                    "error_code": "past_date",
                    "normalized_date": normalized_date_iso,
                    "weekday_he": weekday_he,
                    "date_display_he": date_display_he,
                    "user_message": "זה תאריך שכבר עבר. אפשר תאריך חדש? למשל מחר או שבוע הבא.",
                }

            preferred_time_raw = (preferred_time or "").strip()
            preferred_hhmm = None
            if preferred_time_raw:
                time_res = resolve_hebrew_time(preferred_time_raw)
                if time_res and time_res.candidates_hhmm:
                    preferred_hhmm = pick_best_time_candidate(time_res.candidates_hhmm)

            duration_min = policy.slot_size_min
            try:
                result = _calendar_find_slots_impl(
                    FindSlotsInput(
                        business_id=business_id,
                        date_iso=normalized_date_iso,
                        duration_min=duration_min,
                        preferred_time=preferred_hhmm if preferred_hhmm else None,
                    ),
                    context=context,
                )
            except Exception as e:
                logger.warning(f"WHATSAPP_APPT tool=check_availability success=false error_code=calendar_error appointment_id= - err={e}")
                return {
                    "success": False,
                    "error_code": "calendar_error",
                    "user_message": "יש בעיה לבדוק זמינות כרגע. אפשר תאריך אחר או לנסות שוב עוד מעט?",
                }

            slots_display = [s.start_display for s in (result.slots or [])][:3]
            ok = bool(slots_display)
            payload = {
                "success": ok,
                "normalized_date": normalized_date_iso,
                "weekday_he": weekday_he,
                "date_display_he": date_display_he,
                "slots": slots_display,
                "business_hours": getattr(result, "business_hours", "dynamic"),
                "ts": _time.time(),
            }
            if ok:
                logger.info(f"WHATSAPP_APPT tool=check_availability success=true error_code= appointment_id= - date={normalized_date_iso} slots={slots_display[:2]}")
                return payload

            payload.update(
                {
                    "error_code": "no_slots",
                    "user_message": "אין זמנים פנויים בתאריך הזה. אפשר תאריך אחר? למשל מחר או שבוע הבא.",
                }
            )
            logger.info(f"WHATSAPP_APPT tool=check_availability success=false error_code=no_slots appointment_id= - date={normalized_date_iso}")
            return payload

        @function_tool
        def schedule_appointment(
            customer_name: str,
            appointment_date: str,
            appointment_time: str,
            service_type: str = "",
        ):
            """
            Create an appointment ONLY after checking availability.

            Returns:
                dict with:
                - success: bool
                - appointment_id on success
                - error_code + user_message on failure (MUST be sent verbatim on WhatsApp)
            """
            import time as _time
            from datetime import datetime as _dt, timedelta as _td
            import pytz as _pytz
            from flask import g as _g

            from server.models_sql import BusinessSettings
            from server.policy.business_policy import get_business_policy
            from server.services.hebrew_datetime import resolve_hebrew_date, resolve_hebrew_time, auto_correct_iso_year
            from server.agent_tools.tools_calendar import (
                CreateAppointmentInput,
                FindSlotsInput,
                _calendar_find_slots_impl,
                _calendar_create_appointment_impl,
            )

            name = (customer_name or "").strip()
            date_raw = (appointment_date or "").strip()
            time_raw = (appointment_time or "").strip()
            service = (service_type or "").strip() or "Appointment"

            # ✅ CRITICAL: Only allow in appointment flow (prevents accidental booking in other flows).
            try:
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                call_goal = getattr(settings, "call_goal", "lead_only") if settings else "lead_only"
            except Exception:
                call_goal = "lead_only"
            if call_goal != "appointment":
                return {
                    "success": False,
                    "error_code": "appointments_disabled",
                    "user_message": "תיאום פגישות לא זמין כרגע.",
                }

            if not name:
                return {"success": False, "error_code": "missing_name", "user_message": "על איזה שם לרשום את הפגישה?"}
            if not date_raw or not time_raw:
                return {
                    "success": False,
                    "error_code": "missing_datetime",
                    "user_message": "כדי לקבוע תור אני צריכה תאריך ושעה. לאיזה יום ובאיזו שעה?",
                }

            context = getattr(_g, "agent_context", None) or {}
            policy = get_business_policy(business_id, prompt_text=(context.get("business_prompt") or custom_instructions))
            tz = _pytz.timezone(policy.tz)

            date_res = resolve_hebrew_date(date_raw, tz)
            if not date_res:
                return {
                    "success": False,
                    "error_code": "invalid_date",
                    "user_message": "לא הצלחתי להבין את התאריך. אפשר תאריך אחר? למשל מחר או יום ראשון.",
                }
            time_res = resolve_hebrew_time(time_raw)
            if not time_res or not time_res.candidates_hhmm:
                return {
                    "success": False,
                    "error_code": "invalid_time",
                    "user_message": "באיזו שעה? אפשר להגיד למשל 15:00 או ארבע.",
                }

            normalized_date_iso = date_res.date_iso
            weekday_he = date_res.weekday_he
            date_display_he = date_res.date_display_he

            # 🔥 FIX #1: Auto-correct suspicious ISO year BEFORE past-date guard.
            corrected_iso, corrected, _reason = auto_correct_iso_year(normalized_date_iso, tz)
            if corrected:
                corrected_res = resolve_hebrew_date(corrected_iso, tz)
                if corrected_res:
                    normalized_date_iso = corrected_res.date_iso
                    weekday_he = corrected_res.weekday_he
                    date_display_he = corrected_res.date_display_he
                else:
                    normalized_date_iso = corrected_iso

            today_local = _dt.now(tz).date()
            try:
                y, m, d = map(int, normalized_date_iso.split("-"))
                requested_date = _dt(y, m, d, tzinfo=tz).date()
            except Exception:
                requested_date = None
            if requested_date and requested_date < today_local:
                return {
                    "success": False,
                    "error_code": "past_date",
                    "normalized_date": normalized_date_iso,
                    "weekday_he": weekday_he,
                    "date_display_he": date_display_he,
                    "user_message": "זה תאריך שכבר עבר. אפשר תאריך חדש? למשל מחר או שבוע הבא.",
                }

            duration_min = policy.slot_size_min
            chosen_time = None
            alternatives: list[str] = []
            for cand in time_res.candidates_hhmm:
                try:
                    slots_result = _calendar_find_slots_impl(
                        FindSlotsInput(
                            business_id=business_id,
                            date_iso=normalized_date_iso,
                            duration_min=duration_min,
                            preferred_time=cand,
                        ),
                        context=context,
                    )
                    alternatives = [s.start_display for s in (slots_result.slots or [])][:2]
                    if slots_result.slots and any(s.start_display == cand for s in slots_result.slots):
                        chosen_time = cand
                        break
                except Exception:
                    continue

            if not chosen_time:
                logger.info(
                    f"WHATSAPP_APPT tool=schedule_appointment success=false error_code=slot_unavailable appointment_id= - date={normalized_date_iso} requested='{time_raw}' alt={alternatives}"
                )
                return {
                    "success": False,
                    "error_code": "slot_unavailable",
                    "normalized_date": normalized_date_iso,
                    "weekday_he": weekday_he,
                    "date_display_he": date_display_he,
                    "requested_time_raw": time_raw,
                    "alternative_times": alternatives,
                    "user_message": "השעה שביקשת לא פנויה. מתאים לך אחת מהחלופות, או שתרצה שעה אחרת?",
                }

            requested_dt = tz.localize(_dt.strptime(f"{normalized_date_iso} {chosen_time}", "%Y-%m-%d %H:%M"))
            end_dt = requested_dt + _td(minutes=duration_min)

            # Phone source in WhatsApp: prefer whatsapp_from in agent_context
            # (AgentKit context is the metadata source; do NOT ask for DTMF).
            wa_from = (context or {}).get("whatsapp_from") or (context or {}).get("customer_phone") or None
            notes = "Scheduled via WhatsApp. " + (f"WhatsApp from: {wa_from}. " if wa_from else "Phone not collected (policy optional).")

            input_data = CreateAppointmentInput(
                business_id=business_id,
                customer_name=name,
                customer_phone=wa_from,  # _choose_phone will normalize/fallback
                treatment_type=service,
                start_iso=requested_dt.isoformat(),
                end_iso=end_dt.isoformat(),
                notes=notes,
                source="whatsapp",
            )

            result = _calendar_create_appointment_impl(input_data, context={**context, "channel": "whatsapp"}, session=None)

            # Success
            if hasattr(result, "appointment_id"):
                appt_id = result.appointment_id
                logger.info(f"WHATSAPP_APPT tool=schedule_appointment success=true error_code= appointment_id={appt_id}")
                return {
                    "success": True,
                    "appointment_id": appt_id,
                    "normalized_date": normalized_date_iso,
                    "weekday_he": weekday_he,
                    "date_display_he": date_display_he,
                    "time_hhmm": chosen_time,
                    "start_time": requested_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "customer_name": name,
                    "whatsapp_status": getattr(result, "whatsapp_status", "skipped"),
                }

            # Error dict from calendar impl
            if isinstance(result, dict):
                error_code = result.get("error") or result.get("error_code") or "server_error"
                logger.info(f"WHATSAPP_APPT tool=schedule_appointment success=false error_code={error_code} appointment_id=")
                # Map a safe user_message
                user_message = (
                    "יש בעיה לקבוע את התור כרגע. אפשר לנסות שעה אחרת או תאריך אחר?"
                    if error_code not in {"need_phone", "missing_phone"}
                    else "מה המספר שלך?"
                )
                if isinstance(result.get("message"), str) and result.get("message"):
                    # Keep internal message for logs; do not expose raw tech errors.
                    pass
                return {"success": False, "error_code": error_code, "user_message": user_message}

            logger.info("WHATSAPP_APPT tool=schedule_appointment success=false error_code=unexpected_result appointment_id=")
            return {"success": False, "error_code": "unexpected_result", "user_message": "יש בעיה לקבוע את התור כרגע. אפשר לנסות שוב?"}

        # Wrapper for calendar_find_slots
        @function_tool
        def calendar_find_slots_wrapped(date_iso: str, duration_min: int = 60, preferred_time: str = None):
            """
            Find available appointment slots for a specific date
            
            Args:
                date_iso: Date in ISO format (YYYY-MM-DD) like "2025-11-10"
                duration_min: Duration in minutes (default 60)
                preferred_time: Customer's preferred time in HH:MM format (e.g., "17:00"). IMPORTANT: Always send this when customer requests specific time! System returns 2 slots closest to this time.
                
            Returns:
                FindSlotsOutput with list of available slots (max 2, closest to preferred_time if provided)
            """
            try:
                import time
                tool_start = time.time()
                
                logger.info(f"\n🔧 🔧 🔧 TOOL CALLED: calendar_find_slots_wrapped 🔧 🔧 🔧")
                logger.info(f"   📅 date_iso (RAW from Agent)={date_iso}")
                logger.info(f"   ⏱️  duration_min={duration_min}")
                logger.info(f"   🏢 business_id={business_id}")
                
                # 🔥 FIX #1: Auto-correct suspicious ISO year (generic; no hardcoded year).
                from datetime import datetime
                import pytz
                from server.services.hebrew_datetime import auto_correct_iso_year

                corrected_date = date_iso
                try:
                    tz = pytz.timezone("Asia/Jerusalem")
                    corrected_date, corrected, reason = auto_correct_iso_year(date_iso, tz, datetime.now(tz))
                    if corrected:
                        logger.info(f"   🔧 CORRECTED year: {date_iso} → {corrected_date} (reason={reason})")
                except Exception:
                    pass
                
                logger.info(f"   ✅ date_iso (CORRECTED)={corrected_date}")
                logger.info(f"🔧 TOOL CALLED: calendar_find_slots_wrapped")
                logger.info(f"   📅 date_iso: {date_iso} → {corrected_date}")
                logger.info(f"   ⏱️  duration_min={duration_min}")
                logger.info(f"   🏢 business_id={business_id}")
                
                from server.agent_tools.tools_calendar import FindSlotsInput, _calendar_find_slots_impl
                
                # Tools are called from ai_service.py which already has Flask context
                input_data = FindSlotsInput(
                    business_id=business_id,
                    date_iso=corrected_date,  # Use corrected date!
                    duration_min=duration_min,
                    preferred_time=preferred_time  # 🎯 BUILD 117: Send customer's requested time!
                )
                # Call internal implementation function directly
                result = _calendar_find_slots_impl(input_data)
                
                logger.info(f"✅ calendar_find_slots_wrapped RESULT: {len(result.slots)} slots found")
                logger.info(f"✅ calendar_find_slots_wrapped RESULT: {len(result.slots)} slots found")
                if result.slots:
                    slot_times = [s.start_display for s in result.slots[:5]]
                    logger.info(f"   Available times: {', '.join(slot_times)}{'...' if len(result.slots) > 5 else ''}")
                    logger.info(f"   Available times: {', '.join(slot_times)}{'...' if len(result.slots) > 5 else ''}")
                else:
                    logger.warning(f"   ⚠️ NO SLOTS AVAILABLE for {date_iso}")
                    logger.warning(f"   ⚠️ NO SLOTS AVAILABLE for {date_iso}")
                
                # Convert Pydantic model to dict for Agent SDK
                result_dict = result.model_dump()
                
                # 🔥 BUILD 114: HARD LIMIT - Return ONLY 2 slots maximum!
                # Don't rely on LLM to follow instructions - enforce in code!
                original_count = len(result_dict.get('slots', []))
                if original_count > 2:
                    result_dict['slots'] = result_dict['slots'][:2]
                    logger.info(f"🔥 SLOT_LIMIT: Reduced {original_count} slots → 2 (enforced in code)")
                    logger.info(f"🔥 SLOT_LIMIT: Reduced {original_count} slots → 2 slots")
                
                tool_time = (time.time() - tool_start) * 1000
                logger.info(f"⏱️  TOOL_TIMING: calendar_find_slots = {tool_time:.0f}ms")
                logger.info(f"⏱️  TOOL_TIMING: calendar_find_slots = {tool_time:.0f}ms")
                
                if tool_time > 500:
                    logger.warning(f"⚠️  SLOW TOOL: calendar_find_slots took {tool_time:.0f}ms (expected <500ms)")
                    logger.warning(f"SLOW TOOL: calendar_find_slots took {tool_time:.0f}ms")
                
                logger.info(f"📤 Returning dict with {len(result_dict.get('slots', []))} slots")
                return result_dict
            except Exception as e:
                # 🔥 DON'T raise - return controlled error for Agent to handle
                error_msg = str(e)[:120]
                logger.error(f"❌ calendar_find_slots_wrapped FAILED: {error_msg}")
                import traceback
                traceback.print_exc()
                
                # Return structured error instead of raising
                return {
                    "ok": False,
                    "error": "calendar_error",
                    "message": f"לא ניתן למצוא שעות פנויות: {error_msg}",
                    "slots": []
                }
        
        # Wrapper for calendar_create_appointment  
        @function_tool
        def calendar_create_appointment_wrapped(
            treatment_type: str,
            start_iso: str,
            end_iso: str,
            customer_phone: str = "",
            customer_name: str = "",
            notes: str = None
        ):
            """
            Create a new appointment in the calendar
            
            Phone collection:
            - Phone is OPTIONAL by default (caller-id / WhatsApp context may exist).
            - Only require customer_phone if BusinessPolicy.require_phone_before_booking=True.
            
            Args:
                treatment_type: Type of treatment (required)
                start_iso: Start time in ISO format (required)
                end_iso: End time in ISO format (required)
                customer_phone: Customer phone number (optional unless policy requires it)
                customer_name: Customer name (required - collected verbally)
                notes: Additional notes (optional)
            """
            try:
                import time
                tool_start = time.time()
                
                logger.info(f"\n🔧 🔧 🔧 TOOL CALLED: calendar_create_appointment_wrapped 🔧 🔧 🔧")
                logger.info(f"   📅 treatment_type={treatment_type}")
                logger.info(f"   📅 start_iso={start_iso}, end_iso={end_iso}")
                logger.info(f"   📞 customer_phone (from Agent)={customer_phone}")
                logger.info(f"   👤 customer_name (from Agent)={customer_name}")
                logger.info(f"   🏢 business_id={business_id}")
                
                from server.agent_tools.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
                from flask import g
                from server.policy.business_policy import get_business_policy
                
                # Get context and session for _choose_phone
                context = getattr(g, 'agent_context', None)
                session = None  # TODO: pass session if available

                # Load policy (determines whether phone is required)
                policy = get_business_policy(business_id, (context or {}).get("business_prompt") if context else None)
                
                # 🔥 CRITICAL: Validate both NAME and PHONE!
                if not customer_name or customer_name.strip() in ["", "לקוח", "customer"]:
                    error_msg = "missing_name"
                    logger.error(f"❌ calendar_create_appointment_wrapped: {error_msg}")
                    return {
                        "ok": False,
                        "error": "missing_name",
                        "message": error_msg
                    }
                
                # Phone is optional unless policy explicitly requires it
                if policy.require_phone_before_booking and (not customer_phone or len(customer_phone.strip()) < 9):
                    error_msg = "missing_phone"
                    logger.error(f"❌ calendar_create_appointment_wrapped: {error_msg} (policy requires phone)")
                    return {"ok": False, "error": "missing_phone", "message": error_msg}
                
                # 🔥 CRITICAL: Validate date/time to ensure calendar was checked
                from datetime import datetime
                import pytz
                try:
                    tz = pytz.timezone(policy.tz or "Asia/Jerusalem")
                    now = datetime.now(tz)
                    start_dt = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    
                    # Check 1: Not in the past
                    if start_dt < now:
                        error_msg = "לא ניתן לקבוע תור בעבר! בדוק שוב את היומן עם calendar_find_slots"
                        logger.error(f"❌ calendar_create_appointment: Past date detected - {start_iso}")
                        return {"ok": False, "error": "past_date", "message": error_msg}
                    
                    # Check 2: Within reasonable timeframe (not >6 months ahead)
                    six_months = now + timedelta(days=180)
                    if start_dt > six_months:
                        error_msg = "תאריך רחוק מדי! בדוק שהתאריך נכון"
                        logger.error(f"❌ calendar_create_appointment: Date too far - {start_iso}")
                        return {"ok": False, "error": "date_too_far", "message": error_msg}
                    
                    # Check 3: Basic sanity check (no hard business hours - let calendar_find_slots enforce via policy)
                    # Just reject obviously invalid hours like 25:00 or negative hours
                    hour = start_dt.hour
                    if hour < 0 or hour >= 24:
                        error_msg = f"השעה {hour}:00 לא תקינה! השתמש ב-calendar_find_slots למציאת שעות פנויות"
                        logger.error(f"❌ calendar_create_appointment: Invalid hour - {hour}:00")
                        return {"ok": False, "error": "invalid_hour", "message": error_msg}
                    
                    logger.info(f"✅ Time validation passed: {start_iso}")
                except Exception as e:
                    error_msg = f"תאריך/שעה לא תקינים! השתמש ב-calendar_find_slots כדי למצוא זמנים פנויים"
                    logger.error(f"❌ calendar_create_appointment: Invalid date format - {e}")
                    return {"ok": False, "error": "invalid_date", "message": error_msg}
                
                # Build input - _choose_phone will handle phone fallback
                input_data = CreateAppointmentInput(
                    business_id=business_id,
                    customer_name=customer_name,  # Already validated above!
                    customer_phone=customer_phone,  # Can be empty
                    treatment_type=treatment_type,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    notes=notes,
                    source="ai_agent"
                )
                
                logger.info(f"🔧 calendar_create_appointment_wrapped: {customer_name}, phone={customer_phone}, business_id={business_id}")
                
                # Call internal implementation with context/session
                logger.info(f"🚀 CALLING _calendar_create_appointment_impl...")
                result = _calendar_create_appointment_impl(input_data, context=context, session=session)
                logger.info(f"📥 RESULT from _calendar_create_appointment_impl: {result}")
                
                # Check if result is error dict or success object
                if isinstance(result, dict):
                    # Error response from _calendar_create_appointment_impl
                    logger.error(f"❌ Got ERROR dict: {result}")
                    logger.warning(f"❌ calendar_create_appointment_wrapped returned error: {result}")
                    return result
                
                logger.info(f"✅ SUCCESS! Appointment ID: {result.appointment_id}")
                logger.info(f"✅ calendar_create_appointment_wrapped success: appointment_id={result.appointment_id}")
                
                tool_time = (time.time() - tool_start) * 1000
                logger.info(f"⏱️  TOOL_TIMING: calendar_create_appointment = {tool_time:.0f}ms")
                logger.info(f"⏱️  TOOL_TIMING: calendar_create_appointment = {tool_time:.0f}ms")
                
                if tool_time > 1000:
                    logger.warning(f"⚠️  SLOW TOOL: calendar_create_appointment took {tool_time:.0f}ms (expected <1000ms)")
                    logger.warning(f"SLOW TOOL: calendar_create_appointment took {tool_time:.0f}ms")
                
                # Return success response
                success_response = {
                    "ok": True,
                    "appointment_id": result.appointment_id,
                    "status": result.status,
                    "confirmation_message": result.confirmation_message
                }
                logger.info(f"📤 Returning success: {success_response}")
                return success_response
                
            except Exception as e:
                # 🔥 DON'T raise - return controlled error for Agent to handle
                error_msg = str(e)[:120]  # Limit message length
                logger.error(f"❌ calendar_create_appointment_wrapped error: {error_msg}")
                import traceback
                traceback.print_exc()
                
                # Return structured error instead of raising
                return {
                    "ok": False,
                    "error": "validation_error",
                    "message": error_msg
                }
        
        # Wrapper for leads_upsert (simple implementation - creates lead directly)
        @function_tool
        def leads_upsert_wrapped(name: str, phone_e164: str = "", notes: str = None):
            """
            Create or update customer lead
            
            Args:
                name: Customer name (required)
                phone_e164: Customer phone (optional - uses context if not provided)
                notes: Additional notes (optional)
            """
            try:
                from server.models_sql import db, Lead
                from datetime import datetime
                from flask import g
                
                # 🔥 USE PHONE FROM CONTEXT if not provided
                actual_phone = phone_e164
                if not actual_phone or actual_phone in ["", "לא צויין", "unknown", "None"]:
                    if hasattr(g, 'agent_context'):
                        context_phone = g.agent_context.get('customer_phone', '')
                        if context_phone:
                            actual_phone = context_phone
                            logger.info(f"   ✅ leads_upsert using phone from context: {actual_phone}")
                            logger.info(f"   ✅ leads_upsert using phone from context: {actual_phone}")
                
                if not actual_phone:
                    raise ValueError("Cannot create lead without phone number")
                
                logger.info(f"🔧 leads_upsert_wrapped called: {actual_phone}, name={name}, business_id={business_id}")
                
                # Normalize phone to E.164 format
                phone = actual_phone.strip()
                if not phone.startswith('+'):
                    if phone.startswith('0'):
                        phone = '+972' + phone[1:]
                    else:
                        phone = '+972' + phone
                
                # Search for existing lead
                existing_lead = Lead.query.filter_by(
                    tenant_id=business_id,
                    phone_e164=phone
                ).first()
                
                if existing_lead:
                    # Update existing
                    if name:
                        existing_lead.first_name = name
                    if notes:
                        existing_lead.notes = (existing_lead.notes or "") + "\n" + notes
                    existing_lead.last_contact_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"✅ leads_upsert_wrapped updated: lead_id={existing_lead.id}")
                    return {"lead_id": existing_lead.id, "action": "updated", "phone": phone, "name": name or ""}
                else:
                    # Create new
                    lead = Lead(
                        tenant_id=business_id,
                        phone_e164=phone,
                        first_name=name or "Customer",
                        source="ai_agent",
                        status_name="new",
                        notes=notes,
                        last_contact_at=datetime.utcnow()
                    )
                    db.session.add(lead)
                    db.session.commit()
                    logger.info(f"✅ leads_upsert_wrapped created: lead_id={lead.id}")
                    return {"lead_id": lead.id, "action": "created", "phone": phone, "name": name or ""}
                    
            except Exception as e:
                # 🔥 DON'T raise - return controlled error for Agent to handle
                error_msg = str(e)[:120]
                logger.error(f"❌ leads_upsert_wrapped error: {error_msg}")
                db.session.rollback()
                import traceback
                traceback.print_exc()
                
                # Return structured error instead of raising
                return {
                    "ok": False,
                    "error": "lead_error",
                    "message": f"לא ניתן לשמור פרטי לקוח: {error_msg}"
                }
        
        # 🔥 NEW: Business info wrapper - pre-inject business_id
        from server.agent_tools.tools_business import _business_get_info_impl
        
        @function_tool
        def business_get_info():
            """
            Get business contact information and details
            
            Returns business address, phone number, email, and working hours.
            Use this when customer asks for location, address, contact details, or hours.
            """
            return _business_get_info_impl(business_id=business_id)
        
        # 🎧 CRM Context-Aware Support: Create wrapper tools for customer service mode
        # These tools allow AI to read CRM context and create call summaries
        from server.agent_tools.tools_crm_context import (
            FindLeadByPhoneInput, GetLeadContextInput, CreateLeadNoteInput, UpdateLeadFieldsInput,
            find_lead_by_phone as _find_lead_by_phone,
            get_lead_context as _get_lead_context,
            create_lead_note as _create_lead_note,
            update_lead_fields as _update_lead_fields
        )
        
        @function_tool
        def crm_find_lead_by_phone(phone: str):
            """
            Find a lead by phone number in the CRM.
            Use this at the start of a conversation to identify the customer.
            
            Args:
                phone: Customer phone number (any format, will be normalized)
                
            Returns:
                Lead ID and name if found, or indication that this is a new lead
            """
            from server.agent_tools.tools_crm_context import FindLeadByPhoneInput, find_lead_by_phone_impl
            result = find_lead_by_phone_impl(business_id, phone)
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        @function_tool
        def crm_get_lead_context(lead_id: int):
            """
            Get full context for a lead: details, notes, appointments, call history.
            Use this after identifying a lead to understand their history.
            
            Args:
                lead_id: The lead ID to get context for
                
            Returns:
                Lead details, recent notes, upcoming/past appointments
            """
            from server.agent_tools.tools_crm_context import GetLeadContextInput, get_lead_context_impl
            result = get_lead_context_impl(business_id, lead_id)
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        @function_tool
        def crm_create_note(lead_id: int, content: str, note_type: str = "manual"):
            """
            Create a note for a lead during the conversation (not just at the end).
            Use this to document important information as it comes up.
            
            Args:
                lead_id: The lead ID to add the note to
                content: The note content (e.g., "Customer reported issue with product X", "Promised callback on Monday")
                note_type: Type of note - "manual" (default) or "system"
                
            Returns:
                dict: {success: bool, note_id: int, message: str}
            """
            from server.agent_tools.tools_crm_context import CreateLeadNoteInput, create_lead_note
            result = create_lead_note(CreateLeadNoteInput(
                business_id=business_id,
                lead_id=lead_id,
                note_type=note_type,
                content=content
            ))
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        @function_tool
        def crm_create_call_summary(lead_id: int, summary: str, outcome: str = "", next_step: str = ""):
            """
            Create a call summary note for a lead. Call this at the END of every conversation.
            
            Args:
                lead_id: The lead ID to add the note to
                summary: Summary of the conversation (what was discussed, what was agreed)
                outcome: Outcome of the call (e.g., "appointment_set", "info_provided", "callback_needed", "issue_resolved")
                next_step: What needs to happen next (e.g., "Call back tomorrow at 10:00", "Send follow-up email")
                
            Returns:
                dict: {success: bool, note_id: int, message: str}
            """
            from server.agent_tools.tools_crm_context import create_call_summary_note
            structured_data = {}
            if outcome:
                structured_data['outcome'] = outcome
            if next_step:
                structured_data['next_step'] = next_step
            result = create_call_summary_note(
                business_id=business_id,
                lead_id=lead_id,
                content=summary,
                structured_data=structured_data if structured_data else None
            )
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        # Check if customer service mode is enabled for this business
        customer_service_enabled = False
        try:
            from server.models_sql import BusinessSettings
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            customer_service_enabled = getattr(settings, 'enable_customer_service', False) if settings else False
        except Exception as e:
            logger.warning(f"Could not check customer service setting: {e}")
        
        # ✅ RESTORED: AgentKit tools for non-realtime flows (WhatsApp, backend tasks, post-call)
        # IMPORTANT: These tools are used ONLY in AgentKit / non-realtime flows
        # Realtime phone calls use media_ws_ai.py with separate tool policy
        # WhatsApp MUST use check_availability/schedule_appointment (not calendar_* tools)
        if channel == "whatsapp":
            tools_to_use = [
                check_availability,
                schedule_appointment,
                leads_upsert_wrapped,
                leads_search,
                whatsapp_send,
                business_get_info,
            ]
        else:
            tools_to_use = [
                calendar_find_slots_wrapped,
                calendar_create_appointment_wrapped,
                leads_upsert_wrapped,
                leads_search,
                whatsapp_send,
                business_get_info
            ]
        
        # 🎧 CRM Context-Aware Support: Add customer service tools if enabled
        if customer_service_enabled:
            tools_to_use.extend([
                crm_find_lead_by_phone,
                crm_get_lead_context,
                crm_create_note,
                crm_create_call_summary
            ])
            logger.info(f"🎧 Customer service mode ENABLED for business {business_id} - CRM tools added")
        
        # 📦 Assets Library: Add assets tools if enabled for this business
        try:
            from server.agent_tools.tools_assets import is_assets_enabled, assets_search_impl, assets_get_impl, assets_get_media_impl
            if is_assets_enabled(business_id):
                # Create wrapper tools with business_id pre-injected
                @function_tool
                def assets_search(query: str = "", category: str = "", tag: str = "", limit: int = 5):
                    """
                    חיפוש במאגר הפריטים של העסק
                    
                    Args:
                        query: מילות חיפוש (שם, תיאור, תגיות)
                        category: סינון לפי קטגוריה
                        tag: סינון לפי תגית ספציפית
                        limit: מספר תוצאות מקסימלי (ברירת מחדל: 5)
                    
                    Returns:
                        רשימת פריטים עם שם, תיאור קצר, תגיות ו-attachment_id לתמונת קאבר
                    """
                    result = assets_search_impl(business_id, query or None, category or None, tag or None, limit)
                    return result.model_dump() if hasattr(result, 'model_dump') else result
                
                @function_tool
                def assets_get(asset_id: int):
                    """
                    שליפת פרטי פריט מלאים מהמאגר
                    
                    Args:
                        asset_id: מזהה הפריט
                    
                    Returns:
                        פרטי הפריט כולל שם, תיאור, תגיות, שדות מותאמים, ורשימת תמונות עם attachment_id
                    """
                    result = assets_get_impl(business_id, asset_id)
                    return result.model_dump() if hasattr(result, 'model_dump') else result
                
                @function_tool
                def assets_get_media(asset_id: int):
                    """
                    שליפת רשימת תמונות של פריט לשליחה בוואטסאפ
                    
                    Args:
                        asset_id: מזהה הפריט
                    
                    Returns:
                        רשימת attachment_id + role + mime_type לכל תמונה - ניתן לשלוח עם whatsapp_send
                    """
                    result = assets_get_media_impl(business_id, asset_id)
                    return result.model_dump() if hasattr(result, 'model_dump') else result
                
                tools_to_use.extend([assets_search, assets_get, assets_get_media])
                logger.info(f"📦 Assets Library ENABLED for business {business_id} - assets tools added")
        except Exception as e:
            logger.warning(f"⚠️ Could not load assets tools: {e}")
        
        logger.info(f"✅ AgentKit tools RESTORED for business {business_id} (non-realtime flows)")
    else:
        # ✅ RESTORED: AgentKit tools without business_id injection
        # IMPORTANT: These tools are used ONLY in AgentKit / non-realtime flows
        # Realtime phone calls use media_ws_ai.py with separate tool policy
        tools_to_use = [
            calendar_find_slots,
            calendar_create_appointment,
            leads_upsert,
            leads_search,
            whatsapp_send
        ]
        logger.info(f"✅ AgentKit tools RESTORED (non-realtime flows)")
    

    # 🔥 BUILD 135: MINIMAL SYSTEM RULES (Framework only)
    # CRITICAL: System rules should ONLY contain tool usage rules, not business behavior
    
    today_str = datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d %H:%M')
    tomorrow_str = (datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 🔥 CRITICAL FIX: Check call_goal to determine if appointments are needed
    call_goal = "lead_only"  # default
    if business_id:
        try:
            from server.models_sql import BusinessSettings
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            call_goal = getattr(settings, "call_goal", "lead_only") if settings else "lead_only"
        except Exception:
            pass
    
    # 🔥 NEW ARCHITECTURE: Minimal system rules (framework only)
    # No business logic, no conversation scripts, no appointment flows
    # All behavior comes from custom_instructions (DB prompt)
    if channel == "whatsapp":
        # WhatsApp uses the new Prompt Stack architecture
        # Keep ONLY tool safety rules - zero business logic
        system_rules = f"""🔒 FRAMEWORK (Internal Rules):
TODAY: {today_str}

🔧 Tool Safety:
- Never claim you did something unless tool returned success=true
- If tool fails, acknowledge gracefully

📱 Format:
- Short responses (1-2 sentences)
- One question at a time
- Always Hebrew

---
YOUR INSTRUCTIONS:
"""
        logger.info(f"📱 WhatsApp: using MINIMAL framework ({len(system_rules)} chars)")
    else:
        # 🔥 PHONE CHANNEL = Focused rules for voice calls
        system_rules = f"""🔒 FRAMEWORK:
TODAY: {today_str}

🛡️ Tool Safety:
- NEVER say "קבעתי" unless tool returned success=true
- NEVER say "תפוס"/"פנוי" unless you called availability tool THIS turn
- Ask before calling tools - don't guess

📞 Voice Format:
- Short responses
- Suggest max 2 time options (not all slots)
- Complete one action at a time

---
YOUR INSTRUCTIONS:
"""
    
    # 🔥 BUILD 99: Use DB prompt ONLY if it exists (it's the business's custom instructions!)
    if custom_instructions and custom_instructions.strip():
        # DB prompt exists - use it as the MAIN prompt!
        # 🔥 NEW REQUIREMENT: NO length limits - let business prompts be as long as needed
        # Just ensure system_rules are concise and focused
        instructions = system_rules + custom_instructions
        logger.info(f"\n✅ Using DB prompt for {business_name} ({len(custom_instructions)} chars)")
        logger.info(f"   System rules: {len(system_rules)} chars (prepended)")
        logger.info(f"   DB prompt: {len(custom_instructions)} chars")
        logger.info(f"   = Total: {len(instructions)} chars")
        logger.info(f"✅ Using DATABASE prompt for {business_name} (total: {len(instructions)} chars)")
    else:
        # No DB prompt - use minimal fallback IN HEBREW
        fallback_prompt = f"""אתה העוזר הדיגיטלי של {business_name}.

תענה בעברית, תהיה חם ואדיב, ועזור ללקוח בהתאם לצרכיו.
השתמש בכלים הזמינים לך כשצריך.
תשובות קצרות - 2-3 משפטים."""
        
        instructions = system_rules + fallback_prompt
        logger.warning(f"\n⚠️  NO DB prompt - using minimal fallback for {business_name}")
        logger.warning(f"No DATABASE prompt for {business_name} - using minimal fallback")

    # 🎧 CRM Context-Aware Support: Add customer service instructions if enabled
    # Only for INBOUND calls/messages - outbound should not use customer service mode
    if customer_service_enabled:
        customer_service_instructions = """

🎧 מצב שירות לקוחות חכם (פעיל):
==================================
יש לך גישה מלאה לכלי CRM לשירות לקוחות. השתמש בהם באופן פעיל!

⚠️ חשוב מאוד - רק לשיחות/הודעות נכנסות!
אל תשתמש בכלי שירות הלקוחות בשיחות יוצאות (outbound).
כלי ה-CRM מיועדים רק כשלקוח פונה אלינו, לא כשאנחנו פונים אליו.

🔥 תהליך חובה בתחילת כל שיחה נכנסת (MANDATORY):
========================================================
1️⃣ זיהוי לקוח - ALWAYS קרא ל-crm_find_lead_by_phone() בתחילת השיחה
   → זה יזהה את הלקוח לפי מספר הטלפון שלו
   
2️⃣ טעינת הקשר - אם נמצא lead_id, IMMEDIATELY קרא ל-crm_get_lead_context(lead_id)
   → זה יטען הערות, פגישות, והיסטוריית שיחות
   → עשה זאת אוטומטית! אל תחכה שהלקוח ישאל!
   → זה נותן לך הקשר מלא כדי להבין את הבעיה/מצב של הלקוח
   
3️⃣ שימוש בהקשר - השתמש במידע שקיבלת כדי לענות על שאלות הלקוח:
   → אם יש הערות על בעיה - התייחס אליהן
   → אם יש פגישות קרובות - הזכר אותן
   → אם יש היסטוריה רלוונטית - השתמש בה
   → אם לקוח מזכיר מידע חשוב - שמור אותו עם crm_create_note()
   
4️⃣ תיעוד במהלך השיחה - אם לקוח מספר על בעיה/בקשה חשובה:
   → השתמש ב-crm_create_note() כדי לתעד את זה מיד
   → דוגמאות: "לקוח מבקש חזרה ביום שני", "בעיה עם מוצר X", "הבטחנו החזר כספי"
   
5️⃣ סיכום בסיום - ALWAYS קרא ל-crm_create_call_summary() בסיום השיחה
   → תעד מה נדון, מה הוסכם, ומה הצעד הבא

⚠️ כללים קריטיים:
====================
- 🔥 תמיד טען context בתחילת שיחה! זה לא אופציונלי!
- 🔥 אם לקוח שואל על בעיה/נושא - בדוק אם יש עליו הערות ב-CRM
- 🔥 אם יש הערות רלוונטיות - תן להן משקל בתשובה שלך
- 🔥 תעד מידע חשוב במהלך השיחה עם crm_create_note(), אל תחכה לסוף
- המערכת מחזירה 10 הערות אחרונות (תוכן מלא ללא קיצור!)
- 🔥🔥 קרא את כל 10 ההערות! כל הערה היא חלק מההיסטוריה והקשר של הלקוח
- 🔥🔥 ההערה הראשונה ברשימה היא העדכנית ביותר - זו פיסת האמת למידע סותר!
- 🔥🔥 ההערה העדכנית ביותר מסומנת ב-"[הערה עדכנית ביותר - מידע מדויק]" - זה המידע הנכון ביותר למקרה של סתירות
- אם יש סתירה בין הערות (למשל מחיר השתנה) - תמיד האמן להערה העדכנית ביותר
- אבל כל ההערות חשובות! הן מספרות את ההיסטוריה המלאה - אל תתעלם מהן
- אל תמציא מידע! אם משהו לא מופיע בשום הערה - אמור "לא מופיע לי במערכת"
- אם יש סתירה בין דברי הלקוח ל-CRM - ברר בעדינות, אל תתווכח

🛠️ הכלים שברשותך:
==================
1. crm_find_lead_by_phone(phone) - מזהה לקוח לפי טלפון
2. crm_get_lead_context(lead_id) - טוען הקשר מלא (הערות, פגישות, היסטוריה)
3. crm_create_note(lead_id, content) - יוצר הערה במהלך השיחה
4. crm_create_call_summary(lead_id, summary, outcome, next_step) - סיכום בסוף

📋 המידע שאתה מקבל מ-crm_get_lead_context():
==============================================
1. פרטי הליד: שם, טלפון, אימייל, סטטוס, תגיות, שירות מבוקש, עיר
2. 10 הערות אחרונות ממוינות מהחדשה לישנה (תוכן מלא ללא קיצור):
   - ההערה הראשונה ברשימה = העדכנית ביותר = המידע המדויק ביותר!
   - מסוג: call_summary (סיכום AI), customer_service_ai (הערה ידנית לשירות לקוחות), system (מערכת)
3. 3 פגישות קרובות הבאות + 3 פגישות אחרונות שהיו
4. מספר שיחות שהיו עם הלקוח

💡 דוגמאות לשימוש נכון:
========================
✅ דוגמה 1 - לקוח שואל על בעיה כללית (יש הערה במערכת):
   לקוח: "שלום, אני רוצה לברר לגבי הבעיה"
   אתה: [קורא find_lead → מזהה lead_id=123 → קורא get_context → רואה הערה "לקוח מתלונן על איכות השירות"]
   אתה: "שלום! אני רואה שהיה לך נושא עם איכות השירות. בוא נברר את זה ביחד - תספר לי מה קרה?"

✅ דוגמה 2 - לקוח שואל על בעיה ברכב (יש הערה ספציפית):
   לקוח: "שלום, רציתי לברר על הבעיה שיש לי ברכב"
   אתה: [קורא find_lead → מזהה lead_id=456 → קורא get_context → רואה הערה "לקוח דיווח על בעיה במנוע הרכב, צריך טיפול דחוף"]
   אתה: "שלום! אני רואה שדיווחת על בעיה במנוע הרכב שצריך טיפול דחוף. מה המצב? הצלחת לתאם תור למוסך?"

✅ דוגמה 3 - בדיקת פגישה:
   לקוח: "מתי הפגישה שלי?"
   אתה: [יש לך כבר context טעון] → בודק ברשימת appointments
   אתה: "הפגישה שלך קבועה ליום ראשון ב-14:00. צריך לשנות משהו?"
   
✅ דוגמה 4 - תיעוד בעיה חדשה במהלך שיחה:
   לקוח: "המוצר שקניתי לא עובד, אני רוצה החזר כספי"
   אתה: [קורא crm_create_note(lead_id, "לקוח מבקש החזר כספי על מוצר לא תקין")]
   אתה: "מצטער לשמוע! אני מתעד את הבקשה להחזר כספי ומישהו יחזור אליך תוך 24 שעות."

✅ דוגמה 5 - בעיה ברכב עם פרטים נוספים:
   לקוח: "הרכב שלי עושה רעשים מוזרים"
   אתה: [בודק context → רואה הערה קודמת "רכב טויוטה קורולה 2020, דיווח על רעשים מהמנוע"]
   אתה: "אני רואה שכבר דיווחת בעבר על רעשים מהמנוע של הטויוטה קורולה שלך. הרעשים נמשכים?"
   אתה: [קורא crm_create_note(lead_id, "לקוח מאשר שרעשים במנוע ממשיכים, נדרש תיקון דחוף")]

✅ דוגמה 6 - מידע מחיר משתנה (העדף את ההערה העדכנית אבל השתמש בכל ההיסטוריה!):
   לקוח: "מה היה המחיר הקודם של הרכב?"
   אתה: [בודק context → קורא את כל 3 ההערות:
      1. [הערה עדכנית ביותר - מידע מדויק] "המחיר הסופי הוא 1500 שקלים" (18/01/2026 18:58)
      2. "הצפי ליציאה 25.01, חוב 3000 שקלים" (18/01/2026 17:03)  
      3. "חוב 3000 שקלים על הטיפול" (17/01/2026 14:00)]
   אתה: "המחיר הקודם היה 3000 שקלים (לפי ההערות מ-17.01 ו-18.01), והמחיר הסופי המעודכן עכשיו הוא 1500 שקלים (עדכון אחרון מ-18.01 18:58)"
   🔥 שים לב: קראנו את כל ההערות כדי להבין את ההיסטוריה, והעדפנו את ההערה העדכנית ביותר למידע הסופי!

✅ דוגמה 7 - שימוש בהיסטוריה מכמה הערות:
   לקוח: "מה המצב של הרכב שלי?"
   אתה: [בודק context → קורא את כל ההערות ורואה:
      1. [הערה עדכנית ביותר] "הרכב מוכן לאיסוף, נראה מעולה! המחיר 1500 שקלים" (18/01/2026 18:58)
      2. "הרכב במוסך, צפי ליציאה 25.01" (18/01/2026 17:03)
      3. "לקוח מבקש החלפת טמבון קדמי ואחורי" (18/01/2026 18:37)]
   אתה: "שלום! יש לי חדשות טובות - הרכב שלך מוכן לאיסוף! החלפנו את הטמבון הקדמי והאחורי כמו שביקשת, והוא נראה מעולה. המחיר הסופי 1500 שקלים. בהתחלה היה אמור להיות מוכן רק ב-25 בינואר, אבל סיימנו מוקדם יותר!"
   🔥 שים לב: השתמשנו במידע מכל ההערות ביחד - הבקשה להחלפת טמבון, התאריך המקורי, והמצב הסופי!

❌ דוגמה שגויה - התעלמות מהערות ישנות והיסטוריה:
   לקוח: "מה המחיר ומתי הרכב אמור להיות מוכן?"
   אתה: [רואה את ההערות למעלה אבל קורא רק את הראשונה]
   אתה: "המחיר הוא 1500 שקלים"
   ← זה לא מספיק! חייב לקרוא את כל ההערות כדי לענות גם על "מתי מוכן"!
   ← התשובה הנכונה צריכה לכלול: "המחיר הסופי 1500 שקלים והרכב כבר מוכן לאיסוף (במקור היה אמור להיות מוכן רק ב-25.01)"

❌ דוגמה שגויה - חריטוט במקום להגיד "לא יודע":
   לקוח: "מה דגם הרכב שלי?"
   אתה: [בודק את כל ההערות - אין אזכור של דגם הרכב]
   אתה: "זה טויוטה קורולה" 
   ← זה שגוי! לא מופיע דגם הרכב בשום הערה, אסור לחרטט!
   ← התשובה הנכונה: "לא מופיע לי דגם הרכב במערכת, אבל אני יכול לבדוק לך"

❌ דוגמה שגויה - לא טוען context קודם:
   לקוח: "שלום, מה עם הבעיה שדיברנו עליה?"
   אתה: "שלום! איך אני יכול לעזור?"  
   ← זה שגוי! חייב לקרוא find_lead + get_context קודם כדי לדעת על איזו בעיה מדובר!

📝 סיכום שיחה (חובה בסיום!):
==============================
בסיום כל שיחה נכנסת, תמיד קרא ל-crm_create_call_summary():
- סיכום: מה הלקוח רצה ומה דובר
- outcome: התוצאה (למשל: "info_provided", "appointment_set", "issue_resolved", "callback_needed")
- next_step: מה צריך לקרות הלאה (למשל: "חזרה ללקוח מחר", "בדיקת מלאי", "החזר כספי")

🚫 לא להשתמש בכלי CRM כשאנחנו מתקשרים/שולחים הודעה ללקוח (outbound)!
"""
        instructions = instructions + customer_service_instructions
        logger.info(f"🎧 Added customer service instructions for business {business_id}")

    try:
        # DEBUG: Print the actual instructions the agent receives
        logger.info("\n" + "="*80)
        logger.info("📜 AGENT INSTRUCTIONS (first 500 chars):")
        logger.info("="*80)
        logger.info(instructions[:500])
        logger.info("...")
        logger.info("="*80)
        logger.info(f"📅 Today calculated as: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}")
        logger.info(f"📅 Tomorrow calculated as: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}")
        logger.info("="*80 + "\n")
        
        # 🔥 BUILD 115: Dynamic max_tokens per channel
        # Phone/calls: 60 tokens (15 words) - prevents queue overflow
        # WhatsApp: 800 tokens (~200-250 Hebrew words) - allows full detailed responses without truncation
        if channel == "whatsapp":
            model_settings = ModelSettings(
                temperature=0.0,  # 🔥 FIX: Temperature 0.0 for deterministic responses
                max_tokens=800,  # 🔥 WhatsApp: 800 tokens for complete responses without mid-sentence cuts
                tool_choice="auto",
                parallel_tool_calls=True
            )
            logger.info(f"📱 WhatsApp channel: using max_tokens=800")
        else:
            model_settings = AGENT_MODEL_SETTINGS  # Phone: 60 tokens (global default)
            logger.info(f"📞 Phone channel: using max_tokens=60")
        
        # ✅ RESTORED: AgentKit with tools for non-realtime flows
        # IMPORTANT: Realtime phone calls use media_ws_ai.py (not AgentKit)
        agent = Agent(
            name=f"booking_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",  # ⚡ Fast model for real-time conversations
            instructions=instructions,
            tools=tools_to_use,  # ✅ RESTORED: Full tools for AgentKit / non-realtime
            model_settings=model_settings  # ⚡ Channel-specific settings
        )
        
        logger.info(f"✅ Created booking agent for '{business_name}' with 5 tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise


def create_ops_agent(business_name: str = "העסק", business_id: int = None, channel: str = "phone") -> Agent:
    """
    Create an operations agent with ALL tools - AgentKit full implementation
    
    This agent can:
    - Find and book appointments (calendar tools)
    - Create and manage leads (CRM tools)
    - Generate invoices and payment links (billing tools)
    - Create and send contracts (legal tools)
    - Send WhatsApp messages (communication tools)
    - Summarize conversations (analytics tools)
    
    Args:
        business_name: Business name for personalization
        business_id: Business ID (optional, will be injected in context)
        channel: Communication channel (phone/whatsapp/web)
        
    Returns:
        Configured Agent ready for full operations
    """
    if not AGENTS_ENABLED:
        logger.warning("Agents are disabled (AGENTS_ENABLED=0)")
        return None
    
    # Today's date context
    tz = pytz.timezone("Asia/Jerusalem")
    today = datetime.now(tz)
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    
    instructions = f"""אתה סוכן תפעול של {business_name}. תמיד תענה בעברית.

📅 **הקשר תאריכים:**
היום הוא {today.strftime('%Y-%m-%d (%A)')}, השעה הנוכחית: {today.strftime('%H:%M')} (שעון ישראל).
- מחר = {tomorrow.strftime('%Y-%m-%d')}
- מחרתיים = {day_after.strftime('%Y-%m-%d')}

🎯 **היכולות שלך:**

1. **פגישות (כלי לוח שנה):**
   - מצא זמנים פנויים: calendar_find_slots
   - צור פגישות: calendar_create_appointment
   - תמיד בדוק זמינות לפני אישור
   - 🔥 חשוב: כשמציג זמנים, הצע רק 2 אופציות - לא את כולם!
   - דוגמה: "יש פנוי ב-9:00 או 14:00, מה מתאים לך?"
   - לשעות פעילות: השתמש ב-business_get_info()

2. **לידים/CRM (ניהול לקוחות):**
   - צור או עדכן לידים: leads_upsert
   - חפש לקוחות קיימים: leads_search
   - קשר אוטומטית לידים לפגישות

3. **חשבוניות ותשלומים:**
   - Create invoices: invoices_create
   - Generate payment links: payments_link
   - Send invoices via WhatsApp if requested

4. **CONTRACTS:**
   - Generate contracts from templates: contracts_generate_and_send
   - Available templates: treatment_series, rental, purchase
   - Send signature links via WhatsApp

5. **WHATSAPP & BUSINESS INFO:**
   - Get business details: business_get_info (returns address, phone, email, hours)
   - Send messages: whatsapp_send
   - 🔥 CRITICAL RULE: ONLY use whatsapp_send when customer EXPLICITLY requests "שלח לי בווטסאפ" or "תשלח לי את זה"
   - 📍 Location questions: Use business_get_info to fetch address, answer verbally, then ask if they want it via WhatsApp
   - Example: Customer asks "מה הכתובת?" → call business_get_info → "אנחנו ברחוב X. רוצה שאשלח לך בווטסאפ?" → Only if yes: whatsapp_send

6. **SUMMARIES:**
   - Summarize conversations: summarize_thread
   - Extract key information for CRM notes

🚨 **CRITICAL RULES:**

1. **ALWAYS USE TOOLS - NEVER MAKE CLAIMS WITHOUT VERIFICATION:**
   - For availability → MUST call calendar_find_slots first
   - For customer info → call leads_search first
   - Never say "no availability" without checking
   - Never claim "sent" without calling the tool

2. **AUTOMATIC WORKFLOWS (EXECUTE WITHOUT ASKING):**
   - After appointment → ALWAYS call leads_upsert to save customer data
   - Note: WhatsApp confirmations are sent by the SYSTEM automatically (not by you!) for phone appointments
   - For location/payment links/other requests → ALWAYS ask "רוצה שאשלח לך בווטסאפ?" before using whatsapp_send

3. **LEAD-FIRST PRINCIPLE:**
   - Before ANY operation → check leads_search
   - If no lead exists → create with leads_upsert
   - Update lead notes with every interaction

4. **ERROR HANDLING:**
   - If tool returns ok=false: Ask ONE brief clarification in Hebrew, then retry
   - Never expose technical errors - handle gracefully
   - Keep error messages natural and helpful

5. **CONVERSATION FLOW:**
   - Keep responses SHORT (1-2 sentences max)
   - PHONE CALLS: Maximum 15 words per response! Voice is slow - keep it brief!
   - When showing available slots: Suggest ONLY 2-3 best options, not all slots!
   - Never repeat greetings if conversation already started
   - Check message history before responding
   - Execute automation workflows WITHOUT asking permission

6. **CHANNEL-SPECIFIC BEHAVIOR:**
   - Phone: Can request DTMF input (keypad + #), auto-send summary at end
   - WhatsApp: Natural text, confirmations sent automatically
   - Both: Always confirm important details before final action

7. **STAY ON TOPIC:**
   - Follow YOUR CUSTOM INSTRUCTIONS below for conversation style and topic handling
   - If your custom instructions don't specify, focus on business-related topics
   - Examples:
     ✅ GOOD: Appointments, services, location, hours, pricing, payments, contracts
     ❌ BAD: "מה מזג האויר?", "מי ראש הממשלה?", "תכתוב לי שיר", "מה קורה בעולם?"

📋 **AUTOMATION WORKFLOWS (CRITICAL - ALWAYS FOLLOW):**

**1. APPOINTMENT WORKFLOW (STEP-BY-STEP - MUST FOLLOW ORDER!):**

🎯 **CRITICAL: This is a 4-turn conversation - DO NOT skip steps!**

**Appointment Flow Steps:**
→ Collect customer name
→ Collect phone number (via DTMF on phone calls)
→ Ask for preferred date
→ Ask for preferred time
→ Check availability with calendar_find_slots
→ Create appointment with calendar_create_appointment
→ Confirm booking to customer

🎯 **SMART SLOT SELECTION:**
- ALWAYS use preferred_time parameter in calendar_find_slots when customer mentioned time!
- Tool returns 2 slots CLOSEST to preferred_time automatically
- Example: preferred_time="17:00" → returns ['17:00', '16:30'] or ['16:00', '16:30']

**⚠️ CRITICAL RULES:**
- NEVER claim "קבעתי" or "נקבע" without calling calendar_create_appointment!
- NEVER say "שלחתי" or "אשלח" - you CANNOT send WhatsApp messages!
- NEVER say slot is available/occupied without calling calendar_find_slots!
- ALWAYS ask in order: Name → Phone → Date → Time
- ALWAYS check calendar BEFORE confirming appointment!
- Keep each turn under 15 words!
- If you say "קבעתי" you MUST have called calendar_create_appointment tool!


**2. LOCATION/DETAILS REQUEST:**
When customer asks "מה הכתובת" or "איפה אתם":
→ Answer verbally from your prompt (you have the location!)
→ NEVER offer to send via WhatsApp on phone calls - you don't have access to WhatsApp!

**3. PAYMENT LINK REQUEST:**
When customer needs payment link:
→ payments_link(invoice_id=X)
→ Read the link verbally - you CANNOT send WhatsApp messages!

**4. LEAD-FIRST PRINCIPLE:**
BEFORE any appointment/invoice/contract:
→ Check if customer exists: leads_search(phone=customer_phone)
→ If not found: leads_upsert(name=..., phone=..., status="new")
→ Then proceed with the operation

**CRITICAL FOR PHONE CHANNEL:** You do NOT have access to whatsapp_send on phone calls! NEVER promise to send anything!

⚠️ **KEY POINTS:**
- ALWAYS respond in Hebrew (no matter what language the user uses)
- Always verify with tools before confirming
- Keep it short and friendly
- Business hours are checked dynamically - use calendar_find_slots to see available times
- Never mention technical details or tool names
- If unsure → ASK instead of guessing

**CRITICAL: ALL RESPONSES MUST BE IN HEBREW. USE TOOLS FOR EVERYTHING. KEEP IT SHORT!**
"""

    # ✅ RESTORED: Full ops agent tools for non-realtime flows
    # IMPORTANT: These tools are used ONLY in AgentKit / non-realtime flows
    # Realtime phone calls use media_ws_ai.py with separate tool policy
    from server.agent_tools.tools_business import business_get_info
    
    tools_to_use = [
        calendar_find_slots,
        calendar_create_appointment,
        leads_upsert,
        leads_search,
        invoices_create,
        payments_link,
        contracts_generate_and_send,
        whatsapp_send,
        summarize_thread,
        business_get_info
    ]
    logger.info(f"✅ Ops agent tools RESTORED (non-realtime flows)")
    
    # If business_id provided, could wrap tools here (similar to booking_agent)
    # For now, business_id will come from context
    
    try:
        # ✅ RESTORED: Ops agent with full tools for non-realtime flows
        agent = Agent(
            name=f"ops_agent_{business_name}",
            model="gpt-4o-mini",
            instructions=instructions,
            tools=tools_to_use,  # ✅ RESTORED: Full tools for AgentKit / non-realtime
            model_settings=AGENT_MODEL_SETTINGS
        )
        
        logger.info(f"✅ Created ops agent for '{business_name}' with {len(tools_to_use)} tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create ops agent: {e}")
        raise

def create_sales_agent(business_name: str = "העסק") -> Agent:
    """
    Create an agent specialized in sales and lead qualification
    
    Tools available:
    - leads.upsert: Create and update leads
    - leads.search: Find existing leads
    - whatsapp.send: Follow up with prospects
    
    Args:
        business_name: Name of the business
    
    Returns:
        Configured Agent for sales operations
    """
    if not AGENTS_ENABLED:
        logger.warning("Agents are disabled (AGENTS_ENABLED=0)")
        return None
    
    instructions = f"""אתה סוכן מכירות של {business_name}. תמיד תענה בעברית.

🎯 **התפקיד שלך:**
1. זהה לקוחות פוטנציאליים (לידים) ותעד אותם
2. אסוף מידע רלוונטי: שם, טלפון, צרכים, תקציב
3. סווג לידים לפי סטטוס: חדש/יצרנו קשר/מוסמך/נמכר
4. תאם פעולות מעקב

📋 **תהליך טיפול בליד:**
1. שאלות ממוקדות: "מה את/ה מחפש/ת?", "באיזה אזור?", "מה התקציב?"
2. שמור מידע: קרא ל-`leads.upsert` עם כל הפרטים
3. סכם את השיחה בסיכום קצר (10-30 מילים)
4. הצע מעקב או קבע פגישה

💬 **סגנון תקשורת:**
- חם, מקצועי, לא לוחץ
- שאלות פתוחות
- תשובות קצרות וממוקדות
- הקשבה פעילה

**חשוב: כל התשובות חייבות להיות בעברית - טבעית וחמה!**
"""

    # ✅ RESTORED: Sales agent tools for non-realtime flows
    # IMPORTANT: These tools are used ONLY in AgentKit / non-realtime flows
    from server.agent_tools.tools_business import business_get_info

    try:
        # ✅ RESTORED: Sales agent with tools for AgentKit / non-realtime
        agent = Agent(
            name=f"sales_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",
            instructions=instructions,
            tools=[
                leads_upsert,
                leads_search,
                whatsapp_send,
                business_get_info
            ]  # ✅ RESTORED: Full tools for AgentKit / non-realtime
        )
        
        logger.info(f"✅ Created sales agent for '{business_name}' with 3 tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create sales agent: {e}")
        raise


# ================================================================================
# WARMUP FUNCTION
# ================================================================================

def warmup_all_agents():
    """
    🔥 WARMUP: Pre-create agents for all active businesses to eliminate cold starts
    
    Called on app startup to ensure all businesses have hot agents ready.
    This prevents 10s delays on first customer call!
    
    Strategy:
    - Find all businesses that had activity in last 7 days
    - Pre-create agents for both phone + whatsapp channels
    - Limit to top 10 businesses to avoid startup delay
    """
    try:
        from server.models_sql import Business, db
        from sqlalchemy.exc import SQLAlchemyError
        from datetime import datetime, timedelta
        import time
        
        warmup_start = time.time()
        logger.info("\n🔥 WARMUP: Pre-creating agents for active businesses...")
        logger.info("🔥 Starting agent warmup...")
        
        # 🔥 FIX: Wait for database to be ready with retry logic
        # This prevents OperationalError during startup when DB connection isn't fully initialized
        max_retries = 5
        retry_delay = 1.0  # Start with 1 second
        active_businesses = None
        
        for attempt in range(max_retries):
            try:
                # Test database connection first
                db.session.execute(db.text("SELECT 1"))
                db.session.rollback()  # Clean up any transaction state
                
                # Query businesses - limit to 10 most recent for fast startup
                active_businesses = Business.query.order_by(Business.id.desc()).limit(10).all()
                break  # Success - exit retry loop
                
            except SQLAlchemyError as db_error:
                # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
                db.session.rollback()
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Database not ready (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    logger.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {db_error}")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 5.0)  # Exponential backoff with 5s cap
                else:
                    # Final attempt failed
                    logger.error(f"❌ Database connection failed after {max_retries} attempts")
                    logger.error(f"Database connection failed after {max_retries} attempts: {db_error}")
                    return
        
        if not active_businesses:
            logger.warning("⚠️  No active businesses found for warmup")
            logger.warning("No active businesses found for warmup")
            return
        
        logger.info(f"📊 Found {len(active_businesses)} businesses to warm up")
        logger.info(f"Found {len(active_businesses)} businesses to warm up")
        
        warmed_count = 0
        for biz in active_businesses:
            for channel in ["calls", "whatsapp"]:
                try:
                    agent = get_or_create_agent(
                        business_id=biz.id,
                        channel=channel,
                        business_name=biz.name,
                        custom_instructions=""  # Will load from DB
                    )
                    if agent:
                        warmed_count += 1
                        logger.info(f"✅ Warmed: {biz.name} ({channel})")
                        logger.info(f"✅ Agent warmed: business={biz.name}, channel={channel}")
                except Exception as e:
                    logger.error(f"⚠️  Failed to warm {biz.name} ({channel}): {e}")
                    logger.error(f"Failed to warm agent for {biz.name} ({channel}): {e}")
        
        warmup_time = (time.time() - warmup_start) * 1000
        logger.info(f"\n🎉 WARMUP COMPLETE: {warmed_count} agents ready in {warmup_time:.0f}ms")
        logger.info(f"🎉 Agent warmup complete: {warmed_count} agents in {warmup_time:.0f}ms")
        
    except Exception as e:
        logger.error(f"❌ WARMUP FAILED: {e}")
        logger.error(f"Agent warmup failed: {e}")
        import traceback
        traceback.print_exc()


# ================================================================================
# AGENT REGISTRY
# ================================================================================

_agent_cache = {}

def get_agent(agent_type: str = "booking", business_name: str = "העסק", custom_instructions: str = None, business_id: int = None, channel: str = "phone") -> Agent:
    """
    Get or create an agent by type
    
    Args:
        agent_type: Type of agent (booking/sales/ops)
        business_name: Business name for personalization
        custom_instructions: Custom instructions from database (if provided, creates new agent)
        business_id: Business ID for tool calls (required for booking agent)
        channel: Communication channel (phone/whatsapp/web)
    
    Returns:
        Agent instance (cached unless custom_instructions provided)
    """
    # 🎯 If custom instructions provided, always create fresh agent (don't cache)
    if custom_instructions and isinstance(custom_instructions, str) and custom_instructions.strip():
        logger.info(f"Creating fresh agent with custom instructions ({len(custom_instructions)} chars)")
        if agent_type == "booking":
            return create_booking_agent(business_name, custom_instructions, business_id, channel)
        elif agent_type == "sales":
            return create_sales_agent(business_name)
        elif agent_type == "ops":
            return create_ops_agent(business_name, business_id, channel)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    # Otherwise use cached agent (include channel in cache key!)
    cache_key = f"{agent_type}:{business_name}:{business_id}:{channel}"
    
    if cache_key not in _agent_cache:
        if agent_type == "booking":
            # 🔥 CRITICAL: Load DB prompt if not provided
            actual_instructions = custom_instructions
            if not actual_instructions or not isinstance(actual_instructions, str) or not actual_instructions.strip():
                try:
                    from server.models_sql import BusinessSettings
                    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                    if settings and settings.ai_prompt:
                        import json
                        try:
                            prompt_data = json.loads(settings.ai_prompt)
                            if isinstance(prompt_data, dict):
                                # Extract channel-specific prompt
                                if channel == "whatsapp":
                                    actual_instructions = prompt_data.get('whatsapp', '')
                                else:
                                    actual_instructions = prompt_data.get('calls', '')
                            else:
                                # Legacy single prompt
                                actual_instructions = settings.ai_prompt
                        except json.JSONDecodeError:
                            # Legacy single prompt
                            actual_instructions = settings.ai_prompt
                except Exception as e:
                    logger.warning(f"⚠️ Could not load DB prompt in get_agent for business={business_id}: {e}")
                    actual_instructions = None
            
            _agent_cache[cache_key] = create_booking_agent(business_name, actual_instructions, business_id, channel)
        elif agent_type == "sales":
            _agent_cache[cache_key] = create_sales_agent(business_name)
        elif agent_type == "ops":
            _agent_cache[cache_key] = create_ops_agent(business_name, business_id, channel)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agent_cache[cache_key]
