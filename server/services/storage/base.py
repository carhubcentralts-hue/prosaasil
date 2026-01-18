"""
Storage Abstraction Layer for Attachments

This module provides a unified interface for storing attachments,
supporting both local filesystem and Cloudflare R2 (S3-compatible) storage.

The storage provider is selected based on environment variables:
- ATTACHMENT_STORAGE_DRIVER=local (default) or r2
- R2 requires: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME

Security:
- No hardcoded credentials or bucket names
- Multi-tenant isolation maintained
- Signed URLs with TTL for all storage types
- Fallback to local storage if R2 configuration is missing
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


class StorageResult:
    """Result of a storage operation"""
    def __init__(self, storage_key: str, provider: str, size: int, metadata: Optional[Dict] = None):
        self.storage_key = storage_key
        self.provider = provider
        self.size = size
        self.metadata = metadata or {}
    
    def to_dict(self):
        return {
            'storage_key': self.storage_key,
            'provider': self.provider,
            'size': self.size,
            'metadata': self.metadata
        }


class AttachmentStorageProvider(ABC):
    """Abstract base class for attachment storage providers"""
    
    @abstractmethod
    def upload(self, business_id: int, attachment_id: int, file: FileStorage, 
               mime_type: str, filename: str) -> StorageResult:
        """
        Upload a file to storage
        
        Args:
            business_id: Business ID for tenant isolation
            attachment_id: Attachment ID
            file: File object to upload
            mime_type: MIME type of the file
            filename: Original filename
            
        Returns:
            StorageResult with storage_key and metadata
        """
        pass
    
    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """
        Delete a file from storage
        
        Args:
            storage_key: Storage key of the file
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def generate_signed_url(self, storage_key: str, ttl_seconds: int = 900) -> str:
        """
        Generate a signed URL for accessing the file
        
        Args:
            storage_key: Storage key of the file
            ttl_seconds: Time-to-live in seconds (default: 15 minutes)
            
        Returns:
            Signed URL string
        """
        pass
    
    @abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        """
        Check if a file exists in storage
        
        Args:
            storage_key: Storage key of the file
            
        Returns:
            True if file exists
        """
        pass
    
    def get_storage_key(self, business_id: int, attachment_id: int, filename: str) -> str:
        """
        Generate standardized storage key
        
        Format: attachments/{business_id}/{yyyy}/{mm}/{attachment_id}.ext
        
        Args:
            business_id: Business ID
            attachment_id: Attachment ID
            filename: Original filename (for extension)
            
        Returns:
            Storage key string
        """
        now = datetime.utcnow()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        
        # Extract extension
        ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
        
        # Build storage key
        if ext:
            storage_filename = f"{attachment_id}.{ext}"
        else:
            storage_filename = str(attachment_id)
        
        return f"attachments/{business_id}/{year}/{month}/{storage_filename}"


def get_storage_provider() -> AttachmentStorageProvider:
    """
    Factory function to get the configured storage provider
    
    Returns:
        AttachmentStorageProvider instance based on configuration
        
    Environment Variables:
        ATTACHMENT_STORAGE_DRIVER: 'local' (default) or 'r2'
        
        For R2:
        - R2_ACCOUNT_ID: Cloudflare account ID
        - R2_ACCESS_KEY_ID: R2 access key
        - R2_SECRET_ACCESS_KEY: R2 secret key
        - R2_BUCKET_NAME: R2 bucket name
    """
    driver = os.getenv('ATTACHMENT_STORAGE_DRIVER', 'local').lower()
    
    if driver == 'r2':
        # Try to initialize R2 provider
        try:
            from server.services.storage.r2_provider import R2StorageProvider
            
            # Validate required environment variables
            required_vars = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                logger.error(f"❌ R2 storage selected but missing environment variables: {', '.join(missing_vars)}")
                logger.warning("⚠️ Falling back to local storage")
                driver = 'local'
            else:
                logger.info("✅ Using R2 (Cloudflare) storage provider")
                return R2StorageProvider()
                
        except ImportError as e:
            logger.error(f"❌ R2 provider not available: {e}")
            logger.warning("⚠️ Falling back to local storage")
            driver = 'local'
        except Exception as e:
            logger.error(f"❌ Failed to initialize R2 provider: {e}")
            logger.warning("⚠️ Falling back to local storage")
            driver = 'local'
    
    # Default to local storage
    from server.services.storage.local_provider import LocalStorageProvider
    logger.info("✅ Using local filesystem storage provider")
    return LocalStorageProvider()


# Singleton instance
_storage_provider = None

def get_attachment_storage() -> AttachmentStorageProvider:
    """Get or create storage provider singleton"""
    global _storage_provider
    if _storage_provider is None:
        _storage_provider = get_storage_provider()
    return _storage_provider
