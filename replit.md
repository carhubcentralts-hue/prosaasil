# Overview

ProSaaS is a multi-tenant SaaS platform that provides an AI assistant for WhatsApp and phone calls, primarily in Hebrew. It automates the sales pipeline through real-time call processing, lead information collection, and meeting scheduling, leveraging OpenAI's Realtime API. The platform offers complete business isolation, robust user management with 4-tier role-based access control, and aims to boost sales conversion and operational efficiency via advanced audio processing and customizable AI functionalities. The project's core ambition is to empower businesses with intelligent, automated sales support.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices

ProSaaS utilizes a multi-tenant architecture with strict data isolation and integrates Twilio Media Streams for real-time communication. Key features include Hebrew-optimized Voice Activity Detection (VAD), smart Text-to-Speech (TTS) truncation, and an AI assistant using an Agent SDK for appointment scheduling and lead creation, complete with conversation memory and an Agent Cache System. The system supports dual input (verbal and DTMF), incorporates a DTMF Menu System, and provides channel-aware responses. Agent Validation Guards prevent AI hallucinations. Security is maintained through business identification, rejection of unknown numbers, isolated data, and 4-tier Role-Based Access Control (RBAC). Performance is optimized via explicit OpenAI timeouts, increased Speech-to-Text (STT) streaming timeouts, and a `tx_q` queue with backpressure for audio streaming. A FAQ Hybrid Fast-Path uses a two-step matching approach with channel filtering. STT reliability is enhanced with relaxed validation, Hebrew number context, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice and masculine phrasing, with agent behavioral constraints. Appointment scheduling uses server-side text parsing with GPT-4o-mini for intelligent Hebrew NLP, business hours validation, and DB-based deduplication. Call control is managed by a state machine dictating the call lifecycle and settings.

## Technical Implementations

### Backend
- **Frameworks**: Flask (SQLAlchemy ORM) and Starlette (native WebSocket handling) with Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with RBAC and CSRF protection.
- **AI Prompt System**: Real-time management, versioning, and channel-specific prompts.
- **AI Integration**: Uses `gpt-4o-realtime-preview` for voice calls and `gpt-4o-mini` for server-side NLP, with behavioral rules and hallucination filtering.
- **Hebrew Optimization**: Optimized VAD, AI greeting system, Hebrew normalization dictionary, and grammar improvements. Includes advanced phonetic and fuzzy matching for Hebrew cities and names, and an expanded Hebrew STT dictionary with 2,261 corrections.
- **Call Quality**: Includes barge-in protection, STT segment merging, noise filtering, gibberish/semantic loop detection, mishearing protection, and silence hallucination prevention. VAD parameters are tuned for normal speech.
- **Webhook**: Separate inbound/outbound webhook URLs with HMAC signature verification and retry logic.
- **Conversation Flow**: Implements robust recovery for cancelled responses, smart overlap grace, and a `user_speech_seen` flag to prevent silence and drops. Includes confirmation gates and closing fence guards to prevent AI loops.
- **BUILD 195 Confirmation & Sound Fixes**:
  - **End-of-call confirmation gate**: `pending_confirmation` now requires `lead_captured=True` before activating. Casual "כן" mid-call is ignored - only final verification triggers confirmation.
  - **Context-aware city rejection**: City normalizer rejects non-city words ("כן", "לא", "סבבה") with hint to reprompt.
  - **Sustained speech tracking**: Speech <600ms logged as noise. `_sustained_speech_confirmed` flag set only after 600ms+ continuous speech.
  - **Response grace period**: 1000ms before allowing barge-in on new AI responses.
- **BUILD 196 Audio Preprocessing for Noisy Environments**:
  - **Speech Band Filter**: μ-law → PCM16 → 100Hz HPF + 3400Hz LPF to isolate human voice and remove bass rumble/high-freq noise.
  - **SNR-based Gating**: Rolling noise floor estimation, per-frame SNR calculation (8dB threshold normal, 12dB when music detected), 3-frame hangover to prevent choppiness.
  - **Music Detection**: Multi-indicator system (CV, periodicity, sustained energy) with hysteresis (enter at 0.6, exit at 0.45) to prevent flapping.
  - **Gibberish Word Removal**: GIBBERISH_WORDS_TO_REMOVE set removes known hallucination words ("ידועל", "בלתי") from transcripts as soft guard.
  - **Doubled Consonant Fixes**: Hebrew dictionary corrections for noise-induced errors ("דדלתות" → "דלתות").
- **BUILD 196.1 Production-Grade Audio Pipeline**:
  - **Noise Calibration**: First 600ms of call used to calibrate noise floor (20th percentile). Slow adaptation after calibration to track background changes.
  - **Pre-roll Buffer**: 200ms buffer captures start of words when transitioning SILENCE→SPEECH. Prevents missing first syllable.
  - **State Machine**: SILENCE → MAYBE_SPEECH (3 frames) → SPEECH with separate start/stop SNR thresholds for hysteresis. Strict SILENCE gating prevents noise leaks.
  - **AGC (Automatic Gain Control)**: Normalizes quiet/loud callers to target level (-20dBFS). Max gain 4x, min 0.5x. Applied BEFORE SNR calculation for consistent thresholds.
  - **Legacy Gate Bypass**: BUILD 165/166/167/171 pre-queue noise gates bypassed when using Realtime API - BUILD 196.1 handles all filtering.
  - **Configurable Thresholds**: All parameters exposed via env vars:
    - SNR: `SNR_START_NORMAL`, `SNR_STOP_NORMAL`, `SNR_START_MUSIC`, `SNR_STOP_MUSIC`
    - Timing: `AUDIO_HANGOVER_FRAMES`, `AUDIO_PREROLL_MS`, `NOISE_CALIBRATION_MS`
    - Filters: `AUDIO_HPF_ALPHA`, `AUDIO_LPF_ALPHA`
    - AGC: `AUDIO_TARGET_RMS`, `AUDIO_AGC_ALPHA`, `AUDIO_AGC_MAX_GAIN`, `AUDIO_AGC_MIN_GAIN`
    - State: `AUDIO_MAYBE_SPEECH_FRAMES`, `AUDIO_MUSIC_CONFIRM_FRAMES`
    - Music: `MUSIC_ENTER_THRESHOLD`, `MUSIC_EXIT_THRESHOLD`
- **BUILD 196.2 Corrected Audio Pipeline Order**:
  - **SNR on PRE-AGC audio**: noise_rms and SNR computed on raw filtered signal (not AGC-boosted) for accurate speech/noise separation.
  - **AGC only on SPEECH frames**: AGC applied ONLY after state machine confirms speech, preventing noise amplification.
  - **Strict SILENCE/MAYBE gating**: NEVER send audio in SILENCE or MAYBE_SPEECH states (only SPEECH sends).
  - **Pre-roll with AGC**: Pre-roll buffer stores pre-AGC audio; AGC applied to preroll when flushing for consistent volume.
  - **Pipeline order**: Bandpass → SNR/noise calibration → Music detection → State machine → AGC (SPEECH only) → Send.
  - **Manual response.create trigger**: Since client-side VAD filters audio, OpenAI's server-side VAD may not detect end-of-speech. Solution: send `response.create` manually after END OF UTTERANCE via `[TRIGGER_RESPONSE]` queue command.
- **BUILD 196.4 Echo Protection (Fixed)**:
  - **ALWAYS send audio to OpenAI**: Audio is NEVER blocked - OpenAI must hear everything to understand short Hebrew words ("כן", "לא", city names).
  - **Echo blocking only affects TRIGGER_RESPONSE**: The manual `response.create` trigger is blocked during echo window, but audio transmission continues.
  - **400ms post-AI cooldown**: Reduced from 500ms for faster user responses.
  - **Barge-in preserved**: User can interrupt during AI response - OpenAI's `speech_started` event handles real barge-in detection.
  - **TRIGGER_RESPONSE on SPEECH→SILENCE**: When state machine detects speech ending (and not in echo block), automatically sends `response.create` to OpenAI via queue.
  - **Utterance duration tracking**: Tracks `utterance_start_ms` when speech begins, calculates duration on SPEECH→SILENCE.
  - **Active response guard**: Before sending `response.create`, checks `active_response_id` to prevent duplicate responses.
- **BUILD 196.5 AI Transcript Storage**:
  - **AI transcripts saved to conversation_history**: `response.audio_transcript.done` event now appends AI transcript to `conversation_history` with speaker="assistant".
  - **Complete call transcription**: Both user and AI transcripts are now stored for call logging.
- **BUILD 197 Human-Like VAD (Critical Fix)**:
  - **Problem solved**: AI was responding to short noise bursts (4ms, 95ms, 126ms) instead of waiting for real speech.
  - **MIN_UTTERANCE_DURATION_MS=900**: User must speak for at least 0.9 seconds before AI responds.
  - **MIN_TRAILING_SILENCE_MS=500**: After speech ends, wait 0.5 seconds of silence to confirm end of utterance.
  - **MIN_FIRST_UTTERANCE_MS=1200**: First utterance requires 1.2 seconds to prevent premature responses.
  - **All thresholds configurable via env vars**: MIN_UTTERANCE_DURATION_MS, MIN_TRAILING_SILENCE_MS, MIN_FIRST_UTTERANCE_MS.
  - **Short utterances IGNORED completely**: No trigger, no user_has_spoken flag - prevents AI from interrupting.
  - **Trailing silence tracking**: `last_speech_frame_ts` updated on each speech frame; SPEECH→SILENCE only after silence threshold met.
  - **user_has_spoken gating**: Only set to True when utterance passes duration threshold (not on speech_started or short segments).
  - **CLOSING state guard**: In CLOSING state, all speech events ignored for triggers and user_has_spoken.
  - **Result**: AI waits for user to finish speaking naturally, like a human conversation.
- **BUILD 198 Audio Path Fix (STT Hallucination Fix)**:
  - **Problem solved**: STT was transcribing things user never said ("תודה רבה", "שלום") due to audio path corruption.
  - **Root cause**: Double μ-law encoding (Twilio→PCM→filter→μ-law→AGC→μ-law) corrupted audio sent to OpenAI.
  - **Raw μ-law preservation**: `raw_ulaw_b64` saved immediately from Twilio - NEVER re-encoded.
  - **DSP for VAD only**: Bandpass filter and RMS calculated on PCM copy for VAD decisions, NOT for audio sent.
  - **AGC removed from send path**: No gain applied to audio sent to OpenAI - prevents distortion.
  - **Echo blocking (not just trigger)**: Audio completely blocked when `is_ai_speaking=True`, not just `response.create` trigger.
  - **Preroll uses raw μ-law**: Buffer stores original Twilio audio, not filtered/AGC'd copies.
  - **Diagnostic mode**: Set `AUDIO_DIAGNOSTIC_MODE=true` to save call audio to `/tmp/realtime_{call_sid}.ulaw` and transcripts to `/tmp/realtime_{call_sid}_transcripts.txt` for debugging.
  - **Pipeline order**: Twilio → raw_ulaw saved → decode to PCM for VAD → VAD decision → send raw_ulaw.
  - **Result**: OpenAI receives exact audio from Twilio phone line, no processing artifacts.

### Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography.
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **Security**: CSRF protection, secure redirects, and role-based access control.
- **UI/UX**: Consolidated AI prompt editing, dynamic sidebar visibility, optimized lead search, fast status updates, and a notes tab for leads.

## Feature Specifications
- **Call Logging & Conversation Memory**: Comprehensive tracking and full history.
- **WhatsApp Integration**: Baileys and Meta Cloud API support with per-business provider selection.
- **Lead Management**: Automated capture, creation, deduplication, and customizable statuses.
- **Calendar & Meeting Scheduling**: AI checks real-time availability with configurable slot size, availability, booking window, and minimum notice, validated server-side.
- **Customizable AI Assistant**: Configurable names, introductions, and greetings.
- **Outbound Calls**: AI-initiated calls with concurrency limits and template-based prompts. Supports bulk import of leads for campaigns.
- **FAQ Hybrid Fast-Path**: Sub-2s voice responses.
- **Security Hardening**: Twilio signature validation, dynamic business identification.
- **Payments & Contracts**: Feature flags for billing.
- **CRM Tasks**: Redesigned task board with notifications.
- **Auto Hang-up Settings**: Options to end calls after lead capture or on goodbye.
- **Bot Speaks First**: Option for bot to greet before listening.
- **Admin Business Minutes**: System-admin-only page for call minutes reporting.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini, `gpt-4o-realtime-preview`, and Whisper transcription.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
- **websockets**: Python library for WebSocket connections.
- **n8n**: Workflow automation platform for external integrations (e.g., Monday.com, Google Sheets, Slack) via webhooks.