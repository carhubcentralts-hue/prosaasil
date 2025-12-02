"""
Realtime Prompt Builder
Build dynamic system prompts for OpenAI Realtime API based on business settings
"""
import logging
from typing import Optional, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


def get_greeting_prompt_fast(business_id: int) -> Tuple[str, str]:
    """
    FAST greeting loader - minimal DB access for phase 1
    Returns (greeting_text, business_name)
    
    🔥 CRITICAL: All greetings must come from DB. No hardcoded fallbacks.
    """
    try:
        from server.models_sql import Business
        
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"⚠️ Business {business_id} not found - using minimal generic greeting")
            return ("", "")  # Return empty - let AI handle naturally
        
        business_name = business.name or ""
        greeting = business.greeting_message
        
        if greeting and greeting.strip():
            # Replace placeholder with actual business name
            final_greeting = greeting.strip().replace("{{business_name}}", business_name).replace("{{BUSINESS_NAME}}", business_name)
            logger.info(f"✅ [GREETING] Loaded from DB for business {business_id}: '{final_greeting[:50]}...'")
            return (final_greeting, business_name)
        else:
            logger.warning(f"⚠️ No greeting in DB for business {business_id} - AI will greet naturally")
            return ("", business_name)  # Let AI greet based on prompt
    except Exception as e:
        logger.error(f"❌ Fast greeting load failed: {e}")
        return ("", "")  # Return empty - let AI handle naturally


def build_realtime_system_prompt(business_id: int, db_session=None) -> str:
    """
    Build system prompt for OpenAI Realtime API based on business settings
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
    
    Returns:
        System prompt in Hebrew for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        from server.policy.business_policy import get_business_policy
        
        # Load business and settings
        try:
            if db_session:
                business = db_session.query(Business).get(business_id)
                settings = db_session.query(BusinessSettings).filter_by(tenant_id=business_id).first()
            else:
                business = Business.query.get(business_id)
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        except Exception as db_error:
            logger.error(f"❌ DB error loading business {business_id}: {db_error}")
            return _get_fallback_prompt()
        
        if not business:
            raise ValueError(f"Business {business_id} not found")
        
        business_name = business.name or "העסק"
        
        # Load business policy (slot size, opening hours, etc.)
        policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
        
        logger.info(f"📋 Building Realtime prompt for {business_name} (business_id={business_id})")
        
        # 🔥 Load custom prompt from DB (just like WhatsApp)
        core_instructions = ""
        if settings and settings.ai_prompt and settings.ai_prompt.strip():
            import json
            try:
                if settings.ai_prompt.strip().startswith('{'):
                    prompt_obj = json.loads(settings.ai_prompt)
                    if 'calls' in prompt_obj:
                        core_instructions = prompt_obj['calls']
                        logger.info(f"✅ Using 'calls' prompt from DB for business {business_id}")
                    elif 'whatsapp' in prompt_obj:
                        core_instructions = prompt_obj['whatsapp']
                        logger.info(f"⚠️ Using 'whatsapp' as fallback for business {business_id}")
                    else:
                        core_instructions = settings.ai_prompt
                else:
                    core_instructions = settings.ai_prompt
            except json.JSONDecodeError:
                core_instructions = settings.ai_prompt
        
        if not core_instructions:
            logger.error(f"❌ No 'calls' prompt in DB for business {business_id}")
            core_instructions = f"""אתה נציג טלפוני של "{business_name}". עונה בעברית, קצר וברור."""
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 Get current date for AI context
        tz = pytz.timezone(policy.tz)
        today = datetime.now(tz)
        today_hebrew = today.strftime("%d/%m/%Y")
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        weekday_hebrew = weekday_names[today.weekday()]
        
        # 🔥 LOAD GREETING FROM DB
        greeting_text = business.greeting_message if business else ""
        if not greeting_text:
            greeting_text = ""
        
        # 🔥 BUILD 168: Load required_lead_fields for dynamic verification prompt
        required_lead_fields = ['name', 'phone']  # Default
        if settings and hasattr(settings, 'required_lead_fields') and settings.required_lead_fields:
            required_lead_fields = settings.required_lead_fields
            logger.info(f"✅ Using custom required_lead_fields: {required_lead_fields}")
        
        # 🎯 Build COMPACT system prompt with dynamic verification
        critical_rules = _build_critical_rules_compact(business_name, today_hebrew, weekday_hebrew, greeting_text, required_lead_fields)
        
        # Combine: Rules + Custom prompt + Policy (all in English)
        full_prompt = critical_rules + "\n\nBUSINESS INSTRUCTIONS:\n" + core_instructions
        
        # Add policy info (hours, slots) - keep Hebrew for display to customers
        hours_description = _build_hours_description(policy)
        slot_description = _build_slot_description(policy.slot_size_min)
        
        min_notice = ""
        if policy.min_notice_min > 0:
            min_notice_hours = policy.min_notice_min // 60
            if min_notice_hours > 0:
                min_notice = f" (advance booking: {min_notice_hours}h)"
        
        full_prompt += f"\n\nSCHEDULING: Slots every {policy.slot_size_min} min{min_notice}\n{hours_description}"
        
        # Log final length
        logger.info(f"✅ REALTIME PROMPT [business_id={business_id}] LEN={len(full_prompt)} chars")
        print(f"📏 [PROMPT] Final length: {len(full_prompt)} chars")
        
        if len(full_prompt) > 3000:
            logger.warning(f"⚠️ Prompt may be too long ({len(full_prompt)} chars)")
        
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ Error building Realtime prompt: {e}")
        import traceback
        traceback.print_exc()
        return _get_fallback_prompt()


def _get_fallback_prompt() -> str:
    """Minimal fallback prompt - generic, no business type assumptions"""
    return """You are a professional, friendly service representative. Respond in HEBREW, be brief and clear. Help the customer with what they need."""


def _build_hours_description(policy) -> str:
    """Build opening hours description in Hebrew"""
    if policy.allow_24_7:
        return "פתוח 24/7"
    
    hours = policy.opening_hours
    if not hours:
        return "שעות פעילות לא הוגדרו"
    
    day_names = {
        "sun": "א", "mon": "ב", "tue": "ג", "wed": "ד",
        "thu": "ה", "fri": "ו", "sat": "ש"
    }
    
    parts = []
    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        windows = hours.get(day_key, [])
        if windows:
            time_ranges = ",".join([f"{w[0]}-{w[1]}" for w in windows])
            parts.append(f"{day_names[day_key]}:{time_ranges}")
    
    return "שעות: " + " | ".join(parts) if parts else "שעות לא הוגדרו"


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in Hebrew - COMPACT"""
    if slot_size_min == 15:
        return "כל 15 דק'"
    elif slot_size_min == 30:
        return "כל חצי שעה"
    elif slot_size_min == 60:
        return "כל שעה"
    elif slot_size_min == 90:
        return "כל 90 דק'"
    elif slot_size_min == 120:
        return "כל שעתיים"
    else:
        return f"כל {slot_size_min} דק'"


def _build_critical_rules_compact(business_name: str, today_hebrew: str, weekday_hebrew: str, greeting_text: str = "", required_fields: list = None) -> str:
    """
    BUILD 168: EXACT USER-PROVIDED SYSTEM PROMPT
    English prompt, Hebrew response
    """
    return """You are a phone assistant. 
You ALWAYS respond in Hebrew.

LANGUAGE RULE:
- Always speak Hebrew, even if the caller speaks another language.
- Switch language ONLY if the caller explicitly says:
  "אני לא מבין עברית", "אני לא מדבר עברית", or 
  "תדבר איתי באנגלית/שפה אחרת".

AUDIO & SPEECH RULES:
- Wait for CLEAR speech before responding.
- Completely ignore noise, silence, mumbling, music, wind, static, or background voices.
- Never guess unclear speech. If unsure, ask: "אפשר לחזור שוב?"
- Never speak over the customer — if they start talking, stop immediately.

PHONE NUMBER RULE:
- For phone numbers say ONLY:
  "נא להקיש את המספר בטלפון — מספר שמתחיל ב-05."

RESPONSE STYLE:
- Keep responses short (1–2 sentences).
- Warm, polite, human, and professional.
- No emojis.
- Ask one question at a time.

CONVERSATION FLOW LOGIC:
- The business prompt defines EXACTLY which fields to collect 
  (for example: name, phone, city, service type, problem description, etc.).
- You must follow the business prompt strictly.
- After collecting ALL required fields → move to verification.

VERIFICATION (CRITICAL):
1. After collecting all required fields from the business prompt,
   FIRST repeat them clearly to confirm:
   "רק כדי לוודא — אתה צריך {{service}} ב{{city}}, נכון?"
   (Adapt dynamically to the fields the business requires.)

2. WAIT for explicit confirmation ("כן", "נכון", "כן כן", "בדיוק").

3. If the customer corrects you:
   - Accept correction politely.
   - Repeat the updated details again for confirmation.
   - Do NOT proceed until the customer clearly confirms.

4. ONLY after confirmation:
   - Say your final closing message as defined by the business prompt.
   - Then end the call.

HANGUP LOGIC:
- If customer says "ביי", "להתראות", "תודה רבה":
  → Respond politely with a closing line, then end the call.
- If customer says "לא צריך" or "אין צורך":
  → Respond politely, but do NOT hang up until after your final closing line.
- If final business flow is completed:
  → End the call after your final message.

ROLE & BUSINESS LOGIC:
- The SYSTEM PROMPT controls safety, clarity, audio behavior, verification, and hangup rules.
- The BUSINESS PROMPT controls what information to collect and what final message to give.
- Always combine both: system rules + business logic.
"""
