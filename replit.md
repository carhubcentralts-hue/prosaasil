# Overview

AgentLocator is a Hebrew CRM system tailored for real estate businesses. Its core purpose is to streamline the sales pipeline through an AI-powered assistant that automates lead management. Key capabilities include real-time call processing, intelligent lead information collection, and meeting scheduling, all powered by advanced audio processing for natural conversations. The system aims to provide fully customizable AI assistants and business branding to real estate professionals, enhancing efficiency and sales conversion.

# Recent Changes

## BUILD 128 - TIMEZONE BUG FIX (CRITICAL - FULLY SOLVED!) ✅
**Problem**: Appointments saved 2 hours earlier than requested (14:00 → 12:00, 13:00 → 11:00, 11:30 → 09:30)

**Root Cause**: PostgreSQL was converting timezone-aware datetimes to UTC before saving!
- Agent sends: `"2025-11-05T14:00:00+02:00"` (14:00 Israel time) ✅
- DB columns are `DateTime` (not `DateTimeTZ`), so PostgreSQL auto-converts to UTC
- PostgreSQL: `14:00 - 2 hours = 12:00 UTC` → Saves `12:00` (naive) ❌
- Result: 2-hour shift!

**Complete Fix (4 Files)**:
1. **server/agents/tools_calendar.py**:
   - `_calendar_create_appointment_impl`: Strip timezone before DB save → `start.replace(tzinfo=None)`
   - `_calendar_find_slots_impl`: Add timezone when reading → `tz.localize(apt.start_time)`
2. **server/routes_calendar.py**:
   - POST/PUT (create/update): Strip timezone before DB save
   - GET endpoints: Add timezone before `.isoformat()` for API responses
   - **GET filters**: Convert to Israel time FIRST → `.astimezone(tz)` then strip → `.replace(tzinfo=None)`
3. **server/whatsapp_appointment_handler.py**: Add timezone to all API responses
4. **server/auto_meeting.py**: Add timezone to API response

**Technical Solution**:
- **SAVE to DB**: Always strip timezone → `datetime.replace(tzinfo=None)`
- **READ from DB**: Always add timezone back → `tz.localize(naive_datetime)` for API
- **QUERY filters**: Convert to Israel time → `.astimezone(tz)` then strip → `.replace(tzinfo=None)`
- **DB stores**: Naive datetime (local Israel time: 14:00 stays 14:00)
- **API returns**: ISO with timezone (`"2025-11-05T14:00:00+02:00"`)

**Result**: Agent says 14:00 → DB saves 14:00 → Calendar shows 14:00 ✅✅✅

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices
AgentLocator employs a multi-tenant architecture with business-based data isolation for CRM features. The system is designed for real-time communication, integrating Twilio Media Streams via WebSockets for telephony and WhatsApp. It features sophisticated audio processing, including smart barge-in detection, calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking. Custom greetings are dynamically loaded from business configurations.

The AI utilizes an Agent SDK for real actions, enabling appointment scheduling and lead creation during conversations. It incorporates robust conversation memory, passing full history for contextual responses. The system ensures mandatory name and phone confirmation during scheduling, with dual input collection (verbal name, DTMF phone number) and streamlined 4-turn booking flows. Error handling is graceful, returning structured error messages rather than raising exceptions.

Performance is optimized with explicit OpenAI timeouts, increased STT streaming timeouts, and warnings for long prompts. AI responses prioritize completeness with increased `max_tokens` (350) for `gpt-4o-mini` and a `temperature` of 0.3-0.4 for consistent Hebrew sentences. Robustness is ensured through thread tracking, enhanced cleanup, and a Flask app singleton pattern. STT reliability is improved with relaxed validation, confidence checks, and a 3-attempt retry mechanism. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start optimization includes automatic service warmup.

## Technical Implementations
### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling for Twilio Media Streams, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

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