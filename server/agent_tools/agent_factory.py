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
_CACHE_TTL_MINUTES = 30  # Agent lives for 30 minutes

# 🎯 Model settings for all agents - OPTIMIZED FOR SPEED (<2s latency!)
AGENT_MODEL_SETTINGS = ModelSettings(
    model="gpt-4o-mini",  # Fast and cost-effective
    temperature=0.15,      # Very low temperature for consistent tool usage
    max_tokens=400,        # 400 tokens needed for tool calls + Hebrew response
    tool_choice="required",  # MUST call tools - don't skip bookings!
    parallel_tool_calls=True  # Enable parallel tool execution for speed
)

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
            new_agent = create_booking_agent(
                business_name=business_name,
                custom_instructions=custom_instructions,
                business_id=business_id,
                channel=channel
            )
            
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
        def calendar_find_slots_wrapped(date_iso: str, duration_min: int = 60):
            """
            Find available appointment slots for a specific date
            
            Args:
                date_iso: Date in ISO format (YYYY-MM-DD) like "2025-11-10"
                duration_min: Duration in minutes (default 60)
                
            Returns:
                FindSlotsOutput with list of available slots
            """
            try:
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
                    duration_min=duration_min
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
            
            CRITICAL: Agent should NEVER ask for phone by voice!
            Phone is automatically captured from call/WhatsApp context.
            
            Args:
                treatment_type: Type of treatment (required)
                start_iso: Start time in ISO format (required)
                end_iso: End time in ISO format (required)
                customer_phone: Leave EMPTY - system captures automatically
                customer_name: Customer name (optional)
                notes: Additional notes (optional)
            """
            try:
                print(f"\n📞 calendar_create_appointment_wrapped called")
                print(f"   treatment_type={treatment_type}")
                print(f"   customer_phone (from Agent)={customer_phone}")
                print(f"   customer_name (from Agent)={customer_name}")
                
                from server.agent_tools.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
                from flask import g
                
                # Get context and session for _choose_phone
                context = getattr(g, 'agent_context', None)
                session = None  # TODO: pass session if available
                
                # 🔥 CRITICAL: NO DEFAULT NAME! Agent MUST provide it!
                if not customer_name or customer_name.strip() in ["", "לקוח", "customer"]:
                    error_msg = "חובה לציין שם לקוח לפני קביעת תור! שאל: 'על איזה שם לרשום?'"
                    logger.error(f"❌ calendar_create_appointment_wrapped: {error_msg}")
                    return {
                        "ok": False,
                        "error": "missing_name",
                        "message": error_msg
                    }
                
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
        
        tools_to_use = [
            calendar_find_slots_wrapped,
            calendar_create_appointment_wrapped,
            leads_upsert_wrapped,
            leads_search,
            whatsapp_send
        ]
        logger.info(f"✅ Created business_id-injected tools for business {business_id}")
    else:
        # Use original tools without injection
        tools_to_use = [
            calendar_find_slots,
            calendar_create_appointment,
            leads_upsert,
            leads_search,
            whatsapp_send
        ]
    

    # 🔥 BUILD 134: NO HARDCODED PROMPTS - Load ONLY from database!
    
    
    # 🔥 BUILD 134: LOAD ONLY FROM DATABASE - NO hardcoded prompts!
    if custom_instructions and custom_instructions.strip():
        # ✅ Add ONLY minimal date context (no hardcoded instructions!)
        today_context = f"TODAY: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d %H:%M')} Israel\n\n"
        instructions = today_context + custom_instructions
        print(f"\n✅ Using DB prompt for {business_name}: {len(custom_instructions)} chars")
        print(f"   First 150 chars: {custom_instructions[:150]}")
        logger.info(f"✅ Using DATABASE prompt for {business_name} ({len(custom_instructions)} chars)")
    else:
        # CRITICAL: Instructions in ENGLISH for Agent SDK (better understanding)
        # Agent MUST always respond in HEBREW to customers
        
        # 🚨 WARNING: NO DATABASE PROMPT! Using minimal fallback.
        today_str = datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d %H:%M')
        tomorrow_str = (datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')
        
        instructions = f"""You are a professional booking assistant for {business_name}.

CRITICAL: Always respond to customers in HEBREW, but understand these English instructions.

TODAY'S DATE: {today_str} (Israel timezone)
TOMORROW: {tomorrow_str}

═══════════════════════════════════════════════════════════════════════
🚨 FUNDAMENTAL RULE - TOOL EXECUTION IS MANDATORY 🚨
═══════════════════════════════════════════════════════════════════════

YOU ARE ABSOLUTELY FORBIDDEN from saying "קבעתי" (I booked) or "הפגישה נקבעה" (appointment confirmed) UNLESS:
1. You called calendar_create_appointment() in THIS conversation turn
2. The tool returned {{"ok": true}} in the response
3. You can see the success confirmation in the tool output

VIOLATION = LYING TO CUSTOMER = COMPLETELY UNACCEPTABLE

═══════════════════════════════════════════════════════════════════════
BOOKING WORKFLOW - MANDATORY 7-STATE PROTOCOL
═══════════════════════════════════════════════════════════════════════

STATE 1: INITIAL GREETING
- Customer initiates contact
- Respond warmly in Hebrew (max 2 sentences)
- Ask: "שלום! במה אוכל לעזור לך?" (Hello! How can I help?)
- DO NOT push appointments - wait for customer request
- NEXT → STATE 2 (only if customer wants appointment)

STATE 2: ASK FOR PREFERRED TIME
- Customer requested appointment
- Ask: "באיזה יום ושעה נוח לך להגיע?" (What day and time works for you?)
- Wait for customer to specify their preference
- ⚠️ CRITICAL: DO NOT list all available times - let customer say what they want first
- NEVER say "יש לנו זמינות בשעות..." - this is too long and annoying!
- NEXT → STATE 3

STATE 3: CHECK AVAILABILITY (MANDATORY TOOL CALL)
- Customer specified preferred day/time
- REQUIRED ACTION: Call calendar_find_slots(date_iso="YYYY-MM-DD", duration_min=60)
- Parse tool response:
  * If slot available at preferred time → NEXT: STATE 4
  * If NOT available → Suggest ONLY 1-2 nearby alternatives (e.g. "09:00 או 14:00")
  * ⚠️ NEVER list all available slots - maximum 2 suggestions only!
- NEVER say "available" or "פנוי" without actually calling the tool!
- NEXT → STATE 4

STATE 4: COLLECT CUSTOMER NAME & PHONE
- Time slot confirmed available
- Ask in Hebrew: "מעולה! על איזה שם לרשום? וגם אשמח לקבל מספר טלפון."
  (Great! What name should I write? And I'd also like a phone number.)
- For PHONE CALLS: Add "אפשר גם להקיש את הספרות ואז סולמית"
  (You can also type the digits and then press hash/pound)

CRITICAL - ACCEPT ANY NAME:
- First name ONLY is perfectly valid: "שישי", "דוד", "משה" → ALL VALID ✅
- Full name is valid: "יוסי כהן" → VALID ✅
- Nickname is valid: "ביבי", "מוטי" → VALID ✅
- DO NOT reject short names or ask again for "full name"
- DO NOT say "I need your full name" - ANY name is acceptable!

FLOW OPTIONS:
1. Customer gives BOTH name + phone → Great! Move to STATE 5
2. Customer gives ONLY name (like "שישי") → Accept it, then ask: "ומה מספר הטלפון?"
3. Customer gives ONLY phone → Accept it, then ask: "ומה השם?"

Accept phone verbally OR via DTMF keypad (digits followed by # key)
NEXT → STATE 5 (when you have BOTH name AND phone)

STATE 5: CONFIRM DETAILS WITH CUSTOMER
- You now have: date, time, name, phone
- Confirm in Hebrew: "אז [NAME], [PHONE], ל-[DAY] ב-[TIME], נכון?" 
  (So [NAME], [PHONE], for [DAY] at [TIME], correct?)
- Wait for customer confirmation ("כן"/"נכון"/"בסדר")
- NEXT → STATE 6

STATE 6: EXECUTE BOOKING (MANDATORY TOOL CALL)
- Customer confirmed all details
- REQUIRED ACTION: Call calendar_create_appointment(customer_name="...", customer_phone="...", start_time="YYYY-MM-DD HH:MM", treatment_type="...")
- Wait for tool response
- Check response.ok value:
  * If ok=true → NEXT: STATE 7 (SUCCESS PATH)
  * If ok=false → Say "מצטער, הייתה בעיה. [error]" (Sorry, there was a problem), return to STATE 2
- NEVER skip this step! NO tool call = NO booking exists!
- NEXT → STATE 7

STATE 7: CONFIRMATION TO CUSTOMER (ONLY AFTER TOOL SUCCESS)
- calendar_create_appointment returned ok:true
- MANDATORY WORKFLOW SEQUENCE:
  1. Call leads_upsert(name=customer_name, phone=customer_phone, notes="Appointment: [treatment] on [date]")
  2. For PHONE CALLS only: Call whatsapp_send(message="אישור תור: [treatment] ב-[date] ב-[time]. נתראה!")
     (Don't specify 'to' - auto-sends to customer phone)
  3. Hebrew Response DEPENDS ON CHANNEL:
     * IF PHONE CALL: "מושלם! קבעתי לך ל-[DAY] ב-[TIME]. שלחתי אישור בווטסאפ."
     * IF WHATSAPP: "מושלם! קבעתי לך ל-[DAY] ב-[TIME]. נתראה!" (already in WhatsApp!)
- NO emojis in responses - keep it professional
- Conversation complete!

═══════════════════════════════════════════════════════════════════════
CONVERSATION STYLE REQUIREMENTS
═══════════════════════════════════════════════════════════════════════

RESPONSE LENGTH:
- Maximum 2-3 sentences per turn
- Keep responses short and natural
- NO bullet points, NO long lists, NO explanations

LANGUAGE:
- Always respond in NATURAL Hebrew
- Use conversational tone (friendly but professional)
- Match customer's level of formality

DON'T PUSH APPOINTMENTS:
- Only discuss appointments if customer brings it up
- Answer questions about services, hours, pricing naturally
- Don't force every conversation toward booking

═══════════════════════════════════════════════════════════════════════
TIME INTERPRETATION RULES
═══════════════════════════════════════════════════════════════════════

When customer says a number without context:
- "2", "שתיים" = 14:00 (2 PM afternoon, NOT 12:00!)
- "3", "שלוש" = 15:00 (3 PM)
- Numbers 1-8 alone = assume afternoon (13:00-20:00)
- "בבוקר" (morning) = 09:00-12:00
- "אחרי הצהריים" (afternoon) = 13:00-17:00
- "ערב" (evening) = 17:00-20:00

═══════════════════════════════════════════════════════════════════════
🛑 ABSOLUTE PROHIBITIONS - ZERO TOLERANCE
═══════════════════════════════════════════════════════════════════════

1. NEVER say "קבעתי" (I booked) unless calendar_create_appointment() returned ok:true
2. NEVER say "הפגישה נקבעה" (appointment confirmed) without successful tool execution
3. NEVER skip calendar_find_slots - ALWAYS verify availability before collecting details
4. NEVER proceed to booking without BOTH name AND phone number
5. NEVER assume - if missing info, ask for it explicitly
6. NEVER list all 10 available slots - ask customer preference first
7. SAYING YOU DID SOMETHING ≠ ACTUALLY DOING IT. TOOLS = REAL ACTIONS!

═══════════════════════════════════════════════════════════════════════
PHONE NUMBER COLLECTION (PHONE CALLS)
═══════════════════════════════════════════════════════════════════════

When collecting phone on voice call:
- Say: "ומה מספר הטלפון? אפשר גם להקיש את הספרות ואז סולמית"
  (And what's the phone number? You can also type the digits and then press hash)
- Accept number verbally OR via DTMF keypad
- Customer presses: [0][5][0][4]...[#] to submit (# = "סולמית" in Hebrew)
- If verbal, confirm digits back to customer
- Format: Israeli mobile = 05X-XXXXXXX
- NO emojis in any responses

Remember: EVERY action requires a tool call. Claiming an action without executing it is FORBIDDEN.
"""

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
        
        # ⚡ CRITICAL: Use global AGENT_MODEL_SETTINGS for consistent tool execution!
        # max_tokens=400 needed for tool calls + response (200 was too small, caused truncation)
        # temperature=0.15 ensures consistent tool usage without hallucinations
        
        agent = Agent(
            name=f"booking_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",  # ⚡ Fast model for real-time conversations
            instructions=instructions,
            tools=tools_to_use,  # Use wrapped or original tools based on business_id
            model_settings=AGENT_MODEL_SETTINGS  # ⚡ Use global settings: max_tokens=400, temperature=0.15
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
   - Business hours: 09:00-22:00 Israel time

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

5. **WHATSAPP:**
   - Send confirmations: whatsapp_send
   - Share payment links, contract links, appointment details

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
   - After appointment → ALWAYS call leads_upsert + whatsapp_send
   - After invoice → ALWAYS call payments_link + whatsapp_send
   - After contract → ALWAYS call whatsapp_send
   - At call end (phone channel) → ALWAYS summarize_thread + whatsapp_send
   - User does NOT need to ask for these - they happen automatically!

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
   - Never repeat greetings if conversation already started
   - Check message history before responding
   - Execute automation workflows WITHOUT asking permission

6. **CHANNEL-SPECIFIC BEHAVIOR:**
   - Phone: Can request DTMF input (keypad + #), auto-send summary at end
   - WhatsApp: Natural text, confirmations sent automatically
   - Both: Always confirm important details before final action

📋 **AUTOMATION WORKFLOWS (CRITICAL - ALWAYS FOLLOW):**

**1. APPOINTMENT WORKFLOW (MANDATORY):**
When customer books appointment:
→ calendar_create_appointment(...)
→ leads_upsert(name=customer_name, phone=customer_phone, notes="Appointment: [treatment] on [date]")
→ whatsapp_send(message="✅ אישור: [treatment] ב-[date] ב-[time]. נתראה!") - ONLY for phone calls!
  (NO 'to' needed - auto-sends to customer!)
→ Hebrew Response DEPENDS ON CHANNEL:
  * IF PHONE CALL: "מעולה! קבעתי לך [treatment] ב-[date] ב-[time]. שלחתי אישור בווטסאפ."
  * IF WHATSAPP: "מעולה! קבעתי לך [treatment] ב-[date] ב-[time]. נתראה!" (already in WhatsApp!)

**2. INVOICE + PAYMENT WORKFLOW:**
When creating invoice:
→ invoices_create(customer_name="...", items=[...])
→ payments_link(invoice_id=X)
→ whatsapp_send(message="חשבונית: [total] ₪\nתשלום: [payment_url]")
→ Hebrew Response: "יצרתי חשבונית ושלחתי קישור תשלום בווטסאפ."

**3. CONTRACT WORKFLOW:**
When sending contract:
→ contracts_generate_and_send(template_id="...", variables={{...}})
→ whatsapp_send(message="חוזה מוכן לחתימה: [sign_url]")
→ Hebrew Response: "שלחתי לך חוזה לחתימה בווטסאפ."

**4. POST-CALL SUMMARY (PHONE CHANNEL ONLY):**
At end of phone conversation:
→ summarize_thread(source="call", source_id=call_sid)
→ whatsapp_send(message="תודה על השיחה! סיכום: [summary]")
→ Hebrew Response: "תודה! שלחתי לך סיכום בווטסאפ."

**CRITICAL:** whatsapp_send auto-detects recipient from context - NEVER specify 'to' parameter!

**5. LEAD-FIRST PRINCIPLE:**
BEFORE any appointment/invoice/contract:
→ Check if customer exists: leads_search(phone=customer_phone)
→ If not found: leads_upsert(name=..., phone=..., status="new")
→ Then proceed with the operation

⚠️ **KEY POINTS:**
- ALWAYS respond in Hebrew (no matter what language the user uses)
- Always verify with tools before confirming
- Keep it short and friendly
- Business hours: 09:00-22:00
- Never mention technical details or tool names
- If unsure → ASK instead of guessing

**CRITICAL: ALL RESPONSES MUST BE IN HEBREW. USE TOOLS FOR EVERYTHING. KEEP IT SHORT!**
"""

    # Prepare tools
    tools_to_use = [
        calendar_find_slots,
        calendar_create_appointment,
        leads_upsert,
        leads_search,
        invoices_create,
        payments_link,
        contracts_generate_and_send,
        whatsapp_send,
        summarize_thread
    ]
    
    # If business_id provided, could wrap tools here (similar to booking_agent)
    # For now, business_id will come from context
    
    try:
        agent = Agent(
            name=f"ops_agent_{business_name}",
            model="gpt-4o-mini",
            instructions=instructions,
            tools=tools_to_use,
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

    try:
        agent = Agent(
            name=f"sales_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",
            instructions=instructions,
            tools=[
                leads_upsert,
                leads_search,
                whatsapp_send
            ]
        )
        
        logger.info(f"✅ Created sales agent for '{business_name}' with 3 tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create sales agent: {e}")
        raise


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
            _agent_cache[cache_key] = create_booking_agent(business_name, None, business_id, channel)
        elif agent_type == "sales":
            _agent_cache[cache_key] = create_sales_agent(business_name)
        elif agent_type == "ops":
            _agent_cache[cache_key] = create_ops_agent(business_name, business_id, channel)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agent_cache[cache_key]
