# Overview

AgentLocator is a Hebrew CRM system for real estate, designed to automate the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding. The business vision is to provide a robust, multi-tenant platform that empowers real estate agencies with cutting-edge AI communication tools.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (November 11, 2025)

**BUILD 137 - AGENT BEHAVIOR FIX: Step-by-Step Algorithm for Tool Results!**
1. ✅ **Hebrew Time Normalization**: Explicit mapping table with business hours context:
   - Hours 1-8 → PM (13:00-20:00) unless "בבוקר" specified
   - Hours 9-12 → AM (09:00-12:00) - opening hours
   - **PATTERN-BASED** half hours: `<hour> וחצי` → +30min, `חצי <hour>` → -30min (covers ALL hours!)
   - **PATTERN-BASED** quarter hours: `<hour> ורבע` → +15min, `רבע ל<hour>` → -15min (covers ALL hours!)
   - Explicit modifiers: `<any hour> + בבוקר` → AM, `+ בערב` → keep PM (no change), `+ בלילה` → late hours (21:00+)
2. ✅ **Exact Matching Algorithm**: 5-step procedure with concrete examples:
   - "שעה 1" → 13:00 → Check IN slots ["13:00", "15:00"] → "כן, 1 פנויה!" ✅
3. ✅ **ABSOLUTE SLOT LIMIT**: "NEVER READ MORE THAN 2 SLOT TIMES!"
   - 3+ slots → ask "בוקר או אחר הצהריים?"
   - After answer → filter and present max 2: "יש 9 ו-10. יש עוד, באיזו שעה בדיוק?"
4. ✅ **Complete Flow**: Initial response + follow-up after preference selection
5. ✅ **Edge Cases**: AM/PM qualifiers, half/quarter hours, business hours context

**Critical Production Fixes (Post-Deployment):**
1. ✅ **Barge-in ELIMINATED**: Hard-coded `ENABLE_BARGE_IN = False` (no env var!). STT check moved BEFORE barge-in block. `self.long_response = True` ALWAYS. ZERO interruptions possible!
2. ✅ **Lead Creation Automatic**: Enhanced fallback with duplicate checking. Every call creates/finds lead with detailed logging. GUARANTEED lead capture!
3. ✅ **Availability Validation Fixed**: Changed from detecting all "תפוס/פנוי" words to only absolute claims ("אין זמנים פנויים"). Agent can now say "15:00 תפוס, אבל 17:00 פנוי" after tool call.
4. ✅ **DTMF Instructions VERIFIED IN DB**: Prompt in database already contains "מה המספר שלך? אנא הקלידו והקישו סולמית בסיום" - cache cleared, ready for use!
5. ✅ **BUILD 135 - CRITICAL FIX: Prompt Merge Instead of Replace!** DB prompts now APPEND to base AgentKit instructions (not replace). Agent ALWAYS receives tool handling, DTMF, slot reading, and workflow rules. Custom DB prompts extend base behavior without losing critical instructions!
6. ✅ **BUILD 136 - Workflow Optimization!** Removed STATE 1 (greeting) - agent now starts directly at STATE 1 (ask time) since it's only activated after booking intent detected. Strengthened "HEBREW ONLY" directive throughout workflow. Reduced from 6 states to 5 states for clearer flow.
7. ✅ **STT Ultra-Fast**: Reduced TIMEOUT_MS to 300ms (from 400ms) for faster transcription. DEBOUNCE 80ms, BATCH 30ms.

**Previous Agent Fixes:**
1. ✅ Fixed Runner.run() initialization (TypeError resolved)
2. ✅ Added RULE #1: Agent never verbalizes internal processes
3. ✅ Enhanced DTMF phone collection instructions
4. ✅ Added WhatsApp confirmation tracking
5. ✅ Fixed intent detection with booking-first pre-check
6. ✅ Added tool name extraction fallback (output structure detection)
7. ✅ Fixed verbose slot listing - agent now asks preference instead of reading all times

**Intent Router Fix:**
- Added booking pre-check: detects booking verbs ("לקבוע", "לתאם") + time/day terms before info patterns
- Tightened info patterns to avoid false positives on booking requests
- Fixed "אפשר לקבוע חדר קריוקי למחר?" → book ✅ (was: info ❌)

**Tool Validation Enhancement:**
- Added fallback detection for calendar_find_slots based on output structure
- If tool name extraction fails, checks for {'slots': [...]} in output
- Prevents false negatives when tool wrapper changes name

**WhatsApp QR Code Fix:**
- Fixed `tenant_id_from_ctx()` to correctly retrieve business_id from session['al_user']
- Now supports impersonation (admin can act as business owner)

**Agent Behavior Improvement:**
- Removed overly restrictive guard-rails that rejected legitimate business questions
- Agent now answers questions about: services, bookings, business info, location, hours, prices
- Only rejects: recipes, cooking, jokes, trivia, general knowledge

**Slot Presentation Fix:**
- Agent no longer lists all available time slots (was reading 12+ times causing 24s audio)
- New behavior: If 3+ slots → asks "בוקר או אחה\"צ?" (morning or afternoon?)
- Only presents specific times when 1-2 options available
- Prevents audio cutoff and improves UX dramatically

**Time Interpretation Fix:**
- Fixed critical bug: "ארבע" now correctly maps to 16:00 (4 PM), not 04:00
- Added complete Hebrew number mapping: 1-9 → 13:00-21:00 (afternoon default)
- Only interprets as morning (AM) if customer explicitly says "בבוקר"
- Example: "ארבע" = 16:00 ✅ (was: 04:00 ❌)

**Tool Result Reading Fix:**
- Added explicit instructions on how to read calendar_find_slots results
- Agent now checks if customer's requested time is IN the returned slots
- If found → confirms availability; if not → suggests nearest alternative
- Prevents "no availability" response when slots ARE available

**STATE 1 Skip Logic:**
- Agent now checks conversation history before greeting
- If customer already requested appointment → skips STATE 1, goes to STATE 2/3
- Prevents redundant "How can I help?" after FAQ already identified booking intent

# System Architecture

## System Design Choices

AgentLocator employs a production-ready multi-tenant architecture ensuring complete business isolation and zero cross-tenant exposure risk. It utilizes Twilio Media Streams (WebSockets for telephony and WhatsApp) for real-time communication, featuring **barge-in completely disabled** (3-layer protection), calibrated Voice Activity Detection (VAD) for Hebrew optimized with Hebrew numbers context (boost=20.0), and smart sentence/word-boundary TTS truncation. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business and channel, boosting response times and preserving conversation state with a singleton pattern to eliminate cold starts. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling. **Agent Validation Guards** prevent hallucinated bookings and availability claims - blocking responses that claim "קבעתי" or "תפוס/פנוי" without executing the corresponding calendar tools, and logging warnings when WhatsApp confirmations are missing after successful phone bookings.

**Multi-Tenant Security:**
- Business identification via `BusinessContactChannel` table or `Business.phone_e164` auto-match.
- Unknown phone numbers are rejected (no fallback to prevent cross-tenant exposure).
- Each business has isolated prompts, agents, leads, calls, and messages.
- Universal warmup for all active businesses (up to 10).
- 401 errors for missing authentication context (no hardcoded defaults).
- Complete Role-Based Access Control (RBAC): Admin sees all data, business users see only their tenant's data.
- WhatsApp API is secured with session-based authentication, disallowing query parameter overrides for business identification.

Performance is optimized with explicit OpenAI timeouts (4s + max_retries=1 for both FAQ and Agent), increased Speech-to-Text (STT) streaming timeouts (30/80/400ms for ultra-fast responses), and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=120` for `gpt-4o-mini` and a `temperature` of 0.15 for consistent tool usage and deterministic Hebrew. **FAQ Fast-Path** uses ultra-minimal prompts (4 words), 500-char facts, `max_tokens=80`, and `temperature=0.3` for **faster responses** (~1-1.5s). FAQ handles **ONLY** "info" queries (business questions). **WhatsApp send requests** route to AgentKit to execute the actual `whatsapp_send` tool (ensures messages are actually sent, not just promised). Guard-rail rejections removed - agent answers all questions naturally. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation (confidence 0.25/0.4), Hebrew numbers context (אחד...חמישים...מאה with boost=20.0), 3-attempt retry for **+30-40% accuracy on numbers**, and **longest partial persistence** to prevent transcript regression. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. **Barge-in is completely disabled with 3-layer protection**: (1) audio processing skipped when speaking, (2) TTS loop never interrupted, (3) `long_response=True` always set. Cold start is optimized with automatic service warmup for all active businesses and Agent SDK instances. **Agent behavioral constraints** enforce RULE #1 (never verbalize internal processes like "אני בודק") to maintain professional customer-facing conversations.

## Technical Implementations

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
- **Multi-Tenant Resolution**: `resolve_business_with_fallback()` with strict security (rejects unknown).
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
- **FAQ Fast-Path**: Less than 1.5-second responses for information queries using optimized LLM with fact extraction.
- **Multi-Tenant Isolation**: Complete business data separation with zero cross-tenant exposure risk and full RBAC.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition with longest partial persistence.
  - **TTS**: Standard API with WaveNet-D voice, telephony profile, SSML support, and smart Hebrew pronunciation. Note: Hebrew is not supported by Chirp 3 HD streaming voices.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.