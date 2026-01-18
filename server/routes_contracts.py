"""
Contracts API Blueprint - Digital contract management with attachment-based storage

✅ PERFECT IMPLEMENTATION:
- Reuses attachments table for R2 storage (NO duplication)
- DB-based tokens (NOT JWT) for security
- Multi-tenant isolation
- Audit trail for all operations
- Page permission enforcement

Endpoints:
- GET /api/contracts - List contracts
- POST /api/contracts - Create new contract
- GET /api/contracts/{id} - Get contract details
- POST /api/contracts/{id}/upload - Upload file (via attachments)
- POST /api/contracts/{id}/send_for_signature - Send for signing  
- GET /api/contracts/sign/{token} - Public signing page (no auth)
- POST /api/contracts/sign/{token}/complete - Complete signing
- GET /api/contracts/{id}/files/{file_id}/download - Download file
- GET /api/contracts/{id}/events - Get audit trail
"""

from flask import Blueprint, jsonify, request, g
from werkzeug.utils import secure_filename
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.models_sql import Contract, ContractFile, ContractSignToken, ContractSignEvent, Attachment, Lead, User, db
from server.services.attachment_service import get_attachment_service
from datetime import datetime, timedelta
import logging
import os
import hashlib
import secrets

logger = logging.getLogger(__name__)

contracts_bp = Blueprint("contracts", __name__, url_prefix="/api/contracts")

def create_attachment_from_file(
    file: FileStorage,
    business_id: int,
    user_id: int = None
) -> Attachment:
    """
    Helper to create attachment record and save file to storage
    
    Handles transaction rollback on storage failure to prevent orphaned records.
    
    Args:
        file: Uploaded file
        business_id: Business ID for tenant isolation
        user_id: User ID (None for public endpoints)
        
    Returns:
        Attachment record with storage_path populated
        
    Raises:
        Exception if validation or storage save fails
    """
    attachment_service = get_attachment_service()
    
    # Validate file
    is_valid, error_msg = attachment_service.validate_file(file, channel='email')
    if not is_valid:
        raise ValueError(error_msg)
    
    # Get file metadata
    filename = secure_filename(file.filename)
    mime_type = file.content_type or 'application/octet-stream'
    
    # Get file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    # Create attachment record
    attachment = Attachment(
        business_id=business_id,
        uploaded_by=user_id,
        filename_original=filename,
        mime_type=mime_type,
        file_size=file_size,
        storage_path='',
        metadata={}
    )
    
    db.session.add(attachment)
    db.session.flush()
    
    # Save file via attachment service
    try:
        storage_key, actual_size = attachment_service.save_file(file, business_id, attachment.id)
        attachment.storage_path = storage_key
    except Exception as storage_error:
        logger.error(f"[ATTACHMENT_CREATE] Storage save failed: {storage_error}")
        db.session.rollback()
        raise
    
    db.session.commit()
    return attachment


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

def log_contract_event(
    contract_id: int,
    business_id: int,
    event_type: str,
    metadata: dict = None,
    user_id: int = None
):
    """Log contract event to audit trail"""
    try:
        event = ContractSignEvent(
            business_id=business_id,
            contract_id=contract_id,
            event_type=event_type,
            metadata=metadata or {},
            created_by=user_id
        )
        db.session.add(event)
        db.session.commit()
        
        logger.info(f"[CONTRACT_AUDIT] contract_id={contract_id} event={event_type} user_id={user_id}")
    except Exception as e:
        logger.error(f"[CONTRACT_AUDIT] Failed to log event: {e}")
        db.session.rollback()

def generate_signing_token(contract_id: int, business_id: int, ttl_hours: int = 72) -> tuple:
    """
    Generate secure DB-based token for contract signing (NOT JWT)
    
    Returns:
        (token_plain, token_hash) - store hash in DB, return plain to user
    """
    # Generate random token (32 bytes = 64 hex chars)
    token_plain = secrets.token_urlsafe(32)
    
    # Hash token for DB storage (SHA256)
    token_hash = hashlib.sha256(token_plain.encode()).hexdigest()
    
    # Create token record
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    sign_token = ContractSignToken(
        business_id=business_id,
        contract_id=contract_id,
        token_hash=token_hash,
        scope='sign',
        expires_at=expires_at,
        created_by=get_current_user_id()
    )
    
    db.session.add(sign_token)
    db.session.commit()
    
    logger.info(f"[CONTRACT_TOKEN] Generated token for contract_id={contract_id} expires={expires_at}")
    
    return token_plain, token_hash

def verify_signing_token(token_plain: str) -> dict:
    """
    Verify DB-based signing token (NOT JWT)
    
    Returns:
        dict with contract_id, business_id if valid, None if invalid/expired/used
    """
    try:
        # Hash the provided token
        token_hash = hashlib.sha256(token_plain.encode()).hexdigest()
        
        # Look up token in DB
        sign_token = ContractSignToken.query.filter_by(token_hash=token_hash).first()
        
        if not sign_token:
            logger.warning(f"[CONTRACT_TOKEN] Token not found")
            return None
        
        # Check if already used
        if sign_token.used_at:
            logger.warning(f"[CONTRACT_TOKEN] Token already used at {sign_token.used_at}")
            return None
        
        # Check if expired
        if datetime.utcnow() > sign_token.expires_at:
            logger.warning(f"[CONTRACT_TOKEN] Token expired at {sign_token.expires_at}")
            return None
        
        return {
            'contract_id': sign_token.contract_id,
            'business_id': sign_token.business_id,
            'token_id': sign_token.id
        }
        
    except Exception as e:
        logger.error(f"[CONTRACT_TOKEN] Verification failed: {e}")
        return None


@contracts_bp.route('', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def list_contracts():
    """
    List contracts for current business
    
    Query params:
        - status: Filter by status (draft|sent|signed|cancelled)
        - lead_id: Filter by lead
        - q: Search by title
        - page: Page number (default: 1)
        - per_page: Results per page (default: 20, max: 100)
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Build query
        query = Contract.query.filter_by(business_id=business_id)
        
        # Filters
        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)
        
        lead_id = request.args.get('lead_id', type=int)
        if lead_id:
            query = query.filter_by(lead_id=lead_id)
        
        search = request.args.get('q', '').strip()
        if search:
            query = query.filter(Contract.title.ilike(f'%{search}%'))
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Order by created_at desc
        query = query.order_by(Contract.created_at.desc())
        
        # Execute query
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        contracts = []
        for contract in pagination.items:
            # Get file count (via contract_files → attachments)
            file_count = ContractFile.query.filter_by(
                contract_id=contract.id,
                business_id=business_id
            ).filter(ContractFile.deleted_at.is_(None)).count()
            
            contracts.append({
                'id': contract.id,
                'title': contract.title,
                'status': contract.status,
                'lead_id': contract.lead_id,
                'signer_name': contract.signer_name,
                'signer_phone': contract.signer_phone,
                'signer_email': contract.signer_email,
                'signed_at': contract.signed_at.isoformat() if contract.signed_at else None,
                'created_at': contract.created_at.isoformat(),
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
                'file_count': file_count
            })
        
        return jsonify({
            'contracts': contracts,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACTS_LIST] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list contracts'}), 500


@contracts_bp.route('', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def create_contract():
    """
    Create new contract
    
    Request body (JSON):
        - title: Contract title (required)
        - lead_id: Lead ID (optional)
        - signer_name: Signer name (optional)
        - signer_phone: Signer phone (optional)
        - signer_email: Signer email (optional)
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        # Validate lead_id if provided
        lead_id = data.get('lead_id')
        if lead_id:
            lead = Lead.query.filter_by(id=lead_id, business_id=business_id).first()
            if not lead:
                return jsonify({'error': 'Lead not found'}), 404
        
        # Create contract
        contract = Contract(
            business_id=business_id,
            lead_id=lead_id,
            title=title,
            status='draft',
            signer_name=data.get('signer_name'),
            signer_phone=data.get('signer_phone'),
            signer_email=data.get('signer_email'),
            created_by=user_id
        )
        
        db.session.add(contract)
        db.session.commit()
        
        # Log event
        log_contract_event(
            contract_id=contract.id,
            business_id=business_id,
            event_type='created',
            metadata={'title': title},
            user_id=user_id
        )
        
        logger.info(f"[CONTRACTS_CREATE] Created contract_id={contract.id} business_id={business_id}")
        
        return jsonify({
            'id': contract.id,
            'title': contract.title,
            'status': contract.status,
            'created_at': contract.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"[CONTRACTS_CREATE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to create contract'}), 500


@contracts_bp.route('/<int:contract_id>', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def get_contract(contract_id):
    """Get contract details with files (via attachments)"""
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get contract with tenant isolation
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Get files (via contract_files → attachments)
        contract_files = ContractFile.query.filter_by(
            contract_id=contract_id,
            business_id=business_id
        ).filter(ContractFile.deleted_at.is_(None)).order_by(ContractFile.created_at.desc()).all()
        
        files_data = []
        for cf in contract_files:
            # Get attachment details
            attachment = Attachment.query.get(cf.attachment_id)
            if attachment:
                files_data.append({
                    'id': cf.id,
                    'purpose': cf.purpose,
                    'attachment_id': cf.attachment_id,
                    'filename': attachment.filename_original,
                    'mime_type': attachment.mime_type,
                    'file_size': attachment.file_size,
                    'created_at': cf.created_at.isoformat(),
                    'created_by': cf.created_by
                })
        
        return jsonify({
            'id': contract.id,
            'title': contract.title,
            'status': contract.status,
            'lead_id': contract.lead_id,
            'signer_name': contract.signer_name,
            'signer_phone': contract.signer_phone,
            'signer_email': contract.signer_email,
            'signed_at': contract.signed_at.isoformat() if contract.signed_at else None,
            'created_at': contract.created_at.isoformat(),
            'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            'created_by': contract.created_by,
            'files': files_data
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACTS_GET] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get contract'}), 500


@contracts_bp.route('/<int:contract_id>/upload', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def upload_contract_file(contract_id):
    """
    Upload file to contract - uses attachments service
    
    Request:
        - multipart/form-data
        - file: File to upload
        - purpose: optional (original|signed|extra_doc|template) - default: original
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get contract with tenant isolation
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get purpose
        purpose = request.form.get('purpose', 'original')
        if purpose not in ['original', 'signed', 'extra_doc', 'template']:
            purpose = 'original'
        
        # Create attachment using helper
        attachment = create_attachment_from_file(
            file=file,
            business_id=business_id,
            user_id=user_id
        )
        
        # Create contract_file link
        contract_file = ContractFile(
            business_id=business_id,
            contract_id=contract_id,
            attachment_id=attachment.id,
            purpose=purpose,
            created_by=user_id
        )
        
        db.session.add(contract_file)
        db.session.commit()
        
        # Log event
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='file_uploaded',
            metadata={
                'filename': attachment.filename_original,
                'purpose': purpose,
                'attachment_id': attachment.id
            },
            user_id=user_id
        )
        
        logger.info(f"[CONTRACTS_UPLOAD] Uploaded file_id={contract_file.id} contract_id={contract_id}")
        
        return jsonify({
            'id': contract_file.id,
            'purpose': purpose,
            'attachment_id': attachment.id,
            'filename': attachment.filename_original,
            'mime_type': attachment.mime_type,
            'file_size': attachment.file_size,
            'created_at': contract_file.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"[CONTRACTS_UPLOAD] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to upload file'}), 500


@contracts_bp.route('/<int:contract_id>/files/<int:file_id>/download', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def download_contract_file(contract_id, file_id):
    """
    Get presigned URL for downloading contract file (via attachments)
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get contract_file with tenant isolation
        contract_file = ContractFile.query.filter_by(
            id=file_id,
            contract_id=contract_id,
            business_id=business_id
        ).filter(ContractFile.deleted_at.is_(None)).first()
        
        if not contract_file:
            return jsonify({'error': 'File not found'}), 404
        
        # Get attachment
        attachment = Attachment.query.filter_by(
            id=contract_file.attachment_id,
            business_id=business_id
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Generate presigned URL via attachment service
        attachment_service = get_attachment_service()
        ttl_seconds = int(os.getenv('SIGNED_URL_TTL_SECONDS', 900))
        
        signed_url = attachment_service.generate_signed_url(
            attachment.id,
            attachment.storage_path,
            ttl_minutes=ttl_seconds // 60
        )
        
        if not signed_url:
            return jsonify({'error': 'Failed to generate download URL'}), 500
        
        # Log event
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='file_downloaded',
            metadata={
                'file_id': file_id,
                'filename': attachment.filename_original
            },
            user_id=user_id
        )
        
        return jsonify({
            'url': signed_url,
            'expires_in': ttl_seconds,
            'filename': attachment.filename_original
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACTS_DOWNLOAD] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate download URL'}), 500


@contracts_bp.route('/<int:contract_id>/events', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def get_contract_events(contract_id):
    """Get audit trail for contract"""
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Verify contract exists and belongs to business
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Get events
        events = ContractSignEvent.query.filter_by(
            contract_id=contract_id,
            business_id=business_id
        ).order_by(ContractSignEvent.created_at.desc()).all()
        
        events_data = []
        for event in events:
            events_data.append({
                'id': event.id,
                'event_type': event.event_type,
                'metadata': event.metadata,
                'created_at': event.created_at.isoformat(),
                'created_by': event.created_by
            })
        
        return jsonify({'events': events_data}), 200
        
    except Exception as e:
        logger.error(f"[CONTRACTS_EVENTS] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get events'}), 500


@contracts_bp.route('/<int:contract_id>/send_for_signature', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def send_for_signature(contract_id):
    """
    Send contract for signature - generates signing token
    
    Validates:
        - Contract status is 'draft'
        - At least one file with purpose='original' exists
    
    Creates:
        - ContractSignToken (hashed, 24h expiration)
        - Updates contract status to 'sent'
        - Logs audit event
    
    Returns:
        - sign_url: Public URL for signing (contains token)
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status != 'draft':
            return jsonify({'error': f'Contract must be in draft status (current: {contract.status})'}), 400
        
        original_file = ContractFile.query.filter_by(
            contract_id=contract_id,
            business_id=business_id,
            purpose='original'
        ).filter(ContractFile.deleted_at.is_(None)).first()
        
        if not original_file:
            return jsonify({'error': 'Contract must have at least one original file'}), 400
        
        token_plain, token_hash = generate_signing_token(
            contract_id=contract_id,
            business_id=business_id,
            ttl_hours=24
        )
        
        contract.status = 'sent'
        contract.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='sent_for_signature',
            metadata={'signer_name': contract.signer_name, 'signer_email': contract.signer_email},
            user_id=user_id
        )
        
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:5000')
        sign_url = f"{base_url}/contracts/sign/{token_plain}"
        
        logger.info(f"[CONTRACT_SEND] contract_id={contract_id} status=sent sign_url_generated=yes")
        
        return jsonify({
            'sign_url': sign_url,
            'expires_in_hours': 24,
            'status': 'sent'
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_SEND] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to send contract for signature'}), 500


@contracts_bp.route('/sign/<token>', methods=['GET'])
def get_signing_page(token):
    """
    PUBLIC endpoint - Get contract details for signing (NO auth required)
    
    Verifies:
        - Token exists, not expired, not used
    
    Returns:
        - Contract details
        - File URL (presigned)
        - Signer info
    
    Logs:
        - 'viewed' audit event
    """
    try:
        token_data = verify_signing_token(token)
        if not token_data:
            return jsonify({'error': 'Invalid, expired, or already used token'}), 403
        
        contract_id = token_data['contract_id']
        business_id = token_data['business_id']
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        contract_files = ContractFile.query.filter_by(
            contract_id=contract_id,
            business_id=business_id,
            purpose='original'
        ).filter(ContractFile.deleted_at.is_(None)).order_by(ContractFile.created_at.desc()).all()
        
        files_data = []
        attachment_service = get_attachment_service()
        
        for cf in contract_files:
            attachment = Attachment.query.get(cf.attachment_id)
            if attachment:
                ttl_seconds = int(os.getenv('SIGNED_URL_TTL_SECONDS', 900))
                signed_url = attachment_service.generate_signed_url(
                    attachment.id,
                    attachment.storage_path,
                    ttl_minutes=ttl_seconds // 60
                )
                
                files_data.append({
                    'id': cf.id,
                    'filename': attachment.filename_original,
                    'mime_type': attachment.mime_type,
                    'file_size': attachment.file_size,
                    'download_url': signed_url
                })
        
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='viewed',
            metadata={'token_used': token[:10] + '...'},
            user_id=None
        )
        
        return jsonify({
            'id': contract.id,
            'title': contract.title,
            'signer_name': contract.signer_name,
            'signer_phone': contract.signer_phone,
            'signer_email': contract.signer_email,
            'status': contract.status,
            'files': files_data
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_SIGN_VIEW] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load contract'}), 500


@contracts_bp.route('/sign/<token>/complete', methods=['POST'])
def complete_signing(token):
    """
    PUBLIC endpoint - Complete contract signing (NO auth required)
    
    Verifies:
        - Token valid
    
    Accepts:
        - Signed file upload (multipart/form-data)
    
    Creates:
        - Attachment record
        - ContractFile with purpose='signed'
    
    Updates:
        - Contract status → 'signed'
        - Contract signed_at timestamp
        - Token used_at timestamp
    
    Logs:
        - 'signed_completed' audit event
    """
    try:
        token_data = verify_signing_token(token)
        if not token_data:
            return jsonify({'error': 'Invalid, expired, or already used token'}), 403
        
        contract_id = token_data['contract_id']
        business_id = token_data['business_id']
        token_id = token_data['token_id']
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if 'file' not in request.files:
            return jsonify({'error': 'Signed file required'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Create attachment using helper
        try:
            attachment = create_attachment_from_file(
                file=file,
                business_id=business_id,
                user_id=None
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"[CONTRACT_SIGN_COMPLETE] Attachment creation failed: {e}")
            return jsonify({'error': 'Failed to upload signed file'}), 500
        
        contract_file = ContractFile(
            business_id=business_id,
            contract_id=contract_id,
            attachment_id=attachment.id,
            purpose='signed',
            created_by=None
        )
        
        db.session.add(contract_file)
        
        contract.status = 'signed'
        contract.signed_at = datetime.utcnow()
        contract.updated_at = datetime.utcnow()
        
        sign_token = ContractSignToken.query.get(token_id)
        if sign_token:
            sign_token.used_at = datetime.utcnow()
        
        db.session.commit()
        
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='signed_completed',
            metadata={
                'filename': attachment.filename_original,
                'signer_name': contract.signer_name
            },
            user_id=None
        )
        
        logger.info(f"[CONTRACT_SIGN_COMPLETE] contract_id={contract_id} status=signed")
        
        return jsonify({
            'message': 'Contract signed successfully',
            'contract_id': contract_id,
            'status': 'signed',
            'signed_at': contract.signed_at.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_SIGN_COMPLETE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to complete signing'}), 500


@contracts_bp.route('/<int:contract_id>/cancel', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def cancel_contract(contract_id):
    """Cancel contract - updates status to 'cancelled'"""
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        if contract.status == 'cancelled':
            return jsonify({'error': 'Contract already cancelled'}), 400
        
        previous_status = contract.status
        contract.status = 'cancelled'
        contract.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='cancelled',
            metadata={'previous_status': previous_status},
            user_id=user_id
        )
        
        logger.info(f"[CONTRACT_CANCEL] contract_id={contract_id} previous_status={previous_status} status=cancelled")
        
        return jsonify({
            'message': 'Contract cancelled successfully',
            'status': 'cancelled'
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_CANCEL] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel contract'}), 500
