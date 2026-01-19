"""
Cloudflare R2 Storage Provider

Stores attachments in Cloudflare R2 (S3-compatible storage).
Uses presigned URLs for secure access.

Required Environment Variables:
- R2_ACCOUNT_ID: Cloudflare account ID
- R2_ACCESS_KEY_ID: R2 access key
- R2_SECRET_ACCESS_KEY: R2 secret key  
- R2_BUCKET_NAME: R2 bucket name

NO hardcoded values - all configuration from environment.
"""

import os
import logging
from datetime import timedelta
from typing import Optional
from werkzeug.datastructures import FileStorage
from .base import AttachmentStorageProvider, StorageResult

logger = logging.getLogger(__name__)

# Try to import boto3 (required for R2)
try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("❌ boto3 not installed - R2 storage will not be available")


class R2StorageProvider(AttachmentStorageProvider):
    """Cloudflare R2 (S3-compatible) storage provider"""
    
    def __init__(self):
        """
        Initialize R2 storage provider
        
        Raises:
            ImportError: If boto3 is not installed
            ValueError: If required environment variables are missing
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required for R2 storage. Install with: pip install boto3")
        
        # Load configuration from environment - NO hardcoding
        self.account_id = os.getenv('R2_ACCOUNT_ID')
        self.access_key_id = os.getenv('R2_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('R2_BUCKET_NAME')
        
        # Validate required variables
        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name]):
            missing = []
            if not self.account_id: missing.append('R2_ACCOUNT_ID')
            if not self.access_key_id: missing.append('R2_ACCESS_KEY_ID')
            if not self.secret_access_key: missing.append('R2_SECRET_ACCESS_KEY')
            if not self.bucket_name: missing.append('R2_BUCKET_NAME')
            
            raise ValueError(f"Missing required environment variables for R2: {', '.join(missing)}")
        
        # Build R2 endpoint - prefer explicit R2_ENDPOINT if set, otherwise construct from account ID
        self.endpoint_url = os.getenv('R2_ENDPOINT') or f"https://{self.account_id}.r2.cloudflarestorage.com"
        
        # Initialize S3 client with R2 configuration
        # CRITICAL for R2: region='auto', signature_version='s3v4', path-style addressing
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto',  # R2 requires 'auto' region
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
        )
        
        logger.info(f"[R2_STORAGE] Initialized with bucket: {self.bucket_name}")
        logger.info(f"[R2_STORAGE] Endpoint: {self.endpoint_url}")
        
        # Verify bucket access
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"[R2_STORAGE] ✅ Bucket access verified")
        except ClientError as e:
            logger.error(f"[R2_STORAGE] ❌ Failed to access bucket: {e}")
            raise ValueError(f"Cannot access R2 bucket '{self.bucket_name}'. Check credentials and bucket name.")
    
    def upload(self, business_id: int, attachment_id: int, file: FileStorage, 
               mime_type: str, filename: str) -> StorageResult:
        """Upload file to R2"""
        # Generate storage key
        storage_key = self.get_storage_key(business_id, attachment_id, filename)
        
        try:
            # Read file content
            file.seek(0)
            file_content = file.read()
            file_size = len(file_content)
            
            # Upload to R2 - CRITICAL: Always set ContentType or default to application/octet-stream
            content_type = mime_type or "application/octet-stream"
            
            logger.info(f"[R2_STORAGE] Uploading to bucket={self.bucket_name}, key={storage_key}, size={file_size}, type={content_type}")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'business_id': str(business_id),
                    'attachment_id': str(attachment_id),
                    'original_filename': filename
                }
            )
            
            logger.info(f"[R2_STORAGE] ✅ Uploaded: {storage_key} ({file_size} bytes)")
            
            return StorageResult(
                storage_key=storage_key,
                provider='r2',
                size=file_size,
                metadata={
                    'bucket': self.bucket_name,
                    'endpoint': self.endpoint_url
                }
            )
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Upload failed for {storage_key}: {e}")
            raise Exception(f"Failed to upload to R2: {e}")
    
    def delete(self, storage_key: str) -> bool:
        """Delete file from R2"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            logger.info(f"[R2_STORAGE] Deleted: {storage_key}")
            return True
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Delete failed for {storage_key}: {e}")
            return False
    
    def generate_signed_url(self, storage_key: str, ttl_seconds: int = 900) -> str:
        """
        Generate presigned URL for R2 file access
        
        Args:
            storage_key: Storage key of the file
            ttl_seconds: Time-to-live in seconds (default: 15 minutes)
            
        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': storage_key
                },
                ExpiresIn=ttl_seconds
            )
            
            logger.debug(f"[R2_STORAGE] Generated presigned URL for {storage_key} (TTL: {ttl_seconds}s)")
            return url
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Failed to generate presigned URL for {storage_key}: {e}")
            raise Exception(f"Failed to generate presigned URL: {e}")
    
    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in R2"""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"[R2_STORAGE] File not found: {storage_key}")
                return False
            else:
                logger.error(f"[R2_STORAGE] Error checking file existence for {storage_key}: {e}")
                return False
    
    def download_bytes(self, storage_key: str) -> bytes:
        """
        Download file content from R2 as bytes
        
        This is used for attaching files to emails (SendGrid requires base64 content)
        and for sending media via WhatsApp (Baileys needs the actual bytes/buffer).
        
        Args:
            storage_key: Storage key of the file
            
        Returns:
            File content as bytes
            
        Raises:
            Exception: If download fails or file not found
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            
            # Read the body into bytes
            file_bytes = response['Body'].read()
            
            logger.info(f"[R2_STORAGE] ✅ Downloaded {storage_key} ({len(file_bytes)} bytes)")
            return file_bytes
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404' or error_code == 'NoSuchKey':
                logger.error(f"[R2_STORAGE] File not found for download: {storage_key}")
                raise FileNotFoundError(f"File not found in R2: {storage_key}")
            else:
                logger.error(f"[R2_STORAGE] Download failed for {storage_key}: {e}")
                raise Exception(f"Failed to download from R2: {e}")
    
    def get_metadata(self, storage_key: str) -> dict:
        """
        Get file metadata from R2
        
        Args:
            storage_key: Storage key of the file
            
        Returns:
            Dict with content_type, content_length, and metadata
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            
            return {
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'content_length': response.get('ContentLength', 0),
                'metadata': response.get('Metadata', {}),
                'last_modified': response.get('LastModified')
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404' or error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in R2: {storage_key}")
            else:
                logger.error(f"[R2_STORAGE] Get metadata failed for {storage_key}: {e}")
                raise Exception(f"Failed to get metadata from R2: {e}")
