# Overview

AgentLocator is a Hebrew CRM system for real estate, designed to automate the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding. The business vision is to provide a robust, multi-tenant platform that empowers real estate agencies with cutting-edge AI communication tools.

# Recent Changes

**Build 122 (November 11, 2025):**
- **FAQ Database Schema**: Added FAQ model with question/answer/order_index fields and migration #21
- **FAQ Fast-Path Cache**: Implemented FAQ cache service with OpenAI embeddings (text-embedding-3-small), cosine similarity matching (0.78 threshold), 10-minute TTL, and automatic cache invalidation on CRUD operations
- **FAQ Management UI**: Added dedicated "שאלות נפוצות (FAQ)" tab in settings with add/edit/delete interface, react-query integration, modal form validation (200/2000 char limits), and real-time data rendering
- **AI Service FAQ Integration**: FAQ fast-path activates for intent=="info" queries, uses mini LLM (gpt-4o-mini, max_tokens=80, temp=0.3) for <2s responses, falls back to AgentKit if no match
- **Working Days UI**: Added Sunday-Saturday checkbox selection for configuring business active days in appointment settings
- **TTS Truncation Fix**: Increased smart truncation limit from 150→350 characters to preserve complete sentences

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a production-ready multi-tenant architecture ensuring complete business isolation and zero cross-tenant exposure risk. It utilizes Twilio Media Streams for real-time communication, featuring **barge-in completely disabled** with 3-layer protection, calibrated Voice Activity Detection (VAD) optimized for Hebrew, and smart TTS truncation. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel, boosting response times and preserving conversation state with a singleton pattern to eliminate cold starts. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. **Agent Validation Guards** prevent hallucinated bookings and availability claims by blocking responses that claim "קבעתי" or "תפוס/פנוי" without executing corresponding calendar tools, and logging warnings for missing WhatsApp confirmations.

**Multi-Tenant Security:**
- Business identification via `BusinessContactChannel` or `Business.phone_e164`.
- Unknown phone numbers are rejected to prevent cross-tenant exposure.
- Each business has isolated prompts, agents, leads, calls, and messages.
- Universal warmup for active businesses (up to 10).
- 401 errors for missing authentication context.
- Complete Role-Based Access Control (RBAC): Admin sees all data, business users see only their tenant's data.
- WhatsApp API is secured with session-based authentication.

Performance is optimized with explicit OpenAI timeouts (4s + max_retries=1), increased Speech-to-Text (STT) streaming timeouts (30/80/400ms), and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=120` for `gpt-4o-mini` and a `temperature` of 0.15. **FAQ Fast-Path** uses ultra-minimal prompts, 500-char facts, `max_tokens=80`, and `temperature=0.3` for **faster responses** (~1-1.5s) and handles **ONLY** "info" queries. **WhatsApp send requests** route to AgentKit to execute the `whatsapp_send` tool. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation (confidence 0.25/0.4), Hebrew numbers context (boost=20.0), 3-attempt retry for **+30-40% accuracy on numbers**, and **longest partial persistence**. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start is optimized with automatic service warmup. **Agent behavioral constraints** enforce RULE #1 (never verbalize internal processes).

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` with strict security.
- **RBAC**: Role-based access control with admin/manager/business roles and impersonation support.
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
- **FAQ Fast-Path**: Less than 1.5-second responses for information queries using optimized LLM with fact extraction.
- **Multi-Tenant Isolation**: Complete business data separation with zero cross-tenant exposure risk and full RBAC.
- **Appointment Settings UI**: Allows businesses to configure slot size, 24/7 mode, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with longest partial persistence.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.