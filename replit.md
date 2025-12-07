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
- **AI Integration**: Uses `gpt-4o-mini-realtime-preview` for voice calls (75% cheaper than full model) and `gpt-4o-mini` for server-side NLP, with behavioral rules and hallucination filtering.
- **Hebrew Optimization**: Optimized VAD, AI greeting system, Hebrew normalization dictionary, grammar improvements, and a 3-Layer STT Accuracy System with phonetic encoding and fuzzy matching for Hebrew names/cities.
- **Call Quality**: Barge-in protection, STT segment merging, noise filtering, gibberish/semantic loop detection, mishearing protection, and silence hallucination prevention.
- **Dynamic STT Vocabulary**: Business-specific vocabulary system for transcription quality, including context-based prompts and fuzzy corrections.
- **Telephony Optimization**: Specifically tuned for 8kHz G.711 μ-law, with optimized STT prompts, silence detection, and VAD thresholds.
- **Semantic Repair**: GPT-4o-mini post-processing for short/garbled Hebrew transcriptions using business vocabulary.
- **HARD Barge-In**: Immediate AI interruption and flushing of audio queue upon user speech detection.
- **Greeting Flow & Patience**: Manages greeting state, allows barge-in on greeting, and uses gibberish bypass for early user utterances.
- **ECHO GATE (BUILD 304)**: Blocks audio input to OpenAI while AI is speaking and 800ms after, preventing self-transcription hallucinations. Uses 5+ consecutive frames (100ms) to detect real barge-in vs echo spikes. Voice changed to 'ash' (conversational male, lower pitch).
- **CHOPPY AUDIO FIX (BUILD 305)**: Fixed mid-sentence audio cuts caused by LOOP GUARD clearing TX queue prematurely. Now lets existing audio play while blocking new audio. Also resets gap detector per response to prevent misleading warnings.
- **CITY DETECTION FIX (BUILD 306)**: Relaxed thresholds (90/82 from 93/85), skip common non-city words (שלום, צריך, מנעולן, etc.), lock city immediately on high-confidence match to prevent subsequent overrides.
- **SMART EXTRACTION (BUILD 307)**: City extraction now gated to user speech only - AI questions like "באיזו עיר אתה?" no longer trigger extraction. User confirmation words ("נכון") now lock city from AI's previous statement. Fixed vocabulary duplication bug where multi-word terms like "פורץ דלתות" were doubled. Silence prompts like "אתה עדיין שם?" no longer extract "עדי" as city.
- **LOOP PREVENTION (BUILD 308)**: Critical fix for AI looping on wrong city after rejection. When user says "לא", city is now fully cleared from lead_capture_state (not just unlocked). AI responds naturally and asks dynamically for missing fields based on business settings. STT segment dedupe removes duplicate phrases like "פורץ דלתות פורץ דלתות". 100% dynamic - no hardcoded questions, AI uses business configuration.
- **POST-GREETING PATIENCE (BUILD 311)**: Fixed AI skipping first question after greeting. Added 10-second grace period after greeting finishes before silence warnings can trigger. SILENCE_HANDLER responses no longer count towards consecutive response limit (LOOP GUARD). This ensures customer has time to respond after greeting without being rushed or having questions skipped.
- **EXTRACTION & SILENCE FIX (BUILD 312)**: Critical fix for lead field extraction - now ONLY extracts from user speech, never from AI messages. Added expanded non-city words list (עדיין, עדי, לדעת, etc.) to prevent false positives. Silence monitor now waits until user has spoken at least once before counting silence - prevents AI from asking "are you there?" before user says anything. Added 60-second safety timeout for calls with no user speech. OpenAI connection now has 3s timeout with slow connection warnings (>1.5s).
- **SIMPLE LEAD CAPTURE (BUILD 313)**: MAJOR SIMPLIFICATION - Removed all complex word lists, fuzzy matching, and city normalizer. Now uses OpenAI Realtime Tool Calling: defined `save_lead_info` tool that AI calls naturally when user provides info (city, name, service_type). 100% AI-driven extraction - no hardcoded dictionaries. Kept only minimal fallback for email/budget patterns. True "OpenAI + Twilio only" architecture.
- **CONTEXT-AWARE GREETING (BUILD 315)**: AI now receives FULL business prompt from the first moment (not just minimal greeting). Greeting instruction prepended to full prompt: `{greeting_instruction}\n\n---\n\n{full_business_prompt}`. This gives AI complete context (required fields, business rules, services) from the very first utterance, preventing misunderstandings when user responds to greeting. Phase 2 simplified to only add lead capture tool (prompt already sent in Phase 1).
- **FAST GREETING + NO STT VOCAB (BUILD 316)**: Two critical fixes: (1) Removed dynamic STT vocabulary prompts that were causing hallucinations like "קליבר" - now uses pure `language=he` with no prompt hints. (2) Split greeting into Phase 1 (compact ~800 char prompt for fast 2-second greeting) and Phase 2 (full prompt loaded after greeting). Compact prompt includes business name, type, required fields - enough context to understand responses without slowing down greeting.
- **DYNAMIC GREETING FROM PROMPT (BUILD 317)**: Major improvement - compact prompt now DERIVED from business's actual ai_prompt (first 600 chars), NOT hardcoded. AI generates greeting dynamically based on prompt context. Removed static greeting_message usage. This ensures AI understands business context (locksmith, salon, etc.) and can interpret user responses correctly (e.g., "קריית גת" recognized as city because prompt mentions service areas).
- **COST OPTIMIZATION (BUILD 318)**: CRITICAL cost reduction - previous $15 for 10 minutes now reduced by ~80%. Changes: (1) Switched to `gpt-4o-mini-realtime-preview` model (75% cheaper than gpt-4o-realtime), (2) Added instruction caching to prevent redundant session.update calls, (3) Added RMS-based silence filter (COST_MIN_RMS_THRESHOLD=100) to block pure silence, (4) Added FPS limiter (COST_MAX_FPS=40) to prevent excessive frame sending. Config in `server/config/calls.py`.
- **STABILITY FIX (BUILD 319)**: Critical fixes for call stability: (1) Disabled RMS filter (set to 0) - Twilio audio comes with RMS ~12, threshold 100 was blocking ALL user speech, (2) Changed greeting to use EXACT text from DB (`greeting_message`) instead of AI-generated, (3) AI still receives full business context via compact_prompt (Phase 1) and full_prompt (Phase 2), ensuring it understands responses. No more duplicate greetings, no more AI ignoring user.
- **AUDIO GUARD (BUILD 320)**: Lightweight PSTN noise filtering for improved call quality and reduced OpenAI API costs. Features: (1) Dynamic noise floor tracking with 100-frame EMA calibration, (2) ZCR-based speech detection distinguishing speech from flat noise, (3) Music detection state machine (normal→suspected→confirmed) to filter hold music (~300ms to enter, 2.5s cooldown), (4) Guard applied before OpenAI enqueue - drops silence/noise/music while bypassing during barge-in or active speech, (5) GAP_RECOVERY disabled when guard is ON to prevent conflicts. Config in `server/config/calls.py`.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography.
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI/UX**: Consolidated AI prompt editing, dynamic sidebar, optimized lead search, fast status updates, and user-editable vocabulary settings.

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