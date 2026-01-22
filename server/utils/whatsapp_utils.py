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
