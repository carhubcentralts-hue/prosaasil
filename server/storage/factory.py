"""
Storage driver factory
Creates and caches storage driver instances based on configuration
"""
import os
import logging
from typing import Optional
from .driver import StorageDriver, StorageError
from .r2_driver import R2StorageDriver

logger = logging.getLogger(__name__)

# Singleton instance cache
_driver_instance: Optional[StorageDriver] = None


def get_storage_driver() -> StorageDriver:
    """
    Get storage driver instance (singleton)
    
    Initializes the appropriate storage driver based on STORAGE_DRIVER env variable:
    - 'r2': Cloudflare R2 storage (requires R2_* env variables)
    - Default: R2 storage
    
    Returns:
        StorageDriver instance
        
    Raises:
        StorageError: If configuration is invalid or initialization fails
    """
    global _driver_instance
    
    # Return cached instance if available
    if _driver_instance is not None:
        return _driver_instance
    
    # Get driver type from environment
    driver_type = os.getenv('STORAGE_DRIVER', 'r2').lower()
    
    logger.info(f"[STORAGE] Initializing storage driver: {driver_type}")
    
    if driver_type == 'r2':
        # Initialize R2 driver
        account_id = os.getenv('R2_ACCOUNT_ID')
        access_key_id = os.getenv('R2_ACCESS_KEY_ID')
        secret_access_key = os.getenv('R2_SECRET_ACCESS_KEY')
        bucket_name = os.getenv('R2_BUCKET', 'prosaas-files')
        
        # Validate required configuration
        if not all([account_id, access_key_id, secret_access_key]):
            raise StorageError(
                "Missing required R2 configuration. "
                "Please set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY"
            )
        
        logger.info(f"[STORAGE] Using R2 (Cloudflare) storage provider")
        _driver_instance = R2StorageDriver(
            account_id=account_id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_name=bucket_name
        )
    else:
        raise StorageError(f"Unknown storage driver: {driver_type}")
    
    return _driver_instance


def build_storage_key(business_id: int, category: str, resource_id: str, filename: str) -> str:
    """
    Build a tenant-scoped storage key
    
    Format: business/{business_id}/{category}/{resource_id}/{filename}
    
    Examples:
        - business/1/contracts/123/contract.pdf
        - business/1/attachments/456/image.png
        - business/1/contracts/789/signed_contract.pdf
    
    Args:
        business_id: Business ID for multi-tenant isolation
        category: Category (e.g., 'contracts', 'attachments')
        resource_id: Resource ID (e.g., contract_id, attachment_id)
        filename: Original or generated filename
        
    Returns:
        Storage key string
    """
    # Sanitize filename to prevent path traversal
    safe_filename = filename.replace('..', '').replace('/', '_').strip()
    
    return f"business/{business_id}/{category}/{resource_id}/{safe_filename}"


def reset_driver():
    """
    Reset the cached driver instance (for testing)
    """
    global _driver_instance
    _driver_instance = None
