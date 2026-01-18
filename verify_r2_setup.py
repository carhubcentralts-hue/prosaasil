#!/usr/bin/env python3
"""
Verification Script for R2 Storage Setup
Checks all requirements before going live with R2
"""

import os
import sys

def check_env_var(var_name, required=True):
    """Check if environment variable is set"""
    value = os.getenv(var_name)
    if value:
        if var_name in ['R2_SECRET_ACCESS_KEY', 'ATTACHMENT_SECRET']:
            # Don't print secrets
            print(f"✅ {var_name}: ***{value[-4:]}")
        else:
            print(f"✅ {var_name}: {value}")
        return True
    else:
        if required:
            print(f"❌ {var_name}: NOT SET (REQUIRED)")
            return False
        else:
            print(f"⚠️  {var_name}: Not set (optional)")
            return True

def check_boto3():
    """Check if boto3 is installed"""
    try:
        import boto3
        print(f"✅ boto3 installed: v{boto3.__version__}")
        return True
    except ImportError:
        print("❌ boto3 NOT installed")
        print("   Install with: pip install boto3")
        return False

def check_r2_connection():
    """Test R2 connection"""
    try:
        import boto3
        from botocore.client import Config
        
        account_id = os.getenv('R2_ACCOUNT_ID')
        access_key = os.getenv('R2_ACCESS_KEY_ID')
        secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        bucket_name = os.getenv('R2_BUCKET_NAME')
        
        if not all([account_id, access_key, secret_key, bucket_name]):
            print("⚠️  Skipping R2 connection test - credentials not set")
            return True
        
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        
        # Test bucket access
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ R2 connection successful: {bucket_name}")
        return True
        
    except Exception as e:
        print(f"❌ R2 connection failed: {e}")
        print("   Check credentials and bucket name")
        return False

def main():
    print("=" * 60)
    print("R2 STORAGE SETUP VERIFICATION")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # Check production mode
    print("📋 Production Configuration:")
    all_ok &= check_env_var('PRODUCTION', required=False)
    all_ok &= check_env_var('ATTACHMENT_SECRET', required=True)
    
    # Check if using default secret (BAD!)
    secret = os.getenv('ATTACHMENT_SECRET', '')
    if secret == 'change-me-in-production':
        print("❌ ATTACHMENT_SECRET is still set to default!")
        print("   Generate new: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        all_ok = False
    
    print()
    
    # Check storage driver
    print("📦 Storage Configuration:")
    driver = os.getenv('ATTACHMENT_STORAGE_DRIVER', 'local')
    print(f"   Storage driver: {driver}")
    
    if driver == 'r2':
        print("   → Using R2 storage (Cloudflare)")
    else:
        print("   → Using local storage")
        print("   ⚠️  To use R2, set: ATTACHMENT_STORAGE_DRIVER=r2")
    
    print()
    
    # Check R2 configuration
    print("🌐 Cloudflare R2 Configuration:")
    all_ok &= check_env_var('R2_ACCOUNT_ID', required=(driver=='r2'))
    all_ok &= check_env_var('R2_ACCESS_KEY_ID', required=(driver=='r2'))
    all_ok &= check_env_var('R2_SECRET_ACCESS_KEY', required=(driver=='r2'))
    all_ok &= check_env_var('R2_BUCKET_NAME', required=(driver=='r2'))
    print()
    
    # Check boto3
    print("📚 Dependencies:")
    all_ok &= check_boto3()
    print()
    
    # Test R2 connection if configured
    if driver == 'r2':
        print("🔌 Connection Test:")
        all_ok &= check_r2_connection()
        print()
    
    # Summary
    print("=" * 60)
    if all_ok:
        print("✅ ALL CHECKS PASSED - READY FOR PRODUCTION!")
        print()
        print("Next steps:")
        print("1. Run database migration: python -m server.db_migrate")
        print("2. Restart application")
        print("3. Test upload via UI or API")
        print("4. Verify files appear in R2 bucket")
    else:
        print("❌ SOME CHECKS FAILED - FIX ISSUES BEFORE DEPLOYING")
        print()
        print("See DEPLOYMENT_GUIDE.md for detailed instructions")
    print("=" * 60)
    
    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    main()
