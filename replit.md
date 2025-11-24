# Overview

ProSaaS is a multi-tenant Hebrew AI assistant SaaS platform for WhatsApp and phone calls, leveraging the OpenAI Realtime API. It provides complete business isolation, robust user management with 4-tier role-based access control, and automates the sales pipeline. The system uses an AI-powered assistant for real-time call processing, lead information collection, and meeting scheduling, aiming to enhance efficiency and sales conversion through advanced audio processing and customizable AI.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS employs a multi-tenant architecture with isolated business data. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant uses an Agent SDK for appointment scheduling and lead creation, maintaining conversation memory and utilizing an Agent Cache System. Name and phone number confirmation use dual input (verbal and DTMF), supported by a DTMF Menu System and channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security includes business identification, rejection of unknown numbers, isolated data, universal warmup, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. Audio streaming uses a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints preventing verbalization of internal processes. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection. **BUILD 142 FINAL**: Complete session authentication overhaul - `@require_api_auth()` checks both `session['al_user']` OR `session['user']` in priority order, never clears session automatically, and accepts `business_id=None` for system_admin. Session rotation preserves both keys. Impersonation uses only `session['impersonated_tenant_id']` for state management.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` for secure business identification.
- **RBAC**: 4-tier role hierarchy (system_admin → owner → admin → agent).
- **Multi-Tenant Business Creation**: Atomic transaction for business and owner user creation.
- **DTMF Menu**: Interactive voice response system.
- **Data Protection**: Strictly additive database migrations.
- **User Management API**: `/api/admin/users` endpoint with automatic RBAC filtering.
- **Cross-Tenant Security**: Enforced tenant_id filtering across all dashboard and lead endpoints; `get_business_id()` restricts query parameter override to system_admin only. Baileys Multi-Tenant QR Security uses dynamic tenant-specific paths.
- **Authentication Context**: Uses `@require_api_auth()` decorator for consistent Flask `g` context population. **BUILD 142**: Fixed decorator to check both session keys and properly populate `g.user`/`g.tenant` for all user roles.
- **Critical Tenant Isolation**: Restricted business_id override via query parameters to system_admin only.
- **Impersonation System**: **BUILD 142**: system_admin-only business impersonation with dual response format compatibility (`ok`/`success`, `impersonated_tenant_id`/`business_id`) for frontend/backend sync.
- **OpenAI Realtime API**: Integrates `gpt-4o-realtime-preview` for phone calls with asyncio threads.
- **AI Behavior Optimization**: Uses `gpt-4o-realtime-preview` with behavioral rules and server-side GPT-4o-mini NLP for appointment parsing.
- **Hebrew-Optimized VAD**: Dynamic thresholding.
- **Simplified Barge-In**: 350ms grace period and instant trigger.
- **Cost Tracking**: Real-time chunk-based audio tracking with cost summaries.
- **Error Resilience**: DB query failures fall back to minimal prompt.
- **Greeting System**: System prompt instructs AI to include a business-specific greeting.
- **Lead Name Display**: **BUILD 142**: All lead endpoints (`/api/leads`, `/api/leads/<id>`) return `full_name` computed property for consistent UI display.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI Navigation**: Consolidated AI prompt editing into System Settings → AI Settings tab; access restricted by role.
- **RBAC Sidebar**: "Business Management" restricted to system_admin; "User Management" filtered by business.
- **Role-Based Routing**: Smart default redirect for different roles (system_admin to global, others to business-scoped dashboards).

## Feature Specifications
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
- **CRM Tasks**: Redesigned task board with notifications.
- **Consolidated AI Settings**: All AI prompt editing is now in the System Settings → AI Settings tab.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, Hebrew-Optimized VAD, and Whisper transcription.
- **Google Cloud Platform**: STT Streaming API v1 for Hebrew, TTS Standard API (legacy/fallback).
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.