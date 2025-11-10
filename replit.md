# Overview

AgentLocator is a Hebrew CRM system for real estate businesses that automates the sales pipeline with an AI-powered assistant. It processes calls in real-time, intelligently collects lead information, and schedules meetings using advanced audio processing for natural conversations. The system aims to enhance efficiency and sales conversion for real estate professionals through customizable AI assistants and business branding.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes (Phase 2O - November 10, 2025)

## Critical Latency Crisis Resolved - 40s → <3s Response Time

### Issue Discovered
User experienced 40-second response time after updating prompt:
- AI_PROCESSING: 19.8 seconds (Agent creation)
- Response: 82 words (instead of 2-3 sentences)
- TTS: 17.4 seconds
- Result: WebSocket crash ("Send queue full")

### Root Causes & Fixes

#### 1. **Legacy Agent Creation (CRITICAL)**
**Problem**: `ai_service.py` was using old `get_agent()` which bypassed singleton cache, creating new Agent instance every call with 19.8s OpenAI network overhead for 8 tool registrations.

**Fix** (`ai_service.py` line 911):
```python
# Before: agent = get_agent(...)  ❌
# After:
from server.agent_tools.agent_factory import get_or_create_agent
agent = get_or_create_agent(business_id, channel, business_name, custom_instructions)
```

**Result**: 
- Cache HIT: <100ms (agent already warmed)
- Cache MISS: <2s (new agent creation)
- Eliminates 19.8s cold starts

#### 2. **Long Responses Causing TTS Overload**
**Problem**: `max_tokens=400` allowed 82-word responses → 17.4s TTS → WebSocket crashes

**Fix** (`agent_factory.py` line 55):
```python
max_tokens=120  # 2-3 sentences only (was 400)
```

**Result**: TTS time reduced from 17.4s → <8s, prevents WebSocket backpressure

#### 3. **No Visibility into Performance**
**Problem**: Missing timing logs made debugging impossible

**Fix** (`agent_factory.py` line 118):
```python
agent_creation_time = (time.time() - agent_start) * 1000
print(f"⏱️  AGENT_CREATION_TIME: {agent_creation_time:.0f}ms")
if agent_creation_time > 2000:
    logger.warning(f"⚠️  SLOW AGENT CREATION: {agent_creation_time:.0f}ms > 2000ms!")
```

**Result**: Clear profiling data showing cache hits vs misses

#### 4. **FAQ Fast-Path Failures**
**Problem**: No diagnostic logging when FAQ failed, causing silent fallback to AgentKit

**Fix** (`ai_service.py` lines 724-833):
- Added fact extraction timing
- OpenAI call latency tracking
- Success/failure diagnostics with full error traces
- Guard-rail response detection

**Result**: Clear visibility into why FAQ succeeds/fails

#### 5. **Warmup Import Errors**
**Problem**: Multiple import issues in `lazy_services.py`:
- Wrong import: `from server.policy.business_policy import get_business_prompt` (doesn't exist)
- Missing import: `time` used before being imported
- Type error: `custom_instructions` could be None

**Fixes** (`lazy_services.py`):
```python
# Fixed imports
from server.models import Business, BusinessSettings
import time  # At start of _warmup()

# Fixed type safety
custom_instructions = ""  # Default empty string
if settings and settings.ai_prompt:
    prompts = json.loads(settings.ai_prompt)
    custom_instructions = prompts.get(channel, prompts.get('calls', '')) or ""
```

**Result**: Warmup runs successfully on startup

### Expected Performance After Fixes

| Scenario | Before | After |
|----------|--------|-------|
| **Info queries (FAQ fast-path)** | 40s | <3s ✅ |
| **Booking requests (after warmup)** | 19.8s | <3s ✅ |
| **First call after prompt update** | 19.8s | <5s ✅ |
| **Agent warmup on startup** | None | 4s (both channels) ✅ |

### Multi-Tenant Behavior

**Agent Cache**: Works for all business IDs automatically
- Each business gets its own cache entry: `(business_id, channel)`
- 30-minute TTL per agent
- Auto-invalidation on prompt updates

**Warmup**: Currently only business_id=1
- First call for new businesses: ~1-2s (cache miss, but fast)
- Subsequent calls: <100ms (cache hit)
- Acceptable tradeoff for faster startup

### Files Modified
1. `server/services/ai_service.py`: Singleton cache usage, FAQ logging
2. `server/agent_tools/agent_factory.py`: max_tokens reduction, timing logs
3. `server/services/lazy_services.py`: Import fixes, warmup logic

# System Architecture

## System Design Choices
AgentLocator employs a multi-tenant architecture with business-specific data isolation. It uses Twilio Media Streams (WebSockets for telephony and WhatsApp) for real-time communication, featuring smart barge-in, calibrated VAD for Hebrew, and immediate TTS interruption. Custom greetings are dynamically loaded.

The AI leverages an Agent SDK for tasks like appointment scheduling and lead creation, maintaining conversation memory. An **Agent Cache System retains agent instances for 30 minutes per business+channel**, boosting response times and preserving conversation state with **singleton pattern to eliminate 19.8s cold starts**. It mandates name and phone confirmation during scheduling, using dual input (verbal name, DTMF phone number) for streamlined 4-turn booking flows. Channel-aware responses adapt messaging based on the communication channel. A DTMF Menu System provides interactive voice navigation for phone calls with structured error handling.

Performance is optimized with explicit OpenAI timeouts, increased STT streaming timeouts, and warnings for long prompts. AI responses prioritize short, natural conversations with **`max_tokens=120`** for `gpt-4o-mini` and a `temperature` of 0.15 for consistent tool usage and deterministic Hebrew. Prompts are loaded exclusively from `BusinessSettings.ai_prompt` without hardcoded text (except minimal date context). Robustness is ensured via thread tracking, enhanced cleanup, and a Flask app singleton. STT reliability benefits from relaxed validation, confidence checks, and a 3-attempt retry. Voice consistency is maintained with a male Hebrew voice (`he-IL-Wavenet-D`) and masculine phrasing. Cold start is optimized with automatic service warmup.

## Technical Implementations
### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **Real-time**: Starlette-based native WebSocket handling, Uvicorn ASGI server.
- **Database**: PostgreSQL (production), SQLite (development).
- **Authentication**: JWT-based with role-based access control and SeaSurf CSRF protection.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts.
- **Agent Cache**: Thread-safe singleton cache for Agent SDK instances with auto-expiration and warmup.
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
- **FAQ Fast-Path**: <1.5s responses for info queries using optimized LLM with fact extraction.

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations and FAQ responses.
- **Google Cloud Platform**:
  - **STT**: Streaming API v1 for Hebrew speech recognition.
  - **TTS**: WaveNet-D voice with telephony profile, SSML support, and smart Hebrew pronunciation.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.
