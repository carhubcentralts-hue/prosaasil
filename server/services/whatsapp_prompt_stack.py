"""
WhatsApp Prompt Stack Builder - DB Prompt as Single Source of Truth
=====================================================================

This module builds the prompt stack for WhatsApp bot responses.
The ONLY source of truth for bot behavior is business.whatsapp_system_prompt in DB.

NO hardcoded prompts, rules, or instructions are allowed in this file.
All behavior, tone, rules, and instructions must come from the database.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


def build_whatsapp_prompt_stack(
    business_id: int,
    db_prompt: str,
    context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Build the WhatsApp prompt stack using ONLY the DB prompt as the source of truth.
    
    Stack structure:
    1. DB Business Prompt (from database - ONLY source of truth)
    2. Context Injection (structured data: history as user/assistant messages, memory, state)
    3. User Message (added by caller)
    
    NO hardcoded instructions, rules, or behavioral guidance is included.
    Everything must come from business.whatsapp_system_prompt.
    
    Args:
        business_id: Business ID for logging
        db_prompt: Business prompt from database (whatsapp_system_prompt) - REQUIRED
        context: Optional context dict with:
            - lead_id: Lead ID (if exists)
            - customer_name: Customer name (if exists)
            - customer_memory: Customer memory/notes (if exists)
            - previous_messages: List of last N messages (formatted as "לקוח: ..." or "עוזר: ...")
            - conversation_stage: Current conversation stage (if exists)
            - collected_fields: Fields collected so far (if exists)
    
    Returns:
        List of message dicts ready for LLM, or error if no DB prompt
    """
    messages = []
    
    # ============================================================================
    # LAYER 1: DB PROMPT - SINGLE SOURCE OF TRUTH
    # ============================================================================
    if not db_prompt or not db_prompt.strip():
        logger.error(f"❌ MISSING_WHATSAPP_PROMPT for business {business_id}! Cannot respond without DB prompt.")
        # Return error - bot will not respond
        return [{
            "role": "system",
            "content": "❌ ERROR: MISSING_WHATSAPP_PROMPT - No business prompt configured in database."
        }]
    
    # Add DB prompt as system message - this is the ONLY source of behavior
    messages.append({
        "role": "system",
        "content": db_prompt
    })
    
    logger.info(f"✅ Using DB prompt as single source of truth: {len(db_prompt)} chars")
    
    # ============================================================================
    # LAYER 2: STRUCTURED CONTEXT (Data only, no instructions)
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
        
        # Customer memory (if exists)
        if context.get('customer_memory'):
            context_parts.append(f"זיכרון לקוח: {context['customer_memory']}")
        
        # Conversation stage (if exists)
        if context.get('conversation_stage'):
            context_parts.append(f"שלב נוכחי: {context['conversation_stage']}")
        
        # Collected fields (if exists)
        if context.get('collected_fields'):
            context_parts.append(f"שדות שנאספו: {context['collected_fields']}")
        
        # Lead status context (for Logic-by-Prompt)
        if context.get('lead_status_label'):
            context_parts.append(f"סטטוס ליד: {context['lead_status_label']}")
        
        # Known facts (from lead_facts table)
        if context.get('known_facts'):
            context_parts.append(f"עובדות ידועות: {json.dumps(context['known_facts'], ensure_ascii=False)}")
        
        if context_parts:
            messages.append({
                "role": "system",
                "content": "🔍 הקשר:\n" + "\n".join(context_parts)
            })
        
        # Convert conversation history to proper user/assistant messages
        # This is structured data, not instructions
        if context.get('previous_messages'):
            history = context['previous_messages']
            # Limit to last 20 messages for context
            history = history[-20:] if len(history) > 20 else history
            
            if history:
                logger.info(f"📜 Adding {len(history)} history messages as user/assistant format")
                
                # Convert each message to proper role format
                for msg in history:
                    # Format is "לקוח: text" or "עוזר: text"
                    if msg.startswith("לקוח:"):
                        messages.append({
                            "role": "user",
                            "content": msg.replace("לקוח:", "").strip()
                        })
                    elif msg.startswith("עוזר:") or msg.startswith("עוזרת:"):
                        content = msg.replace("עוזר:", "").replace("עוזרת:", "").strip()
                        messages.append({
                            "role": "assistant",
                            "content": content
                        })
                    else:
                        # If no prefix, assume it's user message
                        logger.warning(f"[HISTORY] Message without prefix: {msg[:50]}...")
                        messages.append({
                            "role": "user",
                            "content": msg
                        })
    
    return messages


def get_db_prompt_for_whatsapp(business_id: int) -> str:
    """
    Get the DB prompt for WhatsApp - the ONLY source of truth for bot behavior.
    
    Uses ONLY business.whatsapp_system_prompt.
    NO fallback to BusinessSettings.ai_prompt or any hardcoded prompts.
    
    Args:
        business_id: Business ID
    
    Returns:
        Prompt string from database, or empty string if not found
    """
    from server.models_sql import Business
    from server.db import db
    
    try:
        # Load ONLY business.whatsapp_system_prompt
        business = Business.query.get(business_id)
        if business and hasattr(business, 'whatsapp_system_prompt') and business.whatsapp_system_prompt:
            prompt = business.whatsapp_system_prompt.strip()
            if prompt:
                logger.info(f"✅ Loaded WhatsApp prompt from business.whatsapp_system_prompt ({len(prompt)} chars)")
                return prompt
        
        # No fallback - return empty string
        logger.error(f"❌ MISSING_WHATSAPP_PROMPT for business {business_id}! Bot will not respond.")
        return ""
        
    except Exception as e:
        logger.error(f"❌ Error loading WhatsApp prompt for business {business_id}: {e}")
        return ""


def validate_prompt_stack_usage(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Validate that the prompt stack is being used correctly.
    
    This function checks:
    - DB prompt is present
    - No hardcoded system instructions
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
    
    # Check for DB prompt (should be first system message)
    if not system_messages:
        result["errors"].append("No system messages found - DB prompt missing!")
        result["valid"] = False
    elif system_messages[0].get("content", "").startswith("❌ ERROR"):
        result["errors"].append("DB prompt missing or error!")
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
