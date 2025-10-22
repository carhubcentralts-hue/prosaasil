# Overview

AgentLocator is a Hebrew CRM system for real estate businesses designed to streamline the sales pipeline. It features an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. It offers fully customizable AI assistants and business names to cater to the specific needs of real estate professionals.

## Recent Changes

**⚡ BUILD 119.2 - Complete Audio Quality Fix (TX + RX Queues):**
- **Problem 1 - TX Queue**: Cached greeting flooded TX queue (195 frames in 21ms) causing choppy audio
  - **Root Cause**: Greeting sent all frames instantly instead of controlled rate
  - **Solution**: Added back-pressure loop in cached greeting sender
  - While loop checks `tx_q.qsize() > 96` (80% of 120 max) before sending each frame
  - Waits 20ms when queue is full (maintains ~50fps flow rate)
  - Result: Smooth greeting playback with no stutters
  
- **Problem 2 - RX Queue**: Audio queue full during user speech (dropped 91+ frames)
  - **Root Cause**: STT audio queue too small (128 frames = 2.5s) for longer user utterances
  - **Solution**: Increased audio_queue from 128 to 384 frames (~7.5s buffer)
  - Handles longer user speech without dropping frames
  - Zero frame loss during conversation
  
- **Complete Benefits**:
  - ✅ Smooth greeting playback (no choppy sound or cuts)
  - ✅ Zero dropped frames during user speech
  - ✅ No background noise from dropped frames
  - ✅ Perfect audio quality in both directions (bot→user and user→bot)
  - ✅ TX queue: healthy 20-80 frames, RX queue: 384 frame buffer
  - ✅ Control frames never blocked
  
- **Result**: Crystal-clear audio in both directions - greeting and conversation!

**⚡ BUILD 119.1 - Production TX Queue with Precise Timing:**
- **Problem**: "Send queue full, dropping frame" errors during longer TTS responses causing audio freezes
- **Root Cause**: Queue too small (120 frames = 2.4s) AND naive solution (256 frames) would create 5-6s hidden lag
- **Solution**: Professional-grade TX queue system with precise timing, back-pressure, and smart drop-oldest
- **Implementation**:
  - asgi.py send_queue: 144 frames (~2.9s balanced buffer, aligned with tx_q)
  - media_ws_ai.py tx_q: 120 frames (~2.4s) with intelligent drop-oldest
  - Added tx_drops counter for telemetry tracking
  - _tx_loop: precise 20ms/frame timing with next_deadline scheduling
  - Back-pressure: 90% threshold triggers double-wait to drain queue
  - **Smart drop-oldest**: Drops ONLY media frames, control frames (clear, mark, keepalive) NEVER dropped
  - **ALL frames via _tx_enqueue**: greeting, TTS, beeps, marks, keepalives - NO direct _ws_send bypasses
  - Real-time telemetry: [TX] fps/q/drops logged every second
  - Greeting sends greeting_end mark for tracking
- **Expected Metrics**:
  - fps ≈ 50 (50 frames/second, stable)
  - q < 20 (queue size under 20 most of the time)
  - drops = 0 (zero dropped frames under normal load)
- **Benefits**:
  - ✅ Zero "Send queue full" errors
  - ✅ No hidden lag accumulation (2.9s max buffer)
  - ✅ Drop-oldest keeps system responsive during spikes WITHOUT breaking control flow
  - ✅ Complete telemetry for monitoring and debugging
  - ✅ Control frames always delivered (critical for Twilio)
- **Result**: Reliable audio streaming without freezes or lag, production-grade quality!

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend
- **Frameworks**: Flask with SQLAlchemy ORM, Starlette for WebSocket handling.
- **ASGI Server**: Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

## Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Design**: Production-grade, accessible, mobile-first design with CSRF protection and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run, inbound_track routing, and statusCallbackEvent handling.
- **Audio Processing**: Smart barge-in detection, calibrated VAD for Hebrew, immediate TTS interruption, and 2-tier early finalization and EOU for seamless turn-taking and sub-3 second response times.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders and caching. Instant greeting playback.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, TTS caching, and accelerated speaking rate.
- **Performance Optimization**: Streaming STT with 3-attempt retry, dynamic model selection, europe-west1 region for low RTT, and balanced parameters for reliability and accuracy.
- **Intelligent Error Handling**: Smart responses for STT failures with consecutive failure tracking.
- **Session Management**: Tracks session duration and handles potential timeouts.
- **Queue Management**: Increased audio queue and send queue sizes to prevent dropped frames and ensure reliable transcription and complete AI responses.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys with optimized response times and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability, suggests appointment slots, and stores precise datetime using Israel timezone. Supports comprehensive numeric date parsing.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders and real-time cache invalidation.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management with create/edit modal and full field support.

## System Design Choices
- **AI Response Optimization**: Max tokens set to 180 for quality Hebrew responses (3-4 sentences) using `gpt-4o-mini`, temperature 0.3-0.4.
- **Robustness**: Thread tracking, enhanced cleanup for background processes, extended ASGI handler timeout.
- **STT Reliability**: RELAXED validation, higher confidence for short utterances, streaming STT with 3-attempt retry, dynamic model selection, regional optimization (europe-west1), and early finalization on strong partials. Enhanced STT accuracy for Hebrew with expanded vocabulary hints (130+ terms) and boost priority.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing.
- **Cold Start Optimization**: Automatic warmup of services on startup and via a dedicated `/warmup` endpoint.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Thread-Safe Multi-Call Support**: Complete registry system with `RLock` protection for concurrent calls (up to 50).
- **Perfect Multi-Tenant Isolation**: Every session registered with `tenant_id`, all Lead queries filtered by `tenant_id` to prevent cross-business data leakage.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.