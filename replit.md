# Overview

AgentLocator is a Hebrew CRM system for real estate professionals, designed to automate the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion through customizable AI assistants and business branding, providing a robust, multi-tenant platform with cutting-edge AI communication tools.

# Recent Changes

**Build 100 (November 12, 2025):**
- **🚨 CRITICAL SECURITY FIX**: Fixed authentication bypass vulnerability in `useAuthState()` - catch block now explicitly sets `isAuthenticated: false` and clears user data (was using `...prev` which could leak authentication state)
- **🔥 CRITICAL BAILEYS FIX**: Fixed auto-reconnect issue - Baileys now automatically cleans up socket + deletes session + reconnects on ANY disconnect (was keeping stale socket, preventing auto-reconnect until frontend refresh)
- **🔧 FIX #1: WhatsApp UI Crash Fix**: Removed blocking `alert()` calls in sendMessage - prevents page freeze when sending messages
- **🔧 FIX #2: Message Loading Fix**: Fixed `/api/crm/threads/{id}/messages` to query both `from_number` AND `to_number` - now loads complete conversations (was missing outbound messages)
- **🔧 FIX #3: Real-Time Polling**: Added 3-second polling for WhatsApp messages with bubble UI display - no more manual refresh needed
- **🔒 Security Impact**: All protected routes (including `/app/whatsapp`) now properly enforce authentication - direct URL access without valid session redirects to login
- **⚡ WhatsApp Impact**: Bot now responds immediately to messages even after network hiccups - no frontend refresh needed for reconnection

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator features a production-ready multi-tenant architecture ensuring complete business isolation. It uses Twilio Media Streams for real-time communication with disabled barge-in, Hebrew-optimized Voice Activity Detection (VAD), and smart TTS truncation. The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel, boosting response times and preserving conversation state with a singleton pattern to eliminate cold starts. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. Agent Validation Guards prevent hallucinated bookings and availability claims by blocking responses that claim "קבעתי" or "תפוס/פנוי" without executing corresponding calendar tools.

Multi-Tenant Security: Business identification via `BusinessContactChannel` or `Business.phone_e164`, rejection of unknown phone numbers, isolated prompts, agents, leads, calls, and messages per business, universal warmup for active businesses, 401 errors for missing authentication context, and comprehensive Role-Based Access Control (RBAC).

Performance is optimized with explicit OpenAI timeouts (4s + max_retries=1), increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=120` for `gpt-4o-mini` and a `temperature` of 0.15. A FAQ Hybrid Fast-Path uses OpenAI embeddings (cosine similarity ≥0.78) with keyword regex fallback, Hebrew normalization, and channel filtering for sub-2s responses (~1-1.5s) on voice calls (≤200 chars), running BEFORE AgentKit for simple queries. WhatsApp send requests route to AgentKit to execute the `whatsapp_send` tool. Prompts are loaded exclusively from `BusinessSettings.ai_prompt`. STT reliability benefits from relaxed validation, Hebrew numbers context, 3-attempt retry for +30-40% accuracy on numbers, and longest partial persistence. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Agent behavioral constraints enforce not verbalizing internal processes.

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
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using OpenAI embeddings + keyword patterns with Hebrew normalization, intent-based routing, and channel filtering (voice-only). Bypasses Agent SDK for ≤200 char queries.
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