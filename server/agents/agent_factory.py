"""
Agent Factory - Create and configure AI agents with tools
Integrates with OpenAI Agents SDK for production-ready agent capabilities
"""
import os
from datetime import datetime, timedelta
import pytz
from agents import Agent
from server.agents.tools_calendar import calendar_find_slots, calendar_create_appointment
from server.agents.tools_leads import leads_upsert, leads_search
from server.agents.tools_whatsapp import whatsapp_send
import logging

logger = logging.getLogger(__name__)

# Check if agents are enabled
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "1") == "1"

def create_booking_agent(business_name: str = "העסק", custom_instructions: str = None, business_id: int = None) -> Agent:
    """
    Create an agent specialized in appointment booking and customer management
    
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
                
                from server.agents.tools_calendar import FindSlotsInput, _calendar_find_slots_impl
                
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
                logger.error(f"❌ calendar_find_slots_wrapped FAILED: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        # Wrapper for calendar_create_appointment  
        @function_tool
        def calendar_create_appointment_wrapped(
            customer_name: str,
            customer_phone: str, 
            treatment_type: str,
            start_iso: str,
            end_iso: str,
            notes: str = None
        ):
            """Create a new appointment"""
            try:
                logger.info(f"🔧 calendar_create_appointment_wrapped called: {customer_name}, business_id={business_id}")
                from server.agents.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
                
                # Tools are called from ai_service.py which already has Flask context
                input_data = CreateAppointmentInput(
                    business_id=business_id,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    treatment_type=treatment_type,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    notes=notes,
                    source="ai_agent"
                )
                # Call internal implementation function directly
                result = _calendar_create_appointment_impl(input_data)
                logger.info(f"✅ calendar_create_appointment_wrapped success: appointment_id={result.appointment_id}")
                # Convert Pydantic model to dict for Agent SDK
                return result.model_dump()
            except Exception as e:
                logger.error(f"❌ calendar_create_appointment_wrapped error: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        # Wrapper for leads_upsert (simple implementation - creates lead directly)
        @function_tool
        def leads_upsert_wrapped(phone_e164: str, name: str = None, notes: str = None):
            """Create or update customer lead"""
            try:
                logger.info(f"🔧 leads_upsert_wrapped called: {phone_e164}, business_id={business_id}")
                from server.models_sql import db, Lead
                from datetime import datetime
                
                # Normalize phone to E.164 format
                phone = phone_e164.strip()
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
                logger.error(f"❌ leads_upsert_wrapped error: {e}")
                db.session.rollback()
                import traceback
                traceback.print_exc()
                raise
        
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
    
    # CRITICAL: Always add date context prefix, even for custom instructions!
    date_context_prefix = f"""📅 **CRITICAL DATE CONTEXT:**
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}, current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time.

When customer says "מחר" (tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
When customer says "מחרתיים" (day after tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}

**ALWAYS use year 2025 for dates! Never use 2023 or 2024.**
Convert all dates to ISO format: YYYY-MM-DD (example: "2025-11-05")

---

"""
    
    # Use custom instructions if provided, else use default
    if custom_instructions and custom_instructions.strip():
        # Prepend date context to custom instructions
        instructions = date_context_prefix + custom_instructions
        print(f"\n🔥 PREPENDING DATE PREFIX TO CUSTOM INSTRUCTIONS!")
        print(f"   Prefix length: {len(date_context_prefix)} chars")
        print(f"   Custom length: {len(custom_instructions)} chars")
        print(f"   Total: {len(instructions)} chars")
        print(f"   First 200 chars of result: {instructions[:200]}")
        logger.info(f"✅ Using CUSTOM instructions for {business_name} ({len(custom_instructions)} chars) + date prefix")
    else:
        # CRITICAL: Instructions in ENGLISH for Agent SDK to understand properly!
        # The agent will still respond in Hebrew to customers.
        instructions = f"""You are an AI booking agent for {business_name}, specializing in appointment scheduling and customer management.

🚨 **CRITICAL RULE - YOU MUST ALWAYS CALL TOOLS:**
NEVER answer availability questions without checking the calendar first!

**When to call calendar_find_slots_wrapped:**
- Customer asks "יש פנוי ב...?" (is there availability on...?) → CALL calendar_find_slots_wrapped
- Customer says "תבדוק לי..." (check for me...) → CALL calendar_find_slots_wrapped
- Customer mentions "מחר" (tomorrow), "שבוע הבא" (next week), or any date → CALL calendar_find_slots_wrapped
- Customer wants to book → FIRST call calendar_find_slots_wrapped to check availability
- **NEVER say "אין זמינות" (no availability) without calling the tool first!**

📅 **Date Parsing (Hebrew to ISO):**
**CRITICAL: Today's date is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}**
Current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time

Date calculations:
- "מחר" (tomorrow) → {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
- "מחרתיים" (day after tomorrow) → {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}
- "יום ראשון" (Sunday) → next Sunday from today's date
- "שבוע הבא" (next week) → add 7 days to current date
- "ב-10" (on the 10th) → this month's 10th, or next month if passed

**ALWAYS use year 2025** for dates! Do not use 2023 or 2024.
Always convert to ISO format: YYYY-MM-DD

📋 **Booking Flow:**
1. Parse the requested date from customer message (if unclear - ASK!)
2. **MANDATORY:** Call calendar_find_slots_wrapped with date_iso (YYYY-MM-DD)
3. Show customer 2-3 available times from the results
4. After customer chooses:
   - Call calendar_create_appointment_wrapped
   - Call leads_upsert_wrapped
   - Confirm warmly in Hebrew

⚠️ **Important Rules:**
- Business hours: 09:00-22:00 (Israel timezone)
- NEVER book appointments outside these hours!
- If calendar_find_slots_wrapped returns empty list → truly no availability
- Always repeat the exact time customer said (don't change!)
- Keep responses short and clear (2-3 sentences in Hebrew)
- Don't mention technical tools to customer - work with them silently

💬 **Example Flow:**

Customer: "תבדוק לי למחר עיסוי שוודי" (check tomorrow for Swedish massage)
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d')}, so tomorrow = {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
→ CALL calendar_find_slots_wrapped(date_iso="{(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}", duration_min=60)
→ Receive results: {{'slots': [{{'start_display': '09:00'}}, {{'start_display': '10:00'}}], 'business_hours': '09:00-22:00'}}
You respond: "יש לי פנוי מחר ב-09:00, 10:00, 11:00 או 14:00. מה מתאים לך?" (I have available tomorrow at...)

Customer: "10:00 מעולה" (10:00 is great)
→ CALL calendar_create_appointment_wrapped(start_iso="{(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}T10:00:00+02:00", ...)
→ CALL leads_upsert_wrapped(...)
You respond: "מעולה! קבעתי לך עיסוי שוודי למחר בשעה 10:00. נתראה!" (Great! I booked you...)

🔧 **Technical Details:**
- Dates always in ISO format: "2025-11-10" (not "ראשון" or "10/11")
- Times for calendar in full ISO format: "2025-11-10T10:00:00+02:00"
- If tool fails - explain to customer kindly in Hebrew without technical details
- If unsure about date - ASK customer instead of guessing!

**RESPOND TO CUSTOMERS IN HEBREW, BUT ALWAYS CALL THE TOOLS!**
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
        
        agent = Agent(
            name=f"booking_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",  # ⚡ Fast model for real-time conversations
            instructions=instructions,
            tools=tools_to_use  # Use wrapped or original tools based on business_id
        )
        
        logger.info(f"✅ Created booking agent for '{business_name}' with 5 tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
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
    
    instructions = f"""אתה סוכן מכירות של {business_name}.

🎯 **תפקידך:**
1. לזהות לקוחות פוטנציאליים (לידים) ולרשום אותם
2. לאסוף מידע רלוונטי: שם, טלפון, צרכים, תקציב
3. לסווג לידים לפי סטטוס: new/contacted/qualified/won
4. לתאם המשך טיפול

📋 **תהליך טיפול בליד:**
1. שאלות מכוונות: "מה אתה מחפש?", "באיזה אזור?", "מה התקציב?"
2. שמור מידע: קרא ל-`leads.upsert` עם כל הפרטים
3. סכם את השיחה ב-summary קצר (10-30 מילים)
4. הצע המשך טיפול או פגישה

💬 **סגנון דיבור:**
- חם, מקצועי, לא לוחץ
- שאלות פתוחות
- תשובות קצרות וממוקדות
- הקשבה אקטיבית
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

def get_agent(agent_type: str = "booking", business_name: str = "העסק", custom_instructions: str = None, business_id: int = None) -> Agent:
    """
    Get or create an agent by type
    
    Args:
        agent_type: Type of agent (booking/sales)
        business_name: Business name for personalization
        custom_instructions: Custom instructions from database (if provided, creates new agent)
        business_id: Business ID for tool calls (required for booking agent)
    
    Returns:
        Agent instance (cached unless custom_instructions provided)
    """
    # 🎯 If custom instructions provided, always create fresh agent (don't cache)
    if custom_instructions and isinstance(custom_instructions, str) and custom_instructions.strip():
        logger.info(f"Creating fresh agent with custom instructions ({len(custom_instructions)} chars)")
        if agent_type == "booking":
            return create_booking_agent(business_name, custom_instructions, business_id)
        elif agent_type == "sales":
            return create_sales_agent(business_name)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    # Otherwise use cached agent
    cache_key = f"{agent_type}:{business_name}:{business_id}"
    
    if cache_key not in _agent_cache:
        if agent_type == "booking":
            _agent_cache[cache_key] = create_booking_agent(business_name, None, business_id)
        elif agent_type == "sales":
            _agent_cache[cache_key] = create_sales_agent(business_name)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agent_cache[cache_key]
