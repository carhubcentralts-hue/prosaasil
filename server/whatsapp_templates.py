"""
WhatsApp Template Management and 24-hour Window Rules
ניהול תבניות WhatsApp וחוקי חלון 24 שעות
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from server.dao_crm import get_thread_by_peer

logger = logging.getLogger(__name__)

# Template definitions for Hebrew real estate agent "Leah"
APPROVED_TEMPLATES = {
    "welcome_first": {
        "name": "welcome_first_time",
        "category": "MARKETING",
        "language": "he",
        "text": "שלום {{1}}! אני לאה מ*שי דירות ומשרדים*. ראיתי שפניתם אלינו - איך אוכל לעזור לכם למצוא את הנכס המושלם? 🏠",
        "components": [
            {
                "type": "BODY",
                "parameters": [{"type": "TEXT", "text": "{{customer_name}}"}]
            }
        ]
    },
    "property_match": {
        "name": "property_match_found", 
        "category": "UTILITY",
        "language": "he", 
        "text": "מצאתי {{1}} נכסים מתאימים באזור {{2}} בתקציב {{3}}! האם תרצו לקבל פרטים? תוכלו לענות כן/לא",
        "components": [
            {
                "type": "BODY",
                "parameters": [
                    {"type": "TEXT", "text": "{{num_properties}}"},
                    {"type": "TEXT", "text": "{{area}}"},
                    {"type": "TEXT", "text": "{{budget}}"}
                ]
            }
        ]
    },
    "appointment_reminder": {
        "name": "appointment_reminder",
        "category": "UTILITY", 
        "language": "he",
        "text": "היי {{1}}! תזכורת לפגישה שלנו מחר ב{{2}} באזור {{3}}. האם הזמן עדיין מתאים לכם?",
        "components": [
            {
                "type": "BODY", 
                "parameters": [
                    {"type": "TEXT", "text": "{{customer_name}}"},
                    {"type": "TEXT", "text": "{{time}}"},
                    {"type": "TEXT", "text": "{{area}}"}
                ]
            }
        ]
    },
    "follow_up_cold": {
        "name": "follow_up_after_silence",
        "category": "MARKETING",
        "language": "he",
        "text": "שלום {{1}}, עבר זמן מאז שדיברנו על חיפוש הנכס שלכם באזור {{2}}. יש לנו הצעות חדשות! האם עדיין מתאים לכם שנעדכן?",
        "components": [
            {
                "type": "BODY",
                "parameters": [
                    {"type": "TEXT", "text": "{{customer_name}}"},
                    {"type": "TEXT", "text": "{{area}}"}
                ]
            }
        ]
    }
}

class WhatsAppWindowManager:
    """Manages 24-hour messaging window rules and template requirements"""
    
    def __init__(self):
        self.business_initiated_window = timedelta(hours=24)
        
    def check_messaging_window(self, business_id: int, peer_number: str) -> Dict[str, Any]:
        """
        Check if we're within the 24-hour messaging window
        Returns window status and required action
        """
        try:
            # Get thread data with last user message
            thread_data = get_thread_by_peer(business_id, "whatsapp", peer_number)
            
            if not thread_data:
                return {
                    "within_window": False,
                    "requires_template": True,
                    "reason": "no_prior_conversation",
                    "window_closed_at": None
                }
            
            last_user_msg_time = thread_data.get("last_user_message_time")
            
            if not last_user_msg_time:
                return {
                    "within_window": False, 
                    "requires_template": True,
                    "reason": "no_user_messages",
                    "window_closed_at": None
                }
            
            # Check if within 24-hour window
            now = datetime.now()
            if isinstance(last_user_msg_time, str):
                last_user_msg_time = datetime.fromisoformat(last_user_msg_time.replace('Z', '+00:00'))
            
            time_diff = now - last_user_msg_time
            within_window = time_diff <= self.business_initiated_window
            window_closes_at = last_user_msg_time + self.business_initiated_window
            
            return {
                "within_window": within_window,
                "requires_template": not within_window,
                "reason": "within_24h" if within_window else "window_expired",
                "window_closes_at": window_closes_at.isoformat(),
                "time_since_user_message": str(time_diff),
                "last_user_message": last_user_msg_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking messaging window: {e}")
            return {
                "within_window": False,
                "requires_template": True, 
                "reason": "error",
                "error": str(e)
            }
    
    def select_appropriate_template(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select the most appropriate template based on conversation context
        """
        try:
            # Default to welcome template for new conversations
            if context.get("reason") == "no_prior_conversation":
                return {
                    "template": APPROVED_TEMPLATES["welcome_first"],
                    "parameters": {
                        "customer_name": context.get("customer_name", "לקוח יקר")
                    }
                }
            
            # For window expired - use follow up template  
            if context.get("reason") == "window_expired":
                return {
                    "template": APPROVED_TEMPLATES["follow_up_cold"],
                    "parameters": {
                        "customer_name": context.get("customer_name", "לקוח יקר"),
                        "area": context.get("area", "האזור המבוקש")
                    }
                }
            
            # For property matches
            if context.get("intent") == "property_match":
                return {
                    "template": APPROVED_TEMPLATES["property_match"],
                    "parameters": {
                        "num_properties": str(context.get("num_properties", 3)),
                        "area": context.get("area", "האזור"),
                        "budget": context.get("budget", "התקציב")
                    }
                }
            
            # For appointment reminders
            if context.get("intent") == "appointment_reminder":
                return {
                    "template": APPROVED_TEMPLATES["appointment_reminder"],
                    "parameters": {
                        "customer_name": context.get("customer_name", "לקוח יקר"),
                        "time": context.get("appointment_time", "השעה"),
                        "area": context.get("area", "האזור")
                    }
                }
            
            # Fallback to welcome template
            return {
                "template": APPROVED_TEMPLATES["welcome_first"],
                "parameters": {
                    "customer_name": context.get("customer_name", "לקוח יקר")
                }
            }
            
        except Exception as e:
            logger.error(f"Error selecting template: {e}")
            return {
                "template": APPROVED_TEMPLATES["welcome_first"],
                "parameters": {"customer_name": "לקוח יקר"}
            }

def send_template_message(to: str, template_name: str, parameters: Dict[str, str], 
                         provider: str = "twilio") -> Dict[str, Any]:
    """
    Send template message via Twilio (required for outside 24h window)
    """
    try:
        if provider != "twilio":
            raise ValueError("Templates can only be sent via Twilio WhatsApp Business API")
        
        from twilio.rest import Client
        
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN") 
        from_number = os.getenv("TWILIO_WA_FROM")
        
        if not all([account_sid, auth_token, from_number]):
            raise RuntimeError("Missing Twilio credentials for template sending")
        
        client = Client(account_sid, auth_token)
        
        # Format WhatsApp number
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        
        # Build template parameters for Twilio
        template_params = []
        for key, value in parameters.items():
            template_params.append(value)
        
        # Send template message
        message = client.messages.create(
            content_sid=None,  # Will be filled with actual template SID in production
            content_variables=parameters,
            from_=from_number,
            to=to
        )
        
        logger.info(f"Template message sent: {message.sid}")
        return {
            "success": True,
            "message_id": message.sid,
            "provider": "twilio",
            "template_used": template_name
        }
        
    except Exception as e:
        logger.error(f"Failed to send template message: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def validate_and_route_message(to: str, message: str, business_id: int = 1, 
                             context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Validate messaging window and route to appropriate sending method
    """
    try:
        window_manager = WhatsAppWindowManager()
        window_status = window_manager.check_messaging_window(business_id, to)
        
        result = {
            "window_status": window_status,
            "route": None,
            "action": None
        }
        
        if window_status["within_window"]:
            # Can send regular message via any provider
            result.update({
                "route": "regular_message",
                "action": "send_regular",
                "provider_recommendation": "baileys",  # Prefer Baileys within window
                "message": message
            })
        else:
            # Must use template via Twilio
            template_context = context or {}
            template_context.update(window_status)
            
            template_data = window_manager.select_appropriate_template(template_context)
            
            result.update({
                "route": "template_required", 
                "action": "send_template",
                "provider_recommendation": "twilio",  # Templates require Twilio
                "template": template_data["template"],
                "template_parameters": template_data["parameters"],
                "original_message": message
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in message validation and routing: {e}")
        return {
            "window_status": {"error": str(e)},
            "route": "error",
            "action": "fallback_regular",
            "provider_recommendation": "twilio"
        }

def get_template_list() -> List[Dict[str, Any]]:
    """Get list of all approved templates"""
    return [
        {
            "name": name,
            "category": template["category"],
            "language": template["language"],
            "text_preview": template["text"][:100] + "..." if len(template["text"]) > 100 else template["text"]
        }
        for name, template in APPROVED_TEMPLATES.items()
    ]

# Initialize window manager
window_manager = WhatsAppWindowManager()