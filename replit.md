# Overview

AgentLocator is a Hebrew CRM system for real estate businesses that automates the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding.

# Recent Changes

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

### **Bug 3) App Crash - "Send queue full, dropping frame"**
- **Problem**: App crashed when TTS generated 606 frames (12s audio), queue overflowed
- **Root Cause**: TX queue too small (120 frames = 2.4s), back-pressure logic dropped frames
- **Solution**: Increased queue 120→800 frames (16s buffer), removed back-pressure continue
- **Files**: `server/media_ws_ai.py` (lines 346, 2547-2549, 2574-2575)
- **Benefits**: ✅ Supports long TTS (up to 16s) without drops or crashes

### **Bug 4) AI Reads Leads/Times Lists - Not Answering Questions**
- **Problem**: AI reads lead lists during calls, lists all times, doesn't answer simple questions
- **Root Cause**: `tool_choice="required"` forced tools EVERY turn, even for "where are you?"
- **Solution**: Changed to `tool_choice="auto"`, rewrote prompt (5000→1500 chars) with brevity rules
- **Files**: `server/agent_tools/agent_factory.py` (line 44), `business_settings.ai_prompt`
- **Benefits**: ✅ Natural conversation, uses tools only when needed, answers questions directly

### **Performance Optimization - Intent Router (Phase 2K)**
- **Problem**: AgentKit adds 1-1.5s latency to EVERY turn, even for simple info questions
- **Solution**: Intent-based routing - AgentKit ONLY for bookings, FAQ path for everything else
- **Architecture**:
  - **Intent Router**: Fast regex-based Hebrew intent detection (<10ms)
  - **AgentKit Gate**: Only runs for `book|reschedule|cancel` intents
  - **FAQ Handler**: Lightweight LLM call (80 tokens) for info questions (~800ms-1.2s)
  - **Environment Flags**: `AGENTKIT_BOOKING_ONLY=1`, `FAST_PATH_ENABLED=1`
- **Files**: `server/services/ai_service.py` (Intent Router, FAQ handler, Gate)
- **Benefits**: 
  - ✅ Info questions: ~1.0-1.5s (was 3-4s with AgentKit)
  - ✅ Booking flows: Still use AgentKit for reliability
  - ✅ Overall target: ≤2.3s for most conversations

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