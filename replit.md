# Overview

AgentLocator is a Hebrew CRM system for real estate professionals that automates the sales pipeline. It features an AI-powered assistant for real-time call processing, intelligent lead information collection, and meeting scheduling. The system uses advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion within a robust, multi-tenant platform. It offers customizable AI assistants and business branding, leveraging cutting-edge AI communication tools to streamline operations and boost real estate sales.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator implements a multi-tenant architecture with complete business isolation, integrating Twilio Media Streams for real-time communication. It includes Hebrew-optimized Voice Activity Detection (VAD), smart Text-to-Speech (TTS) truncation, and an AI assistant utilizing an Agent SDK for appointment scheduling and lead creation with conversation memory. An Agent Cache System improves response times and preserves conversation state. The system confirms names and phone numbers during scheduling via dual input (verbal name, DTMF phone number) and uses channel-aware responses. A DTMF Menu System provides interactive voice navigation, and Agent Validation Guards prevent AI hallucinations. Security features include business identification, rejection of unknown numbers, isolated data per business, universal warmup, and comprehensive Role-Based Access Control (RBAC). Performance optimizations include explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts to prioritize short, natural AI conversations. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a two-step matching approach (keyword and OpenAI embeddings) with channel filtering. STT reliability benefits from relaxed validation, Hebrew numbers context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, and agent behavioral constraints prevent verbalization of internal processes. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` for secure business identification.
- **RBAC**: Role-based access control with admin/manager/business roles and impersonation support.
- **DTMF Menu**: Interactive voice response system for phone calls.
- **Data Protection**: Strictly additive database migrations with automatic verification.
- **OpenAI Realtime API**: Feature-flagged migration for phone calls using **gpt-4o-mini-realtime-preview exclusively** (no tools), with dedicated asyncio threads, thread-safe queues, and bidirectional audio streaming.
- **AI Behavior Optimization**:
  - **Temperature**: 0.18 (very low for focused, consistent responses - reduced from 0.8)
  - **Brief Greetings**: System prompt enforces 1-2 sentence max introductions
  - **Priority Question Handling**: System prompt requires answering hours/availability questions BEFORE discussing other topics
  - **NO Realtime Tools**: Removed all function calling - appointments handled exclusively via NLP parser (appointment_nlp.py)
  - **NLP Appointment Parser**: 
    - Server-side GPT-4o-mini text analysis with current date context (fixes 2023→2025 date bug)
    - Rejects generic names ("לקוח", "אדון", "גברת") - requires real customer names
    - Business hours validation before appointment creation
  - **Appointment Requirements**: System prompt enforces collecting full name + phone number + date/time BEFORE scheduling
- **Cost Optimization**: 
  - **Model Selection**: `OPENAI_REALTIME_MODEL` = `gpt-4o-mini-realtime-preview` (80% cheaper: $0.01/min input, $0.02/min output vs $0.21 per 2-min call)
  - **VAD Tuning**: `silence_duration_ms=600` (reduced from 800ms) for faster end-of-speech detection = 10-15% audio input savings
  - **Enhanced VAD Threshold**: 260 RMS + 800ms min_voice_duration_ms to reduce false triggers
  - **Comprehensive Cost Tracking**: Chunk-based audio duration tracking (50 chunks/sec @ 8kHz μ-law), precise cost calculations with pricing lookup table, per-call cost summary with warnings
  - Session-per-call architecture (no reuse), duplicate session prevention, and failed transcription handling without retries
  - Internal Whisper transcription is mandatory for AI to hear audio - this cost cannot be avoided (included in audio input pricing)
- **Smart Barge-In**: 
  - Enabled by default with intelligent state tracking (`is_ai_speaking`, `has_pending_ai_response`)
  - Comprehensive logging for debugging (RMS levels, grace periods, cooldowns)
  - 400ms grace period after AI starts speaking, 300ms min user speech duration to trigger
  - 260 RMS threshold for voice detection, 800ms cooldown between interruptions
- **Error Resilience**: DB query failures fall back to minimal prompt instead of crashing calls

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.

### Feature Specifications
- **Call Logging**: Comprehensive tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys with optimized response times.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication of lead information.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings with dynamic placeholders. If no greeting is defined, AI speaks first dynamically based on system prompt.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using a 2-step matching process.
- **Multi-Tenant Isolation**: Complete business data separation and full RBAC.
- **Appointment Settings UI**: Allows businesses to configure slot size, availability, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**:
  - GPT-4o-mini for Hebrew real estate conversations, FAQ responses, and server-side NLP parsing for appointments.
  - Realtime API using **gpt-4o-mini-realtime-preview exclusively**:
    - Cost: $0.01/min input + $0.02/min output = **80% cost savings** (~$0.025 per 2-min call vs $0.21)
    - Temperature: 0.18 (very low for consistency)
    - NO function calling tools - appointments via NLP parser only
  - Internal Whisper transcription with auto-detect (Hebrew specified in system prompt)
  - Fresh session per call (no reuse)
- **Google Cloud Platform** (legacy/fallback):
  - STT: Streaming API v1 for Hebrew speech recognition.
  - TTS: Standard API with WaveNet-D voice, telephony profile, SSML support.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.