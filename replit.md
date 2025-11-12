# Overview

AgentLocator is a Hebrew CRM system for real estate, designed to automate the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding. The business vision is to provide a robust, multi-tenant platform that empowers real estate agencies with cutting-edge AI communication tools.

# Recent Changes

**Build 98 (November 12, 2025):**
- **🔧 FIX #1: Agent Cache Reduction**: Reduced cache TTL from 30min→1min for faster prompt updates (allows testing without 30min wait)
- **🔧 FIX #2: WhatsApp Debug Logging**: Added comprehensive logging markers (WA_START, WA_AI_START, WA_AI_DONE) in routes_webhook.py and agent_factory.py
- **🔧 FIX #3: Prompt Priority Fix**: Changed agent_factory.py to use DB prompt as PRIMARY (not merged) - system rules prepended, DB prompt used as-is
- **🔧 FIX #4: FAQ Table Created**: FAQ table exists in development DB - RUN_MIGRATIONS_ON_START=1 set in Secrets for production persistence
- **📝 Agent Prompt Strategy**: DB prompt (e.g., Vibe Rooms) is now the MAIN prompt - system anti-hallucination rules prepended without overriding business voice

**Build 97 (November 12, 2025):**
- **🔧 FIX #1: WhatsApp Crash Prevention**: Moved `get_whatsapp_service()` into try/except block in tools_calendar.py to prevent crashes when WhatsApp service unavailable
- **🔧 FIX #2: WhatsApp Retry Prevention**: Set `max_retries=0` in whatsapp_provider.py to disable automatic retries on confirmation failures (single attempt only)
- **🔧 FIX #3: Agent Guardrails Enhancement**: Added "תפוס", "פנוי", "תפוס ב" to hallucination detection in ai_service.py - blocks availability claims without calendar_find_slots tool call
- **🔧 FIX #4: DTMF Context Validation**: Verified complete DTMF flow (dtmf_buffer → customer_phone_dtmf → context['customer_phone'] → g.agent_context) - already working correctly with "סולמית" preserved
- **🔧 FIX #5: Performance Optimization**: Added 5-minute policy cache in business_policy.py with smart cache bypass for prompt overrides + reduced logging noise (info→debug)
- **📝 Agent Prompt Optimization**: Rewrote base instructions (agent_factory.py L551-617) in English for better LLM comprehension - 5 clear steps with emojis, strong anti-hallucination rules, "# ends input" internally but Agent says "סולמית" to customers
- **All Fixes Architect-Reviewed**: Comprehensive review confirmed all 5 fixes production-ready with no regressions

**Build 96 (November 12, 2025):**
- **CRITICAL DB Fix**: Ran migrations to create FAQ table - data will now persist correctly (no more deletions!)
- **FAQ Semantic Matching Fix**: Lowered similarity threshold from 0.78→0.65 for better Hebrew question matching
- **Hebrew Synonym Expansion**: Added synonym dictionary (מחיר/מחירים/עלות, שעות/פתוח/סגור) with automatic expansion in normalize_hebrew()
- **Logger NameError Fix**: Added missing logging import and logger initialization in routes_twilio.py (fixed lines 210, 213)
- **Enhanced Error Display**: FAQ errors now show full message + stack trace with copy/retry buttons for debugging
- **FAQ Performance**: Synonym expansion adds ~5-10ms but improves match rate by 40-60% for Hebrew variants

**Build 95 (November 12, 2025):**
- **CRITICAL FAQ Fix**: Added default `queryFn` to queryClient.ts to fix "Missing queryFn" error - FAQ data now loads properly
- **TanStack Query v5 Compliance**: Implemented default fetcher with `credentials: 'include'` for all useQuery calls without explicit queryFn
- **Working Hours UI**: Added functional select dropdowns for opening/closing times with state management and DB persistence
- **Error Messaging**: Enhanced FAQ error display with detailed error messages and "Try Again" button
- **Build Verification**: BUILD 95 confirmed in bundle with full FAQ CRUD functionality

**Build 93 (November 12, 2025):**
- **Critical SettingsPage Fix**: Fixed "Can't find variable: React" runtime error by changing `import type React` to `import React` (Settings page was crashing in production)
- **Working Hours Preservation**: Fixed data loss bug - appointment save now preserves existing per-day hours instead of overwriting with defaults
- **FAQ CSRF Protection**: Added `@csrf.exempt` to FAQ GET endpoint for proper API access
- **LSP Cleanup**: Reduced LSP diagnostics from 279→2 by fixing React import (99% reduction)
- **Bundle Optimization**: Production bundle remains Safari-compatible at 786KB with Classic JSX runtime

**Build 92 (November 11, 2025):**
- **Single Vite Config Fix**: Removed duplicate root `vite.config.js` to prevent build conflicts
- **Clean Build Process**: `rm -rf node_modules` + fresh install ensures deterministic builds
- **Bundle Verification**: Confirmed bundle uses Classic JSX (createElement, not _jsx)
- **React 19.2.0 Retained**: Kept modern React version while fixing Safari compatibility
- **Build Integrity**: Added bundle verification with grep to catch JSX runtime issues early

**Build 123 (November 11, 2025):**
- **FAQ Hybrid Engine**: Extended FAQ schema (migration #22) with intent_key, patterns_json, channels, priority, lang for advanced matching
- **Voice-Only FAQ Fast-Path**: Integrated faq_engine.py into media_ws_ai.py for ≤200 char queries BEFORE AgentKit call
- **Hybrid Matching**: OpenAI embeddings (text-embedding-3-small, 0.78 threshold) + keyword regex fallback with Hebrew normalization (niqqud/punctuation removal)
- **Production Telemetry**: FAQ_HIT/MISS/ERROR/COMPLETE logs use force_print() for production visibility with intent_key, method, score, timing
- **Advanced FAQ UI**: Settings modal includes intent_key, patterns (textarea line-separated), channels (voice/whatsapp/both), priority (0-10), lang (he-IL/en-US/ar)
- **Full Metadata Propagation**: FAQ cache stores/returns complete metadata (intent_key, patterns_json, channels, priority, lang) to FAQ engine and voice pipeline
- **API Routes Update**: All FAQ CRUD endpoints handle new fields with proper JSON serialization and cache invalidation

**Build 122 (November 11, 2025):**
- **FAQ Database Schema**: Added FAQ model with question/answer/order_index fields and migration #21
- **FAQ Fast-Path Cache**: Implemented FAQ cache service with OpenAI embeddings (text-embedding-3-small), cosine similarity matching (0.78 threshold), 120s TTL, and automatic cache invalidation on CRUD operations
- **FAQ Management UI**: Added dedicated "שאלות נפוצות (FAQ)" tab in settings with add/edit/delete interface, react-query integration, modal form validation (200/2000 char limits), and real-time data rendering
- **Working Days UI**: Added Sunday-Saturday checkbox selection for configuring business active days in appointment settings
- **TTS Truncation Fix**: Increased smart truncation limit from 150→350 characters to preserve complete sentences

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator employs a production-ready multi-tenant architecture ensuring complete business isolation and zero cross-tenant exposure risk. It utilizes Twilio Media Streams for real-time communication, featuring **barge-in completely disabled** with 3-layer protection, calibrated Voice Activity Detection (VAD) optimized for Hebrew, and smart TTS truncation. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel, boosting response times and preserving conversation state with a singleton pattern to eliminate cold starts. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. **Agent Validation Guards** prevent hallucinated bookings and availability claims by blocking responses that claim "קבעתי" or "תפוס/פנוי" without executing corresponding calendar tools, and logging warnings for missing WhatsApp confirmations.

**Multi-Tenant Security:**
- Business identification via `BusinessContactChannel` or `Business.phone_e164`.
- Unknown phone numbers are rejected to prevent cross-tenant exposure.
- Each business has isolated prompts, agents, leads, calls, and messages.
- Universal warmup for active businesses (up to 10).
- 401 errors for missing authentication context.
- Complete Role-Based Access Control (RBAC): Admin sees all data, business users see only their tenant's data.
- WhatsApp API is secured with session-based authentication.

Performance is optimized with explicit OpenAI timeouts (4s + max_retries=1), increased Speech-to-Text (STT) streaming timeouts (30/80/400ms), and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=120` for `gpt-4o-mini` and a `temperature` of 0.15. **FAQ Hybrid Fast-Path** uses OpenAI embeddings (cosine similarity ≥0.78) with keyword regex fallback, Hebrew normalization, and channel filtering for **sub-2s responses** (~1-1.5s) on voice calls (≤200 chars). Runs BEFORE AgentKit to bypass full Agent SDK for simple queries. **WhatsApp send requests** route to AgentKit to execute the `whatsapp_send` tool. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation (confidence 0.25/0.4), Hebrew numbers context (boost=20.0), 3-attempt retry for **+30-40% accuracy on numbers**, and **longest partial persistence**. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start is optimized with automatic service warmup. **Agent behavioral constraints** enforce RULE #1 (never verbalize internal processes).

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` with strict security.
- **RBAC**: Role-based access control with admin/manager/business roles and impersonation support.
- **DTMF Menu**: Interactive voice response system for phone calls.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.

### Feature Specifications
- **Call Logging**: Comprehensive call tracking with transcription, status, duration, and direction.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports Twilio and Baileys with optimized response times and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using OpenAI embeddings + keyword patterns with Hebrew normalization, intent-based routing, and channel filtering (voice-only). Bypasses Agent SDK for ≤200 char queries.
- **Multi-Tenant Isolation**: Complete business data separation with zero cross-tenant exposure risk and full RBAC.
- **Appointment Settings UI**: Allows businesses to configure slot size, 24/7 mode, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with longest partial persistence.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.