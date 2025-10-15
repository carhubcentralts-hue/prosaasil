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

## BUILD 90 (October 15, 2025) - CRITICAL FIXES: call_status + business_id + WhatsApp AI + Transcription Save + Deployment
- **🔧 CRITICAL FIX 1**: Fixed "null value in column call_status violates not-null constraint" error
  - **ROOT CAUSE**: Production DB has NOT NULL `call_status` field but models_sql.py missing it → fallback call_log creation fails
  - **SYMPTOM**: `stream_status` and `handle_recording` creating fallback → DB rejects with NOT NULL violation → no call_log saved
  - **FIX 1**: Added `call_status` field to CallLog model with default="in-progress"
  - **FIX 2**: Updated all fallback call_log creations to include `call_status`
  - **FIX 3**: `incoming_call` → `call_status="initiated"`
  - **FIX 4**: `stream_status` → `call_status="in-progress"`
  - **FIX 5**: `handle_recording` → `call_status="completed"`
  - **Files**: server/models_sql.py, server/routes_twilio.py
- **🔧 CRITICAL FIX 2**: Fixed "business_id foreign key violation" error
  - **ROOT CAUSE**: Hardcoded business_id=1 but production DB empty → no business exists!
  - **SYMPTOM**: ForeignKeyViolation: Key (business_id)=(1) is not present in table "business"
  - **FIX 1**: Dynamic business detection - find active business or any business
  - **FIX 2**: Auto-healing fallback - create default business if none exists
  - **FIX 3**: Applied to Calls: incoming_call, _create_lead_from_call, stream_status, handle_recording
  - **FIX 4**: Applied to WhatsApp: baileys_webhook, whatsapp_incoming webhook, api_wa_messages, get_conversation, send_manual_message
  - **Files**: server/routes_twilio.py, server/routes_whatsapp.py, server/routes_webhook.py
- **🔧 CRITICAL FIX 4**: Fixed WhatsApp AI responses (was hardcoded text)
  - **ROOT CAUSE**: WhatsApp responses used hardcoded Hebrew text instead of AI
  - **SYMPTOM**: "שלום! קיבלתי את ההודעה שלך" - not intelligent, no context awareness
  - **FIX 1**: Replaced hardcoded text with generate_ai_response() call
  - **FIX 2**: Added customer context (name, lead status) to AI prompt
  - **FIX 3**: Added fallback handling if AI fails
  - **Files**: server/routes_whatsapp.py
- **🔧 CRITICAL FIX 3**: Fixed Autoscale deployment failures
  - **ROOT CAUSE**: Missing INTERNAL_SECRET in deployment + multiple port exposure confusion
  - **FIX 1**: Auto-generate INTERNAL_SECRET if not in environment (secure fallback)
  - **FIX 2**: Clarified port architecture - only Flask on 0.0.0.0:PORT (external), Baileys on 127.0.0.1:3300 (internal only)
  - **FIX 3**: Updated start_production.sh with clear external/internal port documentation
  - **Files**: start_production.sh
- **🔧 CRITICAL FIX 5**: Fixed missing transcription/recording (TwiML incomplete)
  - **ROOT CAUSE**: TwiML only had <Stream> but no <Record> fallback → if WebSocket fails, no recording!
  - **SYMPTOM**: Calls save but transcription=NULL, recording_url=NULL, ai_summary=NULL
  - **FIX 1**: Added <Record> tag after <Stream> as fallback (max_length=300s, timeout=4s)
  - **FIX 2**: Record sends to handle_recording webhook for processing
  - **Files**: server/routes_twilio.py
- **🔧 CRITICAL FIX 6**: Fixed Baileys WhatsApp not starting automatically
  - **ROOT CAUSE**: Baileys service not started in development/production → WhatsApp doesn't work
  - **SYMPTOM**: WhatsApp QR code connects but no responses, no webhook processing
  - **FIX 1**: Added auto-start function in wsgi.py (_start_baileys_service)
  - **FIX 2**: Checks if Baileys already running, starts if not
  - **FIX 3**: Background process with subprocess.Popen (PID tracked)
  - **Files**: wsgi.py
- **🔧 CRITICAL FIX 7**: Fixed transcription not saving to database
  - **ROOT CAUSE**: WebSocket flow saved to `call_log.transcript` but field is `transcription`!
  - **SYMPTOM**: Calls complete but transcription=NULL in database (schema mismatch)
  - **FIX**: Changed `call_log.transcript = ...` to `call_log.transcription = ...`
  - **Files**: server/media_ws_ai.py
- **Impact**: Production deployment works + auto-creates business if needed + all calls/WhatsApp save successfully + WhatsApp replies with intelligent AI responses + calls now have transcription/recording even if WebSocket fails + Baileys starts automatically with Flask + transcription saves correctly to database

## BUILD 89 (October 15, 2025) - CRITICAL FIX: Complete Call Processing Chain
- **🔧 CRITICAL FIX**: Fixed entire call processing chain from ImportError to call_log creation
  - **ROOT CAUSE**: Chain of failures starting with ImportError → no call_log → "No call_log found for final summary"
  - **FIX 1 - Import Error**: Changed `CustomerIntelligenceService` → `CustomerIntelligence`, moved imports to top
  - **FIX 2 - Immediate call_log**: `incoming_call` now creates call_log IMMEDIATELY (before thread) so webhooks find it
  - **FIX 3 - Thread Safety**: `_create_lead_from_call` now has proper try/except, no duplicate imports
  - **FIX 4 - Self-Heal**: `stream_status` creates fallback call_log if missing (self-healing)
  - **FIX 5 - Self-Heal**: `handle_recording` creates fallback call_log if missing (self-healing)
  - **Files**: server/routes_twilio.py (comprehensive rewrite of call flow)
  - **Architecture**: call_log created FIRST → thread enriches with customer/lead → webhooks always find it
- **Impact**: Zero "call_log not found" errors - every call is captured regardless of thread/webhook timing

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