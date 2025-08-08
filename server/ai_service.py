"""
AI Service for Hebrew Call Center
תיקון מלא לפי ההנחיות - August 2, 2025
"""

import openai
import os
import logging

logger = logging.getLogger(__name__)

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_response(prompt):
    """פונקציה פשוטה ליצירת תגובה מ-OpenAI כמו בהנחיות"""
    try:
        if not openai.api_key:
            logger.warning("OpenAI API key not found")
            return "תודה על פנייתכם. נחזור אליכם בהקדם."
        
        from openai import OpenAI
        client = OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        return content.strip() if content else "תודה על פנייתכם. נחזור אליכם בהקדם."
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "תודה על פנייתכם. נחזור אליכם בהקדם."

def get_business_context(business_id):
    """Get business-specific context for AI responses"""
    try:
        from server.models import Business
        business = Business.query.get(business_id)
        if business and business.ai_prompt:
            return business.ai_prompt
        
        # Default real estate context for Shai Real Estate
        return """
        אני עוזר דיגיטלי של שי דירות ומשרדים בע״מ, חברה מקצועית לתיווך נדלן.
        אני מתמחה בסיוע ללקוחות עם:
        - מכירת ורכישת דירות ונכסים
        - השכרת נכסים למגורים ומסחר
        - יעוץ והערכת שווי נכסים
        - ליווי משפטי ומימון
        
        אדבר בעברית בצורה מקצועית ואדיבה, ואפנה לתיאום פגישה עם המתווכים שלנו.
        """
    except Exception as e:
        logger.error(f"Error getting business context: {str(e)}")
        return "אני עוזר דיגיטלי של שי דירות ומשרדים בע״מ, מוכן לעזור בכל נושא של נדלן"

# Compatibility class for existing code
class AIService:
    def __init__(self):
        self.api_available = bool(openai.api_key)
        self.model = "gpt-3.5-turbo"
        
    def generate_response(self, user_input, business=None, conversation_history=None, caller_info=None):
        """Generate AI response with business context"""
        try:
            business_context = get_business_context(business.id if business else 12)  # Default to new real estate business
            full_prompt = f"{business_context}\n\nלקוח: {user_input}\n\nתגובה:"
            return generate_response(full_prompt)
        except:
            return generate_response(user_input)