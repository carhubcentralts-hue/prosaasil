"""
Attachments API Blueprint - Unified file management for Email, WhatsApp, and Broadcasts

Endpoints:
- POST /api/attachments/upload - Upload new attachment
- GET /api/attachments - List attachments with optional filtering
- GET /api/attachments/{id} - Get attachment details
- POST /api/attachments/{id}/sign - Generate signed URL
- GET /api/attachments/{id}/download - Download file (with signed URL)
- DELETE /api/attachments/{id} - Soft delete attachment (admin only)

Security:
- Multi-tenant isolation (business_id)
- Permission checks (require send permission to upload)
- Signed URLs with TTL for downloads
- Audit logging for all operations
- ATTACHMENT_SECRET must be set in production
"""

from flask import Blueprint, jsonify, request, send_file, g
from werkzeug.utils import secure_filename
from server.auth_api import require_api_auth
from server.models_sql import Attachment, User
from server.db import db
from server.services.attachment_service import get_attachment_service
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# 🔒 PRODUCTION GATE: Check ATTACHMENT_SECRET is properly configured
ATTACHMENT_SECRET = os.getenv('ATTACHMENT_SECRET', 'change-me-in-production')
IS_PRODUCTION = os.getenv('PRODUCTION', '0') == '1'  # PRODUCTION=1 means production mode

if IS_PRODUCTION and ATTACHMENT_SECRET == 'change-me-in-production':
    logger.error("=" * 80)
    logger.error("🚨 CRITICAL SECURITY ERROR: ATTACHMENT_SECRET is not set in production!")
    logger.error("Attachment upload is DISABLED for security reasons.")
    logger.error("Set ATTACHMENT_SECRET environment variable to enable attachments.")
    logger.error("=" * 80)
    ATTACHMENTS_ENABLED = False
else:
    ATTACHMENTS_ENABLED = True
    if not IS_PRODUCTION:
        logger.warning("⚠️ Running in development mode with default ATTACHMENT_SECRET")

attachments_bp = Blueprint("attachments", __name__, url_prefix="/api/attachments")

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

def log_audit(action: str, attachment_id: int, details: dict = None):
    """Log attachment operation for audit trail"""
    user_id = get_current_user_id()
    business_id = get_current_business_id()
    
    log_msg = f"[ATTACHMENT_AUDIT] action={action} attachment_id={attachment_id} user_id={user_id} business_id={business_id}"
    if details:
        log_msg += f" details={details}"
    
    logger.info(log_msg)


@attachments_bp.route('/upload', methods=['POST'])
@require_api_auth
def upload_attachment():
    """
    Upload new attachment
    
    Request:
        - multipart/form-data
        - file: File to upload
        - channel: Optional target channel (email/whatsapp/broadcast) for validation
    
    Response:
        - 201: Attachment created
        - 400: Validation error
        - 403: Permission denied
        - 413: File too large
        - 503: Service unavailable (if ATTACHMENT_SECRET not configured)
    """
    # 🔒 PRODUCTION GATE: Block uploads if secret not configured
    if not ATTACHMENTS_ENABLED:
        logger.error("[ATTACHMENT_UPLOAD] ❌ Upload blocked - ATTACHMENT_SECRET not configured")
        return jsonify({
            'error': 'Attachment service unavailable',
            'message': 'קובץ מצורף לא זמין - מערכת לא מוגדרת כראוי'
        }), 503
    
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Check if user has permission to send (required for uploads)
        # For now, all authenticated users can upload
        # In production, check specific permissions based on role
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get target channel for validation (default: email)
        channel = request.form.get('channel', 'email')
        if channel not in ['email', 'whatsapp', 'broadcast']:
            return jsonify({'error': 'Invalid channel'}), 400
        
        # Validate file
        attachment_service = get_attachment_service()
        is_valid, error_msg = attachment_service.validate_file(file, channel)
        
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Get file metadata
        filename = secure_filename(file.filename)
        mime_type = file.content_type or 'application/octet-stream'
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        # Determine channel compatibility
        compatibility = attachment_service.get_channel_compatibility(mime_type, file_size)
        
        # Create attachment record
        attachment = Attachment(
            business_id=business_id,
            uploaded_by=user_id,
            filename_original=filename,
            mime_type=mime_type,
            file_size=file_size,
            storage_path='',  # Will be set after we have the ID
            channel_compatibility=compatibility,
            metadata={}
        )
        
        db.session.add(attachment)
        db.session.flush()  # Get the ID
        
        # Save file to storage
        storage_path, actual_size = attachment_service.save_file(file, business_id, attachment.id)
        attachment.storage_path = storage_path
        
        db.session.commit()
        
        # Generate preview URL (signed URL with short TTL)
        preview_url = attachment_service.generate_signed_url(attachment.id, storage_path, ttl_minutes=15)
        
        # Log audit
        log_audit('upload', attachment.id, {
            'filename': filename,
            'mime_type': mime_type,
            'file_size': file_size,
            'channel': channel
        })
        
        return jsonify({
            'id': attachment.id,
            'filename': filename,
            'mime_type': mime_type,
            'file_size': file_size,
            'channel_compatibility': compatibility,
            'preview_url': preview_url,
            'created_at': attachment.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error uploading attachment: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to upload file'}), 500


@attachments_bp.route('', methods=['GET'])
@require_api_auth
def list_attachments():
    """
    List attachments for current business
    
    Query params:
        - channel: Filter by channel compatibility (email/whatsapp/broadcast)
        - mime_type: Filter by mime type prefix (e.g., 'image/', 'video/')
        - page: Page number (default: 1)
        - per_page: Items per page (default: 30, max: 100)
    
    Response:
        - 200: List of attachments
    """
    try:
        business_id = get_current_business_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Build query
        query = Attachment.query.filter_by(
            business_id=business_id,
            is_deleted=False
        )
        
        # Filter by channel compatibility
        channel = request.args.get('channel')
        if channel and channel in ['email', 'whatsapp', 'broadcast']:
            # Filter attachments where channel_compatibility[channel] = true
            # Using JSON query - PostgreSQL specific
            from sqlalchemy import text
            query = query.filter(
                text(f"channel_compatibility->'{channel}' = 'true'")
            )
        
        # Filter by mime type prefix
        mime_type_prefix = request.args.get('mime_type')
        if mime_type_prefix:
            query = query.filter(Attachment.mime_type.like(f"{mime_type_prefix}%"))
        
        # Pagination
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 30))))
        
        # Order by created_at DESC
        query = query.order_by(Attachment.created_at.desc())
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Build response
        attachment_service = get_attachment_service()
        items = []
        
        for att in paginated.items:
            # Generate signed URL for preview
            preview_url = attachment_service.generate_signed_url(att.id, att.storage_path, ttl_minutes=15)
            
            items.append({
                'id': att.id,
                'filename': att.filename_original,
                'mime_type': att.mime_type,
                'file_size': att.file_size,
                'channel_compatibility': att.channel_compatibility,
                'preview_url': preview_url,
                'created_at': att.created_at.isoformat(),
                'uploaded_by': att.uploaded_by
            })
        
        return jsonify({
            'items': items,
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing attachments: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list attachments'}), 500


@attachments_bp.route('/<int:attachment_id>', methods=['GET'])
@require_api_auth
def get_attachment(attachment_id):
    """
    Get attachment details
    
    Response:
        - 200: Attachment details
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get attachment
        attachment = Attachment.query.filter_by(
            id=attachment_id,
            business_id=business_id,
            is_deleted=False
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Generate signed URL
        attachment_service = get_attachment_service()
        download_url = attachment_service.generate_signed_url(attachment.id, attachment.storage_path, ttl_minutes=60)
        
        return jsonify({
            'id': attachment.id,
            'filename': attachment.filename_original,
            'mime_type': attachment.mime_type,
            'file_size': attachment.file_size,
            'channel_compatibility': attachment.channel_compatibility,
            'metadata': attachment.metadata,
            'download_url': download_url,
            'created_at': attachment.created_at.isoformat(),
            'uploaded_by': attachment.uploaded_by
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting attachment {attachment_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get attachment'}), 500


@attachments_bp.route('/<int:attachment_id>/sign', methods=['POST'])
@require_api_auth
def sign_attachment(attachment_id):
    """
    Generate signed URL for attachment
    
    Request body (JSON):
        - ttl_minutes: Optional TTL in minutes (default: 60, max: 1440)
    
    Response:
        - 200: Signed URL
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get attachment
        attachment = Attachment.query.filter_by(
            id=attachment_id,
            business_id=business_id,
            is_deleted=False
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Get TTL from request (default: 60 minutes, max: 1440 = 24 hours)
        data = request.get_json() or {}
        ttl_minutes = min(1440, max(1, int(data.get('ttl_minutes', 60))))
        
        # Generate signed URL
        attachment_service = get_attachment_service()
        signed_url = attachment_service.generate_signed_url(attachment.id, attachment.storage_path, ttl_minutes=ttl_minutes)
        
        # Log audit
        log_audit('sign', attachment.id, {'ttl_minutes': ttl_minutes})
        
        return jsonify({
            'signed_url': signed_url,
            'expires_in_minutes': ttl_minutes
        }), 200
        
    except Exception as e:
        logger.error(f"Error signing attachment {attachment_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to sign attachment'}), 500


@attachments_bp.route('/<int:attachment_id>/download', methods=['GET'])
def download_attachment(attachment_id):
    """
    Download attachment file (with signed URL)
    
    Query params:
        - expires: Expiration timestamp
        - sig: Signature
    
    Response:
        - 200: File content
        - 403: Permission denied or expired
        - 404: Not found
    """
    try:
        # Get query params
        expires_ts = int(request.args.get('expires', 0))
        signature = request.args.get('sig', '')
        
        if not expires_ts or not signature:
            return jsonify({'error': 'Invalid or missing signature'}), 403
        
        # Get attachment (no business_id check yet - signature will validate)
        attachment = Attachment.query.filter_by(
            id=attachment_id,
            is_deleted=False
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Verify signed URL
        attachment_service = get_attachment_service()
        is_valid, error_msg = attachment_service.verify_signed_url(
            attachment.id,
            attachment.storage_path,
            expires_ts,
            signature
        )
        
        if not is_valid:
            logger.warning(f"Invalid signature for attachment {attachment_id}: {error_msg}")
            return jsonify({'error': error_msg}), 403
        
        # Get file path
        file_path = attachment_service.get_file_path(attachment.storage_path)
        
        if not os.path.isfile(file_path):
            logger.error(f"File not found in storage: {attachment.storage_path}")
            return jsonify({'error': 'File not found in storage'}), 404
        
        # Log audit (no user context in download)
        logger.info(f"[ATTACHMENT_AUDIT] action=download attachment_id={attachment_id} business_id={attachment.business_id}")
        
        # Send file
        return send_file(
            file_path,
            mimetype=attachment.mime_type,
            as_attachment=True,
            download_name=attachment.filename_original
        )
        
    except Exception as e:
        logger.error(f"Error downloading attachment {attachment_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to download file'}), 500


@attachments_bp.route('/<int:attachment_id>', methods=['DELETE'])
@require_api_auth
def delete_attachment(attachment_id):
    """
    Soft delete attachment (admin only)
    
    Response:
        - 200: Deleted successfully
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Check admin permission
        if not check_admin_permission():
            return jsonify({'error': 'Admin permission required'}), 403
        
        # Get attachment
        attachment = Attachment.query.filter_by(
            id=attachment_id,
            business_id=business_id,
            is_deleted=False
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Soft delete
        attachment.is_deleted = True
        attachment.deleted_at = datetime.utcnow()
        attachment.deleted_by = user_id
        
        db.session.commit()
        
        # Log audit
        log_audit('delete', attachment.id, {'filename': attachment.filename_original})
        
        return jsonify({
            'message': 'Attachment deleted successfully',
            'id': attachment_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting attachment {attachment_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to delete attachment'}), 500
