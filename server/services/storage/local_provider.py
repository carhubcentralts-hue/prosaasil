"""
Local Filesystem Storage Provider

Stores attachments on local filesystem with tenant isolation.
Uses signed internal URLs for secure access.
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from werkzeug.datastructures import FileStorage
from .base import AttachmentStorageProvider, StorageResult

logger = logging.getLogger(__name__)


class LocalStorageProvider(AttachmentStorageProvider):
    """Local filesystem storage provider"""
    
    def __init__(self, storage_root: Optional[str] = None):
        """
        Initialize local storage provider
        
        Args:
            storage_root: Root directory for storage (default: ./storage/attachments)
        """
        if storage_root is None:
            storage_root = os.path.join(os.getcwd(), 'storage', 'attachments')
        
        self.storage_root = storage_root
        os.makedirs(self.storage_root, exist_ok=True)
        logger.info(f"[LOCAL_STORAGE] Initialized with root: {self.storage_root}")
    
    def upload(self, business_id: int, attachment_id: int, file: FileStorage, 
               mime_type: str, filename: str) -> StorageResult:
        """Upload file to local filesystem"""
        # Generate storage key
        storage_key = self.get_storage_key(business_id, attachment_id, filename)
        
        # Convert storage key to filesystem path
        file_path = os.path.join(self.storage_root, storage_key)
        
        # Create directory structure
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        logger.info(f"[LOCAL_STORAGE] Uploaded: {storage_key} ({file_size} bytes)")
        
        return StorageResult(
            storage_key=storage_key,
            provider='local',
            size=file_size,
            metadata={'path': file_path}
        )
    
    def delete(self, storage_key: str) -> bool:
        """Delete file from local filesystem"""
        file_path = os.path.join(self.storage_root, storage_key)
        
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.info(f"[LOCAL_STORAGE] Deleted: {storage_key}")
                return True
            else:
                logger.warning(f"[LOCAL_STORAGE] File not found for deletion: {storage_key}")
                return False
        except Exception as e:
            logger.error(f"[LOCAL_STORAGE] Error deleting {storage_key}: {e}")
            return False
    
    def generate_signed_url(self, storage_key: str, ttl_seconds: int = 900) -> str:
        """
        Generate signed internal URL for local file access
        
        Format: /api/attachments/{id}/download?expires={ts}&sig={signature}
        """
        # Extract attachment_id from storage_key
        # Format: attachments/{business_id}/{yyyy}/{mm}/{attachment_id}.ext
        parts = storage_key.split('/')
        if len(parts) >= 4:
            filename_with_ext = parts[-1]  # e.g., "123.jpg"
            attachment_id = filename_with_ext.split('.')[0]  # e.g., "123"
        else:
            attachment_id = "unknown"
        
        # Generate expiration timestamp
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        expires_ts = int(expires_at.timestamp())
        
        # Create signature using HMAC
        secret = os.getenv('ATTACHMENT_SECRET', 'change-me-in-production')
        message = f"{attachment_id}:{expires_ts}:{storage_key}"
        signature = hashlib.sha256(f"{secret}:{message}".encode()).hexdigest()[:16]
        
        # Build signed URL
        signed_url = f"/api/attachments/{attachment_id}/download?expires={expires_ts}&sig={signature}"
        
        logger.debug(f"[LOCAL_STORAGE] Generated signed URL for {storage_key} (TTL: {ttl_seconds}s)")
        
        return signed_url
    
    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in local filesystem"""
        file_path = os.path.join(self.storage_root, storage_key)
        exists = os.path.isfile(file_path)
        
        if not exists:
            logger.warning(f"[LOCAL_STORAGE] File not found: {storage_key}")
        
        return exists
    
    def get_file_path(self, storage_key: str) -> str:
        """Get absolute file path from storage key (local-specific method)"""
        return os.path.join(self.storage_root, storage_key)
