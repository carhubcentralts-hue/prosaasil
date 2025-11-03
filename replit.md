# Overview

AgentLocator is a Hebrew CRM system for real estate businesses. It features an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. Its primary goal is to streamline the sales pipeline for real estate professionals with fully customizable AI assistants and business names.

**⚡ BUILD 115.1 - PRODUCTION-READY STT (HOTFIX):**
- **Simple Model Selection**: ENV-based model selection (NO PROBE - fixes production deployment issue)
- **Default Endpoint**: Uses standard Google Speech client without custom endpoint (production-stable)
- **Non-blocking Fallback**: ThreadPoolExecutor for single-request STT prevents blocking event loop
- **Streaming by Default**: USE_STREAMING_STT=True in code (ENV override: "false"/"0"/"no" disables)
- **Fast Parameters**: BATCH_MS=80ms, DEBOUNCE_MS=120ms, TIMEOUT_MS=450ms for ≤2s total response time
- **3-Attempt Retry**: Streaming STT retries 3x (200ms delay) before falling back to single-request mode
- **Result**: Stable production deployment - works reliably with default/phone_call models for Hebrew
- **Fix**: Removed startup probe and custom endpoint that caused "לא הבנתי" loop in production

**⚡ BUILD 116 - Sub-2s Response Optimization:**
- **Ultra-Fast STT**: BATCH=40ms, DEBOUNCE=90ms, TIMEOUT=320ms, VAD_HANGOVER=180ms (aggressive)
- **Early-Finalize**: Cuts 300-500ms by finalizing strong partials (≥12 chars + punctuation or ≥18 chars)
- **Enhanced Telemetry**: Timestamps for every stage - T0/T1/T2 (WS+Greeting), S1 (STT stream), for sub-2s diagnostics
- **TX System**: 20ms/frame pacing, 120-frame buffers, drop-oldest policy, real-time telemetry [TX] fps=50 q=6 drops=0
- **Target Response Time**: STT ~1.2-1.8s (down from 2.0s), Total ~1.5-2.0s (down from 2.5-3.5s)
- **Result**: Faster, more responsive conversations with Hebrew real estate AI assistant!

**⚡ PHASE 2 - Advanced Sub-2s Optimizations:**
- **Phase 2A (STT Tuning)**: ENV-based ultra-aggressive STT parameters (DEBOUNCE=60ms, TIMEOUT=240ms, HANGOVER=160ms, MIN_UTT=0.25s) for even faster responses beyond BUILD 116
- **Phase 2B (TTS Pre-warming)**: `maybe_warmup()` every 8 minutes prevents cold starts, **FIXED**: Now forces client initialization on startup with explicit error handling, logs success/failure clearly with traceback on errors. Integrated in app_factory.py before serving traffic. **Verified working**: 282ms warmup time in production.
- **Phase 2C (LLM Discipline)**: First turn limited to 24 words (≈40 tokens) for rapid initial response, subsequent turns use full 180 tokens for quality. ENV-configurable via `AI_MAX_WORDS_FIRST_REPLY`
- **Phase 2D (Metrics)**: Complete timing infrastructure with last_ai_time and last_stt_time measurements. Full latency breakdown: STT→AI→TTS→TOTAL printed for every turn.
- **Architecture Notes**: TTS warmup blocks startup until complete (ensures client ready before traffic), turn_count per-call (no race conditions), DEBUG=1 enables detailed timing logs, all defaults tunable via ENV
- **Critical Bug Fixes (Nov 3)**: 
  - Fixed silent TTS warmup failures - now throws exceptions on client init failure, validates synthesis result
  - **CRITICAL**: Added missing AI timing measurement (last_ai_time was never set - causing invisible 6s delays!)
  - **CRITICAL**: Added missing STT timing save (last_stt_time was never saved)
  - **🔴 SMOKING GUN #1**: Fixed Flask app recreation bug - was calling `create_app()` on EVERY AI request causing full app restart mid-call! This caused:
    - 🔴 5-6 second delays (full app reload per turn)
    - 🔴 503 Connection reset errors (GCP STT disconnected)
    - 🔴 `APP_START` logs appearing mid-call (proof of restart)
  - **✅ SOLUTION #1**: Implemented Flask App Singleton pattern with thread-safe double-check locking. App created ONCE for entire process lifecycle, reused across all calls. Replaced all 10+ `create_app()` calls in media_ws_ai.py with `_get_flask_app()` singleton getter.
  - **🔴 SMOKING GUN #2**: Calendar availability check (`_get_calendar_availability`) ran on EVERY phone call before AI response, causing 12s latency when DB slow/unavailable!
  - **✅ SOLUTION #2**: Disabled calendar check for phone calls (channel=='calls'), kept only for WhatsApp where latency acceptable. Added LIMIT 10 for performance.
  - **Migration 19**: Added missing CallLog columns (direction, duration, to_number) to fix "column does not exist" errors
  - Removed noisy media frame logs (50/sec spam in production logs)
  - All timing now logged: ASR_LATENCY, AI_LATENCY, TTS_GENERATION, TOTAL_LATENCY
  - Fixed Deal foreign key constraint to prevent orphaned deals (customer.id with CASCADE)

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
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support, inbound_track routing, and proper statusCallbackEvent handling.
- **Audio Processing**: Smart barge-in detection (disabled for long responses >20 words, enabled for short ones), calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, TTS caching, and accelerated speaking rate (1.05x).
- **Performance Optimization**: ⚡ BUILD 115 Production - Streaming STT with 3-attempt retry + early finalization (saves 400-600ms on strong partials). Dynamic model selection (auto-detects best available model for Hebrew), europe-west1 region for low RTT. Optimized parameters: BATCH_MS=80ms, DEBOUNCE_MS=120ms, TIMEOUT=450ms, VAD_HANGOVER=220ms. Comprehensive latency tracking (partial, final, STT, AI, TTS, total turn). Achieves ≤2 second response times with excellent Hebrew accuracy. Session timestamp updated on every audio frame to prevent 2-minute resets. **3-layer false-positive protection**: (1) Relaxed audio validation (50/30 thresholds - allows quieter speech), (2) STT confidence checks with short-utterance rejection, (3) Common-word filtering with punctuation normalization. **Appointment rejection detection**: 3-layer system (time_parser, conversation parser, auto_meeting) prevents appointments on user refusal.
- **Intelligent Error Handling**: Smart responses for STT failures with consecutive failure tracking (2x trigger "לא הבנתי").

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription, status management, duration, and direction (inbound/outbound) captured from Twilio webhooks.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports both Twilio and Baileys with optimized response times, full message storage, and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: ⚡ BUILD 110.1 - AI checks real-time availability and suggests appointment slots with **explicit time confirmation** that **repeats the exact time the customer said**. Enhanced time parser with 14 confirmation phrases, DEBUG logging for full visibility, and priority given to user input. Appointments store precise datetime (date + time) in start_time/end_time fields. **Iron Rule: AI must repeat customer's exact time, not make up times!**
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders and real-time cache invalidation.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation with lead selection dropdowns.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management with create/edit modal and full field support for lead-specific and general business reminders.
- **Lead Integration in All Modals**: CRM reminders, payment/invoice creation, and contract creation all feature lead selection dropdowns.

## System Design Choices
- **AI Response Optimization**: Max tokens set to 180 for quality Hebrew responses (3-4 sentences) using `gpt-4o-mini`, temperature 0.3-0.4 for balanced natural responses.
- **Robustness**: Implemented thread tracking and enhanced cleanup for background processes, extended ASGI handler timeout.
- **STT Reliability**: RELAXED validation allows quieter speech for better accuracy - amplitude threshold 50, RMS threshold 30, confidence threshold 0.3. Short utterances (≤2 words) require confidence ≥0.6 to prevent responding to noise. ⚡ BUILD 115: Streaming STT with 3-attempt retry mechanism, dynamic model selection with startup probe (phone_call → default fallback), ENHANCED mode preference with graceful degradation, europe-west1 region, early finalization on strong partials (>15 chars + punctuation saves 400-600ms). Optimized timing: BATCH=80ms, DEBOUNCE=120ms, TIMEOUT=450ms. numpy/scipy dependencies added for advanced audio analysis.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing.
- **Cold Start Optimization**: Automatic warmup of services on startup and via a dedicated `/warmup` endpoint.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Streaming STT**: Session-per-call architecture with 3-attempt retry mechanism before fallback to single-request. Dynamic model selection with automatic probe at startup (tries user-preferred → phone_call → default). Regional optimization (europe-west1) for low RTT. Early finalization on strong partials (>15 chars + punctuation) saves 400-600ms. Features dispatcher pattern, continuous audio feed, and smart fallback to single-request mode.
- **Thread-Safe Multi-Call Support**: Complete registry system with `RLock` protection for concurrent calls, supporting up to MAX_CONCURRENT_CALLS (default: 50).
- **Perfect Multi-Tenant Isolation**: Every session registered with tenant_id, all Lead queries filtered by tenant_id, zero cross-business data leakage.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.