# Overview

ProSaaS is a multi-tenant SaaS platform providing an AI assistant for WhatsApp and phone calls, primarily in Hebrew. It leverages the OpenAI Realtime API to automate the sales pipeline by offering real-time call processing, lead information collection, and meeting scheduling. The platform emphasizes complete business isolation, robust user management with 4-tier role-based access control, and aims to boost sales conversion and operational efficiency through advanced audio processing and customizable AI functionalities. The project's ambition is to empower businesses with intelligent, automated sales support.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS employs a multi-tenant architecture with strict data isolation, integrating Twilio Media Streams for real-time communication. It features Hebrew-optimized Voice Activity Detection (VAD), smart Text-to-Speech (TTS) truncation, and an AI assistant utilizing an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. The system supports dual input (verbal and DTMF), includes a DTMF Menu System, and provides channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security is ensured through business identification, rejection of unknown numbers, isolated data, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized via explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication. Call control is managed by a state machine that dictates the call lifecycle and settings.

## Technical Implementations

### Backend
- **Frameworks**: Flask (SQLAlchemy ORM) and Starlette (native WebSocket handling) with Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and CSRF protection.
- **AI Prompt System**: Real-time management, versioning, and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton with auto-expiration for Agent SDK instances.
- **Multi-Tenancy**: Secure business identification and strict `tenant_id` filtering for data isolation.
- **AI Integration**: Uses `gpt-4o-realtime-preview` for voice calls and `gpt-4o-mini` for server-side NLP, with behavioral rules and hallucination filtering.
- **Hebrew Optimization**: Optimized VAD with dynamic thresholding, AI greeting system, Hebrew normalization dictionary, and grammar improvements.
- **Hebrew City Normalization (BUILD 184)**: RapidFuzz-powered fuzzy matching for 120+ Israeli cities. Confidence thresholds: ≥92% auto-accept, 85-92% requires confirmation, <85% retry. Stores both raw input and canonical city name for webhook/CRM tracking.
- **3-Layer STT Accuracy System (BUILD 186)**: Prevents STT hallucinations ("בית שמש" → "מצפה רמון"). Layer 1: Hebrew Soundex + DoubleMetaphone phonetic encoding. Layer 2: RapidFuzz with 450+ cities/places and 5000+ Hebrew names. Layer 3: Consistency filter with majority voting (2/3 match → lock value). Thresholds: ≥90% auto-accept, 82-90% confirm, <82% retry. Big-jump guard blocks >15pt phonetic distance corrections. Webhook includes city_raw_attempts, city_autocorrected for debugging.
- **Hebrew STT Fix (BUILD 186)**: Explicit Hebrew language config (`language: "he"`) in session.update preserves Whisper Hebrew transcription. Expanded English hallucination filter catches 50+ patterns (e.g., "Thank you", "Good luck", "Blah") that occur when Hebrew audio is mistranscribed as English.
- **Extended Hebrew Data Files (BUILD 186)**: israeli_places.json (450+ cities/neighborhoods with aliases), hebrew_first_names.json (5000+ names with variants), hebrew_surnames.json (3000+ surnames), hebrew_phonetic_rules.json (confusion patterns, endings, prefixes). All load with deduplication and legacy fallback.
- **Call Quality**: Includes barge-in protection, STT segment merging, noise filtering, gibberish/semantic loop detection, mishearing protection, and silence hallucination prevention.
- **Verification Gates**: AI confirms collected field values and information immediately after hearing it.
- **Language Support**: Default Hebrew, switches to caller's language on request.
- **Outbound Calls**: AI-initiated calls with concurrency limits, template-based prompts, and separate business-level outbound AI prompts.
- **Webhook (BUILD 183)**: Separate inbound/outbound webhook URLs for direction-based routing. Inbound calls use `inbound_webhook_url` with `generic_webhook_url` fallback; outbound calls use `outbound_webhook_url` ONLY (no webhook sent if not configured). HMAC signature verification and retry logic for all webhooks.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography.
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI/UX**: Consolidated AI prompt editing, dynamic sidebar visibility based on RBAC, optimized lead search, fast status updates, and a notes tab for leads.
- **WhatsApp UI**: Proper styling, AI toggle, message alignment, and prompt fallback.

## Feature Specifications
- **Call Logging & Conversation Memory**: Comprehensive tracking and full history.
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
- **Appointment Validation (BUILD 184)**: Server-side validation enforces booking_window_days (max days ahead), min_notice_min (minimum notice time), and business hours. All checks use business timezone for accuracy.
- **CRM Tasks**: Redesigned task board with notifications.
- **Bulk Lead Deletion**: Cascade delete with transaction rollback.
- **Auto Hang-up Settings**: Options to end calls after lead capture or on goodbye.
- **Bot Speaks First**: Option for bot to greet before listening.
- **Admin Business Minutes**: System-admin-only page showing phone call minutes per business, with date filtering, CSV export, and inbound/outbound breakdown. Data sourced from Twilio callbacks via CallLog.duration.
- **Bulk Import for Outbound Calls (BUILD 182)**: Import leads from Excel/Google Sheets CSV for outbound call campaigns. Features: 5000 leads per business limit, Hebrew/English column support (שם/name, טלפון/phone, הערות/notes), phone normalization to E.164, tenant-isolated storage with source="imported_outbound", deletable only from import list (not regular CRM leads), paginated table with bulk delete, integrates with existing outbound call flow.
- **Calendar Scheduling Toggle (BUILD 186)**: `enable_calendar_scheduling` setting in BusinessSettings controls whether AI attempts to schedule appointments during inbound calls. When disabled, AI collects lead info only and promises callback. Migration 31 adds the column. UI toggle in AI Settings page under call control.
- **Cancelled Response Recovery (BUILD 187)**: When OpenAI cancels a response due to turn_detected BEFORE any audio is sent (output_count=0), the AI would go silent. BUILD 187 adds automatic recovery: after speech_stopped, wait 800ms and if no new response was created, manually trigger response.create. Fixes the "AI suddenly goes silent" bug.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for external integrations (e.g., Monday.com, Google Sheets, Slack) via webhooks.