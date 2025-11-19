# Overview

AgentLocator is a multi-tenant Hebrew CRM system designed for real estate professionals. It automates the sales pipeline with an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to boost efficiency and sales conversion. It offers customizable AI assistants and business branding, leveraging cutting-edge AI communication tools to streamline real estate operations.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a multi-tenant architecture with complete business isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant uses an Agent SDK for appointment scheduling and lead creation, maintaining conversation memory and utilizing an Agent Cache System for improved response times. Name and phone number confirmation during scheduling occur via dual input (verbal name, DTMF phone number), with channel-aware responses and a DTMF Menu System for interactive voice navigation. Agent Validation Guards prevent AI hallucinations. Security features include business identification, rejection of unknown numbers, isolated data per business, universal warmup, and comprehensive Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability benefits from relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, and agent behavioral constraints prevent verbalization of internal processes. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` for secure business identification.
- **RBAC**: Role-based access control with admin/manager/business roles.
- **DTMF Menu**: Interactive voice response system for phone calls.
- **Data Protection**: Strictly additive database migrations.
- **OpenAI Realtime API**: Integrates **gpt-4o-realtime-preview** for phone calls with dedicated asyncio threads and thread-safe queues.
- **AI Behavior Optimization**:
  - **Model**: gpt-4o-realtime-preview, max_tokens: 300, temperature: 0.6 (OpenAI Realtime API minimum).
  - **Critical Rules (Nov 2025)**: 10 comprehensive behavioral rules with STRICT silence enforcement:
    - **Rule 3 - Silence**: AI MUST NOT speak during user silence under any circumstances. No "small talk" after 8 seconds. Only responds to explicit user questions or [SERVER] messages.
    - **Rule 9 - Appointment Flow**: AI forbidden from confirming appointments before [SERVER] ✅ appointment_created. After confirmation, AI MUST stay silent (no re-validation loops).
    - **Guard System**: Post-filter detects forbidden words ("קבעתי", "התור נקבע") without server approval and sends immediate correction.
    - **Loop Prevention**: pending_slot cleared immediately after appointment creation to prevent re-validation cycles.
  - **NLP Appointment Parser**: Server-side GPT-4o-mini text analysis with 3 actions: `hours_info` (general inquiry), `ask` (check availability), `confirm` (create appointment).
  - **Appointment Flow (Nov 2025)**: Date/time first → Check availability → Suggest alternatives if busy → Collect name (verbal) → Collect phone (DTMF with auto-submit after 10 digits) → **DTMF triggers NLP** → Create appointment.
  - **Customer Data Persistence (Nov 2025)**: 4-path hydration system ensures name survival:
    - Path 1: Direct save to crm_context.customer_name when context exists
    - Path 2: Temporary cache (self.pending_customer_name) when context doesn't exist yet
    - Path 3: Auto-hydration when crm_context created (session_description event)
    - Path 4: Auto-hydration when crm_context created by DTMF handler
    - Fallback in confirm handler retrieves from both sources and writes back to context
  - **NLP Trigger (Nov 2025 - CRITICAL FIX)**: NLP runs **AFTER** DTMF is added to conversation_history (line 4102-4109), ensuring NLP sees complete data: date✅ time✅ name✅ phone✅. Previous race condition (NLP before history update) caused silent failures.
  - **NLP Debug Logging (Nov 2025)**: Added comprehensive logging to track NLP execution: conversation hash, deduplication logic, action detection (none/hours_info/ask/confirm), CRM context state, missing data detection, and appointment creation flow. Logs prefixed with 🔍 [DEBUG], 🎯 [NLP], ✅ [CONFIRM] for easy debugging.
  - **CRITICAL FIX (Nov 2025)**: NLP now ALWAYS runs after DTMF (removed customer_name check). The IF statement that prevented NLP from running when customer_name was missing has been removed - NLP extracts name from conversation history. Added extensive error handling and logging throughout entire NLP pipeline (entry → GPT call → result parsing) to catch exceptions early.
  - **Appointment Creation Fix (Nov 2025)**: Fixed `create_appointment_from_realtime` to correctly handle `CreateAppointmentOutput` dataclass instead of expecting dict. Now checks `hasattr(result, 'appointment_id')` and converts to dict for backwards compatibility.
  - **AI Step-by-Step Guidance (Nov 2025)**: AI prompt explicitly instructs to collect name FIRST, then phone SECOND (never together). AI instructs: "תקליד מספר טלפון במקלדת הטלפון - 10 ספרות שמתחילות ב-05" - NO mention of # key.
  - **DTMF Auto-Submit (Nov 2025)**: After collecting 10 digits, system automatically processes phone number without requiring # terminator. AI does NOT instruct user to press # - system handles it silently.
  - **Availability Check**: Real-time slot validation with up to 3 alternative suggestions if requested time is taken.
- **Hebrew-Optimized VAD**: `threshold = min(175, noise_floor + 80)` for reliable Hebrew speech detection.
- **Smart Barge-In**: 400ms grace period, 150 RMS threshold, 400ms minimum voice duration, 800ms cooldown.
- **Cost Tracking (Nov 2025)**: Real-time chunk-based audio tracking with precise cost calculations. Automatic cost summary displayed at end of EVERY call with breakdown: user audio (chunks→minutes→$), AI audio (chunks→minutes→$), total in USD and NIS (₪). Supports all OpenAI Realtime models including new gpt-realtime (2025).
- **Error Resilience**: DB query failures fall back to minimal prompt.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.

### Feature Specifications
- **Call Logging**: Comprehensive tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication of lead information.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using a 2-step matching process.
- **Multi-Tenant Isolation**: Complete business data separation.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**:
  - GPT-4o-mini for FAQ responses and server-side NLP parsing for appointments.
  - Realtime API using **gpt-4o-realtime-preview** for phone calls, with specific model parameters (max_tokens: 300, temperature: 0.18).
  - Hebrew-Optimized VAD and Barge-in mechanisms.
  - Internal Whisper transcription with auto-detect.
- **Google Cloud Platform** (legacy/fallback): STT Streaming API v1 for Hebrew, TTS Standard API.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.