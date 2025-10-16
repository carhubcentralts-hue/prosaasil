# Overview

AgentLocator is a Hebrew CRM system featuring a customizable AI-powered real estate assistant. It automates lead management for real estate businesses by integrating with Twilio and WhatsApp to process real-time calls, collect lead information, and schedule meetings. The system uses advanced audio processing for natural conversations, aiming to streamline the sales pipeline for real estate professionals. The AI assistant name and business name are fully customizable per business using dynamic placeholders.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams (Cloud Run compatible).
- **ASGI Server**: Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

## Frontend Architecture
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support.
- **Audio Processing**: μ-law to PCM conversion with optimized barge-in detection and calibrated VAD for Hebrew speech.
- **WebSocket Protocol**: Starlette WebSocketRoute with Twilio's `audio.twilio.com` subprotocol.
- **Call Management**: TwiML generation for call routing and recording with WSS.
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking.
- **Custom Greetings (BUILD 95)**: Initial phone greeting loads from `greeting_message` field in Business table with {{business_name}} placeholder support for personalized introductions.
- **Business Identification Fix (BUILD 97)**: Critical fix for `to_number` extraction from Twilio WebSocket - now correctly identifies business by the phone number called, enabling proper greeting and prompt loading. Added robust numpy/scipy fallback handling to prevent crashes when packages unavailable.
- **Natural TTS Upgrade (BUILD 98)**: Production-grade Hebrew TTS with WaveNet-D voice, telephony optimization @ 8kHz, SSML smart pronunciation (domain lexicon for acronyms/locations/terms), punctuation enhancement, name pronunciation helper (confidence-based hyphenation), and TTS caching for common phrases. Fully configurable via ENV flags (TTS_VOICE, TTS_RATE, TTS_PITCH, ENABLE_TTS_SSML_BUILDER, ENABLE_HEBREW_GRAMMAR_POLISH, TTS_CACHE_ENABLED).

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation with intelligent business resolution.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **Conversation Memory**: Full conversation history for contextual AI responses (10 messages, unlimited length).
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support with optimized response times.
  - **Performance Optimizations**: Direct processing (no threading overhead), immediate response times, connection pooling.
  - **Message Storage**: Full messages stored without truncation (removed 80-char limit), 50-message retention per lead.
  - **Conversation Memory (BUILD 92)**: AI loads last 10 messages for full context - no more forgetting or repetition!
  - **Context Management**: Full conversation history passed to AI with customer name, lead status, and all previous messages.
  - **Automatic Appointment Creation (BUILD 93)**: Detects appointment requests and creates calendar entries with customer details and preferred times.
  - **Professional UI with AI Summaries (BUILD 94)**: WhatsApp page displays AI-generated conversation summaries only for closed conversations (when AI assistant ends the chat) with lazy loading for optimal performance.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar Integration**: AI checks real-time availability and suggests appointment slots.
- **Meeting Scheduling**: Automatic detection and coordination with calendar-aware suggestions.
- **Customizable AI Assistant (BUILD 95)**: No hardcoded names - fully customizable per business using {{business_name}} placeholder in prompts and greetings. Assistant introduces herself only once in initial greeting, then focuses on conversation without repeating her name.
- **Greeting Management UI (BUILD 96)**: Agent Prompts page now includes dedicated fields for initial greetings (phone calls and WhatsApp). Greetings support {{business_name}} placeholders and load from Business table with real-time cache invalidation for immediate updates.
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

# Recent Changes (BUILD 98 + Critical Fixes)

## Natural Voice TTS Upgrade
**Files Added:**
- `server/services/hebrew_ssml_builder.py` - Smart SSML builder with domain lexicon and pronunciation fixes
- `server/services/punctuation_polish.py` - Automatic punctuation enhancement for STT output
- `.env.tts.example` - Complete TTS configuration template
- `TTS_UPGRADE_SUMMARY.md` - Full feature documentation

**Files Modified:**
- `server/services/gcp_tts_live.py` - Core TTS with WaveNet-D, SSML, caching, and ENV configuration
- `server/media_ws_ai.py` - Integrated upgraded TTS with punctuation polish and fallback handling
  - **Cleanup**: Removed deprecated `TTS_SPEAKING_RATE` variable (dead code)
  - **Cleanup**: Fallback TTS now reads all settings from ENV (voice, rate, pitch) - no hardcoded values

**Features Delivered:**
1. **Natural Voice**: WaveNet-D with telephony profile (8kHz) - no more "plastic" sound
2. **Smart Pronunciation**: SSML builder with Hebrew lexicon for acronyms (CRM→"סי-אר-אם"), locations (ראשל"צ→"ראשון לציון"), phone prefixes
3. **Punctuation Enhancement**: Automatic grammar fixes, transition word commas, cleaned speech patterns
4. **Name Helper**: Confidence-based pronunciation (hyphenation for difficult names, letter-by-letter spelling for very low confidence)
5. **TTS Caching**: Hash-based caching for common phrases (faster responses)
6. **Full ENV Control**: TTS_VOICE, TTS_RATE (0.96), TTS_PITCH (-2.0), feature flags for SSML/polish/cache
7. **Zero Hardcoded Values**: All TTS configuration controlled via ENV - primary service and fallback use same variables

**Architecture:**
- **Primary TTS**: `gcp_tts_live.py` with full feature set (SSML, caching, pronunciation)
- **Fallback TTS**: `media_ws_ai.py` basic synthesis (if primary fails) - uses same ENV variables
- **Legacy Code**: `server/services/tts_gcp.py` (not in use, kept for reference)
- **Single Source of Truth**: All TTS parameters read from ENV variables - no code changes needed for voice tuning

**Configuration:**
See `.env.tts.example` for complete setup guide with A/B testing combinations.

## Critical Production Fix (BUILD 99)
**Problem**: Application crashed in production deployment after playing greeting - Google Cloud TTS/STT clients failed to initialize due to credentials path mismatch.

**Root Cause**: 
- `lazy_services.py` tried to parse `GOOGLE_APPLICATION_CREDENTIALS` as JSON string, but it was a file path (`/tmp/gcp_credentials.json`)
- ASGI WebSocket initialization happened before Flask app initialization, credentials not set early enough

**Files Fixed:**
- `asgi.py` - Added GCP credentials setup BEFORE any imports (lines 34-50)
- `server/services/lazy_services.py` - Smart credentials handler: JSON string OR file path support

**Solution:**
1. ASGI now creates `/tmp/gcp_credentials.json` immediately on startup
2. Lazy services now handle both JSON strings and file paths gracefully
3. Fallback to default Google SDK credential discovery if needed

**Result**: Production deployment now works - TTS/STT services initialize correctly after greeting.