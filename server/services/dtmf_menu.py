"""
DTMF Menu Handler - Interactive Voice Menu for Phone Calls
🔥 BUILD 200: 100% DYNAMIC - No hardcoded business hours or service types!
Allows callers to press digits for different actions (1=booking, 2=info, etc.)
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DTMFMenuHandler:
    """
    Handle DTMF (keypad) input for call menus
    🔥 BUILD 200: All business-specific values must come from context/settings!
    
    Menu structure:
    - Press 1: Book an appointment
    - Press 2: Get business info / opening hours
    - Press 3: Speak to representative
    - Press 0: Repeat menu
    """
    
    MENU_ACTIONS = {
        '1': 'booking',
        '2': 'info',
        '3': 'representative',
        '0': 'repeat_menu'
    }
    
    @staticmethod
    def get_menu_prompt(business_name: str = "העסק שלנו") -> str:
        """
        Get Hebrew voice menu prompt - GENERIC for any business type
        
        Returns:
            Menu text in Hebrew for TTS
        """
        return f"""שלום! התקשרת ל{business_name}.

לחץ 1 לקביעת תור
לחץ 2 למידע על שעות פתיחה
לחץ 3 לדבר עם נציג
לחץ 0 לשמוע שוב את התפריט

או פשוט תגיד מה אתה צריך ואני אעזור לך."""
    
    @staticmethod
    def handle_dtmf_input(digit: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Process DTMF digit and return action
        🔥 BUILD 200: All responses are GENERIC - no hardcoded hours or service types!
        
        Args:
            digit: Single DTMF digit ('0'-'9', '*', '#')
            context: Optional conversation context (should contain business_hours from settings)
            
        Returns:
            Dict with 'action' and 'message' keys
        """
        action = DTMFMenuHandler.MENU_ACTIONS.get(digit)
        
        if not action:
            # Invalid input
            return {
                'action': 'invalid',
                'message': 'מצטער, לא הבנתי את הבחירה. אנא בחר 1, 2, 3 או 0.'
            }
        
        if action == 'booking':
            # 🔥 BUILD 200: GENERIC message - no "טיפול" assumption!
            return {
                'action': 'booking',
                'message': 'מעולה! בואו נקבע לך תור. במה אוכל לעזור?',
                'context_update': {'menu_choice': 'booking', 'mode': 'booking'}
            }
        
        elif action == 'info':
            # 🔥 BUILD 200: Get hours from context, or ask AI to provide from business settings
            business_hours = context.get('business_hours', None) if context else None
            if business_hours:
                return {
                    'action': 'info',
                    'message': f'שעות הפעילות שלנו: {business_hours}. איך אני יכול לעזור?',
                    'context_update': {'menu_choice': 'info'}
                }
            else:
                # 🔥 No hardcoded hours - let AI respond with dynamic info
                return {
                    'action': 'info',
                    'message': 'איך אני יכול לעזור? אם אתה רוצה לדעת את שעות הפעילות, אני אבדוק בשבילך.',
                    'context_update': {'menu_choice': 'info', 'request_hours': True}
                }
        
        elif action == 'representative':
            return {
                'action': 'representative',
                'message': 'מעביר אותך לנציג. רגע אחד בבקשה.',
                'context_update': {'menu_choice': 'representative', 'transfer_requested': True}
            }
        
        elif action == 'repeat_menu':
            return {
                'action': 'repeat_menu',
                'message': DTMFMenuHandler.get_menu_prompt(),
                'context_update': {'menu_choice': 'repeat'}
            }
    
    @staticmethod
    def should_show_menu(context: Dict[str, Any] = None) -> bool:
        """
        Determine if menu should be shown
        
        Args:
            context: Conversation context
            
        Returns:
            True if menu should be presented, False otherwise
        """
        if not context:
            # First turn - show menu
            return True
        
        # Don't show menu if already in conversation
        if context.get('previous_messages'):
            return False
        
        # Don't show menu if user already made a choice
        if context.get('menu_choice'):
            return False
        
        return True

# Helper function for integration
def process_dtmf_digit(digit: str, context: Dict[str, Any] = None) -> Optional[Dict[str, str]]:
    """
    Process DTMF digit if valid
    
    Args:
        digit: DTMF digit
        context: Conversation context
        
    Returns:
        Action dict or None if invalid
    """
    if not digit or digit not in '0123456789*#':
        return None
    
    handler = DTMFMenuHandler()
    return handler.handle_dtmf_input(digit, context)
