# Overview

AgentLocator is a Hebrew CRM system for real estate businesses that automates the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding.

# Recent Changes (PHASE 1 - POLICY ENGINE)

**POLICY ENGINE IMPLEMENTED** - No more hardcoded business hours!
- **BusinessSettings Model Extended** (`server/models_sql.py`):
  - Added 5 new fields: `slot_size_min`, `allow_24_7`, `opening_hours_json`, `booking_window_days`, `min_notice_min`
  - All policy now loaded from DB + parsed from business prompt
- **Database Migration 19** (`server/db_migrate.py`):
  - Safely adds 5 policy columns with defaults (60, FALSE, NULL, 30, 0)
  - Idempotent (checks before adding), additive only (no DROP)
  - Runs automatically with `RUN_MIGRATIONS_ON_START=1` on startup
  - Backwards compatible - existing businesses keep working
- **Policy Engine Created** (`server/policy/business_policy.py`):
  - `get_business_policy()` - loads policy from DB + prompt with fallback to defaults
  - `parse_policy_from_prompt()` - parses Hebrew prompt for: "24/7", "כל רבע שעה", "10:00-20:00", etc.
  - `validate_slot_time()` - checks if time is on-grid (e.g., :00/:15/:30/:45 for 15min slots)
  - `get_nearby_slots()` - returns 2 nearest valid times if off-grid
- **Calendar Tools Updated** (`server/agent_tools/tools_calendar.py`):
  - `calendar_find_slots` - dynamically generates slots based on policy (24/7 vs specific hours, 15/30/60 min intervals)
  - `calendar_create_appointment` - validates on-grid + business hours from policy
  - Returns `{ok: false, error: "off_grid", suggestions: ["10:00", "11:00"]}` if time invalid
- **Benefits**:
  - Business A: "פתוח 24/7 כל רבע שעה" → 96 slots per day
  - Business B: "ראשון עד חמישי 10-20 רק שעה עגולה" → 10 slots per day
  - NO HARDCODED HOURS - all policy is database-driven + prompt-aware

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices
AgentLocator employs a multi-tenant architecture with business-specific data isolation for CRM. It uses Twilio Media Streams (WebSockets for telephony and WhatsApp) for real-time communication, featuring smart barge-in, calibrated VAD for Hebrew, and immediate TTS interruption. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business+channel, boosting response times and preserving conversation state. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel (e.g., WhatsApp confirmation mentioned only during phone calls). A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling.

Performance is optimized with explicit OpenAI timeouts, increased STT streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=150` for `gpt-4o-mini` and a `temperature` of 0.3-0.4 for consistent Hebrew. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation, confidence checks, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start is optimized with automatic service warmup.

## Technical Implementations
### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration.
- **DTMF Menu**: Interactive voice response system for phone calls.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.

### Feature Specifications
- **Call Logging**: Comprehensive call tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys with optimized response times and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.