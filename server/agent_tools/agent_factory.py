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
import logging

logger = logging.getLogger(__name__)

# Check if agents are enabled
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "1") == "1"

# 🔥 SINGLETON CACHE: Store agents by (business_id, channel) key
_AGENT_CACHE: Dict[Tuple[int, str], Tuple[Agent, datetime]] = {}
_AGENT_LOCK = threading.Lock()
_CACHE_TTL_MINUTES = 5  # 🔥 REDUCED to 5 minutes so prompt changes take effect quickly!

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
    temperature=0.15,      # Very low temperature for consistent tool usage
    max_tokens=60,         # 🔥 CRITICAL: 60 tokens = ~15 words in Hebrew - prevents long responses & queue overflow!
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
                logger.info(f"✅ Using cached agent for business={business_id}, channel={channel} (age={age_minutes:.1f}min)")
                return cached_agent
            else:
                logger.info(f"🔄 Agent cache expired for business={business_id}, channel={channel} (age={age_minutes:.1f}min > {_CACHE_TTL_MINUTES}min)")
                # Remove expired entry
                del _AGENT_CACHE[cache_key]
        
        # No valid cache - create new agent
        logger.info(f"🆕 Creating NEW agent for business={business_id}, channel={channel}")
        
        try:
            import time
            agent_start = time.time()
            
            # 🔥 CRITICAL FIX: Load DB prompt if not provided
            print(f"📋 PROMPT LOADING: business_id={business_id}, channel={channel}, custom_instructions provided={bool(custom_instructions)}", flush=True)
            if not custom_instructions or not isinstance(custom_instructions, str) or not custom_instructions.strip():
                try:
                    from server.models_sql import Business
                    from sqlalchemy import text
                    from server.db import db
                    
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
                        print(f"⚠️ [BUILD 309] Raw SQL fallback for prompt: {sql_err}", flush=True)
                    
                    business = Business.query.filter_by(id=business_id).first()
                    print(f"📋 LOADING PROMPT: business_id={business_id}, business_name={business.name if business else 'N/A'}", flush=True)
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
                                print(f"✅ Loaded {channel} prompt from DB for business={business_id} ({len(custom_instructions)} chars)", flush=True)
                                print(f"📝 PROMPT PREVIEW: {custom_instructions[:100] if custom_instructions else 'EMPTY'}...", flush=True)
                            else:
                                # Legacy single prompt
                                custom_instructions = settings_row["ai_prompt"]
                                print(f"✅ Loaded legacy prompt from DB for business={business_id} ({len(custom_instructions)} chars)", flush=True)
                        except json.JSONDecodeError:
                            # Legacy single prompt
                            custom_instructions = settings_row["ai_prompt"]
                            print(f"✅ Loaded legacy prompt from DB for business={business_id} ({len(custom_instructions)} chars)", flush=True)
                    else:
                        print(f"⚠️ NO SETTINGS or NO AI_PROMPT for business={business_id}! settings_row={settings_row is not None}", flush=True)
                except Exception as e:
                    print(f"⚠️ Could not load DB prompt for business={business_id}: {e}", flush=True)
                    logger.warning(f"⚠️ Could not load DB prompt for business={business_id}: {e}")
                    custom_instructions = None
            
            print(f"🔨 CALLING create_booking_agent(business_id={business_id}, channel={channel})")
            logger.info(f"🔨 Creating agent for business={business_id}, channel={channel}")
            
            new_agent = create_booking_agent(
                business_name=business_name,
                custom_instructions=custom_instructions,
                business_id=business_id,
                channel=channel
            )
            
            print(f"✅ create_booking_agent RETURNED: {new_agent is not None}")
            logger.info(f"✅ create_booking_agent returned successfully")
            
            agent_creation_time = (time.time() - agent_start) * 1000
            print(f"⏱️  AGENT_CREATION_TIME: {agent_creation_time:.0f}ms")
            logger.info(f"⏱️  Agent creation took {agent_creation_time:.0f}ms")
            
            if agent_creation_time > 2000:
                logger.warning(f"⚠️  SLOW AGENT CREATION: {agent_creation_time:.0f}ms > 2000ms!")
            
            if new_agent:
                # Cache the new agent
                _AGENT_CACHE[cache_key] = (new_agent, now)
                logger.info(f"✅ Agent created and cached for business={business_id}, channel={channel}")
            
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
    
    # If business_id provided, create wrapper tools that inject it
    if business_id:
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
                
                print(f"\n🔧 🔧 🔧 TOOL CALLED: calendar_find_slots_wrapped 🔧 🔧 🔧")
                print(f"   📅 date_iso (RAW from Agent)={date_iso}")
                print(f"   ⏱️  duration_min={duration_min}")
                print(f"   🏢 business_id={business_id}")
                
                # 🔥 CRITICAL FIX: Agent often sends 2023 dates due to training data
                # Force-correct any year <2025 to 2025 (or map relative dates)
                from datetime import datetime
                import pytz
                import re
                
                corrected_date = date_iso
                match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_iso)
                if match:
                    year, month, day = match.groups()
                    year_int = int(year)
                    
                    if year_int < 2025:
                        # Agent sent old year - recalculate based on TODAY
                        now_israel = datetime.now(tz=pytz.timezone('Asia/Jerusalem'))
                        
                        # If month/day match tomorrow or day-after, use that
                        tomorrow = now_israel + timedelta(days=1)
                        day_after = now_israel + timedelta(days=2)
                        
                        if int(month) == tomorrow.month and int(day) == tomorrow.day:
                            corrected_date = tomorrow.strftime('%Y-%m-%d')
                            print(f"   🔧 CORRECTED 'tomorrow': {date_iso} → {corrected_date}")
                        elif int(month) == day_after.month and int(day) == day_after.day:
                            corrected_date = day_after.strftime('%Y-%m-%d')
                            print(f"   🔧 CORRECTED 'day after': {date_iso} → {corrected_date}")
                        else:
                            # Just fix the year to 2025
                            corrected_date = f"2025-{month}-{day}"
                            print(f"   🔧 CORRECTED year: {date_iso} → {corrected_date}")
                
                print(f"   ✅ date_iso (CORRECTED)={corrected_date}")
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
                
                print(f"✅ calendar_find_slots_wrapped RESULT: {len(result.slots)} slots found")
                logger.info(f"✅ calendar_find_slots_wrapped RESULT: {len(result.slots)} slots found")
                if result.slots:
                    slot_times = [s.start_display for s in result.slots[:5]]
                    print(f"   Available times: {', '.join(slot_times)}{'...' if len(result.slots) > 5 else ''}")
                    logger.info(f"   Available times: {', '.join(slot_times)}{'...' if len(result.slots) > 5 else ''}")
                else:
                    print(f"   ⚠️ NO SLOTS AVAILABLE for {date_iso}")
                    logger.warning(f"   ⚠️ NO SLOTS AVAILABLE for {date_iso}")
                
                # Convert Pydantic model to dict for Agent SDK
                result_dict = result.model_dump()
                
                # 🔥 BUILD 114: HARD LIMIT - Return ONLY 2 slots maximum!
                # Don't rely on LLM to follow instructions - enforce in code!
                original_count = len(result_dict.get('slots', []))
                if original_count > 2:
                    result_dict['slots'] = result_dict['slots'][:2]
                    print(f"🔥 SLOT_LIMIT: Reduced {original_count} slots → 2 (enforced in code)")
                    logger.info(f"🔥 SLOT_LIMIT: Reduced {original_count} slots → 2 slots")
                
                tool_time = (time.time() - tool_start) * 1000
                print(f"⏱️  TOOL_TIMING: calendar_find_slots = {tool_time:.0f}ms")
                logger.info(f"⏱️  TOOL_TIMING: calendar_find_slots = {tool_time:.0f}ms")
                
                if tool_time > 500:
                    print(f"⚠️  SLOW TOOL: calendar_find_slots took {tool_time:.0f}ms (expected <500ms)")
                    logger.warning(f"SLOW TOOL: calendar_find_slots took {tool_time:.0f}ms")
                
                print(f"📤 Returning dict with {len(result_dict.get('slots', []))} slots")
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
            
            CRITICAL: Must have valid customer_phone before calling this!
            Agent MUST collect phone via DTMF (keypad input) BEFORE booking.
            
            Args:
                treatment_type: Type of treatment (required)
                start_iso: Start time in ISO format (required)
                end_iso: End time in ISO format (required)
                customer_phone: Customer phone number (required - collected via DTMF)
                customer_name: Customer name (required - collected verbally)
                notes: Additional notes (optional)
            """
            try:
                import time
                tool_start = time.time()
                
                print(f"\n🔧 🔧 🔧 TOOL CALLED: calendar_create_appointment_wrapped 🔧 🔧 🔧")
                print(f"   📅 treatment_type={treatment_type}")
                print(f"   📅 start_iso={start_iso}, end_iso={end_iso}")
                print(f"   📞 customer_phone (from Agent)={customer_phone}")
                print(f"   👤 customer_name (from Agent)={customer_name}")
                print(f"   🏢 business_id={business_id}")
                
                from server.agent_tools.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
                from flask import g
                
                # Get context and session for _choose_phone
                context = getattr(g, 'agent_context', None)
                session = None  # TODO: pass session if available
                
                # 🔥 CRITICAL: Validate both NAME and PHONE!
                if not customer_name or customer_name.strip() in ["", "לקוח", "customer"]:
                    error_msg = "חובה לציין שם לקוח לפני קביעת תור! שאל: 'מה השם שלך?'"
                    logger.error(f"❌ calendar_create_appointment_wrapped: {error_msg}")
                    return {
                        "ok": False,
                        "error": "missing_name",
                        "message": error_msg
                    }
                
                # 🔥 NEW: Validate phone was collected via DTMF
                if not customer_phone or len(customer_phone.strip()) < 9:
                    error_msg = "חובה לאסוף מספר טלפון לפני קביעת תור! בקש: 'הקלד את מספר הטלפון במקשים ולחץ #'"
                    logger.error(f"❌ calendar_create_appointment_wrapped: {error_msg}")
                    return {
                        "ok": False,
                        "error": "missing_phone",
                        "message": error_msg
                    }
                
                # 🔥 CRITICAL: Validate date/time to ensure calendar was checked
                from datetime import datetime
                import pytz
                try:
                    tz = pytz.timezone("Asia/Jerusalem")
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
                print(f"🚀 CALLING _calendar_create_appointment_impl...")
                result = _calendar_create_appointment_impl(input_data, context=context, session=session)
                print(f"📥 RESULT from _calendar_create_appointment_impl: {result}")
                
                # Check if result is error dict or success object
                if isinstance(result, dict):
                    # Error response from _calendar_create_appointment_impl
                    print(f"❌ Got ERROR dict: {result}")
                    logger.warning(f"❌ calendar_create_appointment_wrapped returned error: {result}")
                    return result
                
                print(f"✅ SUCCESS! Appointment ID: {result.appointment_id}")
                logger.info(f"✅ calendar_create_appointment_wrapped success: appointment_id={result.appointment_id}")
                
                tool_time = (time.time() - tool_start) * 1000
                print(f"⏱️  TOOL_TIMING: calendar_create_appointment = {tool_time:.0f}ms")
                logger.info(f"⏱️  TOOL_TIMING: calendar_create_appointment = {tool_time:.0f}ms")
                
                if tool_time > 1000:
                    print(f"⚠️  SLOW TOOL: calendar_create_appointment took {tool_time:.0f}ms (expected <1000ms)")
                    logger.warning(f"SLOW TOOL: calendar_create_appointment took {tool_time:.0f}ms")
                
                # Return success response
                success_response = {
                    "ok": True,
                    "appointment_id": result.appointment_id,
                    "status": result.status,
                    "confirmation_message": result.confirmation_message
                }
                print(f"📤 Returning success: {success_response}")
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
                            print(f"   ✅ leads_upsert using phone from context: {actual_phone}")
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
        
        # ✅ RESTORED: AgentKit tools for non-realtime flows (WhatsApp, backend tasks, post-call)
        # IMPORTANT: These tools are used ONLY in AgentKit / non-realtime flows
        # Realtime phone calls use media_ws_ai.py with separate tool policy
        tools_to_use = [
            calendar_find_slots_wrapped,
            calendar_create_appointment_wrapped,
            leads_upsert_wrapped,
            leads_search,
            whatsapp_send,
            business_get_info
        ]
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
    

    # 🔥 BUILD 135: MERGE DB prompts WITH base instructions (not replace!)
    # CRITICAL: DB prompts now EXTEND the base AgentKit instructions
    
    today_str = datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d %H:%M')
    tomorrow_str = (datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 🔥 BUILD 138: Load business policy to get slot_size_min
    slot_interval_text = ""
    if business_id:
        try:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=custom_instructions)
            
            # Convert slot size to Hebrew description
            if policy.slot_size_min == 15:
                interval_desc = "כל רבע שעה (15 דקות)"
            elif policy.slot_size_min == 30:
                interval_desc = "כל חצי שעה (30 דקות)"
            elif policy.slot_size_min == 45:
                interval_desc = "כל 45 דקות (שלושת רבעי שעה)"
            elif policy.slot_size_min == 60:
                interval_desc = "כל שעה (60 דקות)"
            elif policy.slot_size_min == 75:
                interval_desc = "כל שעה ורבע (75 דקות)"
            elif policy.slot_size_min == 90:
                interval_desc = "כל שעה וחצי (90 דקות)"
            elif policy.slot_size_min == 105:
                interval_desc = "כל שעה ושלושת רבעי (105 דקות)"
            elif policy.slot_size_min == 120:
                interval_desc = "כל שעתיים (120 דקות)"
            else:
                interval_desc = f"כל {policy.slot_size_min} דקות"
            
            slot_interval_text = f"\nAPPOINTMENT INTERVALS: תורים בעסק הזה ניתנים לקביעה {interval_desc}"
            logger.info(f"📅 Agent will use slot interval: {policy.slot_size_min} minutes ({interval_desc})")
        except Exception as e:
            logger.warning(f"⚠️ Could not load policy for slot_size_min: {e}")
    
    # 🔥 CRITICAL SYSTEM RULES (prepended to all prompts - NEVER remove!)
    system_rules = f"""🔒 SYSTEM CONTEXT (READ BUT DON'T MENTION):
TODAY: {today_str} (Israel)
TOMORROW: {tomorrow_str}{slot_interval_text}

⚠️ CRITICAL ANTI-HALLUCINATION RULES (BUILD 112):
1. NEVER say "קבעתי"/"הפגישה נקבעה" UNLESS you called calendar_create_appointment() THIS turn and got ok:true
2. NEVER say "תפוס"/"פנוי"/"יש תור" UNLESS you called calendar_find_slots() THIS turn
3. NEVER say "שלחתי אישור" UNLESS you called whatsapp_send() THIS turn
4. 🔥 BUILD 112: After SUCCESSFUL booking (ok:true), ALWAYS call whatsapp_send() to send confirmation
5. NEVER say "אני מחפש" or "תן לי לבדוק" - just call the tool silently
6. 🔥 NEW: If you don't have enough info yet, ASK before calling tools - don't guess!
7. 🔥 NEW: Complete ONE action at a time - don't claim "קבעתי + שלחתי" in same turn

🎯 SLOT PRESENTATION RULE (BUILD 113):
- When calendar_find_slots returns results, suggest ONLY 2 times maximum
- Pick 2 diverse times (e.g., morning + afternoon, or 2 closest to customer's request)
- NEVER list all available slots - it's overwhelming on voice calls!
- Example GOOD: "יש פנוי ב-9:00 או 14:00, מה מתאים?"
- Example BAD: "יש פנוי ב-9:00, 10:00, 11:00, 12:00, 13:00, 14:00..." ❌

⏱️ TURN MANAGEMENT:
- You have max 25 turns to complete the task (increased from 15)
- Prioritize gathering info first (name, phone, date, time)
- Then check availability → book → send confirmation
- If running out of turns, ask for ONE thing at a time

🎯 SMART APPOINTMENT OFFERING (CRITICAL!):
- 🔥 DO NOT offer/suggest appointments unless customer explicitly asks for one!
- Wait for customer to say things like: "רוצה לקבוע תור", "מתי יש פנוי", "אפשר קביעה"
- If customer asks general questions, answer them WITHOUT offering appointments
- Example BAD: "שלום! רוצה לקבוע תור?" ❌ (too pushy)
- Example GOOD: "שלום! איך אני יכולה לעזור?" ✅ (let customer lead)

🔒 STAY ON TOPIC (CRITICAL!):
- 🔥 ONLY discuss topics related to THIS business and the services mentioned in your prompt!
- If customer asks unrelated questions (weather, news, general knowledge, other businesses):
  → Politely redirect: "אני כאן לעזור עם תיאום פגישות ופרטי העסק. איך אוכל לעזור?"
- Examples:
  ✅ GOOD: Questions about appointments, services, location, hours, pricing
  ❌ BAD: "מה מזג האויר?", "מי ראש הממשלה?", "תכתוב לי שיר"
- 🔥 NEVER answer questions outside your business scope - always redirect politely!

📋 BOOKING WORKFLOW (ONLY when customer requests appointment!):
1. Ask for DATE & TIME preference first
2. Call calendar_find_slots() to check availability
3. Suggest 2 available times if requested time is unavailable
4. Once time is confirmed, ask for NAME only: "על איזה שם?"
5. Once you have name, ask for PHONE:
   - 📞 PHONE channel ONLY: "מה המספר שלך? אנא הקלידו והקישו סולמית (#) בסיום"
   - 📱 WHATSAPP channel: "מה המספר שלך?" (NO DTMF instruction!)
6. Call calendar_create_appointment() with all details
7. Confirm booking based on whatsapp_status

🔥 CRITICAL: Ask for NAME and PHONE separately - NEVER together!
🔥 Get DATE/TIME confirmed BEFORE asking for NAME
🔥 DTMF (# key) is ONLY for PHONE calls - NEVER mention it on WhatsApp!

📱 WHATSAPP CONFIRMATIONS (BUILD 115 - AUTOMATIC!):
- calendar_create_appointment now returns "whatsapp_status" field with values:
  * "sent" → WhatsApp אישור נשלח בהצלחה
  * "failed" → WhatsApp נכשל (עדיין הפגישה נקבעה!)
  * "pending" → אין מספר טלפון עדיין
  * "skipped" → לא רלוונטי לערוץ הזה
  
🎯 HOW TO RESPOND BASED ON whatsapp_status:
- whatsapp_status="sent" → Say: "קבעתי לך את הפגישה ושלחתי עכשיו אישור בווטסאפ!"
- whatsapp_status="failed" → Say: "קבעתי לך את הפגישה, הפרטים יישלחו אליך מאוחר יותר בווטסאפ."
- whatsapp_status="pending" → Say: "קבעתי לך את הפגישה, פרטים ישלחו בהמשך."
- whatsapp_status="skipped" → Just confirm the appointment normally

🔥 CRITICAL: NEVER say "לא הצלחתי לשלוח" or "שירות לא זמין" - customer doesn't care!
🔥 NEVER claim "שלחתי אישור" unless whatsapp_status="sent"

📞 DTMF Phone Input (internal note):
- PHONE channel: When asking for phone, say "מה המספר שלך? אנא הקלידו והקישו סולמית בסיום"
- WHATSAPP channel: Just say "מה המספר שלך?"
Customer presses digits + # to end input.

---
"""
    
    # 🔥 BUILD 99: Use DB prompt ONLY if it exists (it's the business's custom instructions!)
    if custom_instructions and custom_instructions.strip():
        # DB prompt exists - use it as the MAIN prompt!
        instructions = system_rules + custom_instructions
        print(f"\n✅ Using DB prompt for {business_name} ({len(custom_instructions)} chars)")
        print(f"   System rules: {len(system_rules)} chars (prepended)")
        print(f"   DB prompt: {len(custom_instructions)} chars")
        print(f"   = Total: {len(instructions)} chars")
        logger.info(f"✅ Using DATABASE prompt for {business_name} (total: {len(instructions)} chars)")
    else:
        # No DB prompt - use minimal fallback
        fallback_prompt = f"""You are a Hebrew booking assistant for {business_name}.

Your job:
1. Help customers find available appointment times
2. Book appointments using the calendar tools
3. Collect customer information (name + phone)
4. Send WhatsApp confirmations when possible

🔥 WhatsApp Error Handling:
- If whatsapp_send fails → Say "פרטים ישלחו בהמשך" (don't mention the failure)
- NEVER say technical errors like "שירות לא זמין"

Always respond in HEBREW only.
Keep responses short (2-3 sentences).
Be friendly and professional."""
        
        instructions = system_rules + fallback_prompt
        print(f"\n⚠️  NO DB prompt - using minimal fallback for {business_name}")
        logger.warning(f"No DATABASE prompt for {business_name} - using minimal fallback")

    try:
        # DEBUG: Print the actual instructions the agent receives
        print("\n" + "="*80)
        print("📜 AGENT INSTRUCTIONS (first 500 chars):")
        print("="*80)
        print(instructions[:500])
        print("...")
        print("="*80)
        print(f"📅 Today calculated as: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}")
        print(f"📅 Tomorrow calculated as: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}")
        print("="*80 + "\n")
        
        # 🔥 BUILD 115: Dynamic max_tokens per channel
        # Phone/calls: 60 tokens (15 words) - prevents queue overflow
        # WhatsApp: 800 tokens (~200-250 Hebrew words) - allows full detailed responses without truncation
        if channel == "whatsapp":
            model_settings = ModelSettings(
                temperature=0.15,
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
    
    instructions = f"""You are an operations agent for {business_name}. ALWAYS respond in Hebrew.

📅 **DATE CONTEXT:**
Today is {today.strftime('%Y-%m-%d (%A)')}, current time: {today.strftime('%H:%M')} Israel time (Asia/Jerusalem).
- Tomorrow ("מחר") = {tomorrow.strftime('%Y-%m-%d')}
- Day after tomorrow ("מחרתיים") = {day_after.strftime('%Y-%m-%d')}

🎯 **YOUR CAPABILITIES:**

1. **APPOINTMENTS (Calendar Tools):**
   - Find available slots: calendar_find_slots
   - Create appointments: calendar_create_appointment
   - ALWAYS check availability before confirming
   - 🔥 CRITICAL: When showing slots, suggest ONLY 2 times MAX - NOT all available slots!
   - Example: "יש פנוי ב-9:00 או 14:00, מה מתאים לך?" (רק 2 שעות!)
   - For business hours: Use business_get_info() to get actual operating hours

2. **LEADS/CRM (Customer Management):**
   - Create or update leads: leads_upsert
   - Search existing customers: leads_search
   - Automatically link leads to appointments

3. **INVOICES & PAYMENTS:**
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

7. **STAY ON TOPIC (CRITICAL!):**
   - 🔥 ONLY discuss topics related to THIS business and the services mentioned in your prompt!
   - If customer asks unrelated questions (weather, news, general knowledge, other businesses):
     → Politely redirect: "אני כאן לעזור עם תיאום פגישות ופרטי העסק. איך אוכל לעזור?"
   - Examples:
     ✅ GOOD: Appointments, services, location, hours, pricing, payments, contracts
     ❌ BAD: "מה מזג האויר?", "מי ראש הממשלה?", "תכתוב לי שיר", "מה קורה בעולם?"
   - 🔥 NEVER answer questions outside your business scope - always redirect politely!

📋 **AUTOMATION WORKFLOWS (CRITICAL - ALWAYS FOLLOW):**

**1. APPOINTMENT WORKFLOW (STEP-BY-STEP - MUST FOLLOW ORDER!):**

🎯 **CRITICAL: This is a 4-turn conversation - DO NOT skip steps!**

**Turn 1: Get NAME**
→ Ask: "מה השם שלך?" or "איך קוראים לך?"
→ WAIT for customer to say their name
→ Save name in memory

**Turn 2: Get PHONE via DTMF**
→ Request DTMF phone input: "בבקשה הקלד את מספר הטלפון שלך במקשים ואז לחץ על סולמית (#)"
→ WAIT for phone_number from DTMF
→ Save phone in memory

**Turn 3: Get DATE preference**
→ Ask: "באיזה תאריך נוח לך? מחר? מחרתיים?"
→ WAIT for customer to say date (e.g., "מחר", "יום רביעי", "13 בנובמבר")
→ Convert Hebrew to ISO date (use context: today={today.strftime('%Y-%m-%d')})

**Turn 4: Get TIME + CHECK + BOOK**
→ IF customer already mentioned specific time (e.g., "רוצה תור ב-17:00"):
  • Parse the time from their message
  • MUST call: calendar_find_slots(date_iso="YYYY-MM-DD", duration_min=60, preferred_time="17:00")
  • IF requested time IS IN the returned slots:
    ✅ BOOK IMMEDIATELY! Call: calendar_create_appointment(date_iso=..., time_str=..., customer_name=..., customer_phone=...)
    ✅ Respond: "מעולה! קבעתי לך תור ב-[date] ב-[time]. נתראה!"
  • IF requested time NOT in returned slots (occupied/unavailable):
    ❌ Say: "17:00 תפוס. הכי קרוב: [slot1] או [slot2]. באיזו שעה נוח?"
    ❌ WAIT for customer to choose → then book
→ IF customer did NOT mention specific time:
  • Ask: "באיזו שעה נוח לך?"
  • WAIT for customer to say time → then check calendar

🚨 **CRITICAL RULE - DON'T ASK IF CUSTOMER ALREADY SAID!**
- Customer said "תור ב-17:00" + 17:00 available → BOOK at 17:00 (DON'T ask "באיזו שעה?")
- Customer said "תור ב-17:00" + 17:00 occupied → Suggest alternatives
- Customer said "תור מחר" (no time) → Ask "באיזו שעה?"

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
    
    instructions = f"""You are a sales agent for {business_name}. ALWAYS respond in Hebrew.

🎯 **YOUR ROLE:**
1. Identify potential customers (leads) and record them
2. Collect relevant information: name, phone, needs, budget
3. Classify leads by status: new/contacted/qualified/won
4. Coordinate follow-up actions

📋 **LEAD HANDLING PROCESS:**
1. Targeted questions: "What are you looking for?", "Which area?", "What's your budget?"
2. Save information: Call `leads.upsert` with all details
3. Summarize the conversation in a short summary (10-30 words)
4. Suggest follow-up or schedule a meeting

💬 **COMMUNICATION STYLE:**
- Warm, professional, not pushy
- Open-ended questions
- Short, focused responses
- Active listening

**CRITICAL: ALL RESPONSES MUST BE IN HEBREW - NATURAL AND WARM!**
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
        from datetime import datetime, timedelta
        import time
        
        warmup_start = time.time()
        print("\n🔥 WARMUP: Pre-creating agents for active businesses...")
        logger.info("🔥 Starting agent warmup...")
        
        # Get active businesses (had activity in last 7 days)
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        # Query businesses - limit to 10 most recent for fast startup
        active_businesses = Business.query.order_by(Business.id.desc()).limit(10).all()
        
        if not active_businesses:
            print("⚠️  No active businesses found for warmup")
            logger.warning("No active businesses found for warmup")
            return
        
        print(f"📊 Found {len(active_businesses)} businesses to warm up")
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
                        print(f"✅ Warmed: {biz.name} ({channel})")
                        logger.info(f"✅ Agent warmed: business={biz.name}, channel={channel}")
                except Exception as e:
                    print(f"⚠️  Failed to warm {biz.name} ({channel}): {e}")
                    logger.error(f"Failed to warm agent for {biz.name} ({channel}): {e}")
        
        warmup_time = (time.time() - warmup_start) * 1000
        print(f"\n🎉 WARMUP COMPLETE: {warmed_count} agents ready in {warmup_time:.0f}ms")
        logger.info(f"🎉 Agent warmup complete: {warmed_count} agents in {warmup_time:.0f}ms")
        
    except Exception as e:
        print(f"❌ WARMUP FAILED: {e}")
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
