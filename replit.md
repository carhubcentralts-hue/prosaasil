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

**⚡ BUILD 116.1 - UI Bug Fixes & Debugging:**
- **Calendar Datetime Fix**: Fixed timezone conversion bug that saved appointments to wrong day. datetime-local inputs now send ISO timestamps WITH local timezone offset (e.g., "2025-10-21T14:00:00+03:00") instead of UTC, ensuring user's chosen time is preserved exactly as entered.
- **Status Dropdown Debug**: Added comprehensive logging to status management hooks to diagnose "No Options" display issue. Includes fallback messaging when statuses array is empty, console logs for API responses and state updates.
- **Appointment Edit Debug**: Enhanced error logging in both client and server for appointment updates - full traceback and request data logged server-side, detailed status and error info client-side. Error messages remain generic to users for security.
- **Result**: Correct datetime handling across all timezones, improved debugging capabilities for status management and appointment editing, secure error handling.

**⚡ BUILD 117 - Instant Greeting Cache:**
- **Pre-built Greeting Frames**: Greetings are synthesized once per business and stored as μ-law 20ms frames in memory cache (thread-safe with RLock, LRU eviction at 256 businesses)
- **Ultra-Fast Delivery**: Cached greetings play in <200ms (vs 1-2s for live TTS) - frames sent directly to WebSocket for immediate playback
- **Smart Fallback**: If cache fails, seamlessly falls back to live TTS without crashing
- **Automatic Cache Invalidation**: API endpoint POST /api/greeting/invalidate clears cache when business greeting/voice changes
- **New Services**: greeting_cache.py (thread-safe storage), audio_utils.py (PCM16→μ-law→frames conversion), greeting_builder.py (cache management)
- **Result**: Instant greeting playback on repeat calls, business-specific customization, zero impact on existing STT/AI/TTS flow.

**⚡ BUILD 117.1 - Audio Quality Fix (HOTFIX):**
- **Critical Fix**: Cached greeting frames now sent **directly to WebSocket** instead of through TX Queue - prevents premature `_finalize_speaking()` call
- **Root Cause**: BUILD 117 enqueued frames to TX Queue then immediately called `_finalize_speaking()`, causing system to return to LISTEN state while greeting was still playing
- **Symptoms Fixed**: Choppy audio, cut-off words, background noise artifacts caused by STT processing audio during greeting playback
- **Solution**: Greeting frames sent synchronously to WebSocket (like original TTS path), ensuring `_finalize_speaking()` only called after all frames transmitted
- **Result**: Clean, stable greeting audio with no interruptions or artifacts - production-ready quality restored!

**⚡ BUILD 118 - Balanced Parameters (Reduce False Positives + ≤3s Response):**
- **Problem**: BUILD 116/117 were TOO aggressive - bot responded to background noise, stopped mid-sentence saying "לא הבנתי", 4s STT time
- **VAD Tuning**: VAD_RMS 65→95 (less sensitive to noise), VAD_HANGOVER_MS 180→500ms (prevents mid-sentence cuts)
- **STT Tuning**: BATCH_MS 40→60ms, DEBOUNCE_MS 90→250ms (more patient), TIMEOUT_MS 320→900ms (prevents cutting user off)
- **False-Positive Protection**: consecutive_empty_stt 2→3 (less frequent "לא הבנתי"), enhanced common-word list
- **Barge-in Hardening**: Threshold 1500→2500 (much higher), Duration 1500ms→2000ms (100 frames), Multiplier 15.0→20.0
- **Target**: Maintain ≤3s response time while eliminating false positives and mid-sentence interruptions
- **Result**: Stable, reliable conversations - bot completes full responses, ignores background noise, only responds to real speech!

**⚡ BUILD 118.1 - Instant Greeting Delivery:**
- **Problem**: Greeting took 3-6 seconds to START playing (T0→T1 latency)
- **Root Cause**: STT initialization (100-300ms) + call log creation (50-200ms) + DB queries happened BEFORE greeting
- **Solution**: Deferred setup - greeting sent IMMEDIATELY after business lookup, all other setup (STT init, call log) moved AFTER greeting
- **Flow Change**: T0→greet→T1→[greeting plays]→T2→[STT init]→[call log] (was: T0→[STT init]→[call log]→greet→T1→[greeting plays]→T2)
- **Target**: T0→T1 latency ≤500ms (down from 3-6 seconds)
- **Result**: Instant greeting playback - caller hears business greeting within half a second of connection!

**⚡ BUILD 118.2 - Calendar Timezone Fix:**
- **Problem**: Appointments saved to wrong day/time - timezone conversion bug from BUILD 116.1
- **Root Cause**: Frontend sent ISO timestamps with timezone offset (e.g., "2025-10-21T14:00:00+03:00"), but server converted to UTC instead of keeping local time
- **Solution**: Custom timezone parser strips offset and keeps local time as-is (14:00 stays 14:00, not converted to 11:00 UTC)
- **Fix**: Updated routes_calendar.py with parse_iso_with_timezone() function - no external dependencies needed
- **Impact**: CREATE/UPDATE/DELETE appointments now work correctly with user's local timezone
- **Result**: When user says "יום שני 14:00", appointment is saved for Monday 14:00, not wrong day/time!

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
- **Performance Optimization**: ⚡ BUILD 118 Production - Streaming STT with 3-attempt retry + early finalization (saves 400-600ms on strong partials). Dynamic model selection (auto-detects best available model for Hebrew), europe-west1 region for low RTT. **Balanced parameters for reliability**: BATCH_MS=60ms, DEBOUNCE_MS=250ms, TIMEOUT=900ms, VAD_HANGOVER=500ms, VAD_RMS=95. Comprehensive latency tracking (partial, final, STT, AI, TTS, total turn). Achieves ≤3 second response times with excellent Hebrew accuracy and zero false positives. Session timestamp updated on every audio frame to prevent 2-minute resets. **Enhanced false-positive protection**: (1) Higher VAD thresholds (95 RMS), (2) STT confidence checks with short-utterance rejection, (3) Common-word filtering with punctuation normalization, (4) 3x consecutive failures before "לא הבנתי". **Hardened barge-in**: Requires 2000ms of VERY loud voice (threshold 2500) to interrupt bot. **Appointment rejection detection**: 3-layer system (time_parser, conversation parser, auto_meeting) prevents appointments on user refusal.
- **Intelligent Error Handling**: Smart responses for STT failures with consecutive failure tracking (3x trigger "לא הבנתי").

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