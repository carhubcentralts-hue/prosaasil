"""
WhatsApp Webhook Routes - Receive incoming events from Baileys service
מסלולי Webhook של WhatsApp - קבלת אירועים נכנסים מ-Baileys service
"""
import os
import logging
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

@csrf.exempt  # Bypass CSRF for internal webhook
@webhook_bp.route('/whatsapp/incoming', methods=['POST'])
def whatsapp_incoming():
    """
    Receive incoming WhatsApp events from Baileys service
    קבלת אירועי WhatsApp נכנסים מ-Baileys service
    """
    try:
        # Validate internal secret
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        # Get payload
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        events = payload.get('payload', {})
        
        logger.info(f"WhatsApp incoming webhook - tenant: {tenant_id}, events: {len(events.get('messages', []))}")
        
        # TODO: Process incoming messages/events
        # This is where you would:
        # 1. Parse WhatsApp messages
        # 2. Create leads from new contacts
        # 3. Update conversation threads
        # 4. Trigger AI responses if needed
        
        # For now, just log and acknowledge
        messages = events.get('messages', [])
        for msg in messages:
            from_number = msg.get('key', {}).get('remoteJid', 'unknown')
            message_text = msg.get('message', {}).get('conversation', '')
            logger.info(f"WhatsApp message from {from_number}: {message_text[:50]}...")
        
        return '', 204  # Acknowledge receipt
        
    except Exception as e:
        logger.error(f"WhatsApp incoming webhook error: {e}")
        return jsonify({"error": "processing_failed"}), 500

@csrf.exempt  # Bypass CSRF for internal webhook  
@webhook_bp.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    """
    Receive WhatsApp connection status updates from Baileys service
    קבלת עדכוני סטטוס חיבור WhatsApp מ-Baileys service  
    """
    try:
        # Validate internal secret
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        # Get payload
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        connection_status = payload.get('connection', 'unknown')
        push_name = payload.get('pushName', '')
        
        logger.info(f"WhatsApp status update - tenant: {tenant_id}, status: {connection_status}, name: {push_name}")
        
        # TODO: Update database with connection status
        # This is where you would:
        # 1. Update business WhatsApp connection status
        # 2. Notify UI of connection changes
        # 3. Log connection events for monitoring
        
        return '', 204  # Acknowledge receipt
        
    except Exception as e:
        logger.error(f"WhatsApp status webhook error: {e}")
        return jsonify({"error": "processing_failed"}), 500