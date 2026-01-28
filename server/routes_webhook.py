"""
WhatsApp Webhook Routes - OPTIMIZED FOR SPEED ⚡
מסלולי Webhook של WhatsApp - מותאם למהירות מקסימלית

✅ PRODUCTION-READY:
- Uses unified jobs.py wrapper (no inline Redis/Queue)
- Atomic deduplication via Redis SETNX
- ACKs immediately, processes async via RQ
- No threading fallback - fully async via RQ workers
"""
import os
import logging
import uuid
from flask import Blueprint, request, jsonify
from server.extensions import csrf

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')
INTERNAL_SECRET = os.getenv('INTERNAL_SECRET')



def validate_internal_secret():
    """Validate that request has correct internal secret"""
    received_secret = request.headers.get('X-Internal-Secret')
    if not received_secret or received_secret != INTERNAL_SECRET:
        logger.warning(f"Webhook called without valid internal secret from {request.remote_addr}")
        return False
    return True

@csrf.exempt
@webhook_bp.route('/whatsapp/incoming', methods=['POST'])
def whatsapp_incoming():
    """
    ⚡ ULTRA-FAST WhatsApp webhook - ACK immediately, process in background
    תגובה מהירה לווטסאפ - מחזיר 200 מיד, מעבד ברקע
    """
    try:
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        events = payload.get('payload', {})
        messages = events.get('messages', [])
        
        if messages:
            # ✅ RQ: Enqueue webhook processing job with deduplication
            try:
                from server.services.jobs import enqueue_with_dedupe
                from server.jobs.webhook_process_job import webhook_process_job
                from server.services.business_resolver import resolve_business_with_fallback
                
                # Resolve business_id for faster job processing
                business_id, _ = resolve_business_with_fallback('whatsapp', tenant_id)
                
                # Enqueue with deduplication per message
                for msg in messages:
                    # Extract message ID for deduplication
                    message_id = msg.get('key', {}).get('id', '')
                    if not message_id:
                        logger.warning(f"⚠️ WhatsApp message without ID, skipping dedupe")
                        message_id = str(uuid.uuid4())
                    
                    # Generate dedupe key: webhook:baileys:{message_id}
                    dedupe_key = f"webhook:baileys:{message_id}"
                    
                    # Enqueue with atomic deduplication
                    job = enqueue_with_dedupe(
                        'default',
                        webhook_process_job,
                        dedupe_key=dedupe_key,
                        business_id=business_id,
                        tenant_id=tenant_id,
                        messages=[msg],  # Process one message per job for better deduplication
                        timeout=300,  # 5 minutes
                        ttl=600  # 10 minutes TTL
                    )
                    
                    if job:
                        logger.info(f"✅ Enqueued webhook_process_job for tenant={tenant_id}, msg_id={message_id[:8]}")
                    else:
                        logger.info(f"⏭️  Skipped duplicate webhook for msg_id={message_id[:8]}")
                        
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to enqueue webhook job: {e}")
                # No fallback - return 503 to indicate temporary failure
                # This prevents duplicate processing and maintains single execution path
                return jsonify({"error": "service_unavailable", "message": "Job queue temporarily unavailable"}), 503
        
        # ⚡ ACK immediately - don't wait for processing
        return '', 200
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return '', 200  # Still ACK to avoid retries



@csrf.exempt
@webhook_bp.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    """
    Receive WhatsApp connection status updates from Baileys service
    """
    try:
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        connection_status = payload.get('connection', 'unknown')
        push_name = payload.get('pushName', '')
        
        logger.info(f"WhatsApp status - tenant: {tenant_id}, status: {connection_status}, name: {push_name}")
        
        return '', 200
        
    except Exception as e:
        logger.error(f"WhatsApp status webhook error: {e}")
        return '', 200
