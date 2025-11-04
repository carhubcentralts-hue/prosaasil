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
                
                from server.agents.tools_calendar import CreateAppointmentInput, _calendar_create_appointment_impl
                from flask import g
                
                # Get context and session for _choose_phone
                context = getattr(g, 'agent_context', None)
                session = None  # TODO: pass session if available
                
                # Build input - _choose_phone will handle phone fallback
                input_data = CreateAppointmentInput(
                    business_id=business_id,
                    customer_name=customer_name or "לקוח",
                    customer_phone=customer_phone,  # Can be empty
                    treatment_type=treatment_type,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    notes=notes,
                    source="ai_agent"
                )
                
                logger.info(f"🔧 calendar_create_appointment_wrapped: {customer_name}, phone={customer_phone}, business_id={business_id}")
                
                # Call internal implementation with context/session
                result = _calendar_create_appointment_impl(input_data, context=context, session=session)
                logger.info(f"✅ calendar_create_appointment_wrapped success: appointment_id={result.appointment_id}")
                
                # Return success response
                return {
                    "ok": True,
                    "appointment_id": result.appointment_id,
                    "status": result.status,
                    "confirmation_message": result.confirmation_message
                }
                
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
    
    # CRITICAL: Always add date context prefix, even for custom instructions!
    date_context_prefix = f"""📅 **CRITICAL DATE CONTEXT:**
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}, current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time.

When customer says "מחר" (tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
When customer says "מחרתיים" (day after tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}

**ALWAYS use year 2025 for dates! Never use 2023 or 2024.**
Convert all dates to ISO format: YYYY-MM-DD (example: "2025-11-05")

🎯 **IMPORTANT - When showing available times:**
- DON'T read ALL available times (boring and long!)
- DO mention 2-3 example times and ASK which time works
- Example: "יש פנוי מחר ב-09:00, 14:00 או אחה״צ. באיזו שעה נוח לך?" (Available tomorrow at 09:00, 14:00 or afternoon. What time works for you?)
- Keep responses SHORT (2-3 sentences max)

🚨 **CRITICAL - Smart Booking Flow:**

**🎯 STEP 1: GET CLEAR NAME (MANDATORY!):**
1. Ask for name: "מעולה! על איזה שם לרשום?" (Great! What name to book under?)
2. Customer gives name: "דני"
3. **CONFIRM NAME by repeating it**: "תודה דני! אז דני, נכון?" (Thanks Danny! So Danny, correct?)
4. Wait for confirmation ("כן" / "נכון" / "כן כן")
5. If customer corrects: "אה סליחה, אז על שם...?" and repeat step 3
6. **DON'T proceed without clear name confirmation!**

**🎯 STEP 2: GET PHONE NUMBER:**
**IF phone was captured from call (customer_phone in context):**
- Skip this step entirely
- Use customer_phone="" in the tool call

**IF no phone in context (customer_phone is empty/missing):**
- Say: "איזה מספר טלפון להשאיר?" (What phone number to leave?)
- Customer gives phone: "050-1234567" or "חמש אפס אחת שתיים שלוש ארבע חמש שש שבע"
- **CONFIRM PHONE by repeating it**: "מצוין! אז המספר הוא 050-1234567, נכון?"
- Wait for confirmation
- Use the confirmed phone in customer_phone parameter

**🎯 STEP 3: CONFIRM TIME AND BOOK:**
1. **Repeat the EXACT time**: "אז קבעתי לך תור למחר ב-12:00, נכון?"
   - Always use specific day and time, not generic placeholders
2. Wait for final confirmation
3. **ONLY THEN call** `calendar_create_appointment_wrapped`:
   - treatment_type: "עיסוי שוודי"
   - start_iso: "2025-11-05T12:00:00+02:00" (EXACT time!)
   - end_iso: "2025-11-05T13:00:00+02:00" (EXACT end time!)
   - customer_phone: "050-1234567" or "" if from call
   - customer_name: "דני" (confirmed name!)
4. After booking success, say: "מעולה דני! קבעתי לך תור למחר ב-12:00. המספר שלך הוא 050-1234567. נתראה!"

**KEY RULES:**
- ✅ ALWAYS confirm name by repeating it ("תודה דני!")
- ✅ ALWAYS ask for phone if not in call context
- ✅ ALWAYS confirm phone by repeating it
- ✅ ALWAYS confirm exact time before booking
- ✅ Use EXACT times in ISO format (never approximate!)
- ❌ NEVER book without clear name
- ❌ NEVER book without phone (from call OR asked)
- ❌ NEVER say "אני לא מבין" - ask politely to repeat

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
        # CRITICAL: Instructions in ENGLISH for Agent SDK (better understanding)
        # Agent MUST always respond in HEBREW to customers
        instructions = f"""You are a booking agent for {business_name}. Always respond in Hebrew.

📅 **DATE CONTEXT:**
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}, current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time.
- "מחר" (tomorrow) = {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
- "מחרתיים" (day after tomorrow) = {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}
ALWAYS use year 2025 for dates! Convert to ISO: YYYY-MM-DD.

🚨 **CRITICAL RULES:**

1. **TOOL USAGE IS MANDATORY:**
   - NEVER claim availability without calling calendar_find_slots_wrapped first
   - NEVER say "אין זמינות" without checking the tool
   - When customer asks for appointment → MUST call calendar_find_slots_wrapped

2. **NAME AND PHONE COLLECTION:**
   - ALWAYS ask for customer name: "על איזה שם לרשום?"
   - ALWAYS confirm name by repeating: "תודה דני! אז דני, נכון?"
   - IF customer_phone exists in context (from call): Use customer_phone="" in tool
   - IF customer_phone is missing/empty: Say "תקליד את המספר טלפון במקלדת ואחרי זה תקיש סולמית (#)"
   - After customer types digits + #: Confirm by repeating the number received
   - NEVER book without clear name AND phone number
   - Name and phone must be confirmed before booking

3. **ERROR HANDLING:**
   - If a tool returns ok=false or error=validation_error:
     - Ask ONE brief clarification question in Hebrew
     - Retry the tool with corrected parameters
   - Never tell customer about technical errors - handle gracefully

4. **CONVERSATION CONTINUITY:**
   - If this is NOT the first user turn in messages:
     - Do NOT greet again
     - Continue the current flow and complete any missing information
   - Check message history before responding

5. **BOOKING FLOW:**
   - Customer asks for appointment → Call calendar_find_slots_wrapped
   - Show 2-3 available times (not all!)
   - Customer picks time → Ask for name: "על איזה שם לרשום?"
   - Customer gives name → CONFIRM: "תודה דני! אז דני, נכון?"
   - Wait for confirmation
   - IF no phone in context → Say: "תקליד את המספר טלפון במקלדת ואחרי זה תקיש סולמית (#)" → Wait for DTMF input → CONFIRM by repeating
   - ONLY after name AND phone confirmed → Call calendar_create_appointment_wrapped
   - Confirm warmly with ALL details: "מעולה דני! קבעתי לך תור למחר ב-12:00. המספר: 050-1234567"

📋 **EXAMPLE FLOW (WITH PHONE FROM CALL):**

Turn 1: Customer: "תבדוק למחר עיסוי"
→ Call calendar_find_slots_wrapped(date_iso="2025-11-05", duration_min=60)
→ Response: "יש פנוי מחר ב-09:00, 12:00 או 16:00. מה מתאים?"

Turn 2: Customer: "12:00"
→ Response: "מעולה! על איזה שם לרשום?"

Turn 3: Customer: "דני"
→ Response: "תודה דני! אז דני, נכון?"

Turn 4: Customer: "כן"
→ Call calendar_create_appointment_wrapped(
    treatment_type="עיסוי",
    start_iso="2025-11-05T12:00:00+02:00",
    end_iso="2025-11-05T13:00:00+02:00",
    customer_phone="",  # Empty - from call context
    customer_name="דני"
  )
→ Response: "מעולה דני! קבעתי לך תור למחר ב-12:00. נתראה!"

📋 **EXAMPLE FLOW (WITHOUT PHONE - MUST ASK):**

Turn 1-4: [Same as above until name confirmed]

Turn 5: [After name confirmed, NO phone in context]
→ Response: "תקליד את המספר טלפון במקלדת ואחרי זה תקיש סולמית (#)"

Turn 6: Customer: [types 0501234567# on keypad]
→ System receives: "0501234567"
→ Response: "מצוין! אז המספר הוא 050-1234567, נכון?"

Turn 7: Customer: "כן"
→ Call calendar_create_appointment_wrapped(
    treatment_type="עיסוי",
    start_iso="2025-11-05T12:00:00+02:00",
    end_iso="2025-11-05T13:00:00+02:00",
    customer_phone="0501234567",
    customer_name="דני"
  )
→ Response: "מעולה דני! קבעתי לך תור למחר ב-12:00. המספר שלך: 050-1234567. נתראה!"

⚠️ **KEY POINTS:**
- Business hours: 09:00-22:00 Israel time
- Keep responses SHORT (2-3 sentences)
- Never mention tools to customer
- Always respond in Hebrew
- If unsure about date - ASK instead of guessing

**ALWAYS RESPOND IN HEBREW. ALWAYS USE TOOLS.**
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
