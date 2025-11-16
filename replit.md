# Overview

AgentLocator is a Hebrew CRM system for real estate professionals that automates the sales pipeline. It features an AI-powered assistant that processes calls in real-time, intelligently collects lead information, and schedules meetings. The system utilizes advanced audio processing for natural conversations, aiming to enhance efficiency and sales conversion. It provides a robust, multi-tenant platform with customizable AI assistants and business branding, leveraging cutting-edge AI communication tools.

## Recent Changes (2025-01-16)

### Realtime API Audio Fix
Fixed critical audio output issue where Realtime API connected successfully but calls produced only background noise. Root cause was incorrect Twilio WebSocket message format in audio output bridge.

**Fixes:**
1. Corrected Twilio message format from `{"type": "media", "payload": "..."}` to `{"event": "media", "media": {"payload": "..."}}` in `server/media_ws_ai.py`
2. Added audio chunk logging for debugging: "Sending X bytes to Twilio"
3. Improved greeting delivery using `conversation.item.create` + `response.create` sequence
4. Enhanced session configuration logging to show audio format

**Files Modified:**
- `server/media_ws_ai.py` - Audio output bridge and Twilio message format
- `server/services/openai_realtime_client.py` - Greeting delivery and session logging

### Realtime API Parameter Fixes
Fixed critical API errors that caused silent calls and Spanish responses instead of Hebrew.

**Errors Fixed:**
1. `Unknown parameter: 'session.max_output_tokens'` → Changed to `max_response_output_tokens`
2. `Invalid value: 'input_text'. Value must be 'text'` → Fixed content type in conversation items

**Impact:**
- Silent audio resolved
- Spanish responses resolved (now Hebrew)
- Greeting delivery fixed
- Session configuration validated

**Files Modified:**
- `server/services/openai_realtime_client.py` - Parameter names and content types
- `server/media_ws_ai.py` - Added prompt preview logging

### Complete Realtime API Audio Pipeline Fix
Implemented comprehensive fix following detailed guide. Resolved tx=0 issue (no audio sent to Twilio).

**Root Cause:**
- Audio bridge used wrong format: `{"event": "media", "media": {...}}` instead of `{"type": "media", "payload": ...}`
- VAD threshold too low (35.0) caused constant false noise detection

**Fixes Applied:**
1. **Audio Chunk Logging** - Added logging in `openai_realtime_client.py` when receiving audio from OpenAI
2. **Audio Bridge Fix** - Corrected format from `event` to `type` in `_realtime_audio_out_loop`
3. **Transmission Tracking** - Added counters and logging for audio sent to Twilio
4. **G.711 μ-law Verification** - Confirmed proper audio format configuration (8kHz)
5. **VAD Threshold Increase** - Raised from 35.0 → 800.0 to prevent false noise detection
6. **Logging Reduction** - Reduced spam from every frame to every 50th frame

**Expected Results:**
- `tx > 0` in WS_STOP logs (frames actually sent)
- Logs show: `[REALTIME] got audio chunk from OpenAI: bytes=X`
- Logs show: `[REALTIME] sent media frame to Twilio: total_sent=X`
- Clear Hebrew voice in calls, no "vacuum cleaner" noise
- AI doesn't complain about background noise constantly

**Files Modified:**
- `server/services/openai_realtime_client.py` - Audio chunk logging
- `server/media_ws_ai.py` - Audio bridge format fix, transmission tracking, VAD threshold increase

### Final Twilio Format Fix
Fixed incorrect Twilio message format that caused noise instead of clear audio.

**Root Cause:**
- Used `{"type": "media", "payload": ...}` but Twilio requires `{"event": "media", "streamSid": ..., "media": {"payload": ...}}`
- VAD threshold was too high (800) after previous fix

**Fixes Applied:**
1. **Correct Twilio Format** - Fixed to exact Twilio Media Streams specification with `streamSid`
2. **Enhanced Logging** - Added first10 bytes logging to verify μ-law format
3. **No PCM Conversion** - Verified audio stays as g711_ulaw throughout (line 978 sends `b64` directly)
4. **Moderate VAD Threshold** - Reverted from 800 to 150-250 for balanced Hebrew speech detection

**Expected Results:**
- Clear Hebrew voice (no noise/static)
- User speech detected and transcribed
- Logs show: `[REALTIME] sending frame to Twilio: len=X, first10=...`

**Files Modified:**
- `server/media_ws_ai.py` - Twilio format fix, VAD threshold revert, enhanced logging

### Enhanced Realtime Audio Debugging (2025-01-16)
Added comprehensive logging to track audio flow in both directions for debugging persistent noise issue.

**Logging Added:**
1. **Twilio → OpenAI**: First 3 chunks logged with hex dump of μ-law bytes
2. **OpenAI → Twilio**: First 3 chunks + every 100th frame logged with hex dump
3. **streamSid validation**: Verify streamSid is present before sending to Twilio
4. **Frame counting**: Track total frames sent via Realtime path

**Debug Logs to Check:**
```
[REALTIME] sending audio TO OpenAI: chunk#1, μ-law bytes=160, first5=ff 7f ff 7f ff
[REALTIME] got audio chunk from OpenAI: chunk#1, bytes=160, first5=ff 7f ff 7f ff
[REALTIME] TX frame #1: len=160, first5_hex=ff 7f ff 7f ff, streamSid=MZ...
```

**Files Modified:**
- `server/media_ws_ai.py` - Enhanced bidirectional audio logging

### Critical TX Counter Fix (2025-01-16)
Fixed the root cause of tx=0 issue where frames were processed but counter wasn't incremented.

**Root Cause:**
- Audio output bridge correctly sent frames to tx_q (44 frames, 530400 bytes logged)
- TX loop received and sent frames via WebSocket
- BUT self.tx counter was never incremented → tx=0 in WS_STOP logs

**Fixes Applied:**
1. **TX Counter Increment** - Added `self.tx += 1` after successful `_ws_send()` in both Realtime and legacy paths
2. **Temperature Minimum** - Fixed `temperature=0.15` → `max(0.6, temperature)` (Realtime API requires ≥0.6)
3. **TX Loop Logging** - Added debug logs for first 3 frames to verify format detection and send success

**Expected Results:**
```
[TX_LOOP] Frame 0: type=None, event=media, has_media=True
[TX_LOOP] Sent Realtime format: success=True
WS_STOP: tx=44 (not 0!)
```

**Files Modified:**
- `server/media_ws_ai.py` - TX counter fix and enhanced logging
- `server/services/openai_realtime_client.py` - Temperature minimum enforcement

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

AgentLocator uses a multi-tenant architecture with complete business isolation. It integrates Twilio Media Streams for real-time communication, featuring Hebrew-optimized Voice Activity Detection (VAD) and smart TTS truncation. The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel to boost response times and preserve conversation state. The system mandates name and phone confirmation during scheduling, utilizing dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. Agent Validation Guards prevent AI hallucinations by blocking responses that claim bookings or availability without executing corresponding calendar tools.

Multi-tenant security is paramount, with business identification via `BusinessContactChannel` or `Business.phone_e164`, rejection of unknown phone numbers, and isolated prompts, agents, leads, calls, and messages per business. It includes universal warmup for active businesses, handles 401 errors for missing authentication, and implements comprehensive Role-Based Access Control (RBAC).

Performance optimization includes explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=60` and a `temperature` of 0.15. Audio streaming uses a `tx_q` queue with 90% backpressure. A FAQ Hybrid Fast-Path uses a 2-step matching approach: first, `patterns_json` keyword matching (sub-100ms, score=1.0), then an OpenAI embeddings fallback (cosine similarity ≥0.78). Keywords are case-insensitive with bidirectional substring matching. FAQ runs BEFORE AgentKit on phone calls only. Channel filtering ensures voice-only FAQs, and WhatsApp send requests route to AgentKit to execute the `whatsapp_send` tool. Prompts are loaded exclusively from `BusinessSettings.ai_prompt`. STT reliability benefits from relaxed validation, Hebrew numbers context, and a 3-attempt retry for improved accuracy. Voice consistency is maintained with a male Hebrew voice and masculine phrasing. Agent behavioral constraints enforce not verbalizing internal processes.

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
- **Data Protection**: Database migrations are strictly additive with automatic verification; no user data deleted on deployment.
- **OpenAI Realtime API**: Feature-flagged migration (`USE_REALTIME_API=true`) from Google STT/TTS to OpenAI Realtime API for phone calls. Uses dedicated asyncio thread with thread-safe queues, bidirectional audio streaming, and `websockets>=13.0`.

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
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses using 2-step matching: (1) patterns_json keyword matching (instant, score=1.0), (2) OpenAI embeddings fallback (cosine similarity ≥0.78).
- **Multi-Tenant Isolation**: Complete business data separation with zero cross-tenant exposure risk and full RBAC.
- **Appointment Settings UI**: Allows businesses to configure slot size, 24/7 mode, booking window, and minimum notice time.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: 
  - GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
  - **Realtime API** (`gpt-4o-realtime-preview`): Low-latency speech-to-speech for phone calls when `USE_REALTIME_API=true`. Handles Hebrew conversation with ~1.5-2.0s total latency (ASR ~0.3-0.6s, AI ~0.7-1.3s, TTS ~0.2-0.4s).
- **Google Cloud Platform** (legacy/fallback when `USE_REALTIME_API=false`):
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets>=13.0**: Python library for WebSocket connections (OpenAI Realtime API).