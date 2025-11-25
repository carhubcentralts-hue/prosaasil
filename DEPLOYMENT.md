# 🚀 ProSaaS Deployment Guide

This guide covers deploying ProSaaS to different environments.

---

## 📋 Table of Contents

1. [Development (Replit)](#development-replit)
2. [Docker Deployment (VPS/Self-hosted)](#docker-deployment)
3. [Cloud Run Deployment](#cloud-run-deployment)
4. [Environment Variables](#environment-variables)
5. [Troubleshooting](#troubleshooting)

---

## 🛠️ Development (Replit)

### Quick Start

```bash
# In Replit workspace - run both services
honcho start -f Procfile
```

This starts:
- **Flask/ASGI** on port 5000
- **Baileys** on port 3300

### Manual Start

```bash
# Start backend only
uvicorn asgi:app --host 0.0.0.0 --port 5000 --ws websockets

# Start Baileys (in separate terminal)
cd services/whatsapp && node baileys_service.js
```

---

## 🐳 Docker Deployment

### Prerequisites

- Docker & Docker Compose installed
- Git repository cloned
- GCP credentials JSON file (for TTS/STT)

### Step 1: Clone & Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/prosaas.git
cd prosaas

# Copy environment template
cp .env.example .env

# Edit with your values
nano .env
```

### Step 2: Prepare Credentials

```bash
# Create credentials directory
mkdir -p credentials

# Copy your GCP service account JSON
cp /path/to/your-gcp-credentials.json credentials/gcp-credentials.json
```

### Step 3: Build & Run

```bash
# Build all images
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Step 4: Verify

```bash
# Check backend health
curl http://localhost:5000/health

# Check Baileys health
curl http://localhost:3300/health

# Check frontend
curl http://localhost/health
```

### Production with Managed Database

If using an external managed database (Railway, Neon, Supabase, etc.):

```bash
# Use production overrides (skips local PostgreSQL)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Useful Commands

```bash
# Stop all services
docker compose down

# Restart specific service
docker compose restart backend

# View logs for specific service
docker compose logs -f backend

# Rebuild and restart
docker compose up -d --build

# Clean everything (including volumes)
docker compose down -v
```

### Service Ports

| Service   | Internal Port | External Port | Description                    |
|-----------|---------------|---------------|--------------------------------|
| Frontend  | 80            | 80            | Nginx serving React app        |
| Backend   | 5000          | 5000          | Flask/ASGI API + WebSockets    |
| Baileys   | 3300          | 3300          | WhatsApp Baileys service       |
| Database  | 5432          | 5432          | PostgreSQL (local only)        |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Frontend   │  │   Backend    │  │   Baileys    │      │
│  │   (Nginx)    │──│ (Flask/ASGI) │──│  (Node.js)   │      │
│  │   :80        │  │   :5000      │  │   :3300      │      │
│  └──────────────┘  └──────┬───────┘  └──────────────┘      │
│                           │                                 │
│                    ┌──────┴───────┐                        │
│                    │  PostgreSQL  │                        │
│                    │    :5432     │                        │
│                    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
              │              │              │
              ▼              ▼              ▼
         External:       External:      External:
          OpenAI         Twilio      Google Cloud
```

### WhatsApp QR Code

After starting, get the WhatsApp QR code:

```bash
# Check Baileys logs for QR code
docker compose logs baileys

# Or via API
curl http://localhost:3300/qr
```

Scan the QR code with your WhatsApp mobile app to connect.

---

## ☁️ Cloud Run Deployment

### Overview

Deploy Flask/ASGI to Cloud Run with external Baileys service.

### Required Environment Variables

```bash
BAILEYS_BASE_URL=https://your-baileys-service.com
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON={...}
INTERNAL_SECRET=...
```

### Deployment Command

```bash
# In Replit
replit deploy

# The deployment will:
# 1. Skip Baileys installation (BAILEYS_BASE_URL is set)
# 2. Start only Flask/ASGI on port $PORT
# 3. Use external Baileys service
```

### How it Works

The `start_production.sh` script checks for `BAILEYS_BASE_URL`:

- **If SET**: Skip Baileys, use external service → ✅ Cloud Run compatible
- **If NOT SET**: Start Baileys locally → ⚠️ Development only

### Testing Deployment

```bash
# Check health
curl https://your-app.run.app/health

# Check warmup status
curl https://your-app.run.app/warmup

# Check version
curl https://your-app.run.app/version
```

---

## 🔐 Environment Variables

### Required

| Variable                 | Description                              | Example                        |
|--------------------------|------------------------------------------|--------------------------------|
| `DATABASE_URL`           | PostgreSQL connection string             | `postgresql://user:pass@host/db` |
| `OPENAI_API_KEY`         | OpenAI API key                           | `sk-...`                       |
| `TWILIO_ACCOUNT_SID`     | Twilio Account SID                       | `AC...`                        |
| `TWILIO_AUTH_TOKEN`      | Twilio Auth Token                        | `...`                          |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP credentials JSON    | `/app/credentials/gcp.json`    |

### Optional

| Variable           | Default                | Description                   |
|--------------------|------------------------|-------------------------------|
| `TTS_VOICE`        | `he-IL-Standard-A`     | Google TTS voice              |
| `TTS_RATE`         | `1.0`                  | Speech rate                   |
| `TTS_PITCH`        | `0.0`                  | Voice pitch                   |
| `INTERNAL_SECRET`  | (auto-generated)       | Internal API security token   |
| `FLASK_ENV`        | `production`           | Flask environment             |

See `.env.example` for the complete list.

---

## 🔧 Troubleshooting

### Docker Issues

**Error: Port already in use**
```bash
# Check what's using the port
lsof -i :5000

# Kill the process or change port in .env
BACKEND_PORT=8000
```

**Error: Database connection failed**
```bash
# Check if PostgreSQL is running
docker compose ps db

# Check database logs
docker compose logs db

# Restart database
docker compose restart db
```

**Error: WhatsApp not connecting**
```bash
# Check Baileys logs
docker compose logs baileys

# Restart Baileys
docker compose restart baileys

# Remove auth and re-scan QR
rm -rf storage/whatsapp/*
docker compose restart baileys
```

### Cloud Run Issues

**Error: "multiple ports exposed"**
- Cloud Run only uses port 5000. This warning is normal.

**Error: "multiple services"**
- Set `BAILEYS_BASE_URL` to use external Baileys service.

**Error: "localhost not accessible"**
- Cloud Run doesn't support localhost. Use external services.

---

## 📊 Monitoring

### Health Endpoints

```bash
# Backend
curl http://localhost:5000/health

# Baileys
curl http://localhost:3300/health

# Frontend
curl http://localhost/health
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f baileys
```

---

## 🔄 Updates

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose up -d --build
```

### Database Migrations

Migrations run automatically on startup. If needed manually:

```bash
docker compose exec backend python -c "from server.db import db; db.create_all()"
```

---

## 📞 Support

For issues:
1. Check logs: `docker compose logs -f`
2. Check health endpoints
3. Review environment variables
4. Check GitHub issues
