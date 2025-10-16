# Overview

AgentLocator is a Hebrew CRM system tailored for real estate businesses. It features a customizable AI-powered assistant that automates lead management by integrating with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. Its primary purpose is to streamline the sales pipeline for real estate professionals, offering fully customizable AI assistant and business names through dynamic placeholders.

# User Preferences

Preferred communication style: Simple, everyday language.

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
- **Audio Processing**: μ-law to PCM conversion, optimized barge-in detection, and calibrated VAD for Hebrew speech, with immediate TTS interruption and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, and TTS caching.

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
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
## Background Thread Cleanup Fix (BUILD 100.8)
**Critical Fix**: Prevent post-call crashes by properly cleaning up background threads.

**Problem Analysis:**
System crashed ~30 seconds after call completion because 4 background threads continued running after WebSocket closed:
1. `finalize_in_background` - Call summary and DB finalization
2. `create_in_background` - Call log creation  
3. `save_in_background` - Conversation turn persistence
4. `process_in_background` - Customer intelligence processing

These daemon threads attempted to access DB/resources after the WebSocket connection ended, causing crashes.

**Root Cause:**
- `finally` block only cleaned up `tx_thread`
- Background threads were daemon=True but never joined
- No tracking or timeout mechanism existed
- Orphaned operations accessed closed connections

**Solution:**
1. **Thread Tracking**: Added `self.background_threads = []` list
2. **Registration**: All 4 thread types now append to tracking list on creation
3. **Enhanced Cleanup**: `finally` block now:
   - Waits for all background threads with 3s timeout each
   - Logs completion status per thread
   - Handles hung threads gracefully
   - Ensures clean shutdown before WebSocket close

**Files Changed:**
- `server/media_ws_ai.py`:
  - Line 140: Initialize background_threads tracking
  - Lines 2025, 2083, 2140, 2218: Track thread creation
  - Lines 632-646: Enhanced finally block with comprehensive cleanup

**Impact:**
✅ No more post-call crashes
✅ All background operations complete before shutdown
✅ Graceful handling of slow/hung threads
✅ Clean resource cleanup guaranteed

**Testing:**
Verified handler initialization with thread tracking enabled.
