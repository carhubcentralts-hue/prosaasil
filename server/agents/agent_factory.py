"""
Agent Factory - Create and configure AI agents with tools
Integrates with OpenAI Agents SDK for production-ready agent capabilities
"""
import os
from openai_agents import Agent
from server.agents.tools_calendar import calendar_find_slots, calendar_create_appointment
from server.agents.tools_leads import leads_upsert, leads_search
from server.agents.tools_whatsapp import whatsapp_send
import logging

logger = logging.getLogger(__name__)

# Check if agents are enabled
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "1") == "1"

def create_booking_agent(business_name: str = "העסק") -> Agent:
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
    
    Returns:
        Configured Agent ready to handle booking requests
    """
    if not AGENTS_ENABLED:
        logger.warning("Agents are disabled (AGENTS_ENABLED=0)")
        return None
    
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
            model="gpt-4o-mini",  # ⚡ Fast model for real-time conversations
            instructions=instructions,
            tools=[
                calendar_find_slots,
                calendar_create_appointment,
                leads_upsert,
                leads_search,
                whatsapp_send
            ],
            strict=True  # ⚡ Enforce schema validation
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
            model="gpt-4o-mini",
            instructions=instructions,
            tools=[
                leads_upsert,
                leads_search,
                whatsapp_send
            ],
            strict=True
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

def get_agent(agent_type: str = "booking", business_name: str = "העסק") -> Agent:
    """
    Get or create an agent by type
    
    Args:
        agent_type: Type of agent (booking/sales)
        business_name: Business name for personalization
    
    Returns:
        Agent instance (cached)
    """
    cache_key = f"{agent_type}:{business_name}"
    
    if cache_key not in _agent_cache:
        if agent_type == "booking":
            _agent_cache[cache_key] = create_booking_agent(business_name)
        elif agent_type == "sales":
            _agent_cache[cache_key] = create_sales_agent(business_name)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
    
    return _agent_cache[cache_key]
