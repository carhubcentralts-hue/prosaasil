# Environment Variables

This document lists all environment variables required by ProSaaS.

## Core Configuration

### Domain & URLs
```bash
# Production domain (with protocol)
PUBLIC_HOST=https://your-domain.com
PUBLIC_BASE_URL=https://your-domain.com

# Docker network name
DOCKER_NETWORK_NAME=prosaas-net
```

## Database

### PostgreSQL Connection
```bash
# For Supabase (recommended): Use separate URLs
DATABASE_URL_POOLER=postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres
DATABASE_URL_DIRECT=postgresql://user:pass@xyz.db.supabase.com:5432/postgres

# For other providers (Railway, Neon, local): Use same URL for both
DATABASE_URL_POOLER=postgresql://user:pass@host:5432/database
DATABASE_URL_DIRECT=postgresql://user:pass@host:5432/database

# Legacy fallback (if POOLER/DIRECT not set)
DATABASE_URL=postgresql://user:pass@host:5432/database

# Local Docker PostgreSQL
POSTGRES_USER=prosaas
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=prosaas
DB_PORT=5432
```

**Important**: 
- Use `DATABASE_URL_POOLER` for API and worker connections
- Use `DATABASE_URL_DIRECT` for migrations and DDL operations
- For Supabase, pooler bypasses pgbouncer to prevent lock issues

## Security

### Authentication & Secrets
```bash
# Flask secret key for session signing and CSRF protection
# 🔒 CRITICAL: Generate a strong random secret in production
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-64-char-random-string-here

# Session configuration
SESSION_COOKIE_SECURE=true  # Set to false for local development
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

## AI Services

### OpenAI
```bash
# OpenAI API key for GPT models
OPENAI_API_KEY=sk-...

# Model configuration (optional)
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_TEMPERATURE=0.7
```

### Google Cloud (Optional)
```bash
# For Speech-to-Text and Text-to-Speech
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_CLOUD_PROJECT_ID=your-project-id

# Or use credentials JSON directly
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
```

### Google Gemini (Optional)
```bash
# For Gemini AI models
GOOGLE_GENAI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash-exp
```

## Communication Services

### Twilio (Voice Calls)
```bash
# Twilio account credentials
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# Phone numbers
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_VERIFY_SERVICE_SID=VA...  # For 2FA (optional)

# Voice configuration
TWILIO_VOICE_URL=${PUBLIC_BASE_URL}/api/voice/incoming
TWILIO_STATUS_CALLBACK_URL=${PUBLIC_BASE_URL}/api/voice/status
```

### WhatsApp (Baileys)
```bash
# WhatsApp service endpoint
BAILEYS_SERVICE_URL=http://baileys:3001
BAILEYS_WEBHOOK_SECRET=your-random-secret-here

# Storage (auth sessions stored in volume)
WHATSAPP_AUTH_PATH=/app/auth_info_baileys
```

### Gmail (Email Integration)
```bash
# Gmail API credentials for email sending/receiving
GMAIL_CREDENTIALS_JSON={"installed":{...}}
GMAIL_ENCRYPTION_KEY=your-32-byte-base64-key

# Generate encryption key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### SMS (Optional)
```bash
# BulkGate or other SMS provider
BULKGATE_APPLICATION_ID=...
BULKGATE_APPLICATION_TOKEN=...
```

## Storage

### Cloudflare R2 / AWS S3 (Optional)
```bash
# For media file storage (recordings, uploads)
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=prosaas-media

# S3-compatible endpoint
R2_ENDPOINT_URL=https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
```

### Local Storage (Development)
```bash
# Local file paths (used when R2 not configured)
RECORDINGS_PATH=/app/server/recordings
UPLOADS_PATH=/app/server/uploads
```

## Background Jobs

### Redis Queue (RQ)
```bash
# Redis connection
REDIS_URL=redis://redis:6379/0

# Worker configuration
RQ_WORKER_COUNT=2
RQ_QUEUE_TIMEOUT=3600  # 1 hour
```

## Service-Specific Variables

### API Service (prosaas-api)
```bash
# Flask configuration
FLASK_ENV=production
FLASK_DEBUG=false

# API settings
API_RATE_LIMIT=1000 per hour
MAX_CONTENT_LENGTH=16777216  # 16MB
```

### Calls Service (prosaas-calls)
```bash
# WebSocket settings
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS=100

# Audio processing
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
```

### Worker Service
```bash
# Job processing
WORKER_CONCURRENCY=4
WORKER_MAX_JOBS=1000

# Recording processing
RECORDING_WORKER_ENABLED=true
TRANSCRIPTION_ENABLED=true
```

### N8N (Workflow Automation)
```bash
# N8N configuration
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your-secure-password

# N8N paths
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=https
N8N_PATH=/n8n/

# Webhook base URL
WEBHOOK_URL=${PUBLIC_BASE_URL}/n8n/
```

## Feature Flags

### Optional Features
```bash
# Enable/disable features
ENABLE_CALL_RECORDING=true
ENABLE_TRANSCRIPTION=true
ENABLE_EMAIL_SYNC=true
ENABLE_WHATSAPP_BOT=true
ENABLE_CALENDAR_INTEGRATION=true

# AI Features
ENABLE_VOICE_AI=true
ENABLE_GEMINI_VOICES=false  # Experimental
```

## Monitoring & Logging

### Logging
```bash
# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Log format
LOG_FORMAT=json  # or 'text'

# Sentry error tracking (optional)
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
```

## Development Only

### Local Development
```bash
# Development mode
FLASK_ENV=development
FLASK_DEBUG=true

# CORS (allow all origins in dev)
CORS_ORIGINS=*

# Database (local Docker)
DATABASE_URL=postgresql://prosaas:password@localhost:5432/prosaas

# Disable SSL requirements
SESSION_COOKIE_SECURE=false
```

## Environment File Example

Create `.env` from this template:

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit with your values
nano .env
```

Minimal production `.env`:
```bash
# Domain
PUBLIC_HOST=https://your-domain.com
PUBLIC_BASE_URL=https://your-domain.com

# Database
DATABASE_URL_POOLER=postgresql://...
DATABASE_URL_DIRECT=postgresql://...

# Security
SECRET_KEY=<64-char-random>

# AI
OPENAI_API_KEY=sk-...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Redis
REDIS_URL=redis://redis:6379/0
```

## Security Notes

⚠️ **Never commit `.env` files to version control!**

- Use `.env.example` as template (without actual secrets)
- Generate strong random key for SECRET_KEY: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Rotate credentials regularly
- Use environment-specific values (dev/staging/prod)
- Store production secrets in secure vault (AWS Secrets Manager, etc.)

## Validation

Verify your environment configuration:

```bash
# Check required variables are set
docker compose config

# Test database connection
docker compose run --rm prosaas-api python -c "from server import db; print('DB OK')"

# Test Redis connection
docker compose run --rm prosaas-api python -c "from redis import Redis; r=Redis.from_url('$REDIS_URL'); r.ping(); print('Redis OK')"
```
