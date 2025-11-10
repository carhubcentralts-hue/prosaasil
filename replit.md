# Overview

AgentLocator is a Hebrew CRM system for real estate businesses that automates the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding.

# Recent Changes

## PHASE 2L - AGENTKIT GATE SYSTEM (IN PROGRESS - November 10, 2025)

**SMART ROUTING ARCHITECTURE - AgentKit Only When Needed**

### **Problem**: AgentKit running on EVERY message → slow responses (4-7s)
- Info questions ("כמה עולה?") don't need AgentKit
- Simple bookings ("מחר ב-2") can be faster with direct calendar calls
- Only complex bookings need full AgentKit orchestration

### **Solution - 3-Route Architecture**:

**Route 1: FAQ Path** (~0.8s latency)
- **Intents**: info, other, whatsapp, human
- **Method**: Lightweight GPT-4o-mini, no tools, 50 max_tokens
- **Example**: "כמה עולה?" → Quick answer from business prompt

**Route 2: Fast-Path** (~1.5s latency)
- **Intents**: book (simple time pattern detected)
- **Method**: Regex time parsing + direct calendar tool calls
- **Example**: "מחר ב-2" → Parse time → Check availability → Respond
- **Fallback**: If parsing fails or needs name/phone → Route 3

**Route 3: Full AgentKit** (~2-3s latency)
- **Intents**: book (complex), reschedule, cancel
- **Method**: Full Agent SDK with all tools
- **Example**: Multi-turn booking with name/phone collection

### **Implementation**:
1. **Intent Router** (`route_intent()`) - Fast Hebrew keyword detection
   - No LLM needed - simple keyword matching
   - Detects: book, reschedule, cancel, info, whatsapp, human, other
   
2. **AgentKit Gate** - Controls when to invoke Agent SDK
   - `AGENTKIT_BOOKING_ONLY=1` (default) - Only for booking intents
   - `FAST_PATH_ENABLED=1` (default) - Try fast-path before AgentKit
   
3. **Helper Functions**:
   - `_generate_faq_response()` - Quick GPT-4o-mini for info
   - `_handle_direct_booking()` - Regex parsing + calendar tools

### **Files Modified**:
- `server/services/ai_service.py` (34-93, 494-617, 656-678): Intent router, helpers, gate logic

### **Expected Impact**:
- Info questions: 4s → **0.8s** (80% faster!)
- Simple bookings: 4s → **1.5s** (60% faster!)
- Complex bookings: ~3s (unchanged, still need full AgentKit)

---

## PHASE 2K - BARGE-IN & WHATSAPP FIX (COMPLETED - November 10, 2025)

**CRITICAL USER-REPORTED BUGS FIXED** - Architect-reviewed!

### **Bug 1) Barge-in Too Sensitive - Stops Mid-Sentence**
- **Problem**: Background noise (רעש קטן) interrupted Agent mid-sentence  
- **Root Cause**: grace_period=2.5s too short, barge_in_threshold=1500-1800 RMS too low
- **Solution**: grace_period→3.5s, barge_in_threshold→2200-2500 RMS, voice_in_row→120 frames (2.4s)
- **Files**: `server/media_ws_ai.py` (lines 817-831)
- **Benefits**: ✅ Agent finishes sentences, only genuine loud interruptions work

### **Bug 2) WhatsApp Confirmation Not Sending**
- **Problem**: User log showed booking success but NO "📱 Sending WhatsApp" message
- **Root Cause**: Code tried `flask.g.agent_context` inside Agent SDK tool (not available)
- **Solution**: Use `context` parameter, added logging, fixed channel mismatch ("phone" not "voice_call")
- **Files**: `server/agent_tools/tools_calendar.py` (457-467), `server/media_ws_ai.py` (2358-2359)
- **Benefits**: ✅ WhatsApp confirmation now sends after phone call bookings

### **Bug 3) AI Reads ALL Available Times - TOO LONG!**
- **Problem**: AI said "יש לנו זמינות בשעות 09:00, 10:00, 11:00..." (23 words, 24s TTS!)
- **Root Cause**: Tool returned ALL slots, AI read them all (no code enforcement)
- **Solution**: 
  - **CODE ENFORCEMENT**: Tool now returns MAX 4 slots (truncates at tool level)
  - Updated agent_factory.py STATE 2/3: "NEVER list all slots - max 2 suggestions!"
  - Updated calendar_find_slots tool description with examples
- **Files**: 
  - `server/agent_tools/tools_calendar.py` (229-235): **Max 4 slots hardcoded**
  - `server/agent_tools/agent_factory.py` (498-508): Prompt instructions
- **Benefits**: ✅ **Guaranteed** max 4 options, even if AI ignores prompt

### **Bug 4) AI Latency Optimization Attempt (ROLLED BACK)**
- **Problem**: Total latency 4.47s (ai=3.9s, stt=0.0s, tts=0.54s)
- **Attempted Solution**: Shortened prompts to 400 chars, reduced max_tokens to 160
- **Result**: FAILED - latency increased to 7.6s, bot became incoherent and verbose
- **Root Cause of Failure**: Prompt too short caused AI confusion, leading to longer processing
- **Final Solution - BALANCED OPTIMIZATION**:
  1. **Moderate prompt compression**: 2.8k → ~800 chars (still clear and functional)
  2. **Truncated history**: 10 messages → 8 messages (4 full conversation turns)
  3. **Message truncation**: Long messages cut to 250 chars max
  4. **Reduced max_tokens**: 400 → 300 tokens (enough for Hebrew + tools)
  5. **TTS optimization**: speaking_rate=1.05 (already configured)
- **Files**: 
  - `server/agent_tools/agent_factory.py` (40-46, 465-490): Prompts + settings
  - `server/services/ai_service.py` (597-599): History truncation
- **Expected Impact**: Modest improvement (~10-20%) without breaking functionality

---

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## System Design Choices
AgentLocator employs a multi-tenant architecture with business-specific data isolation. It uses Twilio Media Streams (WebSockets for telephony and WhatsApp) for real-time communication, featuring smart barge-in, calibrated VAD for Hebrew, and immediate TTS interruption. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An Agent Cache System retains agent instances for 30 minutes per business+channel, boosting response times and preserving conversation state. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling.

Performance is optimized with explicit OpenAI timeouts, increased STT streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with `max_tokens=400` for `gpt-4o-mini` and a `temperature` of 0.15 for consistent tool usage and deterministic Hebrew. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation, confidence checks, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start is optimized with automatic service warmup.

## Technical Implementations
### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration.
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

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.