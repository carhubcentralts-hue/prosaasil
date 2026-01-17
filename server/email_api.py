"""
Email API Blueprint - CRM Email System
Production-grade email management with per-business configuration

✅ Features:
   - Email settings management (per-business)
   - Send emails from leads
   - Email history and logs
   - Test email functionality
   - Complete multi-tenant isolation
   - Rate limiting (30 emails/hour per user, 500/day per business)
"""
from flask import Blueprint, jsonify, request, g
from server.auth_api import require_api_auth
from server.services.email_service import get_email_service
from server.models_sql import Lead, User
from server.db import db
from sqlalchemy import text as sa_text, desc
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

email_bp = Blueprint("email_bp", __name__)

# Rate limiting storage (in-memory - for production use Redis)
_rate_limit_user = {}  # {user_id: [(timestamp, count)]}
_rate_limit_business = {}  # {business_id: [(timestamp, count)]}

# Rate limit configuration
RATE_LIMIT_USER_HOURLY = 30  # emails per user per hour
RATE_LIMIT_BUSINESS_DAILY = 500  # emails per business per day

# Email validation constants
MIN_HTML_LENGTH = 50  # Minimum HTML length to consider valid (chars)

def get_current_business_id():
    """Get current business ID from authenticated user (populated by @require_api_auth)"""
    if hasattr(g, 'tenant') and g.tenant:
        return g.tenant
    
    # Fallback to user.business_id if available
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('business_id')
    
    return None

def check_admin_permission():
    """Check if current user has admin/owner permission"""
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        role = g.user.get('role')
        return role in ['system_admin', 'owner', 'admin']
    return False

def check_rate_limit(user_id: int, business_id: int) -> tuple[bool, str]:
    """
    Check rate limits for email sending
    
    Args:
        user_id: User ID
        business_id: Business ID
        
    Returns:
        (bool, str): (allowed, error_message)
    """
    now = datetime.utcnow()
    
    # Check user hourly limit
    if user_id:
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        if user_id in _rate_limit_user:
            _rate_limit_user[user_id] = [
                ts for ts in _rate_limit_user[user_id] if ts > hour_ago
            ]
        else:
            _rate_limit_user[user_id] = []
        
        # Check limit
        if len(_rate_limit_user[user_id]) >= RATE_LIMIT_USER_HOURLY:
            return False, f"Rate limit exceeded: {RATE_LIMIT_USER_HOURLY} emails per hour per user"
        
        # Add current timestamp
        _rate_limit_user[user_id].append(now)
    
    # Check business daily limit
    if business_id:
        day_ago = now - timedelta(days=1)
        
        # Clean old entries
        if business_id in _rate_limit_business:
            _rate_limit_business[business_id] = [
                ts for ts in _rate_limit_business[business_id] if ts > day_ago
            ]
        else:
            _rate_limit_business[business_id] = []
        
        # Check limit
        if len(_rate_limit_business[business_id]) >= RATE_LIMIT_BUSINESS_DAILY:
            return False, f"Rate limit exceeded: {RATE_LIMIT_BUSINESS_DAILY} emails per day per business"
        
        # Add current timestamp
        _rate_limit_business[business_id].append(now)
    
    return True, ""

# ========================================================================
# Email Settings Endpoints
# ========================================================================

@email_bp.route('/api/email/settings', methods=['GET'])
@require_api_auth
def get_email_settings():
    """
    Get email settings for current business
    
    Returns:
        200: Email settings object or null if not configured
        403: No permission
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        email_service = get_email_service()
        settings = email_service.get_email_settings(business_id)
        
        if not settings:
            return jsonify({
                'configured': False,
                'settings': None,
                'sendgrid_available': email_service.client is not None
            }), 200
        
        return jsonify({
            'configured': True,
            'settings': {
                'id': settings['id'],
                'from_email': settings['from_email'],
                'from_name': settings['from_name'],
                'reply_to': settings['reply_to'],
                'is_enabled': settings['is_enabled'],
                'provider': settings['provider'],
                'theme_id': settings.get('theme_id', 'classic_blue'),
                'cta_default_text': settings.get('cta_default_text'),
                'cta_default_url': settings.get('cta_default_url'),
                'footer_text': settings.get('footer_text'),
                'footer_html': settings.get('footer_html'),
                'default_greeting': settings.get('default_greeting'),
                'brand_primary_color': settings.get('brand_primary_color'),
                'brand_logo_url': settings.get('brand_logo_url'),
                'created_at': settings['created_at'].isoformat() if settings['created_at'] else None,
                'updated_at': settings['updated_at'].isoformat() if settings['updated_at'] else None
            },
            'sendgrid_available': email_service.client is not None
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to get email settings: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/settings', methods=['POST'])
@require_api_auth
def save_email_settings():
    """
    Save/update email settings for current business
    Admin/Owner only
    
    🔒 CRITICAL: from_email is ENFORCED to noreply@prosaas.pro
    Business can customize branding, greeting, footer, theme, and reply_to
    
    Request body:
        {
            "from_name": "My Business",
            "reply_to": "contact@mybusiness.com",
            "reply_to_enabled": true,
            "brand_logo_url": "https://...",  // optional
            "brand_primary_color": "#2563EB",  // optional
            "default_greeting": "שלום {{lead.first_name}},",  // optional
            "footer_html": "<p>Contact us...</p>",  // optional
            "footer_text": "Contact us...",  // optional
            "theme_id": "classic_blue",  // optional
            "cta_default_text": "Click here",  // optional
            "cta_default_url": "https://...",  // optional
            "is_enabled": true
        }
    
    Returns:
        200: Settings saved successfully
        400: Invalid data
        403: No permission
    """
    try:
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('from_name'):
            return jsonify({'error': 'from_name is required'}), 400
        
        from_name = data['from_name'].strip()
        reply_to = data.get('reply_to', '').strip() or None
        reply_to_enabled = data.get('reply_to_enabled', True)
        brand_logo_url = data.get('brand_logo_url', '').strip() or None
        brand_primary_color = data.get('brand_primary_color', '').strip() or None
        default_greeting = data.get('default_greeting', '').strip() or None
        footer_html = data.get('footer_html', '').strip() or None
        footer_text = data.get('footer_text', '').strip() or None
        is_enabled = data.get('is_enabled', True)
        theme_id = data.get('theme_id', '').strip() or None
        cta_default_text = data.get('cta_default_text', '').strip() or None
        cta_default_url = data.get('cta_default_url', '').strip() or None
        
        # Save settings (from_email is enforced internally)
        email_service = get_email_service()
        success = email_service.upsert_email_settings(
            business_id=business_id,
            from_name=from_name,
            reply_to=reply_to,
            reply_to_enabled=reply_to_enabled,
            brand_logo_url=brand_logo_url,
            brand_primary_color=brand_primary_color,
            default_greeting=default_greeting,
            footer_html=footer_html,
            footer_text=footer_text,
            is_enabled=is_enabled,
            theme_id=theme_id,
            cta_default_text=cta_default_text,
            cta_default_url=cta_default_url
        )
        
        if not success:
            return jsonify({'error': 'Failed to save settings'}), 500
        
        return jsonify({
            'success': True,
            'message': 'Email settings saved successfully',
            'note': 'Emails will be sent from noreply@prosaas.pro with your business name'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to save email settings: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/settings/test', methods=['POST'])
@require_api_auth
def send_test_email():
    """
    Send a test email using current business settings
    Admin/Owner only
    
    Request body:
        {
            "to_email": "test@example.com"
        }
    
    Returns:
        200: Test email sent
        400: Invalid data or settings not configured
        403: No permission
    """
    try:
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        data = request.get_json()
        to_email = data.get('to_email', '').strip()
        
        if not to_email:
            return jsonify({'error': 'to_email is required'}), 400
        
        # Send test email
        email_service = get_email_service()
        result = email_service.send_test_email(business_id, to_email)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Test email sent successfully',
                'email_id': result['email_id']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error'],
                'message': result['message']
            }), 400
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to send test email: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================================================
# Email Sending Endpoints
# ========================================================================

@email_bp.route('/api/leads/<int:lead_id>/email', methods=['POST'])
@require_api_auth
def send_email_to_lead(lead_id):
    """
    Send email to a lead
    
    🔒 Rate limited: 30 emails/hour per user, 500/day per business
    
    Request body:
        {
            "to_email": "optional@override.com",  # Optional, defaults to lead email
            "subject": "Email subject",
            "html": "<p>Email body</p>",  # Primary field for HTML content
            "body_html": "<p>Email body</p>",  # Alternative field name (for compatibility)
            "text": "Plain text version",  # Optional
            "body_text": "Plain text version"  # Alternative field name (for compatibility)
        }
    
    Returns:
        200: Email sent successfully
        400: Invalid data or email not configured
        403: No permission or lead not found
        404: Lead not found
        429: Rate limit exceeded
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        # Get current user ID
        user_id = None
        if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
            user_id = g.user.get('id')
        
        # Check rate limits
        allowed, error_msg = check_rate_limit(user_id, business_id)
        if not allowed:
            logger.warning(f"[EMAIL_API] Rate limit exceeded: user_id={user_id}, business_id={business_id}")
            return jsonify({'error': error_msg}), 429
        
        # Get lead and verify it belongs to this business
        lead = db.session.query(Lead).filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        data = request.get_json()
        
        # Get to_email (use lead's email if not specified)
        to_email = data.get('to_email', '').strip()
        if not to_email:
            to_email = lead.email
        
        if not to_email:
            return jsonify({'error': 'No email address available for this lead'}), 400
        
        subject = data.get('subject', '').strip()
        
        # 🔥 FIX: Support both 'html' and 'body_html' field names for compatibility
        html = data.get('html', '').strip() or data.get('body_html', '').strip()
        
        # 🔥 FIX: Support both 'text' and 'body_text' field names for compatibility
        plain_text = data.get('text', '').strip() or data.get('body_text', '').strip() or None
        
        # 🔥 DEBUG LOGGING: Log what we received before validation
        logger.info(f"[EMAIL_TO_LEAD] lead_id={lead_id} subject_len={len(subject)} html_len={len(html)} text_len={len(plain_text) if plain_text else 0}")
        logger.debug(f"[EMAIL_TO_LEAD] Payload keys: {list(data.keys())}")
        
        # 🔥 FIX 4: Validate required fields
        if not subject or not html:
            logger.warning(f"[EMAIL_TO_LEAD] Missing required fields: subject={bool(subject)} html={bool(html)}")
            return jsonify({'error': 'subject and html (or body_html) are required'}), 400
        
        # 🔥 FIX 4: Validate HTML length (atomic check before send)
        if len(html) < MIN_HTML_LENGTH:
            logger.error(f"[EMAIL_TO_LEAD] HTML too short ({len(html)} chars) - likely render failed")
            return jsonify({
                'error': 'Invalid HTML content',
                'message': f'HTML content too short ({len(html)} chars). Please ensure render was successful.'
            }), 400
        
        # 🔥 DEBUG LOGGING: Log final values before sending
        logger.info(f"[EMAIL_TO_LEAD] Validated - subject='{subject[:50]}...' html_bytes={len(html.encode('utf-8'))} text_bytes={len(plain_text.encode('utf-8')) if plain_text else 0}")
        
        # Send email
        email_service = get_email_service()
        result = email_service.send_crm_email(
            business_id=business_id,
            to_email=to_email,
            subject=subject,
            html=html,
            plain_text=plain_text,
            lead_id=lead_id,
            created_by_user_id=user_id,
            meta={'source': 'lead_page'}
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Email sent successfully',
                'email_id': result['email_id']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error'],
                'message': result['message']
            }), 400
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to send email to lead {lead_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/leads/<int:lead_id>/emails', methods=['GET'])
@require_api_auth
def get_lead_emails(lead_id):
    """
    Get email history for a lead
    
    Returns:
        200: List of emails
        403: No permission
        404: Lead not found
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        # Verify lead belongs to this business
        lead = db.session.query(Lead).filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Get emails for this lead
        result = db.session.execute(
            sa_text("""
                SELECT 
                    em.id, em.to_email, em.subject, em.status, em.error,
                    em.from_email, em.from_name, em.reply_to,
                    em.sent_at, em.created_at,
                    u.name as created_by_name, u.email as created_by_email
                FROM email_messages em
                LEFT JOIN users u ON em.created_by_user_id = u.id
                WHERE em.business_id = :business_id AND em.lead_id = :lead_id
                ORDER BY em.created_at DESC
            """),
            {"business_id": business_id, "lead_id": lead_id}
        ).fetchall()
        
        emails = []
        for row in result:
            emails.append({
                'id': row[0],
                'to_email': row[1],
                'subject': row[2],
                'status': row[3],
                'error': row[4],
                'from_email': row[5],
                'from_name': row[6],
                'reply_to': row[7],
                'sent_at': row[8].isoformat() if row[8] else None,
                'created_at': row[9].isoformat() if row[9] else None,
                'created_by': {
                    'name': row[10],
                    'email': row[11]
                } if row[10] or row[11] else None
            })
        
        return jsonify({
            'emails': emails,
            'count': len(emails)
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to get emails for lead {lead_id}: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================================================
# Email Messages List Endpoint
# ========================================================================

@email_bp.route('/api/email/messages', methods=['GET'])
@require_api_auth
def list_email_messages():
    """
    List email messages for current business with filters
    
    Query params:
        status: Filter by status (queued, sent, failed, etc.)
        q: Search in subject and to_email
        page: Page number (default 1)
        per_page: Results per page (default 50, max 100)
    
    Returns:
        200: List of email messages with pagination
        403: No permission
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        # Get query parameters
        status_filter = request.args.get('status', '').strip()
        search_query = request.args.get('q', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
        
        # Build query
        where_clauses = ["em.business_id = :business_id"]
        params = {"business_id": business_id}
        
        if status_filter:
            where_clauses.append("em.status = :status")
            params['status'] = status_filter
        
        if search_query:
            where_clauses.append("(em.subject ILIKE :search OR em.to_email ILIKE :search)")
            params['search'] = f"%{search_query}%"
        
        where_clause = " AND ".join(where_clauses)
        
        # Get total count
        count_result = db.session.execute(
            sa_text(f"SELECT COUNT(*) FROM email_messages em WHERE {where_clause}"),
            params
        ).scalar()
        
        # Get paginated results
        offset = (page - 1) * per_page
        
        result = db.session.execute(
            sa_text(f"""
                SELECT 
                    em.id, em.to_email, em.subject, em.status, em.error,
                    em.from_email, em.from_name, em.reply_to,
                    em.sent_at, em.created_at,
                    em.lead_id,
                    l.first_name, l.last_name,
                    u.name as created_by_name, u.email as created_by_email
                FROM email_messages em
                LEFT JOIN leads l ON em.lead_id = l.id
                LEFT JOIN users u ON em.created_by_user_id = u.id
                WHERE {where_clause}
                ORDER BY em.created_at DESC
                LIMIT :per_page OFFSET :offset
            """),
            {**params, 'per_page': per_page, 'offset': offset}
        ).fetchall()
        
        emails = []
        for row in result:
            emails.append({
                'id': row[0],
                'to_email': row[1],
                'subject': row[2],
                'status': row[3],
                'error': row[4],
                'from_email': row[5],
                'from_name': row[6],
                'reply_to': row[7],
                'sent_at': row[8].isoformat() if row[8] else None,
                'created_at': row[9].isoformat() if row[9] else None,
                'lead_id': row[10],
                'lead_name': f"{row[11] or ''} {row[12] or ''}".strip() if row[11] or row[12] else None,
                'created_by': {
                    'name': row[13],
                    'email': row[14]
                } if row[13] or row[14] else None
            })
        
        total_pages = (count_result + per_page - 1) // per_page
        
        return jsonify({
            'emails': emails,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': count_result,
                'total_pages': total_pages
            }
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to list email messages: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================================================
# Template Management Endpoints
# ========================================================================

@email_bp.route('/api/email/templates', methods=['GET'])
@require_api_auth
def list_templates():
    """
    List email templates for current business
    
    Query params:
        active_only: Only return active templates (default true)
    
    Returns:
        200: List of templates
        403: No permission
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        email_service = get_email_service()
        templates = email_service.list_templates(business_id, active_only=active_only)
        
        return jsonify({
            'templates': templates,
            'count': len(templates)
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to list templates: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/templates', methods=['POST'])
@require_api_auth
def create_template():
    """
    Create a new email template
    Admin/Owner only
    
    Request body:
        {
            "name": "Template name",
            "type": "generic|lead_outreach|followup",
            "subject_template": "Subject with {{variables}}",
            "html_template": "<p>HTML body with {{variables}}</p>",
            "text_template": "Plain text version"  // optional
        }
    
    Returns:
        201: Template created
        400: Invalid data
        403: No permission
    """
    try:
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('subject_template') or not data.get('html_template'):
            return jsonify({'error': 'name, subject_template, and html_template are required'}), 400
        
        # Get current user ID
        user_id = None
        if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
            user_id = g.user.get('id')
        
        # Create template
        email_service = get_email_service()
        template_id = email_service.create_template(
            business_id=business_id,
            name=data['name'],
            subject_template=data['subject_template'],
            html_template=data['html_template'],
            text_template=data.get('text_template'),
            template_type=data.get('type', 'generic'),
            created_by_user_id=user_id
        )
        
        if not template_id:
            return jsonify({'error': 'Failed to create template'}), 500
        
        return jsonify({
            'success': True,
            'template_id': template_id,
            'message': 'Template created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to create template: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/templates/<int:template_id>', methods=['PUT'])
@require_api_auth
def update_template(template_id):
    """
    Update an existing email template
    Admin/Owner only
    
    Request body:
        {
            "name": "New name",  // optional
            "subject_template": "New subject",  // optional
            "html_template": "New HTML",  // optional
            "text_template": "New text",  // optional
            "type": "generic",  // optional
            "is_active": true  // optional
        }
    
    Returns:
        200: Template updated
        400: Invalid data
        403: No permission
        404: Template not found
    """
    try:
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        data = request.get_json()
        
        # Update template
        email_service = get_email_service()
        success = email_service.update_template(
            business_id=business_id,
            template_id=template_id,
            name=data.get('name'),
            subject_template=data.get('subject_template'),
            html_template=data.get('html_template'),
            text_template=data.get('text_template'),
            template_type=data.get('type'),
            is_active=data.get('is_active')
        )
        
        if not success:
            return jsonify({'error': 'Template not found or failed to update'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Template updated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to update template {template_id}: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/templates/<int:template_id>', methods=['DELETE'])
@require_api_auth
def delete_template(template_id):
    """
    Delete (soft delete) an email template
    Admin/Owner only
    
    Returns:
        200: Template deleted
        403: No permission
        404: Template not found
    """
    try:
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        # Delete template (soft delete)
        email_service = get_email_service()
        success = email_service.delete_template(business_id, template_id)
        
        if not success:
            return jsonify({'error': 'Template not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Template deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to delete template {template_id}: {e}")
        return jsonify({'error': str(e)}), 500

@email_bp.route('/api/email/templates/<int:template_id>/preview', methods=['POST'])
@require_api_auth
def preview_template(template_id):
    """
    Preview template with sample data
    
    Request body:
        {
            "lead": {"first_name": "John", "last_name": "Doe", ...},  // optional
            "business": {"name": "My Business", ...},  // optional
            "agent": {"name": "Agent Name", ...},  // optional
            "extra_vars": {...}  // optional
        }
    
    Returns:
        200: Rendered template preview
        403: No permission
        404: Template not found
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business not found'}), 403
        
        data = request.get_json() or {}
        
        # Get template
        email_service = get_email_service()
        templates = email_service.list_templates(business_id, active_only=False)
        template = next((t for t in templates if t['id'] == template_id), None)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Render template with provided data
        rendered = email_service.render_template(
            template=template,
            lead=data.get('lead'),
            business=data.get('business'),
            agent=data.get('agent'),
            extra_vars=data.get('extra_vars')
        )
        
        return jsonify({
            'success': True,
            'preview': {
                'subject': rendered['subject'],
                'html': rendered['html'],
                'text': rendered['text']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"[EMAIL_API] Failed to preview template {template_id}: {e}")
        return jsonify({'error': str(e)}), 500

# ========================================================================
# Email Template Themes - Luxury Pre-built Templates
# ========================================================================

@email_bp.route('/api/email/template-catalog', methods=['GET'])
@require_api_auth
def get_template_catalog():
    """
    Get catalog of luxury pre-built email templates
    These are theme-based templates with simple fields (no HTML editing)
    
    🔥 CRITICAL: Always returns static 5 themes - no dependency on DB or tenant
    
    Returns:
        200: List of available template themes (always 5 themes)
        403: No permission
    """
    try:
        business_id = get_current_business_id()
        
        # 🔥 FIX: Always return static themes from code - no DB dependency
        from server.services.email_template_themes import get_all_themes
        
        themes = get_all_themes()
        
        # 🔥 LOG: Always log for debugging
        logger.info(f"[EMAIL_CATALOG] tenant_id={business_id}, themes_count={len(themes)}")
        
        # 🔥 FIX: Consistent format with 'ok' field for compatibility
        return jsonify({
            'ok': True,
            'success': True,
            'themes': themes,
            'count': len(themes)
        }), 200
        
    except Exception as e:
        logger.exception(f"[EMAIL_CATALOG] Failed to get template catalog")
        # 🔥 FIX: On error, still return basic themes as fallback
        fallback_themes = [
            {
                "id": "classic_blue",
                "name": "Classic Blue",
                "description": "תבנית כחולה קלאסית",
                "default_fields": {
                    "subject": "",
                    "greeting": "שלום {{lead.first_name}},",
                    "body": "",
                    "cta_text": "",
                    "cta_url": "",
                    "footer": "© {{business.name}}"
                }
            }
        ]
        return jsonify({
            'ok': True,
            'success': True,
            'themes': fallback_themes,
            'count': len(fallback_themes),
            'warning': 'Using fallback themes due to error'
        }), 200

@email_bp.route('/api/email/render-theme', methods=['POST'])
@require_api_auth
def render_theme_template():
    """
    Render a theme-based email template with user fields
    
    🔥 CRITICAL: Always returns {ok: true/false} format for consistency
    
    Request body:
        {
            "theme_id": "classic_blue",
            "fields": {
                "subject": "Email subject",
                "greeting": "שלום {{lead.first_name}},",
                "body": "Email body content...",
                "cta_text": "Click here",
                "cta_url": "https://example.com",
                "footer": "Footer text"
            },
            "lead_id": 123  // Optional: for variable substitution
        }
    
    Returns:
        200: {ok: true, html: "...", rendered: {...}}
        400: {ok: false, error: "..."}
        500: {ok: false, error: "..."}
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'ok': False, 'error': 'Business not found'}), 403
        
        data = request.get_json(force=True) or {}
        theme_id = data.get('theme_id')
        fields = data.get('fields') or {}
        lead_id = data.get('lead_id')
        
        # 🔥 FIX 3: Validate theme_id is provided with clear error message
        if not theme_id:
            logger.error(f"[EMAIL_API] render-theme called without theme_id: tenant_id={business_id} lead_id={lead_id}")
            return jsonify({
                'ok': False,
                'error': 'theme_id is required',
                'message': 'Must provide theme_id parameter (e.g., "classic_blue", "green_success")'
            }), 400
        
        # 🔥 FIX 3: Validate theme_id exists with helpful error
        from server.services.email_template_themes import EMAIL_TEMPLATE_THEMES
        if theme_id not in EMAIL_TEMPLATE_THEMES:
            available_themes = ', '.join(EMAIL_TEMPLATE_THEMES.keys())
            logger.error(f"[EMAIL_API] Invalid theme_id='{theme_id}' tenant_id={business_id} lead_id={lead_id}")
            return jsonify({
                'ok': False,
                'error': 'Invalid theme_id',
                'message': f'Theme "{theme_id}" not found. Available themes: {available_themes}'
            }), 400
        
        # 🔥 FIX 3: Log successful theme selection
        logger.info(f"[EMAIL_API] render-theme: theme_id={theme_id} tenant_id={business_id} lead_id={lead_id}")
        
        # 🔥 FIX: Always provide business and lead context with fallbacks to prevent undefined errors
        business_info = None
        lead_info = None
        
        try:
            from sqlalchemy import text as sa_text
            
            # Get business info - ALWAYS provide fallback
            biz_result = db.session.execute(
                sa_text("SELECT name, phone_number FROM business WHERE id = :business_id"),
                {"business_id": business_id}
            ).fetchone()
            if biz_result and biz_result[0]:
                business_info = {
                    'name': biz_result[0],
                    'phone': biz_result[1] or ''
                }
            else:
                # Fallback if business not found
                business_info = {
                    'name': 'העסק שלי',
                    'phone': ''
                }
            
            # Get lead info if provided - ALWAYS provide fallback
            if lead_id:
                lead_result = db.session.execute(
                    sa_text("SELECT first_name, last_name, email, phone_e164 FROM leads WHERE id = :lead_id AND tenant_id = :business_id"),
                    {"lead_id": lead_id, "business_id": business_id}
                ).fetchone()
                if lead_result:
                    lead_info = {
                        'first_name': lead_result[0] or 'שם',
                        'last_name': lead_result[1] or '',
                        'email': lead_result[2] or '',
                        'phone': lead_result[3] or ''
                    }
                else:
                    # Lead ID provided but not found - use placeholders
                    lead_info = {
                        'first_name': 'שם',
                        'last_name': '',
                        'email': '',
                        'phone': ''
                    }
            else:
                # No lead ID - use placeholders
                lead_info = {
                    'first_name': 'שם',
                    'last_name': '',
                    'email': '',
                    'phone': ''
                }
        except Exception as e:
            logger.warning(f"[EMAIL_API] Failed to fetch context info: {e}")
            # Provide fallbacks even on DB errors
            business_info = {'name': 'העסק שלי', 'phone': ''}
            lead_info = {'first_name': 'שם', 'last_name': '', 'email': '', 'phone': ''}
        
        # 🔥 FIX: Render variables in all fields with proper context
        from server.services.email_service import render_variables
        variables = {
            'business': business_info,
            'lead': lead_info
        }
        
        # Render each field with variables
        rendered_fields = {}
        for key, value in fields.items():
            if isinstance(value, str):
                rendered_fields[key] = render_variables(value, variables)
            else:
                rendered_fields[key] = value
        
        # Generate HTML from theme - this should NEVER fail with valid theme_id
        from server.services.email_template_themes import get_template_html
        html = get_template_html(theme_id, rendered_fields)
        
        # Validate HTML was generated
        if not html or not isinstance(html, str):
            logger.error(f"[EMAIL_API] get_template_html returned invalid html: type={type(html)}")
            return jsonify({
                'ok': False,
                'error': 'Failed to generate HTML from theme'
            }), 500
        
        # Generate plain text version
        from server.services.email_service import strip_html
        text = strip_html(html)
        
        logger.info(f"[EMAIL_API] render_theme success: theme={theme_id}, business_id={business_id}, lead_id={lead_id}, html_len={len(html)}")
        
        # 🔥 CONSISTENT FORMAT: Always return {ok: true, ...}
        return jsonify({
            'ok': True,
            'html': html,  # For backward compatibility
            'rendered': {
                'subject': rendered_fields.get('subject', ''),
                'html': html,
                'text': text
            }
        }), 200
        
    except Exception as e:
        logger.exception(f"[EMAIL_API] Failed to render theme template")
        # 🔥 CONSISTENT FORMAT: Always return {ok: false, error: ...}
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


# ========================================================================
# EMAIL TEXT TEMPLATES API - Quick text snippets for email content
# ========================================================================

@email_bp.route('/api/email/text-templates', methods=['GET'])
@require_api_auth
def list_email_text_templates():
    """
    List all email text templates for the current business
    
    Returns:
        JSON with templates array
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Get templates from database
        result = db.session.execute(
            sa_text("""
                SELECT id, name, category, subject_line, body_text, is_active, created_at, updated_at
                FROM email_text_templates
                WHERE business_id = :business_id AND is_active = TRUE
                ORDER BY created_at DESC
            """),
            {"business_id": business_id}
        ).fetchall()
        
        templates = []
        for row in result:
            templates.append({
                'id': row[0],
                'name': row[1],
                'category': row[2] or 'general',
                'subject_line': row[3] or '',
                'body_text': row[4],
                'is_active': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'updated_at': row[7].isoformat() if row[7] else None
            })
        
        return jsonify({'ok': True, 'templates': templates}), 200
        
    except Exception as e:
        logger.exception("[EMAIL_API] Failed to list text templates")
        return jsonify({'ok': False, 'error': str(e)}), 500


@email_bp.route('/api/email/text-templates', methods=['POST'])
@require_api_auth
def create_email_text_template():
    """
    Create a new email text template
    
    JSON body:
        - name: Template name (required)
        - category: Category like 'quote', 'greeting', 'pricing' (optional)
        - subject_line: Default subject line (optional)
        - body_text: Template body content (required)
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        category = data.get('category', 'general').strip()
        subject_line = data.get('subject_line', '').strip()
        body_text = data.get('body_text', '').strip()
        
        # Validation
        if not name:
            return jsonify({'ok': False, 'error': 'Template name is required'}), 400
        if not body_text:
            return jsonify({'ok': False, 'error': 'Template body text is required'}), 400
        
        # Get current user ID
        user_id = None
        if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
            user_id = g.user.get('id')
        
        # Insert template
        result = db.session.execute(
            sa_text("""
                INSERT INTO email_text_templates 
                (business_id, name, category, subject_line, body_text, created_by_user_id, is_active, created_at, updated_at)
                VALUES (:business_id, :name, :category, :subject_line, :body_text, :user_id, TRUE, NOW(), NOW())
                RETURNING id, created_at
            """),
            {
                "business_id": business_id,
                "name": name,
                "category": category,
                "subject_line": subject_line,
                "body_text": body_text,
                "user_id": user_id
            }
        )
        row = result.fetchone()
        db.session.commit()
        
        logger.info(f"[EMAIL_API] Created text template: id={row[0]}, name={name}, business_id={business_id}")
        
        return jsonify({
            'ok': True,
            'template': {
                'id': row[0],
                'name': name,
                'category': category,
                'subject_line': subject_line,
                'body_text': body_text,
                'created_at': row[1].isoformat() if row[1] else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.exception("[EMAIL_API] Failed to create text template")
        return jsonify({'ok': False, 'error': str(e)}), 500


@email_bp.route('/api/email/text-templates/<int:template_id>', methods=['GET'])
@require_api_auth
def get_email_text_template(template_id: int):
    """Get a specific email text template"""
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        result = db.session.execute(
            sa_text("""
                SELECT id, name, category, subject_line, body_text, is_active, created_at, updated_at
                FROM email_text_templates
                WHERE id = :template_id AND business_id = :business_id
            """),
            {"template_id": template_id, "business_id": business_id}
        ).fetchone()
        
        if not result:
            return jsonify({'ok': False, 'error': 'Template not found'}), 404
        
        return jsonify({
            'ok': True,
            'template': {
                'id': result[0],
                'name': result[1],
                'category': result[2] or 'general',
                'subject_line': result[3] or '',
                'body_text': result[4],
                'is_active': result[5],
                'created_at': result[6].isoformat() if result[6] else None,
                'updated_at': result[7].isoformat() if result[7] else None
            }
        }), 200
        
    except Exception as e:
        logger.exception("[EMAIL_API] Failed to get text template")
        return jsonify({'ok': False, 'error': str(e)}), 500


@email_bp.route('/api/email/text-templates/<int:template_id>', methods=['PATCH'])
@require_api_auth
def update_email_text_template(template_id: int):
    """Update an email text template"""
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json() or {}
        
        # Check template exists and belongs to this business
        existing = db.session.execute(
            sa_text("SELECT id FROM email_text_templates WHERE id = :id AND business_id = :business_id"),
            {"id": template_id, "business_id": business_id}
        ).fetchone()
        
        if not existing:
            return jsonify({'ok': False, 'error': 'Template not found'}), 404
        
        # Allowlist of updatable fields - prevents SQL injection by only allowing known fields
        ALLOWED_FIELDS = {'name', 'category', 'subject_line', 'body_text', 'is_active'}
        
        # Build update query dynamically using allowlisted fields
        updates = []
        params = {"id": template_id, "business_id": business_id}
        
        for field in ALLOWED_FIELDS:
            if field in data:
                if field == 'is_active':
                    updates.append(f"{field} = :{field}")
                    params[field] = bool(data[field])
                else:
                    updates.append(f"{field} = :{field}")
                    params[field] = str(data[field]).strip()
        
        if not updates:
            return jsonify({'ok': False, 'error': 'No fields to update'}), 400
        
        updates.append("updated_at = NOW()")
        
        db.session.execute(
            sa_text(f"""
                UPDATE email_text_templates
                SET {', '.join(updates)}
                WHERE id = :id AND business_id = :business_id
            """),
            params
        )
        db.session.commit()
        
        logger.info(f"[EMAIL_API] Updated text template: id={template_id}, business_id={business_id}")
        
        return jsonify({'ok': True, 'message': 'Template updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.exception("[EMAIL_API] Failed to update text template")
        return jsonify({'ok': False, 'error': str(e)}), 500


@email_bp.route('/api/email/text-templates/<int:template_id>', methods=['DELETE'])
@require_api_auth
def delete_email_text_template(template_id: int):
    """Delete (soft-delete by setting is_active=false) an email text template"""
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # Soft delete - set is_active to false
        result = db.session.execute(
            sa_text("""
                UPDATE email_text_templates
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = :id AND business_id = :business_id
                RETURNING id
            """),
            {"id": template_id, "business_id": business_id}
        )
        row = result.fetchone()
        db.session.commit()
        
        if not row:
            return jsonify({'ok': False, 'error': 'Template not found'}), 404
        
        logger.info(f"[EMAIL_API] Deleted text template: id={template_id}, business_id={business_id}")
        
        return jsonify({'ok': True, 'message': 'Template deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.exception("[EMAIL_API] Failed to delete text template")
        return jsonify({'ok': False, 'error': str(e)}), 500
