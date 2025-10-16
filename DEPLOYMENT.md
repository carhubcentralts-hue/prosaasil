# 🚀 Cloud Run Deployment Guide

## Overview
AgentLocator can be deployed to Cloud Run with the Flask/ASGI service, while Baileys runs as a separate service or in development mode.

## Deployment Options

### Option 1: Single Service (Flask only) - RECOMMENDED for Cloud Run
Deploy only the Flask/ASGI service to Cloud Run. Baileys runs separately (external service or dev environment).

**Required Environment Variables:**
```bash
# Set in Cloud Run secrets/environment
BAILEYS_BASE_URL=https://your-baileys-service.com  # External Baileys service URL
DATABASE_URL=postgresql://...                       # PostgreSQL connection string
OPENAI_API_KEY=sk-...                              # OpenAI API key
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON={...}            # GCP credentials (JSON)
INTERNAL_SECRET=...                                # Auto-generated if not set
```

**Deployment Command:**
```bash
# In Replit
replit deploy

# The deployment will:
# 1. Skip Baileys installation (BAILEYS_BASE_URL is set)
# 2. Start only Flask/ASGI on port $PORT
# 3. Use external Baileys service
```

### Option 2: Development (Both services)
For local development, both services run together.

**No environment variables needed** - defaults to localhost.

```bash
# In Replit workspace
honcho start -f Procfile
```

## How start_production.sh Works

The script checks for `BAILEYS_BASE_URL`:

- **If SET**: Skip Baileys, use external service → ✅ Cloud Run compatible
- **If NOT SET**: Start Baileys locally on 127.0.0.1:3300 → ⚠️ Development only

## Cloud Run Configuration

### 1. Deployment Settings
```yaml
# In .replit (already configured)
[deployment]
run = ["sh", "-c", "bash ./start_production.sh"]
deploymentTarget = "cloudrun"
build = ["sh", "-c", "pip install ."]
```

### 2. Required Secrets (add in Replit)
1. `DATABASE_URL` - PostgreSQL database
2. `OPENAI_API_KEY` - OpenAI API key
3. `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` - GCP credentials
4. `BAILEYS_BASE_URL` - External Baileys service URL (e.g., https://baileys.example.com)

### 3. Optional Secrets
- `INTERNAL_SECRET` - Auto-generated if not provided
- `TTS_VOICE` - Google TTS voice (default: he-IL-Wavenet-D)
- `TTS_PITCH` - TTS pitch (default: 0)
- `TTS_RATE` - TTS rate (default: 1.0)

## Warmup & Cold Start

The system includes automatic warmup to eliminate first-call latency:

1. **Automatic warmup** on startup (warmup_services_async)
2. **Warmup endpoint**: `GET /warmup` for Cloud Run startup probes

### Add Startup Probe (Optional)
```yaml
# Cloud Run configuration
startupProbe:
  httpGet:
    path: /warmup
    port: 5000
  initialDelaySeconds: 3
  periodSeconds: 10
  failureThreshold: 3
```

## Troubleshooting

### Error: "multiple ports exposed"
**Solution**: The .replit file has development ports. Cloud Run only uses port 5000 (or $PORT). This is normal - the script handles it.

### Error: "multiple services"
**Solution**: Set `BAILEYS_BASE_URL` environment variable to skip local Baileys.

### Error: "localhost/127.0.0.1 not accessible"
**Solution**: Use external Baileys service via `BAILEYS_BASE_URL`.

## Testing Deployment

After deployment:

```bash
# 1. Check health
curl https://your-app.run.app/healthz

# 2. Check warmup status
curl https://your-app.run.app/warmup

# 3. Check version
curl https://your-app.run.app/version
```

Expected response:
```json
{
  "status": "warmed",
  "services": {
    "openai": "ok",
    "tts": "ok",
    "stt": "ok",
    "database": "ok"
  },
  "duration_ms": 2000
}
```

## Architecture

```
┌─────────────────────────────────────┐
│         Cloud Run Instance          │
│  ┌──────────────────────────────┐   │
│  │   Flask/ASGI (port $PORT)    │   │
│  │  - Twilio WebSocket          │   │
│  │  - REST API                  │   │
│  │  - WhatsApp integration      │   │
│  └──────────────────────────────┘   │
│              │                       │
│              ▼                       │
│     (BAILEYS_BASE_URL)               │
└──────────────┼──────────────────────┘
               │
               ▼
   ┌────────────────────────┐
   │  External Baileys      │
   │  (Separate service)    │
   └────────────────────────┘
```

## Port Configuration

- **Cloud Run**: Uses `$PORT` environment variable (default: 8080)
- **Development**: Flask on 5000, Baileys on 3300
- **The script automatically adapts** based on `BAILEYS_BASE_URL`

## BUILD 100.15 Features

✅ Automatic service warmup (eliminates cold start)
✅ External Baileys support (Cloud Run compatible)
✅ Single-port deployment
✅ Automatic INTERNAL_SECRET generation
✅ Sub-2-second first-call latency
