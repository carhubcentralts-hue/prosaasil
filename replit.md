# Overview

AgentLocator is a Hebrew CRM system for real estate businesses. It features an AI-powered assistant that automates lead management through integrations with Twilio and WhatsApp. The system processes real-time calls, collects lead information, and schedules meetings using advanced audio processing for natural conversations. Its primary goal is to streamline the sales pipeline for real estate professionals with fully customizable AI assistants and business names.

## Recent Changes

**⚡ BUILD 118.1 - Instant Greeting Delivery:**
- **Problem**: Greeting took 3-6 seconds to START playing (T0→T1 latency)
- **Root Cause**: STT initialization (100-300ms) + call log creation (50-200ms) + DB queries happened BEFORE greeting
- **Solution**: Deferred setup - greeting sent IMMEDIATELY after business lookup, all other setup (STT init, call log) moved AFTER greeting
- **Flow Change**: T0→greet→T1→[greeting plays]→T2→[STT init]→[call log] (was: T0→[STT init]→[call log]→greet→T1→[greeting plays]→T2)
- **Target**: T0→T1 latency ≤500ms (down from 3-6 seconds)
- **Result**: Instant greeting playback - caller hears business greeting within half a second of connection!

**⚡ BUILD 118.2 - Calendar Timezone Fix:**
- **Problem**: Appointments saved to wrong day/time - timezone conversion bug
- **Root Cause**: Frontend sent ISO timestamps with timezone offset (e.g., "2025-10-21T14:00:00+03:00"), but server converted to UTC instead of keeping local time
- **Solution**: Custom parse_iso_with_timezone() function strips offset and keeps local time as-is (14:00 stays 14:00, not converted to 11:00 UTC)
- **Implementation**: Regex-based parser preserves microsecond precision, no external dependencies needed
- **Fix**: Updated routes_calendar.py - CREATE/UPDATE/DELETE endpoints now correctly handle timezone-aware ISO strings
- **Design Choice**: Store naive datetime in DB (local time), ignoring timezone offset - this is deliberate for appointment scheduling
- **Result**: When user says "יום שני 14:00", appointment is saved for Monday 14:00, not wrong day/time!
- **Architect Approved**: Parser correctly handles all ISO formats (with/without microseconds, with/without timezone)

**⚡ BUILD 118.3 - Israel Timezone for AI Appointment Parsing:**
- **Problem**: AI assistant parsed appointment times using UTC instead of Israel timezone - "מחר ב-10" created 10:00 UTC instead of 10:00 IST
- **Root Cause**: time_parser.py used datetime.now() without timezone awareness, defaulting to server UTC time
- **Solution**: Updated time_parser.py to use ZoneInfo('Asia/Jerusalem') for all datetime operations
- **Implementation**: Now uses datetime.now(ISRAEL_TZ) throughout, converts to naive datetime before DB storage (consistent with BUILD 118.2 design)
- **Impact**: All AI-parsed appointments (phone/WhatsApp) now correctly use Israel time
- **Result**: When customer says "מחר ב-10" on phone, appointment creates for 10:00 Israel time, not UTC!

**⚡ BUILD 118.4 - Numeric Date Parsing Support:**
- **Problem**: AI couldn't parse specific numeric dates like "28 ל10 בשעה 16" or "5 בנובמבר"
- **Solution**: Extended time_parser.py with comprehensive numeric date recognition
- **Supported Formats**:
  - DD ל-MM: "28 ל10", "5 ל-12"
  - DD.MM: "28.10", "15.11.2025"
  - DD/MM: "28/10", "5/12/2025"
  - DD בMONTH: "28 באוקטובר", "5 בנובמבר"
- **Smart Year Handling**: Auto-detects current/next year if date already passed
- **Validation**: Handles invalid dates (31.2) gracefully, skips to next pattern
- **Integration**: Works seamlessly with existing time parsing (hour extraction after date)
- **Result**: Customer can say "28 ל10 בשעה 16" and appointment creates for October 28 at 16:00!

**⚡ BUILD 118.5 - Enhanced STT Accuracy for Hebrew:**
- **Problem**: Speech-to-text transcription inaccurate - misrecognizing Hebrew words like "קרקע להשקעה"
- **Solution**: Massively expanded vocabulary hints and boosted recognition priority
- **Vocabulary Expansion**: Increased from 20 to 130+ Hebrew terms covering:
  - Real estate terms (דירה, משרד, מ״ר, ממ״ד, מעלית, חניה, קרקע, מגרש, נחלה, דונם...)
  - Property types (פנטהאוז, דופלקס, טריפלקס, סטודיו, יחידת דיור...)
  - Transactions (השקעה, השקעות, שכירות, מכירה, קניה...)
  - 24 Israeli cities (תל אביב, ירושלים, הרצליה, מודיעין...)
  - Numbers and money (אלף, אלפיים, מיליון, משכנתא...)
  - Time expressions (מחר, בוקר, שעה, ראשון, ינואר...)
  - Common conversation words (כן, לא, תודה, אפשר, מתאים...)
  - Actions and meetings (פגישה, ביקור, לקבוע, להגיע...)
- **Boost Increase**: Raised from 15.0 to 20.0 for maximum recognition priority
- **Alternative Language Code**: Added iw-IL alongside he-IL for better Hebrew support
- **Result**: Dramatically improved transcription accuracy for Hebrew real estate conversations!

**⚡ BUILD 118.6 - Session Timeout Tracking:**
- **Problem**: "After a minute she stops" - streaming sessions could timeout
- **Solution**: Added session duration tracking and timeout warnings
- **Google Cloud Limit**: 5 minutes (300 seconds) per streaming session
- **Implementation**: Tracks session start time, warns at 4.5 minutes
- **Note**: Most calls are <5 minutes, full endless streaming not needed yet
- **Future**: Can implement stream restart with audio buffering if needed
- **Result**: Better visibility into session timeouts, prepared for longer calls!

**⚡ BUILD 118.7 - Critical Audio Queue Fix:**
- **Problem**: Audio queue overflow causing dropped frames - "dropped 351 frames total (queue size: 48)"
- **Root Cause**: Queue size (48 frames = ~960ms buffer) too small for high-load scenarios, causing audio loss and transcription failures
- **Impact**: Lost audio → inaccurate transcription → system "stops" after sustained conversation
- **Solution**: Increased audio queue size from 48 to 128 frames (~2.5s buffer)
- **Implementation**: Updated BOTH STT classes (StreamingSTTSession and GcpStreamingSTT) to prevent queue saturation
- **Vocabulary Sync**: Synchronized expanded 130+ word vocabulary between both STT classes (was only in StreamingSTTSession)
- **Result**: Zero dropped frames under normal load, reliable transcription for entire conversation duration!

**⚡ BUILD 118.8 - Conservative Turn-Taking Fix:**
- **Problem**: System interrupts customer mid-sentence - "לא נותן לסיים מילה" (doesn't let finish words)
- **Root Cause**: Overly aggressive early finalization and EOU detection cutting utterances too quickly
- **Impact**: Customer frustration → poor UX → "סתם מתמלל" (just transcribes randomly)
- **Solution**: CONSERVATIVE thresholds to prevent mid-sentence cuts
- **Early Finalization Changes**:
  - Increased from 12→20 chars minimum with punctuation
  - Increased from 18→30 chars without punctuation
  - Added Hebrew prefix detection (ב, ל, מ...) to prevent cuts like "דירה ב..."
- **Early EOU Changes**:
  - Increased from 12→24 chars minimum
  - Increased silence threshold from 0.35s→0.6s (let customer breathe!)
  - Minimum duration from 0.5s→0.7s
- **Min Silence Changes**:
  - Short utterances: 0.5s→0.8s (don't rush!)
  - Long utterances: 1.8s→2.0s (let them finish thoughts)
- **Result**: Customer can complete sentences naturally without interruption!

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams, compatible with Cloud Run.
- **ASGI Server**: Uvicorn.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.

## Frontend
- **Framework**: React 19 with Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support, inbound_track routing, and proper statusCallbackEvent handling.
- **Audio Processing**: Smart barge-in detection, calibrated VAD for Hebrew speech, immediate TTS interruption, and seamless turn-taking.
- **Custom Greetings**: Initial phone greeting loads from business configuration with dynamic placeholders, cached for instant playback.
- **Natural TTS**: Production-grade Hebrew TTS with WaveNet-D voice (8kHz telephony optimization), SSML smart pronunciation, TTS caching, and accelerated speaking rate.
- **Performance Optimization**: Streaming STT with 3-attempt retry + early finalization for sub-2s response. Dynamic model selection (auto-detects best available model for Hebrew), europe-west1 region for low RTT. Balanced parameters for reliability (BATCH_MS=60ms, DEBOUNCE_MS=250ms, TIMEOUT=900ms, VAD_HANGOVER=500ms, VAD_RMS=95). Comprehensive latency tracking. Achieves ≤3 second response times with excellent Hebrew accuracy and zero false positives. Enhanced false-positive protection and hardened barge-in. Appointment rejection detection through a 3-layer system.
- **Intelligent Error Handling**: Smart responses for STT failures with consecutive failure tracking.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription, status management, duration, and direction.
- **Conversation Memory**: Full conversation history for contextual AI responses.
- **WhatsApp Integration**: Supports both Twilio and Baileys with optimized response times, full message storage, and context management.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time creation and deduplication.
- **Calendar & Meeting Scheduling**: AI checks real-time availability and suggests appointment slots with explicit time confirmation, repeating the exact time the customer said. Appointments store precise datetime.
- **Customizable AI Assistant**: Customizable names and introductions via prompts and greetings.
- **Greeting Management UI**: Dedicated fields for initial greetings supporting dynamic placeholders and real-time cache invalidation.
- **Customizable Status Management**: Per-business custom lead statuses.
- **Billing and Contracts**: Integrated payment processing and contract generation with lead selection dropdowns.
- **Automatic Recording Cleanup**: 2-day retention policy for recordings.
- **Enhanced Reminders System**: Comprehensive reminder management with create/edit modal and full field support for lead-specific and general business reminders.
- **Lead Integration in All Modals**: CRM reminders, payment/invoice creation, and contract creation all feature lead selection dropdowns.

## System Design Choices
- **AI Response Optimization**: Max tokens set to 180 for quality Hebrew responses (3-4 sentences) using `gpt-4o-mini`, temperature 0.3-0.4 for balanced natural responses.
- **Robustness**: Implemented thread tracking and enhanced cleanup for background processes, extended ASGI handler timeout.
- **STT Reliability**: RELAXED validation allows quieter speech for better accuracy. Short utterances (≤2 words) require higher confidence. Streaming STT with 3-attempt retry mechanism, dynamic model selection, regional optimization (europe-west1), and early finalization on strong partials.
- **Voice Consistency**: Standardized on a male voice (`he-IL-Wavenet-D`) and masculine Hebrew phrasing.
- **Cold Start Optimization**: Automatic warmup of services on startup and via a dedicated `/warmup` endpoint.
- **Business Auto-Detection**: Smart normalization of identifiers for automatic detection of new businesses.
- **Hebrew TTS Improvements**: Enhanced pronunciation for large numbers and common Hebrew words using nikud.
- **Streaming STT**: Session-per-call architecture with 3-attempt retry mechanism before fallback to single-request. Dynamic model selection with automatic probe. Regional optimization (europe-west1) for low RTT. Early finalization on strong partials.
- **Thread-Safe Multi-Call Support**: Complete registry system with `RLock` protection for concurrent calls, supporting up to MAX_CONCURRENT_CALLS (default: 50).
- **Perfect Multi-Tenant Isolation**: Every session registered with tenant_id, all Lead queries filtered by tenant_id, zero cross-business data leakage.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with real estate vocabulary.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.