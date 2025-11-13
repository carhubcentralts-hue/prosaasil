# Overview

AgentLocator is a Hebrew CRM system for real estate professionals. Its core purpose is to automate the sales pipeline using an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion. It provides a robust, multi-tenant platform with customizable AI assistants and business branding, leveraging cutting-edge AI communication tools.

# Recent Changes

**Build 109 (November 13, 2025):**
- **🔒 DATA PROTECTION GUARANTEE**: Added explicit data protection to migrations - NO user FAQs/leads ever deleted on deployment
- **✅ Migration Safety**: Migrations are additive (CREATE TABLE, ADD COLUMN, CREATE INDEX) with limited exceptions
- **📊 Data Verification**: Automatic before/after count comparison with delta calculation and data loss detection
- **🛡️ Multi-Layer Protection**: 
  - No TRUNCATE operations on user tables
  - No DROP TABLE on user tables  
  - DELETE operations only for deduplication of corrupted data (duplicate messages/calls with same provider ID)
  - Explicit verification: Reports "X FAQs preserved" or "ERROR: Y FAQs DELETED!" if data loss detected
- **Impact**: System now actively monitors and reports any unexpected data loss during deployment migrations

**Build 108 (November 12, 2025):**
- **🔥 CRITICAL FAQ FIX**: Fixed patterns_json keyword matching - FAQ system now checks keywords/patterns BEFORE embeddings for instant matches
- **⚡ FIX #1: Hybrid Matching Strategy**: FAQ now uses 2-step approach: (1) Check patterns_json keywords for exact matches (score=1.0), (2) Fall back to embeddings if no keyword match
- **🎯 FIX #2: Case-Insensitive Matching**: Keywords are normalized (lowercase + strip) for reliable matching regardless of user input case
- **🔧 FIX #3: Bidirectional Substring Match**: Checks both "pattern in query" and "query in pattern" to catch partial matches (e.g., "חדר קריוקי" matches "כמה זה חדר קריוקי")
- **📱 FIX #4: Mobile Bottom Navigation Spacing**: Added padding-bottom (80px) to all pages on mobile to prevent bottom navigation bar from hiding content
- **📊 Impact**: FAQ responses now work with business-specific keywords (e.g., "חדר קריוקי" → instant match), sub-100ms keyword lookup vs 6s embeddings, perfect accuracy on exact terms; mobile pages now fully scrollable without content hiding

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a production-ready multi-tenant architecture ensuring complete business isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart TTS truncation. The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel to boost response times and preserve conversation state. The system mandates name and phone confirmation during scheduling, utilizing dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. Agent Validation Guards prevent AI hallucinations by blocking responses that claim bookings or availability without executing corresponding calendar tools.

Multi-tenant security is paramount, with business identification via `BusinessContactChannel` or `Business.phone_e164`, rejection of unknown phone numbers, and isolated prompts, agents, leads, calls, and messages per business. It includes universal warmup for active businesses, handles 401 errors for missing authentication, and implements comprehensive Role-Based Access Control (RBAC).

Performance optimization includes explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=60` (15-word hard limit for phone calls) for `gpt-4o-mini` and a `temperature` of 0.15. Audio streaming uses a `tx_q` queue with 90% backpressure to prevent send queue overflow. A FAQ Hybrid Fast-Path uses a 2-step matching approach: first, `patterns_json` keyword matching (sub-100ms, score=1.0), then an OpenAI embeddings fallback (cosine similarity ≥0.78). Keywords are case-insensitive with bidirectional substring matching. FAQ runs BEFORE AgentKit on phone calls only. Channel filtering ensures voice-only FAQs, and WhatsApp send requests route to AgentKit to execute the `whatsapp_send` tool. Prompts are loaded exclusively from `BusinessSettings.ai_prompt`. STT reliability benefits from relaxed validation, Hebrew numbers context, and a 3-attempt retry for improved accuracy. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Agent behavioral constraints enforce not verbalizing internal processes.

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
- **🔒 Data Protection**: Database migrations are strictly additive with automatic verification - NO user data deleted on deployment. All FAQs, leads, messages, calls, and other user data are permanently preserved.

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
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using 2-step matching: (1) patterns_json keyword matching (instant, score=1.0), (2) OpenAI embeddings fallback (cosine similarity ≥0.78). Keywords are case-insensitive with bidirectional substring matching. Intent-based routing and channel filtering (voice-only). Bypasses Agent SDK for ≤200 char queries on phone calls.
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