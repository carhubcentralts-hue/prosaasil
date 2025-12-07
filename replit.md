# Overview

ProSaaS is a multi-tenant SaaS platform designed to automate sales pipelines using AI for WhatsApp and phone calls, primarily in Hebrew. It leverages OpenAI's Realtime API for call processing, lead generation, and meeting scheduling, aiming to boost sales conversion and operational efficiency. The platform offers complete business isolation, robust 4-tier role-based access control, and advanced audio processing with customizable AI functionalities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS employs a multi-tenant architecture with strict data isolation. Key features include Hebrew-optimized Voice Activity Detection (VAD), smart Text-to-Speech (TTS) truncation, and an AI assistant built with an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. The system supports dual input (verbal and DTMF), includes a DTMF Menu System, and provides channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security features include business identification, rejection of unknown numbers, isolated data, and 4-tier Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency uses a male Hebrew voice with masculine phrasing, and agent behavioral constraints are enforced. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and database-based deduplication. Call control is managed by a state machine, ensuring 100% dynamic content adaptable to any business via database configuration.

## Technical Implementations

### Backend
- **Frameworks**: Flask (SQLAlchemy ORM) and Starlette (WebSocket handling) with Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and CSRF protection.
- **AI Integration**: Uses `gpt-4o-mini-realtime-preview` for voice calls and `gpt-4o-mini` for server-side NLP, with behavioral rules and hallucination filtering. English prompts are used for OpenAI comprehension while AI speaks Hebrew to customers.
- **Hebrew Optimization**: Optimized VAD, AI greeting system, Hebrew normalization dictionary, grammar improvements, and a 3-Layer STT Accuracy System with phonetic encoding and fuzzy matching for Hebrew names/cities.
- **Call Quality**: Barge-in protection, STT segment merging, noise filtering, gibberish/semantic loop detection, mishearing protection, silence hallucination prevention, and PSTN noise filtering (Audio Guard). BUILD 325 CRITICAL: AUDIO_GUARD disabled to trust OpenAI VAD - was blocking quiet speech. VAD thresholds lowered (baseline 80, cap 120). Echo gate kept at 300 to prevent AI self-echo. BUILD 326: City Lock Mechanism - locks city from user's STT utterance as single source of truth, blocks AI from changing locked values, only user rejection can unlock. BUILD 327: STT AS SOURCE OF TRUTH - AI must respond ONLY to what customer actually said, never invent or guess values. Strong prompt rules added to prevent hallucination. BUILD 329: FIXED TOKEN LEAK - Phase 2 loop was resending full prompt with datetime.now() (1.7M tokens/day!). Now: Phase 1 sends FULL database prompt ONCE, Phase 2 only adds tool without resending prompt. max_tokens restored to 4096. BUILD 330: FIXED TRANSCRIPTION QUALITY - FPS throttler (COST_MAX_FPS=40) was dropping 20% of audio frames! Phone calls require 50fps (8kHz @ 20ms). DISABLED FPS limiting - all audio now passes through to OpenAI for accurate transcription. BUILD 331: COST SAFETY LIMITS - Added hard per-call limits (MAX_REALTIME_SECONDS=90, MAX_AUDIO_FRAMES=4500) to prevent runaway token consumption. Clear OPENAI_USAGE_GUARD logging at call end. REALTIME_WS_OPEN/CLOSED logging added for session tracking. BUILD 332: BALANCED COST FIX - Re-enabled FPS limiter at 48 FPS (96% audio vs 80% at 40 FPS). Fixed hard limit guard to actually terminate calls via Twilio API (ws.close() wasn't breaking Eventlet's wait() loop). Multiple checkpoint checks for _limit_exceeded flag in main loop. BUILD 333: PHASE-BASED FLOW - Fixed AI confirming after every question instead of only at end. Implemented 4-phase conversation flow: Greeting → Discovery → Single Confirmation → Closing. AI now confirms ONCE at end with full summary, not mid-conversation.
- **Dynamic STT Vocabulary**: Business-specific vocabulary system for transcription quality, including context-based prompts and fuzzy corrections.
- **Telephony Optimization**: Specifically tuned for 8kHz G.711 μ-law, with optimized STT prompts, silence detection, and VAD thresholds.
- **Semantic Repair**: GPT-4o-mini post-processing for short/garbled Hebrew transcriptions using business vocabulary.
- **Call Flow Management**: Implements hard barge-in, greeting flow and patience mechanisms, echo gate to prevent self-transcription, and loop prevention for AI conversations. Lead capture is simplified using OpenAI Realtime Tool Calling. Context-aware greetings are used with dynamic generation from business prompts.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography.
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI/UX**: Consolidated AI prompt editing, dynamic sidebar, optimized lead search, fast status updates, and user-editable vocabulary settings. BUILD 327: Simplified call control settings - removed `required_lead_fields` (duplicates prompt instructions) and `auto_end_after_lead_capture` (duplicates call_goal). Bot_speaks_first now only appears in call control settings, not business settings.

## Feature Specifications
- **Call Logging & Conversation Memory**: Comprehensive tracking and history.
- **WhatsApp Integration**: Baileys and Meta Cloud API support with per-business provider selection.
- **Lead Management**: Automated capture, creation, deduplication, and customizable statuses.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Configurable names, introductions, and greetings.
- **Automatic Recording Cleanup**: 7-day retention.
- **Payments & Contracts**: Feature flags for billing.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice.
- **Bulk Import/Export**: CSV import for outbound call campaigns and bulk lead deletion.
- **Auto Hang-up Settings**: Options to end calls after lead capture or on goodbye.
- **Bot Speaks First**: Option for bot to greet before listening.
- **Admin Business Minutes**: System-admin-only page for phone call minutes tracking.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-mini-realtime-preview` (voice calls), and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for external integrations.