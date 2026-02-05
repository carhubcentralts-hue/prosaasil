"""
Webhook Leads API Routes - CRUD for webhook configuration + ingestion endpoint

Provides:
1. CRUD operations for webhook_lead_ingest configuration (max 3 per business)
2. Public webhook endpoint for lead ingestion from external sources (Make, Zapier, etc.)
3. Duplicate prevention by phone number
4. Best-effort payload field extraction
"""
import os
import logging
import secrets
from flask import Blueprint, jsonify, request, g
from server.models_sql import WebhookLeadIngest, Lead, LeadStatus, Business
from server.db import db
from server.auth_api import require_api_auth
from datetime import datetime
from sqlalchemy import func

logger = logging.getLogger(__name__)

webhook_leads_bp = Blueprint('webhook_leads', __name__, url_prefix='/api')


def generate_webhook_secret():
    """Generate a secure random secret for webhook authentication"""
    return f"wh_{secrets.token_urlsafe(32)}"


@webhook_leads_bp.route('/leads/webhooks', methods=['POST'])
@require_api_auth
def create_webhook():
    """
    Create a new webhook configuration
    
    POST /api/leads/webhooks
    Body: {
        "name": "Make Source 1",
        "status_id": 123
    }
    
    Returns: {
        "id": 1,
        "name": "Make Source 1",
        "secret": "wh_...",
        "status_id": 123,
        "is_active": true,
        "created_at": "2024-01-01T00:00:00"
    }
    """
    # 🔍 Log incoming request for debugging
    logger.info(f"[LEAD_WEBHOOK_CREATE] Received request: method={request.method}, business_id={getattr(g, 'business_id', None)}")
    logger.info(f"[LEAD_WEBHOOK_CREATE] payload={request.get_json()}")
    
    try:
        # Parse JSON safely and validate it's a dict
        data = request.get_json(silent=True)
        
        if not isinstance(data, dict):
            return jsonify({
                "error": "Invalid JSON payload",
                "details": "Expected application/json body with valid JSON object"
            }), 400
        
        business_id = g.business_id
        
        # Validate required fields
        name = (data.get('name') or '').strip()
        status_id = data.get('status_id')
        
        if not name:
            return jsonify({"error": "name is required"}), 400
        
        if not status_id:
            return jsonify({"error": "status_id is required"}), 400
        
        # Check if status exists and belongs to this business
        status = LeadStatus.query.filter_by(
            id=status_id,
            business_id=business_id
        ).first()
        
        if not status:
            return jsonify({"error": "Invalid status_id or status does not belong to this business"}), 400
        
        # Check maximum limit: 3 webhooks per business
        existing_count = WebhookLeadIngest.query.filter_by(
            business_id=business_id
        ).count()
        
        if existing_count >= 3:
            return jsonify({
                "error": "Maximum 3 webhooks per business",
                "message": "מקסימום 3 webhooks לכל עסק. מחק webhook קיים כדי ליצור חדש."
            }), 400
        
        # Generate secret
        secret = generate_webhook_secret()
        
        # Create webhook
        webhook = WebhookLeadIngest(
            business_id=business_id,
            name=name,
            secret=secret,
            status_id=status_id,
            is_active=True
        )
        
        db.session.add(webhook)
        db.session.commit()
        
        logger.info(f"✅ Created webhook {webhook.id} for business {business_id}: {name}")
        
        return jsonify({
            "id": webhook.id,
            "name": webhook.name,
            "secret": webhook.secret,
            "status_id": webhook.status_id,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else None
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Error creating webhook: {e}", exc_info=True)
        db.session.rollback()
        
        # Check if it's a table-not-found error (migration not run)
        error_msg = str(e).lower()
        if 'webhook_lead_ingest' in error_msg and ('does not exist' in error_msg or 'no such table' in error_msg):
            logger.error("❌ CRITICAL: webhook_lead_ingest table does not exist - migrations need to run!")
            return jsonify({
                "error": "Database not initialized",
                "message": "The webhook_lead_ingest table does not exist. Migrations need to run.",
                "details": "Run migrations with RUN_MIGRATIONS=1 or execute: python -m server.db_migrate"
            }), 500
        
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@webhook_leads_bp.route('/leads/webhooks', methods=['GET'])
@require_api_auth
def list_webhooks():
    """
    List all webhooks for the current business
    
    GET /api/leads/webhooks
    
    Returns: [{
        "id": 1,
        "name": "Make Source 1",
        "secret": "wh_...",
        "status_id": 123,
        "status_name": "חדש",
        "is_active": true,
        "created_at": "2024-01-01T00:00:00"
    }]
    """
    try:
        business_id = g.business_id
        
        webhooks = WebhookLeadIngest.query.filter_by(
            business_id=business_id
        ).order_by(WebhookLeadIngest.created_at).all()
        
        result = []
        for webhook in webhooks:
            result.append({
                "id": webhook.id,
                "name": webhook.name,
                "secret": webhook.secret,
                "status_id": webhook.status_id,
                "status_name": webhook.status.label if webhook.status else None,
                "is_active": webhook.is_active,
                "created_at": webhook.created_at.isoformat() if webhook.created_at else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"❌ Error listing webhooks: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@webhook_leads_bp.route('/leads/webhooks/<int:webhook_id>', methods=['PATCH'])
@require_api_auth
def update_webhook(webhook_id):
    """
    Update a webhook configuration
    
    PATCH /api/leads/webhooks/{id}
    Body: {
        "name": "Updated Name",  # optional
        "status_id": 456,        # optional
        "is_active": false,      # optional
        "regenerate_secret": true # optional - generates new secret if true
    }
    
    Returns: {
        "id": 1,
        "name": "Updated Name",
        "secret": "wh_...",
        "status_id": 456,
        "is_active": false,
        "created_at": "2024-01-01T00:00:00"
    }
    """
    try:
        # Parse JSON safely and validate it's a dict
        data = request.get_json(silent=True)
        
        if not isinstance(data, dict):
            return jsonify({
                "error": "Invalid JSON payload",
                "details": "Expected application/json body with valid JSON object"
            }), 400
        
        business_id = g.business_id
        
        # Find webhook
        webhook = WebhookLeadIngest.query.filter_by(
            id=webhook_id,
            business_id=business_id
        ).first()
        
        if not webhook:
            return jsonify({"error": "Webhook not found"}), 404
        
        # Update fields if provided
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({"error": "name cannot be empty"}), 400
            webhook.name = name
        
        if 'status_id' in data:
            status_id = data['status_id']
            # Validate status exists and belongs to this business
            status = LeadStatus.query.filter_by(
                id=status_id,
                business_id=business_id
            ).first()
            
            if not status:
                return jsonify({"error": "Invalid status_id or status does not belong to this business"}), 400
            
            webhook.status_id = status_id
        
        if 'is_active' in data:
            webhook.is_active = bool(data['is_active'])
        
        if data.get('regenerate_secret'):
            webhook.secret = generate_webhook_secret()
        
        webhook.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ Updated webhook {webhook_id} for business {business_id}")
        
        return jsonify({
            "id": webhook.id,
            "name": webhook.name,
            "secret": webhook.secret,
            "status_id": webhook.status_id,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
            "updated_at": webhook.updated_at.isoformat() if webhook.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error updating webhook: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


@webhook_leads_bp.route('/leads/webhooks/<int:webhook_id>', methods=['DELETE'])
@require_api_auth
def delete_webhook(webhook_id):
    """
    Delete a webhook configuration
    
    DELETE /api/leads/webhooks/{id}
    
    Returns: {"success": true}
    """
    try:
        business_id = g.business_id
        
        # Find webhook
        webhook = WebhookLeadIngest.query.filter_by(
            id=webhook_id,
            business_id=business_id
        ).first()
        
        if not webhook:
            return jsonify({"error": "Webhook not found"}), 404
        
        db.session.delete(webhook)
        db.session.commit()
        
        logger.info(f"✅ Deleted webhook {webhook_id} for business {business_id}")
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting webhook: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC WEBHOOK INGESTION ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

def extract_lead_fields(payload):
    """
    Extract lead fields from webhook payload using best-effort approach
    
    Looks for common field patterns:
    - name, full_name, first_name + last_name, firstName + lastName
    - phone, mobile, tel, telephone, phone_number
    - email, email_address
    - message, notes, description, comment
    - city, location
    - source
    
    Returns: dict with extracted fields
    """
    if not isinstance(payload, dict):
        return {}
    
    result = {}
    
    # Flatten nested objects (one level deep only)
    flat_payload = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            # Flatten nested dict
            for nested_key, nested_value in value.items():
                flat_payload[f"{key}_{nested_key}".lower()] = nested_value
        flat_payload[key.lower()] = value
    
    # Extract name (try multiple patterns)
    name_fields = ['name', 'full_name', 'fullname', 'customer_name', 'contact_name']
    for field in name_fields:
        if field in flat_payload and flat_payload[field]:
            result['name'] = str(flat_payload[field]).strip()
            break
    
    # Try first_name + last_name
    if 'name' not in result:
        first_name = flat_payload.get('first_name') or flat_payload.get('firstname')
        last_name = flat_payload.get('last_name') or flat_payload.get('lastname')
        
        if first_name and last_name:
            result['name'] = f"{first_name} {last_name}".strip()
        elif first_name:
            result['name'] = str(first_name).strip()
        elif last_name:
            result['name'] = str(last_name).strip()
    
    # Extract phone (try multiple patterns)
    phone_fields = ['phone', 'mobile', 'tel', 'telephone', 'phone_number', 'phonenumber', 'cell', 'cellphone']
    for field in phone_fields:
        if field in flat_payload and flat_payload[field]:
            result['phone'] = str(flat_payload[field]).strip()
            break
    
    # Extract email
    email_fields = ['email', 'email_address', 'emailaddress', 'mail']
    for field in email_fields:
        if field in flat_payload and flat_payload[field]:
            result['email'] = str(flat_payload[field]).strip().lower()
            break
    
    # Extract message/notes
    message_fields = ['message', 'notes', 'description', 'comment', 'details', 'text', 'body']
    for field in message_fields:
        if field in flat_payload and flat_payload[field]:
            result['notes'] = str(flat_payload[field]).strip()
            break
    
    # Extract city
    city_fields = ['city', 'location', 'address']
    for field in city_fields:
        if field in flat_payload and flat_payload[field]:
            result['city'] = str(flat_payload[field]).strip()
            break
    
    # Extract source (if not provided, will be set to webhook source)
    source_fields = ['source', 'lead_source', 'origin']
    for field in source_fields:
        if field in flat_payload and flat_payload[field]:
            result['source'] = str(flat_payload[field]).strip()
            break
    
    return result


@webhook_leads_bp.route('/webhooks/leads/<int:webhook_id>', methods=['POST'])
def webhook_ingest_lead(webhook_id):
    """
    Public webhook endpoint for lead ingestion
    
    POST /api/webhooks/leads/{webhook_id}
    Headers:
        X-Webhook-Secret: wh_...
        Content-Type: application/json
    Body: Any JSON payload (best-effort field extraction)
    
    Returns: {
        "success": true,
        "lead_id": 123,
        "updated": false  # true if existing lead was updated
    }
    
    Errors:
    - 401: Invalid or missing secret
    - 400: No contact identifier (phone or email)
    - 404: Webhook not found or inactive
    - 500: Server error
    """
    try:
        # Find webhook
        webhook = WebhookLeadIngest.query.filter_by(id=webhook_id).first()
        
        if not webhook:
            logger.warning(f"⚠️ Webhook {webhook_id} not found")
            return jsonify({"error": "Webhook not found"}), 404
        
        # Check if webhook is active
        if not webhook.is_active:
            logger.warning(f"⚠️ Webhook {webhook_id} is inactive")
            return jsonify({"error": "Webhook is inactive"}), 404
        
        # Validate secret
        secret_header = request.headers.get('X-Webhook-Secret')
        if not secret_header or secret_header != webhook.secret:
            logger.warning(f"⚠️ Invalid secret for webhook {webhook_id}")
            return jsonify({"error": "Invalid or missing X-Webhook-Secret header"}), 401
        
        # Get payload
        payload = request.get_json(silent=True)
        
        if not isinstance(payload, dict):
            logger.warning(f"⚠️ Webhook {webhook_id}: Invalid JSON payload, expected dict")
            return jsonify({
                "error": "Invalid JSON payload",
                "details": "Expected application/json body with valid JSON object"
            }), 400
        
        # Extract lead fields
        fields = extract_lead_fields(payload)
        
        # Validate: must have phone or email
        phone = fields.get('phone')
        email = fields.get('email')
        
        if not phone and not email:
            logger.warning(f"⚠️ Webhook {webhook_id}: No contact identifier in payload")
            return jsonify({
                "error": "no contact identifier",
                "message": "Must provide either phone or email"
            }), 400
        
        # Normalize phone (remove spaces, dashes, etc.)
        if phone:
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            # Add + if missing and looks like international
            if phone and phone[0] != '+' and len(phone) >= 10:
                phone = f"+{phone}"
        
        # Check for duplicate lead by phone (priority) or email
        existing_lead = None
        updated = False
        
        if phone:
            existing_lead = Lead.query.filter_by(
                tenant_id=webhook.business_id,
                phone_e164=phone
            ).first()
        
        if not existing_lead and email:
            existing_lead = Lead.query.filter_by(
                tenant_id=webhook.business_id,
                email=email
            ).first()
        
        if existing_lead:
            # Update existing lead with new information
            updated = True
            
            # Update fields if they're currently empty
            if fields.get('name') and not existing_lead.name:
                existing_lead.name = fields['name']
            
            if email and not existing_lead.email:
                existing_lead.email = email
            
            if phone and not existing_lead.phone_e164:
                existing_lead.phone_e164 = phone
            
            if fields.get('city') and not existing_lead.city:
                existing_lead.city = fields['city']
            
            # Append notes if provided
            if fields.get('notes'):
                note_text = f"Lead updated from webhook '{webhook.name}': {fields['notes']}"
                if existing_lead.notes:
                    existing_lead.notes = f"{existing_lead.notes}\n\n{note_text}"
                else:
                    existing_lead.notes = note_text
            else:
                note_text = f"Lead updated from webhook '{webhook.name}'"
                if existing_lead.notes:
                    existing_lead.notes = f"{existing_lead.notes}\n\n{note_text}"
                else:
                    existing_lead.notes = note_text
            
            # Update raw_payload (merge or replace)
            existing_lead.raw_payload = payload
            existing_lead.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f"✅ Updated existing lead {existing_lead.id} from webhook {webhook_id}")
            
            return jsonify({
                "success": True,
                "lead_id": existing_lead.id,
                "updated": True
            }), 200
        
        else:
            # Create new lead
            lead = Lead(
                tenant_id=webhook.business_id,
                name=fields.get('name', 'ללא שם'),
                phone_e164=phone,
                email=email,
                city=fields.get('city'),
                notes=fields.get('notes'),
                source=fields.get('source', f"webhook_{webhook_id}"),
                status=webhook.status.name if webhook.status else 'new',  # Use status name for Lead model
                raw_payload=payload,
                created_at=datetime.utcnow()
            )
            
            db.session.add(lead)
            db.session.commit()
            
            logger.info(f"✅ Created new lead {lead.id} from webhook {webhook_id} in status '{lead.status}'")
            
            return jsonify({
                "success": True,
                "lead_id": lead.id,
                "updated": False
            }), 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook {webhook_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500
