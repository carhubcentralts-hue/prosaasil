# Overview

AgentLocator is a Hebrew CRM system for real estate businesses. It features an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. Its primary goal is to streamline the sales pipeline for real estate professionals with fully customizable AI assistants and business names.

**⚡ BUILD 113 - TRANSCRIPTION ACCURACY FIX:**
- **CRITICAL FIX**: Hebrew speech was cutting off mid-sentence due to aggressive timeouts
- **STT Utterance Timeout**: 300ms → 1200ms (allows users to finish complete sentences)
- **VAD_HANGOVER_MS**: 220ms → 600ms (tolerates natural breathing pauses between words)
- **Audio Validation Thresholds**: Relaxed from 60/40 to 50/30 (accepts quieter speech for better accuracy)
- **Trade-off**: Slight latency increase (~300-500ms) for significantly better transcription quality
- **Result**: Users can now speak naturally without system cutting them off prematurely

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
- **Performance Optimization**: ⚡ BUILD 113 Accuracy-focused - BASIC model STT only (1.2s timeout for complete sentences), VAD silence detection with natural pause tolerance (600ms hangover), Early EOU detection, comprehensive latency tracking (ASR, AI, TTS, Total). Achieves <2.5 second response times with better transcription quality. Session timestamp updated on every audio frame to prevent 2-minute resets. **3-layer false-positive protection**: (1) Relaxed audio validation (50/30 thresholds - allows quieter speech), (2) STT confidence checks with short-utterance rejection, (3) Common-word filtering with punctuation normalization. **Appointment rejection detection**: 3-layer system (time_parser, conversation parser, auto_meeting) prevents appointments on user refusal.
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
- **STT Reliability**: RELAXED validation allows quieter speech for better accuracy - amplitude threshold 50, RMS threshold 30, confidence threshold 0.3. Short utterances (≤2 words) require confidence ≥0.6 to prevent responding to noise. ⚡ BUILD 113: Utterance timeout 1.2s (was 0.3s - users can finish sentences), BASIC model only. numpy/scipy dependencies added for advanced audio analysis.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing.
- **Cold Start Optimization**: Automatic warmup of services on startup and via a dedicated `/warmup` endpoint.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Streaming STT**: Session-per-call architecture for streaming STT, ensuring stability, real-time streaming, and adherence to Google's API limits. Features a dispatcher pattern, continuous audio feed, and smart fallback.
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