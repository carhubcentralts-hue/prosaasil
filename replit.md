# Overview

ProSaaS is a multi-tenant Hebrew AI assistant SaaS platform designed for WhatsApp and phone calls, leveraging the OpenAI Realtime API. Its core purpose is to automate the sales pipeline by providing an AI-powered assistant for real-time call processing, lead information collection, and meeting scheduling. The platform ensures complete business isolation, robust user management with 4-tier role-based access control, and aims to significantly enhance sales conversion and operational efficiency through advanced audio processing and customizable AI functionalities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS implements a multi-tenant architecture with strict data isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant uses an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. Key features include dual input (verbal and DTMF) for name/phone confirmation, a DTMF Menu System, and channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security measures include business identification, rejection of unknown numbers, isolated data, universal warmup, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and SeaSurf CSRF protection. Features a comprehensive session authentication system, including impersonation for system administrators.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration.
- **Multi-Tenant Resolution**: Secure business identification via `resolve_business_with_fallback()`.
- **RBAC**: 4-tier hierarchy (system_admin → owner → admin → agent).
- **Security**: Critical tenant isolation, cross-tenant security enforcing `tenant_id` filtering, and restricted `business_id` override.
- **OpenAI Realtime API**: Integrates `gpt-4o-realtime-preview` for real-time voice calls.
- **AI Behavior Optimization**: Uses `gpt-4o-realtime-preview` with behavioral rules and server-side GPT-4o-mini NLP for appointment parsing and hallucination filtering. Includes mechanisms to prevent AI loops and manage concurrent NLP processing.
- **Hebrew-Optimized VAD**: Dynamic thresholding and simplified barge-in.
- **Cost Tracking**: Real-time chunk-based audio tracking.
- **Error Resilience**: DB query failures fall back to minimal prompts.
- **Greeting System**: AI includes business-specific greetings.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI Navigation**: Consolidated AI prompt editing into System Settings, restricted by role.
- **RBAC Sidebar**: Dynamic visibility for "Business Management" and "User Management".
- **Role-Based Routing**: Smart default redirects based on user roles.

## Feature Specifications
- **Call Logging**: Comprehensive tracking.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Customizable names, introductions, and greetings.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Automatic Recording Cleanup**: 7-day retention with scheduled cleanup.
- **WhatsApp AI Toggle**: Customer service can toggle AI on/off per conversation, allowing human agent intervention.
- **WhatsApp Disconnect Notifications**: Automatic system notifications for business owners/admins upon WhatsApp disconnection/reconnection.
- **Security Hardening**: Twilio signature validation, dynamic business identification, and robust RBAC for user/lead management.
- **Payments & Contracts Feature Flags**: Conditional enabling/disabling of billing features.
- **Enhanced Reminders System**.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice time.
- **CRM Tasks**: Redesigned task board with notifications.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview` (primary for voice calls), and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for custom automations triggered by events like WhatsApp messages and calls.

---

# BUILD 155 - FINAL PRODUCTION QA

**Date**: November 27, 2025  
**Target**: Deploy to prosaas.pro (Contabo VPS)

## QA Verification Summary

### 1. Twilio Security ✔
- `require_twilio_signature` decorator on all webhook POST endpoints
- Production mode (`FLASK_ENV != 'development'`) blocks signature bypass
- Missing `TWILIO_AUTH_TOKEN` in production returns 403

### 2. Multi-Tenant Business Resolution ✔
- **FIXED**: Removed all `Business.query.first()` fallbacks from:
  - `routes_twilio.py` (5 locations)
  - `auto_meeting.py` - now requires deterministic business_id from call_log
  - `tasks_recording.py` - returns None instead of random business
- No more hardcoded `business_id = 1` defaults
- System properly rejects operations without valid business_id

### 3. WhatsApp/Baileys/AgentKit ✔
- `Dockerfile.baileys` uses Node 20+ (required for Baileys 7.x)
- `whatsapp_appointment_handler.py` requires explicit business_id
- No phone number fallbacks - dynamic lookup via `Business.phone_e164`

### 4. CRM Multi-Tenant Security ✔
- `get_business_id()` enforces tenant isolation
- Only `system_admin` can override `business_id` via query param
- Lead deletion: uses `check_lead_access()` for tenant filtering
- User deletion RBAC: system_admin (any user), owner (own business only)

### 5. Payments/Contracts Feature Freeze ✔
- `ENABLE_PAYMENTS=false` and `ENABLE_CONTRACTS=false` in `.env.example`
- All billing endpoints return 410 Gone when disabled

### 6. Google TTS/STT Fallback ✔
- `TTS_DISABLED` auto-set when credentials missing
- `USE_REALTIME_API=true` default - OpenAI Realtime API, no GCP needed

### 7. Domain Configuration ✔
- `PUBLIC_BASE_URL=https://prosaas.pro` in `.env.example`
- No hardcoded `ai-crmd.replit.app` in production code

### 8. Docker/Deployment ✔
- `.dockerignore` comprehensive
- `DEPLOYMENT.md` updated for prosaas.pro
- All Docker files verified

## Status: READY FOR PRODUCTION

✅ All security checks passed  
✅ Multi-tenant isolation verified  
✅ Feature flags configured  
✅ Docker deployment files ready  
✅ Domain configuration set to prosaas.pro