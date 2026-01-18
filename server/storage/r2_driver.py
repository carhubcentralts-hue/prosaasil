"""
Cloudflare R2 storage driver implementation
Uses boto3 S3-compatible API to interact with R2
"""
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import os
import logging
from typing import Optional, Dict, Any
from .driver import StorageDriver, StorageError

logger = logging.getLogger(__name__)


class R2StorageDriver(StorageDriver):
    """
    Cloudflare R2 storage implementation
    
    Uses S3-compatible API via boto3 to interact with Cloudflare R2.
    All files are stored as private objects with signed URL access.
    """
    
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str
    ):
        """
        Initialize R2 storage driver
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
        """
        self.bucket_name = bucket_name
        self.account_id = account_id
        
        # R2 endpoint URL format
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        # Initialize boto3 S3 client configured for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name='auto',  # R2 uses 'auto' as region
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        )
        
        logger.info(f"[R2_STORAGE] Initialized with bucket: {bucket_name}")
        
        # Verify bucket access
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"[R2_STORAGE] ✅ Bucket access verified")
        except ClientError as e:
            logger.error(f"[R2_STORAGE] ❌ Bucket access failed: {e}")
            raise StorageError(f"Failed to access R2 bucket: {e}")
    
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = 'application/octet-stream',
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload bytes to R2"""
        try:
            put_args = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': data,
                'ContentType': content_type,
            }
            
            # Add metadata if provided
            if metadata:
                put_args['Metadata'] = metadata
            
            self.s3_client.put_object(**put_args)
            logger.info(f"[R2_STORAGE] Uploaded: {key} ({len(data)} bytes)")
            return key
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Upload failed for {key}: {e}")
            raise StorageError(f"Failed to upload to R2: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete a file from R2"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"[R2_STORAGE] Deleted: {key}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"[R2_STORAGE] Delete failed - key not found: {key}")
                return False
            logger.error(f"[R2_STORAGE] Delete failed for {key}: {e}")
            raise StorageError(f"Failed to delete from R2: {e}")
    
    def presign_get(self, key: str, ttl_seconds: int = 900) -> str:
        """Generate presigned URL for downloading"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=ttl_seconds
            )
            logger.info(f"[R2_STORAGE] Generated presigned GET URL for {key} (TTL: {ttl_seconds}s)")
            return url
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Presign GET failed for {key}: {e}")
            raise StorageError(f"Failed to generate presigned URL: {e}")
    
    def presign_put(
        self,
        key: str,
        ttl_seconds: int = 900,
        content_type: Optional[str] = None
    ) -> str:
        """Generate presigned URL for uploading"""
        try:
            params = {
                'Bucket': self.bucket_name,
                'Key': key
            }
            
            if content_type:
                params['ContentType'] = content_type
            
            url = self.s3_client.generate_presigned_url(
                'put_object',
                Params=params,
                ExpiresIn=ttl_seconds
            )
            logger.info(f"[R2_STORAGE] Generated presigned PUT URL for {key} (TTL: {ttl_seconds}s)")
            return url
            
        except ClientError as e:
            logger.error(f"[R2_STORAGE] Presign PUT failed for {key}: {e}")
            raise StorageError(f"Failed to generate presigned upload URL: {e}")
    
    def exists(self, key: str) -> bool:
        """Check if file exists in R2"""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"[R2_STORAGE] Exists check failed for {key}: {e}")
            raise StorageError(f"Failed to check file existence: {e}")
    
    def get_metadata(self, key: str) -> Dict[str, Any]:
        """Get file metadata from R2"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            return {
                'size': response.get('ContentLength'),
                'content_type': response.get('ContentType'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise StorageError(f"File not found: {key}")
            logger.error(f"[R2_STORAGE] Get metadata failed for {key}: {e}")
            raise StorageError(f"Failed to get file metadata: {e}")
