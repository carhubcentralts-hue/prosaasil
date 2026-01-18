"""
Storage abstraction layer for file management
Supports multiple storage backends (R2, local, etc.)
"""
from .driver import StorageDriver, StorageError
from .r2_driver import R2StorageDriver
from .factory import get_storage_driver, build_storage_key

__all__ = ['StorageDriver', 'StorageError', 'R2StorageDriver', 'get_storage_driver', 'build_storage_key']
