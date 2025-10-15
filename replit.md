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
  - **Professional UI with AI Summaries (BUILD 94)**: WhatsApp page displays AI-generated conversation summaries only for closed conversations (when Leah ends the chat) with lazy loading for optimal performance.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar Integration**: AI checks real-time availability and suggests appointment slots.
- **Meeting Scheduling**: Automatic detection and coordination with calendar-aware suggestions.
- **Customizable AI Assistant (BUILD 95)**: No hardcoded names - fully customizable per business using {{business_name}} placeholder in prompts and greetings. Assistant introduces herself only once in initial greeting, then focuses on conversation without repeating her name.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**: STT Streaming for Hebrew and TTS Wavenet for natural Hebrew voice.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.