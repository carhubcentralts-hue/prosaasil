"""
WhatsApp Utilities - Message extraction and trace ID generation
עזרי WhatsApp - חילוץ הודעות ויצירת trace_id
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def generate_trace_id(business_id: int, remote_jid: str, message_id: str = None) -> str:
    """
    Generate unified trace ID for end-to-end tracking
    
    Format: business_id:remoteJid:message_id
    
    Args:
        business_id: Business/tenant ID
        remote_jid: WhatsApp JID (e.g., 972501234567@s.whatsapp.net)
        message_id: Optional message ID
    
    Returns:
        str: Trace ID for logging
    """
    phone = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
    if message_id:
        return f"{business_id}:{phone}:{message_id}"
    else:
        return f"{business_id}:{phone}"


def extract_inbound_text(msg: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    Extract text from WhatsApp message in any format
    
    Supports:
    - conversation
    - extendedTextMessage.text
    - imageMessage.caption
    - videoMessage.caption
    - documentMessage.caption
    - responses (for button replies)
    
    Args:
        msg: WhatsApp message object
    
    Returns:
        tuple: (text, format_type) where text is always a string (empty if no text found)
    """
    message_content = msg.get('message', {})
    
    # Try conversation (most common)
    text = message_content.get('conversation')
    if text:
        return text, 'conversation'
    
    # Try extendedTextMessage
    extended = message_content.get('extendedTextMessage', {})
    text = extended.get('text')
    if text:
        return text, 'extendedTextMessage'
    
    # Try imageMessage caption
    image = message_content.get('imageMessage', {})
    text = image.get('caption')
    if text:
        return text, 'imageMessage.caption'
    
    # Try videoMessage caption
    video = message_content.get('videoMessage', {})
    text = video.get('caption')
    if text:
        return text, 'videoMessage.caption'
    
    # Try documentMessage caption
    document = message_content.get('documentMessage', {})
    text = document.get('caption')
    if text:
        return text, 'documentMessage.caption'
    
    # Try audioMessage (no text, but we should note it)
    if message_content.get('audioMessage'):
        return '', 'audioMessage'
    
    # Try button response
    button_response = message_content.get('buttonsResponseMessage', {})
    text = button_response.get('selectedDisplayText')
    if text:
        return text, 'buttonsResponseMessage'
    
    # Try template button response
    template_response = message_content.get('templateButtonReplyMessage', {})
    text = template_response.get('selectedDisplayText')
    if text:
        return text, 'templateButtonReplyMessage'
    
    # Try list response
    list_response = message_content.get('listResponseMessage', {})
    text = list_response.get('title')
    if text:
        return text, 'listResponseMessage'
    
    # Return empty string if no text found
    return '', None


def normalize_whatsapp_to(
    to: str,
    lead_phone: Optional[str] = None,
    lead_reply_jid: Optional[str] = None,
    lead_id: Optional[int] = None,
    business_id: Optional[int] = None
) -> tuple[str, str]:
    """
    ✅ UNIFIED: Normalize WhatsApp destination JID with consistent logic
    
    This function ensures both /api/whatsapp/send and /api/crm/threads/{phone}/message
    use the EXACT same normalization logic to prevent Baileys 500 errors.
    
    Priority:
    1. If lead_reply_jid exists and is valid s.whatsapp.net → use it (most reliable)
    2. Otherwise normalize 'to' parameter: remove +, spaces, dashes, add @s.whatsapp.net
    3. If result is @g.us (group) → raise error (don't send to groups)
    
    Args:
        to: Destination from client (can be +972XXX, 972XXX, or with @s.whatsapp.net)
        lead_phone: Lead's phone_e164 from database (optional)
        lead_reply_jid: Lead's reply_jid from database (optional, most reliable)
        lead_id: Lead ID for logging (optional)
        business_id: Business ID for logging (optional)
    
    Returns:
        tuple: (normalized_jid, source) where source is 'reply_jid', 'to', or 'phone'
        
    Raises:
        ValueError: If trying to send to group/broadcast
        
    Examples:
        >>> normalize_whatsapp_to("+972509237456", None, "972509237456@s.whatsapp.net")
        ("972509237456@s.whatsapp.net", "reply_jid")
        
        >>> normalize_whatsapp_to("+972509237456", None, None)
        ("972509237456@s.whatsapp.net", "to")
        
        >>> normalize_whatsapp_to("972509237456@g.us", None, None)
        ValueError: Cannot send to groups
    """
    source = "unknown"
    jid = None
    
    # Priority 1: Use reply_jid if available and is s.whatsapp.net (most reliable)
    if lead_reply_jid and isinstance(lead_reply_jid, str):
        lead_reply_jid = lead_reply_jid.strip()
        if '@s.whatsapp.net' in lead_reply_jid:
            jid = lead_reply_jid
            source = "reply_jid"
            logger.debug(f"[WA-NORMALIZE] Using reply_jid: {jid}")
    
    # Priority 2: Normalize 'to' parameter
    if not jid and to:
        to_clean = str(to).strip()
        
        # 🔥 CRITICAL: Check for group/broadcast BEFORE normalization
        if ('@g.us' in to_clean or 
            '@broadcast' in to_clean or 
            '@newsletter' in to_clean or
            'status@broadcast' in to_clean):
            logger.warning(f"[WA-NORMALIZE] ❌ BLOCKED: Attempt to send to non-private chat: {to_clean[:50]}")
            raise ValueError("Cannot send to groups, broadcasts, or status updates")
        
        # If already has @s.whatsapp.net, use it
        if '@s.whatsapp.net' in to_clean:
            jid = to_clean
            source = "to"
        else:
            # Remove @ suffix if present
            to_clean = to_clean.split('@')[0]
            
            # Remove +, spaces, dashes, and any non-numeric characters
            phone_only = ''.join(c for c in to_clean if c.isdigit())
            
            if phone_only:
                jid = f"{phone_only}@s.whatsapp.net"
                source = "to"
                logger.debug(f"[WA-NORMALIZE] Normalized to: {to} → {jid}")
    
    # Priority 3: Fallback to lead_phone if provided
    if not jid and lead_phone:
        phone_clean = str(lead_phone).strip().replace('+', '').replace(' ', '').replace('-', '')
        phone_only = ''.join(c for c in phone_clean if c.isdigit())
        if phone_only:
            jid = f"{phone_only}@s.whatsapp.net"
            source = "phone"
            logger.debug(f"[WA-NORMALIZE] Using lead phone: {jid}")
    
    # Validate we got a JID
    if not jid:
        logger.error(f"[WA-NORMALIZE] Failed to normalize: to={to}, lead_phone={lead_phone}, lead_reply_jid={lead_reply_jid}")
        raise ValueError("Could not normalize WhatsApp destination")
    
    # 🔥 CRITICAL: Block sending to groups, broadcasts, newsletters
    if (jid.endswith('@g.us') or 
        jid.endswith('@broadcast') or 
        jid.endswith('@newsletter') or
        'status@broadcast' in jid):
        logger.warning(f"[WA-NORMALIZE] ❌ BLOCKED: Attempt to send to non-private chat: {jid[:50]}")
        raise ValueError("Cannot send to groups, broadcasts, or status updates")
    
    # Log final result
    logger.info(f"[WA-SEND] normalized_to={jid} source={source} lead_id={lead_id} business_id={business_id}")
    
    return jid, source


def normalize_conversation_key(
    remote_jid: str,
    from_number_e164: Optional[str] = None,
    phone_for_ai_check: Optional[str] = None
) -> str:
    """
    🔥 SINGLE SOURCE FOR CONVERSATION KEY
    
    Generate a consistent conversation key for tracking message history,
    conversation state, and deduplication across all WhatsApp operations.
    
    This ensures:
    - Save inbound message → same key
    - Load previous_messages → same key
    - Conversation state get/set → same key
    - Dedup keys → same key
    - Scheduled messages recipient → same key
    
    Priority:
    1. phone_for_ai_check (handles @lid, Android, iPhone consistently)
    2. from_number_e164 (E.164 format, standard)
    3. remote_jid (original JID as fallback)
    
    Args:
        remote_jid: Original WhatsApp JID from message
        from_number_e164: Normalized E.164 phone (if available)
        phone_for_ai_check: Special normalized phone for AI context (handles @lid)
    
    Returns:
        str: Consistent conversation key
        
    Examples:
        >>> normalize_conversation_key("972501234567@s.whatsapp.net", "+972501234567", "+972501234567")
        "+972501234567"
        
        >>> normalize_conversation_key("ABC123@lid", None, "972501234567@s.whatsapp.net")
        "972501234567@s.whatsapp.net"
        
        >>> normalize_conversation_key("972501234567@s.whatsapp.net", None, None)
        "972501234567@s.whatsapp.net"
    """
    # Priority 1: phone_for_ai_check (most reliable, handles @lid)
    if phone_for_ai_check:
        logger.debug(f"[CONV-KEY] Using phone_for_ai_check: {phone_for_ai_check[:30]}")
        return phone_for_ai_check
    
    # Priority 2: from_number_e164 (E.164 format)
    if from_number_e164:
        logger.debug(f"[CONV-KEY] Using from_number_e164: {from_number_e164}")
        return from_number_e164
    
    # Priority 3: remote_jid (original JID)
    logger.debug(f"[CONV-KEY] Using remote_jid: {remote_jid[:30]}")
    return remote_jid


def get_canonical_conversation_key(
    business_id: int,
    lead_id: Optional[int] = None,
    phone_e164: Optional[str] = None
) -> str:
    """
    🎯 CANONICAL CONVERSATION KEY - Single Source of Truth
    
    Generate THE authoritative key for conversation identification.
    This ensures one conversation per person, regardless of how they're identified.
    
    Rules:
    1. If lead_id exists: key = "lead:{business_id}:{lead_id}"
    2. Otherwise: key = "phone:{business_id}:{phone_e164}"
    
    This key is used for:
    - WhatsAppConversation.canonical_key (DB unique constraint)
    - Conversation deduplication
    - Session tracking
    
    Args:
        business_id: Business/tenant ID
        lead_id: Lead ID if customer is identified
        phone_e164: Normalized E.164 phone number (with +)
        
    Returns:
        str: Canonical conversation key
        
    Raises:
        ValueError: If neither lead_id nor phone_e164 is provided
        
    Examples:
        >>> get_canonical_conversation_key(1, lead_id=123)
        "lead:1:123"
        
        >>> get_canonical_conversation_key(1, phone_e164="+972501234567")
        "phone:1:+972501234567"
        
        >>> get_canonical_conversation_key(1, lead_id=123, phone_e164="+972501234567")
        "lead:1:123"  # lead_id takes priority
    """
    if not business_id:
        raise ValueError("business_id is required")
    
    # Priority 1: Lead ID (most reliable, survives phone changes)
    if lead_id:
        key = f"lead:{business_id}:{lead_id}"
        logger.debug(f"[CANONICAL_KEY] Generated: {key}")
        return key
    
    # Priority 2: Phone E.164 (for unidentified customers)
    if phone_e164:
        # Ensure phone has + prefix for consistency
        if not phone_e164.startswith('+'):
            phone_e164 = f"+{phone_e164}"
        key = f"phone:{business_id}:{phone_e164}"
        logger.debug(f"[CANONICAL_KEY] Generated: {key}")
        return key
    
    # Error: Need at least one identifier
    raise ValueError("Either lead_id or phone_e164 is required for canonical key")

