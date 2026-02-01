# ProSaaS - AI-Powered Communication Platform

ProSaaS is a comprehensive SaaS platform for AI-powered voice calls, WhatsApp integration, and customer relationship management.

## Features

- **AI Voice Calls**: Real-time AI-powered voice conversations using OpenAI, Google Gemini, and other providers
- **WhatsApp Integration**: Full WhatsApp Business API support via Baileys
- **CRM System**: Lead management, contact tracking, and customer service tools
- **Multi-Channel**: Support for voice calls (Twilio), WhatsApp, email (Gmail), and SMS
- **Automation**: N8N workflow integration for automated processes
- **Queue Management**: Redis-based background job processing (RQ)
- **Recording & Transcription**: Automatic call recording and transcription services

## Tech Stack

### Backend
- **Python 3.11+**: Flask, SQLAlchemy, Redis Queue (RQ)
- **PostgreSQL**: Primary database
- **Redis**: Queue management and caching

### Frontend
- **React 19**: Modern React with TypeScript
- **Vite**: Fast build tooling
- **TailwindCSS**: Utility-first styling
- **React Router**: Client-side routing

### Services
- **Nginx**: Reverse proxy and load balancing
- **N8N**: Workflow automation
- **Baileys**: WhatsApp multi-device API
- **Twilio**: Voice calling infrastructure

## Quick Start (Development)

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 1. Clone and Setup
```bash
git clone <repository-url>
cd prosaasil
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration (see ENVIRONMENT.md)
```

### 3. Run with Docker Compose
```bash
# Development mode
docker compose up

# Production mode
docker compose --profile prod up
```

The application will be available at:
- Frontend: http://localhost (via Nginx)
- API: http://localhost/api
- N8N: http://localhost/n8n

### 4. Run Locally (Development)

#### Backend
```bash
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -e .

# Run migrations
python -m server.db_migrate

# Start API server
python run_server.py
```

#### Frontend
```bash
cd client
npm install
npm run dev
```

#### Background Workers
```bash
source .venv/bin/activate
python -m worker.worker
```

## Project Structure

```
prosaasil/
├── server/          # Backend API (Flask)
│   ├── routes_*.py  # API route handlers
│   ├── models.py    # Database models
│   └── services/    # Business logic services
├── client/          # Frontend (React + Vite)
│   └── src/
├── worker/          # Background job workers (RQ)
├── services/        # External services
│   └── whatsapp/    # Baileys WhatsApp service
├── docker/          # Docker configuration
└── tests/           # Test suites
```

## Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_example.py

# Frontend tests (if configured)
cd client && npm test
```

## Building for Production

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed production deployment instructions.

Quick build:
```bash
# Build all Docker images
docker compose -f docker-compose.prod.yml build

# Start production stack
docker compose -f docker-compose.prod.yml --profile prod up -d
```

## Environment Variables

All required environment variables are documented in [ENVIRONMENT.md](./ENVIRONMENT.md).

Key variables:
- `DATABASE_URL_POOLER` / `DATABASE_URL_DIRECT`: PostgreSQL connection strings
- `OPENAI_API_KEY`: OpenAI API credentials
- `TWILIO_*`: Twilio voice service credentials
- `PUBLIC_HOST`: Production domain URL

## Security

See [SECURITY.md](./SECURITY.md) for security best practices and guidelines.

Key security measures:
- All secrets must be in `.env` (never committed)
- CSRF protection with Flask-SeaSurf
- Rate limiting with Flask-Limiter
- JWT-based authentication
- Secure session management

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and ensure they pass
4. Submit a pull request

## License

Proprietary - All rights reserved
