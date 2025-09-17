# server/routes_whatsapp.py - CANONICAL WhatsApp API
"""
Canonical WhatsApp API - Production Ready
Unified proxy to Baileys Multi-Tenant Service with tenant isolation
"""
from flask import Blueprint, request, jsonify, session, g
from server.auth_api import require_api_auth
import requests, os
import logging

logger = logging.getLogger(__name__)

# Canonical WhatsApp Blueprint - replaces all other WhatsApp routes
whatsapp_bp = Blueprint('whatsapp_canonical', __name__, url_prefix='/api/whatsapp')

# Configuration
BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
INTERNAL_SECRET = os.getenv('INTERNAL_SECRET')

def get_tenant_id():
    """Extract tenant_id from session/JWT context"""
    # Try various sources for tenant ID
    if hasattr(g, 'tenant_id'):
        return str(g.tenant_id)
    
    # From session (business impersonation or direct login)
    if session.get('impersonated_tenant_id'):
        return str(session.get('impersonated_tenant_id'))
    
    # From user session business_id
    user = session.get('al_user', {})
    if user.get('business_id'):
        return str(user.get('business_id'))
    
    # From headers (fallback for API calls)
    tenant_from_header = request.headers.get('X-Tenant-Id')
    if tenant_from_header:
        return str(tenant_from_header)
    
    # Default tenant for development/testing
    return "1"

def baileys_headers():
    """Generate headers for Baileys internal requests"""
    headers = {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET
    }
    return headers

def make_baileys_request(method, path, tenant_id=None, **kwargs):
    """Make authenticated request to Baileys service"""
    if not tenant_id:
        tenant_id = get_tenant_id()
    
    url = f"{BAILEYS_BASE}/whatsapp/{tenant_id}/{path}"
    
    try:
        response = requests.request(
            method=method,
            url=url, 
            headers=baileys_headers(),
            timeout=10,
            **kwargs
        )
        return response
    except requests.RequestException as e:
        logger.error(f"Baileys request failed: {method} {url} - {e}")
        raise

# === CORE WHATSAPP ENDPOINTS ===

@whatsapp_bp.route('/status', methods=['GET'])
@require_api_auth()
def get_status():
    """Get WhatsApp connection status for current tenant"""
    try:
        tenant_id = get_tenant_id()
        response = make_baileys_request('GET', 'status', tenant_id)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'tenant_id': tenant_id,
                'connected': data.get('connected', False),
                'pushName': data.get('pushName', ''),
                'hasQR': data.get('hasQR', False)
            })
        else:
            return jsonify({'success': False, 'error': 'status_unavailable'}), response.status_code
            
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@whatsapp_bp.route('/qr', methods=['GET'])
@require_api_auth()
def get_qr():
    """Get QR code for WhatsApp connection"""
    try:
        tenant_id = get_tenant_id()
        response = make_baileys_request('GET', 'qr', tenant_id)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'qr_data': data.get('dataUrl', ''),
                'tenant_id': tenant_id
            })
        elif response.status_code == 404:
            return jsonify({
                'success': False,
                'error': 'no_qr_available',
                'message': 'QR not available - might be connected already'
            }), 204
        else:
            return jsonify({'success': False, 'error': 'qr_unavailable'}), response.status_code
            
    except Exception as e:
        logger.error(f"QR fetch failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@whatsapp_bp.route('/start', methods=['POST'])
@require_api_auth()
def start_session():
    """Start WhatsApp session for current tenant"""
    try:
        tenant_id = get_tenant_id()
        response = make_baileys_request('POST', 'start', tenant_id)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'WhatsApp session started',
                'tenant_id': tenant_id
            })
        else:
            data = response.json() if response.content else {}
            return jsonify({
                'success': False, 
                'error': data.get('error', 'start_failed')
            }), response.status_code
            
    except Exception as e:
        logger.error(f"Start session failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@whatsapp_bp.route('/send', methods=['POST'])
@require_api_auth()
def send_message():
    """Send WhatsApp message via Baileys"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        to_number = data.get('to')
        text = data.get('text') or data.get('message')
        
        if not to_number or not text:
            return jsonify({
                'success': False, 
                'error': 'to and text are required'
            }), 400
        
        tenant_id = get_tenant_id()
        response = make_baileys_request('POST', 'send', tenant_id, json={
            'to': to_number,
            'text': text
        })
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'Message sent successfully',
                'tenant_id': tenant_id
            })
        else:
            data = response.json() if response.content else {}
            return jsonify({
                'success': False,
                'error': data.get('error', 'send_failed')
            }), response.status_code
            
    except Exception as e:
        logger.error(f"Send message failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@whatsapp_bp.route('/logout', methods=['POST'])
@require_api_auth()
def logout_session():
    """Logout WhatsApp session for current tenant"""
    try:
        tenant_id = get_tenant_id()
        response = make_baileys_request('POST', 'logout', tenant_id)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'WhatsApp session logged out',
                'tenant_id': tenant_id
            })
        else:
            data = response.json() if response.content else {}
            return jsonify({
                'success': False,
                'error': data.get('error', 'logout_failed')
            }), response.status_code
            
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# === LEGACY COMPATIBILITY ENDPOINTS ===

# Legacy routes for backward compatibility - redirect to canonical
@whatsapp_bp.route('/baileys/qr', methods=['GET'])
@require_api_auth()
def legacy_baileys_qr():
    """Legacy QR endpoint - redirects to canonical"""
    return get_qr()

@whatsapp_bp.route('/baileys/status', methods=['GET'])
@require_api_auth()
def legacy_baileys_status():
    """Legacy status endpoint - redirects to canonical"""
    return get_status()

# === DIAGNOSTIC ENDPOINTS ===

@whatsapp_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for WhatsApp service"""
    try:
        # Check Baileys service health
        response = requests.get(f"{BAILEYS_BASE}/healthz", timeout=5)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'baileys_service': 'healthy',
                'baileys_url': BAILEYS_BASE
            })
        else:
            return jsonify({
                'success': False,
                'baileys_service': 'unhealthy',
                'status_code': response.status_code
            }), 503
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'baileys_service': 'unreachable'
        }), 503

# === WEBHOOK ENDPOINTS ===

@whatsapp_bp.route('/webhook/incoming', methods=['POST'])
def webhook_incoming():
    """
    Webhook endpoint to receive incoming WhatsApp messages from Baileys service.
    Called by services/whatsapp/baileys_service.js with Internal Secret authentication.
    """
    try:
        # Validate Internal Secret
        received_secret = request.headers.get('X-Internal-Secret')
        if not received_secret or received_secret != INTERNAL_SECRET:
            logger.warning("Webhook rejected - invalid internal secret")
            return jsonify({'success': False, 'error': 'unauthorized'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'no_data'}), 400
        
        # Extract webhook data
        tenant_id = data.get('tenantId')
        from_number = data.get('from', '').replace('@s.whatsapp.net', '').replace('@c.us', '')
        message_text = data.get('text', '')
        message_id = data.get('messageId', '')
        message_type = data.get('type', 'text')
        timestamp = data.get('timestamp')
        
        if not tenant_id or not from_number or not message_text:
            logger.warning("Invalid webhook payload - missing required fields")
            return jsonify({'success': False, 'error': 'invalid_payload'}), 400
        
        logger.info(f"WhatsApp webhook received: tenant={tenant_id}, from={from_number}, type={message_type}")
        
        # Import here to avoid circular imports
        from server.dao_crm import upsert_thread, insert_message
        from server.api_whatsapp_unified import handle_whatsapp_logic
        
        # Find/create thread for this tenant and conversation
        thread_id = upsert_thread(
            business_id=int(tenant_id),
            type_="whatsapp",
            provider="baileys",
            peer_number=from_number
        )
        
        # Record incoming message
        message_record_id = insert_message(
            thread_id=thread_id,
            direction="in",
            message_type=message_type,
            content_text=message_text,
            provider_msg_id=message_id,
            status="received"
        )
        
        # Generate AI response with fallback
        ai_response = ""
        try:
            context = {
                "phone_number": from_number,
                "channel": "baileys",
                "thread_id": thread_id,
                "tenant_id": tenant_id
            }
            
            ai_response = handle_whatsapp_logic(message_text, business_id=int(tenant_id), context=context)
        except Exception as ai_error:
            logger.error(f"AI response generation failed: {ai_error}")
            # Continue processing even if AI fails
        
        # Send AI response back via Baileys
        if ai_response and len(ai_response.strip()) > 0:
            try:
                response = make_baileys_request('POST', 'send', tenant_id, json={
                    'to': from_number,
                    'text': ai_response
                })
                
                if response.status_code == 200:
                    # Record outbound AI response
                    insert_message(
                        thread_id=thread_id,
                        direction="out",
                        message_type="text",
                        content_text=ai_response,
                        provider_msg_id=f"ai_{message_id}",
                        status="sent"
                    )
                    logger.info(f"AI response sent via Baileys to {from_number} (tenant: {tenant_id})")
                else:
                    logger.error(f"Failed to send AI response via Baileys: {response.status_code}")
                    
            except Exception as send_error:
                logger.error(f"Error sending AI response: {send_error}")
        
        return jsonify({
            'success': True,
            'thread_id': thread_id,
            'message_id': message_record_id,
            'ai_response_sent': bool(ai_response and len(ai_response.strip()) > 0)
        })
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500