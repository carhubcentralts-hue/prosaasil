"""
Attachment Storage Service - Unified file management for Email, WhatsApp, and Broadcasts

Features:
- Multi-tenant file storage with business isolation
- Secure file validation (mime type, size, dangerous files)
- Signed URL generation with TTL
- Storage abstraction layer (supports local filesystem and Cloudflare R2)
- Channel compatibility checking (WhatsApp has size/mime restrictions)

Security:
- No direct filesystem access (abstracted through storage providers)
- All access through authenticated endpoints
- Business isolation enforced
- Dangerous file types blocked

Storage Providers:
- Local: /storage/attachments/{business_id}/{yyyy}/{mm}/{attachment_id}.ext
- R2: Cloudflare R2 bucket with presigned URLs

Configuration via environment variables - see storage/base.py
"""

import os
import logging
import mimetypes
from typing import Optional, Dict, List, Tuple
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from server.services.storage import get_attachment_storage

logger = logging.getLogger(__name__)

# File type configurations
ALLOWED_MIME_TYPES = {
    # Images
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    # Videos
    'video/mp4', 'video/mpeg', 'video/quicktime',
    # Documents
    'application/pdf',
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    # Audio (optional)
    'audio/mpeg', 'audio/wav', 'audio/ogg',
}

# Dangerous file extensions that should never be uploaded
BLOCKED_EXTENSIONS = {
    'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jse', 'wsf', 'wsh',
    'msi', 'jar', 'app', 'deb', 'rpm', 'dmg', 'pkg', 'sh', 'bash', 'ps1',
    'html', 'htm', 'svg', 'xml'  # Can contain scripts
}

# Channel-specific limits (bytes)
CHANNEL_LIMITS = {
    'email': 25 * 1024 * 1024,  # 25 MB - typical email limit
    'whatsapp': 16 * 1024 * 1024,  # 16 MB - WhatsApp limit
    'broadcast': 16 * 1024 * 1024,  # 16 MB - same as WhatsApp
}

# WhatsApp supported mime types (more restrictive)
WHATSAPP_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp',
    'video/mp4', 'video/3gpp',
    'audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg',
    'application/pdf',
    'application/vnd.ms-powerpoint',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


class AttachmentService:
    """Service for managing file attachments with storage abstraction"""
    
    def __init__(self):
        """
        Initialize attachment service with storage provider
        
        Storage provider is selected based on ATTACHMENT_STORAGE_DRIVER environment variable.
        See server/services/storage/base.py for configuration details.
        """
        self.storage = get_attachment_storage()
        logger.info(f"Attachment service initialized with storage provider: {type(self.storage).__name__}")
    
    def validate_file(self, file: FileStorage, channel: str = 'email') -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file
        
        Args:
            file: Werkzeug FileStorage object
            channel: Target channel ('email', 'whatsapp', 'broadcast')
            
        Returns:
            (is_valid, error_message)
        """
        # Check if file exists
        if not file or not file.filename:
            return False, "No file provided"
        
        # Get file extension
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        # Check for dangerous extensions
        if ext in BLOCKED_EXTENSIONS:
            return False, f"File type .{ext} is not allowed for security reasons"
        
        # Check mime type
        mime_type = file.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        if mime_type not in ALLOWED_MIME_TYPES:
            return False, f"File type {mime_type} is not supported"
        
        # Check channel-specific restrictions
        if channel == 'whatsapp' or channel == 'broadcast':
            if mime_type not in WHATSAPP_MIME_TYPES:
                return False, f"File type {mime_type} is not supported by WhatsApp"
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        max_size = CHANNEL_LIMITS.get(channel, CHANNEL_LIMITS['email'])
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds {max_mb:.0f} MB limit for {channel}"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, None
    
    def get_channel_compatibility(self, mime_type: str, file_size: int) -> Dict[str, bool]:
        """
        Determine which channels support this file
        
        Args:
            mime_type: File MIME type
            file_size: File size in bytes
            
        Returns:
            Dict with channel compatibility: {'email': True, 'whatsapp': False, ...}
        """
        compatibility = {}
        
        for channel, max_size in CHANNEL_LIMITS.items():
            # Check size
            if file_size > max_size:
                compatibility[channel] = False
                continue
            
            # Check mime type
            if channel == 'whatsapp' or channel == 'broadcast':
                compatibility[channel] = mime_type in WHATSAPP_MIME_TYPES
            else:
                compatibility[channel] = mime_type in ALLOWED_MIME_TYPES
        
        return compatibility
    
    def save_file(self, file: FileStorage, business_id: int, attachment_id: int, purpose: str = 'general_upload') -> Tuple[str, int]:
        """
        Save file to storage (using configured storage provider)
        
        Args:
            file: Werkzeug FileStorage object
            business_id: Business ID for tenant isolation
            attachment_id: Attachment ID for path generation
            purpose: File purpose for categorization (e.g., 'receipt_source', 'contract_original')
            
        Returns:
            (storage_key, file_size)
        """
        # Get mime type and filename
        mime_type = file.content_type or 'application/octet-stream'
        filename = secure_filename(file.filename)
        
        # Upload via storage provider with purpose in path
        result = self.storage.upload(
            business_id=business_id,
            attachment_id=attachment_id,
            file=file,
            mime_type=mime_type,
            filename=filename,
            purpose=purpose  # Pass purpose to storage provider
        )
        
        logger.info(f"Saved attachment {attachment_id} via {result.provider} ({result.size} bytes) purpose={purpose}")
        
        return result.storage_key, result.size
    
    def get_file_path(self, storage_key: str) -> str:
        """
        Get file path from storage key (LOCAL STORAGE ONLY)
        
        This method is ONLY for local storage provider.
        For R2 or other providers, use generate_signed_url instead.
        
        Args:
            storage_key: Storage key
            
        Returns:
            Absolute file path (local storage only)
        """
        # Check if we're using local storage
        from server.services.storage.local_provider import LocalStorageProvider
        
        if isinstance(self.storage, LocalStorageProvider):
            return self.storage.get_file_path(storage_key)
        else:
            # For R2 or other providers, this method doesn't make sense
            logger.warning(f"get_file_path called on non-local storage provider: {type(self.storage).__name__}")
            raise NotImplementedError("get_file_path is only supported for local storage. Use generate_signed_url instead.")
    
    def file_exists(self, storage_key: str) -> bool:
        """
        Check if file exists in storage
        
        Args:
            storage_key: Storage key
            
        Returns:
            True if file exists
        """
        return self.storage.file_exists(storage_key)
    
    def delete_file(self, storage_key: str) -> bool:
        """
        Delete file from storage (physical delete)
        
        Args:
            storage_key: Storage key
            
        Returns:
            True if deleted successfully
        """
        return self.storage.delete(storage_key)
    
    def generate_signed_url(self, attachment_id: int, storage_key: str, ttl_minutes: int = 60, 
                           mime_type: str = None, filename: str = None) -> str:
        """
        Generate signed URL with TTL and optional response headers
        
        Uses storage provider's signed URL generation (presigned for R2, internal token for local)
        
        Args:
            attachment_id: Attachment ID (for local storage URL generation)
            storage_key: Storage key
            ttl_minutes: Time-to-live in minutes (default: 60)
            mime_type: Optional MIME type to force in Content-Type header
            filename: Optional filename to use in Content-Disposition header
            
        Returns:
            Signed URL
        """
        ttl_seconds = ttl_minutes * 60
        
        # Try to use enhanced signature with headers (R2 provider supports this)
        try:
            # Build optional parameters
            kwargs = {'ttl_seconds': ttl_seconds}
            
            # Add Content-Type if provided (ensures PDF is served as application/pdf)
            if mime_type:
                kwargs['content_type'] = mime_type
                
            # Add Content-Disposition if filename provided (inline for PDFs to allow iframe viewing)
            if filename:
                # Use 'inline' for PDFs to allow browser viewing, otherwise 'attachment'
                disposition = 'inline' if mime_type and 'pdf' in mime_type.lower() else 'attachment'
                kwargs['content_disposition'] = f'{disposition}; filename="{filename}"'
            
            return self.storage.generate_signed_url(storage_key, **kwargs)
        except TypeError:
            # Fallback for storage providers that don't support the new signature
            logger.warning(f"[ATTACHMENT_SERVICE] Storage provider doesn't support header parameters, using basic signature")
            return self.storage.generate_signed_url(storage_key, ttl_seconds)
    
    def open_file(self, storage_key: str, filename: str = None, mime_type: str = None) -> Tuple[str, str, bytes]:
        """
        Open and read file from storage (works with both Local and R2)
        
        This is the PRIMARY method for accessing file content for:
        - Email attachments (SendGrid requires base64 of actual bytes)
        - WhatsApp media (Baileys needs bytes/buffer)
        
        Unlike get_file_path (which only works with local storage),
        this method works uniformly with any storage provider.
        
        Args:
            storage_key: Storage key from attachment record
            filename: Original filename (used for email attachment name)
            mime_type: MIME type of file (if known)
            
        Returns:
            Tuple of (filename, mime_type, file_bytes)
            
        Raises:
            FileNotFoundError: If file does not exist
            Exception: On storage access failure
        """
        # Download bytes from storage (works with both Local and R2)
        file_bytes = self.storage.download_bytes(storage_key)
        
        # Get metadata if we don't have mime_type
        if not mime_type:
            try:
                metadata = self.storage.get_metadata(storage_key)
                mime_type = metadata.get('content_type', 'application/octet-stream')
            except Exception:
                mime_type = 'application/octet-stream'
        
        # Default filename from storage key if not provided
        if not filename:
            # Extract filename from storage key (last part)
            filename = storage_key.split('/')[-1] if '/' in storage_key else storage_key
        
        logger.info(f"[ATTACHMENT] Opened file: {filename} ({len(file_bytes)} bytes, {mime_type})")
        
        return filename, mime_type, file_bytes
    
    def verify_signed_url(self, attachment_id: int, storage_key: str, expires_ts: int, signature: str) -> Tuple[bool, Optional[str]]:
        """
        Verify signed URL (LOCAL STORAGE ONLY)
        
        For R2, presigned URLs are verified by the S3 service itself.
        This method is only used for local storage internal URLs.
        
        Args:
            attachment_id: Attachment ID
            storage_key: Storage key
            expires_ts: Expiration timestamp
            signature: URL signature
            
        Returns:
            (is_valid, error_message)
        """
        from server.services.storage.local_provider import LocalStorageProvider
        from datetime import datetime
        import hashlib
        
        # This verification is only for local storage
        if not isinstance(self.storage, LocalStorageProvider):
            return True, None  # R2 handles verification itself
        
        # Check expiration
        now_ts = int(datetime.utcnow().timestamp())
        if now_ts > expires_ts:
            return False, "URL has expired"
        
        # Verify signature
        secret = os.getenv('ATTACHMENT_SECRET', 'change-me-in-production')
        message = f"{attachment_id}:{expires_ts}:{storage_key}"
        expected_sig = hashlib.sha256(f"{secret}:{message}".encode()).hexdigest()[:16]
        
        if signature != expected_sig:
            return False, "Invalid signature"
        
        return True, None


# Singleton instance
_attachment_service = None

def get_attachment_service() -> AttachmentService:
    """Get or create attachment service singleton"""
    global _attachment_service
    if _attachment_service is None:
        _attachment_service = AttachmentService()
    return _attachment_service
