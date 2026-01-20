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
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', '')

# OAuth scopes - minimal required for reading emails and attachments
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
]

# Encryption for refresh tokens
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', os.getenv('FERNET_KEY', ''))

# Create blueprints
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
    """Encrypt a token for storage"""
    if not ENCRYPTION_KEY:
        logger.warning("No encryption key configured - using base64 encoding (NOT SECURE)")
        import base64
        return base64.b64encode(token.encode()).decode()
    
    try:
        from cryptography.fernet import Fernet
        f = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
        return f.encrypt(token.encode()).decode()
    except ImportError:
        logger.error("cryptography package not installed - using base64 encoding")
        import base64
        return base64.b64encode(token.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        import base64
        return base64.b64encode(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token"""
    if not ENCRYPTION_KEY:
        import base64
        return base64.b64decode(encrypted.encode()).decode()
    
    try:
        from cryptography.fernet import Fernet
        f = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        import base64
        return base64.b64decode(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        import base64
        return base64.b64decode(encrypted.encode()).decode()


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
    
    # Determine redirect URI
    redirect_uri = GOOGLE_REDIRECT_URI
    if not redirect_uri:
        # Auto-detect from request
        redirect_uri = f"{request.host_url.rstrip('/')}/api/gmail/oauth/callback"
    
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
        
        redirect_uri = GOOGLE_REDIRECT_URI
        if not redirect_uri:
            redirect_uri = f"{request.host_url.rstrip('/')}/api/gmail/oauth/callback"
        
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
        
        # Store connection
        existing = GmailConnection.query.filter_by(business_id=business_id).first()
        
        if existing:
            # Update existing connection
            existing.email_address = email
            existing.google_sub = google_sub
            existing.refresh_token_encrypted = encrypt_token(refresh_token)
            existing.status = 'connected'
            existing.error_message = None
            existing.updated_at = datetime.utcnow()
        else:
            # Create new connection
            connection = GmailConnection(
                business_id=business_id,
                email_address=email,
                google_sub=google_sub,
                refresh_token_encrypted=encrypt_token(refresh_token),
                status='connected'
            )
            db.session.add(connection)
        
        db.session.commit()
        logger.info(f"Gmail connected for business {business_id}: {email}")
        
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
                "filename": receipt.attachment.original_filename,
                "mime_type": receipt.attachment.mime_type,
                "size": receipt.attachment.size,
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
            signed_url = attachment_service.get_signed_url(
                receipt.attachment.storage_path,
                ttl=3600  # 1 hour
            )
        except Exception as e:
            logger.warning(f"Failed to generate signed URL: {e}")
        
        result["attachment"] = {
            "id": receipt.attachment.id,
            "filename": receipt.attachment.original_filename,
            "mime_type": receipt.attachment.mime_type,
            "size": receipt.attachment.size,
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
    
    This fetches new emails that may contain receipts and processes them.
    Returns immediately with status - actual sync happens asynchronously or synchronously
    depending on configuration.
    """
    business_id = get_current_business_id()
    
    # Check Gmail connection
    connection = GmailConnection.query.filter_by(business_id=business_id).first()
    
    if not connection or connection.status != 'connected':
        return jsonify({
            "success": False,
            "error": "Gmail not connected. Please connect your Gmail account first."
        }), 400
    
    # Import sync service
    try:
        from server.services.gmail_sync_service import sync_gmail_receipts
        
        # Run sync synchronously for now (can be made async later)
        result = sync_gmail_receipts(business_id)
        
        # Update last sync time
        connection.last_sync_at = datetime.utcnow()
        if result.get('history_id'):
            connection.last_history_id = result['history_id']
        db.session.commit()
        
        log_audit('sync', 'gmail_receipts', details={'new_receipts': result.get('new_count', 0)})
        
        return jsonify({
            "success": True,
            "message": "Sync completed",
            "new_receipts": result.get('new_count', 0),
            "processed": result.get('processed', 0),
            "skipped": result.get('skipped', 0)
        })
        
    except ImportError:
        logger.warning("Gmail sync service not yet implemented")
        return jsonify({
            "success": False,
            "error": "Gmail sync service not available yet"
        }), 501
    except Exception as e:
        logger.error(f"Sync error: {e}")
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
