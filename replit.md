# Overview

This is AgentLocator, a Hebrew CRM system with AI-powered real-time call processing integrated with Twilio and WhatsApp. The system features "Leah", an intelligent Hebrew real estate agent that handles live phone conversations, collects lead information, and schedules meetings. The application handles incoming calls through Twilio's Media Streams with enhanced WebSocket stability, natural barge-in capabilities, and focused lead collection protocols.

## Recent Major Enhancements (September 2025)

- **Complete Frontend Rebuild**: Production-grade React 19 + Vite + Tailwind v4 with RTL/mobile-first design
- **Secure Authentication System**: Login, forgot/reset password with JWT and role-based access control
- **Professional Admin Dashboard**: System-wide KPIs, provider status, activity monitoring for admin/manager roles
- **Business Dashboard**: Tenant-specific overview with leads, calls, WhatsApp metrics and quick actions
- **Responsive RTL Layout**: Professional sidebar navigation with mobile bottom nav and Hebrew typography
- **Enhanced WebSocket Stability**: Heartbeat mechanism every 15-20 seconds prevents idle timeouts
- **Improved Barge-in Handling**: 200ms grace period with immediate TTS interruption for natural conversation flow  
- **Google STT Streaming Primary**: Hebrew language with real estate speech contexts for accurate transcription
- **Focused AI Agent**: Maximum 15-word responses, single questions, clarification requests over assumptions
- **Intelligent Meeting Scheduling**: Automatic detection when lead data is complete, offers specific time windows
- **Clean Logging**: Reduced noise, focus on key conversation events and system status

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM for database operations
- **WebSocket Support**: Eventlet-based WebSocket handling for Twilio Media Streams with `simple-websocket` library
- **WSGI Server**: Gunicorn with eventlet worker for production deployment
- **Database**: PostgreSQL (with SQLite fallback for development) using SQLAlchemy models
- **Authentication**: JWT-based authentication with role-based access control (admin, business_owner, business_agent, read_only)

## Frontend Architecture
- **Framework**: React 19 with modern hooks and concurrent features
- **Build Tool**: Vite 5.4.19 with optimized development and production builds
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font)
- **Routing**: React Router v7 with AuthGuard/RoleGuard protection and role-based redirects
- **State Management**: Context API for authentication state with HTTP-only cookie sessions
- **Components**: Production-grade component library with accessibility, loading states, and mobile-first design
- **Pages**: Login/Forgot/Reset authentication flows + Admin/Business dashboard overviews
- **Security**: CSRF protection, secure redirects, and role-based access control integration

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with enhanced stability and keepalive mechanisms
- **Audio Processing**: μ-law to PCM conversion with optimized barge-in detection (200ms grace period)
- **WebSocket Protocol**: Custom protocol supporting Twilio's `audio.twilio.com` subprotocol with heartbeat
- **Call Management**: TwiML generation for call routing and recording
- **Voice Activity Detection**: Calibrated VAD with dynamic threshold adjustment for Hebrew speech
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation with role-based permissions
- **Call Logging**: Comprehensive call tracking with transcription and status management
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support
- **Intelligent Lead Collection**: Automated capture of area, property type, budget, timing, and contact info
- **Meeting Scheduling**: Smart detection of complete lead profiles with automatic meeting coordination
- **Hebrew Real Estate Agent**: "Leah" - specialized AI agent with 15-word response limit and focused questioning

## External Dependencies

- **Twilio**: Primary telephony service for voice calls and WhatsApp Business API
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations with optimized prompts and response limits
- **Google Cloud Platform**: Primary STT Streaming with Hebrew speech contexts, TTS Wavenet for natural Hebrew voice
- **PostgreSQL**: Production database system
- **WhatsApp Business API**: Message handling through Twilio's WhatsApp integration
- **Baileys Library**: Alternative WhatsApp Web API client for direct WhatsApp connectivity

The system is designed for deployment on cloud platforms like Replit with environment-based configuration and supports both development and production modes with appropriate WebSocket and HTTP handling.