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