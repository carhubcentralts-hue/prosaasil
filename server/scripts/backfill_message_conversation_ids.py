"""
Backfill conversation_id for existing WhatsApp messages

🎯 PURPOSE: Link existing messages to their conversations to prevent thread splitting
🔥 CRITICAL: This fixes the issue where inbound/outbound messages appear as separate threads

This script:
1. Finds all WhatsApp messages without conversation_id
2. For each message, finds or creates the appropriate conversation
3. Links the message to the conversation using conversation_id

Usage:
    python -m server.scripts.backfill_message_conversation_ids
"""

import logging
import sys
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def backfill_message_conversation_ids():
    """Backfill conversation_id for existing WhatsApp messages"""
    from server.app import create_app
    from server.db import db
    from server.models_sql import WhatsAppMessage, WhatsAppConversation, Lead
    from server.utils.whatsapp_utils import get_canonical_conversation_key
    from server.agent_tools.phone_utils import normalize_phone
    
    app = create_app()
    
    with app.app_context():
        logger.info("=" * 80)
        logger.info("Starting conversation_id backfill for WhatsApp messages")
        logger.info("=" * 80)
        
        # Get all messages without conversation_id
        messages_without_conv = WhatsAppMessage.query.filter(
            WhatsAppMessage.conversation_id.is_(None)
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        logger.info(f"Found {len(messages_without_conv)} messages without conversation_id")
        
        if len(messages_without_conv) == 0:
            logger.info("✅ All messages already have conversation_id - nothing to do")
            return
        
        # Track statistics
        stats = {
            'total': len(messages_without_conv),
            'linked': 0,
            'skipped_no_phone': 0,
            'errors': 0,
            'conversations_created': 0,
            'conversations_reused': 0
        }
        
        # Process each message
        for i, msg in enumerate(messages_without_conv):
            try:
                if (i + 1) % 100 == 0:
                    logger.info(f"Progress: {i + 1}/{len(messages_without_conv)} messages processed")
                
                # Skip if no phone number
                if not msg.to_number:
                    logger.warning(f"Message {msg.id} has no to_number, skipping")
                    stats['skipped_no_phone'] += 1
                    continue
                
                # Normalize phone to E.164
                phone_e164 = normalize_phone(msg.to_number)
                if not phone_e164 and not msg.to_number.startswith('+'):
                    phone_e164 = f"+{msg.to_number}"
                
                # Find lead for this phone
                lead = None
                if phone_e164:
                    lead = Lead.query.filter_by(
                        business_id=msg.business_id,
                        phone_e164=phone_e164
                    ).first()
                
                # If message already has lead_id, use it
                if msg.lead_id and not lead:
                    lead = Lead.query.get(msg.lead_id)
                
                # Generate canonical key
                try:
                    canonical_key = get_canonical_conversation_key(
                        business_id=msg.business_id,
                        lead_id=lead.id if lead else None,
                        phone_e164=phone_e164
                    )
                except Exception as e:
                    logger.warning(f"Could not generate canonical key for message {msg.id}: {e}")
                    stats['errors'] += 1
                    continue
                
                # Find or create conversation
                conversation = WhatsAppConversation.query.filter_by(
                    business_id=msg.business_id,
                    canonical_key=canonical_key
                ).first()
                
                if not conversation:
                    # Create new conversation
                    conversation = WhatsAppConversation()
                    conversation.business_id = msg.business_id
                    conversation.canonical_key = canonical_key
                    conversation.customer_number = msg.to_number
                    conversation.customer_wa_id = msg.to_number
                    conversation.lead_id = lead.id if lead else None
                    conversation.provider = msg.provider or 'baileys'
                    conversation.started_at = msg.created_at or datetime.utcnow()
                    conversation.last_message_at = msg.created_at or datetime.utcnow()
                    conversation.is_open = True
                    
                    if lead:
                        conversation.customer_name = lead.name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
                    
                    db.session.add(conversation)
                    db.session.flush()  # Get conversation.id
                    stats['conversations_created'] += 1
                    logger.debug(f"Created conversation {conversation.id} for canonical_key={canonical_key}")
                else:
                    stats['conversations_reused'] += 1
                    # Update last_message_at if this message is newer
                    if msg.created_at and (not conversation.last_message_at or msg.created_at > conversation.last_message_at):
                        conversation.last_message_at = msg.created_at
                
                # Link message to conversation
                msg.conversation_id = conversation.id
                
                # Also update lead_id if we found one
                if lead and not msg.lead_id:
                    msg.lead_id = lead.id
                
                stats['linked'] += 1
                
                # Commit every 100 messages
                if (i + 1) % 100 == 0:
                    db.session.commit()
                    logger.info(f"  ✅ Committed {i + 1} messages")
                
            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {e}")
                stats['errors'] += 1
                db.session.rollback()
                continue
        
        # Final commit
        try:
            db.session.commit()
            logger.info("✅ Final commit successful")
        except Exception as e:
            logger.error(f"❌ Final commit failed: {e}")
            db.session.rollback()
            stats['errors'] += 1
        
        # Print statistics
        logger.info("=" * 80)
        logger.info("Backfill complete! Statistics:")
        logger.info(f"  Total messages processed: {stats['total']}")
        logger.info(f"  Messages linked: {stats['linked']}")
        logger.info(f"  Conversations created: {stats['conversations_created']}")
        logger.info(f"  Conversations reused: {stats['conversations_reused']}")
        logger.info(f"  Skipped (no phone): {stats['skipped_no_phone']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("=" * 80)
        
        if stats['linked'] > 0:
            logger.info("✅ Success! Messages are now linked to conversations")
            logger.info("   This should fix the conversation splitting issue in the UI")
        
        return stats


if __name__ == '__main__':
    backfill_message_conversation_ids()
