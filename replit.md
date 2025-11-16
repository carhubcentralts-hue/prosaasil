# Overview

AgentLocator is a Hebrew CRM system for real estate professionals designed to automate the sales pipeline. It features an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion. It provides a robust, multi-tenant platform with customizable AI assistants and business branding, leveraging cutting-edge AI communication tools to streamline operations and boost sales for real estate businesses.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a multi-tenant architecture with complete business isolation, integrating Twilio Media Streams for real-time communication. It features Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for improved response times and conversation state preservation. The system enforces name and phone confirmation during scheduling via dual input (verbal name, DTMF phone number) for streamlined booking. Channel-aware responses adapt messaging based on the communication channel, and a DTMF Menu System provides interactive voice navigation for phone calls. Agent Validation Guards prevent AI hallucinations by blocking unverified actions.

Security is paramount, ensuring business identification, rejection of unknown numbers, and isolated data (prompts, agents, leads, calls, messages) per business. It includes universal warmup for active businesses, handles authentication errors, and implements comprehensive Role-Based Access Control (RBAC).

Performance optimizations include explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a 2-step matching approach: keyword matching and an OpenAI embeddings fallback, with channel filtering to ensure voice-only FAQs. Prompts are loaded exclusively from `BusinessSettings.ai_prompt`. STT reliability benefits from relaxed validation, Hebrew numbers context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, and agent behavioral constraints prevent verbalization of internal processes.

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
- **OpenAI Realtime API**: Feature-flagged migration for phone calls, using dedicated asyncio threads, thread-safe queues, and bidirectional audio streaming.

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
- **Greeting Management UI**: Dedicated fields for initial greetings with dynamic placeholders.
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
  - GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
  - **Realtime API** (`gpt-4o-realtime-preview`): Low-latency speech-to-speech for phone calls.
- **Google Cloud Platform** (legacy/fallback):
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.