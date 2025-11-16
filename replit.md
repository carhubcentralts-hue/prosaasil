# Overview

AgentLocator is a Hebrew CRM system for real estate professionals designed to automate the sales pipeline. It features an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion. It provides a robust, multi-tenant platform with customizable AI assistants and business branding, leveraging cutting-edge AI communication tools to streamline operations and boost sales for real estate businesses.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a multi-tenant architecture with complete business isolation, integrating Twilio Media Streams for real-time communication. It features Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for improved response times and conversation state preservation. The system enforces name and phone confirmation during scheduling via dual input (verbal name, DTMF phone number) for streamlined booking. Channel-aware responses adapt messaging based on the communication channel, and a DTMF Menu System provides interactive voice navigation for phone calls. Agent Validation Guards prevent AI hallucinations by blocking unverified actions.

Security is paramount, ensuring business identification, rejection of unknown numbers, and isolated data (prompts, agents, leads, calls, messages) per business. It includes universal warmup for active businesses, handles authentication errors, and implements comprehensive Role-Based Access Control (RBAC).

Performance optimizations include explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a 2-step matching approach: keyword matching and an OpenAI embeddings fallback, with channel filtering to ensure voice-only FAQs. Prompts are loaded exclusively from `BusinessSettings.ai_prompt`. STT reliability benefits from relaxed validation, Hebrew numbers context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, and agent behavioral constraints prevent verbalization of internal processes.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` for secure business identification.
- **RBAC**: Role-based access control with admin/manager/business roles and impersonation support.
- **DTMF Menu**: Interactive voice response system for phone calls.
- **Data Protection**: Strictly additive database migrations with automatic verification.
- **OpenAI Realtime API**: Feature-flagged migration for phone calls, using dedicated asyncio threads, thread-safe queues, and bidirectional audio streaming.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.

### Feature Specifications
- **Call Logging**: Comprehensive tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys with optimized response times.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication of lead information.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings with dynamic placeholders.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using a 2-step matching process.
- **Multi-Tenant Isolation**: Complete business data separation and full RBAC.
- **Appointment Settings UI**: Allows businesses to configure slot size, availability, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: 
  - GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
  - **Realtime API** (`gpt-4o-realtime-preview`): Low-latency speech-to-speech for phone calls.
- **Google Cloud Platform** (legacy/fallback):
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.

# Recent Changes

## Realtime API Migration Progress (2025-11-16)

### 1. TX Counter Fix ✅
**Problem:** WS_STOP logs showed tx=0 despite frames being sent successfully.  
**Root Cause:** Audio output bridge sent 44 frames to tx_q, but `self.tx` counter was never incremented.  
**Fix:** Added `self.tx += 1` after successful `_ws_send()` in both Realtime and legacy paths.  
**Files:** `server/media_ws_ai.py`

### 2. Temperature Parameter Fix ✅
**Problem:** OpenAI Realtime API rejected temperature=0.15 (minimum is 0.6).  
**Fix:** Enforced minimum temperature: `max(0.6, temperature)` in session configuration.  
**Files:** `server/services/openai_realtime_client.py`

### 3. Hebrew STT Fix ✅
**Problem:** Whisper auto-detection transcribed English/Portuguese instead of Hebrew.  
**Fix:** Added explicit `"language": "he"` to input_audio_transcription config.  
**Result:** STT now correctly transcribes Hebrew speech.  
**Files:** `server/services/openai_realtime_client.py`

### 4. Audio Cutoff Fix ✅
**Problem:** AI responses cut off mid-sentence (e.g., "בטח! חדר דובאי מתאים עד" - missing end).  
**Root Causes:**
- `max_tokens=60` too low for full Hebrew sentences
- `silence_duration_ms=500` too short, triggering premature cutoff

**Fixes:**
- Increased `max_tokens`: 60 → 300 (allow full sentences)
- Increased `silence_duration_ms`: 500 → 800 (prevent mid-sentence cutoff)
- Increased `temperature`: 0.15 → 0.8 (more natural conversations)

**Files:** `server/media_ws_ai.py`

### 5. Audio Duplication Fix ✅
**Problem:** Audio would start → pause → repeat mid-sentence (stuttering effect).  
**Root Cause:** Processing multiple Realtime event types containing audio:
- `response.audio.delta` - streaming chunks (correct)
- `response.audio.done` - complete buffer (caused duplication)
- `response.output_item.done` - might contain audio (caused duplication)

**Fix:** 
- Only process `response.audio.delta` events
- Explicitly ignore `response.audio.done` and `response.output_item.done`
- Added event type logging to detect unexpected sources
- Added frame sequence tracking (1,2,3... vs 1,2,1,2)

**Files:** `server/media_ws_ai.py`

## Current Status
- ✅ Audio output working (μ-law format verified)
- ✅ Hebrew transcription accurate
- ✅ Full sentences without cutoff
- ✅ No audio duplication/stuttering
- ✅ TX counter tracking correctly
- 🔄 Testing audio smoothness and natural flow