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
- **Mandatory Verification Gate (BUILD 168)**: AI must recite ALL collected field values before hangup is allowed. User must confirm with multilingual response (Hebrew/English/Arabic) before call can end.
- **Dynamic Lead Field Prompts**: Verification prompts reference business-specific `required_lead_fields` from database.
- **Whisper Hallucination Filter**: Blocks pure English words fabricated from Hebrew audio (e.g., "Bye", "Thank you").
- **Multi-Language Support**: AI responds in Hebrew by default but switches to caller's language when requested.
- **BUILD 169 - Voice Call Quality Improvements** (Architect-Reviewed):
  - **Barge-in Protection**: Increased from 220ms to 700ms (35 frames) to prevent AI cutoff on background noise. Fixed hardcoded value to use configurable constant.
  - **STT Segment Merging**: 800ms debounce window with max length (100 chars) and long pause flush (1.5s) to prevent over-merging distinct intents.
  - **Enhanced Noise Filter**: Expanded Hebrew whitelist includes fillers (יאללה, סבבה, דקה), numbers (אחד-עשר), and natural elongations (אמממ, אההה). Blocks English hallucinations.
  - **Gibberish Detection**: Only filters 4+ repeated identical letters, allows natural elongations.
  - **Semantic Loop Detection**: Tracks AI response similarity (>70%) with 15-char minimum length floor to avoid false positives on short confirmations.
  - **Mishearing Protection**: Triggers clarification after 2 consecutive "לא הבנתי" responses (reduced from 3 for better UX).
  - **Call Session Logging**: Unique session IDs (SES-XXXXXXXX) for connect/disconnect tracking.
- **BUILD 170 - Silence Hallucination Prevention & Mandatory Verification**:
  - **Stricter VAD**: Threshold raised from 0.6 to 0.75, silence duration raised from 500ms to 1200ms to prevent false triggers.
  - **Low-RMS Gate**: Tracks audio RMS levels and rejects transcripts that arrive when audio was actually silent (prevents Whisper hallucinating on silence).
  - **Mandatory Per-Field Verification**: AI must repeat back and confirm EVERY field immediately after collecting it, even if the data looks wrong or doesn't match expectations. The AI may have misheard - the caller will correct if needed.
  - **Final Summary**: After all fields are individually confirmed, AI provides a final summary and waits for confirmation before closing.
- **BUILD 170.3 - Voice Call Quality Fixes** (Architect-Reviewed):
  - **Relaxed LOOP GUARD**: Increased max consecutive AI responses from 3 to 5. Added 8-second time window check - only triggers if user hasn't spoken in 8+ seconds.
  - **Lowered RMS Thresholds**: MIN_SPEECH_RMS reduced from 200 to 60, RMS_SILENCE_THRESHOLD from 120 to 40, VAD_RMS from 150 to 80. Hebrew speech can be quiet.
  - **Relaxed SILENCE GATE**: Only rejects transcripts with RMS < 15 (near-zero silence). Removed overly aggressive speech_threshold*0.5 check.
  - **Better Loop Guard Tracking**: Added `_last_user_speech_ts` to track when user last spoke, preventing false loop triggers during natural conversation pauses.
  - **Less Aggressive Mishearing Detection**: Back to 3 consecutive "לא הבנתי" responses before triggering clarification (was 2).

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI Navigation**: Consolidated AI prompt editing into System Settings, restricted by role.
- **RBAC Sidebar**: Dynamic visibility for "Business Management" and "User Management".
- **Role-Based Routing**: Smart default redirects based on user roles.
- **BUILD 170 - Leads UX Improvements**:
  - **Optimized Lead Search**: Filters only by name or phone number (partial match works - e.g., "075" finds any number containing "075").
  - **Fast Status Updates**: Optimistic UI updates for instant feedback (no 6-second delay).
  - **Notes Tab**: New "הערות" tab in lead detail page for free-text notes, images, and file attachments (session-local storage).
- **BUILD 170.1 - WhatsApp Chat UI Fixes**:
  - **Message Colors**: Outgoing messages (green, right side), incoming messages (white/gray, left side) - proper WhatsApp-like styling.
  - **Toggle AI Endpoint**: Added `/api/whatsapp/toggle-ai` endpoint for frontend compatibility with AI on/off toggle per conversation.
  - **Message Alignment**: Fixed RTL alignment - outgoing messages now appear on the right, incoming on the left.
  - **AI Prompt Fallback Fix**: Fixed issue where AI was always returning static "קיבלתי את ההודעה" instead of using business prompt. Now properly falls back through: Agent SDK → Regular AI (DB prompt) → Business name fallback → Static message.
  - **Database Session Fix**: Fixed `customer_number` NOT NULL constraint violation that poisoned DB sessions and broke AI responses. Added proper rollback handling.
  - **Notes Tab Sync Fix**: Fixed issue where saved notes would disappear - now properly syncs with lead data after save.

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
- **CRM Tasks**: Redesigned task board with notifications.
- **Monday.com Webhook Integration**: Per-business configurable webhook for call transcript sending.
- **Auto Hang-up Settings**: Options to automatically end calls after lead capture or on goodbye phrases.
- **Bot Speaks First**: Option for the bot to play greeting before listening to the customer.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for custom automations.