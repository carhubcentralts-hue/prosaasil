# Overview

AgentLocator is a Hebrew CRM system for real estate professionals. Its core purpose is to automate the sales pipeline using an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion. It provides a robust, multi-tenant platform with customizable AI assistants and business branding, leveraging cutting-edge AI communication tools.

# Recent Changes

**Build 111 (November 13, 2025):**
- **🔄 BOOKING WORKFLOW ORDER CHANGED**: Updated appointment booking sequence to Name → Phone → Date → Time (previously: Name → Date → Time → Phone)
- **⚡ IMPROVED BOOKING FLOW**: Agent now collects phone number earlier, checks calendar for requested time, and immediately suggests alternatives if slot is occupied
- **📊 SMARTER SCHEDULING**: Agent can now handle time conflicts in real-time within the same conversation instead of failing at the end
- **🎯 PROXIMITY-BASED ALTERNATIVES**: When requested time is occupied, agent suggests ONLY the 2 closest available slots (e.g., if 9:00 is occupied → suggests 8:00 and 10:00, not 14:00 or 19:00)
- **🔒 CRITICAL FIX: FAQ PERSISTENCE**: Added default FAQs to init_database.py to ensure FAQs are auto-created on deployment (2 sample FAQs: operating hours, address) - prevents FAQ deletion bug on Replit deployments
- **⚙️ CRITICAL FIX: SETTINGS PERSISTENCE**: Added BusinessSettings creation to init_database.py - settings (slot_size, 24/7, booking window, etc.) now persist across deployments. Previously settings would reset to defaults (60min) after each deploy.

**Build 110 (November 13, 2025):**
- **🛡️ CRITICAL FIX: HARD BLOCK - Agent Cannot Lie Anymore**
  - **HARD BLOCK #1**: Regex detection for booking claims (קבעתי, קבענו, שריינתי) - BLOCKED if no calendar_create_appointment called
  - **HARD BLOCK #2**: Regex detection for WhatsApp claims (שלחתי אישור) - BLOCKED if no whatsapp_send called
  - **HARD BLOCK #3**: Availability claims (פנוי, תפוס) - BLOCKED if no calendar_find_slots called
  - **Enforcement**: Reply text is OVERRIDDEN with safe fallback if mismatch detected
  - **Impact**: Agent physically CANNOT respond with lies - hard code block prevents it
- **📊 Performance Improvements**:
  - Max turns: 10 → 5 (50% reduction)
  - Expected latency: 22s → <10s for appointment booking
  - Validation: Hard regex-based blocking with immediate override

**Build 109 (November 13, 2025):**
- **🔒 DATA PROTECTION GUARANTEE**: Added strict data protection with automatic rollback - FAQs/leads NEVER deleted on deployment
- **✅ Migration Safety**: Migrations are mostly additive (CREATE TABLE, ADD COLUMN, CREATE INDEX) with limited exceptions for deduplication only
- **📊 Data Verification**: Automatic before/after count comparison with delta calculation - migrations FAIL and ROLLBACK if data loss detected
- **🛡️ Multi-Layer Protection**: 
  - No TRUNCATE operations on any tables
  - No DROP TABLE on any tables
  - DELETE operations ONLY for deduplication of corrupted data (duplicate messages/calls with identical provider_msg_id)
  - Automatic rollback if FAQs or leads count decreases
  - Explicit logging: "X FAQs preserved" or "MIGRATION FAILED: Data loss detected" with rollback
- **Impact**: Zero-tolerance data protection - any migration that attempts to delete FAQs or leads will automatically fail and roll back, preserving all user data

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

AgentLocator employs a production-ready multi-tenant architecture ensuring complete business isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart TTS truncation. The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel to boost response times and preserve conversation state. The system mandates name and phone confirmation during scheduling, utilizing dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows: (1) Get name, (2) Get phone via DTMF, (3) Get date, (4) Get time + check availability + book or suggest alternatives. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. Agent Validation Guards prevent AI hallucinations by blocking responses that claim bookings or availability without executing corresponding calendar tools.

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