# 🚀 Deployment Checklist: R2 Storage & Critical Crash Fixes

## Critical Fixes Summary

This deployment includes **critical crash fixes** that must be deployed immediately:

### 🔥 Crash Fix #1: SQLAlchemy Reserved Word
- **Problem**: `metadata` is reserved by SQLAlchemy, causing immediate backend crash
- **Solution**: Renamed to `event_metadata` in `ContractSignEvent` model
- **Migration**: Migration 78 will automatically rename the database column

### 🔥 Crash Fix #2: Double App Creation  
- **Problem**: Flask app created multiple times causing "Business table already defined"
- **Solution**: Fixed singleton pattern in `asgi.py` with proper thread-safe locking

### 🔥 Production Safety: R2 Enforcement
- **Problem**: System silently falls back to local storage when R2 misconfigured
- **Solution**: In production mode, app will FAIL FAST if R2 is not properly configured

---

## Pre-Deployment Checklist

### 1. Environment Variables Setup

Ensure your `.env` file contains:

```bash
# Production Mode (REQUIRED)
PRODUCTION=1

# Storage Driver (REQUIRED for production)
ATTACHMENT_STORAGE_DRIVER=r2

# Attachment Secret (REQUIRED - generate new!)
ATTACHMENT_SECRET=<generate-with-command-below>

# Cloudflare R2 Configuration (ALL REQUIRED)
R2_ACCOUNT_ID=your-cloudflare-account-id
R2_BUCKET_NAME=prosaas-attachment
R2_ACCESS_KEY_ID=your-r2-access-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
R2_ENDPOINT=https://your-account-id.r2.cloudflarestorage.com
```

**Generate ATTACHMENT_SECRET:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Docker Compose Configuration

Verify `docker-compose.yml` includes R2 environment variables in the backend service:

```yaml
backend:
  environment:
    PRODUCTION: ${PRODUCTION:-0}
    ATTACHMENT_STORAGE_DRIVER: ${ATTACHMENT_STORAGE_DRIVER:-local}
    ATTACHMENT_SECRET: ${ATTACHMENT_SECRET}
    R2_ACCOUNT_ID: ${R2_ACCOUNT_ID}
    R2_BUCKET_NAME: ${R2_BUCKET_NAME}
    R2_ACCESS_KEY_ID: ${R2_ACCESS_KEY_ID}
    R2_SECRET_ACCESS_KEY: ${R2_SECRET_ACCESS_KEY}
    R2_ENDPOINT: ${R2_ENDPOINT}
```

### 3. R2 Bucket Setup

Ensure your R2 bucket is properly configured:

1. **Log in to Cloudflare Dashboard**: https://dash.cloudflare.com
2. **Navigate to R2**: R2 → Overview
3. **Create/Verify Bucket**: 
   - Name: `prosaas-attachment` (or your chosen name)
   - Location: Auto (recommended)
4. **Create API Token**:
   - Go to: R2 → Manage R2 API Tokens
   - Click: Create API Token
   - Permissions: Object Read & Write
   - Bucket: Select your bucket
   - **Save credentials immediately** (secret shown only once!)

---

## Deployment Steps

### Step 1: Stop Current Services

```bash
cd /opt/prosaasil
docker compose down
```

### Step 2: Update Code

```bash
git pull origin main
# or
git pull origin copilot/fix-storage-errors-r2-attachments
```

### Step 3: Verify Environment File

```bash
# Check that .env exists and has all required variables
cat .env | grep -E "PRODUCTION|ATTACHMENT_STORAGE_DRIVER|R2_"

# Verify values are set (not showing secrets)
docker compose exec backend env | grep -E "PRODUCTION|ATTACHMENT_STORAGE_DRIVER|R2_ACCOUNT_ID"
```

### Step 4: Start Services

```bash
docker compose up -d --build
```

### Step 5: Monitor Startup Logs

```bash
# Watch backend startup
docker compose logs -f backend

# Look for these SUCCESS indicators:
# ✅ R2 storage configuration validated successfully
# [R2_STORAGE] Initialized with bucket: prosaas-attachment
# [R2_STORAGE] ✅ Bucket access verified
```

### Step 6: Verify Database Migration

```bash
# Check migration 78 was applied
docker compose exec backend python3 -c "
from server.app_factory import create_app
from server.db import db
from sqlalchemy import text
app = create_app()
with app.app_context():
    result = db.session.execute(text(\"\"\"
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'contract_sign_events' AND column_name = 'event_metadata'
    \"\"\"))
    if result.fetchone():
        print('✅ Migration 78 completed: event_metadata column exists')
    else:
        print('❌ Migration 78 not applied: event_metadata column missing')
"
```

### Step 7: Verify R2 Storage

```bash
# Find the verify_r2_setup.py script
docker compose exec backend find /app -name "verify_r2_setup.py" -type f

# Run verification (use the path found above)
docker compose exec backend python3 /app/verify_r2_setup.py
```

---

## Expected Startup Behavior

### ✅ Success Indicators

Your backend should start with these logs:

```
[INFO] 🔒 Production mode detected - validating R2 storage configuration...
[INFO]    Validating R2 connection...
[INFO]    ✅ Storage provider initialized: R2StorageProvider
[INFO] ✅ R2 storage configuration validated successfully
[R2_STORAGE] Initialized with bucket: prosaas-attachment
[R2_STORAGE] Endpoint: https://xxxxx.r2.cloudflarestorage.com
[R2_STORAGE] ✅ Bucket access verified
```

### ❌ Failure Indicators & Solutions

#### Error: "PRODUCTION=1 but ATTACHMENT_STORAGE_DRIVER is not 'r2'"

**Solution:**
```bash
echo "ATTACHMENT_STORAGE_DRIVER=r2" >> .env
docker compose restart backend
```

#### Error: "Missing required R2 environment variables"

**Solution:**
```bash
# Add missing variables to .env
vim .env  # or nano .env

# Variables needed:
# R2_ACCOUNT_ID=...
# R2_BUCKET_NAME=...
# R2_ACCESS_KEY_ID=...
# R2_SECRET_ACCESS_KEY=...

docker compose restart backend
```

#### Error: "Attribute name 'metadata' is reserved"

**This should NOT happen** after this deployment. If you see it:
- Code was not properly updated
- Run: `git pull` and rebuild: `docker compose up -d --build`

#### Error: "Table 'business' is already defined"

**This should NOT happen** after this deployment. If you see it:
- Old code is still running
- Run: `docker compose down && docker compose up -d --build`

---

## Post-Deployment Verification

### Test File Upload

```bash
# Test attachment upload endpoint
curl -X POST http://localhost:5000/api/attachments/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf" \
  -F "business_id=1"

# Expected response:
# {"attachment_id": 123, "storage_path": "attachments/1/2026/01/123.pdf", ...}
```

### Check Logs for R2 Activity

```bash
# Watch for R2 storage operations
docker compose logs -f backend | grep R2_STORAGE

# Expected when files are uploaded:
# [R2_STORAGE] Uploaded: attachments/5/2026/01/123.pdf (102400 bytes)
# [R2_STORAGE] Generated presigned URL for ... (TTL: 900s)
```

### Verify No Local Storage Fallback

```bash
# In production, you should NEVER see this:
docker compose logs backend | grep "Using local filesystem storage"

# If you see it, R2 is not properly configured!
```

---

## Rollback Plan (If Needed)

If deployment fails and you need to roll back:

```bash
# 1. Stop services
docker compose down

# 2. Revert code to previous version
git reset --hard HEAD~2

# 3. For emergency: Allow local storage temporarily
echo "PRODUCTION=0" >> .env
echo "ATTACHMENT_STORAGE_DRIVER=local" >> .env

# 4. Restart
docker compose up -d

# 5. Notify team and fix R2 configuration before retry
```

---

## Final Checklist

Before marking deployment as complete:

- [ ] Backend starts without crashes
- [ ] No "metadata is reserved" errors in logs
- [ ] No "Business table already defined" errors in logs  
- [ ] R2 storage provider initialized successfully
- [ ] R2 bucket access verified
- [ ] Migration 78 completed (event_metadata column exists)
- [ ] File upload test successful
- [ ] Files stored in R2 (not local filesystem)
- [ ] Presigned URLs generated correctly
- [ ] No local storage fallback messages in logs
- [ ] All containers healthy: `docker compose ps`

---

## Support & Troubleshooting

### Debug Commands

```bash
# Check environment variables inside container
docker compose exec backend env | grep -E "PRODUCTION|ATTACHMENT|R2_"

# Check if metadata column still exists (should NOT exist)
docker compose exec backend python3 -c "
from server.app_factory import create_app
from server.db import db
from sqlalchemy import text
app = create_app()
with app.app_context():
    result = db.session.execute(text(\"\"\"
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'contract_sign_events' AND column_name = 'metadata'
    \"\"\"))
    if result.fetchone():
        print('❌ OLD metadata column still exists - migration not applied!')
    else:
        print('✅ Old metadata column removed')
"

# Test R2 connection manually
docker compose exec backend python3 -c "
import os
import boto3
from botocore.client import Config

account_id = os.getenv('R2_ACCOUNT_ID')
bucket = os.getenv('R2_BUCKET_NAME')
access_key = os.getenv('R2_ACCESS_KEY_ID')
secret_key = os.getenv('R2_SECRET_ACCESS_KEY')

s3 = boto3.client(
    's3',
    endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
    region_name='auto'
)

try:
    s3.head_bucket(Bucket=bucket)
    print(f'✅ R2 bucket {bucket} accessible')
except Exception as e:
    print(f'❌ R2 bucket access failed: {e}')
"
```

### Common Issues

1. **"ATTACHMENT_SECRET is still set to default value"**
   - Generate a new secret: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Update `.env` file
   - Restart: `docker compose restart backend`

2. **R2 credentials not working**
   - Verify credentials in Cloudflare dashboard
   - Check API token permissions (must have Read & Write)
   - Verify bucket name matches exactly
   - Check account ID is correct

3. **Files uploading to local storage instead of R2**
   - Check: `docker compose exec backend env | grep ATTACHMENT_STORAGE_DRIVER`
   - Should show: `ATTACHMENT_STORAGE_DRIVER=r2`
   - If not, update `.env` and restart

---

## Architecture Notes

### How R2 Storage Works

1. **Single Bucket**: All files (CRM, WhatsApp, Contracts) use ONE R2 bucket: `prosaas-attachment`
2. **Logical Separation**: Database tables separate file types:
   - `attachments` table: Physical storage references
   - `contract_files` table: Links contracts to attachments
   - `crm_files` / `whatsapp_files`: Same pattern
3. **Key Structure**: `attachments/{business_id}/{year}/{month}/{attachment_id}.ext`
4. **Access Control**: Presigned URLs with TTL (default 15 minutes)

### What Changed

**Before (Broken)**:
- `metadata` field name → SQLAlchemy crash
- Multiple app instances → "Business table defined twice" 
- Silent fallback to local → Files not in R2

**After (Fixed)**:
- `event_metadata` field name → No SQLAlchemy conflict
- Single app instance → Proper singleton pattern
- Fail-fast in production → Must configure R2 or app won't start

---

## Questions?

If you encounter issues not covered here:
1. Check full logs: `docker compose logs backend > backend.log`
2. Share relevant error messages
3. Verify all environment variables are set correctly

**Remember**: In production mode (`PRODUCTION=1`), the app will **fail fast** if R2 is not properly configured. This is by design to prevent silent failures!
