"""
WhatsApp Prompt Stack Builder - Clean Separation of Concerns
=============================================================

This module implements the "Prompt Stack" architecture where:
- SYSTEM prompts = Framework only (tools, rules, format, memory, safety)
- DB prompts = Single source of truth for business behavior
- Context injection = Customer data, history, state

The SYSTEM prompt is minimal and never contains:
- Sales scripts or conversation examples
- Appointment processes or detailed flows
- Business descriptions, services, pricing
- Personality beyond general tone

All business behavior comes from business.whatsapp_system_prompt in DB.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# ============================================================================
# FRAMEWORK SYSTEM PROMPT - SHORT & MECHANICAL
# ============================================================================
# This prompt contains ONLY:
# 1. Tool usage rules
# 2. Memory/context rules
# 3. Format rules (WhatsApp: short, one message, one question)
# 4. Safety rules (don't invent facts, ask if missing info)
# 5. CRM update rules (when to update after changes)
# ============================================================================

FRAMEWORK_SYSTEM_PROMPT = """אתה עוזר דיגיטלי ב-WhatsApp.

🔧 כללי עבודה עם כלים (Tools):
- אם אתה צריך מידע על לקוח/סטטוס/היסטוריה/שירותים - השתמש בכלים הזמינים.
- אם יש צורך לעדכן CRM לאחר שינוי משמעותי - השתמש בכלי העדכון.

🧠 כללי זיכרון והקשר:
- אם יש summary/last_state: אל תתנהג כאילו זו שיחה חדשה.
- שאל את הלקוח: "ראיתי שעצרנו ב-X. להמשיך משם או להתחיל מחדש?"
- השתמש בהיסטוריה כדי להבין את ההקשר, אל תחזור על מה שכבר נשאל.
- אם הלקוח כבר ענה על שאלה - אל תשאל אותה שוב! המשך לשאלה הבאה.

📱 כללי פורמט ב-WhatsApp:
- תענה קצר - הודעה אחת בכל פעם.
- שאלה אחת בכל תגובה.
- אל תשלח יותר מ-2-3 שורות.
- תהיה ישיר ולעניין.

🔄 כללי התקדמות בשיחה:
- אם יש history_count >= 2 - זו לא שיחה חדשה! אל תברך שוב.
- אם הלקוח ענה על השאלה שלך - המשך לשאלה הבאה, אל תחזור על הברכה.
- בדוק את ההיסטוריה לראות מה כבר נשאל ומה כבר נענה.
- כל תגובה שלך צריכה להתקדם בתהליך, לא לחזור על מה שכבר נאמר.

🛡️ כללי בטיחות ויציבות:
- אם חסר לך מידע - שאל את הלקוח במקום להמציא.
- אל תבטיח דברים שאתה לא בטוח בהם.
- אם יש שגיאה - הודה ושאל לנסות שוב.

📝 כללי תיעוד:
- לאחר שינוי משמעותי - עדכן את ה-CRM דרך הכלים.

זהו. כל שאר ההתנהגות מגיעה מהפרומפט העסקי שלך."""


def build_whatsapp_prompt_stack(
    business_id: int,
    db_prompt: str,
    context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Build the complete WhatsApp prompt stack with clean separation.
    
    Stack structure:
    1. SYSTEM Framework Prompt (fixed, short)
    2. DB Business Prompt (from database - single source of truth)
    3. Context Injection (customer info, history, state)
    4. User Message (added by caller)
    
    Args:
        business_id: Business ID for logging
        db_prompt: Business prompt from database (whatsapp_system_prompt)
        context: Optional context dict with:
            - lead_id: Lead ID (if exists)
            - customer_name: Customer name (if exists)
            - summary: Conversation summary (if exists)
            - last_state: Last conversation state (if exists)
            - last_intent: Last detected intent (if exists)
            - history: List of last N messages (if exists)
    
    Returns:
        List of message dicts ready for LLM
    """
    messages = []
    
    # ============================================================================
    # LAYER 1: SYSTEM FRAMEWORK (Fixed - Never changes unless tools change)
    # ============================================================================
    messages.append({
        "role": "system",
        "content": FRAMEWORK_SYSTEM_PROMPT
    })
    
    # ============================================================================
    # LAYER 2: DB BUSINESS PROMPT (Single source of truth for behavior)
    # ============================================================================
    if not db_prompt or not db_prompt.strip():
        logger.error(f"❌ NO DB PROMPT for business {business_id}! Using emergency fallback.")
        db_prompt = "אתה עוזר דיגיטלי. תענה בעברית ותהיה חם ואדיב."
    
    messages.append({
        "role": "system",
        "content": f"📋 הנחיות עסקיות:\n{db_prompt}"
    })
    
    logger.info(f"✅ Prompt stack built: framework={len(FRAMEWORK_SYSTEM_PROMPT)} + db={len(db_prompt)} chars")
    
    # ============================================================================
    # LAYER 3: CONTEXT INJECTION (Customer data & state)
    # ============================================================================
    if context:
        context_parts = []
        
        # Business & Lead IDs
        if business_id:
            context_parts.append(f"business_id: {business_id}")
        if context.get('lead_id'):
            context_parts.append(f"lead_id: {context['lead_id']}")
        
        # Customer name
        if context.get('customer_name'):
            context_parts.append(f"שם לקוח: {context['customer_name']}")
        
        # 🔥 FIX: Add conversation history indicator
        if context.get('conversation_has_history'):
            context_parts.append(f"⚠️ זו לא שיחה חדשה! כבר יש היסטוריה של הודעות.")
        
        # Conversation state (if exists)
        if context.get('summary'):
            context_parts.append(f"סיכום שיחה קודמת: {context['summary']}")
        
        if context.get('last_state'):
            context_parts.append(f"מצב אחרון: {context['last_state']}")
        
        if context.get('last_intent'):
            context_parts.append(f"כוונה אחרונה: {context['last_intent']}")
        
        # 🔥 FIX: Add last exchange information
        if context.get('last_user_message'):
            context_parts.append(f"הודעה אחרונה מהלקוח: {context['last_user_message'][:100]}...")
        
        if context.get('last_agent_message'):
            context_parts.append(f"התשובה האחרונה שלך: {context['last_agent_message'][:100]}...")
        
        if context_parts:
            messages.append({
                "role": "system",
                "content": "🔍 הקשר נוכחי:\n" + "\n".join(context_parts)
            })
        
        # History (keep minimal - last 5-10 messages only)
        if context.get('history'):
            history = context['history']
            # Limit to last 10 messages maximum
            history = history[-10:] if len(history) > 10 else history
            
            if history:
                messages.append({
                    "role": "system",
                    "content": f"📜 היסטוריה אחרונה ({len(history)} הודעות):\n" + "\n".join(history)
                })
                logger.info(f"📜 Added {len(history)} history messages to stack")
        
        # 🔥 FIX: Add anti-repetition instruction if there's a history
        if context.get('anti_repeat_instruction'):
            messages.append({
                "role": "system",
                "content": f"⚠️ הוראה חשובה:\n{context['anti_repeat_instruction']}"
            })
    
    return messages


def get_db_prompt_for_whatsapp(business_id: int) -> str:
    """
    Get the DB prompt for WhatsApp - the single source of truth for behavior.
    
    Priority order:
    1. business.whatsapp_system_prompt (primary)
    2. BusinessSettings.ai_prompt['whatsapp'] (fallback)
    3. Emergency minimal fallback (only if nothing exists)
    
    Args:
        business_id: Business ID
    
    Returns:
        Prompt string from database
    """
    from server.models_sql import Business, BusinessSettings
    from server.db import db
    import json
    
    try:
        # Priority 1: business.whatsapp_system_prompt
        business = Business.query.get(business_id)
        if business and hasattr(business, 'whatsapp_system_prompt') and business.whatsapp_system_prompt:
            prompt = business.whatsapp_system_prompt.strip()
            if prompt:
                logger.info(f"✅ Loaded WhatsApp prompt from business.whatsapp_system_prompt ({len(prompt)} chars)")
                return prompt
        
        # Priority 2: BusinessSettings.ai_prompt (JSON with 'whatsapp' key)
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if settings and settings.ai_prompt:
            try:
                if settings.ai_prompt.strip().startswith('{'):
                    prompt_obj = json.loads(settings.ai_prompt)
                    if 'whatsapp' in prompt_obj:
                        prompt = prompt_obj['whatsapp'].strip()
                        if prompt:
                            logger.info(f"✅ Loaded WhatsApp prompt from BusinessSettings.ai_prompt ({len(prompt)} chars)")
                            return prompt
            except json.JSONDecodeError:
                pass
        
        # Priority 3: Emergency fallback
        logger.error(f"❌ NO WhatsApp prompt found for business {business_id}! Using emergency fallback.")
        business_name = business.name if business else "העסק"
        return f"אתה העוזר הדיגיטלי של {business_name}. תענה בעברית, תהיה חם ואדיב, ועזור ללקוח בהתאם לצרכיו."
        
    except Exception as e:
        logger.error(f"❌ Error loading WhatsApp prompt for business {business_id}: {e}")
        return "אתה עוזר דיגיטלי. תענה בעברית ותהיה חם ואדיב."


def validate_prompt_stack_usage(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Validate that the prompt stack is being used correctly.
    
    This function checks:
    - Framework prompt is present
    - DB prompt is present
    - No duplicate system prompts
    - Total token count is reasonable
    
    Args:
        messages: List of message dicts
    
    Returns:
        Validation result dict with warnings/errors
    """
    result = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "stats": {}
    }
    
    # Count system messages
    system_messages = [m for m in messages if m.get("role") == "system"]
    result["stats"]["system_message_count"] = len(system_messages)
    
    # Check for framework prompt
    has_framework = any("כללי עבודה עם כלים" in m.get("content", "") for m in system_messages)
    if not has_framework:
        result["errors"].append("Framework prompt missing!")
        result["valid"] = False
    
    # Check for DB prompt
    has_db_prompt = any("הנחיות עסקיות" in m.get("content", "") for m in system_messages)
    if not has_db_prompt:
        result["errors"].append("DB prompt missing!")
        result["valid"] = False
    
    # Check total length
    total_chars = sum(len(m.get("content", "")) for m in messages)
    result["stats"]["total_chars"] = total_chars
    
    if total_chars > 5000:
        result["warnings"].append(f"Prompt stack is large ({total_chars} chars). Consider reducing history.")
    
    # Rough token estimate (1 token ≈ 4 chars for Hebrew)
    estimated_tokens = total_chars // 4
    result["stats"]["estimated_tokens"] = estimated_tokens
    
    if estimated_tokens > 2000:
        result["warnings"].append(f"Estimated {estimated_tokens} tokens. May cause latency.")
    
    return result
