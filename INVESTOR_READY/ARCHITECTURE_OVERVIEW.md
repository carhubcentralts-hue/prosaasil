# Architecture Overview

## System Components

```
┌──────────────────────────────────────────────────────────┐
│                      Nginx Reverse Proxy                  │
│               (SSL, Headers, CORS, Rate Limiting)         │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────┐     ┌──────────────────────────────┐    │
│  │  Frontend    │     │         Backend (Flask)       │    │
│  │  React 19    │────▶│  REST API + WebSocket         │    │
│  │  Vite + TS   │     │  Auth: JWT + Session          │    │
│  │  TailwindCSS │     │  ORM: SQLAlchemy              │    │
│  └─────────────┘     └──────┬───────────┬────────────┘    │
│                              │           │                 │
│                    ┌─────────▼──┐  ┌─────▼──────────┐     │
│                    │ PostgreSQL │  │  Redis Queue   │     │
│                    │ (Primary)  │  │  (Jobs/Cache)  │     │
│                    └────────────┘  └────────────────┘     │
│                                                           │
│  ┌─────────────────────────────────────────────────┐      │
│  │              External Services                   │      │
│  │  • OpenAI (AI Agent, Summaries)                  │      │
│  │  • Twilio (Voice Calls)                          │      │
│  │  • WhatsApp (Baileys / Green API)                │      │
│  │  • Google Cloud (TTS, Speech)                    │      │
│  │  • SendGrid (Email)                              │      │
│  └─────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript 5.9, Vite, TanStack Query |
| **Styling** | Tailwind CSS v4, Framer Motion |
| **Backend** | Python 3.11+, Flask, SQLAlchemy |
| **Database** | PostgreSQL (psycopg2) |
| **Cache/Queue** | Redis, RQ (Redis Queue) |
| **AI/ML** | OpenAI GPT, Google Gemini |
| **Telephony** | Twilio (voice), WebRTC |
| **Messaging** | WhatsApp (Baileys), SendGrid (email) |
| **Auth** | JWT + Flask-Login + Session cookies |
| **Security** | Flask-SeaSurf (CSRF), Flask-Limiter (rate limiting), bcrypt |
| **Deploy** | Docker, Docker Compose, Nginx, Gunicorn |

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
- **telephony/** — Call handling and recording
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
