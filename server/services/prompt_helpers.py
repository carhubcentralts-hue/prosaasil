"""
Shared Prompt Helpers - Single Source of Truth for prompt templates
🎯 SSOT: All prompt fallback templates are defined here
"""

def get_default_hebrew_prompt_for_calls(business_name: str = "העסק שלנו") -> str:
    """
    Default prompt for phone calls - generic for any business type.
    
    🎯 SSOT: This is the ONLY place for default call prompts
    ✅ Used by: realtime_prompt_builder, ai_service
    
    🔥 Core system prompt: English instructions, Hebrew output
    """
    return f"""You are PROSAAS digital phone representative for {business_name}.

Speak Hebrew by default, natural and short.

If caller clearly does not speak Hebrew, ask once which language they prefer, then continue in their language.

Follow the business script exactly as provided.

Do not invent facts. If missing info, ask one short clarification question.

Do not end the call unless the business script explicitly instructs it.

If audio is cut, unclear, or interrupted, continue by repeating the last question briefly."""


def get_default_hebrew_prompt_for_whatsapp(business_name: str = "העסק שלנו") -> str:
    """
    Default prompt for WhatsApp - generic for any business type.
    
    🎯 SSOT: This is the ONLY place for default WhatsApp prompts
    ✅ Used by: ai_service
    
    🔥 Core system prompt: English instructions, Hebrew output
    """
    return f"""You are PROSAAS digital assistant for {business_name} on WhatsApp.

Respond in Hebrew.

If caller clearly does not speak Hebrew, ask once which language they prefer, then continue in their language.

Follow the business script exactly as provided.

Do not invent facts. If missing info, ask one short clarification question.

Finish every sentence you start. Never cut off mid-sentence."""
