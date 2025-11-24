# Overview

AgentLocator is a multi-tenant Hebrew CRM system for real estate professionals. It automates the sales pipeline with an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system aims to boost efficiency and sales conversion through advanced audio processing and customizable AI assistants, leveraging cutting-edge AI communication tools to streamline real estate operations.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator features a multi-tenant architecture with complete business isolation, integrating Twilio Media Streams for real-time communication. It includes Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant uses an Agent SDK for appointment scheduling and lead creation, maintaining conversation memory and utilizing an Agent Cache System. Name and phone number confirmation occur via dual input (verbal name, DTMF phone number), with channel-aware responses and a DTMF Menu System. Agent Validation Guards prevent AI hallucinations. Security features encompass business identification, rejection of unknown numbers, isolated data per business, universal warmup, and comprehensive Role-Based Access Control (RBAC) with a 4-tier hierarchy (system_admin, owner, admin, agent). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path employs a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, while agent behavioral constraints prevent verbalization of internal processes. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts, automatically loaded from `BusinessSettings.ai_prompt`.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` for secure business identification.
- **RBAC**: 4-tier role hierarchy.
- **Multi-Tenant Business Creation**: Atomic transaction for business and owner user creation.
- **DTMF Menu**: Interactive voice response system.
- **Data Protection**: Strictly additive database migrations.
- **User Management API** (BUILD 134): `/api/admin/users` endpoint with automatic RBAC filtering - system_admin sees all users, owner/admin see only their business users. Tenant-scoped password reset at `/api/admin/businesses/<id>/users/<user_id>/change-password`.
- **OpenAI Realtime API**: Integrates `gpt-4o-realtime-preview` for phone calls with asyncio threads and thread-safe queues.
- **AI Behavior Optimization**: Uses `gpt-4o-realtime-preview` (max_tokens: 300, temperature: 0.18) with 10 critical behavioral rules. Includes a server-side GPT-4o-mini NLP appointment parser for `hours_info`, `ask`, and `confirm` actions. The appointment flow prioritizes date/time, checks availability, collects name verbally, and phone via DTMF (10-digit auto-submit without `#`). Customer data persistence is handled by a 4-path hydration system. NLP runs after DTMF is added to conversation history to ensure complete data processing, with extensive logging.
- **Hebrew-Optimized VAD**: `threshold = min(175, noise_floor + 80)`.
- **Simplified Barge-In**: 350ms grace period, calibrated speech threshold, instant trigger on speech detection.
- **Cost Tracking**: Real-time chunk-based audio tracking, with cost summaries for user and AI audio displayed at the end of each call.
- **Error Resilience**: DB query failures fall back to minimal prompt.
- **Greeting System**: System prompt instructs AI to include a business-specific greeting in the first response after user speaks, integrating with the user's first question.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control supporting the 4-tier role hierarchy.
- **UI Navigation**: Main sidebar no longer shows separate "AI Prompts" menu item. All AI prompt editing (calls and WhatsApp) is consolidated into System Settings → AI Settings tab. AI tab access restricted to system_admin, owner, and admin roles only (not agent).
- **RBAC Sidebar** (BUILD 134): "Business Management" restricted to system_admin only (prevents owners from seeing other businesses). "User Management" accessible to system_admin/owner/admin (shows only their business users via automatic filtering).

### Feature Specifications
- **Call Logging**: Comprehensive tracking.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Customizable names and introductions.
- **Greeting Management UI**: Dedicated fields for initial greetings.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy.
- **Enhanced Reminders System**: Comprehensive management.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Multi-Tenant Isolation**: Complete business data separation.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice time.
- **CRM Tasks**: Redesigned to show task board with Pending, Overdue, and Completed columns. Task notifications are integrated into the NotificationPanel.
- **Consolidated AI Settings**: All AI prompt editing (for both calls and WhatsApp) is now accessed via System Settings → AI Settings tab, no longer as a separate sidebar menu item. The FAQ tab has been removed from System Settings.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini (FAQ, server-side NLP), `gpt-4o-realtime-preview` (phone calls), Hebrew-Optimized VAD, and Whisper transcription.
- **Google Cloud Platform**: (Legacy/fallback) STT Streaming API v1 for Hebrew, TTS Standard API.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.