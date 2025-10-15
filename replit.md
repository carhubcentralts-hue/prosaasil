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