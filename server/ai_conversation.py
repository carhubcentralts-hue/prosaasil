# server/ai_conversation.py
import os
import logging
from typing import Optional
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

REAL_ESTATE_PROMPT = """אתה עוזר דיגיטלי מקצועי של מערכת CRM מתקדמת לנדלן.
אתה מומחה בתחום הנדל"ן הישראלי ויכול לעזור עם:
- דירות למכירה ולהשכרה
- משרדים ומבנים מסחריים  
- השקעות נדל"ן
- יעוץ משכנתאות
- הערכת שווי נכסים
- ייעוץ משפטי בסיסי בנדל"ן

תן תשובות קצרות ומועילות בעברית, עד 50 מילים.
היה חם ומקצועי. אל תציין מחירים ספציפיים."""

def generate_response(text: str, call_sid: str = "", turn: int = 1) -> str:
    """Generate AI response in Hebrew for real estate conversation"""
    
    if not OPENAI_AVAILABLE:
        logger.warning("OpenAI not available, using fallback response")
        return get_fallback_response(text)
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.warning("No OpenAI API key, using fallback response")
        return get_fallback_response(text)
    
    try:
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI not available")
            
        if openai is None:
            raise ImportError("OpenAI not available")
        client = openai.OpenAI(api_key=openai_key)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": REAL_ESTATE_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        # Handle response properly with null checks
        ai_response = ""
        if response and response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            ai_response = content.strip() if content else ""
        
        logger.info("AI response generated for call %s: %d chars", call_sid, len(ai_response))
        
        return ai_response
        
    except Exception as e:
        logger.error("AI response generation failed: %s", e)
        return get_fallback_response(text)

def get_fallback_response(text: str) -> str:
    """Fallback responses when AI is not available"""
    text_lower = text.lower()
    
    if "דירה" in text_lower or "בית" in text_lower:
        return "אשמח לעזור לך למצוא דירה מתאימה. איזה אזור מעניין אותך?"
    elif "משרד" in text_lower or "מסחרי" in text_lower:
        return "יש לנו מבחר משרדים מעולים. כמה מטרים רבועים אתה מחפש?"
    elif "מחיר" in text_lower or "כסף" in text_lower:
        return "המחירים משתנים לפי המיקום והגודל. בואו נתאם פגישה לפרטים."
    elif "משכנתא" in text_lower:
        return "אפשר לקבל ייעוץ משכנתאות מקצועי. נתאם פגישה עם היועץ שלנו?"
    else:
        return "אני כאן לעזור בכל נושא נדל״ן. על מה תרצה לשמוע?"

def test_ai():
    """Test function for AI conversation"""
    logger.info("AI conversation handler loaded successfully")
    return "AI ready for Hebrew real estate conversations"