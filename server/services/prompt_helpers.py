"""
Shared Prompt Helpers - Minimal Fallback Templates
====================================================

🎯 CRITICAL: This file contains MINIMAL fallback prompts only.
System behavior rules are defined in realtime_prompt_builder.py (single source).

This avoids duplication and ensures system rules appear only once.
"""

def get_default_hebrew_prompt_for_calls(business_name: str = "העסק שלנו") -> str:
    """
    MINIMAL fallback prompt for phone calls.
    
    ⚠️ This should RARELY be used - proper prompts come from DB.
    ⚠️ Does NOT duplicate system behavior rules (those are in system prompt).
    
    Only contains: basic identity and language preference.
    All behavior rules (tone, call control, etc.) are in the system layer.
    
    Used by: realtime_prompt_builder fallback chain (last resort)
    """
    return f"""You are a voice assistant for {business_name}.
Default language: Hebrew.
Respond naturally and briefly."""


def get_default_hebrew_prompt_for_whatsapp(business_name: str = "העסק שלנו") -> str:
    """
    MINIMAL fallback prompt for WhatsApp.
    
    ⚠️ This should RARELY be used - proper prompts come from DB.
    ⚠️ Does NOT duplicate system behavior rules.
    
    Only contains: basic identity and channel context.
    
    Used by: ai_service fallback chain (last resort)
    """
    return f"""You are a messaging assistant for {business_name} on WhatsApp.
Respond in Hebrew naturally."""
