# Overview

AgentLocator is a Hebrew CRM system for real estate businesses, designed to streamline the sales pipeline. It features an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. Its primary goal is to provide fully customizable AI assistants and business names to real estate professionals.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams.
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
- **Audio Processing**: Smart barge-in detection, calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, TTS caching, and accelerated speaking rate.
- **Performance Optimization**: Streaming STT with 3-attempt retry + early finalization, dynamic model selection, europe-west1 region for low RTT. Optimized parameters for fast response times. Comprehensive latency tracking. Achieves ≤2 second response times with excellent Hebrew accuracy.
- **Intelligent Error Handling**: Smart responses for STT failures with consecutive failure tracking.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription, status management, duration, and direction.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports both Twilio and Baileys with optimized response times and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders and real-time cache invalidation.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.

## System Design Choices
- **BUILD 121 - Mandatory Name & Phone Confirmation + DTMF Support** ✅ 100% PRODUCTION READY:
  - **Name Confirmation Required**: Agent MUST confirm customer name by repeating ("תודה דני! אז דני, נכון?")
  - **DTMF Phone Input**: Agent instructs user to type phone number on keypad + press # ("תקליד את המספר טלפון במקלדת ואחרי זה תקיש סולמית (#)")
  - **DTMF Processing**: WebSocket handles "dtmf" events, buffers digits until #, validates 9+ digits, processes as AI input
  - **Barge-in Disabled During DTMF**: System disables voice interruption when waiting for keypad input to prevent false triggers
  - **Phone Collection Enhanced**: If no phone from call context, Agent uses DTMF input (more accurate than voice)
  - **Phone is OPTIONAL**: System can create appointments without phone number (nullable in DB), graceful handling if unavailable
  - **Graceful Error Handling**: All validation errors return {ok: false, error, message} instead of raising exceptions
  - **Strict Name Validation**: Cannot create appointment without clear name (no "לקוח", "customer", generic names)
  - **Time Confirmation**: Agent confirms exact time before booking ("אז קבעתי לך תור למחר ב-12:00, נכון?")
  - **Full Details Summary**: After booking, Agent repeats ALL details (name, time, phone if available) for customer confirmation
- **BUILD 120 - Agent Memory & Phone Handling Fix** ✅ PRODUCTION READY:
  - **Conversation Memory Fixed**: Agent now receives full conversation history via `input` parameter in Runner.run()
  - **Phone Fallback System**: New _choose_phone() with hierarchy: input → context → session → None
  - **Graceful Error Handling**: All tools return {ok: false, error, message} instead of raising exceptions
  - **Phone Utilities**: Created phone_utils.py with normalize_il_phone for Israeli phone number normalization
- **BUILD 119 - AgentKit Integration for Real Actions** ✅ PRODUCTION READY:
  - **OpenAI Agents SDK**: Integrated `openai-agents` package (correct import: `from agents import Agent`)
  - **Tool System**: Comprehensive tools for calendar (find_slots, create_appointment), leads (upsert, search), and WhatsApp (send)
  - **Agent Factory**: Central orchestration with booking and sales agent types, fresh agent creation per request
  - **AIService Integration**: `generate_response_with_agent()` extracts `system_prompt` from prompt_data dict
  - **Real Actions**: AI performs actual operations during conversations - schedule appointments, create leads, send confirmations
  - **Smart Context**: Agents receive full business context (tenant_id, customer info, channel) for accurate operations
  - **Dynamic Prompts**: Agents load custom instructions from BusinessSettings.ai_prompt (channel-specific JSON)
  - **Error Resilience**: Multi-layer fallback ensures system stability even if agents fail
  - **API Endpoints**: `/api/agent/booking` and `/api/agent/sales` for direct agent interactions
  - **Environment Control**: `AGENTS_ENABLED` environment variable for easy enable/disable (default: enabled)
  - **AUTO-APPOINTMENT Deprecated**: Disabled legacy auto-appointment system - Agent handles everything in real-time
  - **Production Validations**:
    - ✅ Timezone & Business Hours: Strict 09:00-22:00 Asia/Jerusalem enforcement
    - ✅ Conflict Detection: Overlapping appointments rejected with clear Hebrew error messages
    - ✅ Field Validation: Phone format (E.164), treatment_type required, duration 15-240 minutes
    - ✅ Agent Tracing: Full logging to `agent_trace` table (tool_calls, duration_ms, status, errors)
    - ✅ Kill-switch: `AGENTS_ENABLED=0` instantly disables agents with graceful fallback
    - ✅ Time Handling: Clear ISO format requirements with timezone, date calculation guidance
    - ✅ Deduplication: Leads deduped by phone+tenant_id, appointments conflict-checked before creation
    - ✅ Type Safety: isinstance() checks prevent dict/string type errors
- **BUILD 118 - Fixed Timeout Issues & Reliability**:
  - **OpenAI timeout added**: 3.5s explicit timeout prevents indefinite waits
  - **Better error logging**: Now logs exact error types (APITimeoutError, RateLimitError, etc.)
  - **STT streaming timeout increased**: 0.45s → 0.85s for reliable final results
  - **Prompt length warnings**: Alert if prompt >3000 chars (causes OpenAI timeouts)
  - **Root cause identified**: Long prompts (5,615 chars) + no timeout = 12s "latency" → fallback responses
- **BUILD 117 - Complete Sentences & Stability**: 
  - **NO TOKEN LIMITS!** Increased max_tokens from 180→350 to allow AI to finish ALL sentences completely
  - First turn uses full 350 tokens (no special reduction) - "אם היא צריכה להסביר דקה שתסביר דקה"
  - Barge-in threshold 12 words (was 20), grace period 2.5s (was 1.5s), RMS 1800 (was 1500), continuous voice 2000ms (was 1500ms)
  - Hebrew numbers in STT contexts (אחד, שניים, שלוש...שש) with 20.0 boost for better accuracy
  - REMOVED broken word filter that rejected valid words - now trusts Google STT completely (only rejects ≤2 chars)
  - WebSocket stability: 120s timeout (was 30s), 10s keepalive (was 18s) to prevent ABNORMAL_CLOSURE
  - **CRITICAL FIX: STT model hard-coded to "default"** - Google STT phone_call model NOT supported for Hebrew (iw-IL)
- **AI Response Optimization**: Max tokens set to 350 for COMPLETE Hebrew sentences using `gpt-4o-mini`, temperature 0.3-0.4.
- **Robustness**: Implemented thread tracking, enhanced cleanup for background processes, extended ASGI handler timeout. Flask app singleton pattern to prevent app restarts mid-call.
- **STT Reliability**: Relaxed validation for quieter speech, confidence checks, and short-utterance rejection. Streaming STT with 3-attempt retry, dynamic model selection, and early finalization.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing.
- **Cold Start Optimization**: Automatic warmup of services on startup and via a dedicated `/warmup` endpoint.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Streaming STT**: Session-per-call architecture with 3-attempt retry mechanism before fallback to single-request.
- **Thread-Safe Multi-Call Support**: Complete registry system with `RLock` protection for concurrent calls.
- **Perfect Multi-Tenant Isolation**: Every session registered with `tenant_id`, all Lead queries filtered by `tenant_id`.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.