# Overview

AgentLocator is a Hebrew CRM system for real estate businesses, designed to automate the sales pipeline with an AI-powered assistant. It offers real-time call processing, intelligent lead information collection, and meeting scheduling using advanced audio processing for natural conversations. The system aims to provide customizable AI assistants and business branding to real estate professionals, enhancing efficiency and sales conversion.

# Recent Changes (BUILD 134)

**Performance + Accuracy Optimization:**
- **STT Accuracy**: Expanded speech_contexts from 30→80+ Hebrew phrases, boost=20.0, stricter confidence (0.4→0.7)
- **Performance**: `tool_choice="auto"` (saves 1-2s), `max_tokens=250`, OpenAI timeout=2.5s
- **Target**: <2s WhatsApp response, <2.5s phone calls
- Agent modules imported at module level - eliminates import overhead
- Fixed Foreign Key violations in Invoice/Contract creation - auto-creates Customer records

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices
AgentLocator utilizes a multi-tenant architecture with business-based data isolation for CRM functionalities. It supports real-time communication via Twilio Media Streams (WebSockets for telephony and WhatsApp) and features sophisticated audio processing, including smart barge-in detection, calibrated VAD for Hebrew speech, and immediate TTS interruption. Custom greetings are dynamically loaded.

The AI uses an Agent SDK for actions like appointment scheduling and lead creation, maintaining robust conversation memory for contextual responses. **Agent Cache System**: Agents persist for 30 minutes per business+channel combination, improving response time from 100ms to 1ms (30x faster) and maintaining conversation state across multiple turns. It enforces mandatory name and phone confirmation during scheduling, with dual input collection (verbal name, DTMF phone number) and streamlined 4-turn booking flows. **Channel-Aware Responses**: Agent adapts messaging based on communication channel - mentions WhatsApp confirmation only during phone calls, not when already conversing via WhatsApp. **DTMF Menu System**: Interactive voice menu for phone calls (press 1 for appointments, 2 for info, 3 for representative) with fallback to natural conversation. Error handling provides structured messages.

Performance is optimized with explicit OpenAI timeouts, increased STT streaming timeouts, and warnings for long prompts. AI responses prioritize completeness with increased `max_tokens` (350) for `gpt-4o-mini` and a `temperature` of 0.3-0.4 for consistent Hebrew sentences. Robustness is ensured through thread tracking, enhanced cleanup, and a Flask app singleton pattern. STT reliability is improved with relaxed validation, confidence checks, and a 3-attempt retry mechanism. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start optimization includes automatic service warmup.

## Technical Implementations
### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache maintaining Agent SDK instances for 30 minutes with automatic expiration and cleanup (`server/services/agent_cache.py`).
- **DTMF Menu**: Interactive voice response system for phone calls with keypad navigation (`server/services/dtmf_menu.py`).

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