# Backup & Restore Procedures

**Last Updated**: 2026-01-23  
**Status**: Production Ready

---

## Overview

This document describes what data must be backed up, how to perform backups, and how to restore in case of disaster. The ProSaaS system stores data in three layers:

1. **External Managed Services** (Database, R2 Storage)
2. **Docker Volumes** (n8n workflows, WhatsApp sessions)
3. **Ephemeral/Cache** (Redis, temporary recordings)

---

## What Must Be Backed Up

### 🔴 Critical (Must Backup)

#### 1. Database (External Managed Service)
- **Provider**: Supabase / Railway / Neon (via `DATABASE_URL`)
- **Contains**: 
  - Business accounts, users, leads
  - Call logs, recordings metadata
  - AI prompts, topics, FAQs
  - Contracts, receipts metadata
  - Calendar appointments
- **Impact if Lost**: Total data loss - system non-functional
- **Backup Method**: Use provider's automated backup
- **RTO**: 1 hour
- **RPO**: 15 minutes (provider-dependent)

**Action Required**:
```bash
# Verify database backups are enabled in your provider's dashboard
# Examples:
# - Supabase: Settings → Database → Backups
# - Railway: Database → Backups
# - Neon: Console → Project → Backups
```

#### 2. n8n_data Volume
- **Docker Volume**: `prosaasil_n8n_data`
- **Mount Point**: `/home/node/.n8n`
- **Contains**:
  - n8n workflows (automation logic)
  - Credentials (API keys, OAuth tokens)
  - Workflow execution history
  - n8n encryption keys
- **Impact if Lost**: All automation workflows gone, credentials lost
- **Backup Frequency**: Weekly manual backup recommended
- **RTO**: 30 minutes
- **RPO**: 1 week (manual backup)

**Backup Command**:
```bash
# Create timestamped backup
docker run --rm \
  -v prosaasil_n8n_data:/data \
  -v $(pwd)/backups:/backup \
  alpine \
  tar czf /backup/n8n_data_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Output: backups/n8n_data_20260123_140530.tar.gz
```

#### 3. whatsapp_auth Volume
- **Docker Volume**: `prosaasil_whatsapp_auth`
- **Mount Point**: `/app/storage/whatsapp`
- **Contains**:
  - WhatsApp session files (QR code auth state)
  - Connection credentials for each business
- **Impact if Lost**: All users must re-authenticate WhatsApp (scan QR code again)
- **Backup Frequency**: Weekly manual backup recommended
- **RTO**: 10 minutes (restore) + re-auth time per business
- **RPO**: 1 week (manual backup)

**Backup Command**:
```bash
# Create timestamped backup
docker run --rm \
  -v prosaasil_whatsapp_auth:/data \
  -v $(pwd)/backups:/backup \
  alpine \
  tar czf /backup/whatsapp_auth_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Output: backups/whatsapp_auth_20260123_140530.tar.gz
```

#### 4. R2 Storage (External Cloudflare Service)
- **Provider**: Cloudflare R2 (via `R2_*` environment variables)
- **Contains**:
  - Uploaded attachments (CRM files)
  - Contract PDFs and signatures
  - Receipt images
  - Email attachments
  - Call recordings (after upload from recordings_data volume)
- **Impact if Lost**: All uploaded files gone, contracts unreadable
- **Backup Method**: R2 has built-in redundancy + object versioning
- **RTO**: 0 minutes (R2 is replicated)
- **RPO**: 0 minutes (R2 is real-time)

**Action Required**:
```bash
# Enable R2 object versioning in Cloudflare dashboard:
# 1. Go to: Cloudflare Dashboard → R2 → Your Bucket
# 2. Settings → Object Versioning → Enable
# 3. Set retention policy: Keep 30 versions or 30 days
```

### 🟡 Optional (Good to Have)

#### recordings_data Volume
- **Docker Volume**: `prosaasil_recordings_data`
- **Mount Point**: `/app/server/recordings`
- **Contains**: Temporary call recordings before upload to R2
- **Impact if Lost**: Minimal - recordings already uploaded to R2
- **Backup**: Not necessary (R2 is the source of truth)

---

## What Can Be Skipped

### ✅ Redis
- **Purpose**: Cache only (capacity counters, session state)
- **Impact if Lost**: None - rebuilt automatically on restart
- **Backup**: Not needed

### ✅ recordings_data (if R2 upload succeeds)
- **Purpose**: Temporary cache before R2 upload
- **Impact if Lost**: None - recordings already in R2
- **Backup**: Optional (not critical)

---

## Backup Procedures

### Automated Backups

#### Database
- **Provider**: Configured in your database provider's dashboard
- **Frequency**: Every 15 minutes (provider-dependent)
- **Retention**: 7-30 days (provider-dependent)
- **Verification**: Check provider dashboard for latest backup timestamp

#### R2 Storage
- **Provider**: Cloudflare R2 (built-in redundancy)
- **Frequency**: Real-time replication across regions
- **Retention**: Enable versioning for 30 days
- **Verification**: Check Cloudflare dashboard → R2 → Bucket → Settings

### Manual Backups

#### Weekly Volume Backup Script
Create a file `backup_volumes.sh`:
```bash
#!/bin/bash
# ProSaaS Volume Backup Script
# Run weekly via cron: 0 2 * * 0 /path/to/backup_volumes.sh

BACKUP_DIR="/path/to/secure/backup/location"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup n8n_data
echo "Backing up n8n_data..."
docker run --rm \
  -v prosaasil_n8n_data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine \
  tar czf /backup/n8n_data_$TIMESTAMP.tar.gz /data

# Backup whatsapp_auth
echo "Backing up whatsapp_auth..."
docker run --rm \
  -v prosaasil_whatsapp_auth:/data \
  -v "$BACKUP_DIR":/backup \
  alpine \
  tar czf /backup/whatsapp_auth_$TIMESTAMP.tar.gz /data

# Optional: Backup recordings_data
# echo "Backing up recordings_data..."
# docker run --rm \
#   -v prosaasil_recordings_data:/data \
#   -v "$BACKUP_DIR":/backup \
#   alpine \
#   tar czf /backup/recordings_data_$TIMESTAMP.tar.gz /data

# Remove backups older than 30 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
```

**Setup Cron Job**:
```bash
# Make script executable
chmod +x backup_volumes.sh

# Add to crontab (run every Sunday at 2 AM)
crontab -e
# Add line:
0 2 * * 0 /path/to/backup_volumes.sh >> /var/log/prosaas-backup.log 2>&1
```

---

## Restore Procedures

### Database Restore

**Prerequisites**:
- Latest database backup from provider
- Database credentials (`DATABASE_URL`)

**Steps**:
```bash
# 1. Stop all services to prevent write conflicts
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# 2. Restore via your database provider
# Example for Supabase:
supabase db restore --project-ref <project-ref> --backup-id <backup-id>

# Example for Railway:
railway db restore --service <service-id> --backup <backup-id>

# Example for Neon:
# Use Neon console → Project → Backups → Restore

# 3. Verify database connection
docker compose run --rm prosaas-api python -c "from server.db import db; db.engine.execute('SELECT 1')"

# 4. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Volume Restore

**Prerequisites**:
- Backup files (`n8n_data_*.tar.gz`, `whatsapp_auth_*.tar.gz`)
- Services stopped

**Steps**:
```bash
# 1. Stop services
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# 2. Restore n8n_data
docker run --rm \
  -v prosaasil_n8n_data:/data \
  -v $(pwd)/backups:/backup \
  alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/n8n_data_20260123_140530.tar.gz -C /"

# 3. Restore whatsapp_auth
docker run --rm \
  -v prosaasil_whatsapp_auth:/data \
  -v $(pwd)/backups:/backup \
  alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/whatsapp_auth_20260123_140530.tar.gz -C /"

# 4. Verify volume restoration
docker run --rm -v prosaasil_n8n_data:/data alpine ls -la /data
docker run --rm -v prosaasil_whatsapp_auth:/data alpine ls -la /data

# 5. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### R2 Storage Restore

**Prerequisites**:
- R2 versioning enabled (preventative)
- Cloudflare dashboard access

**Steps**:
```bash
# Via Cloudflare Dashboard:
# 1. Go to: Cloudflare Dashboard → R2 → Your Bucket → Browse
# 2. Find the object you want to restore
# 3. Click on the object → Version History
# 4. Select the version to restore → Restore

# Via CLI (if needed):
wrangler r2 object get <bucket-name>/<object-key> --version-id <version-id>
```

---

## Disaster Recovery Scenarios

### Scenario 1: Database Corruption

**Symptoms**:
- Database connection errors
- Data inconsistency
- Migration failures

**Recovery**:
1. Stop services: `docker compose down`
2. Restore database from latest backup (see Database Restore above)
3. Verify migrations: `docker compose run --rm prosaas-api python -m server.db_migrate`
4. Start services: `docker compose up -d`
5. Verify health: `curl https://prosaas.pro/health`

**RTO**: 1 hour  
**RPO**: 15 minutes

### Scenario 2: n8n Workflows Lost

**Symptoms**:
- n8n workflows missing
- Automation not working
- n8n credentials lost

**Recovery**:
1. Stop n8n: `docker compose stop n8n`
2. Restore n8n_data volume (see Volume Restore above)
3. Start n8n: `docker compose start n8n`
4. Verify workflows: Access https://prosaas.pro/n8n

**RTO**: 30 minutes  
**RPO**: 1 week (last manual backup)

### Scenario 3: WhatsApp Sessions Lost

**Symptoms**:
- WhatsApp not connecting
- QR code required again
- Session authentication failures

**Recovery**:
1. Stop baileys: `docker compose stop baileys`
2. Restore whatsapp_auth volume (see Volume Restore above)
3. Start baileys: `docker compose start baileys`
4. If restore fails: Businesses must re-scan QR codes

**RTO**: 10 minutes (restore) or 5 minutes per business (re-auth)  
**RPO**: 1 week (last manual backup)

### Scenario 4: Complete Server Loss

**Symptoms**:
- Server hardware failure
- Hosting provider outage
- Data center disaster

**Recovery**:
1. Provision new server with same domain/IP
2. Install Docker: `curl -fsSL https://get.docker.com | sh`
3. Clone repository: `git clone <repo-url>`
4. Restore .env file: Copy from secure backup location
5. Create Docker network: `docker network create prosaas-net`
6. Restore database (see Database Restore)
7. Restore volumes (see Volume Restore)
8. Start services: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
9. Verify all services healthy
10. Update DNS if IP changed

**RTO**: 2-4 hours  
**RPO**: 15 minutes (database), 1 week (volumes)

---

## Backup Verification

### Monthly Verification Procedure

**Test Restore in Staging Environment**:
```bash
# 1. Set up staging environment (separate domain/IP)
# 2. Restore latest backups
# 3. Verify data integrity
# 4. Test critical functionality:
#    - User login
#    - WhatsApp connection
#    - n8n workflows
#    - Call recording playback
#    - Contract viewing
# 5. Document any issues
# 6. Destroy staging environment
```

**Checklist**:
- [ ] Database restored successfully
- [ ] n8n workflows present and functional
- [ ] WhatsApp sessions restore without re-auth
- [ ] R2 files accessible
- [ ] All services start without errors
- [ ] Health checks pass

---

## Backup Storage Recommendations

### Off-Site Backup Storage

**Recommended Providers**:
- AWS S3 (with versioning)
- Backblaze B2
- Google Cloud Storage
- Encrypted local backup + offline storage

**Requirements**:
- ✅ Encrypted at rest
- ✅ Encrypted in transit
- ✅ Geographic redundancy
- ✅ Access logging
- ✅ 30-day retention minimum

### Security Best Practices

1. **Encrypt Backups**:
   ```bash
   # Encrypt before upload
   tar czf - /data | openssl enc -aes-256-cbc -pbkdf2 -out backup.tar.gz.enc
   
   # Decrypt for restore
   openssl enc -d -aes-256-cbc -pbkdf2 -in backup.tar.gz.enc | tar xzf -
   ```

2. **Limit Access**:
   - Use dedicated backup service account
   - Rotate credentials quarterly
   - Enable MFA on backup storage

3. **Test Restores**:
   - Monthly test restores in staging
   - Document restore time
   - Update procedures as needed

---

## Monitoring & Alerting

### Backup Health Checks

**Database Backups**:
```bash
# Check last backup timestamp via provider API or dashboard
# Alert if last backup > 24 hours old
```

**Volume Backups**:
```bash
# Check last backup file timestamp
find /backup -name "n8n_data_*.tar.gz" -mtime -7 -ls
find /backup -name "whatsapp_auth_*.tar.gz" -mtime -7 -ls

# Alert if no backup in last 7 days
```

**R2 Storage**:
```bash
# Verify versioning enabled via Cloudflare API
# Alert if versioning disabled
```

### Recommended Alerts

1. **Database backup failed** (Critical)
2. **Volume backup script failed** (High)
3. **Backup older than 7 days** (Medium)
4. **R2 versioning disabled** (High)

---

## Compliance & Retention

### Data Retention Policy

- **Database Backups**: 30 days (provider-dependent)
- **Volume Backups**: 30 days (manual cleanup)
- **R2 Versions**: 30 days (configurable)
- **Audit Logs**: 90 days (compliance)

### Legal Considerations

- Backups contain customer data (PII)
- Must be encrypted at rest
- Must be geographically compliant (GDPR, local laws)
- Access must be logged and monitored

---

## Summary

### Critical Backups (Must Have)
1. ✅ **Database**: Automated via provider (every 15 min)
2. ✅ **n8n_data**: Manual weekly backup
3. ✅ **whatsapp_auth**: Manual weekly backup
4. ✅ **R2 Storage**: Versioning enabled

### Recovery Targets
- **RTO (Recovery Time)**: 2-4 hours (complete system)
- **RPO (Recovery Point)**: 15 minutes (database), 1 week (volumes)

### Action Items
- [ ] Verify database backups enabled
- [ ] Enable R2 versioning
- [ ] Set up weekly volume backup cron job
- [ ] Test restore procedure monthly
- [ ] Document backup storage location

---

**Questions?** Contact DevOps or refer to deployment documentation.
