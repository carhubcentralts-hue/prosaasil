# Overview

ProSaaS is a multi-tenant Hebrew AI assistant SaaS platform designed for WhatsApp and phone calls, leveraging the OpenAI Realtime API. Its core purpose is to automate the sales pipeline by providing an AI-powered assistant for real-time call processing, lead information collection, and meeting scheduling. The platform ensures complete business isolation, robust user management with 4-tier role-based access control, and aims to significantly enhance sales conversion and operational efficiency through advanced audio processing and customizable AI functionalities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS implements a multi-tenant architecture with strict data isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant uses an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. Key features include dual input (verbal and DTMF) for name/phone confirmation, a DTMF Menu System, and channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security measures include business identification, rejection of unknown numbers, isolated data, universal warmup, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration.
- **Multi-Tenant Resolution**: Secure business identification via `resolve_business_with_fallback()`.
- **RBAC**: 4-tier hierarchy (system_admin → owner → admin → agent).
- **Security**: Critical tenant isolation, cross-tenant security enforcing `tenant_id` filtering.
- **OpenAI Realtime API**: Integrates `gpt-4o-realtime-preview` for real-time voice calls.
- **AI Behavior Optimization**: Uses `gpt-4o-realtime-preview` with behavioral rules and server-side GPT-4o-mini NLP for appointment parsing and hallucination filtering.
- **Hebrew-Optimized VAD**: Dynamic thresholding and simplified barge-in.
- **Greeting System**: AI includes business-specific greetings.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI Navigation**: Consolidated AI prompt editing into System Settings, restricted by role.
- **RBAC Sidebar**: Dynamic visibility for "Business Management" and "User Management".
- **Role-Based Routing**: Smart default redirects based on user roles.

## Feature Specifications
- **Call Logging**: Comprehensive tracking.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Customizable names, introductions, and greetings.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Automatic Recording Cleanup**: 7-day retention with scheduled cleanup.
- **WhatsApp AI Toggle**: Customer service can toggle AI on/off per conversation.
- **WhatsApp Disconnect Notifications**: Automatic system notifications for business owners/admins.
- **Security Hardening**: Twilio signature validation, dynamic business identification, and robust RBAC.
- **Payments & Contracts Feature Flags**: Conditional enabling/disabling of billing features.
- **Enhanced Reminders System**.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice time.
- **CRM Tasks**: Redesigned task board with notifications.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for custom automations.

---

# BUILD 160 - Docker Infrastructure Rebuild

**Date**: November 28, 2025

## Changes Made

### 1. docker-compose.yml - Complete replacement
- Simplified service definitions
- Added env_file support for backend
- Fixed n8n configuration with proper public URL and paths
- Removed unnecessary healthchecks and volumes

### 2. Dockerfile.frontend
- Changed `npm ci` to `npm install --force` for better dependency resolution

### 3. Dockerfile.backend  
- Fixed client/dist copy block:
  - Before: `COPY client/dist/ ./server/public/ 2>/dev/null || mkdir -p ./server/public`
  - After: `RUN mkdir -p server/public` + `COPY client/dist/ server/public/`

### 4. docker/nginx.conf - Complete replacement
- Simplified configuration
- Fixed n8n proxy paths: `/n8n/`, `/n8nstatic/`, `/n8nassets/`
- Proper API and WebSocket proxying

## Deployment Commands (STEP 5)

```bash
cd /opt/prosaasil
git pull

docker compose down --remove-orphans
docker system prune -af
docker compose build --no-cache
docker compose up -d
```

## Validation Commands (STEP 6)

```bash
# Test n8n
curl -I https://prosaas.pro/n8n/
curl -I https://prosaas.pro/n8nassets/index-*.js
curl -I https://prosaas.pro/n8nstatic/prefers-color-scheme.css

# If any service fails, check logs:
docker compose logs n8n --tail 200
docker compose logs backend --tail 200
docker compose logs frontend --tail 200
docker compose logs baileys --tail 200
```

---

# BUILD 158 - Production AI Silence Fix

**Date**: November 28, 2025

## Issue
Production calls (Contabo) connect but AI doesn't speak. Logs show:
- ✅ WebSocket connected
- ✅ Business identified
- ❌ NO OpenAI/Realtime logs

## Root Cause Analysis
1. `USE_REALTIME_API` defaults to `"true"` (verified working)
2. BUT: All `print()` statements in `media_ws_ai.py` are suppressed via `builtins.print = _dprint` when `DEBUG=0`
3. Production has `DEBUG=0`, so no diagnostic output is visible

## Fix Applied

### 1. Changed USE_REALTIME_API default (line 72)
```python
# Was: os.getenv("USE_REALTIME_API", "false")
# Now: os.getenv("USE_REALTIME_API", "true")
```

### 2. Added Forced Prints (bypass DEBUG override)
Added `_orig_print(..., flush=True)` at critical points:

**server/media_ws_ai.py:**
- Line 2340: `MediaStreamHandler.run() entered main loop`
- Line 2393: `START EVENT RECEIVED!`
- Line 2513: `Checking Realtime: USE_REALTIME_API=X`
- Line 2517: `Starting Realtime API mode`
- Line 988: `Thread started for call X`
- Line 1014: `Async loop starting`

**asgi.py:**
- Lines 238-248: Handler creation and startup logging

**server/services/openai_realtime_client.py:**
- Line 76: `Connecting to OpenAI`

### 3. Added logger.info() calls
All critical points also log via `logger.info("[CALL DEBUG] ...")` which goes to stdout via Python logging.

## Expected Log Sequence After Deployment
```
🔧 [HANDLER] Getting Flask app...
🔧 [HANDLER] Flask app ready
🔧 Creating MediaStreamHandler...
🔧 Starting MediaStreamHandler.run()...
🎯 [CALL DEBUG] MediaStreamHandler.run() entered main loop
📨 Received: start
🎯 [CALL DEBUG] START EVENT RECEIVED!
🎯 [CALL DEBUG] Checking Realtime: USE_REALTIME_API=True
🚀 [REALTIME] Starting Realtime API mode for call XXXXXXXX
🚀 [REALTIME] Thread started for call XXXXXXXX
🚀 [REALTIME] Async loop starting for business_id=X
🔌 [CALL DEBUG] Connecting to OpenAI: model=gpt-4o-realtime-preview
✅ Connected to OpenAI Realtime API
```

## Deployment Commands
```bash
cd /opt/prosaasil
git pull
docker compose down
docker compose build backend
docker compose up -d
docker compose logs backend -f --tail=200
```

---

# BUILD 159 - Baileys Docker Networking Fix

**Date**: November 28, 2025

## Issue
Backend container cannot communicate with Baileys container:
```
curl http://baileys:3300/health → Connection refused
```
But inside Baileys container:
```
curl 127.0.0.1:3300/health → ok ✅
```

## Root Cause
`services/whatsapp/baileys_service.js` hardcoded `127.0.0.1` in the listen call:
```javascript
server = app.listen(PORT, '127.0.0.1', () => {...});
```
This made Baileys only accessible from inside its own container.

## Fix Applied

### 1. Updated `services/whatsapp/baileys_service.js`:
- Added `HOST` constant that reads `BAILEYS_HOST` env var (default: `0.0.0.0`)
- Changed `app.listen(PORT, '127.0.0.1', ...)` to `app.listen(PORT, HOST, ...)`
- Added logging to confirm Docker networking mode

### 2. Updated `docker-compose.yml`:
- Added `BAILEYS_HOST: 0.0.0.0` to baileys service environment

## Expected Log After Deployment
```
[BOOT] Baileys listening on 0.0.0.0:3300 pid=1
[BOOT] Docker networking: ✅ accessible from other containers
```

## Deployment Commands
```bash
cd /opt/prosaasil
git pull
docker compose down
docker compose build baileys
docker compose up -d
docker compose logs baileys --tail=20

# Test connectivity:
docker compose exec backend curl -v --max-time 5 http://baileys:3300/health
```