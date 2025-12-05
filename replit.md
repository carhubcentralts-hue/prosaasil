# Overview

ProSaaS is a multi-tenant SaaS platform that provides an AI assistant for WhatsApp and phone calls, primarily in Hebrew. Its core purpose is to automate sales pipelines by leveraging OpenAI's Realtime API for real-time call processing, lead generation, and meeting scheduling. The platform ensures complete business isolation, offers robust 4-tier role-based access control, and aims to significantly boost sales conversion and operational efficiency through advanced audio processing and customizable AI functionalities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS utilizes a multi-tenant architecture with strict data isolation. Key features include Hebrew-optimized Voice Activity Detection (VAD), smart Text-to-Speech (TTS) truncation, and an AI assistant built with an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. The system supports dual input (verbal and DTMF), features a DTMF Menu System, and provides channel-aware responses. Agent Validation Guards are implemented to prevent AI hallucinations. Security is maintained through business identification, rejection of unknown numbers, isolated data, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized via explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency uses a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and database-based deduplication. Call control is managed by a state machine that dictates the call lifecycle and settings. The system is designed for 100% dynamic content, ensuring zero hardcoded business-specific values, allowing it to adapt to any business type through database configuration.

## Technical Implementations

### Backend
- **Frameworks**: Flask (SQLAlchemy ORM) and Starlette (WebSocket handling) with Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and CSRF protection.
- **AI Prompt System**: Real-time management, versioning, and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton with auto-expiration for Agent SDK instances.
- **Multi-Tenancy**: Secure business identification and strict `tenant_id` filtering.
- **AI Integration**: Uses `gpt-4o-realtime-preview` for voice calls and `gpt-4o-mini` for server-side NLP, with behavioral rules and hallucination filtering.
- **Hebrew Optimization**: Optimized VAD, AI greeting system, Hebrew normalization dictionary, grammar improvements, and a 3-Layer STT Accuracy System with phonetic encoding, RapidFuzz matching for cities/names, and a consistency filter. Includes extensive Hebrew data files (places, names).
- **Call Quality**: Barge-in protection, STT segment merging, noise filtering, gibberish/semantic loop detection, mishearing protection, and silence hallucination prevention.
- **Verification Gates**: AI confirmation of collected field values.
- **Language Support**: Default Hebrew, with on-request switching to caller's language.
- **Outbound Calls**: AI-initiated calls with concurrency limits and template-based prompts.
- **Webhook**: Separate inbound/outbound URLs with HMAC signature verification and retry logic.
- **Single Pipeline Lockdown**: Centralized `trigger_response()` function for all response creation, unified OpenAI Realtime STT, and robust response lifecycle tracking.
- **Major Hebrew STT Upgrade (BUILD 202)**: Switched to `gpt-4o-transcribe` with minimal, focused transcription prompts. Prompt includes business name + required field types (שמות, שעות, ערים) as short rules, NOT long vocabulary lists. Under 100 chars for optimal performance.
- **Trusted OpenAI STT (BUILD 202)**: Fixed SILENCE_GATE blocking valid transcriptions. The local RMS gate was rejecting valid OpenAI transcriptions due to race conditions. Now trusts OpenAI's VAD when it successfully transcribes speech, only rejects true silence (RMS<10 + text<3 chars). Fixes "AI ignores what user said" bug.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography.
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI/UX**: Consolidated AI prompt editing, dynamic sidebar visibility, optimized lead search, fast status updates, notes tab for leads, and proper WhatsApp UI styling.

## Feature Specifications
- **Call Logging & Conversation Memory**: Comprehensive tracking and history.
- **WhatsApp Integration**: Baileys and Meta Cloud API support with per-business provider selection.
- **Lead Management**: Automated capture, creation, deduplication, and customizable statuses.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Configurable names, introductions, and greetings.
- **Automatic Recording Cleanup**: 7-day retention.
- **WhatsApp AI Toggle**: Customer service control per conversation.
- **Security Hardening**: Twilio signature validation, dynamic business identification.
- **Payments & Contracts**: Feature flags for billing.
- **Enhanced Reminders System**.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice.
- **CRM Tasks**: Redesigned task board with notifications.
- **Bulk Lead Deletion**: Cascade delete with transaction rollback.
- **Auto Hang-up Settings**: Options to end calls after lead capture or on goodbye.
- **Bot Speaks First**: Option for bot to greet before listening.
- **Admin Business Minutes**: System-admin-only page for phone call minutes tracking.
- **Bulk Import for Outbound Calls**: Import leads from CSV for campaigns, with phone normalization and tenant-isolated storage.
- **Calendar Scheduling Toggle**: Setting to enable/disable AI appointment scheduling during inbound calls.
- **Cancelled Response Recovery**: Automatic recovery mechanism for OpenAI responses cancelled before audio is sent.
- **Noise Filtering Overhaul**: Significantly increased voice detection thresholds to filter background noise and prevent false interruptions.
- **OpenAI VAD Tuning**: Increased OpenAI Realtime API turn detection thresholds for stricter speech detection.
- **Response Grace Period**: Ignores speech_started events shortly after response creation to prevent AI cutoff.
- **City Correction Detection**: AI can unlock and accept explicit city corrections from users, even if previously locked.
- **Trusted OpenAI STT (BUILD 202)**: Fixed SILENCE_GATE blocking valid transcriptions. The local RMS gate was rejecting valid OpenAI transcriptions due to race conditions. Now trusts OpenAI's VAD when it successfully transcribes speech, only rejects true silence (RMS<10 + text<3 chars). Fixes "AI ignores what user said" bug.
- **Major Hebrew STT Upgrade (BUILD 202)**: Switched to `gpt-4o-transcribe` with minimal, focused transcription prompts. Prompt includes business name + required field types (שמות, שעות, ערים) as short rules, NOT long vocabulary lists. Under 100 chars for optimal performance.
- **Dynamic STT Vocabulary (BUILD 204)**: Business-specific vocabulary system for better transcription quality:
  - Per-business vocabulary stored in DB (services, staff, products, locations)
  - Dynamic STT prompts generated from business context
  - Vocabulary-based fuzzy corrections (78% threshold with WRatio scorer)
  - Conservative approach: never modifies numbers, phone numbers, times, or short tokens
  - Uses gpt-4o-transcribe model (upgraded from whisper-1) for better Hebrew
  - Consolidated [STT_FINAL] logging for easy debugging
  - 100% dynamic - no hardcoded values, works for ANY business type
  - **Example vocabulary for hair salon:**
    ```json
    {
      "services": ["תספורת", "החלקה", "פן", "גוונים", "צביעה"],
      "products": ["שמפו", "מסכה", "קרם לחות"],
      "staff": ["דנה", "יוסי", "שי", "רוני"],
      "locations": ["תל אביב", "רמת גן", "גבעתיים"]
    }
    ```
  - **Example business_context:** "מספרה יוקרתית בתל אביב, מתמחה בהחלקות ותספורות גברים."
- **Voice Upgrade (BUILD 205)**: Switched from "shimmer" to "coral" voice for OpenAI Realtime API. Coral is one of OpenAI's expressive voices (Oct 2024) with better Hebrew intonation and multilingual support.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for external integrations.