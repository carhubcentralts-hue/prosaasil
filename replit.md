# Overview

AgentLocator is a Hebrew CRM system centered around an AI-powered real estate agent named "Leah." Its primary purpose is to automate lead management for real estate businesses by integrating with Twilio and WhatsApp to process real-time calls, collect lead information, and schedule meetings. The system uses advanced audio processing for natural conversations and aims to streamline the sales pipeline for real estate professionals.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams (Cloud Run compatible).
- **ASGI Server**: Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control.
- **Security**: SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

## Frontend Architecture
- **Framework**: React 19.
- **Build Tool**: Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support.
- **Audio Processing**: μ-law to PCM conversion with optimized barge-in detection.
- **WebSocket Protocol**: Starlette WebSocketRoute with Twilio's `audio.twilio.com` subprotocol.
- **Call Management**: TwiML generation for call routing and recording with WSS.
- **Voice Activity Detection**: Calibrated VAD for Hebrew speech.
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **Conversation Memory**: Full conversation history stored and used for contextual AI responses.
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time lead creation and deduplication (one lead per phone number).
- **Calendar Integration**: AI checks real-time availability and suggests appointment slots.
- **Meeting Scheduling**: Automatic detection and coordination with calendar-aware suggestions.
- **Hebrew Real Estate Agent**: "Leah" - specialized AI agent with context-aware responses and calendar integration.
- **Customizable Status Management**: Per-business custom lead statuses with default Hebrew options.
- **Billing and Contracts**: Integrated payment processing (PayPal, Tranzilla) and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.

# Recent Changes

## BUILD 89 (October 15, 2025) - CRITICAL FIX: ImportError in Lead Creation Thread
- **🔧 CRITICAL FIX**: Fixed ImportError causing lead creation thread to crash
  - **ROOT CAUSE**: Thread imported non-existent `CustomerIntelligenceService` → ImportError → thread dies → no call_log created
  - **SYMPTOM**: "No call_log found for final summary" + "Call SID not found for status update"
  - **FIX 1**: Changed import from `CustomerIntelligenceService` to correct `CustomerIntelligence`
  - **FIX 2**: Updated service instantiation to use correct class name
  - **Files**: server/routes_twilio.py (lines 150, 169)
  - **Verification**: Import test passes ✅
- **Impact**: Lead creation thread now runs successfully - calls are saved and processed correctly

## BUILD 88 (October 15, 2025) - CRITICAL FIX: Missing to_number in Lead Creation
- **🔧 CRITICAL FIX**: Fixed "null value in column to_number" error in lead creation thread
  - **ROOT CAUSE**: `_create_lead_from_call` created call_log without to_number → NOT NULL constraint violation
  - **FIX 1**: Added `to_number` parameter to `_create_lead_from_call` function
  - **FIX 2**: Added `to_number` field to CallLog model in models_sql.py
  - **FIX 3**: Extract `to_number` from Twilio webhook in `incoming_call`
  - **FIX 4**: Pass `to_number` to lead creation thread with default fallback
  - **Files**: server/routes_twilio.py, server/models_sql.py
- **Impact**: Lead creation now works without errors - all calls save with complete data

## BUILD 87 (October 14, 2025) - CRITICAL FIX: Duplicate call_sid Race Condition
- **🔧 CRITICAL FIX**: Fixed race condition causing duplicate call_log records and "Failing row contains" errors
  - **ROOT CAUSE**: Multiple threads created call_log simultaneously → duplicate call_sid → database errors → "Call SID not found"
  - **FIX 1 - Database Level**: Added unique constraint on call_log.call_sid (prevents duplicates at DB level)
  - **FIX 2 - Code Level**: Added duplicate error handling with rollback in _create_call_log_on_start
  - **Migration 15**: Removes existing duplicates then creates unique index on call_sid
  - **Files**: server/db_migrate.py, server/media_ws_ai.py
- **Impact**: Eliminates production errors - calls now save correctly without duplicates

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**: STT Streaming for Hebrew and TTS Wavenet for natural Hebrew voice.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.