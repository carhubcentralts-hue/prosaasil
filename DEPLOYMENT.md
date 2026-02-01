# Deployment Guide

This guide covers deploying ProSaaS to production environments.

## Prerequisites

### Required
- Docker & Docker Compose v2.x
- PostgreSQL database (managed service recommended: Railway, Neon, Supabase)
- Redis instance (optional, included in Docker setup)
- Domain with SSL certificate
- Minimum 2GB RAM, 2 vCPU per service

### External Services
- **Twilio**: Voice calling (SIP/WebRTC)
- **OpenAI**: AI conversation engine
- **Google Cloud**: Speech-to-Text, Text-to-Speech (optional)
- **Cloudflare R2 / S3**: Media storage (optional)

## Production Architecture

```
Internet
   ↓
Nginx (80/443) → Reverse Proxy
   ↓
   ├─→ Frontend (React SPA)
   ├─→ API Service (Flask)
   ├─→ Calls Service (WebSocket + AI)
   ├─→ N8N (Workflow Automation)
   └─→ Baileys (WhatsApp)
       ↓
   PostgreSQL Database
   Redis (Background Jobs)
```

## Step-by-Step Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/docker-compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd prosaasil

# Create environment file
cp .env.example .env
```

### 3. Configure Environment Variables

Edit `.env` with production values (see [ENVIRONMENT.md](./ENVIRONMENT.md)):

**Critical Settings:**
```bash
# Domain
PUBLIC_HOST=https://your-domain.com
PUBLIC_BASE_URL=https://your-domain.com

# Database (use connection pooler for API, direct for migrations)
DATABASE_URL_POOLER=postgresql://user:pass@host.pooler.supabase.com:5432/db
DATABASE_URL_DIRECT=postgresql://user:pass@host.db.supabase.com:5432/db

# Security
SECRET_KEY=<generate-random-64-char-string>
JWT_SECRET_KEY=<generate-random-64-char-string>

# APIs
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
```

Generate secure keys:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. SSL Certificates

Place SSL certificates in `docker/nginx/ssl/`:

```bash
mkdir -p docker/nginx/ssl
# Copy your certificates
cp /path/to/cert.pem docker/nginx/ssl/
cp /path/to/key.pem docker/nginx/ssl/
```

Or use Let's Encrypt:
```bash
sudo certbot certonly --standalone -d your-domain.com
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/nginx/ssl/key.pem
```

### 5. Build Docker Images

```bash
# Build all production images
docker compose -f docker-compose.prod.yml build

# This will build:
# - Backend API (Python/Flask)
# - Frontend (React/Vite)
# - Worker (Background jobs)
# - Baileys (WhatsApp service)
# - N8N (Workflow automation)
# - Nginx (Reverse proxy)
```

### 6. Run Database Migrations

```bash
# Ensure database is accessible
docker compose -f docker-compose.prod.yml run --rm migrate

# Verify migrations completed
docker compose -f docker-compose.prod.yml logs migrate
```

### 7. Start Production Services

```bash
# Start with production profile
docker compose -f docker-compose.prod.yml --profile prod up -d

# Check all services are healthy
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 8. Verify Deployment

```bash
# Health checks
curl https://your-domain.com/health
curl https://your-domain.com/api/health

# Check service status
docker compose -f docker-compose.prod.yml exec prosaas-api python -c "from server import db; print(db.engine.url)"
```

## Docker Compose Profiles

The application uses profiles to separate development and production services:

**Development** (default):
```bash
docker compose up
```
Starts: nginx, redis, postgres, backend, frontend, worker, baileys, n8n

**Production**:
```bash
docker compose --profile prod up
```
Starts: nginx, redis, migrate, prosaas-api, prosaas-calls, frontend, worker, baileys, n8n

## Nginx Configuration

The Nginx reverse proxy handles:
- SSL termination
- Request routing to services
- Static file serving
- WebSocket proxying for real-time features

Routes:
- `/` → Frontend (React SPA)
- `/api/*` → Backend API
- `/ws/calls/*` → WebSocket calls service
- `/n8n/*` → N8N workflow UI

## Database Migrations

**Important**: Always run migrations before deploying new code.

```bash
# Run migrations
docker compose -f docker-compose.prod.yml run --rm migrate

# Rollback (if needed)
# Migrations are forward-only; rollback requires restore from backup
```

### Migration Guidelines
- Use `DATABASE_URL_DIRECT` for migrations (not pooler)
- Migrations run automatically in Docker via the `migrate` service
- Never run migrations concurrently
- Always backup database before migrations

## Background Workers

The worker service processes:
- Call recordings and transcriptions
- Email sending (Gmail integration)
- WhatsApp message broadcasting
- Scheduled notifications
- Receipt processing

Worker runs via Redis Queue (RQ):
```bash
# Scale workers
docker compose -f docker-compose.prod.yml up -d --scale worker=3

# Monitor worker jobs
docker compose -f docker-compose.prod.yml exec worker python -m rq info
```

## Monitoring and Logs

```bash
# View logs for all services
docker compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker compose -f docker-compose.prod.yml logs -f prosaas-api
docker compose -f docker-compose.prod.yml logs -f worker

# Check resource usage
docker stats
```

## Backup and Restore

### Database Backup
```bash
# Backup PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U prosaas prosaas > backup_$(date +%Y%m%d).sql

# Or for external database
pg_dump $DATABASE_URL_DIRECT > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
# Restore PostgreSQL
psql $DATABASE_URL_DIRECT < backup_20240101.sql
```

## Scaling

### Horizontal Scaling
```bash
# Scale API service
docker compose -f docker-compose.prod.yml up -d --scale prosaas-api=3

# Scale workers
docker compose -f docker-compose.prod.yml up -d --scale worker=5
```

### Vertical Scaling
Edit `docker-compose.prod.yml` to adjust resource limits:
```yaml
services:
  prosaas-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Check health
docker compose -f docker-compose.prod.yml ps

# Restart service
docker compose -f docker-compose.prod.yml restart <service-name>
```

### Database connection issues
- Verify `DATABASE_URL_POOLER` is correct
- Check database server is accessible
- Ensure SSL mode matches database provider
- For Supabase: Use pooler URL for API, direct URL for migrations

### Migration failures
- Check `DATABASE_URL_DIRECT` is correct (not pooler)
- Ensure no concurrent migrations
- Review migration logs: `docker compose logs migrate`

## Security Checklist

- [ ] All secrets in `.env` (not in code)
- [ ] SSL certificates installed and valid
- [ ] Firewall configured (allow 80, 443 only)
- [ ] Database uses strong passwords
- [ ] Regular backups configured
- [ ] Monitoring and alerting setup
- [ ] Rate limiting enabled
- [ ] CSRF protection active

## Updates and Maintenance

```bash
# Pull latest changes
git pull origin main

# Rebuild images
docker compose -f docker-compose.prod.yml build

# Run migrations
docker compose -f docker-compose.prod.yml run --rm migrate

# Restart services with zero-downtime
docker compose -f docker-compose.prod.yml up -d --no-deps --build prosaas-api
```

## Environment-Specific Notes

### Railway
- Use Railway PostgreSQL plugin
- Set `DATABASE_URL` from Railway
- Configure custom domain in Railway settings

### AWS / DigitalOcean
- Use managed PostgreSQL (RDS/Managed Databases)
- Configure security groups for ports 80, 443
- Use load balancer for multiple instances

### Supabase
- **Critical**: Use separate pooler and direct URLs
- Pooler for API: `*.pooler.supabase.com`
- Direct for migrations: `*.db.supabase.com`
- Enable connection pooling in Supabase settings
