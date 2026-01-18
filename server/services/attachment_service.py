"""
Attachment Storage Service - Unified file management for Email, WhatsApp, and Broadcasts

Features:
- Multi-tenant file storage with business isolation
- Secure file validation (mime type, size, dangerous files)
- Signed URL generation with TTL
- Local storage with path structure: /storage/attachments/{business_id}/{yyyy}/{mm}/{attachment_id}.ext
- Channel compatibility checking (WhatsApp has size/mime restrictions)

Security:
- No direct filesystem access
- All access through authenticated endpoints
- Business isolation enforced
- Dangerous file types blocked
"""

import os
import hashlib
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

# File type configurations
ALLOWED_MIME_TYPES = {
    # Images
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
    # Videos
    'video/mp4', 'video/mpeg', 'video/quicktime',
    # Documents
    'application/pdf',
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    # Audio (optional)
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg',
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
    """Service for managing file attachments"""
    
    def __init__(self, storage_root: Optional[str] = None):
        """
        Initialize attachment service
        
        Args:
            storage_root: Root directory for file storage (defaults to ./storage/attachments)
        """
        if storage_root is None:
            storage_root = os.path.join(os.getcwd(), 'storage', 'attachments')
        
        self.storage_root = storage_root
        os.makedirs(self.storage_root, exist_ok=True)
        logger.info(f"Attachment service initialized with storage root: {self.storage_root}")
    
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
    
    def get_storage_path(self, business_id: int, attachment_id: int, filename: str) -> str:
        """
        Generate storage path for attachment
        
        Format: {business_id}/{yyyy}/{mm}/{attachment_id}_{secure_filename}
        
        Args:
            business_id: Business ID for tenant isolation
            attachment_id: Attachment ID
            filename: Original filename
            
        Returns:
            Relative storage path
        """
        now = datetime.utcnow()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        
        # Secure filename and preserve extension
        secure_name = secure_filename(filename)
        ext = secure_name.rsplit('.', 1)[-1] if '.' in secure_name else ''
        
        # Build path: business_id/year/month/attachment_id.ext
        if ext:
            storage_filename = f"{attachment_id}.{ext}"
        else:
            storage_filename = str(attachment_id)
        
        return os.path.join(str(business_id), year, month, storage_filename)
    
    def save_file(self, file: FileStorage, business_id: int, attachment_id: int) -> Tuple[str, int]:
        """
        Save file to storage
        
        Args:
            file: Werkzeug FileStorage object
            business_id: Business ID for tenant isolation
            attachment_id: Attachment ID for path generation
            
        Returns:
            (storage_path, file_size)
        """
        # Generate storage path
        rel_path = self.get_storage_path(business_id, attachment_id, file.filename)
        abs_path = os.path.join(self.storage_root, rel_path)
        
        # Create directory structure
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # Save file
        file.save(abs_path)
        
        # Get file size
        file_size = os.path.getsize(abs_path)
        
        logger.info(f"Saved attachment {attachment_id} to {rel_path} ({file_size} bytes)")
        
        return rel_path, file_size
    
    def get_file_path(self, storage_path: str) -> str:
        """
        Get absolute file path from storage path
        
        Args:
            storage_path: Relative storage path
            
        Returns:
            Absolute file path
        """
        return os.path.join(self.storage_root, storage_path)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in storage
        
        Args:
            storage_path: Relative storage path
            
        Returns:
            True if file exists
        """
        abs_path = self.get_file_path(storage_path)
        return os.path.isfile(abs_path)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from storage (physical delete)
        
        Args:
            storage_path: Relative storage path
            
        Returns:
            True if deleted successfully
        """
        abs_path = self.get_file_path(storage_path)
        
        try:
            if os.path.isfile(abs_path):
                os.remove(abs_path)
                logger.info(f"Deleted file: {storage_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {storage_path}")
                return False
        except Exception as e:
            logger.error(f"Error deleting file {storage_path}: {e}")
            return False
    
    def generate_signed_url(self, attachment_id: int, storage_path: str, ttl_minutes: int = 60) -> str:
        """
        Generate signed URL with TTL
        
        For production: Implement actual signed URL with HMAC or JWT
        For now: Returns a token-based URL that will be validated by the endpoint
        
        Args:
            attachment_id: Attachment ID
            storage_path: Storage path
            ttl_minutes: Time-to-live in minutes (default: 60)
            
        Returns:
            Signed URL with expiration
        """
        # Generate expiration timestamp
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        expires_ts = int(expires_at.timestamp())
        
        # Create signature using HMAC
        # In production, use a secret key from environment
        secret = os.getenv('ATTACHMENT_SECRET', 'change-me-in-production')
        message = f"{attachment_id}:{expires_ts}:{storage_path}"
        signature = hashlib.sha256(f"{secret}:{message}".encode()).hexdigest()[:16]
        
        # Build signed URL
        # Format: /api/attachments/{id}/download?expires={ts}&sig={signature}
        return f"/api/attachments/{attachment_id}/download?expires={expires_ts}&sig={signature}"
    
    def verify_signed_url(self, attachment_id: int, storage_path: str, expires_ts: int, signature: str) -> Tuple[bool, Optional[str]]:
        """
        Verify signed URL
        
        Args:
            attachment_id: Attachment ID
            storage_path: Storage path
            expires_ts: Expiration timestamp
            signature: URL signature
            
        Returns:
            (is_valid, error_message)
        """
        # Check expiration
        now_ts = int(datetime.utcnow().timestamp())
        if now_ts > expires_ts:
            return False, "URL has expired"
        
        # Verify signature
        secret = os.getenv('ATTACHMENT_SECRET', 'change-me-in-production')
        message = f"{attachment_id}:{expires_ts}:{storage_path}"
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
