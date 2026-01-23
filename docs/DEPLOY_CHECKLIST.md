# Deployment Checklist — ProSaaS

**Last Updated**: 2026-01-23  
**Version**: 1.0  
**Environment**: Production

---

## PRE-DEPLOYMENT

### 1. Environment Variables (Critical)

#### Security & Authentication
- [ ] `PRODUCTION=1` — Enable production mode
- [ ] `SECRET_KEY` — Session secret (generate: `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `COOKIE_SECURE=true` — HTTPS-only cookies (enforced in production)
- [ ] `INTERNAL_SECRET` — Internal service authentication (generate: `openssl rand -hex 32`)

#### Database
- [ ] `DATABASE_URL` — External managed database connection string
  - Format: `postgresql://user:password@host:5432/database?sslmode=require`
  - Provider: Supabase / Railway / Neon
  - Verify connection: `psql $DATABASE_URL -c "SELECT 1"`

#### Redis Cache
- [ ] `REDIS_URL` — Defaults to `redis://redis:6379/0` (internal Docker)
  - No external Redis needed (runs in Docker)

#### Twilio (Phone Calls)
- [ ] `TWILIO_ACCOUNT_SID` — Twilio account SID (starts with `AC...`)
- [ ] `TWILIO_AUTH_TOKEN` — Twilio auth token
- [ ] `TWILIO_PHONE_NUMBER` — Twilio phone number (format: `+1234567890`)
- [ ] `VALIDATE_TWILIO_SIGNATURE=true` — Verify webhook signatures (production)

#### OpenAI (AI Calls)
- [ ] `OPENAI_API_KEY` — OpenAI API key (starts with `sk-...`)
- [ ] `USE_REALTIME_API=true` — Use OpenAI Realtime API (recommended)
- [ ] `DISABLE_GOOGLE=true` — Disable Google TTS/STT (production stability)

#### Storage (Cloudflare R2)
- [ ] `ATTACHMENT_STORAGE_DRIVER=r2` — **REQUIRED** in production
- [ ] `ATTACHMENT_SECRET` — Encryption key (generate: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] `R2_ACCOUNT_ID` — Cloudflare account ID
- [ ] `R2_BUCKET_NAME` — R2 bucket name (e.g., `prosaas-attachments`)
- [ ] `R2_ACCESS_KEY_ID` — R2 access key
- [ ] `R2_SECRET_ACCESS_KEY` — R2 secret key
- [ ] `R2_ENDPOINT` — R2 endpoint (format: `https://ACCOUNT_ID.r2.cloudflarestorage.com`)

#### n8n Automation (v2.5.1)
- [ ] `N8N_ENCRYPTION_KEY` — **NO DEFAULT** (generate: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] `N8N_JWT_SECRET` — **NO DEFAULT** (generate: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)
- [ ] `N8N_HOST` — n8n domain (e.g., `n8n.prosaas.pro`)
- [ ] `N8N_PROTOCOL=https` — HTTPS required
- [ ] `N8N_EDITOR_BASE_URL` — Full editor URL (e.g., `https://n8n.prosaas.pro`)
- [ ] `N8N_WEBHOOK_URL` — Webhook base URL (e.g., `https://n8n.prosaas.pro`)
- [ ] `N8N_DB_HOST`, `N8N_DB_PORT`, `N8N_DB_NAME`, `N8N_DB_USER`, `N8N_DB_PASSWORD` — n8n database

#### WhatsApp (Baileys)
- [ ] `BAILEYS_BASE_URL=http://baileys:3300` — Internal Docker service
- [ ] `WHATSAPP_WEBHOOK_SECRET` — Webhook secret (generate: `openssl rand -hex 32`)

#### Calls Capacity
- [ ] `MAX_ACTIVE_CALLS=15` — Maximum concurrent calls (increase as needed)
- [ ] `CALLS_OVER_CAPACITY_BEHAVIOR=reject` — Behavior when at capacity

#### Optional (Good to Have)
- [ ] `SENDGRID_API_KEY` — For password reset emails (optional)
- [ ] `MAIL_FROM_EMAIL` — Sender email (e.g., `noreply@prosaas.pro`)
- [ ] `ENCRYPTION_KEY` — For Gmail OAuth tokens (if using Gmail sync)
- [ ] `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Gmail API credentials

### 2. External Dependencies

#### Database
- [ ] Database provisioned and accessible
- [ ] Connection tested: `psql $DATABASE_URL -c "SELECT 1"`
- [ ] Automated backups enabled (verify in provider dashboard)
- [ ] Retention policy: 7-30 days minimum

#### R2 Storage
- [ ] R2 bucket created in Cloudflare dashboard
- [ ] Bucket is **not** public (private access only)
- [ ] CORS configured (if needed for frontend uploads)
- [ ] Object versioning enabled (Settings → Versioning)

#### SSL/TLS Certificates
- [ ] SSL certificates obtained (Cloudflare Origin / Let's Encrypt)
- [ ] Certificates placed in `docker/nginx/ssl/`:
  - `prosaas-origin.crt`
  - `prosaas-origin.key`
- [ ] Certificates valid for 90+ days

#### DNS
- [ ] Domain pointing to server IP
- [ ] DNS propagation complete (test: `dig prosaas.pro`)
- [ ] Subdomain for n8n (if needed): `n8n.prosaas.pro`

### 3. Docker Environment

#### Docker Network
```bash
# Create Docker network (must exist before compose up)
docker network create prosaas-net
```
- [ ] Network created: `docker network ls | grep prosaas-net`

#### Docker Volumes
Volumes are created automatically, but verify they don't exist from previous deployment:
```bash
docker volume ls | grep prosaasil
```
- [ ] `prosaasil_n8n_data` — n8n workflows
- [ ] `prosaasil_recordings_data` — Call recordings cache
- [ ] `prosaasil_whatsapp_auth` — WhatsApp sessions

If volumes exist from old deployment, decide:
- **Keep**: Data persists (recommended for upgrades)
- **Remove**: Fresh start (only for fresh installs)

### 4. Pre-Deployment Verification

#### Configuration Files
- [ ] `.env` file created (copy from `.env.example`)
- [ ] All required variables set (no `CHANGE_ME` or placeholder values)
- [ ] No secrets in git: `git status` shows `.env` ignored
- [ ] `docker-compose.yml` unchanged (base config)
- [ ] `docker-compose.prod.yml` unchanged (production overrides)

#### Code Review
- [ ] Latest code pulled: `git pull origin main`
- [ ] No uncommitted changes: `git status` clean
- [ ] Tests passed (if applicable)
- [ ] Security scan passed (if applicable)

---

## DEPLOYMENT

### Step 1: Pull Latest Code
```bash
cd /home/runner/work/prosaasil/prosaasil
git pull origin main
```
- [ ] Code pulled successfully
- [ ] Correct branch: `main` or production branch

### Step 2: Verify Docker Network
```bash
docker network create prosaas-net 2>/dev/null || echo "Network already exists"
```
- [ ] Network exists: `docker network inspect prosaas-net`

### Step 3: Build Docker Images
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
```
- [ ] All images built successfully (no errors)
- [ ] Image tags: `prosaasil-nginx`, `prosaasil-prosaas-api`, `prosaasil-prosaas-calls`, etc.

**Time**: ~5-10 minutes depending on cache

### Step 4: Start Services
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```
- [ ] All services started
- [ ] No immediate exit or crash loops

### Step 5: Monitor Startup
```bash
# Watch logs for all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Or watch specific services
docker compose logs prosaas-api -f
docker compose logs prosaas-calls -f
docker compose logs worker -f
docker compose logs baileys -f
docker compose logs n8n -f
```

**Expected Startup Time**: 30-60 seconds

---

## POST-DEPLOYMENT VERIFICATION

### 1. Service Health

#### Check Service Status
```bash
docker compose ps
```
**Expected Output**:
```
NAME                    STATUS              PORTS
prosaasil-nginx-1       Up (healthy)        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
prosaasil-prosaas-api-1 Up (healthy)        5000/tcp
prosaasil-prosaas-calls-1 Up (healthy)      5050/tcp
prosaasil-worker-1      Up (healthy)
prosaasil-baileys-1     Up (healthy)        3300/tcp
prosaasil-redis-1       Up (healthy)        6379/tcp
prosaasil-n8n-1         Up                  5678/tcp
prosaasil-frontend-1    Up (healthy)        80/tcp
```
- [ ] All services showing `Up` or `Up (healthy)`
- [ ] No services in restart loop

#### Health Check Endpoints
```bash
# Main health check
curl https://prosaas.pro/health
# Expected: {"status":"ok"}

# Detailed health (calls capacity)
curl https://prosaas.pro/health/details
# Expected: {"status":"ok","active_calls":0,"max_calls":15,"capacity_available":15,"at_capacity":false}

# API health (database check)
curl https://prosaas.pro/api/health
# Expected: {"status":"ok","database":"connected"}
```
- [ ] Main health returns `200 OK`
- [ ] Capacity check shows `active_calls: 0`
- [ ] Database connected

### 2. Log Verification

#### prosaas-api Service
```bash
docker compose logs prosaas-api | grep -E "CRITICAL|ERROR|Database ready|PRODUCTION"
```
**Check for**:
- [ ] `✅ Database ready - connectivity and schema validated`
- [ ] `PRODUCTION=1` detected (if production mode enabled)
- [ ] No `❌ CRITICAL: No database configuration found`
- [ ] No `❌ SECURITY: PRODUCTION=1 requires COOKIE_SECURE=true`
- [ ] No `❌ CRITICAL: ATTACHMENT_SECRET is still set to default value`

#### prosaas-calls Service
```bash
docker compose logs prosaas-calls | grep -E "CRITICAL|ERROR|worker|capacity"
```
**Check for**:
- [ ] Single worker confirmed (no multi-worker warnings)
- [ ] `[CAPACITY]` logs showing initialization with `MAX_ACTIVE_CALLS=15`
- [ ] No `Over capacity` errors on startup
- [ ] No `❌ CRITICAL` errors

#### worker Service
```bash
docker compose logs worker | grep -E "ERROR|Redis|RQ"
```
**Check for**:
- [ ] Redis connection successful
- [ ] RQ queues initialized: `high,default,low,receipts,receipts_sync`
- [ ] No Redis connection errors

#### baileys Service (WhatsApp)
```bash
docker compose logs baileys | grep -E "ERROR|health|3300"
```
**Check for**:
- [ ] Service listening on port 3300
- [ ] Health check responding
- [ ] No connection errors to prosaas-api

#### n8n Service
```bash
docker compose logs n8n | grep -E "ERROR|Database|Encryption"
```
**Check for**:
- [ ] Database connection successful
- [ ] Encryption key loaded
- [ ] Workflows loaded (if any exist)
- [ ] No `N8N_ENCRYPTION_KEY` missing errors

#### nginx Service
```bash
docker compose logs nginx | grep -E "ERROR|listening|443"
```
**Check for**:
- [ ] Listening on port 80 (HTTP)
- [ ] Listening on port 443 (HTTPS)
- [ ] SSL certificates loaded (if HTTPS enabled)
- [ ] No upstream connection errors

### 3. Database Verification

#### Check Migrations
```bash
docker compose exec prosaas-api python -m server.db_migrate --verify
```
- [ ] All migrations applied
- [ ] No schema drift warnings
- [ ] No critical column missing errors

#### Check Database Connection
```bash
docker compose exec prosaas-api python -c "from server.db import db; print('DB OK')"
```
- [ ] Output: `DB OK`
- [ ] No connection errors

### 4. Redis Verification

#### Check Redis Connection
```bash
docker compose exec redis redis-cli ping
```
- [ ] Output: `PONG`

#### Check Capacity Keys
```bash
docker compose exec redis redis-cli SCARD calls:active
```
- [ ] Output: `0` (no active calls on startup)

### 5. Frontend Verification

#### Access Web UI
```bash
curl -I https://prosaas.pro/
```
- [ ] Status: `200 OK`
- [ ] Content-Type: `text/html`

**Manual Test**:
- [ ] Open browser: https://prosaas.pro
- [ ] Login page loads
- [ ] No 404 errors
- [ ] No JavaScript console errors

### 6. Webhook Verification

#### Test Twilio Webhook
```bash
curl -X POST https://prosaas.pro/webhook/incoming_call \
  -d "CallSid=TEST123" \
  -d "From=+1234567890" \
  -d "To=+0987654321"
```
- [ ] Response: TwiML XML (not 500 error)
- [ ] Logs show webhook received

**Note**: This is a test call - it won't actually connect. Real test in Step 8.

---

## FIRST CALL TEST (Critical)

### Step 7: Test Live Call

**Prerequisites**:
- [ ] Twilio webhook configured: `https://prosaas.pro/webhook/incoming_call`
- [ ] Test phone available

**Test Procedure**:
1. Call the Twilio number from a phone
2. Wait for connection
3. Speak to the AI
4. End the call

**Monitor Logs During Call**:
```bash
# Watch calls service
docker compose logs prosaas-calls -f | grep -E "CAPACITY|WebSocket|MediaStream"

# Watch capacity
watch -n 1 'curl -s https://prosaas.pro/health/details | jq .'
```

**Verification Checklist**:
- [ ] Call connects (no immediate hangup)
- [ ] AI responds to speech
- [ ] `[CAPACITY] ACQUIRED` log appears
- [ ] `active_calls` increments to 1
- [ ] Call completes successfully
- [ ] `[CAPACITY] RELEASED` log appears
- [ ] `active_calls` returns to 0
- [ ] Recording saved (check database or logs)

**If Call Fails**:
1. Check `docker compose logs prosaas-calls`
2. Check Twilio debugger: https://www.twilio.com/console/debugger
3. Verify `OPENAI_API_KEY` is valid
4. Verify `DATABASE_URL` connection

---

## MONITORING SETUP

### What to Monitor First Week

#### Calls Capacity
```bash
# Check active calls
curl https://prosaas.pro/health/details | jq '.active_calls'

# Check for stuck slots (should be 0 when no calls)
docker compose exec redis redis-cli SCARD calls:active
```
- [ ] Active calls tracked correctly
- [ ] Slots released after calls end
- [ ] No stuck slots accumulating

#### Database Connections
```bash
# Check database pool
docker compose logs prosaas-api | grep -i "pool"
```
- [ ] `pool_pre_ping` working (no stale connections)
- [ ] No connection pool exhaustion

#### Error Logs
```bash
# Check for critical errors
docker compose logs | grep -E "CRITICAL|ERROR" | tail -100
```
- [ ] No repeated errors
- [ ] No SECRET_KEY errors
- [ ] No CSRF errors (unless expected from P1 audit)

#### WhatsApp Sessions
```bash
# Check WhatsApp connections
docker compose logs baileys | grep -i "connection\|session"
```
- [ ] Sessions stable
- [ ] No repeated disconnections
- [ ] QR code only shown on first connection

---

## BACKUP VERIFICATION

### Post-Deployment Backup Check

#### Database Backups
- [ ] Verify automated backups running (check provider dashboard)
- [ ] Latest backup timestamp < 24 hours

#### Volume Backups
```bash
# Create initial backup
./backup_volumes.sh

# Verify backup files created
ls -lh backups/
```
- [ ] `n8n_data_*.tar.gz` created
- [ ] `whatsapp_auth_*.tar.gz` created
- [ ] Backup files have reasonable size (not empty)

#### R2 Versioning
- [ ] Access Cloudflare dashboard
- [ ] Navigate to R2 → Bucket → Settings
- [ ] Verify "Object Versioning" is **Enabled**

---

## ROLLBACK PROCEDURE

### If Deployment Fails

#### Immediate Rollback
```bash
# 1. Stop new deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# 2. Checkout previous version
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>

# 3. Rebuild (if needed)
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 4. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Verify health
curl https://prosaas.pro/health
```

#### Rollback Checklist
- [ ] Services started
- [ ] Health checks passing
- [ ] Test call successful
- [ ] Document rollback reason
- [ ] Create incident report

---

## FINAL CHECKLIST

### Pre-Go-Live
- [ ] All environment variables set
- [ ] External dependencies verified (DB, R2, DNS)
- [ ] Docker network and volumes ready
- [ ] SSL certificates valid
- [ ] Services deployed and healthy
- [ ] Health checks passing
- [ ] Database migrations applied
- [ ] First test call successful
- [ ] Monitoring configured
- [ ] Backups verified
- [ ] Rollback procedure tested

### Go-Live Approval
- [ ] Technical lead approval
- [ ] Stakeholder approval
- [ ] Incident response plan ready
- [ ] Support team notified

---

## SUPPORT & TROUBLESHOOTING

### Common Issues

#### Issue: Service won't start
```bash
# Check logs for specific service
docker compose logs <service-name>

# Common causes:
# - Missing environment variable
# - Database not accessible
# - Port conflict
# - Volume permission issues
```

#### Issue: Health check fails
```bash
# Check service status
docker compose ps

# Restart service
docker compose restart <service-name>

# Check dependencies
docker compose logs redis
docker compose logs prosaas-api
```

#### Issue: Calls not connecting
```bash
# Check calls service
docker compose logs prosaas-calls

# Check Twilio webhook configuration
# Verify OPENAI_API_KEY is valid
# Check capacity not at limit
curl https://prosaas.pro/health/details
```

### Emergency Contacts
- **Technical Lead**: [Contact Info]
- **DevOps**: [Contact Info]
- **On-Call**: [Contact Info]

---

**Deployment Date**: _____________  
**Deployed By**: _____________  
**Sign-Off**: _____________  
**Notes**: 

---

**Next Review**: 7 days post-deployment  
**Status**: ☐ Stable | ☐ Monitoring | ☐ Issues
