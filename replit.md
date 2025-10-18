# Overview

AgentLocator is a Hebrew CRM system for real estate businesses, featuring an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. It processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to streamline the sales pipeline for real estate professionals with fully customizable AI assistants and business names.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (October 18, 2025)
- Fixed invoice.payment_id database schema with proper foreign key to payment.id
- Removed "Support Management" card from business overview page
- Added lead selection dropdowns to payment and contract creation modals
- Unified tasks and reminders into single "Reminders" feature
- **CRITICAL FIX**: Fixed duplicate lead creation - system now properly deduplicates leads by phone number instead of creating new lead for each call
- **Enhanced Reminders System**: Converted CRM page from "tasks" to "reminders" with comprehensive modal supporting note, description, date/time, priority, type, and optional lead association
- **Database Schema Update**: LeadReminder model now supports general business reminders with nullable lead_id and direct tenant_id ownership for proper multi-tenant isolation
- **MAJOR PERFORMANCE OPTIMIZATION**: Reduced call response latency by ~545ms (from 5s to 3.9-4.2s expected):
  - STT_BATCH_MS: 150ms → 90ms (60ms faster)
  - STT_PARTIAL_DEBOUNCE_MS: 180ms → 120ms (60ms faster)
  - VAD_HANGOVER_MS: 800ms → 375ms (425ms faster)
  - **IMPORTANT**: Update production secrets to match new optimized values for latency improvements to take effect
- **UI Terminology Fix**: All "משימות" (tasks) changed to "תזכורות" (reminders) throughout CRM and Lead pages
- **Status Dropdown Fix**: Fixed lead status dropdown in LeadsPage - now properly opens when clicking status badge without triggering navigation to lead detail page. Applied to both desktop (table) and mobile (card) views with proper event stopPropagation.
- **Lead Integration**: All dropdowns (CRM reminders, invoices, contracts) are connected to `/api/leads` and display real leads from database with name and phone number.

# System Architecture

## Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams, compatible with Cloud Run.
- **ASGI Server**: Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

## Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support.
- **Audio Processing**: μ-law to PCM conversion, optimized barge-in detection, calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, and TTS caching.
- **Performance Optimization**: Sub-second greeting, natural number pronunciation using SSML, and faster STT response times (0.65s silence detection).
- **Intelligent Error Handling**: Smart responses for STT failures, including silence on first failure and a prompt for repetition on subsequent failures.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation with intelligent business resolution via E.164 phone numbers.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports both Twilio and Baileys with optimized response times, full message storage, and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots, with automatic calendar entry creation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings (phone calls and WhatsApp) supporting dynamic placeholders and real-time cache invalidation.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation with lead selection dropdowns for creating invoices and contracts.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management with create/edit modal, full field support (note, description, date/time, priority, type, lead association), and support for both lead-specific and general business reminders.
- **Lead Integration in All Modals**: CRM reminders, payment/invoice creation, and contract creation all feature lead selection dropdowns that fetch real leads from `/api/leads` endpoint.

## System Design Choices
- **AI Response Optimization**: Max tokens reduced to 200 for shorter, more conversational responses using `gpt-4o-mini`.
- **Robustness**: Implemented thread tracking and enhanced cleanup for background processes to prevent post-call crashes. Extended ASGI handler timeout to 15s to ensure complete cleanup before WebSocket closure.
- **STT Reliability**: Implemented a confidence threshold (>=0.5) to reject unreliable transcriptions and extended STT timeout to 3 seconds for Hebrew speech.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing across all AI prompts and conversational elements.
- **Cold Start Optimization**: Automatic warmup of services (OpenAI, STT, TTS, DB) on startup and via a dedicated `/warmup` endpoint to eliminate first-call latency.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses and creation of `BusinessContactChannel`.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Streaming STT**: Implemented a session-per-call architecture for streaming STT, ensuring stability, true real-time streaming, and adherence to Google's API limits. Features a dispatcher pattern for utterance routing, continuous audio feed, and smart fallback to single-request STT if streaming fails. Optimized queue (maxsize=16) with aggressive consumption (20ms timeout) to prevent audio backlog and dropped frames.
- **Thread-Safe Multi-Call Support**: Complete registry system (`_sessions_registry`) with `RLock` protection for concurrent calls. Each call_sid has isolated session + dispatcher state. Supports up to MAX_CONCURRENT_CALLS (default: 50) with capacity protection and automatic session reaper (120s timeout).
- **Perfect Multi-Tenant Isolation**: Every session registered with tenant_id (business_id), all Lead queries filtered by tenant_id, zero cross-business data leakage. Business auto-detected by to_number on "start" event before session initialization.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
