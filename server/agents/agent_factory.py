"""
Agent Factory - Create and configure AI agents with tools
Integrates with OpenAI Agents SDK for production-ready agent capabilities
"""
import os
from datetime import datetime, timedelta
import pytz
from agents import Agent, ModelSettings
from server.agents.tools_calendar import calendar_find_slots, calendar_create_appointment
from server.agents.tools_leads import leads_upsert, leads_search
from server.agents.tools_whatsapp import whatsapp_send
from server.agents.tools_invoices import invoices_create, payments_link
from server.agents.tools_contracts import contracts_generate_and_send
from server.agents.tools_summarize import summarize_thread
import logging

logger = logging.getLogger(__name__)

# Check if agents are enabled
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "1") == "1"

# 🎯 Model settings for all agents - matching AgentKit best practices
AGENT_MODEL_SETTINGS = ModelSettings(
    model="gpt-4o-mini",  # Fast and cost-effective
    temperature=0.2,       # Low temperature for consistent, predictable responses
    max_tokens=350,        # Enough for detailed Hebrew responses
    tool_choice="required", # Always use tools (no text-only responses)
    parallel_tool_calls=True  # Enable parallel tool execution
)

def create_booking_agent(business_name: str = "העסק", custom_instructions: str = None, business_id: int = None, channel: str = "phone") -> Agent:
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
                
                # Check if result is error dict or success object
                if isinstance(result, dict):
                    # Error response from _calendar_create_appointment_impl
                    logger.warning(f"❌ calendar_create_appointment_wrapped returned error: {result}")
                    return result
                
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
    # 🎯 Different instructions for WhatsApp vs Phone calls!
    
    if channel == "whatsapp":
        # WhatsApp - NO DTMF, ask nicely for name and phone
        name_phone_instructions = """**🎯 STEP 1: GET NAME AND PHONE (Simple & Nice!):**
1. **Ask for BOTH name AND phone in ONE question**: "מעולה! על איזה שם לרשום ומה מספר הטלפון?"
   - Customer will write their name and phone in WhatsApp message
2. Wait for customer to provide both details
3. System will automatically capture the information from WhatsApp text"""
    else:
        # Phone calls - USE DTMF for phone number
        name_phone_instructions = """**🎯 STEP 1: GET NAME AND PHONE TOGETHER (MANDATORY!):**
1. **Ask for BOTH name AND phone in ONE question**: "מעולה! על איזה שם לרשום? ומספר טלפון - תקליד במקלדת והקש #"
   - Customer will say their name verbally
   - Customer will type phone on keypad and press #
2. Wait for customer to provide name (verbally) and phone (via DTMF keypad)
3. System will automatically capture DTMF digits when customer presses #"""
    
    date_context_prefix = f"""⏰ ⏰ ⏰ ULTRA CRITICAL - TIME CONVERSION (READ THIS FIRST!) ⏰ ⏰ ⏰

When customer says a NUMBER for appointment time, convert to 24-hour format:
- "2" or "שתיים" = 14:00 (2 PM in afternoon) - NEVER use 12:00!
- "3" or "שלוש" = 15:00 (3 PM)  
- "4" or "ארבע" = 16:00 (4 PM)
- "11:30" = 11:30 (keep exact time)
- "9 בבוקר" = 09:00 (morning)

MANDATORY RULE: Numbers 1-8 without "בבוקר" ALWAYS mean PM afternoon hours (13:00-20:00)!

EXAMPLES YOU MUST FOLLOW:
- Customer: "2" → calendar_create_appointment(start_iso="2025-11-05T14:00:00+02:00")
- Customer: "11:30" → calendar_create_appointment(start_iso="2025-11-05T11:30:00+02:00")
- Customer: "שתיים" → calendar_create_appointment(start_iso="2025-11-05T14:00:00+02:00")

---

📅 **CRITICAL DATE CONTEXT:**
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}, current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time.

When customer says "מחר" (tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
When customer says "מחרתיים" (day after tomorrow), that means: {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}

**ALWAYS use year 2025 for dates! Never use 2023 or 2024.**
Convert all dates to ISO format: YYYY-MM-DD (example: "2025-11-05")

⏰ **HEBREW TIME CONVERSION (24-HOUR FORMAT):**
When customer says time in Hebrew, convert to 24-hour format:
- "1" / "אחת" / "אחד בצהריים" = 13:00 (1 PM)
- "2" / "שתיים" / "שעתיים" / "שתים" = 14:00 (2 PM) ← THIS IS 2 PM, NOT 12 PM!
- "3" / "שלוש" = 15:00 (3 PM)
- "4" / "ארבע" = 16:00 (4 PM)
- "5" / "חמש" = 17:00 (5 PM)
- "9 בבוקר" / "9 AM" = 09:00
- "10 בבוקר" = 10:00
- "11 בבוקר" = 11:00
- "12 בצהריים" / "12 PM" = 12:00 (noon)

**EXAMPLES:**
- Customer: "שתיים" → Use "2025-11-05T14:00:00+02:00" (NOT 12:00!)
- Customer: "ארבע אחרי הצהריים" → Use "2025-11-05T16:00:00+02:00"
- Customer: "9 בבוקר" → Use "2025-11-05T09:00:00+02:00"

**CRITICAL:** In Israel, when people say a number 1-8 without "בבוקר", they mean PM (afternoon)!
Default assumption for 1-8: PM hours (13:00-20:00)

🎯 **IMPORTANT - When showing available times:**
- DON'T read ALL available times (boring and long!)
- DO mention 2-3 example times and ASK which time works
- Example: "יש פנוי מחר ב-09:00, 14:00 או אחה״צ. באיזו שעה נוח לך?" (Available tomorrow at 09:00, 14:00 or afternoon. What time works for you?)
- Keep responses SHORT (2-3 sentences max)

🚨 **CRITICAL - Smart Booking Flow:**

{name_phone_instructions}

**🎯 STEP 2: CONFIRM BOTH NAME AND PHONE:**
1. **CONFIRM by repeating BOTH name and phone**: "תודה! אז [שם], [מספר טלפון], נכון?"
   - Use the exact name customer provided
   - Use the exact phone number customer provided
2. Wait for confirmation ("כן" / "נכון" / "בסדר")
3. If customer corrects: "אה סליחה, מה השם הנכון?" or ask for correct phone
4. **DON'T proceed without clear confirmation of BOTH!**

**Special cases:**
- **IF phone was captured from call context (customer_phone in context):** Still ask for name, but use customer_phone="" in tool
- **IF customer refuses to give phone:** That's OK! Proceed with customer_phone="" (phone is optional)

**🎯 STEP 3: BOOK IMMEDIATELY AFTER NAME CONFIRMATION (MANDATORY!):**
1. After customer confirms name with "כן":
   - **IMMEDIATELY call** `calendar_create_appointment_wrapped` - THIS IS MANDATORY!
   - You MUST call the tool to actually create the appointment
   - DO NOT ask for time confirmation again - time was already discussed!
   - **CRITICAL TIMEZONE:** Use Asia/Jerusalem timezone in ISO format: "2025-11-05T12:00:00+02:00"
   - Example parameters:
     * treatment_type: "עיסוי שוודי"
     * start_iso: "2025-11-05T12:00:00+02:00" (EXACT time from conversation in Israel timezone!)
     * end_iso: "2025-11-05T13:00:00+02:00" (EXACT end time in Israel timezone!)
     * customer_phone: "050-1234567" or "" if from call or if customer refused
     * customer_name: "דני" (confirmed name!)
2. After tool returns ok=True, say: "מעולה! קבעתי לך תור ל[תאריך] ב-[שעה]. נתראה!"
   - Use PAST tense "קבעתי" (I booked) - the appointment is already created!
3. If tool returns ok=False with error message - ask customer for alternative time and retry

**KEY RULES:**
- ✅ ALWAYS ask for name AND phone TOGETHER (format depends on channel)
- ✅ ALWAYS confirm BOTH by repeating name and phone
- ✅ MANDATORY: After customer confirms with "כן" → IMMEDIATELY call calendar_create_appointment_wrapped
- ✅ Use EXACT times in ISO format with +02:00 or +03:00 timezone (Asia/Jerusalem)
- ✅ Phone is OPTIONAL - can proceed without phone if customer refuses
- ✅ After tool succeeds, use PAST tense: "מעולה! קבעתי לך תור למחר ב-14:00. נתראה!"
- ❌ NEVER book without clear name (reject "לקוח" / "customer" / generic names)
- ❌ NEVER ask for time confirmation again after name+phone confirmed - just book it!
- ❌ NEVER skip calling calendar_create_appointment_wrapped after customer confirms!
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
        
        # Different name/phone instructions based on channel
        if channel == "whatsapp":
            default_name_phone_rule = """2. **NAME AND PHONE COLLECTION (ASK TOGETHER!):**
   - ALWAYS ask for BOTH name AND phone in ONE question: "מעולה! על איזה שם לרשום ומה מספר הטלפון?"
   - Customer will write their name and phone in WhatsApp message
   - ALWAYS confirm BOTH by repeating: "תודה! אז [שם], [מספר], נכון?"
   - Name is MANDATORY, phone is OPTIONAL (can proceed without phone if customer refuses)
   - Both must be confirmed before booking"""
        else:
            default_name_phone_rule = """2. **NAME AND PHONE COLLECTION (ASK TOGETHER!):**
   - ALWAYS ask for BOTH name AND phone in ONE question: "על איזה שם לרשום? ומספר טלפון - תקליד במקלדת והקש #"
   - Customer says name verbally + types phone on keypad + presses #
   - System captures DTMF phone automatically
   - ALWAYS confirm BOTH by repeating: "תודה! אז [שם], [מספר], נכון?"
   - Name is MANDATORY, phone is OPTIONAL (can proceed without phone if customer refuses)
   - Both must be confirmed before booking"""
        
        instructions = f"""You are a booking agent for {business_name}. Always respond in Hebrew.

📅 **DATE CONTEXT:**
Today is {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%Y-%m-%d (%A)')}, current time: {datetime.now(tz=pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')} Israel time.
- "מחר" (tomorrow) = {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=1)).strftime('%Y-%m-%d')}
- "מחרתיים" (day after tomorrow) = {(datetime.now(tz=pytz.timezone('Asia/Jerusalem')) + timedelta(days=2)).strftime('%Y-%m-%d')}
ALWAYS use year 2025 for dates! Convert to ISO: YYYY-MM-DD.

⏰ **CRITICAL - HEBREW TIME CONVERSION (24-HOUR FORMAT):**
When customer says time in Hebrew, convert to 24-hour format:
- "1" / "אחת" / "אחד בצהריים" = 13:00 (1 PM)
- "2" / "שתיים" / "שעתיים" / "שתים" = 14:00 (2 PM) ← THIS IS 2 PM, NOT 12 PM!
- "3" / "שלוש" = 15:00 (3 PM)
- "4" / "ארבע" = 16:00 (4 PM)
- "5" / "חמש" = 17:00 (5 PM)
- "9 בבוקר" / "9 AM" = 09:00
- "10 בבוקר" = 10:00
- "11 בבוקר" = 11:00
- "12 בצהריים" / "12 PM" = 12:00 (noon)

**EXAMPLES:**
- Customer: "שתיים" → Use "2025-11-05T14:00:00+02:00" (NOT 12:00!)
- Customer: "ארבע אחרי הצהריים" → Use "2025-11-05T16:00:00+02:00"
- Customer: "9 בבוקר" → Use "2025-11-05T09:00:00+02:00"

**CRITICAL:** In Israel, when people say a number 1-8 without "בבוקר", they mean PM (afternoon)!
Default assumption for 1-8: PM hours (13:00-20:00)

🚨 **CRITICAL RULES:**

1. **TOOL USAGE IS MANDATORY:**
   - NEVER claim availability without calling calendar_find_slots_wrapped first
   - NEVER say "אין זמינות" without checking the tool
   - When customer asks for appointment → MUST call calendar_find_slots_wrapped

{default_name_phone_rule}

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

5. **BOOKING FLOW WITH AUTO-AUTOMATION:**
   - Customer asks for appointment → Call calendar_find_slots_wrapped
   - Show 2-3 available times (not all!)
   - Customer picks time → Ask for name (phone auto-captured)
   - CONFIRM: "תודה! אז [שם], נכון?"
   - Wait for "כן"
   - **AUTOMATION SEQUENCE (DO NOT ASK - JUST EXECUTE):**
     1. calendar_create_appointment_wrapped(...)
     2. leads_upsert_wrapped(name=..., phone=..., notes="Appointment booked")
     3. whatsapp_send(text="✅ אישור: [טיפול] ב-[תאריך] ב-[שעה]. נתראה!")
   - Response: "מעולה! קבעתי לך תור ושלחתי אישור בווטסאפ."
   - **AUTOMATION HAPPENS AUTOMATICALLY - USER DOESN'T REQUEST IT!**

📋 **EXAMPLE FLOW (ASK NAME AND PHONE TOGETHER):**

Turn 1: Customer: "תבדוק למחר עיסוי"
→ Call calendar_find_slots_wrapped(date_iso="2025-11-05", duration_min=60)
→ Response: "יש פנוי מחר ב-09:00, 14:00 או 16:00. מה מתאים?"

Turn 2: Customer: "שתיים" or "2"
→ **UNDERSTAND: "2" = 14:00 (2 PM, NOT 12:00!)**
→ Response: "מעולה! על איזה שם לרשום? ומספר טלפון - תקליד במקלדת והקש #"

Turn 3: Customer: "שי דהן" + [types 0501234567# on keypad]
→ System receives name: "שי דהן" and DTMF: "0501234567"
→ Response: "תודה שי! אז שי דהן, 050-1234567, נכון?"

Turn 4: Customer: "כן"
→ **AUTOMATION SEQUENCE:**
  1. calendar_create_appointment_wrapped(treatment="עיסוי", start="2025-11-05T14:00:00+02:00", ...)
  2. leads_upsert_wrapped(name="שי דהן", phone="0501234567", notes="Appointment: עיסוי on 2025-11-05")
  3. whatsapp_send(message="✅ אישור: עיסוי מחר ב-14:00. נתראה!")
     (NO 'to' needed - auto-detected!)
→ Response: "מעולה שי! קבעתי לך תור למחר ב-14:00 ושלחתי אישור בווטסאפ."

⚠️ **KEY POINTS:**
- Business hours: 09:00-22:00 Israel time
- Keep responses SHORT (1-2 sentences max!)
- Never mention tools to customer
- Always respond in Hebrew
- If unsure about date - ASK instead of guessing
- **AUTOMATION:** After booking → ALWAYS call leads_upsert + whatsapp_send (NO ASKING!)
- **AUTOMATION HAPPENS AUTOMATICALLY** - customer doesn't need to request it!
- Phone auto-captured from context - no need to ask verbally
- Ask for name only, confirm, then execute 3-step automation sequence

**CRITICAL: AFTER CONFIRMATION → RUN AUTOMATION (appointment + lead + whatsapp) AUTOMATICALLY!**
**ALWAYS RESPOND IN HEBREW. AUTOMATION IS MANDATORY - DON'T ASK FOR PERMISSION!**
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
        
        # ⚡ CRITICAL: Add model_settings with timeout for fast responses!
        from agents import ModelSettings
        
        model_settings = ModelSettings(
            max_tokens=300,  # Limit response length for speed
            temperature=0.3,  # Lower temperature for faster, more focused responses
        )
        
        agent = Agent(
            name=f"booking_agent_{business_name}",  # Required: Agent name
            model="gpt-4o-mini",  # ⚡ Fast model for real-time conversations
            instructions=instructions,
            tools=tools_to_use,  # Use wrapped or original tools based on business_id
            model_settings=model_settings  # ⚡ Performance settings
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
→ whatsapp_send(message="✅ אישור: [treatment] ב-[date] ב-[time]. נתראה!")
  (NO 'to' needed - auto-sends to customer!)
→ Hebrew Response: "מעולה! קבעתי לך [treatment] ב-[date] ב-[time]. שלחתי אישור בווטסאפ."

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
