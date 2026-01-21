"""
Gmail Receipts API Blueprint - Receipt extraction from Gmail

Endpoints:
- GET /api/gmail/oauth/start - Start Gmail OAuth flow
- GET /api/gmail/oauth/callback - Handle OAuth callback
- DELETE /api/gmail/oauth/disconnect - Disconnect Gmail
- GET /api/gmail/status - Get Gmail connection status

- GET /api/receipts - List receipts with filtering
- GET /api/receipts/:id - Get receipt details
- POST /api/receipts/sync - Trigger manual sync
- PATCH /api/receipts/:id/mark - Mark receipt status
- DELETE /api/receipts/:id - Soft delete receipt

Security:
- Multi-tenant isolation (business_id)
- Permission checks via @require_page_access
- Encrypted refresh tokens
- Rate limiting for Gmail API calls
"""

from flask import Blueprint, jsonify, request, g, redirect, url_for, session
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.models_sql import GmailConnection, Receipt, Attachment, User, ReceiptSyncRun
from server.db import db
from datetime import datetime, timezone
import logging
import os
import json
import secrets
import threading
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Gmail OAuth Configuration
# IMPORTANT: Set these environment variables in production:
# - GOOGLE_CLIENT_ID: Your Google OAuth Client ID
# - GOOGLE_CLIENT_SECRET: Your Google OAuth Client Secret
# - GOOGLE_REDIRECT_URI: https://prosaas.pro/api/gmail/oauth/callback
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
# Default production redirect URI for prosaas.pro
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'https://prosaas.pro/api/gmail/oauth/callback')

# OAuth scopes - minimal required for reading emails and attachments
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
]

# Encryption for refresh tokens
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', os.getenv('FERNET_KEY', ''))

# Create blueprints
# The callback endpoint will be at: https://prosaas.pro/api/gmail/oauth/callback
gmail_oauth_bp = Blueprint("gmail_oauth", __name__, url_prefix="/api/gmail/oauth")
receipts_bp = Blueprint("receipts", __name__, url_prefix="/api/receipts")


# === Helper Functions ===

def get_current_user_id():
    """Get current user ID from authenticated context"""
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('id')
    return None


def get_current_business_id():
    """Get current business ID from authenticated context"""
    if hasattr(g, 'tenant') and g.tenant:
        return g.tenant
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('business_id')
    return None


def get_current_user_role():
    """Get current user role"""
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('role')
    return None


def check_admin_permission():
    """Check if current user has admin permission"""
    role = get_current_user_role()
    return role in ['system_admin', 'owner', 'admin']


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for storage using Fernet symmetric encryption.
    
    Security: In production, ENCRYPTION_KEY must be set to a valid Fernet key.
    In development only, falls back to base64 with a warning.
    """
    import os
    IS_PRODUCTION = os.getenv('PRODUCTION', '0') == '1'
    
    if not ENCRYPTION_KEY:
        if IS_PRODUCTION:
            raise ValueError("ENCRYPTION_KEY must be set in production for secure token storage")
        logger.warning("⚠️ DEV ONLY: No ENCRYPTION_KEY - using base64 encoding (NOT SECURE)")
        import base64
        return base64.b64encode(token.encode()).decode()
    
    try:
        from cryptography.fernet import Fernet
        key = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
        f = Fernet(key)
        return f.encrypt(token.encode()).decode()
    except ImportError:
        if IS_PRODUCTION:
            raise ValueError("cryptography package required for production deployment")
        logger.error("cryptography package not installed - using base64 encoding (DEV ONLY)")
        import base64
        return base64.b64encode(token.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Encryption failed - check ENCRYPTION_KEY format: {e}")


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token"""
    if not encrypted:
        return ''
    
    if not ENCRYPTION_KEY:
        import base64
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except Exception:
            return ''
    
    try:
        from cryptography.fernet import Fernet
        key = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        import base64
        return base64.b64decode(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return ''


def log_audit(action: str, resource_type: str, resource_id: int = None, details: dict = None):
    """Log operation for audit trail"""
    user_id = get_current_user_id()
    business_id = get_current_business_id()
    
    log_msg = f"[RECEIPTS_AUDIT] action={action} resource={resource_type}"
    if resource_id:
        log_msg += f" id={resource_id}"
    log_msg += f" user_id={user_id} business_id={business_id}"
    if details:
        # Don't log sensitive data
        safe_details = {k: v for k, v in details.items() if k not in ['token', 'refresh_token', 'access_token']}
        log_msg += f" details={safe_details}"
    
    logger.info(log_msg)


# === Gmail OAuth Endpoints ===

@gmail_oauth_bp.route('/start', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def oauth_start():
    """
    Start Gmail OAuth flow
    Returns URL to redirect user to Google's OAuth consent screen
    """
    if not GOOGLE_CLIENT_ID:
        return jsonify({
            "success": False,
            "error": "Gmail integration not configured. Contact administrator."
        }), 503
    
    business_id = get_current_business_id()
    if not business_id:
        return jsonify({"success": False, "error": "Business context required"}), 400
    
    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    session['gmail_oauth_state'] = state
    session['gmail_oauth_business_id'] = business_id
    
    # Determine redirect URI - uses GOOGLE_REDIRECT_URI env var or default to prosaas.pro
    redirect_uri = GOOGLE_REDIRECT_URI
    
    # Log the redirect URI being used
    logger.info(f"Gmail OAuth redirect URI: {redirect_uri}")
    
    # Build OAuth URL
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(GMAIL_SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    log_audit('oauth_start', 'gmail_connection')
    
    return jsonify({
        "success": True,
        "auth_url": auth_url
    })


@gmail_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Handle OAuth callback from Google
    Exchanges code for tokens and stores connection
    """
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Error from Google
    if error:
        logger.warning(f"OAuth error from Google: {error}")
        return redirect(f"/app/receipts?error={error}")
    
    # Validate state
    expected_state = session.pop('gmail_oauth_state', None)
    business_id = session.pop('gmail_oauth_business_id', None)
    
    if not state or state != expected_state:
        logger.warning("OAuth state mismatch - possible CSRF attack")
        return redirect("/app/receipts?error=invalid_state")
    
    if not business_id:
        logger.warning("No business_id in OAuth session")
        return redirect("/app/receipts?error=session_expired")
    
    if not code:
        return redirect("/app/receipts?error=no_code")
    
    # Exchange code for tokens
    try:
        import requests
        
        # Use the same redirect URI that was used to start the OAuth flow
        redirect_uri = GOOGLE_REDIRECT_URI
        logger.info(f"Gmail OAuth callback using redirect URI: {redirect_uri}")
        
        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=30
        )
        
        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return redirect("/app/receipts?error=token_exchange_failed")
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        
        if not refresh_token:
            logger.error("No refresh token received - user may have already authorized")
            return redirect("/app/receipts?error=no_refresh_token")
        
        # Get user info
        userinfo_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30
        )
        
        if userinfo_response.status_code != 200:
            logger.error(f"Failed to get user info: {userinfo_response.text}")
            return redirect("/app/receipts?error=userinfo_failed")
        
        userinfo = userinfo_response.json()
        email = userinfo.get('email')
        google_sub = userinfo.get('id')
        
        # Encrypt tokens (will raise error if ENCRYPTION_KEY not set in production)
        try:
            encrypted_refresh_token = encrypt_token(refresh_token)
        except ValueError as ve:
            # Encryption key missing or invalid
            logger.error(f"Token encryption failed: {ve}")
            return redirect("/app/receipts?error=encryption_not_configured")
        
        # Store connection
        existing = GmailConnection.query.filter_by(business_id=business_id).first()
        
        if existing:
            # Update existing connection
            existing.email_address = email
            existing.google_sub = google_sub
            existing.refresh_token_encrypted = encrypted_refresh_token
            existing.status = 'connected'
            existing.error_message = None
            existing.updated_at = datetime.utcnow()
        else:
            # Create new connection
            connection = GmailConnection(
                business_id=business_id,
                email_address=email,
                google_sub=google_sub,
                refresh_token_encrypted=encrypted_refresh_token,
                status='connected'
            )
            db.session.add(connection)
        
        db.session.commit()
        logger.info(f"Gmail connected for business {business_id}: {email}")
        
        # Trigger initial sync in the background
        # NOTE: Actual sync implementation should be done asynchronously
        logger.info(f"Gmail connection established. Sync will start automatically.")
        
        return redirect("/app/receipts?connected=true")
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        db.session.rollback()
        return redirect(f"/app/receipts?error=server_error")


@gmail_oauth_bp.route('/disconnect', methods=['DELETE'])
@require_api_auth()
@require_page_access('gmail_receipts')
def oauth_disconnect():
    """
    Disconnect Gmail integration
    Removes stored tokens but keeps existing receipts
    """
    business_id = get_current_business_id()
    
    connection = GmailConnection.query.filter_by(business_id=business_id).first()
    
    if not connection:
        return jsonify({"success": False, "error": "No Gmail connection found"}), 404
    
    # Mark as disconnected (keep record for audit)
    connection.status = 'disconnected'
    connection.refresh_token_encrypted = ''  # Clear token
    connection.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    log_audit('disconnect', 'gmail_connection', connection.id)
    
    return jsonify({
        "success": True,
        "message": "Gmail disconnected successfully"
    })


@gmail_oauth_bp.route('/status', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def oauth_status():
    """
    Get Gmail connection status
    """
    business_id = get_current_business_id()
    
    connection = GmailConnection.query.filter_by(business_id=business_id).first()
    
    if not connection:
        return jsonify({
            "connected": False,
            "status": "not_connected"
        })
    
    return jsonify({
        "connected": connection.status == 'connected',
        "status": connection.status,
        "email": connection.email_address if connection.status == 'connected' else None,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "error_message": connection.error_message if connection.status == 'error' else None
    })


# === Receipts CRUD Endpoints ===

@receipts_bp.route('', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def list_receipts():
    """
    List receipts with filtering and pagination
    
    Query params:
    - status: Filter by status (pending_review|approved|rejected|not_receipt)
    - vendor: Search vendor name
    - from_date: Filter by received_at >= date (ISO format: YYYY-MM-DD)
    - to_date: Filter by received_at <= date (ISO format: YYYY-MM-DD, inclusive end of day)
    - min_amount: Minimum amount
    - max_amount: Maximum amount
    - page: Page number (1-indexed)
    - per_page: Items per page (default 20, max 100)
    - sort: Sort field (received_at|amount|vendor_name|created_at)
    - order: Sort order (asc|desc)
    """
    business_id = get_current_business_id()
    
    # Log filter parameters (without sensitive data)
    from_date_param = request.args.get('from_date')
    to_date_param = request.args.get('to_date')
    status_param = request.args.get('status')
    logger.info(f"[list_receipts] Filtering - business_id={business_id}, from_date={from_date_param}, to_date={to_date_param}, status={status_param}")
    
    # Build query with distinct to prevent duplicates
    query = Receipt.query.filter_by(
        business_id=business_id,
        is_deleted=False
    ).distinct(Receipt.id)
    
    # Apply filters
    status = request.args.get('status')
    if status:
        query = query.filter(Receipt.status == status)
    
    vendor = request.args.get('vendor')
    if vendor:
        query = query.filter(Receipt.vendor_name.ilike(f'%{vendor}%'))
    
    # Date filtering with proper parsing
    from_date = request.args.get('from_date')
    if from_date:
        try:
            # Handle both plain date (YYYY-MM-DD) and ISO datetime formats
            if 'T' in from_date:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            else:
                # Plain date - set to start of day (00:00:00) in UTC
                from_dt = datetime.strptime(from_date, '%Y-%m-%d').replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
            query = query.filter(Receipt.received_at >= from_dt)
            logger.info(f"[list_receipts] Applied from_date filter: {from_dt.isoformat()}")
        except (ValueError, TypeError) as e:
            logger.warning(f"[list_receipts] Invalid from_date format: {from_date}, error: {e}")
    
    to_date = request.args.get('to_date')
    if to_date:
        try:
            # Handle both plain date (YYYY-MM-DD) and ISO datetime formats
            if 'T' in to_date:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            else:
                # Plain date - set to end of day (23:59:59.999999) in UTC for inclusive range
                to_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
                )
            query = query.filter(Receipt.received_at <= to_dt)
            logger.info(f"[list_receipts] Applied to_date filter: {to_dt.isoformat()}")
        except (ValueError, TypeError) as e:
            logger.warning(f"[list_receipts] Invalid to_date format: {to_date}, error: {e}")
    
    min_amount = request.args.get('min_amount', type=float)
    if min_amount is not None:
        query = query.filter(Receipt.amount >= min_amount)
    
    max_amount = request.args.get('max_amount', type=float)
    if max_amount is not None:
        query = query.filter(Receipt.amount <= max_amount)
    
    # Sorting - use stable ordering with id as tiebreaker to prevent pagination issues
    sort_field = request.args.get('sort', 'received_at')
    sort_order = request.args.get('order', 'desc')
    
    sort_column = {
        'received_at': Receipt.received_at,
        'amount': Receipt.amount,
        'vendor_name': Receipt.vendor_name,
        'created_at': Receipt.created_at,
        'status': Receipt.status,
    }.get(sort_field, Receipt.received_at)
    
    # Note: nullslast/nullsfirst are PostgreSQL-specific but this codebase requires PostgreSQL
    # Add id as secondary sort for stable pagination
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc().nullslast(), Receipt.id.asc())
    else:
        query = query.order_by(sort_column.desc().nullsfirst(), Receipt.id.desc())
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    total = query.count()
    receipts = query.offset((page - 1) * per_page).limit(per_page).all()
    
    logger.info(f"[list_receipts] Query returned {len(receipts)} receipts, total={total}")
    
    # Build response
    items = []
    for receipt in receipts:
        item = {
            "id": receipt.id,
            "source": receipt.source,
            "gmail_message_id": receipt.gmail_message_id,
            "from_email": receipt.from_email,
            "subject": receipt.subject,
            "received_at": receipt.received_at.isoformat() if receipt.received_at else None,
            "vendor_name": receipt.vendor_name,
            "amount": float(receipt.amount) if receipt.amount else None,
            "currency": receipt.currency,
            "invoice_number": receipt.invoice_number,
            "invoice_date": receipt.invoice_date.isoformat() if receipt.invoice_date else None,
            "confidence": receipt.confidence,
            "status": receipt.status,
            "attachment_id": receipt.attachment_id,
            "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
        }
        
        # Include attachment info if available
        if receipt.attachment_id and receipt.attachment:
            item["attachment"] = {
                "id": receipt.attachment.id,
                "filename": receipt.attachment.filename_original,
                "mime_type": receipt.attachment.mime_type,
                "size": receipt.attachment.file_size,
            }
        
        items.append(item)
    
    return jsonify({
        "success": True,
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    })


@receipts_bp.route('/<int:receipt_id>', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def get_receipt(receipt_id):
    """
    Get single receipt details with signed URL for attachment
    """
    business_id = get_current_business_id()
    
    receipt = Receipt.query.filter_by(
        id=receipt_id,
        business_id=business_id,
        is_deleted=False
    ).first()
    
    if not receipt:
        return jsonify({"success": False, "error": "Receipt not found"}), 404
    
    result = {
        "id": receipt.id,
        "source": receipt.source,
        "gmail_message_id": receipt.gmail_message_id,
        "gmail_thread_id": receipt.gmail_thread_id,
        "from_email": receipt.from_email,
        "subject": receipt.subject,
        "received_at": receipt.received_at.isoformat() if receipt.received_at else None,
        "vendor_name": receipt.vendor_name,
        "amount": float(receipt.amount) if receipt.amount else None,
        "currency": receipt.currency,
        "invoice_number": receipt.invoice_number,
        "invoice_date": receipt.invoice_date.isoformat() if receipt.invoice_date else None,
        "confidence": receipt.confidence,
        "raw_extraction_json": receipt.raw_extraction_json,
        "status": receipt.status,
        "reviewed_by": receipt.reviewed_by,
        "reviewed_at": receipt.reviewed_at.isoformat() if receipt.reviewed_at else None,
        "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
        "updated_at": receipt.updated_at.isoformat() if receipt.updated_at else None,
    }
    
    # Get reviewer info
    if receipt.reviewed_by:
        reviewer = User.query.get(receipt.reviewed_by)
        if reviewer:
            result["reviewer"] = {
                "id": reviewer.id,
                "name": reviewer.name,
                "email": reviewer.email
            }
    
    # Get attachment with signed URL
    if receipt.attachment_id and receipt.attachment:
        from server.services.attachment_service import get_attachment_service
        attachment_service = get_attachment_service()
        
        signed_url = None
        try:
            signed_url = attachment_service.generate_signed_url(
                attachment_id=receipt.attachment.id,
                storage_key=receipt.attachment.storage_path,
                ttl_minutes=60  # 1 hour
            )
        except Exception as e:
            logger.warning(f"Failed to generate signed URL: {e}")
        
        result["attachment"] = {
            "id": receipt.attachment.id,
            "filename": receipt.attachment.filename_original,
            "mime_type": receipt.attachment.mime_type,
            "size": receipt.attachment.file_size,
            "signed_url": signed_url
        }
    
    return jsonify({"success": True, "receipt": result})


@receipts_bp.route('/<int:receipt_id>/mark', methods=['PATCH'])
@require_api_auth()
@require_page_access('gmail_receipts')
def mark_receipt(receipt_id):
    """
    Mark receipt status (approve, reject, or mark as not a receipt)
    
    Body:
    - status: New status (approved|rejected|not_receipt|pending_review)
    """
    business_id = get_current_business_id()
    user_id = get_current_user_id()
    
    receipt = Receipt.query.filter_by(
        id=receipt_id,
        business_id=business_id,
        is_deleted=False
    ).first()
    
    if not receipt:
        return jsonify({"success": False, "error": "Receipt not found"}), 404
    
    data = request.get_json() or {}
    new_status = data.get('status')
    
    valid_statuses = ['approved', 'rejected', 'not_receipt', 'pending_review']
    if new_status not in valid_statuses:
        return jsonify({
            "success": False,
            "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        }), 400
    
    old_status = receipt.status
    receipt.status = new_status
    receipt.reviewed_by = user_id
    receipt.reviewed_at = datetime.utcnow()
    receipt.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    log_audit('mark', 'receipt', receipt_id, {'old_status': old_status, 'new_status': new_status})
    
    return jsonify({
        "success": True,
        "receipt": {
            "id": receipt.id,
            "status": receipt.status,
            "reviewed_at": receipt.reviewed_at.isoformat()
        }
    })


@receipts_bp.route('/<int:receipt_id>', methods=['DELETE'])
@require_api_auth()
@require_page_access('gmail_receipts')
def delete_receipt(receipt_id):
    """
    Soft delete a receipt (admin only)
    """
    business_id = get_current_business_id()
    
    if not check_admin_permission():
        return jsonify({"success": False, "error": "Admin permission required"}), 403
    
    receipt = Receipt.query.filter_by(
        id=receipt_id,
        business_id=business_id,
        is_deleted=False
    ).first()
    
    if not receipt:
        return jsonify({"success": False, "error": "Receipt not found"}), 404
    
    receipt.is_deleted = True
    receipt.deleted_at = datetime.utcnow()
    receipt.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    log_audit('delete', 'receipt', receipt_id)
    
    return jsonify({
        "success": True,
        "message": "Receipt deleted successfully"
    })


@receipts_bp.route('/purge', methods=['DELETE'])
@require_api_auth()
@require_page_access('gmail_receipts')
def purge_all_receipts():
    """
    Delete ALL receipts for the current business (admin/owner only)
    
    Requires double confirmation:
    - Body must include: {"confirm": true, "typed": "DELETE"}
    
    Optionally deletes attachments from storage if delete_attachments=true
    
    Returns:
    - deleted_receipts_count: Number of receipts deleted
    - deleted_attachments_count: Number of attachments deleted (if requested)
    """
    business_id = get_current_business_id()
    
    # Check admin/owner permission
    role = get_current_user_role()
    if role not in ['system_admin', 'owner', 'admin']:
        return jsonify({
            "success": False,
            "error": "Owner or admin permission required"
        }), 403
    
    # Get confirmation
    data = request.get_json() or {}
    confirm = data.get('confirm', False)
    typed = data.get('typed', '')
    delete_attachments = data.get('delete_attachments', False)
    
    # Require double confirmation
    if not confirm or typed != 'DELETE':
        return jsonify({
            "success": False,
            "error": "Confirmation required. Send: {\"confirm\": true, \"typed\": \"DELETE\"}"
        }), 400
    
    try:
        # Find all receipts for this business
        receipts = Receipt.query.filter_by(
            business_id=business_id,
            is_deleted=False
        ).all()
        
        deleted_count = len(receipts)
        deleted_attachments_count = 0
        
        # Collect attachment IDs if we need to delete them
        attachment_ids_to_delete = set()
        if delete_attachments:
            for receipt in receipts:
                if receipt.attachment_id:
                    attachment_ids_to_delete.add(receipt.attachment_id)
                if receipt.preview_attachment_id:
                    attachment_ids_to_delete.add(receipt.preview_attachment_id)
        
        # Soft delete all receipts
        for receipt in receipts:
            receipt.is_deleted = True
            receipt.deleted_at = datetime.utcnow()
            receipt.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Delete attachments if requested
        if delete_attachments and attachment_ids_to_delete:
            from server.services.attachment_service import get_attachment_service
            attachment_service = get_attachment_service()
            
            for att_id in attachment_ids_to_delete:
                try:
                    attachment = Attachment.query.get(att_id)
                    if attachment and attachment.purpose in ('receipt_source', 'receipt_preview'):
                        # Delete from storage (R2)
                        try:
                            attachment_service.delete_file(
                                storage_key=attachment.storage_path
                            )
                        except Exception as storage_err:
                            logger.warning(f"Failed to delete attachment {att_id} from storage: {storage_err}")
                        
                        # Delete from database
                        db.session.delete(attachment)
                        deleted_attachments_count += 1
                except Exception as att_err:
                    logger.error(f"Failed to delete attachment {att_id}: {att_err}")
            
            db.session.commit()
        
        log_audit('purge', 'receipts', business_id, {
            'deleted_receipts': deleted_count,
            'deleted_attachments': deleted_attachments_count
        })
        
        return jsonify({
            "success": True,
            "message": f"Purged {deleted_count} receipts",
            "deleted_receipts_count": deleted_count,
            "deleted_attachments_count": deleted_attachments_count
        })
        
    except Exception as e:
        logger.error(f"Receipt purge failed: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Purge failed: {str(e)}"
        }), 500


@receipts_bp.route('/sync', methods=['POST'])
@require_api_auth()
@require_page_access('gmail_receipts')
def sync_receipts():
    """
    Trigger manual sync of receipts from Gmail
    
    Body (optional):
    - mode: 'full_backfill' or 'incremental' (default: incremental)
    - max_messages: Maximum messages to process (optional)
    - from_date: Start date in YYYY-MM-DD format (optional, overrides mode)
    - to_date: End date in YYYY-MM-DD format (optional)
    - months_back: Number of months to go back for full_backfill (default: 36)
    
    Date range examples:
    - {"mode": "full_backfill", "months_back": 60} - Sync last 60 months (5 years)
    - {"from_date": "2023-01-01", "to_date": "2023-12-31"} - Sync all of 2023
    - {"from_date": "2020-01-01"} - Sync from 2020 onwards
    - {"to_date": "2024-12-31"} - Sync everything up to end of 2024
    
    This fetches new emails that may contain receipts and processes them.
    Returns immediately with status - sync happens synchronously.
    """
    business_id = get_current_business_id()
    
    # Log sync request
    logger.info(f"🔔 SYNC REQUEST: business_id={business_id}")
    
    # Check Gmail connection
    connection = GmailConnection.query.filter_by(business_id=business_id).first()
    
    if not connection or connection.status != 'connected':
        logger.warning(f"🔔 SYNC FAILED: Gmail not connected for business_id={business_id}")
        return jsonify({
            "success": False,
            "error": "Gmail not connected. Please connect your Gmail account first."
        }), 400
    
    # Get parameters - handle both JSON and empty body
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    
    logger.info(f"🔔 SYNC PARAMS: {data}")
    
    mode = data.get('mode', 'incremental')
    max_messages = data.get('max_messages', None)
    from_date = data.get('from_date', None)  # NEW: Support custom date range
    to_date = data.get('to_date', None)      # NEW: Support custom date range
    months_back = data.get('months_back', 36)  # NEW: Support configurable backfill depth
    
    if mode not in ['full_backfill', 'incremental', 'full']:  # Support legacy 'full' mode
        return jsonify({
            "success": False,
            "error": "Invalid mode. Must be 'full_backfill', 'full', or 'incremental'"
        }), 400
    
    # Map legacy 'full' to 'full_backfill'
    if mode == 'full':
        mode = 'full_backfill'
    
    # Validate date formats if provided
    if from_date:
        try:
            datetime.strptime(from_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid from_date format. Use YYYY-MM-DD (e.g., 2023-01-01)"
            }), 400
    
    if to_date:
        try:
            datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid to_date format. Use YYYY-MM-DD (e.g., 2023-12-31)"
            }), 400
    
    # Import sync service
    try:
        from server.services.gmail_sync_service import sync_gmail_receipts
        
        # Check for existing running sync (prevent double-click)
        existing_run = ReceiptSyncRun.query.filter_by(
            business_id=business_id,
            status='running'
        ).first()
        
        if existing_run:
            logger.info(f"🔔 SYNC ALREADY RUNNING: run_id={existing_run.id}")
            return jsonify({
                "success": True,
                "message": "Sync already in progress",
                "sync_run_id": existing_run.id,
                "status": "running"
            }), 409  # Conflict
        
        logger.info(f"🔔 STARTING SYNC: mode={mode}, from_date={from_date}, to_date={to_date}, max_messages={max_messages}")
        
        # Start background thread (non-daemon to prevent data loss on server restart)
        def run_sync_in_background():
            from server.db import db
            # Need app context for background thread
            from flask import current_app
            with current_app.app_context():
                try:
                    logger.info(f"🔔 BACKGROUND SYNC STARTED: business_id={business_id}")
                    sync_gmail_receipts(
                        business_id=business_id,
                        mode=mode,
                        max_messages=max_messages,
                        from_date=from_date,
                        to_date=to_date,
                        months_back=months_back
                    )
                    logger.info(f"🔔 BACKGROUND SYNC COMPLETED: business_id={business_id}")
                except Exception as e:
                    logger.error(f"🔔 BACKGROUND SYNC FAILED: {e}", exc_info=True)

        thread = threading.Thread(target=run_sync_in_background, daemon=False)
        thread.start()
        
        logger.info(f"🔔 SYNC THREAD STARTED: business_id={business_id}")
        
        # Return immediately with 202 Accepted
        return jsonify({
            "success": True,
            "message": "Sync started in background",
            "sync_run_id": None,  # Will be created by sync function
            "status": "starting"
        }), 202
        
    except ImportError:
        logger.warning("Gmail sync service not yet implemented")
        return jsonify({
            "ok": False,
            "error": {
                "code": "SERVICE_NOT_AVAILABLE",
                "message": "Gmail sync service not available yet",
                "hint": "The Gmail sync feature is not yet implemented on this server"
            }
        }), 501
    except ValueError as e:
        # Invalid date format or other validation errors
        logger.warning(f"Validation error: {e}")
        return jsonify({
            "ok": False,
            "error": {
                "code": "INVALID_DATE_FORMAT",
                "message": str(e),
                "hint": "Use YYYY-MM-DD format for dates (e.g., 2023-01-01)"
            }
        }), 400
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        
        # 🔥 CRITICAL FIX: Always rollback on exception to prevent PendingRollbackError
        db.session.rollback()
        
        if connection:
            connection.status = 'error'
            connection.error_message = str(e)[:500]
            try:
                db.session.commit()
            except Exception as commit_err:
                logger.error(f"Failed to update connection status: {commit_err}")
                db.session.rollback()
        
        # Determine error code and hint based on exception type and message
        error_code = "SYNC_FAILED"
        hint = "Please try again later. If the problem persists, contact support."
        error_message = str(e)
        
        # Check for specific error types using exception classes and patterns
        from sqlalchemy.exc import OperationalError, ProgrammingError
        import re
        
        if isinstance(e, (OperationalError, ProgrammingError)):
            # Database errors
            if re.search(r'(UndefinedColumn|column.*does not exist)', error_message, re.IGNORECASE):
                error_code = "DB_MIGRATION_MISSING_COLUMN"
                hint = "Database schema needs to be updated. Please run migrations: python -m server.db_migrate"
            elif re.search(r'(relation.*does not exist|table.*does not exist)', error_message, re.IGNORECASE):
                error_code = "DB_MIGRATION_MISSING_TABLE"
                hint = "Database tables are missing. Please run migrations: python -m server.db_migrate"
        elif re.search(r'(permission|unauthorized|401|403)', error_message, re.IGNORECASE):
            # Permission/auth errors
            error_code = "GMAIL_PERMISSION_DENIED"
            hint = "Gmail access token expired or permissions revoked. Try disconnecting and reconnecting Gmail."
        elif re.search(r'(rate.*limit|429|quota.*exceeded)', error_message, re.IGNORECASE):
            # Rate limiting errors
            error_code = "GMAIL_RATE_LIMIT"
            hint = "Gmail API rate limit exceeded. Please wait a few minutes and try again."
        elif re.search(r'(timeout|timed out)', error_message, re.IGNORECASE):
            # Timeout errors
            error_code = "SYNC_TIMEOUT"
            hint = "Sync operation timed out. Try syncing a smaller date range or contact support."
        
        return jsonify({
            "ok": False,
            "error": {
                "code": error_code,
                "message": error_message[:500],
                "hint": hint
            }
        }), 500


@receipts_bp.route('/stats', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def get_receipt_stats():
    """
    Get receipt statistics for dashboard
    """
    business_id = get_current_business_id()
    from sqlalchemy import func
    
    # Count by status
    status_counts = db.session.query(
        Receipt.status,
        func.count(Receipt.id)
    ).filter(
        Receipt.business_id == business_id,
        Receipt.is_deleted == False
    ).group_by(Receipt.status).all()
    
    status_dict = dict(status_counts)
    
    # Total amount by month (last 12 months)
    # This would be a more complex query - simplified for now
    total = db.session.query(
        func.count(Receipt.id),
        func.sum(Receipt.amount)
    ).filter(
        Receipt.business_id == business_id,
        Receipt.is_deleted == False,
        Receipt.status == 'approved'
    ).first()
    
    return jsonify({
        "success": True,
        "stats": {
            "total": total[0] or 0,
            "total_amount": float(total[1]) if total[1] else 0,
            "by_status": {
                "pending_review": status_dict.get('pending_review', 0),
                "approved": status_dict.get('approved', 0),
                "rejected": status_dict.get('rejected', 0),
                "not_receipt": status_dict.get('not_receipt', 0),
            }
        }
    })


@receipts_bp.route('/sync/status', methods=['GET'])
@require_api_auth()
@require_page_access('gmail_receipts')
def get_sync_status():
    """
    Get status of current or most recent sync job
    
    Query params:
    - run_id: Specific sync run ID (optional, defaults to most recent)
    """
    business_id = get_current_business_id()
    from server.models_sql import ReceiptSyncRun
    
    # Get sync run
    run_id = request.args.get('run_id', type=int)
    
    if run_id:
        sync_run = ReceiptSyncRun.query.filter_by(
            id=run_id,
            business_id=business_id
        ).first()
    else:
        # Get most recent sync run
        sync_run = ReceiptSyncRun.query.filter_by(
            business_id=business_id
        ).order_by(ReceiptSyncRun.started_at.desc()).first()
    
    if not sync_run:
        return jsonify({
            "success": False,
            "error": "No sync runs found"
        }), 404
    
    # Calculate duration
    duration_seconds = None
    if sync_run.finished_at:
        delta = sync_run.finished_at - sync_run.started_at
        duration_seconds = int(delta.total_seconds())
    
    # Calculate progress percentage
    progress_pct = 0
    if sync_run.status == 'completed':
        progress_pct = 100
    elif sync_run.messages_scanned > 0:
        # Rough estimate based on saved receipts vs scanned messages
        progress_pct = min(95, (sync_run.saved_receipts / max(1, sync_run.messages_scanned)) * 100)
    
    return jsonify({
        "success": True,
        "sync_run": {
            "id": sync_run.id,
            "mode": sync_run.mode,
            "status": sync_run.status,
            "started_at": sync_run.started_at.isoformat(),
            "finished_at": sync_run.finished_at.isoformat() if sync_run.finished_at else None,
            "duration_seconds": duration_seconds,
            "progress_percentage": progress_pct,
            "progress": {
                "pages_scanned": sync_run.pages_scanned,
                "messages_scanned": sync_run.messages_scanned,
                "candidate_receipts": sync_run.candidate_receipts,
                "saved_receipts": sync_run.saved_receipts,
                "preview_generated_count": sync_run.preview_generated_count,
                "errors_count": sync_run.errors_count
            },
            "error_message": sync_run.error_message if sync_run.status == 'failed' else None
        }
    })


@receipts_bp.route('/sync/<int:run_id>/cancel', methods=['POST'])
@require_api_auth()
@require_page_access('gmail_receipts')
def cancel_sync(run_id):
    """
    Cancel a running sync job
    
    Sets the status to 'cancelled' which will be detected by the sync loop
    and cause it to stop gracefully after finishing the current message.
    """
    business_id = get_current_business_id()
    from server.models_sql import ReceiptSyncRun
    
    sync_run = ReceiptSyncRun.query.filter_by(
        id=run_id,
        business_id=business_id
    ).first()
    
    if not sync_run:
        return jsonify({
            "success": False,
            "error": "Sync run not found"
        }), 404
    
    # Can only cancel running syncs
    if sync_run.status != 'running':
        return jsonify({
            "success": False,
            "error": f"Cannot cancel sync with status '{sync_run.status}'"
        }), 400
    
    # Mark as cancelled - the sync loop will detect this and stop
    sync_run.status = 'cancelled'
    sync_run.cancelled_at = datetime.now(timezone.utc)
    sync_run.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    log_audit('cancel', 'receipt_sync_run', run_id, {
        'messages_scanned': sync_run.messages_scanned,
        'receipts_saved': sync_run.saved_receipts
    })
    
    return jsonify({
        "success": True,
        "message": "Sync cancellation requested. It will stop after finishing the current message.",
        "sync_run": {
            "id": sync_run.id,
            "status": sync_run.status,
            "cancelled_at": sync_run.cancelled_at.isoformat() if sync_run.cancelled_at else None
        }
    })
