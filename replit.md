# Overview

ProSaaS is a multi-tenant Hebrew AI assistant SaaS platform designed for WhatsApp and phone calls, leveraging the OpenAI Realtime API. Its core purpose is to automate the sales pipeline by providing an AI-powered assistant for real-time call processing, lead information collection, and meeting scheduling. The platform ensures complete business isolation, robust user management with 4-tier role-based access control, and aims to significantly enhance sales conversion and operational efficiency through advanced audio processing and customizable AI functionalities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS implements a multi-tenant architecture with strict data isolation, integrating Twilio Media Streams for real-time communication. It features Hebrew-optimized Voice Activity Detection (VAD) and smart Text-to-Speech (TTS) truncation. The AI assistant utilizes an Agent SDK for appointment scheduling and lead creation, incorporating conversation memory and an Agent Cache System. Key features include dual input (verbal and DTMF), a DTMF Menu System, and channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security measures include business identification, rejection of unknown numbers, isolated data, universal warmup, and a 4-tier Role-Based Access Control (RBAC). Performance is optimized through explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration.
- **Multi-Tenant Resolution**: Secure business identification via `resolve_business_with_fallback()`.
- **RBAC**: 4-tier hierarchy (system_admin → owner → admin → agent).
- **Security**: Critical tenant isolation, cross-tenant security enforcing `tenant_id` filtering.
- **OpenAI Realtime API**: Integrates `gpt-4o-realtime-preview` for real-time voice calls.
- **AI Behavior Optimization**: Uses `gpt-4o-realtime-preview` with behavioral rules and server-side GPT-4o-mini NLP for appointment parsing and hallucination filtering.
- **Hebrew-Optimized VAD**: Dynamic thresholding and simplified barge-in.
- **Greeting System**: AI includes business-specific greetings.
- **Verification Gates**: AI must confirm collected field values before hangup and confirm each piece of information immediately after hearing it.
- **Whisper Hallucination Filter**: Blocks pure English words fabricated from Hebrew audio.
- **Multi-Language Support**: AI responds in Hebrew by default but switches to caller's language when requested.
- **Voice Call Quality Improvements**: Includes barge-in protection, STT segment merging, enhanced noise filtering, gibberish detection, semantic loop detection, and mishearing protection.
- **Silence Hallucination Prevention**: Stricter VAD thresholds, low-RMS gate, and a three-layer defense combining RMS gating, consecutive frames, and a post-AI cooldown.
- **Hebrew Grammar & Natural Speech**: Improved system prompt, Hebrew normalization dictionary, expanded whitelist for valid speech, smarter filter logic, phrase detection, and language switch rules.
- **Call Control State Machine (BUILD 172)**: Single source of truth for all call settings. CallState enum (WARMUP/ACTIVE/CLOSING/ENDED) manages lifecycle. load_call_config() loads BusinessSettings once per call. All settings (bot_speaks_first, auto_end_*, silence_timeout, etc.) read from CallConfig only. Legacy `_load_call_behavior_settings()` removed. Safety guards ensure ACTIVE state on first speech. Silence monitoring with configurable warnings and polite hangup.
- **BUILD 176 Hangup Improvements**: Enhanced call hangup logic with 4 cases: (1) user_goodbye - user said bye + AI responds, (2) lead_captured_confirmed - lead captured + confirmed + auto_end=True, (3) user_verified - user confirmed details, (4) ai_goodbye_auto_end - AI goodbye with auto_end_on_goodbye=True + meaningful user interaction (safety guards: user_has_spoken + verification OR lead captured OR 4+ conversation turns). Expanded Hebrew confirmation detection with 25+ words (כן, נכון, בדיוק, יופי, מסכים, בסדר, אוקי, תודה, מאשר, סגור, זהו, etc.).
- **BUILD 176 Monday.com Webhook Debugging**: Comprehensive logging throughout webhook flow: settings lookup, URL/enabled flags, payload preview, HTTP response/status. Helps diagnose why transcripts may not be sent.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI Navigation**: Consolidated AI prompt editing into System Settings, restricted by role.
- **RBAC Sidebar**: Dynamic visibility for "Business Management" and "User Management".
- **Role-Based Routing**: Smart default redirects based on user roles.
- **Leads UX Improvements**: Optimized lead search, fast status updates, and a notes tab for free-text notes, images, and file attachments.
- **Lead Notes System (BUILD 172)**: Permanent LeadNote model separate from WhatsApp/call logs. CRUD API endpoints with tenant isolation. File uploads with 10MB limit and session-authenticated serving. Edit/delete functionality with chronological display.
- **WhatsApp Chat UI Fixes**: Proper WhatsApp-like styling for messages, toggle AI endpoint, correct message alignment, AI prompt fallback, and database session fixes.

## Feature Specifications
- **Call Logging**: Comprehensive tracking.
- **Conversation Memory**: Full history for contextual AI responses.
- **WhatsApp Integration**: Supports Baileys (WhatsApp Web) and Meta Cloud API, with per-business provider selection.
- **Intelligent Lead Collection**: Automated capture, creation, and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability.
- **Customizable AI Assistant**: Customizable names, introductions, and greetings.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Automatic Recording Cleanup**: 7-day retention with scheduled cleanup.
- **WhatsApp AI Toggle**: Customer service can toggle AI on/off per conversation.
- **WhatsApp Disconnect Notifications**: Automatic system notifications for business owners/admins.
- **Security Hardening**: Twilio signature validation, dynamic business identification, and robust RBAC.
- **Payments & Contracts Feature Flags**: Conditional enabling/disabling of billing features.
- **Enhanced Reminders System**.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Appointment Settings UI**: Configurable slot size, availability, booking window, and minimum notice time.
- **CRM Tasks**: Redesigned task board with notifications. N+1 query optimized with batch prefetch (BUILD 172).
- **Bulk Lead Deletion**: Cascade delete for all related FK tables (LeadActivity, LeadReminder, LeadNote, LeadMergeCandidate) with proper transaction rollback.
- **Monday.com Webhook Integration**: Per-business configurable webhook for call transcript sending.
- **Auto Hang-up Settings**: Options to automatically end calls after lead capture or on goodbye phrases.
- **Bot Speaks First**: Option for the bot to play greeting before listening to the customer.
- **Outbound AI Calls (BUILD 174)**: AI-initiated calls to leads with concurrency limits (max 3 outbound, 5 total per business). Template-based prompts with custom greeting injection. Frontend page at `/app/outbound-calls` with lead selection, template picker, and real-time call status. Call limiter service enforces limits for both inbound and outbound calls. Separate outbound AI prompt (`outbound_ai_prompt`) for business-level outbound call instructions distinct from inbound calls.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for custom automations.

# Outbound Calls – Validation Checklist (BUILD 174)

## Models Used
- `CallLog` - Extended with `lead_id`, `outbound_template_id`, `direction` fields (all nullable for backward compatibility)
- `OutboundCallTemplate` - New model: `id`, `business_id`, `name`, `description`, `prompt_text`, `greeting_template`, `is_active`

## Routes Added
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/outbound_calls/templates` | GET | List active templates for business |
| `/api/outbound_calls/templates` | POST | Create new template (owner/admin) |
| `/api/outbound_calls/templates/<id>` | DELETE | Soft-delete template |
| `/api/outbound_calls/counts` | GET | Get active call counts |
| `/api/outbound_calls/start` | POST | Start outbound calls to leads |
| `/webhook/outbound_call` | POST/GET | Twilio webhook for outbound calls |

## Concurrency Limits
- **Max 3 outbound calls** per business (simultaneous)
- **Max 5 total calls** (inbound + outbound combined) per business
- Enforced via `server/services/call_limiter.py`
- Inbound calls return polite TwiML rejection when at limit
- Outbound API returns 429 with Hebrew error message when at limit

## Files Modified for BUILD 174
### Backend
- `server/models_sql.py` - Added `OutboundCallTemplate` model, extended `CallLog`, added `outbound_ai_prompt` to `BusinessSettings`
- `server/routes_outbound.py` - New file: outbound call API endpoints
- `server/services/call_limiter.py` - New file: call concurrency limiting
- `server/routes_twilio.py` - Added `/webhook/outbound_call` and `check_inbound_call_limit()`
- `server/app_factory.py` - Registered `outbound_bp` blueprint
- `server/services/realtime_prompt_builder.py` - Updated `build_realtime_system_prompt()` to accept `call_direction` parameter, uses `outbound_ai_prompt` for outbound calls
- `server/routes_ai_prompt.py` - Updated GET/PUT `/api/business/current/prompt` to handle `outbound_calls_prompt` field

### Frontend
- `client/src/pages/calls/OutboundCallsPage.tsx` - New page: lead selection, template picker, call status
- `client/src/app/layout/MainLayout.tsx` - Added sidebar item "שיחות יוצאות"
- `client/src/app/routes.tsx` - Added `/app/outbound-calls` route
- `client/src/components/settings/BusinessAISettings.tsx` - Added dedicated "Outbound Calls Prompt" section with separate save functionality

## WebSocket Integration (media_ws_ai.py)
- Extracts outbound parameters (`direction`, `lead_id`, `lead_name`, `template_id`, `business_id`, `business_name`) from Twilio customParameters
- **🔒 SECURITY**: Uses explicit `business_id` for outbound calls (NOT phone-based resolution) to prevent tenant cross-contamination
- Loads template prompt from database for outbound calls
- Injects lead context into AI prompt (business name, lead name)
- Uses pre-existing `lead_id` for CRM context (no duplicate lead creation)
- Summaries and transcripts saved via shared pipeline for both inbound/outbound calls
- `_identify_business_and_get_greeting()` handles both inbound (phone resolution) and outbound (explicit business_id) with shared CallConfig loading

## Manually Tested
- Template CRUD operations
- Lead selection with limit enforcement (1-3 leads max)
- Call counts display and refresh
- Hebrew error messages for limit violations
- Sidebar navigation to outbound calls page
- Inbound call flow unchanged when under limits
- WebSocket handler processes outbound parameters correctly