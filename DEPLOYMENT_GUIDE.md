# 🚀 Deployment Guide - Unified Attachments with R2 Storage

## Pre-Deployment Checklist

### 1. Cloudflare R2 Setup ✅
- [ ] Cloudflare account created
- [ ] R2 enabled on account
- [ ] Bucket created (suggested name: `prosaasil-attachments` or `{company}-attachments`)
- [ ] R2 API Token created with permissions:
  - Object Read
  - Object Write
  - List (optional but recommended)
- [ ] Credentials saved securely

### 2. Dependencies ✅
```bash
# Install boto3 for R2 support
pip install boto3
# or with poetry
poetry add boto3
```

### 3. Environment Configuration ✅
```bash
# Copy template
cp .env.r2.example .env

# Edit .env with your actual values
nano .env

# Generate secure ATTACHMENT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Database Migration ✅
```bash
# Run migration 76 to create attachments table
python -m server.db_migrate

# Verify output:
# ✅ attachments table created
# ✅ Index created: idx_attachments_business
# ✅ Index created: idx_attachments_uploader
```

## Step-by-Step Deployment

### Step 1: Get Cloudflare R2 Credentials

#### A. Create R2 Bucket
1. Log in to Cloudflare Dashboard: https://dash.cloudflare.com
2. Navigate to **R2 Object Storage** in sidebar
3. Click **Create bucket**
4. Bucket name: `prosaasil-attachments` (or your choice)
5. Location: Choose closest to your users (or **Automatic**)
6. Click **Create bucket**

#### B. Create API Token
1. In R2, click **Manage R2 API Tokens**
2. Click **Create API Token**
3. Token name: `prosaasil-attachments-api`
4. Permissions:
   - ✅ Object Read & Write
5. Specify bucket:
   - Select your bucket: `prosaasil-attachments`
6. TTL: No expiration (or set as per policy)
7. Click **Create API Token**
8. **IMPORTANT**: Copy credentials immediately:
   - Access Key ID: `abc123...`
   - Secret Access Key: `xyz789...` (shown only once!)
9. Note your **Account ID** from R2 overview page

### Step 2: Configure Environment Variables

Create or edit `.env` file:

```bash
# Production mode
PRODUCTION=1

# Security - CHANGE THIS!
ATTACHMENT_SECRET=YOUR_GENERATED_SECRET_HERE

# Storage: R2 (not local!)
ATTACHMENT_STORAGE_DRIVER=r2

# Cloudflare R2
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=prosaasil-attachments
```

### Step 3: Install Dependencies

```bash
# Required for R2
pip install boto3

# Verify installation
python3 -c "import boto3; print(f'boto3 version: {boto3.__version__}')"
```

### Step 4: Run Database Migration

```bash
# Run migration
python -m server.db_migrate

# Expected output:
🔧 MIGRATION CHECKPOINT: Running Migration 76: Create attachments table
✅ attachments table created
✅ Index created: idx_attachments_business
✅ Index created: idx_attachments_uploader
✅ Storage directory ensured: /storage/attachments
✅ Migration 76 completed successfully
```

### Step 5: Test R2 Connection

```bash
# Start server
python -m server.app

# Check startup logs for:
✅ Using R2 (Cloudflare) storage provider
[R2_STORAGE] Initialized with bucket: prosaasil-attachments
[R2_STORAGE] Endpoint: https://your-account-id.r2.cloudflarestorage.com
[R2_STORAGE] ✅ Bucket access verified
```

**If you see errors:**
```
❌ R2 storage selected but missing environment variables: ...
⚠️ Falling back to local storage
```
→ Check your `.env` file - variables not loaded correctly

### Step 6: Test Upload

```bash
# Test upload via API
curl -X POST http://localhost:5000/api/attachments/upload \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -F "file=@test-image.jpg" \
  -F "channel=email"

# Expected response:
{
  "id": 1,
  "filename": "test-image.jpg",
  "mime_type": "image/jpeg",
  "file_size": 102400,
  "channel_compatibility": {
    "email": true,
    "whatsapp": true,
    "broadcast": true
  },
  "preview_url": "https://your-account-id.r2.cloudflarestorage.com/...?X-Amz-...",
  "created_at": "2026-01-18T21:00:00Z"
}
```

### Step 7: Verify in Cloudflare

1. Go to R2 Dashboard
2. Open your bucket
3. Navigate to: `attachments/{business_id}/2026/01/`
4. You should see your uploaded file: `1.jpg`

## Verification Checklist

After deployment, verify:

- [ ] Server starts without errors
- [ ] Logs show: "✅ Using R2 (Cloudflare) storage provider"
- [ ] Logs show: "[R2_STORAGE] ✅ Bucket access verified"
- [ ] Can upload file via UI (Email/WhatsApp/Broadcast pages)
- [ ] File appears in Cloudflare R2 bucket
- [ ] Can list attachments via API
- [ ] Can download attachment (presigned URL works)
- [ ] Multi-tenant isolation works (business A can't see business B's files)
- [ ] Signed URLs expire after TTL

## Troubleshooting

### Error: "boto3 not installed"
```bash
pip install boto3
# Verify
python3 -c "import boto3"
```

### Error: "Missing required environment variables"
Check `.env` file has all 4 R2 variables:
```bash
grep R2_ .env
# Should show 4 lines
```

### Error: "Cannot access R2 bucket"
1. Verify bucket name is exact (case-sensitive)
2. Verify API token has correct permissions
3. Verify Account ID is correct
4. Try creating new API token

### Error: "ATTACHMENT_SECRET not set in production"
```bash
# Generate new secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to .env
echo "ATTACHMENT_SECRET=<generated-secret>" >> .env
```

### Attachments still using local storage
Check startup logs:
```bash
# If you see:
⚠️ Falling back to local storage

# Then check:
echo $ATTACHMENT_STORAGE_DRIVER  # Should be: r2
# or
grep ATTACHMENT_STORAGE_DRIVER .env  # Should show: r2
```

### Files not appearing in R2 bucket
1. Check server logs for upload errors
2. Verify bucket permissions (not public, but API token has write access)
3. Check Cloudflare R2 console for any bucket-level restrictions

## Rollback Plan

If R2 has issues, instantly fallback to local storage:

```bash
# Option 1: Change ENV
export ATTACHMENT_STORAGE_DRIVER=local
# Restart server

# Option 2: Remove R2 config (will auto-fallback)
unset R2_ACCOUNT_ID
# Restart server
```

System will automatically use local storage. Existing R2 files remain accessible via their signed URLs until they expire.

## Monitoring

### Key Metrics to Track
1. **Upload success rate**: Should be >99%
2. **Signed URL generation time**: Should be <100ms
3. **R2 API errors**: Should be 0
4. **Storage costs**: Track via Cloudflare dashboard

### Logs to Monitor
```bash
# Upload success
[R2_STORAGE] Uploaded: attachments/5/2026/01/123.jpg (102400 bytes)

# Signed URL generation
[R2_STORAGE] Generated presigned URL for ... (TTL: 900s)

# Errors (investigate immediately)
❌ [R2_STORAGE] Upload failed: ...
❌ [R2_STORAGE] Failed to generate presigned URL: ...
```

## Security Best Practices

1. **Never commit .env** - Already in .gitignore
2. **Rotate R2 API tokens** - Every 90 days recommended
3. **Use minimal permissions** - Only Object Read & Write needed
4. **Monitor usage** - Set up Cloudflare alerts for unusual activity
5. **Backup strategy** - R2 is durable, but consider backup policy
6. **ATTACHMENT_SECRET** - Must be 32+ random characters
7. **PRODUCTION=1** - Only set in actual production environment

## Cost Optimization

### R2 Pricing (2024)
- Storage: $0.015/GB/month
- Class A (writes): $4.50/million
- Class B (reads): $0.36/million  
- Egress: **FREE** 🎉

### Estimated Costs (Example)
- 10GB storage: $0.15/month
- 10,000 uploads/month: $0.045
- 100,000 downloads/month: $0.036
**Total: ~$0.23/month** for 10GB + 110K operations

### Tips
1. Use TTL to automatically expire old signed URLs
2. Clean up orphaned attachments periodically (soft-deleted records)
3. Compress images before upload (client-side if possible)
4. Set lifecycle policies in R2 for auto-archival (if needed)

## Support

If issues persist:
1. Check this deployment guide
2. Review R2_STORAGE_SETUP.md for technical details
3. Check Cloudflare R2 status page
4. Review server logs: `tail -f logs/app.log | grep R2_STORAGE`

## Post-Deployment

After successful deployment:
- [ ] Document actual bucket name in team wiki
- [ ] Store R2 credentials in secure vault (1Password, etc.)
- [ ] Set up monitoring/alerts
- [ ] Test from production URL
- [ ] Inform team that attachments are live
- [ ] Monitor costs in Cloudflare dashboard for first week

---

## Quick Reference

```bash
# Check storage provider
grep "Using.*storage provider" logs/app.log

# Test upload
curl -X POST https://your-domain.com/api/attachments/upload \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@test.jpg" \
  -F "channel=email"

# Check R2 bucket
# Go to: https://dash.cloudflare.com → R2 → your-bucket

# Fallback to local
export ATTACHMENT_STORAGE_DRIVER=local && restart
```

**System is production-ready! 🚀**
