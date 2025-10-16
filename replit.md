# Overview

AgentLocator is a Hebrew CRM system designed for real estate businesses. It features a customizable AI-powered assistant that automates lead management by integrating with Twilio and WhatsApp to process real-time calls, collect lead information, and schedule meetings. The system utilizes advanced audio processing for natural conversations, aiming to streamline the sales pipeline for real estate professionals. The AI assistant and business names are fully customizable using dynamic placeholders.

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
- **Audio Processing**: μ-law to PCM conversion, optimized barge-in detection, and calibrated VAD for Hebrew speech.
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from the business configuration with dynamic placeholders for personalization.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice, telephony optimization (8kHz), SSML smart pronunciation (domain lexicon, punctuation enhancement, name pronunciation helper), and TTS caching. Configurable via environment flags.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation with intelligent business resolution based on E.164 phone numbers.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **Conversation Memory**: Full conversation history for contextual AI responses (10 messages, unlimited length).
- **WhatsApp Integration**: Supports both Twilio and Baileys (direct WhatsApp Web API) with optimized response times, full message storage, and context management (customer name, lead status, previous messages).
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots, with automatic creation of calendar entries.
- **Customizable AI Assistant**: Fully customizable names and introductions via prompts and greetings, with assistant introducing herself only once.
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