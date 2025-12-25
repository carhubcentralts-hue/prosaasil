"""
WhatsApp Webhook Secret Management API
Provides secure webhook secret generation and retrieval for n8n integration
"""
from flask import Blueprint, request, jsonify, session, g
from server.models_sql import Business, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
import secrets
import logging

logger = logging.getLogger(__name__)

webhook_secret_bp = Blueprint('webhook_secret', __name__)


def generate_webhook_secret():
    """
    Generate a secure webhook secret with wh_n8n_ prefix
    Format: wh_n8n_<48_hex_chars> (24 bytes = 48 hex)
    """
    random_hex = secrets.token_hex(24)  # 24 bytes = 48 hex characters
    return f"wh_n8n_{random_hex}"


def mask_secret(secret):
    """
    Mask webhook secret for secure display
    Shows: wh_n8n_****...b7 (first 7 chars + last 2 chars)
    """
    if not secret:
        return None
    if len(secret) < 10:
        return "wh_n8n_****"
    # Show wh_n8n_ prefix and last 2 chars
    return f"{secret[:7]}{'*' * (len(secret) - 9)}{secret[-2:]}"


@webhook_secret_bp.route('/api/business/settings/webhook-secret', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'manager'])
def get_webhook_secret():
    """
    Get current webhook secret (masked)
    Returns masked secret and has_secret flag
    Never returns full secret
    """
    try:
        # Get business context
        business_id = g.get('tenant') or getattr(g, 'business_id', None)
        if not business_id:
            user = session.get('user') or session.get('al_user') or {}
            business_id = session.get('impersonated_tenant_id') or (user.get('business_id') if isinstance(user, dict) else None)
        
        if not business_id:
            return jsonify({"ok": False, "error": "No business context found"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"ok": False, "error": "Business not found"}), 404
        
        has_secret = business.webhook_secret is not None and business.webhook_secret != ""
        
        return jsonify({
            "ok": True,
            "webhook_secret_masked": mask_secret(business.webhook_secret) if has_secret else None,
            "has_secret": has_secret
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook secret: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500


@webhook_secret_bp.route('/api/business/settings/webhook-secret/rotate', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin', 'manager'])
def rotate_webhook_secret():
    """
    Generate/rotate webhook secret
    Returns full secret (one-time reveal) and masked version
    """
    try:
        # Get business context
        business_id = g.get('tenant') or getattr(g, 'business_id', None)
        if not business_id:
            user = session.get('user') or session.get('al_user') or {}
            business_id = session.get('impersonated_tenant_id') or (user.get('business_id') if isinstance(user, dict) else None)
        
        if not business_id:
            return jsonify({"ok": False, "error": "No business context found"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"ok": False, "error": "Business not found"}), 404
        
        # Generate new secret
        max_attempts = 5
        for attempt in range(max_attempts):
            new_secret = generate_webhook_secret()
            
            # Check uniqueness
            existing = Business.query.filter_by(webhook_secret=new_secret).first()
            if not existing:
                break
            
            if attempt == max_attempts - 1:
                return jsonify({"ok": False, "error": "Failed to generate unique secret"}), 500
        
        # Update business with new secret
        old_secret_masked = mask_secret(business.webhook_secret) if business.webhook_secret else None
        business.webhook_secret = new_secret
        db.session.commit()
        
        # Log the rotation (masked only)
        logger.info(f"Webhook secret rotated for business {business_id}: {old_secret_masked} -> {mask_secret(new_secret)}")
        
        return jsonify({
            "ok": True,
            "webhook_secret": new_secret,  # Full secret - one-time reveal
            "webhook_secret_masked": mask_secret(new_secret)
        })
        
    except Exception as e:
        logger.error(f"Error rotating webhook secret: {e}")
        db.session.rollback()
        return jsonify({"ok": False, "error": "Internal server error"}), 500
