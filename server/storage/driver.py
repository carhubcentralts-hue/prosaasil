"""
Abstract base class for storage drivers
Defines the interface that all storage implementations must follow
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class StorageDriver(ABC):
    """
    Abstract storage driver interface
    
    All storage implementations (R2, S3, local, etc.) must implement these methods
    to ensure consistent behavior across the application.
    """
    
    @abstractmethod
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = 'application/octet-stream',
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload bytes to storage
        
        Args:
            key: Storage key (path) for the file
            data: File content as bytes
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            
        Returns:
            Storage key of the uploaded file
            
        Raises:
            StorageError: If upload fails
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a file from storage
        
        Args:
            key: Storage key (path) of the file to delete
            
        Returns:
            True if deleted successfully, False if file not found
            
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    def presign_get(self, key: str, ttl_seconds: int = 900) -> str:
        """
        Generate a presigned URL for downloading a file
        
        Args:
            key: Storage key (path) of the file
            ttl_seconds: Time-to-live for the URL in seconds (default: 15 minutes)
            
        Returns:
            Presigned URL that allows temporary access to the file
            
        Raises:
            StorageError: If URL generation fails
        """
        pass
    
    @abstractmethod
    def presign_put(
        self,
        key: str,
        ttl_seconds: int = 900,
        content_type: Optional[str] = None
    ) -> str:
        """
        Generate a presigned URL for uploading a file
        
        Args:
            key: Storage key (path) where the file will be uploaded
            ttl_seconds: Time-to-live for the URL in seconds (default: 15 minutes)
            content_type: Expected MIME type of the file
            
        Returns:
            Presigned URL that allows temporary upload access
            
        Raises:
            StorageError: If URL generation fails
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a file exists in storage
        
        Args:
            key: Storage key (path) to check
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_metadata(self, key: str) -> Dict[str, Any]:
        """
        Get metadata for a file
        
        Args:
            key: Storage key (path) of the file
            
        Returns:
            Dictionary with file metadata (size, content_type, last_modified, etc.)
            
        Raises:
            StorageError: If file not found or metadata retrieval fails
        """
        pass


class StorageError(Exception):
    """Base exception for storage operations"""
    pass
