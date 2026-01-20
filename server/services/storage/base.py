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
               mime_type: str, filename: str, purpose: str = 'general_upload') -> StorageResult:
        """
        Upload a file to storage
        
        Args:
            business_id: Business ID for tenant isolation
            attachment_id: Attachment ID
            file: File object to upload
            mime_type: MIME type of the file
            filename: Original filename
            purpose: File purpose for path organization (e.g., 'receipt_source', 'contract_original')
            
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
    
    def get_storage_key(self, business_id: int, attachment_id: int, filename: str, purpose: str = 'general_upload') -> str:
        """
        Generate standardized storage key with purpose-based path
        
        Format: attachments/{business_id}/{purpose}/{yyyy}/{mm}/{attachment_id}.ext
        
        Args:
            business_id: Business ID
            attachment_id: Attachment ID
            filename: Original filename (for extension)
            purpose: File purpose for organization
            
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
        
        return f"attachments/{business_id}/{purpose}/{year}/{month}/{storage_filename}"


def get_storage_provider() -> AttachmentStorageProvider:
    """
    Factory function to get the configured storage provider
    
    Returns:
        AttachmentStorageProvider instance based on configuration
        
    Environment Variables:
        PRODUCTION: Set to '1' or 'true' for production mode
        ATTACHMENT_STORAGE_DRIVER: 'local' (default) or 'r2'
        R2_FALLBACK_TO_LOCAL: Set to '1' or 'true' to allow fallback to local storage on R2 failure (optional)
        
        For R2:
        - R2_ACCOUNT_ID: Cloudflare account ID
        - R2_ACCESS_KEY_ID: R2 access key
        - R2_SECRET_ACCESS_KEY: R2 secret key
        - R2_BUCKET_NAME: R2 bucket name
        
    Raises:
        RuntimeError: In production mode if R2 is not properly configured (and no fallback allowed)
    """
    driver = os.getenv('ATTACHMENT_STORAGE_DRIVER', 'local').lower()
    is_production = os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
    allow_fallback = os.getenv('R2_FALLBACK_TO_LOCAL', '0') in ('1', 'true', 'True')
    
    # 🔥 PRODUCTION SAFETY: R2 is REQUIRED in production (unless fallback is explicitly enabled)
    if is_production and driver != 'r2' and not allow_fallback:
        logger.error("🚨 CRITICAL: Production mode requires ATTACHMENT_STORAGE_DRIVER=r2")
        logger.error("❌ Local storage is NOT allowed in production")
        logger.error("Set ATTACHMENT_STORAGE_DRIVER=r2 and configure R2_* environment variables")
        logger.error("Or set R2_FALLBACK_TO_LOCAL=1 to allow graceful degradation to local storage")
        raise RuntimeError(
            "Production mode requires R2 storage. "
            "Set ATTACHMENT_STORAGE_DRIVER=r2 and configure R2 credentials. "
            "See .env.r2.example for configuration details."
        )
    
    if driver == 'r2':
        # Try to initialize R2 provider
        try:
            from server.services.storage.r2_provider import R2StorageProvider
            
            # Validate required environment variables
            required_vars = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                error_msg = f"R2 storage selected but missing environment variables: {', '.join(missing_vars)}"
                logger.error(f"❌ {error_msg}")
                
                # 🔥 PRODUCTION SAFETY: NO fallback in production unless explicitly allowed
                if is_production and not allow_fallback:
                    logger.error("🚨 CRITICAL: Cannot fall back to local storage in production mode")
                    logger.error(f"Missing: {', '.join(missing_vars)}")
                    logger.error("Set these environment variables and restart the application")
                    raise RuntimeError(
                        f"Production mode requires complete R2 configuration. {error_msg}. "
                        "See .env.r2.example for configuration details."
                    )
                
                # Development or fallback allowed: allow fallback with warning
                logger.warning("⚠️ Falling back to local storage due to missing R2 configuration")
                driver = 'local'
            else:
                logger.info("✅ Using R2 (Cloudflare) storage provider")
                return R2StorageProvider()
                
        except ImportError as e:
            error_msg = f"R2 provider not available (boto3 missing): {e}"
            logger.error(f"❌ {error_msg}")
            
            # 🔥 PRODUCTION SAFETY: NO fallback in production unless explicitly allowed
            if is_production and not allow_fallback:
                logger.error("🚨 CRITICAL: Cannot fall back to local storage in production mode")
                logger.error("Install boto3: pip install boto3")
                raise RuntimeError(
                    f"Production mode requires R2 provider. {error_msg}. "
                    "Install boto3: pip install boto3"
                )
            
            # Development or fallback allowed: allow fallback with warning
            logger.warning("⚠️ Falling back to local storage due to boto3 not available")
            driver = 'local'
        except Exception as e:
            error_msg = f"Failed to initialize R2 provider: {e}"
            logger.error(f"❌ {error_msg}")
            
            # 🔥 PRODUCTION SAFETY: NO fallback in production unless explicitly allowed
            if is_production and not allow_fallback:
                logger.error("🚨 CRITICAL: Cannot fall back to local storage in production mode")
                logger.error(f"R2 initialization error: {e}")
                raise RuntimeError(
                    f"Production mode requires working R2 configuration. {error_msg}"
                )
            
            # Development or fallback allowed: allow fallback with warning
            logger.warning(f"⚠️ Falling back to local storage due to R2 initialization failure: {e}")
            driver = 'local'
    
    # Default to local storage (only allowed in development or with fallback enabled)
    from server.services.storage.local_provider import LocalStorageProvider
    
    if is_production and not allow_fallback:
        # This should never be reached due to earlier checks, but double-check
        logger.error("🚨 CRITICAL: Local storage is NOT allowed in production mode")
        raise RuntimeError(
            "Production mode requires R2 storage. "
            "Set ATTACHMENT_STORAGE_DRIVER=r2 and configure R2 credentials."
        )
    
    if is_production:
        logger.warning("⚠️ Using local filesystem storage provider in production (R2_FALLBACK_TO_LOCAL enabled)")
    else:
        logger.info("✅ Using local filesystem storage provider (development only)")
    return LocalStorageProvider()


# Singleton instance
_storage_provider = None

def get_attachment_storage() -> AttachmentStorageProvider:
    """Get or create storage provider singleton"""
    global _storage_provider
    if _storage_provider is None:
        _storage_provider = get_storage_provider()
    return _storage_provider
