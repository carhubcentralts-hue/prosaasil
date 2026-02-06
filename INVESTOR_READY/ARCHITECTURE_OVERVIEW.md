# Architecture Overview

## System Components

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Nginx Reverse Proxy                          │
│              (SSL, Headers, CORS, Rate Limiting, WebSocket)          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌──────────────────┐    ┌──────────────────┐   │
│  │  Frontend    │     │  prosaas-api     │    │  prosaas-calls   │   │
│  │  React 19    │────▶│  REST API        │    │  WebSocket       │   │
│  │  Vite + TS   │     │  (scalable)      │    │  Twilio voice    │   │
│  │  TailwindCSS │     │  Port 5000       │    │  Port 5050       │   │
│  └─────────────┘     └──────┬───────────┘    └──────┬───────────┘   │
│                              │                       │               │
│               ┌──────────────┼───────────────────────┘               │
│               ▼              ▼                                       │
│  ┌────────────────┐  ┌──────────────┐                               │
│  │   PostgreSQL   │  │    Redis     │◀── Worker (high/default/low)  │
│  │   (Pooler)     │  │ Queue+State  │◀── Scheduler                  │
│  └────────────────┘  └──────────────┘                               │
│                                                                      │
│  ┌───────────────────┐   ┌───────────────────────────────────┐      │
│  │  Baileys 1..N     │   │        External Services           │      │
│  │  WhatsApp Shards  │   │  • OpenAI (AI Agent, Summaries)    │      │
│  │  (per-tenant)     │   │  • Twilio (Voice Calls)            │      │
│  └───────────────────┘   │  • Google Cloud (TTS, Speech)      │      │
│                          │  • SendGrid (Email)                │      │
│                          │  • Cloudflare R2 (Storage)         │      │
│                          └───────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
```

## Service Architecture

| Service | Port | Role | Scaling |
|---------|------|------|---------|
| nginx | 80/443 | Reverse proxy, SSL, load balancing | Single (stateless config) |
| prosaas-api | 5000 | REST API, business logic | Horizontal (stateless) |
| prosaas-calls | 5050 | WebSocket, Twilio voice | Horizontal (Redis state) |
| worker | — | Background jobs (RQ) | Horizontal (queue-dedicated) |
| scheduler | — | Periodic job scheduling | Single (Redis-locked) |
| baileys | 3300 | WhatsApp gateway | Sharded (per-tenant) |
| redis | 6379 | Queue, cache, call state | Single (managed in prod) |
| frontend | 80 | Static SPA | Single (CDN-ready) |
| n8n | 5678 | Workflow automation | Single |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript 5.9, Vite, TanStack Query |
| **Styling** | Tailwind CSS v4, Framer Motion |
| **Backend** | Python 3.11+, Flask, SQLAlchemy |
| **Database** | PostgreSQL (psycopg2, connection pooling) |
| **Cache/Queue** | Redis, RQ (Redis Queue) |
| **AI/ML** | OpenAI GPT, Google Gemini |
| **Telephony** | Twilio (voice), WebSocket media streams |
| **Messaging** | WhatsApp (Baileys, sharded), SendGrid (email) |
| **Auth** | JWT + Flask-Login + Session cookies |
| **Security** | Flask-SeaSurf (CSRF), Flask-Limiter, bcrypt |
| **Deploy** | Docker, Docker Compose, Nginx |
| **Monitoring** | Health endpoints, `/metrics.json`, Docker healthchecks |

## Scaling Architecture

### WhatsApp Sharding
- Tenant-based: `Business.whatsapp_shard` → shard routing
- Each shard has isolated auth state (separate Docker volumes)
- See: `INVESTOR_READY/SCALING_PLAN.md`, `server/SSOT_SHARDING.md`

### Worker Queues
- Priority-based: high, default, low, media, recordings, broadcasts, maintenance
- Multi-worker deployment via Docker profiles
- SSOT: `server/queues.py`

### Calls Scaling
- Redis-backed call state (no in-memory state)
- Global `MAX_CONCURRENT_CALLS` enforcement via Redis atomic counter
- Graceful degradation when at capacity
- See: `server/calls_scaling.md`

## Key Modules

### Frontend (`client/src/`)
- **pages/** — Route-level components (Dashboard, Leads, Calls, Calendar, etc.)
- **features/** — Feature-specific logic (auth, admin, permissions)
- **shared/** — Reusable components, hooks, utilities
- **services/** — HTTP client, API services
- **lib/** — React Query client, configuration

### Backend (`server/`)
- **routes_*.py** — API route handlers (50+ route modules)
- **models_sql.py** — SQLAlchemy ORM models
- **services/** — Business logic services
- **agent_tools/** — AI agent factory and tools
- **queues.py** — Queue definitions (SSOT)
- **metrics.py** — Operational metrics
- **calls_state.py** — Redis-backed call state
- **whatsapp_shard_router.py** — Baileys shard routing
- **health_endpoints.py** — Health/readiness probes
- **scheduler/** — Background job scheduling

## Authentication Flow

1. User submits credentials via login form
2. Backend validates with bcrypt, creates session
3. JWT token issued for API authentication
4. CSRF token managed by Flask-SeaSurf
5. Role-based access: `system_admin` > `owner` > `admin` > `agent`

## Data Flow

1. **Inbound**: Webhook → Backend → DB → Push notification → Frontend
2. **Outbound**: Frontend → API → Backend → External service (Twilio/WhatsApp)
3. **AI**: Message → Backend → OpenAI Agent → Response → WhatsApp/Call
4. **Queue**: API → Redis Queue → Worker → Processing → DB update
