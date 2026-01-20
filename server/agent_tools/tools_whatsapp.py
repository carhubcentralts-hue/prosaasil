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
    attachment_ids: Optional[list[int]] = Field(None, description="List of attachment IDs to send as images (from assets_get_media or direct attachment IDs)")

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
    Send WhatsApp message with optional media attachments
    
    Recipient (to):
    - If provided: use it
    - If not provided: auto-use customer_phone from context (conversation partner)
    
    Media attachments (attachment_ids):
    - Optional list of attachment IDs (from assets_get_media or direct attachment IDs)
    - Sends images/videos/documents from the system
    - Limit: 5 attachments per message
    - First image/media will include the message as caption
    
    Provider logic:
    - Auto: tries Baileys first, falls back to Twilio
    - Baileys: for real-time conversations (24h window)
    - Twilio: for templates and out-of-window messages
    """
    try:
        print(f"\n🔥🔥🔥 WHATSAPP_SEND CALLED! 🔥🔥🔥")
        print(f"   Message: '{input.message[:60] if len(input.message) > 60 else input.message}...'")
        print(f"   To (provided): {input.to}")
        logger.info(f"📱 whatsapp_send called: message='{input.message[:60]}...', to={input.to}")
        
        # 🔥 SMART PHONE RESOLUTION: Use provided 'to' or auto-detect from context
        recipient_phone = input.to
        
        if not recipient_phone:
            # Try to get from Flask g.agent_context
            from flask import g
            if hasattr(g, 'agent_context'):
                recipient_phone = g.agent_context.get('customer_phone') or g.agent_context.get('whatsapp_from')
                if recipient_phone:
                    logger.info(f"✅ whatsapp_send: Auto-detected recipient from context: {recipient_phone}")
        
        if not recipient_phone or recipient_phone == 'None':
            logger.error(f"❌ whatsapp_send: No valid recipient phone (got: {recipient_phone})")
            return SendWhatsAppOutput(
                status='error',
                provider='unknown',
                error='No recipient phone number provided'
            )
        
        # 🔥 CRITICAL FIX: Normalize phone to E.164 format!
        from server.agent_tools.phone_utils import normalize_il_phone
        normalized_phone = normalize_il_phone(recipient_phone)
        
        if not normalized_phone:
            logger.error(f"❌ whatsapp_send: Invalid phone format: {recipient_phone}")
            return SendWhatsAppOutput(
                status='error',
                provider='unknown',
                error=f'Invalid phone number format: {recipient_phone}'
            )
        
        logger.info(f"✅ Phone normalized: {recipient_phone} → {normalized_phone}")
        recipient_phone = normalized_phone
        
        # Get WhatsApp service with smart routing (with error handling)
        try:
            wa_service = get_whatsapp_service(provider=input.provider)
        except Exception as service_error:
            logger.error(f"❌ WhatsApp service unavailable: {service_error}")
            return SendWhatsAppOutput(
                status='error',
                provider='unknown',
                error='שירות WhatsApp לא זמין כרגע'
            )
        
        # 🖼️ Send media attachments first (if provided)
        media_sent_count = 0
        if input.attachment_ids and len(input.attachment_ids) > 0:
            try:
                from server.models_sql import Attachment
                from server.services.attachment_service import get_attachment_service
                from flask import g
                import base64
                
                # Get current business_id for multi-tenant validation
                current_business_id = None
                if hasattr(g, 'tenant') and g.tenant:
                    current_business_id = g.tenant
                elif hasattr(g, 'user') and g.user and isinstance(g.user, dict):
                    current_business_id = g.user.get('business_id')
                
                if not current_business_id:
                    logger.warning(f"⚠️ Cannot send media: business_id not found in context")
                else:
                    attachment_service = get_attachment_service()
                    
                    for attachment_id in input.attachment_ids[:5]:  # Limit to 5 images to avoid spam
                        try:
                            # 🔒 SECURITY: Fetch attachment with business_id validation (multi-tenant)
                            attachment = Attachment.query.filter_by(
                                id=attachment_id,
                                business_id=current_business_id,
                                is_deleted=False
                            ).first()
                            
                            if not attachment:
                                logger.warning(f"⚠️ Attachment {attachment_id} not found or not accessible for business {current_business_id}")
                                continue
                            
                            # Get attachment content
                            content = attachment_service.get_attachment_content(attachment.id, attachment.storage_path)
                            if not content:
                                logger.warning(f"⚠️ Could not read attachment {attachment_id}")
                                continue
                            
                            # Convert to base64
                            base64_data = base64.b64encode(content).decode('utf-8')
                            
                            # Determine media type
                            media_type = 'document'
                            if attachment.mime_type and attachment.mime_type.startswith('image/'):
                                media_type = 'image'
                            elif attachment.mime_type and attachment.mime_type.startswith('video/'):
                                media_type = 'video'
                            elif attachment.mime_type and attachment.mime_type.startswith('audio/'):
                                media_type = 'audio'
                            
                            # Prepare media dict
                            media_dict = {
                                'data': base64_data,
                                'mimetype': attachment.mime_type,
                                'filename': attachment.filename_original or f'file_{attachment_id}'
                            }
                            
                            # Send media with caption (first image gets the message)
                            caption = input.message if media_sent_count == 0 else ""
                            media_result = wa_service.send_media_message(
                                to=recipient_phone,
                                caption=caption,
                                media=media_dict,
                                media_type=media_type
                            )
                            
                            if media_result.get('status') == 'sent':
                                media_sent_count += 1
                                logger.info(f"✅ Sent media attachment {attachment_id} ({media_type})")
                            else:
                                logger.warning(f"⚠️ Failed to send media {attachment_id}: {media_result.get('error')}")
                        
                        except Exception as media_error:
                            logger.error(f"❌ Error sending media {attachment_id}: {media_error}")
                            continue
                    
                    if media_sent_count > 0:
                        logger.info(f"✅ Successfully sent {media_sent_count} media attachments")
                        # Media sent successfully - return success
                        # Note: Text message was already included as caption on first media
                        return SendWhatsAppOutput(
                            status='sent',
                            provider=wa_service.get_provider_name() if hasattr(wa_service, 'get_provider_name') else 'whatsapp',
                            message_id=f"media_{media_sent_count}",
                            error=None
                        )
                    else:
                        logger.warning(f"⚠️ No media attachments could be sent - falling back to text message")
                    
            except Exception as media_error:
                logger.error(f"❌ Error processing media attachments: {media_error}")
                # Continue to send text message even if media fails
        
        # Send text message (with timeout protection)
        try:
            result = wa_service.send_message(to=recipient_phone, message=input.message)
        except Exception as send_error:
            logger.error(f"❌ WhatsApp send failed: {send_error}")
            return SendWhatsAppOutput(
                status='error',
                provider='unknown',
                error='לא הצלחתי לשלוח WhatsApp כרגע'
            )
        
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
            error=error if error else ('לא זמין כרגע' if status != 'sent' else None)
        )
        
    except Exception as e:
        logger.error(f"❌ Unexpected error sending WhatsApp: {e}")
        import traceback
        traceback.print_exc()
        return SendWhatsAppOutput(
            status='error',
            provider='unknown',
            error='שירות WhatsApp לא זמין כרגע'
        )
