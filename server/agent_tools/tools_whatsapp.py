"""
WhatsApp Tools for AgentKit - Send messages and confirmations
Integrates with existing WhatsApp service (Baileys/Twilio)
"""
from agents import function_tool
from pydantic import BaseModel, Field
from typing import Optional
from server.whatsapp_provider import get_whatsapp_service
import logging

logger = logging.getLogger(__name__)

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class SendWhatsAppInput(BaseModel):
    """Input for sending WhatsApp message"""
    to: Optional[str] = Field(None, description="Recipient phone in E.164 format (+972...). Leave empty to auto-use customer from context.")
    message: str = Field(..., description="Message text to send", min_length=1, max_length=4000)
    provider: Optional[str] = Field(None, description="Provider to use (baileys/twilio/auto)")

class SendWhatsAppOutput(BaseModel):
    """WhatsApp send result"""
    status: str  # sent/error
    provider: str  # baileys/twilio
    message_id: Optional[str] = None
    error: Optional[str] = None

# ================================================================================
# TOOLS
# ================================================================================

@function_tool
def whatsapp_send(input: SendWhatsAppInput) -> SendWhatsAppOutput:
    """
    Send WhatsApp message
    
    Recipient (to):
    - If provided: use it
    - If not provided: auto-use customer_phone from context (conversation partner)
    
    Provider logic:
    - Auto: tries Baileys first, falls back to Twilio
    - Baileys: for real-time conversations (24h window)
    - Twilio: for templates and out-of-window messages
    """
    try:
        # 🔥 SMART PHONE RESOLUTION: Use provided 'to' or auto-detect from context
        recipient_phone = input.to
        
        if not recipient_phone:
            # Try to get from Flask g.agent_context
            from flask import g
            if hasattr(g, 'agent_context'):
                recipient_phone = g.agent_context.get('customer_phone') or g.agent_context.get('whatsapp_from')
                if recipient_phone:
                    logger.info(f"✅ whatsapp_send: Auto-detected recipient from context: {recipient_phone}")
        
        if not recipient_phone:
            logger.error("❌ whatsapp_send: No recipient phone provided and none in context")
            return SendWhatsAppOutput(
                status='error',
                provider='unknown',
                error='No recipient phone number provided'
            )
        
        # Get WhatsApp service with smart routing
        wa_service = get_whatsapp_service(provider=input.provider)
        
        # Send message
        result = wa_service.send_message(to=recipient_phone, message=input.message)
        
        # Parse result
        status = result.get('status', 'unknown')
        provider = result.get('provider', 'unknown')
        message_id = result.get('sid') or result.get('message_id')
        error = result.get('error')
        
        if status == 'sent':
            logger.info(f"✅ WhatsApp message sent via {provider} to {recipient_phone}")
        else:
            logger.warning(f"⚠️ WhatsApp send failed via {provider} to {recipient_phone}: {error}")
        
        return SendWhatsAppOutput(
            status=status,
            provider=provider,
            message_id=message_id,
            error=error
        )
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp: {e}")
        return SendWhatsAppOutput(
            status='error',
            provider='unknown',
            error=str(e)
        )
