# Overview

AgentLocator is a Hebrew CRM system for real estate businesses, featuring an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. It processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to streamline the sales pipeline for real estate professionals with fully customizable AI assistants and business names.

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
- **Audio Processing**: μ-law to PCM conversion, optimized barge-in detection, calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, and TTS caching.
- **Performance Optimization**: Sub-second greeting, natural number pronunciation using SSML, and faster STT response times (0.65s silence detection).
- **Intelligent Error Handling**: Smart responses for STT failures, including silence on first failure and a prompt for repetition on subsequent failures.

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

## System Design Choices
- **AI Response Optimization**: Max tokens reduced to 200 for shorter, more conversational responses using `gpt-4o-mini`.
- **Robustness**: Implemented thread tracking and enhanced cleanup for background processes to prevent post-call crashes. Extended ASGI handler timeout to 15s to ensure complete cleanup before WebSocket closure.
- **STT Reliability**: Implemented a confidence threshold (>=0.5) to reject unreliable transcriptions and extended STT timeout to 3 seconds for Hebrew speech.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing across all AI prompts and conversational elements.
- **Cold Start Optimization**: Automatic warmup of services (OpenAI, STT, TTS, DB) on startup and via a dedicated `/warmup` endpoint to eliminate first-call latency.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses and creation of `BusinessContactChannel`.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.