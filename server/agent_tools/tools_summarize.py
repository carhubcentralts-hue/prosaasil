"""
Conversation Summarization Tools for AgentKit
Generates structured summaries of calls and WhatsApp conversations for CRM
"""
# 🔥 CRITICAL FIX: Import OpenAI Agents SDK directly (server/agents/__init__.py is now empty)
from agents import function_tool

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import logging
import openai
import os

logger = logging.getLogger(__name__)

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class SummarizeInput(BaseModel):
    """Input for summarizing a conversation"""
    business_id: int = Field(..., description="Business ID", ge=1)
    source: Literal["call", "whatsapp", "conversation"] = Field(..., description="Source type")
    source_id: str = Field(..., description="Source ID (call_sid, whatsapp_message_id, conversation_id)")
    max_words: int = Field(120, description="Maximum words in summary", ge=20, le=500)

class SummaryOutput(BaseModel):
    """Structured conversation summary"""
    ok: bool
    key_intent: Optional[str] = None
    chosen_treatment: Optional[str] = None
    preferred_time: Optional[str] = None
    next_step: Optional[str] = None
    sentiment: Optional[str] = None
    bullets: List[str] = []
    summary_text: Optional[str] = None
    reason: Optional[str] = None

# ================================================================================
# TOOL FUNCTIONS
# ================================================================================

@function_tool
def summarize_thread(
    business_id: int,
    source: str,
    source_id: str,
    max_words: int = 120
) -> dict:
    """
    Generate a structured summary of a conversation for CRM notes
    
    Args:
        business_id: Business ID
        source: Source type ("call", "whatsapp", "conversation")
        source_id: Source identifier
        max_words: Maximum words in summary (default 120)
        
    Returns:
        Dict with ok, key_intent, chosen_treatment, preferred_time, next_step, sentiment, bullets, summary_text
    """
    try:
        logger.info(f"📊 Summarizing {source} ID={source_id}, business_id={business_id}")
        
        # Import models
        from server.models_sql import CallLog, WhatsAppMessage
        
        # Extract conversation text based on source
        conversation_text = ""
        
        if source == "call":
            call_log = CallLog.query.filter_by(call_sid=source_id, business_id=business_id).first()
            if not call_log:
                return {
                    "ok": False,
                    "reason": "שיחה לא נמצאה"
                }
            conversation_text = call_log.transcription or ""
            
        elif source == "whatsapp":
            # Get WhatsApp conversation thread
            messages = WhatsAppMessage.query.filter_by(
                conversation_id=source_id,
                business_id=business_id
            ).order_by(WhatsAppMessage.created_at).all()
            
            if not messages:
                return {
                    "ok": False,
                    "reason": "שיחת WhatsApp לא נמצאה"
                }
            
            # Build conversation
            conversation_text = "\n".join([
                f"{'לקוח' if msg.direction == 'incoming' else 'נציג'}: {msg.body}"
                for msg in messages
            ])
        
        else:
            return {
                "ok": False,
                "reason": f"סוג מקור לא נתמך: {source}"
            }
        
        if not conversation_text or len(conversation_text) < 10:
            return {
                "ok": False,
                "reason": "אין מספיק תוכן לסיכום"
            }
        
        # Generate structured summary using OpenAI
        summary = _generate_structured_summary(conversation_text, max_words)
        
        logger.info(f"✅ Summary generated: intent={summary.get('key_intent')}, treatment={summary.get('chosen_treatment')}")
        
        return {
            "ok": True,
            **summary
        }
        
    except Exception as e:
        logger.error(f"❌ Error summarizing conversation: {e}")
        return {
            "ok": False,
            "reason": str(e)[:160]
        }

def _generate_structured_summary(conversation_text: str, max_words: int = 120) -> dict:
    """
    Generate structured summary using OpenAI
    
    Returns dict with: key_intent, chosen_treatment, preferred_time, next_step, sentiment, bullets, summary_text
    """
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""סכם את השיחה הבאה בעברית במבנה מובנה:

שיחה:
{conversation_text[:2000]}

חלץ:
1. כוונה עיקרית (key_intent): למה הלקוח פנה?
2. טיפול/שירות שנבחר (chosen_treatment): מה הוזמן?
3. זמן מועדף (preferred_time): מתי הלקוח רוצה?
4. צעד הבא (next_step): מה צריך לקרות אחר כך?
5. סנטימנט (sentiment): חיובי/שלילי/ניטרלי
6. נקודות עיקריות (bullets): 2-3 נקודות חשובות

השב בפורמט JSON בלבד:
{{"key_intent": "...", "chosen_treatment": "...", "preferred_time": "...", "next_step": "...", "sentiment": "...", "bullets": ["...", "..."], "summary_text": "סיכום קצר במילים {max_words}"}}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "אתה עוזר מקצועי לסיכום שיחות CRM בעברית. תמיד השב בJSON בלבד."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"}
        )
        
        import json
        summary = json.loads(response.choices[0].message.content)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating summary with OpenAI: {e}")
        # Fallback to basic summary
        return {
            "key_intent": "לא זוהה",
            "chosen_treatment": None,
            "preferred_time": None,
            "next_step": "מעקב נדרש",
            "sentiment": "ניטרלי",
            "bullets": ["שיחה התקבלה"],
            "summary_text": conversation_text[:max_words * 7]  # Rough word count
        }
