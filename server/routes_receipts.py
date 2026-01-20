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
from server.models_sql import GmailConnection, Receipt, Attachment, User
from server.db import db
from datetime import datetime
import logging
import os
import json
import secrets
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
    - from_date: Filter by received_at >= date
    - to_date: Filter by received_at <= date
    - min_amount: Minimum amount
    - max_amount: Maximum amount
    - page: Page number (1-indexed)
    - per_page: Items per page (default 20, max 100)
    - sort: Sort field (received_at|amount|vendor_name|created_at)
    - order: Sort order (asc|desc)
    """
    business_id = get_current_business_id()
    
    # Build query
    query = Receipt.query.filter_by(
        business_id=business_id,
        is_deleted=False
    )
    
    # Apply filters
    status = request.args.get('status')
    if status:
        query = query.filter(Receipt.status == status)
    
    vendor = request.args.get('vendor')
    if vendor:
        query = query.filter(Receipt.vendor_name.ilike(f'%{vendor}%'))
    
    from_date = request.args.get('from_date')
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            query = query.filter(Receipt.received_at >= from_dt)
        except ValueError:
            pass
    
    to_date = request.args.get('to_date')
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            query = query.filter(Receipt.received_at <= to_dt)
        except ValueError:
            pass
    
    min_amount = request.args.get('min_amount', type=float)
    if min_amount is not None:
        query = query.filter(Receipt.amount >= min_amount)
    
    max_amount = request.args.get('max_amount', type=float)
    if max_amount is not None:
        query = query.filter(Receipt.amount <= max_amount)
    
    # Sorting
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
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullsfirst())
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    total = query.count()
    receipts = query.offset((page - 1) * per_page).limit(per_page).all()
    
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


@receipts_bp.route('/sync', methods=['POST'])
@require_api_auth()
@require_page_access('gmail_receipts')
def sync_receipts():
    """
    Trigger manual sync of receipts from Gmail
    
    Body (optional):
    - mode: 'full' or 'incremental' (default: incremental)
    - max_messages: Maximum messages to process (optional)
    - from_date: Start date in YYYY-MM-DD format (optional, overrides mode)
    - to_date: End date in YYYY-MM-DD format (optional)
    
    Date range examples:
    - {"from_date": "2023-01-01", "to_date": "2023-12-31"} - Sync all of 2023
    - {"from_date": "2020-01-01"} - Sync from 2020 onwards
    - {"to_date": "2024-12-31"} - Sync everything up to end of 2024
    
    This fetches new emails that may contain receipts and processes them.
    Returns immediately with status - sync happens synchronously.
    """
    business_id = get_current_business_id()
    
    # Check Gmail connection
    connection = GmailConnection.query.filter_by(business_id=business_id).first()
    
    if not connection or connection.status != 'connected':
        return jsonify({
            "success": False,
            "error": "Gmail not connected. Please connect your Gmail account first."
        }), 400
    
    # Get parameters - handle both JSON and empty body
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    
    mode = data.get('mode', 'incremental')
    max_messages = data.get('max_messages', None)
    from_date = data.get('from_date', None)  # NEW: Support custom date range
    to_date = data.get('to_date', None)      # NEW: Support custom date range
    
    if mode not in ['full', 'incremental']:
        return jsonify({
            "success": False,
            "error": "Invalid mode. Must be 'full' or 'incremental'"
        }), 400
    
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
        
        # Run sync synchronously with date parameters
        result = sync_gmail_receipts(
            business_id, 
            mode=mode, 
            max_messages=max_messages,
            from_date=from_date,
            to_date=to_date
        )
        
        log_audit('sync', 'gmail_receipts', details={
            'mode': mode,
            'from_date': from_date,
            'to_date': to_date,
            'new_receipts': result.get('new_count', 0),
            'pages_scanned': result.get('pages_scanned', 0),
            'messages_scanned': result.get('messages_scanned', 0)
        })
        
        return jsonify({
            "success": True,
            "message": "Sync completed",
            "mode": mode,
            "from_date": from_date,
            "to_date": to_date,
            "sync_run_id": result.get('sync_run_id'),
            "new_receipts": result.get('new_count', 0),
            "processed": result.get('processed', 0),
            "skipped": result.get('skipped', 0),
            "pages_scanned": result.get('pages_scanned', 0),
            "messages_scanned": result.get('messages_scanned', 0),
            "errors": result.get('errors', 0)
        })
        
    except ImportError:
        logger.warning("Gmail sync service not yet implemented")
        return jsonify({
            "success": False,
            "error": "Gmail sync service not available yet"
        }), 501
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        
        if connection:
            connection.status = 'error'
            connection.error_message = str(e)[:500]
            db.session.commit()
        
        return jsonify({
            "success": False,
            "error": "Sync failed. Please try again later."
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
    
    return jsonify({
        "success": True,
        "sync_run": {
            "id": sync_run.id,
            "mode": sync_run.mode,
            "status": sync_run.status,
            "started_at": sync_run.started_at.isoformat(),
            "finished_at": sync_run.finished_at.isoformat() if sync_run.finished_at else None,
            "duration_seconds": duration_seconds,
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
