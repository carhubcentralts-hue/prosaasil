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

from __future__ import annotations

from flask import Blueprint, jsonify, request, g, Response
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.models_sql import Contract, ContractFile, ContractSignToken, ContractSignEvent, Attachment, Lead, User, db
from server.services.attachment_service import get_attachment_service
from datetime import datetime, timedelta
import logging
import os
import io
import hashlib
import secrets

logger = logging.getLogger(__name__)

contracts_bp = Blueprint("contracts", __name__, url_prefix="/api/contracts")

# Constants
CONTRACT_FILE_PURPOSE_ORIGINAL = 'original'
CONTRACT_FILE_PURPOSE_SIGNED = 'signed'

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
        meta_json={}
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
            event_metadata=metadata or {},
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
    Create new contract - supports both JSON and FormData with multiple files
    
    Request body (JSON):
        - title: Contract title (required)
        - lead_id: Lead ID (optional)
        - customer_id: Customer ID (optional, legacy)
        - signer_name: Signer name (optional)
        - signer_phone: Signer phone (optional)
        - signer_email: Signer email (optional)
    
    Request body (FormData):
        - title: Contract title (required)
        - type: Contract type (optional)
        - lead_id: Lead ID (optional)
        - signer_name: Signer name (optional)
        - signer_phone: Signer phone (optional)
        - signer_email: Signer email (optional)
        - files: Multiple files to upload (optional)
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Detect if this is JSON or FormData
        is_form_data = request.content_type and 'multipart/form-data' in request.content_type
        
        if is_form_data:
            # Handle FormData (from LeadDetailPage with file uploads)
            title = request.form.get('title', '').strip()
            lead_id = request.form.get('lead_id', type=int)
            customer_id = request.form.get('customer_id', type=int)
            signer_name = request.form.get('signer_name', '').strip()
            signer_phone = request.form.get('signer_phone', '').strip()
            signer_email = request.form.get('signer_email', '').strip()
        else:
            # Handle JSON (from CreateContractModal)
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body required'}), 400
            
            title = data.get('title', '').strip()
            lead_id = data.get('lead_id')
            customer_id = data.get('customer_id')
            signer_name = data.get('signer_name')
            signer_phone = data.get('signer_phone')
            signer_email = data.get('signer_email')
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        # Validate lead_id if provided
        if lead_id:
            lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id).first()
            if not lead:
                return jsonify({'error': 'Lead not found'}), 404
        
        # Create contract
        contract = Contract(
            business_id=business_id,
            lead_id=lead_id,
            customer_id=customer_id,  # Legacy support
            title=title,
            status='draft',
            signer_name=signer_name if signer_name else None,
            signer_phone=signer_phone if signer_phone else None,
            signer_email=signer_email if signer_email else None,
            created_by=user_id
        )
        
        db.session.add(contract)
        db.session.flush()  # Get contract.id before processing files
        
        # Process uploaded files if FormData
        uploaded_files = []
        if is_form_data and 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    try:
                        # Create attachment
                        attachment = create_attachment_from_file(
                            file=file,
                            business_id=business_id,
                            user_id=user_id
                        )
                        
                        # Mark attachment as compatible with contracts channel
                        if attachment.channel_compatibility:
                            attachment.channel_compatibility['contracts'] = True
                        else:
                            attachment.channel_compatibility = {'contracts': True, 'email': True}
                        
                        # Create contract_file link
                        contract_file = ContractFile(
                            business_id=business_id,
                            contract_id=contract.id,
                            attachment_id=attachment.id,
                            purpose='original',
                            created_by=user_id
                        )
                        
                        db.session.add(contract_file)
                        uploaded_files.append({
                            'id': contract_file.id,
                            'attachment_id': attachment.id,
                            'filename': attachment.filename_original,
                            'mime_type': attachment.mime_type,
                            'file_size': attachment.file_size
                        })
                        
                        # Log file upload event
                        log_contract_event(
                            contract_id=contract.id,
                            business_id=business_id,
                            event_type='file_uploaded',
                            metadata={
                                'filename': attachment.filename_original,
                                'purpose': 'original',
                                'attachment_id': attachment.id
                            },
                            user_id=user_id
                        )
                        
                    except (ValueError, IOError) as file_error:
                        logger.warning(f"[CONTRACTS_CREATE] Failed to upload file {file.filename}: {file_error}")
                        # Continue with other files, don't fail the entire contract creation
        
        db.session.commit()
        
        # Log contract creation event
        log_contract_event(
            contract_id=contract.id,
            business_id=business_id,
            event_type='created',
            metadata={'title': title, 'files_count': len(uploaded_files)},
            user_id=user_id
        )
        
        logger.info(f"[CONTRACTS_CREATE] Created contract_id={contract.id} business_id={business_id} files_count={len(uploaded_files)}")
        
        response_data = {
            'success': True,
            'contract_id': contract.id,
            'id': contract.id,
            'title': contract.title,
            'status': contract.status,
            'lead_id': contract.lead_id,
            'created_at': contract.created_at.isoformat()
        }
        
        if uploaded_files:
            response_data['files'] = uploaded_files
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"[CONTRACTS_CREATE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to create contract'}), 500


@contracts_bp.route('/upload', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def create_contract_with_file():
    """
    Create new contract with file upload in one step
    
    Request:
        - multipart/form-data
        - file: PDF/DOCX file to upload (required)
        - title: Contract title (optional, defaults to filename)
        - lead_id: Lead ID (optional)
        - customer_id: Customer ID (optional, legacy)
        - signer_name: Signer name (optional)
        - signer_phone: Signer phone (optional)
        - signer_email: Signer email (optional)
    
    Response:
        - 201: Contract created with file attached
        - 400: Validation error
        - 403: Permission denied
        - 500: Server error
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get title (default to filename if not provided)
        title = request.form.get('title', '').strip()
        if not title:
            title = secure_filename(file.filename)
            # Remove extension from title
            if '.' in title:
                title = title.rsplit('.', 1)[0]
        
        # Validate lead_id if provided
        lead_id = request.form.get('lead_id', type=int)
        if lead_id:
            lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id).first()
            if not lead:
                return jsonify({'error': 'Lead not found'}), 404
        
        # Create contract first
        contract = Contract(
            business_id=business_id,
            lead_id=lead_id,
            customer_id=request.form.get('customer_id', type=int),  # Legacy support
            title=title,
            status='draft',
            signer_name=request.form.get('signer_name'),
            signer_phone=request.form.get('signer_phone'),
            signer_email=request.form.get('signer_email'),
            created_by=user_id
        )
        
        db.session.add(contract)
        db.session.flush()  # Get contract.id without committing yet
        
        # Create attachment using helper
        try:
            attachment = create_attachment_from_file(
                file=file,
                business_id=business_id,
                user_id=user_id
            )
        except ValueError as ve:
            db.session.rollback()
            return jsonify({'error': str(ve)}), 400
        
        # Mark attachment as compatible with contracts channel
        if attachment.channel_compatibility:
            attachment.channel_compatibility['contracts'] = True
        else:
            attachment.channel_compatibility = {'contracts': True, 'email': True}
        
        # Create contract_file link
        contract_file = ContractFile(
            business_id=business_id,
            contract_id=contract.id,
            attachment_id=attachment.id,
            purpose='original',
            created_by=user_id
        )
        
        db.session.add(contract_file)
        db.session.commit()
        
        # Log events
        log_contract_event(
            contract_id=contract.id,
            business_id=business_id,
            event_type='created',
            metadata={'title': title},
            user_id=user_id
        )
        
        log_contract_event(
            contract_id=contract.id,
            business_id=business_id,
            event_type='file_uploaded',
            metadata={
                'filename': attachment.filename_original,
                'purpose': 'original',
                'attachment_id': attachment.id
            },
            user_id=user_id
        )
        
        logger.info(f"[CONTRACTS_CREATE_UPLOAD] Created contract_id={contract.id} with file_id={contract_file.id}")
        
        return jsonify({
            'id': contract.id,
            'title': contract.title,
            'status': contract.status,
            'lead_id': contract.lead_id,
            'file': {
                'id': contract_file.id,
                'attachment_id': attachment.id,
                'filename': attachment.filename_original,
                'mime_type': attachment.mime_type,
                'file_size': attachment.file_size
            },
            'created_at': contract.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"[CONTRACTS_CREATE_UPLOAD] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to create contract with file'}), 500


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
            ttl_minutes=ttl_seconds // 60,
            mime_type=attachment.mime_type,
            filename=attachment.filename_original
        )
        
        if not signed_url:
            return jsonify({'error': 'Failed to generate download URL'}), 500
        
        # Log event (best effort - don't fail if audit logging fails)
        try:
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
        except Exception as audit_err:
            # Don't fail download if audit logging fails
            logger.warning(f"[CONTRACTS_DOWNLOAD] Audit logging failed: {audit_err}")
        
        return jsonify({
            'url': signed_url,
            'expires_in': ttl_seconds,
            'filename': attachment.filename_original
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACTS_DOWNLOAD] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate download URL'}), 500


@contracts_bp.route('/<int:contract_id>/pdf', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def stream_contract_pdf(contract_id):
    """
    Stream PDF for contract - for iframe/PDF.js viewers
    
    This endpoint streams the PDF directly to the browser with proper headers
    for inline display. It requires authentication and enforces tenant isolation.
    
    Returns:
        PDF file stream with application/pdf mime type and inline disposition
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        logger.info(f"[CONTRACTS_PDF_STREAM] Request for contract_id={contract_id}, business_id={business_id}, user_id={user_id}")
        
        if not business_id:
            logger.warning(f"[CONTRACTS_PDF_STREAM] Missing business_id for contract {contract_id}")
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Verify contract exists and belongs to business
        contract = Contract.query.filter_by(
            id=contract_id,
            business_id=business_id
        ).first()
        
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Get the first PDF file (original purpose)
        contract_file = ContractFile.query.filter_by(
            contract_id=contract_id,
            business_id=business_id,
            purpose=CONTRACT_FILE_PURPOSE_ORIGINAL
        ).filter(ContractFile.deleted_at.is_(None)).first()
        
        if not contract_file:
            return jsonify({'error': 'No PDF file found for this contract'}), 404
        
        # Get attachment
        attachment = Attachment.query.filter_by(
            id=contract_file.attachment_id,
            business_id=business_id
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        # Verify it's a PDF
        if attachment.mime_type != 'application/pdf':
            return jsonify({'error': 'File is not a PDF'}), 400
        
        # Get file bytes from storage
        attachment_service = get_attachment_service()
        filename, mime_type, file_bytes = attachment_service.open_file(
            attachment.storage_path,
            filename=attachment.filename_original,
            mime_type=attachment.mime_type
        )
        
        logger.info(f"[CONTRACTS_PDF_STREAM] Successfully loaded PDF: contract_id={contract_id}, filename={filename}, size={len(file_bytes)} bytes")
        
        # Log event (best effort - don't fail if audit logging fails)
        try:
            log_contract_event(
                contract_id=contract_id,
                business_id=business_id,
                event_type='file_viewed',
                metadata={
                    'file_id': contract_file.id,
                    'filename': filename
                },
                user_id=user_id
            )
        except Exception as audit_err:
            # Don't fail PDF viewing if audit logging fails
            logger.warning(f"[CONTRACTS_PDF_STREAM] Audit logging failed: {audit_err}")
        
        # Return PDF stream with proper headers for inline viewing
        # Including Accept-Ranges for browser PDF viewers to work properly
        return Response(
            io.BytesIO(file_bytes),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'inline; filename="contract.pdf"',
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'X-Content-Type-Options': 'nosniff',
                'Content-Length': str(len(file_bytes))
            }
        )
        
    except FileNotFoundError as e:
        logger.error(f"[CONTRACTS_PDF_STREAM] File not found: {e}")
        return jsonify({'error': 'PDF file not found in storage'}), 404
    except Exception as e:
        logger.error(f"[CONTRACTS_PDF_STREAM] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to stream PDF'}), 500


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
                'metadata': event.event_metadata,
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
        
        # ✅ FIX (Problem 3): Use PUBLIC_BASE_URL instead of localhost
        from server.utils.url_builder import public_url
        sign_url = public_url(f"/contracts/sign/{token_plain}")
        
        logger.info(f"[CONTRACT_SEND] contract_id={contract_id} status=sent sign_url={sign_url}")
        
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
        
        # ✅ Generate download URL for signed document
        attachment_service = get_attachment_service()
        signed_document_url = None
        try:
            signed_document_url = attachment_service.generate_signed_url(
                attachment.storage_path,
                expires_in=86400  # 24 hours
            )
        except Exception as url_err:
            logger.warning(f"[CONTRACT_SIGN_COMPLETE] Could not generate signed URL: {url_err}")
        
        return jsonify({
            'message': 'Contract signed successfully',
            'contract_id': contract_id,
            'status': 'signed',
            'signed_at': contract.signed_at.isoformat(),
            'signed_document_url': signed_document_url,
            'signer_name': contract.signer_name
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_SIGN_COMPLETE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to complete signing'}), 500


@contracts_bp.route('/sign/<token>/embed-signature', methods=['POST'])
def embed_signature_in_pdf(token):
    """
    PUBLIC endpoint - Embed signature(s) into PDF document (NO auth required)
    
    Supports two modes:
    1. New mode (with pre-marked fields): Send single signature + signer name, 
       signatures are automatically placed in all pre-marked areas
    2. Legacy mode (manual placements): Send signature placements array
    
    Request body (JSON):
        Mode 1 (with pre-marked fields):
            - file_id: ID of the original PDF file
            - signature_data: Base64 encoded PNG signature image (single signature)
            - signer_name: Name of the signer
        
        Mode 2 (legacy - manual placements):
            - file_id: ID of the original PDF file
            - signatures: Array of signature placements
                - page_number: 0-indexed page number
                - x: X coordinate (from left, in PDF points)
                - y: Y coordinate (from bottom, in PDF points)
                - width: Signature width in PDF points
                - height: Signature height in PDF points
                - signature_data: Base64 encoded PNG signature image
            - signer_name: Name of the signer
    
    Returns:
        - Signed PDF saved as attachment
        - Download URL for the signed document
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
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        file_id = data.get('file_id')
        signer_name = data.get('signer_name', contract.signer_name or 'Unknown')
        
        if not file_id:
            return jsonify({'error': 'file_id is required'}), 400
        
        # Get the original PDF file
        contract_file = ContractFile.query.filter_by(
            id=file_id,
            contract_id=contract_id,
            business_id=business_id
        ).filter(ContractFile.deleted_at.is_(None)).first()
        
        if not contract_file:
            return jsonify({'error': 'File not found'}), 404
        
        attachment = Attachment.query.get(contract_file.attachment_id)
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        if attachment.mime_type != 'application/pdf':
            return jsonify({'error': 'Only PDF files can be signed with embedded signatures'}), 400
        
        # Download the original PDF
        attachment_service = get_attachment_service()
        try:
            filename, mime_type, pdf_data = attachment_service.open_file(
                attachment.storage_path,
                filename=attachment.filename_original,
                mime_type=attachment.mime_type
            )
        except Exception as download_err:
            logger.error(f"[CONTRACT_EMBED_SIGN] Failed to download PDF: {download_err}")
            return jsonify({'error': 'Failed to load original document'}), 500
        
        # Import PDF signing service
        from server.services.pdf_signing_service import SignaturePlacement, embed_signatures_in_pdf, get_pdf_info
        import base64
        
        # Determine which mode: pre-marked fields or manual placements
        signatures_data = data.get('signatures', [])
        signature_data_single = data.get('signature_data')
        
        signature_placements = []
        
        if signature_data_single and not signatures_data:
            # NEW MODE: Single signature with pre-marked fields
            logger.info(f"[CONTRACT_EMBED_SIGN] Using pre-marked signature fields mode")
            
            # Decode the single signature image
            try:
                sig_image_b64 = signature_data_single
                if sig_image_b64.startswith('data:'):
                    sig_image_b64 = sig_image_b64.split(',')[1]
                sig_image_bytes = base64.b64decode(sig_image_b64)
            except Exception as decode_err:
                logger.error(f"[CONTRACT_EMBED_SIGN] Failed to decode signature: {decode_err}")
                return jsonify({'error': 'Invalid signature image data'}), 400
            
            # Get pre-marked signature fields from database
            from sqlalchemy import text
            result = db.session.execute(text("""
                SELECT page, x, y, w, h
                FROM contract_signature_fields
                WHERE contract_id = :contract_id
                ORDER BY page, y, x
            """), {"contract_id": contract_id})
            
            fields = []
            for row in result:
                fields.append({
                    'page': row[0],
                    'x': float(row[1]),
                    'y': float(row[2]),
                    'w': float(row[3]),
                    'h': float(row[4])
                })
            
            if not fields:
                return jsonify({'error': 'No signature fields defined for this contract'}), 400
            
            # Get PDF info to convert relative coordinates to absolute
            try:
                pdf_info = get_pdf_info(pdf_data)
                pages_info = pdf_info.get('pages', [])
            except Exception as info_err:
                logger.error(f"[CONTRACT_EMBED_SIGN] Failed to get PDF info: {info_err}")
                return jsonify({'error': 'Failed to analyze PDF'}), 500
            
            # Create signature placements from fields
            for field in fields:
                page_num = field['page'] - 1  # Convert to 0-indexed
                
                if page_num < 0 or page_num >= len(pages_info):
                    logger.warning(f"[CONTRACT_EMBED_SIGN] Field page {field['page']} out of range, skipping")
                    continue
                
                page_info = pages_info[page_num]
                page_width = page_info['width']
                page_height = page_info['height']
                
                # Convert relative coordinates (0-1) to absolute (PDF points)
                abs_x = field['x'] * page_width
                abs_y = field['y'] * page_height
                abs_w = field['w'] * page_width
                abs_h = field['h'] * page_height
                
                placement = SignaturePlacement(
                    page_number=page_num,
                    x=abs_x,
                    y=abs_y,
                    width=abs_w,
                    height=abs_h,
                    signature_image=sig_image_bytes,
                    signer_name=signer_name
                )
                signature_placements.append(placement)
            
            logger.info(f"[CONTRACT_EMBED_SIGN] Created {len(signature_placements)} signature placements from pre-marked fields")
            
        elif signatures_data:
            # LEGACY MODE: Manual signature placements
            logger.info(f"[CONTRACT_EMBED_SIGN] Using legacy manual placements mode")
            
            for sig_data in signatures_data:
                try:
                    # Decode base64 signature image
                    sig_image_b64 = sig_data.get('signature_data', '')
                    if sig_image_b64.startswith('data:'):
                        sig_image_b64 = sig_image_b64.split(',')[1]
                    
                    sig_image_bytes = base64.b64decode(sig_image_b64)
                    
                    placement = SignaturePlacement(
                        page_number=int(sig_data.get('page_number', 0)),
                        x=float(sig_data.get('x', 0)),
                        y=float(sig_data.get('y', 0)),
                        width=float(sig_data.get('width', 150)),
                        height=float(sig_data.get('height', 50)),
                        signature_image=sig_image_bytes,
                        signer_name=signer_name
                    )
                    signature_placements.append(placement)
                except Exception as parse_err:
                    logger.warning(f"[CONTRACT_EMBED_SIGN] Error parsing signature: {parse_err}")
                    continue
        else:
            return jsonify({'error': 'Either signature_data or signatures array is required'}), 400
        
        if not signature_placements:
            return jsonify({'error': 'No valid signatures provided'}), 400
        
        # Embed signatures into PDF
        try:
            signed_pdf_data = embed_signatures_in_pdf(pdf_data, signature_placements)
        except Exception as embed_err:
            logger.error(f"[CONTRACT_EMBED_SIGN] Failed to embed signatures: {embed_err}")
            return jsonify({'error': 'Failed to embed signatures in PDF'}), 500
        
        # Save the signed PDF as a new attachment
        from werkzeug.datastructures import FileStorage
        signed_filename = f"signed_{attachment.filename_original}"
        signed_file = FileStorage(
            stream=io.BytesIO(signed_pdf_data),
            filename=signed_filename,
            content_type='application/pdf'
        )
        
        try:
            signed_attachment = create_attachment_from_file(
                file=signed_file,
                business_id=business_id,
                user_id=None
            )
        except Exception as save_err:
            logger.error(f"[CONTRACT_EMBED_SIGN] Failed to save signed PDF: {save_err}")
            return jsonify({'error': 'Failed to save signed document'}), 500
        
        # Create contract_file record for signed document
        signed_contract_file = ContractFile(
            business_id=business_id,
            contract_id=contract_id,
            attachment_id=signed_attachment.id,
            purpose='signed',
            created_by=None
        )
        
        db.session.add(signed_contract_file)
        
        # Update contract status
        contract.status = 'signed'
        contract.signed_at = datetime.utcnow()
        contract.updated_at = datetime.utcnow()
        if signer_name:
            contract.signer_name = signer_name
        
        # Mark token as used
        sign_token = ContractSignToken.query.get(token_id)
        if sign_token:
            sign_token.used_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log event
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='signed_completed',
            metadata={
                'filename': signed_filename,
                'signer_name': signer_name,
                'signature_count': len(signature_placements),
                'signature_type': 'embedded'
            },
            user_id=None
        )
        
        # Generate download URL for signed document
        signed_document_url = None
        try:
            signed_document_url = attachment_service.generate_signed_url(
                signed_attachment.storage_path,
                expires_in=86400  # 24 hours
            )
        except Exception as url_err:
            logger.warning(f"[CONTRACT_EMBED_SIGN] Could not generate signed URL: {url_err}")
        
        logger.info(f"[CONTRACT_EMBED_SIGN] contract_id={contract_id} signatures={len(signature_placements)} status=signed")
        
        return jsonify({
            'message': 'Contract signed successfully with embedded signatures',
            'contract_id': contract_id,
            'status': 'signed',
            'signed_at': contract.signed_at.isoformat(),
            'signed_document_url': signed_document_url,
            'signer_name': signer_name,
            'signature_count': len(signature_placements)
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_EMBED_SIGN] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to embed signatures'}), 500


@contracts_bp.route('/sign/<token>/pdf-info/<int:file_id>', methods=['GET'])
def get_pdf_info_for_signing(token, file_id):
    """
    PUBLIC endpoint - Get PDF info for signature placement (NO auth required)
    
    Returns page count and dimensions for proper signature placement UI
    """
    try:
        token_data = verify_signing_token(token)
        if not token_data:
            return jsonify({'error': 'Invalid, expired, or already used token'}), 403
        
        contract_id = token_data['contract_id']
        business_id = token_data['business_id']
        
        # Get the PDF file
        contract_file = ContractFile.query.filter_by(
            id=file_id,
            contract_id=contract_id,
            business_id=business_id
        ).filter(ContractFile.deleted_at.is_(None)).first()
        
        if not contract_file:
            return jsonify({'error': 'File not found'}), 404
        
        attachment = Attachment.query.get(contract_file.attachment_id)
        if not attachment:
            return jsonify({'error': 'Attachment not found'}), 404
        
        if attachment.mime_type != 'application/pdf':
            return jsonify({'error': 'Not a PDF file'}), 400
        
        # Download and analyze PDF
        attachment_service = get_attachment_service()
        try:
            filename, mime_type, pdf_data = attachment_service.open_file(
                attachment.storage_path,
                filename=attachment.filename_original,
                mime_type=attachment.mime_type
            )
        except Exception as download_err:
            logger.error(f"[CONTRACT_PDF_INFO] Failed to download PDF: {download_err}")
            return jsonify({'error': 'Failed to load document'}), 500
        
        from server.services.pdf_signing_service import get_pdf_info
        
        try:
            pdf_info = get_pdf_info(pdf_data)
        except Exception as info_err:
            logger.error(f"[CONTRACT_PDF_INFO] Failed to get PDF info: {info_err}")
            return jsonify({'error': 'Failed to analyze PDF'}), 500
        
        return jsonify({
            'file_id': file_id,
            'filename': attachment.filename_original,
            **pdf_info
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_PDF_INFO] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get PDF info'}), 500


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


@contracts_bp.route('/<int:contract_id>', methods=['PUT'])
@require_api_auth
@require_page_access('contracts')
def update_contract(contract_id):
    """
    Update contract details
    
    Request body (JSON):
        - title: Contract title (optional)
        - signer_name: Signer name (optional)
        - signer_phone: Signer phone (optional)
        - signer_email: Signer email (optional)
    
    Only allowed when contract status is 'draft'
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Only allow editing draft contracts
        if contract.status != 'draft':
            return jsonify({'error': 'Only draft contracts can be edited'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Track changes for audit
        changes = {}
        
        if 'title' in data:
            new_title = data['title'].strip() if data['title'] else ''
            if not new_title:
                return jsonify({'error': 'Title cannot be empty'}), 400
            if contract.title != new_title:
                changes['title'] = {'from': contract.title, 'to': new_title}
                contract.title = new_title
        
        if 'signer_name' in data:
            new_value = data['signer_name'].strip() if data['signer_name'] else None
            if contract.signer_name != new_value:
                changes['signer_name'] = {'from': contract.signer_name, 'to': new_value}
                contract.signer_name = new_value
        
        if 'signer_phone' in data:
            new_value = data['signer_phone'].strip() if data['signer_phone'] else None
            if contract.signer_phone != new_value:
                changes['signer_phone'] = {'from': contract.signer_phone, 'to': new_value}
                contract.signer_phone = new_value
        
        if 'signer_email' in data:
            new_value = data['signer_email'].strip() if data['signer_email'] else None
            if contract.signer_email != new_value:
                changes['signer_email'] = {'from': contract.signer_email, 'to': new_value}
                contract.signer_email = new_value
        
        if changes:
            contract.updated_at = datetime.utcnow()
            db.session.commit()
            
            log_contract_event(
                contract_id=contract_id,
                business_id=business_id,
                event_type='updated',
                metadata={'changes': changes},
                user_id=user_id
            )
            
            logger.info(f"[CONTRACT_UPDATE] contract_id={contract_id} changes={list(changes.keys())}")
        
        return jsonify({
            'id': contract.id,
            'title': contract.title,
            'status': contract.status,
            'signer_name': contract.signer_name,
            'signer_phone': contract.signer_phone,
            'signer_email': contract.signer_email,
            'updated_at': contract.updated_at.isoformat() if contract.updated_at else None
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_UPDATE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to update contract'}), 500


@contracts_bp.route('/<int:contract_id>', methods=['DELETE'])
@require_api_auth
@require_page_access('contracts')
def delete_contract(contract_id):
    """
    Delete contract (soft delete)
    
    Allows deleting contracts in any status
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Store status before deletion for logging
        contract_status = contract.status
        contract_title = contract.title
        
        # Soft delete all contract files (keep attachment records)
        contract_files = ContractFile.query.filter_by(
            contract_id=contract_id,
            business_id=business_id
        ).filter(ContractFile.deleted_at.is_(None)).all()
        
        for cf in contract_files:
            cf.deleted_at = datetime.utcnow()
        
        # Log deletion event before removing
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='deleted',
            metadata={'title': contract_title, 'status': contract_status},
            user_id=user_id
        )
        
        # Hard delete the contract record
        db.session.delete(contract)
        db.session.commit()
        
        logger.info(f"[CONTRACT_DELETE] contract_id={contract_id} status={contract_status} deleted by user_id={user_id}")
        
        return jsonify({
            'message': 'Contract deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"[CONTRACT_DELETE] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to delete contract'}), 500


# ============================================================================
# PDF Signature Placement API
# ============================================================================

@contracts_bp.route('/<int:contract_id>/signature-fields', methods=['POST'])
@require_api_auth
@require_page_access('contracts')
def save_signature_fields(contract_id):
    """
    Save signature field placements for a contract
    
    Request body (JSON):
        - fields: Array of field objects with:
            - page: Page number (1-based)
            - x, y, w, h: Coordinates (0-1 range, relative)
            - required: Boolean (optional, default True)
    
    Returns:
        - List of created field IDs
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Verify contract exists and belongs to business
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        data = request.get_json()
        if not data or 'fields' not in data:
            return jsonify({'error': 'Missing fields array'}), 400
        
        fields = data['fields']
        if not isinstance(fields, list):
            return jsonify({'error': 'fields must be an array'}), 400
        
        # Validate field count
        if len(fields) > 30:
            return jsonify({'error': 'Maximum 30 signature fields allowed'}), 400
        
        if len(fields) == 0:
            return jsonify({'error': 'At least one signature field required'}), 400
        
        # Validate each field
        for i, field in enumerate(fields):
            # Required fields
            for key in ['page', 'x', 'y', 'w', 'h']:
                if key not in field:
                    return jsonify({'error': f'Field {i}: missing {key}'}), 400
            
            # Validate types and ranges
            try:
                page = int(field['page'])
                if page < 1:
                    return jsonify({'error': f'Field {i}: page must be >= 1'}), 400
                
                x = float(field['x'])
                y = float(field['y'])
                w = float(field['w'])
                h = float(field['h'])
                
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    return jsonify({'error': f'Field {i}: x,y must be in range 0-1'}), 400
                
                if not (0 < w <= 1 and 0 < h <= 1):
                    return jsonify({'error': f'Field {i}: w,h must be in range 0-1'}), 400
                    
            except (ValueError, TypeError):
                return jsonify({'error': f'Field {i}: invalid numeric values'}), 400
        
        # Delete existing fields for this contract
        from sqlalchemy import text
        db.session.execute(
            text("DELETE FROM contract_signature_fields WHERE contract_id = :contract_id"),
            {"contract_id": contract_id}
        )
        
        # Create new fields
        field_ids = []
        for field in fields:
            required = field.get('required', True)
            
            db.session.execute(text("""
                INSERT INTO contract_signature_fields 
                (business_id, contract_id, page, x, y, w, h, required)
                VALUES (:business_id, :contract_id, :page, :x, :y, :w, :h, :required)
            """), {
                'business_id': business_id,
                'contract_id': contract_id,
                'page': int(field['page']),
                'x': float(field['x']),
                'y': float(field['y']),
                'w': float(field['w']),
                'h': float(field['h']),
                'required': required
            })
        
        db.session.commit()
        
        # Log event
        log_contract_event(
            contract_id=contract_id,
            business_id=business_id,
            event_type='signature_fields_updated',
            metadata={'field_count': len(fields)},
            user_id=user_id
        )
        
        logger.info(f"[SIGNATURE_FIELDS] Saved {len(fields)} fields for contract_id={contract_id}")
        
        return jsonify({
            'message': 'Signature fields saved successfully',
            'field_count': len(fields)
        }), 200
        
    except Exception as e:
        logger.error(f"[SIGNATURE_FIELDS] Error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to save signature fields'}), 500


@contracts_bp.route('/<int:contract_id>/signature-fields', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def get_signature_fields(contract_id):
    """
    Get signature field placements for a contract
    
    Returns:
        - fields: Array of field objects
    """
    try:
        business_id = get_current_business_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Verify contract exists and belongs to business
        contract = Contract.query.filter_by(id=contract_id, business_id=business_id).first()
        if not contract:
            return jsonify({'error': 'Contract not found'}), 404
        
        # Get fields
        from sqlalchemy import text
        result = db.session.execute(text("""
            SELECT id, page, x, y, w, h, required, created_at
            FROM contract_signature_fields
            WHERE contract_id = :contract_id
            ORDER BY page, y, x
        """), {"contract_id": contract_id})
        
        fields = []
        for row in result:
            fields.append({
                'id': row[0],
                'page': row[1],
                'x': float(row[2]),
                'y': float(row[3]),
                'w': float(row[4]),
                'h': float(row[5]),
                'required': row[6],
                'created_at': row[7].isoformat() if row[7] else None
            })
        
        return jsonify({
            'fields': fields,
            'field_count': len(fields)
        }), 200
        
    except Exception as e:
        logger.error(f"[SIGNATURE_FIELDS] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get signature fields'}), 500


# Public endpoint to get signature fields (for signing page)
@contracts_bp.route('/sign/<token>/signature-fields', methods=['GET'])
def get_signature_fields_public(token):
    """
    Get signature field placements using sign token (public endpoint)
    
    Returns:
        - fields: Array of field objects
    """
    try:
        # Validate token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        sign_token = ContractSignToken.query.filter_by(token_hash=token_hash).first()
        
        if not sign_token:
            return jsonify({'error': 'Invalid token'}), 404
        
        if sign_token.used_at:
            return jsonify({'error': 'Token already used'}), 400
        
        if sign_token.expires_at < datetime.utcnow():
            return jsonify({'error': 'Token expired'}), 400
        
        contract_id = sign_token.contract_id
        
        # Get fields
        from sqlalchemy import text
        result = db.session.execute(text("""
            SELECT id, page, x, y, w, h, required
            FROM contract_signature_fields
            WHERE contract_id = :contract_id
            ORDER BY page, y, x
        """), {"contract_id": contract_id})
        
        fields = []
        for row in result:
            fields.append({
                'id': row[0],
                'page': row[1],
                'x': float(row[2]),
                'y': float(row[3]),
                'w': float(row[4]),
                'h': float(row[5]),
                'required': row[6]
            })
        
        return jsonify({
            'fields': fields,
            'field_count': len(fields)
        }), 200
        
    except Exception as e:
        logger.error(f"[SIGNATURE_FIELDS_PUBLIC] Error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get signature fields'}), 500
