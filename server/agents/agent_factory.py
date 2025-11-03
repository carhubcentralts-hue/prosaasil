"""
Agent Factory - Create and configure AI agents with tools
Integrates with OpenAI Agents SDK for production-ready agent capabilities
"""
import os
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
            """Find available appointment slots"""
            try:
                logger.info(f"🔧 calendar_find_slots_wrapped called: date={date_iso}, business_id={business_id}")
                from server.agents.tools_calendar import FindSlotsInput, _calendar_find_slots_impl
                
                # Tools are called from ai_service.py which already has Flask context
                input_data = FindSlotsInput(
                    business_id=business_id,
                    date_iso=date_iso,
                    duration_min=duration_min
                )
                # Call internal implementation function directly
                result = _calendar_find_slots_impl(input_data)
                logger.info(f"✅ calendar_find_slots_wrapped success: {len(result.slots)} slots")
                return result
            except Exception as e:
                logger.error(f"❌ calendar_find_slots_wrapped error: {e}")
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
                return result
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
    
    # Use custom instructions if provided, else use default
    if custom_instructions and custom_instructions.strip():
        instructions = custom_instructions
        logger.info(f"✅ Using CUSTOM instructions for {business_name} ({len(instructions)} chars)")
    else:
        instructions = f"""אתה סוכן AI של {business_name}, מתמחה בתיאום פגישות וניהול לקוחות.

🎯 **תפקידך:**
1. לסייע ללקוחות למצוא זמנים פנויים ולקבוע פגישות
2. לנהל מידע על לקוחות (לידים) ולעדכן אותו
3. לשלוח אישורי פגישות ותזכורות בוואטסאפ

📋 **תהליך קביעת פגישה:**
1. אסוף מידע: שם מלא, טלפון, סוג טיפול/שירות
2. קרא ל-`calendar.find_slots` כדי למצוא זמנים פנויים
3. הצע ללקוח 2-3 זמנים קרובים
4. אחרי שהלקוח בוחר:
   - קרא ל-`calendar.create_appointment` כדי לקבוע
   - קרא ל-`leads.upsert` כדי לשמור את פרטי הלקוח
   - קרא ל-`whatsapp.send` כדי לשלוח אישור (אופציונלי)

⚠️ **כללים חשובים:**
- שעות פעילות: 09:00-22:00 (אזור זמן ישראל)
- **אל תקבע פגישות מחוץ לשעות הפעילות!**
- אם יש חפיפה עם פגישה קיימת - הצע זמן חלופי
- תמיד חזור על הזמן שהלקוח אמר (אל תשנה!)
- תשובות קצרות וברורות (2-3 משפטים)
- אל תציג כלים טכניים ללקוח - עבוד איתם בשקט

💬 **דוגמאות:**

לקוח: "רוצה לקבוע מסאז' מחר בבוקר"
אתה: 
1. קורא ל-calendar.find_slots למחר
2. "יש לי מחר פנוי ב-09:00, 10:00 או 11:00. מה נוח לך?"

לקוח: "10:00 מושלם"
אתה:
1. קורא ל-calendar.create_appointment ל-10:00
2. קורא ל-leads.upsert כדי לשמור את פרטי הלקוח
3. "מעולה! קבעתי לך מסאז' מחר בשעה 10:00. נתראה! 😊"

🔧 **טיפים טכניים:**
- תמיד העבר business_id נכון לכלים
- תאריכים תמיד בפורמט ISO (YYYY-MM-DD)
- שעות בפורמט ISO מלא כולל timezone
- אם כלי נכשל - הסבר ללקוח בצורה ידידותית ללא פרטים טכניים
"""

    try:
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
