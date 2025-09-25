# Overview

AgentLocator is a Hebrew CRM system featuring an AI-powered real estate agent named "Leah." It integrates with Twilio and WhatsApp to process real-time calls, collect lead information, and schedule meetings. The system uses Twilio's Media Streams for stable real-time audio, natural barge-in capabilities, and focused lead collection, aiming to automate lead management for real estate businesses.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Eventlet-based WebSocket handling for Twilio Media Streams.
- **WSGI Server**: Gunicorn with eventlet worker.
- **Database**: PostgreSQL (SQLite for development).
- **Authentication**: JWT-based with role-based access control (admin, business_owner, business_agent, read_only).
- **Security**: SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning.

## Frontend Architecture
- **Framework**: React 19.
- **Build Tool**: Vite 5.4.19.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with enhanced stability and keepalive mechanisms.
- **Audio Processing**: μ-law to PCM conversion with optimized barge-in detection (200ms grace period).
- **WebSocket Protocol**: Custom protocol for Twilio's `audio.twilio.com` subprotocol.
- **Call Management**: TwiML generation for call routing and recording.
- **Voice Activity Detection**: Calibrated VAD for Hebrew speech.
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support.
- **Intelligent Lead Collection**: Automated capture of key lead information.
- **Meeting Scheduling**: Automatic detection and coordination when lead data is complete.
- **Hebrew Real Estate Agent**: "Leah" - specialized AI agent with 15-word response limit and focused questioning.
- **Customizable Status Management**: Per-business custom lead statuses with default Hebrew options.
- **Billing and Contracts**: Integrated payment processing (PayPal, Tranzilla) and contract generation.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**: STT Streaming for Hebrew and TTS Wavenet for natural Hebrew voice.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.