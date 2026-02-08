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
import re
from flask import Blueprint, jsonify, request, g
from server.models_sql import WebhookLeadIngest, Lead, LeadStatus, Business
from server.db import db
from server.auth_api import require_api_auth
from server.extensions import csrf
from datetime import datetime
from sqlalchemy import func

logger = logging.getLogger(__name__)

webhook_leads_bp = Blueprint('webhook_leads', __name__, url_prefix='/api')


def json_response(data, status_code=200):
    """
    Create a JSON response with proper UTF-8 charset for Hebrew support
    
    Args:
        data: Dictionary to be serialized as JSON
        status_code: HTTP status code (default: 200)
    
    Returns:
        Flask Response object with Content-Type: application/json; charset=utf-8
    """
    response = jsonify(data)
    response.status_code = status_code
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def generate_webhook_secret():
    """Generate a secure random secret for webhook authentication"""
    return f"wh_{secrets.token_urlsafe(32)}"


def validate_json_body(request, allow_none=False):
    """
    Validate that request body contains valid JSON object (dict)
    
    Args:
        request: Flask request object
        allow_none: If True, returns None for missing body; if False, returns error tuple
    
    Returns:
        Tuple of (data, error_response) where error_response is None if successful
        If error_response is not None, it's a tuple of (jsonify_response, status_code)
    """
    data = request.get_json(silent=True)
    
    if data is None:
        if allow_none:
            return None, None
        return None, (jsonify({
            "error": "Invalid or missing JSON body",
            "details": "Request body must be valid JSON with Content-Type: application/json"
        }), 400)
    
    if not isinstance(data, dict):
        return None, (jsonify({
            "error": "Invalid JSON payload",
            "details": f"Expected JSON object, received: {type(data).__name__}"
        }), 400)
    
    return data, None


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
        # Parse and validate JSON body
        data, error_response = validate_json_body(request)
        if error_response:
            return error_response
        
        business_id = g.business_id
        
        # Validate required fields
        name = data.get('name', '').strip()
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
        # Parse and validate JSON body
        data, error_response = validate_json_body(request)
        if error_response:
            return error_response
        
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

def normalize_phone_number(phone):
    """
    Normalize phone number to E.164 format
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Normalized phone number (e.g., +972501234567) or None if invalid
    """
    if not phone:
        return None
    
    # Convert to string and strip whitespace
    phone = str(phone).strip()
    
    # Remove common separators (spaces, dashes, parentheses)
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # If empty after cleanup, return None
    if not phone:
        return None
    
    # If already has +, keep it
    if phone.startswith('+'):
        return phone
    
    # Israeli number starting with 0 (e.g., 0501234567)
    if phone.startswith('0') and len(phone) >= 9:
        return f"+972{phone[1:]}"
    
    # Already in international format without + (e.g., 972501234567)
    if phone.startswith('972') and len(phone) >= 12:
        return f"+{phone}"
    
    # Other international formats - add + if numeric
    if phone.isdigit() and len(phone) >= 10:
        return f"+{phone}"
    
    # Return as-is if we can't determine format
    return phone


def extract_lead_fields(payload):
    """
    Extract lead fields from webhook payload with support for flat and nested structures.
    
    Supported payload formats:
    1. Flat: {"name": "...", "phone": "...", "email": "...", "source": "..."}
    2. Nested: {"contact": {"name": "...", "phone": "...", "email": "..."}, "source": "..."}
    
    This is the SSOT (Single Source of Truth) for webhook field extraction.
    
    Returns: dict with normalized fields: name, phone, email, city, notes, source
    """
    if not isinstance(payload, dict):
        return {}
    
    result = {}
    
    # Build a unified flat view that supports both formats
    # Priority: direct fields > nested contact fields
    flat_payload = {}
    
    # First, add all direct (non-dict) values
    for key, value in payload.items():
        if not isinstance(value, dict):
            flat_payload[key.lower()] = value
    
    # Then, check for nested "contact" object and extract its fields
    # This handles the nested format: {"contact": {"name": "...", "phone": "..."}}
    if 'contact' in payload and isinstance(payload['contact'], dict):
        contact_data = payload['contact']
        for key, value in contact_data.items():
            # Add contact fields but don't override existing direct fields
            field_key = key.lower()
            if field_key not in flat_payload and not isinstance(value, dict):
                flat_payload[field_key] = value
    
    # Also flatten any other nested dicts with prefix (for compatibility)
    for key, value in payload.items():
        if isinstance(value, dict) and key.lower() != 'contact':
            for nested_key, nested_value in value.items():
                prefixed_key = f"{key}_{nested_key}".lower()
                if prefixed_key not in flat_payload and not isinstance(nested_value, dict):
                    flat_payload[prefixed_key] = nested_value
    
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
    
    # Extract phone (try multiple patterns with aliases)
    # Support various field names including camelCase and WhatsApp
    phone_fields = ['phone', 'phone_number', 'mobile', 'tel', 'whatsapp', 'phoneNumber', 'telephone', 'phonenumber', 'cell', 'cellphone']
    for field in phone_fields:
        if field in flat_payload and flat_payload[field]:
            phone_value = str(flat_payload[field]).strip()
            # Only use non-empty phone values
            if phone_value:
                result['phone'] = phone_value
                break
    
    # Extract email
    email_fields = ['email', 'email_address', 'emailaddress', 'mail']
    for field in email_fields:
        if field in flat_payload and flat_payload[field]:
            email_value = str(flat_payload[field]).strip().lower()
            # Only use non-empty email values
            if email_value:
                result['email'] = email_value
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
    # Support UTM and other source field names
    source_fields = ['source', 'utm_source', 'lead_source', 'origin']
    for field in source_fields:
        if field in flat_payload and flat_payload[field]:
            result['source'] = str(flat_payload[field]).strip()
            break
    
    return result


@webhook_leads_bp.route('/webhook/leads/<int:webhook_id>', methods=['POST', 'OPTIONS'])
@csrf.exempt  # Public webhook endpoint - authentication via X-Webhook-Secret header
def webhook_ingest_lead(webhook_id):
    """
    Public webhook endpoint for lead ingestion
    
    POST /api/webhook/leads/{webhook_id}
    Headers:
        X-Webhook-Secret: wh_...
        Content-Type: application/json; charset=utf-8
    Body: Any JSON payload (best-effort field extraction)
    
    Returns: {
        "ok": true,
        "lead_id": 123,
        "status_id": 9  # ID of the status assigned to the lead
    }
    
    Errors:
    - 401: Invalid or missing secret
    - 400: No contact identifier (phone or email) - returns {"ok": false, "error": "phone_or_email_required"}
    - 404: Webhook not found or inactive
    - 500: Server error
    """
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        response = json_response({"ok": True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Webhook-Secret'
        return response
    
    try:
        # Find webhook
        webhook = WebhookLeadIngest.query.filter_by(id=webhook_id).first()
        
        if not webhook:
            logger.warning(f"⚠️ Webhook {webhook_id} not found")
            return json_response({"ok": False, "error": "webhook_not_found"}, 404)
        
        # Check if webhook is active
        if not webhook.is_active:
            logger.warning(f"⚠️ Webhook {webhook_id} is inactive")
            return json_response({"ok": False, "error": "webhook_inactive"}, 404)
        
        # Validate secret
        secret_header = request.headers.get('X-Webhook-Secret')
        if not secret_header or secret_header != webhook.secret:
            logger.warning(f"⚠️ Invalid secret for webhook {webhook_id}")
            return json_response({"ok": False, "error": "invalid_secret"}, 401)
        
        # Get and validate payload
        payload, error_response = validate_json_body(request)
        if error_response:
            logger.warning(f"⚠️ Webhook {webhook_id}: Invalid JSON payload")
            return json_response({"ok": False, "error": "invalid_json"}, 400)
        
        # Extract lead fields
        fields = extract_lead_fields(payload)
        
        # 🔍 IMPROVED LOGGING: Show what we got from extraction
        logger.info(f"🔍 [WEBHOOK {webhook_id}] Raw payload keys: {list(payload.keys())}")
        logger.info(f"🔍 [WEBHOOK {webhook_id}] Raw payload values (first 50 chars): {dict((k, str(v)[:50]) for k, v in payload.items())}")
        logger.info(f"🔍 [WEBHOOK {webhook_id}] Extracted fields keys: {list(fields.keys())}")
        logger.info(f"🔍 [WEBHOOK {webhook_id}] Extracted values: name={fields.get('name')}, phone={fields.get('phone')}, email={fields.get('email')}, source={fields.get('source')}")
        logger.info(f"🔍 [WEBHOOK {webhook_id}] Has name={bool(fields.get('name'))}, phone={bool(fields.get('phone'))}, email={bool(fields.get('email'))}, source={bool(fields.get('source'))}")
        
        # Get raw values
        phone_raw = fields.get('phone')
        raw_email = fields.get('email')
        
        # Extract phone digits (only digits, no formatting)
        # This handles Google Sheets numbers without leading zero (e.g., 549750505 instead of 0549750505)
        phone_digits = None
        if phone_raw:
            phone_digits = re.sub(r'\D', '', str(phone_raw))
            logger.info(f"🔍 [WEBHOOK {webhook_id}] Phone extraction: raw='{phone_raw}' → digits='{phone_digits}'")
        
        # Validate: must have phone_digits or email (SSOT - this is the only requirement)
        # Don't block on phone format - as long as we have digits or email, we can create the lead
        if not phone_digits and not raw_email:
            logger.warning(f"⚠️ [WEBHOOK {webhook_id}] Missing phone/email - payload keys: {list(payload.keys())}, extracted: {list(fields.keys())}")
            return json_response({
                "ok": False,
                "error": "phone_or_email_required",
                "message": "Missing phone or email - חסר טלפון או אימייל"
            }, 400)
        
        # Normalize phone for E.164 format (best effort, but don't fail if can't normalize)
        phone = normalize_phone_number(phone_raw) if phone_raw else None
        email = raw_email  # Email is already lowercased in extraction
        
        # Log normalization result
        if phone_raw:
            logger.info(f"🔍 [WEBHOOK {webhook_id}] Phone normalized: raw='{phone_raw}', digits='{phone_digits}', e164='{phone}'")
        
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
            
            # Get status_id for response (look up current lead status)
            status_obj = LeadStatus.query.filter_by(
                business_id=webhook.business_id,
                name=existing_lead.status
            ).first()
            status_id = status_obj.id if status_obj else None
            
            # Log success with details
            identifier_type = "phone" if phone else "email"
            identifier_value = phone if phone else email
            logger.info(f"✅ [WEBHOOK {webhook_id}] Updated lead {existing_lead.id} via {identifier_type}={identifier_value}, status_id={status_id}")
            
            return json_response({
                "ok": True,
                "lead_id": existing_lead.id,
                "created": False,
                "status_id": status_id
            }, 200)
        
        else:
            # Determine target status for new lead
            target_status_name = None
            target_status_id = None
            
            # Try to use webhook's configured target status
            logger.info(f"🔍 [WEBHOOK {webhook_id}] Determining target status: webhook.status_id={webhook.status_id}")
            if webhook.status_id:
                target_status = LeadStatus.query.filter_by(
                    id=webhook.status_id,
                    business_id=webhook.business_id,
                    is_active=True
                ).first()
                
                if target_status:
                    target_status_name = target_status.name
                    target_status_id = target_status.id
                    logger.info(f"✅ [WEBHOOK {webhook_id}] Using webhook target status: '{target_status_name}' (id={target_status_id})")
                else:
                    logger.warning(f"⚠️ Webhook {webhook_id}: Target status_id {webhook.status_id} not found or inactive, using fallback")
            
            # Fallback to business default status
            if not target_status_name:
                default_status = LeadStatus.query.filter_by(
                    business_id=webhook.business_id,
                    is_active=True,
                    is_default=True
                ).first()
                
                if default_status:
                    target_status_name = default_status.name
                    target_status_id = default_status.id
                    logger.info(f"ℹ️ [WEBHOOK {webhook_id}]: Using business default status '{target_status_name}' (id={target_status_id})")
                else:
                    # Final fallback to 'new' if no default exists
                    target_status_name = 'new'
                    # Try to get the 'new' status ID
                    new_status = LeadStatus.query.filter_by(
                        business_id=webhook.business_id,
                        name='new',
                        is_active=True
                    ).first()
                    target_status_id = new_status.id if new_status else None
                    logger.warning(f"⚠️ [WEBHOOK {webhook_id}]: No default status found, using hardcoded fallback 'new' (id={target_status_id})")
            
            # Create new lead
            lead = Lead(
                tenant_id=webhook.business_id,
                name=fields.get('name', 'ללא שם'),
                phone_e164=phone,
                email=email,
                city=fields.get('city'),
                notes=fields.get('notes'),
                source=f'webhook_{webhook_id}',  # Always use webhook source for traceability
                status=target_status_name,
                raw_payload=payload,
                created_at=datetime.utcnow()
            )
            
            db.session.add(lead)
            db.session.commit()
            
            # Log success with all details
            identifier_type = "phone" if phone else "email"
            identifier_value = phone if phone else email
            logger.info(f"✅ [WEBHOOK {webhook_id}] Created lead {lead.id} via {identifier_type}={identifier_value}, status='{target_status_name}' (id={target_status_id})")
            logger.info(f"   📋 Extracted fields: name='{fields.get('name', 'ללא שם')}', phone_raw='{phone_raw or 'N/A'}', phone_digits='{phone_digits or 'N/A'}', phone_e164='{phone or 'N/A'}', email='{email or 'N/A'}', source='{fields.get('source', 'N/A')}'")
            logger.info(f"   🎯 Status assigned: '{target_status_name}' (id={target_status_id})")
            
            return json_response({
                "ok": True,
                "lead_id": lead.id,
                "created": True,
                "status_id": target_status_id
            }, 201)
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook {webhook_id}: {e}", exc_info=True)
        db.session.rollback()
        return json_response({"ok": False, "error": "internal_server_error", "details": str(e)}, 500)
