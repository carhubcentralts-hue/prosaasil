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

# Compatibility class for existing code
class AIService:
    def __init__(self):
        self.api_available = bool(openai.api_key)
        self.model = "gpt-3.5-turbo"
        
    def generate_response(self, user_input, business=None, conversation_history=None, caller_info=None):
        """Generate AI response - compatibility wrapper"""
        return generate_response(user_input)