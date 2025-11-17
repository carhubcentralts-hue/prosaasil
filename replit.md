# Overview

AgentLocator is a Hebrew CRM system for real estate professionals that automates the sales pipeline. It features an AI-powered assistant for real-time call processing, intelligent lead information collection, and meeting scheduling. The system uses advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion within a robust, multi-tenant platform. It offers customizable AI assistants and business branding, leveraging cutting-edge AI communication tools to streamline operations and boost real estate sales.

## Recent Improvements (2025-11-17)

**Agent 3 Final Implementation** - Production-ready with verification logs:

### 1. Model Configuration (Locked & Verified)
**Phone Calls (Realtime API)**:
- Model: `gpt-4o-realtime-preview` (NOT mini - **HARDCODED**, ignores env var)
- max_tokens: 300 (range: 280-320, balanced Hebrew responses)
- temperature: 0.18 (range: 0.18-0.25, very low for consistency)
- Whisper transcription: `whisper-1` auto-detect (NO explicit language field)
- ✅ Verification log: `[REALTIME CONFIG] model=gpt-4o-realtime-preview, temp=0.18, max_tokens=300`
- ⚠️ Protection: Warns if `OPENAI_REALTIME_MODEL` secret tries to override

**NLP Appointment Parser**:
- Model: `gpt-4o-mini` (text-only analysis, NOT realtime)
- temperature: 0.1 (range: 0.1-0.2, deterministic extraction)
- Purpose: Extract date/time/name from conversation text
- ✅ Verification log: `[NLP VERIFICATION] Using model=gpt-4o-mini, temperature=0.1`

### 2. Critical Rules System
8 comprehensive behavioral rules enforced in system prompt:
1. **Identity**: Present ONLY as defined in custom business prompt (NOT business_name from DB)
2. **Brevity**: 1-2 sentences maximum per response
3. **Silence**: Don't talk over 3s+ quiet periods (once per ~8s max)
4. **Appointment Honesty**: NEVER say "קבעתי" until `has_appointment_created=True` from server
5. **DTMF Phone**: Clear instructions: "תלחץ על הספרות ותסיים בסולמית (#)"
6. **Turn-taking**: Stop immediately when user starts speaking (barge-in)
7. **Answer Questions**: Don't push appointments - answer what customer asks
8. **Server Messages**: Silent [SERVER] events (role="system")

### 3. Hebrew-Optimized VAD
**Formula**: `threshold = min(175, noise_floor + 80)`
- Calibrates ONLY on quiet frames (RMS < 120) for first 4 seconds
- 80 RMS margin prevents false triggers from background noise (60-120 RMS)
- 175 RMS cap GUARANTEES Hebrew speech detection (180-220 RMS typical)
- Result: Speech ALWAYS detected, noise NEVER triggers
- ✅ Verification log: `VAD CALIBRATED (noise=X, threshold=Y, quiet_frames=Z)`

### 4. Barge-in Timing (Agent 3 Spec)
- **is_ai_speaking**: Implemented with `threading.Event()` (thread-safe)
- **Grace period**: 400ms after AI starts speaking
- **Barge-in RMS threshold**: 150 (safety margin below speech 180-220 RMS)
- **Min voice duration**: 400ms continuous speech to trigger
- **Cooldown**: 800ms between interruptions
- Comprehensive debug logs for all barge-in events

### 5. Appointment Workflow (Server-Side Validation)
**Order of Operations**:
1. NLP extracts datetime from conversation (gpt-4o-mini server-side)
2. Server checks availability against `AppointmentSettings` + `business_policy`
3. Server validates business hours, slot availability, min_notice
4. ONLY if all valid → Create appointment in DB
5. Set `has_appointment_created=True` in `CallCrmContext`
6. Send `[SERVER] ✅ appointment_created` to AI
7. AI can now say "התור נקבע!"

**Protection**:
- AI CANNOT say confirmation words until `has_appointment_created=True`
- Guard system monitors AI transcripts for forbidden phrases
- ✅ Verification log: `[APPOINTMENT VERIFICATION] Created appointment #X - has_appointment_created=True`

**Missing Phone (DTMF)**:
- Server sends `[SERVER] need_phone`
- AI receives explicit instruction text with DTMF guidance
- ✅ Verification log: `[DTMF VERIFICATION] Requesting phone via DTMF`

### 6. Previous Bug Fixes (Retained)
- NLP deduplication (30s TTL cache)
- Response collision prevention (thread-safe locks)
- Server messages silent (role="system")

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
- **OpenAI Realtime API**: Feature-flagged migration for phone calls using **gpt-4o-realtime-preview** (NOT mini, Agent 3 spec), with dedicated asyncio threads, thread-safe queues, and bidirectional audio streaming.
- **AI Behavior Optimization**:
  - **Model**: gpt-4o-realtime-preview (Agent 3 requirement)
  - **max_tokens**: 300 (balanced Hebrew responses, Agent 3 spec)
  - **Temperature**: 0.18 (very low for focused responses, no constraint)
  - **Critical Rules**: 8 comprehensive rules covering identity, brevity, silence, honesty, DTMF, turn-taking
  - **NO Realtime Tools**: Removed all function calling - appointments handled exclusively via NLP parser (appointment_nlp.py)
  - **NLP Appointment Parser**: 
    - Server-side GPT-4o-mini text analysis with current date context (fixes 2023→2025 date bug)
    - Rejects generic names ("לקוח", "אדון", "גברת") - requires real customer names
    - Business hours validation before appointment creation
  - **Appointment Requirements**: System prompt enforces collecting full name + phone number + date/time BEFORE scheduling
- **Hebrew-Optimized VAD** (Agent 3 spec):
  - **Formula**: `threshold = min(175, noise_floor + 80)` - GUARANTEES Hebrew speech detection (180-220 RMS)
  - **Calibration**: ONLY quiet frames (RMS < 120) during first 4 seconds, excludes speech pollution
  - **Margin**: 80 RMS above noise prevents false triggers (60-120 RMS background noise)
  - **Cap**: 175 RMS ensures speech detection in all environments
  - **Result**: Hebrew speech (180-220 RMS) ALWAYS detected, noise (60-120 RMS) NEVER triggers
- **Smart Barge-In** (Agent 3 spec): 
  - **Grace period**: 400ms after AI starts speaking (aligned with VAD)
  - **Barge-in threshold**: 150 RMS (safety margin below speech 180-220 RMS)
  - **Min voice duration**: 400ms continuous speech to trigger
  - **Cooldown**: 800ms between interruptions
  - Enabled by default with intelligent state tracking (`is_ai_speaking`, `has_pending_ai_response`)
  - Comprehensive logging for debugging (RMS levels, grace periods, cooldowns)
- **Cost Tracking**: 
  - Chunk-based audio duration tracking (50 chunks/sec @ 8kHz μ-law)
  - Precise cost calculations with pricing lookup table
  - Per-call cost summary with warnings
  - Session-per-call architecture (no reuse), duplicate session prevention
  - Internal Whisper transcription is mandatory for AI to hear audio (included in audio input pricing)
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
  - GPT-4o-mini for FAQ responses and server-side NLP parsing for appointments
  - Realtime API using **gpt-4o-realtime-preview** (Agent 3 spec):
    - Model: gpt-4o-realtime-preview (NOT mini)
    - max_tokens: 300 (balanced Hebrew responses)
    - Temperature: 0.18 (very low for consistency)
    - Critical Rules: 8 comprehensive behavioral rules
    - NO function calling tools - appointments via NLP parser only
  - Hebrew-Optimized VAD: `threshold = min(175, noise_floor + 80)` guarantees speech detection (180-220 RMS)
  - Barge-in: 400ms grace, 150 RMS threshold, 400ms min speech, 800ms cooldown
  - Internal Whisper transcription with auto-detect (Hebrew specified in system prompt)
  - Fresh session per call (no reuse)
- **Google Cloud Platform** (legacy/fallback):
  - STT: Streaming API v1 for Hebrew speech recognition.
  - TTS: Standard API with WaveNet-D voice, telephony profile, SSML support.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.