"""
WhatsApp Message Sending Job
Send WhatsApp messages with retry and Twilio fallback

This replaces the background thread in routes_whatsapp.py
"""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def send_whatsapp_message_job(
    business_id: int,
    tenant_id: str,
    remote_jid: str,
    response_text: str,
    wa_msg_id: int = None,
    lead_id: int = None,  # 🔥 NEW: For session tracking
    phone_e164: str = None  # 🔥 NEW: For session tracking
):
    """
    Send WhatsApp message with retry logic and Twilio fallback.
    
    Args:
        business_id: Business ID for multi-tenant routing
        tenant_id: Tenant ID (e.g., "business_1") for Baileys routing
        remote_jid: FULL WhatsApp JID (e.g., 972501234567@s.whatsapp.net or 823...@lid)
        response_text: The message text to send
        wa_msg_id: Optional incoming message ID for tracking
        lead_id: Optional lead ID for session tracking
        phone_e164: Optional phone E164 for session tracking
    
    Returns:
        dict: Send result summary
    """
    from server.whatsapp_provider import get_whatsapp_service
    from server.models_sql import WhatsAppMessage, Lead, db
    
    send_start = time.time()
    
    # 🔥 SAFETY CHECK: Never send to groups, broadcasts, newsletters, or status updates
    if (remote_jid.endswith('@g.us') or 
        remote_jid.endswith('@broadcast') or 
        remote_jid.endswith('@newsletter') or
        'status@broadcast' in remote_jid):
        logger.error(f"[WA-SEND-JOB] ❌ BLOCKED: Attempted to send to non-private chat {remote_jid[:30]}...")
        return {
            'status': 'blocked',
            'reason': 'non-private-chat',
            'remote_jid': remote_jid[:30],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    logger.info(f"[WA-SEND-JOB] Starting send to {remote_jid[:20]}... business_id={business_id} lead_id={lead_id}")
    
    # 🔥 LID FIX: Log clear message for LID vs standard JID
    if remote_jid.endswith('@lid'):
        logger.info(f"[WA-SEND-JOB] 🔵 Sending to LID: {remote_jid}")
    elif remote_jid.endswith('@s.whatsapp.net'):
        logger.info(f"[WA-SEND-JOB] 📱 Sending to standard WhatsApp: {remote_jid}")
    else:
        logger.warning(f"[WA-SEND-JOB] ⚠️ Sending to non-standard JID: {remote_jid}")
    
    # 🔥 CRITICAL: Use app context for DB operations
    from flask import current_app
    
    with current_app.app_context():
        try:
            # 🔥 NEW: If lead_id/phone_e164 not provided, try to look them up
            if not lead_id or not phone_e164:
                try:
                    # Extract phone from remote_jid
                    phone_clean = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
                    
                    # Try to find lead by phone
                    from server.agent_tools.phone_utils import normalize_phone
                    phone_normalized = normalize_phone(phone_clean)
                    
                    if phone_normalized:
                        lead = Lead.query.filter_by(
                            business_id=business_id,
                            phone_e164=phone_normalized
                        ).first()
                        
                        if lead:
                            lead_id = lead.id
                            phone_e164 = lead.phone_e164
                            logger.info(f"[WA-SEND-JOB] Found lead for session tracking: lead_id={lead_id}")
                except Exception as lookup_err:
                    logger.debug(f"[WA-SEND-JOB] Could not lookup lead: {lookup_err}")
            
            # Get WhatsApp service (Baileys or Twilio)
            wa_service = get_whatsapp_service(tenant_id)
            
            # Send message (handles retries internally)
            result = wa_service.send_message(to=remote_jid, message=response_text, tenant_id=tenant_id)
            
            # Create outgoing message record
            try:
                # 🔥 CRITICAL FIX: Store FULL JID (including @lid/@s.whatsapp.net) so history can find it!
                # Previously stored only: remote_jid.split('@')[0] which broke history matching
                outgoing_msg = WhatsAppMessage(
                    business_id=business_id,
                    to_number=remote_jid,  # 🔥 FIX: Store FULL JID for history matching
                    body=response_text,
                    direction='out',  # 🔥 Consistent 'in'/'out' values (not 'outbound')
                    provider='baileys',  # Default provider for this job
                    status='sent',
                    message_type='text',
                    source='bot',  # 🔥 CONTEXT FIX: Mark as bot-generated for LLM context
                    lead_id=lead_id  # 🔥 NEW: Link to lead
                )
                db.session.add(outgoing_msg)
                db.session.commit()
                logger.info(f"[WA-SEND-JOB] ✅ Outgoing message saved to DB: {outgoing_msg.id} (source=bot, lead_id={lead_id})")
            except Exception as db_err:
                logger.error(f"[WA-SEND-JOB] ⚠️ Failed to save outgoing message to DB: {db_err}")
                db.session.rollback()
            
            # 🔥 NEW: Track session for outbound message
            try:
                from server.services.whatsapp_session_service import update_session_activity
                
                # Extract clean phone for session tracking
                clean_phone = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
                
                update_session_activity(
                    business_id=business_id,
                    customer_wa_id=clean_phone,
                    direction="out",
                    provider='baileys',
                    lead_id=lead_id,  # 🔥 FIX: Pass lead_id for canonical_key
                    phone_e164=phone_e164  # 🔥 FIX: Pass phone_e164 for canonical_key
                )
                logger.info(f"[WA-SEND-JOB] ✅ Session activity tracked: lead_id={lead_id}, phone={phone_e164}")
            except Exception as session_err:
                logger.warning(f"[WA-SEND-JOB] ⚠️ Session tracking failed: {session_err}")
            
            send_duration = time.time() - send_start
            
            # Check if send was successful (result is a dict with 'status' key)
            success = result and (result.get('status') in ['sent', 'queued', 'accepted'])
            
            if success:
                logger.info(f"[WA-SEND-JOB] ✅ Message sent successfully in {send_duration:.2f}s")
                return {
                    'status': 'success',
                    'remote_jid': remote_jid[:20],
                    'duration': send_duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"[WA-SEND-JOB] ❌ Message send failed after {send_duration:.2f}s")
                return {
                    'status': 'failed',
                    'remote_jid': remote_jid[:20],
                    'duration': send_duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            send_duration = time.time() - send_start
            logger.error(f"[WA-SEND-JOB] ❌ Exception during send: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'remote_jid': remote_jid[:20],
                'duration': send_duration,
                'timestamp': datetime.utcnow().isoformat()
            }
