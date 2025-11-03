"""
WhatsApp Tools for AgentKit - Send messages and confirmations
Integrates with existing WhatsApp service (Baileys/Twilio)
"""
from openai_agents import tool
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
    to: str = Field(..., description="Recipient phone in E.164 format (+972...)")
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

@tool(
    name="whatsapp.send",
    description="Send a WhatsApp message to a customer. Automatically selects best provider (Baileys or Twilio). Use for appointment confirmations, reminders, or follow-ups.",
    input_model=SendWhatsAppInput,
    output_model=SendWhatsAppOutput
)
def whatsapp_send(input: SendWhatsAppInput) -> SendWhatsAppOutput:
    """
    Send WhatsApp message
    
    Provider logic:
    - Auto: tries Baileys first, falls back to Twilio
    - Baileys: for real-time conversations (24h window)
    - Twilio: for templates and out-of-window messages
    """
    try:
        # Get WhatsApp service with smart routing
        wa_service = get_whatsapp_service(provider=input.provider)
        
        # Send message
        result = wa_service.send_message(to=input.to, message=input.message)
        
        # Parse result
        status = result.get('status', 'unknown')
        provider = result.get('provider', 'unknown')
        message_id = result.get('sid') or result.get('message_id')
        error = result.get('error')
        
        if status == 'sent':
            logger.info(f"✅ WhatsApp message sent via {provider} to {input.to}")
        else:
            logger.warning(f"⚠️ WhatsApp send failed via {provider}: {error}")
        
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
