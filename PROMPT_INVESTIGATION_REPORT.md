# 🔍 INVESTIGATION REPORT: Prompt Not Updating / Old Prompt Being Sent

**Date:** 2026-01-08  
**Repository:** carhubcentralts-hue/prosaasil  
**Investigation Type:** Deep Analysis (No Fixes)  
**Languages:** Python (Flask), OpenAI Realtime API  

---

## 📋 EXECUTIVE SUMMARY

This document provides a comprehensive analysis of the prompt caching and session management system to investigate the reported issue: "Updated prompts (inbound/outbound) are not taking effect, old prompts continue to be used even 10+ minutes after update."

**Key Finding:** The system has **TWO SEPARATE CACHE SYSTEMS** that must BOTH be invalidated:
1. AIService cache (in-memory dict)
2. PromptCache (in-memory singleton with direction-based keys)

---

## 1. FLOW MAP: How Prompts Travel from DB to OpenAI

### 1.1 INBOUND CALL FLOW

```
┌─────────────────┐
│ User Updates    │
│ Prompt in CRM   │ 
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ /api/admin/businesses/<id>/prompt [PUT]                     │
│ File: server/routes_ai_prompt.py:129                        │
│ Updates: settings.ai_prompt or settings.outbound_ai_prompt  │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ 🔥 CRITICAL: invalidate_business_cache(business_id)         │
│ File: server/routes_ai_prompt.py:248                        │
│ Clears: AIService._cache keys (business_{id}_{channel})     │
│ ❌ MISSING: Does NOT invalidate PromptCache!                │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Next Call Arrives → Twilio Webhook                          │
│ File: server/media_ws_ai.py                                 │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ build_realtime_system_prompt()                              │
│ File: server/services/realtime_prompt_builder.py:1240       │
│ Checks: PromptCache.get(business_id, direction="inbound")   │
│ 🚨 PROBLEM: Returns CACHED prompt (TTL=600s = 10 minutes)  │
└────────┬───────────────────────────────────────────────────┘
         │ Cache MISS? (only if expired or invalidated)
         ▼
┌─────────────────────────────────────────────────────────────┐
│ build_inbound_system_prompt()                               │
│ File: server/services/realtime_prompt_builder.py:1460       │
│ Reads: Business.query.get() → settings.ai_prompt            │
│ Builds: FULL prompt (system + business + appointment)       │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ PromptCache.set(business_id, prompt, direction="inbound")   │
│ File: server/services/prompt_cache.py:80                    │
│ TTL: 600 seconds (10 minutes)                               │
│ Key format: f"{business_id}:inbound"                        │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ _send_session_config() → session.update                     │
│ File: server/media_ws_ai.py:3023                            │
│ Sends: instructions=sanitized_prompt to OpenAI              │
│ Event: session.update → session.updated confirmation        │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ OpenAI Realtime Session Active                              │
│ Instructions: LOCKED for this session (no mid-call update)  │
│ response.create: Uses instructions from session.update      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 OUTBOUND CALL FLOW

```
Same as inbound, but:
- Direction: "outbound"
- Source field: settings.outbound_ai_prompt
- Function: build_outbound_system_prompt()
- Cache key: f"{business_id}:outbound"
```

---

## 2. PROMPT SOURCES: Database Fields & Fallbacks

### 2.1 Database Schema

**Table: `business_settings`**
```sql
tenant_id (FK → business.id)
ai_prompt TEXT  -- Inbound prompt (can be JSON with 'calls' and 'whatsapp')
outbound_ai_prompt TEXT  -- Outbound-specific prompt
updated_at TIMESTAMP
updated_by VARCHAR
```

**Table: `business`**
```sql
id INTEGER PRIMARY KEY
name VARCHAR
system_prompt TEXT  -- Legacy fallback
greeting_message TEXT  -- Greeting text
```

### 2.2 Prompt Selection Rules

**INBOUND CALL:**
```python
# File: server/services/realtime_prompt_builder.py:1488
ai_prompt_raw = settings.ai_prompt if settings else ""

# Fallback chain (Tier 1 → 2 → 3 → 4):
1. settings.ai_prompt (primary)
2. settings.outbound_ai_prompt (if inbound missing)
3. business.system_prompt (legacy)
4. FALLBACK_INBOUND_PROMPT_TEMPLATE (hardcoded)
```

**OUTBOUND CALL:**
```python
# File: server/services/realtime_prompt_builder.py:1625
outbound_prompt_raw = settings.outbound_ai_prompt if settings else ""

# Fallback chain:
1. settings.outbound_ai_prompt (primary)
2. settings.ai_prompt (if outbound missing)  ← 🚨 Can cause confusion!
3. FALLBACK_OUTBOUND_PROMPT_TEMPLATE (hardcoded)
```

### 2.3 JSON Format Support

Prompts can be stored as:
```json
{
  "calls": "Prompt for phone calls",
  "whatsapp": "Prompt for WhatsApp"
}
```

Extraction logic:
```python
# File: server/services/realtime_prompt_builder.py:1074
if ai_prompt_raw.startswith('{'):
    prompt_obj = json.loads(ai_prompt_raw)
    ai_prompt_text = prompt_obj.get("calls") or prompt_obj.get("whatsapp") or raw_prompt
```

---

## 3. CACHE INVENTORY: All Caching Mechanisms

### 3.1 PromptCache (PRIMARY CACHE)

**Location:** `server/services/prompt_cache.py`

**Type:** In-memory singleton (thread-safe)

**Cache Key Format:**
```python
f"{business_id}:{direction}"
# Examples:
# "123:inbound"
# "123:outbound"
```

**Cached Data Structure:**
```python
@dataclass
class CachedPrompt:
    business_id: int
    direction: str  # 'inbound' or 'outbound'
    system_prompt: str
    greeting_text: str
    language_config: Dict[str, Any]
    cached_at: float
```

**TTL:** 600 seconds (10 minutes)

**Read Operation:**
```python
# File: server/services/prompt_cache.py:51
cache_key = f"{business_id}:{direction}"
entry = self._cache.get(cache_key)
if entry and not entry.is_expired():
    return entry  # Cache hit
return None  # Cache miss
```

**Write Operation:**
```python
# File: server/services/prompt_cache.py:80
cache_key = f"{business_id}:{direction}"
entry = CachedPrompt(
    business_id=business_id,
    direction=direction,
    system_prompt=system_prompt,
    greeting_text=greeting_text,
    language_config=language_config or {},
    cached_at=time.time()
)
self._cache[cache_key] = entry
```

**Invalidation:**
```python
# File: server/services/prompt_cache.py:105
def invalidate(self, business_id: int, direction: Optional[str] = None):
    if direction:
        # Invalidate specific direction
        cache_key = f"{business_id}:{direction}"
        if cache_key in self._cache:
            del self._cache[cache_key]
    else:
        # Invalidate both directions
        for dir_name in ["inbound", "outbound"]:
            cache_key = f"{business_id}:{dir_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
```

**🚨 CRITICAL FINDING:** This cache is **NOT automatically invalidated** when prompts are updated via the API!

### 3.2 AIService._cache (SECONDARY CACHE)

**Location:** `server/services/ai_service.py:286`

**Type:** Instance dictionary (shared via singleton)

**Cache Key Format:**
```python
f"business_{business_id}_{channel}"
# Examples:
# "business_123_calls"
# "business_123_whatsapp"
```

**Cached Data:**
```python
{
    "prompt": "...",
    "temperature": 0.7,
    # ... other AI config
}
```

**TTL:** 300 seconds (5 minutes)

**Invalidation:**
```python
# File: server/services/ai_service.py:255
def invalidate_business_cache(business_id: int):
    service = get_ai_service()
    cache_keys_to_remove = [
        f"business_{business_id}_calls",
        f"business_{business_id}_whatsapp"
    ]
    for key in cache_keys_to_remove:
        if key in service._cache:
            del service._cache[key]
```

**✅ This cache IS invalidated** when prompts are updated (line 248 in routes_ai_prompt.py).

### 3.3 OpenAI Session State (NOT A CACHE - SESSION-BOUND)

**Location:** OpenAI Realtime API websocket session

**Lifecycle:** Per-call (new session for each call)

**Instructions Setting:**
```python
# File: server/media_ws_ai.py:3087
await client.configure_session(
    instructions=greeting_prompt,  # ← Set once at call start
    voice=call_voice,
    input_audio_format="g711_ulaw",
    output_audio_format="g711_ulaw",
    # ... other config
)
```

**Event Flow:**
```
session.update (client → OpenAI)
   ↓
session.updated (OpenAI → client)
   ↓
Instructions locked for this session
   ↓
response.create uses these instructions
```

**⚠️ IMPORTANT:** 
- Instructions are **per-session**, not global
- New call = new session = fresh instructions
- No way to update instructions mid-call (by design)

### 3.4 Redis Cache

**Status:** ❌ NOT FOUND

No Redis usage detected in the codebase for prompt caching.

### 3.5 Database Query Caching

**Status:** ❌ NOT DETECTED

SQLAlchemy queries are executed fresh each time (no query-level caching detected).

---

## 4. SESSION UPDATE / ORDERING AUDIT

### 4.1 Session Configuration Lifecycle

```
┌──────────────────────┐
│ WebSocket Connect    │
│ (Twilio → Server)    │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Start RX Loop BEFORE session.update            │
│ File: media_ws_ai.py:3705-3726                          │
│ Purpose: Prevent event loss (listen before sending)     │
│ Wait: Max 2s for recv_loop_started flag                 │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Build Full Prompt                               │
│ File: media_ws_ai.py:3554-3641                          │
│ Source: stream_registry (prebuilt by webhook)           │
│ OR: build_realtime_system_prompt() if not prebuilt      │
│ Includes: System + Business + Appointment rules         │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Clear Session Flags                             │
│ File: media_ws_ai.py:3730-3735                          │
│ _session_config_confirmed = False                       │
│ _session_config_failed = False                          │
│ _session_config_event.clear()                           │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Send session.update                             │
│ File: media_ws_ai.py:3737                               │
│ Event: {"type": "session.update", "session": {...}}     │
│ Contains: instructions, voice, audio format, tools      │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Wait for session.updated (Event-Driven)         │
│ File: media_ws_ai.py:3746-3795                          │
│ Max wait: 8 seconds (with retry at 3s)                  │
│ Uses: asyncio.Event() for instant wake-up               │
│ Retry: If no response in 3s, resend with force=True     │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ session.updated Received                                 │
│ File: media_ws_ai.py:5410-5497                          │
│ Validates: audio format, voice, instructions            │
│ Sets: _session_config_confirmed = True                  │
│ Sets: _session_config_event.set()                       │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ response.create (Greeting)                               │
│ File: media_ws_ai.py:4029                               │
│ 🔥 GATE: Blocked until _session_config_confirmed=True   │
│ Uses: Instructions from session.update                   │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│ Conversation Loop                                        │
│ All response.create calls use session instructions      │
│ No mid-call instruction updates possible                 │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Critical Ordering Rules

**✅ CORRECT ORDER (Always Enforced):**
```
1. Start recv_events() listener
2. Build full prompt from cache/DB
3. Send session.update(instructions=prompt)
4. Wait for session.updated confirmation
5. Trigger response.create (greeting)
```

**❌ NEVER HAPPENS (Prevented by Gates):**
```
response.create BEFORE session.updated
→ Would cause: Default settings (English, PCM16, no instructions)
→ Prevention: Line 4636-4655 in media_ws_ai.py
```

### 4.3 Deduplication Logic

**Hash-Based Deduplication:**
```python
# File: server/services/openai_realtime_client.py (referenced)
# Prevents duplicate session.update if instructions unchanged
_last_instructions_hash = hashlib.md5(instructions.encode()).hexdigest()
if hash == _last_instructions_hash and not force:
    return True  # Skip send (already configured)
```

**Force Flag:**
```python
# Used when retrying after timeout (line 3772)
await _send_session_config(..., force=True)
# Bypasses hash check to ensure update is sent
```

---

## 5. TENANT ISOLATION AUDIT

### 5.1 Tenant Selection Logic

**Inbound Calls (from Twilio):**
```python
# File: server/routes_twilio.py (webhook handling)
# Twilio → /twiml/incoming/<tenant>
# tenant is extracted from URL path
tenant_id = request.view_args.get('tenant')
business = Business.query.filter_by(id=tenant_id).first()
```

**Outbound Calls:**
```python
# File: server/media_ws_ai.py:9592
# business_id is passed in custom_parameters
self.outbound_business_id = evt.get("business_id")
```

### 5.2 Tenant Passing Through Layers

```
Twilio Webhook (tenant in URL)
   ↓
WebSocket Connection (business_id in g.tenant or custom_parameters)
   ↓
MediaStreamHandler.__init__(business_id=X)
   ↓
build_realtime_system_prompt(business_id=X)
   ↓
PromptCache.get(business_id=X, direction=...)
```

### 5.3 Cross-Contamination Prevention

**Business Isolation Logging:**
```python
# File: realtime_prompt_builder.py:1292
logger.info(f"[BUSINESS_ISOLATION] prompt_request business_id={business_id} direction={call_direction}")

# File: realtime_prompt_builder.py:1337
logger.info(f"[BUSINESS_ISOLATION] prompt_built business_id={business_id} contains_business_name={business_name in final_prompt}")
```

**Potential Issues:**
1. ❌ **Global singleton cache** could theoretically serve wrong business if:
   - Key collision (unlikely with f"{id}:{direction}" format)
   - Race condition in cache write (mitigated by RLock)
   
2. ✅ **Session state is per-call** (no cross-contamination possible)

3. ✅ **Database queries always include business_id** filter

### 5.4 Suspected Issues

**HYPOTHESIS:** If `business_id` is None or 0:
```python
# Would create cache key: "None:inbound" or "0:inbound"
# Could be shared across all calls with missing business_id!
```

**CHECK NEEDED:** Log analysis to verify business_id is always set correctly.

---

## 6. SUGGESTED LOGS: Diagnostic Instrumentation

### 6.1 Prompt Loading & Hashing

**Location A: Before Cache Check**
```python
# File: server/services/realtime_prompt_builder.py
# Line: ~1260 (inside build_realtime_system_prompt)

# ADD THIS:
import hashlib
logger.info(
    f"[PROMPT_LOAD] business_id={business_id}, direction={call_direction}, "
    f"use_cache={use_cache}, timestamp={datetime.now().isoformat()}"
)
```

**Location B: Cache Hit**
```python
# File: server/services/prompt_cache.py
# Line: ~74 (inside get() method, cache hit branch)

# ADD THIS:
prompt_hash = hashlib.md5(entry.system_prompt.encode()).hexdigest()[:12]
cached_age_sec = time.time() - entry.cached_at
logger.info(
    f"[PROMPT_CACHE_HIT] business_id={business_id}, direction={direction}, "
    f"prompt_hash={prompt_hash}, cached_age_sec={cached_age_sec:.1f}, "
    f"prompt_len={len(entry.system_prompt)}"
)
```

**Location C: Cache Miss → DB Read**
```python
# File: server/services/realtime_prompt_builder.py
# Line: ~1488 (in build_inbound_system_prompt, after reading from DB)

# ADD THIS:
import hashlib
prompt_hash = hashlib.md5(business_prompt.encode()).hexdigest()[:12]
settings_updated_at = settings.updated_at.isoformat() if settings and settings.updated_at else "unknown"
logger.info(
    f"[PROMPT_DB_READ] business_id={business_id}, direction=inbound, "
    f"prompt_hash={prompt_hash}, prompt_len={len(business_prompt)}, "
    f"db_updated_at={settings_updated_at}, source=settings.ai_prompt"
)
```

**Location D: Cache Write**
```python
# File: server/services/prompt_cache.py
# Line: ~103 (after setting cache entry)

# ADD THIS:
prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()[:12]
logger.info(
    f"[PROMPT_CACHE_SET] business_id={business_id}, direction={direction}, "
    f"prompt_hash={prompt_hash}, prompt_len={len(system_prompt)}, "
    f"ttl_sec={CACHE_TTL_SECONDS}"
)
```

### 6.2 Session Update Tracking

**Location E: Before session.update**
```python
# File: server/media_ws_ai.py
# Line: ~3737 (before await _send_session_config)

# ADD THIS:
prompt_hash = hashlib.md5(greeting_prompt.encode()).hexdigest()[:12]
logger.info(
    f"[SESSION_UPDATE_SEND] call_sid={self.call_sid[:12]}, business_id={self.business_id}, "
    f"direction={self.call_direction}, prompt_hash={prompt_hash}, "
    f"instructions_len={len(greeting_prompt)}, attempt=initial"
)
```

**Location F: session.updated confirmation**
```python
# File: server/media_ws_ai.py
# Line: ~5495 (inside session.updated event handler)

# ADD THIS:
instructions_received = session_data.get("instructions", "")
received_hash = hashlib.md5(instructions_received.encode()).hexdigest()[:12]
expected_hash = getattr(self, '_business_prompt_hash', 'unknown')
logger.info(
    f"[SESSION_UPDATED] call_sid={self.call_sid[:12]}, business_id={self.business_id}, "
    f"received_hash={received_hash}, expected_hash={expected_hash}, "
    f"hash_match={received_hash == expected_hash}, instructions_len={len(instructions_received)}"
)
```

### 6.3 Cache Invalidation Tracking

**Location G: API Update Endpoint**
```python
# File: server/routes_ai_prompt.py
# Line: ~248 (after calling invalidate_business_cache)

# ADD THIS:
logger.info(
    f"[PROMPT_UPDATE_API] business_id={business_id}, updated_by={user_id}, "
    f"timestamp={datetime.utcnow().isoformat()}, "
    f"inbound_len={len(calls_prompt) if calls_prompt else 0}, "
    f"outbound_len={len(outbound_calls_prompt) if outbound_calls_prompt else 0}"
)
```

**Location H: AIService Cache Invalidation**
```python
# File: server/services/ai_service.py
# Line: ~268 (after del self._cache[key])

# ALREADY EXISTS (good)
# Just verify it's working:
logger.info(f"✅ AIService cache invalidated: {key}")
```

**Location I: PromptCache Invalidation (MISSING!)**
```python
# File: server/routes_ai_prompt.py
# Line: ~250 (ADD THIS AFTER invalidate_business_cache call)

# ADD THIS NEW CODE:
try:
    from server.services.prompt_cache import get_prompt_cache
    cache = get_prompt_cache()
    cache.invalidate(business_id)  # Invalidates both inbound and outbound
    logger.info(f"✅ PromptCache invalidated for business {business_id} (both directions)")
except Exception as e:
    logger.error(f"❌ Failed to invalidate PromptCache: {e}")
```

### 6.4 Tenant Context Verification

**Location J: WebSocket Connection Start**
```python
# File: server/media_ws_ai.py
# Line: ~9527 (in handle() method, after business_id is set)

# ADD THIS:
logger.info(
    f"[WS_CONNECT] call_sid={self.call_sid}, business_id={self.business_id}, "
    f"call_direction={self.call_direction}, phone={self.phone_number}"
)
```

---

## 7. TOP 5 HYPOTHESES (Ordered by Probability)

### 🥇 HYPOTHESIS #1: PromptCache Not Invalidated on Update (HIGH PROBABILITY)

**Evidence:**
1. ✅ `PromptCache` exists with 10-minute TTL (prompt_cache.py:14)
2. ✅ `PromptCache.invalidate()` method exists (prompt_cache.py:105)
3. ❌ `invalidate_business_cache()` does NOT call `PromptCache.invalidate()` (ai_service.py:255-275)
4. ✅ API route DOES call `invalidate_business_cache()` (routes_ai_prompt.py:248)
5. ❌ **MISSING:** Call to `get_prompt_cache().invalidate(business_id)`

**Root Cause:**
```python
# File: server/services/ai_service.py:255
def invalidate_business_cache(business_id: int):
    # ✅ Clears AIService._cache
    # ❌ Does NOT clear PromptCache!
```

**Expected Behavior:**
```python
def invalidate_business_cache(business_id: int):
    # 1. Clear AIService cache
    service = get_ai_service()
    # ... existing code ...
    
    # 2. Clear PromptCache (MISSING!)
    from server.services.prompt_cache import get_prompt_cache
    cache = get_prompt_cache()
    cache.invalidate(business_id)  # Clears both inbound and outbound
```

**Timeline:**
```
T=0:    User updates prompt in CRM
T=0.1:  API invalidates AIService._cache only
T=0.2:  New call arrives
T=0.3:  build_realtime_system_prompt() checks PromptCache
T=0.4:  PromptCache returns OLD prompt (still cached, TTL not expired)
T=600:  PromptCache TTL expires → next call gets new prompt
```

**Verification:**
- Add log at Location I (section 6.3)
- Monitor if PromptCache invalidation is called on prompt update
- Check cache age in logs (should reset to 0 after update)

---

### 🥈 HYPOTHESIS #2: Direction Mismatch in Cache Key (MEDIUM PROBABILITY)

**Evidence:**
1. ✅ Cache key format: `f"{business_id}:{direction}"` (prompt_cache.py:48)
2. ✅ Two directions: "inbound" and "outbound"
3. ⚠️ If direction is wrong/missing, could serve wrong cached prompt
4. ⚠️ Fallback chain can cause cross-contamination (inbound → outbound or vice versa)

**Root Cause:**
```python
# File: realtime_prompt_builder.py:1129
# INBOUND prompt selection:
ai_prompt_raw = settings.ai_prompt if (settings and settings.ai_prompt) else ""

# If empty, falls back to:
if call_direction == "outbound" and settings and settings.ai_prompt:
    logger.warning(f"[PROMPT FALLBACK] Using inbound prompt for outbound...")
    return settings.ai_prompt  # ← WRONG prompt for wrong direction!
```

**Scenario:**
```
1. User updates outbound_ai_prompt only
2. Inbound prompt (ai_prompt) is empty
3. Next inbound call tries to load ai_prompt
4. Fallback uses outbound_ai_prompt instead
5. PromptCache stores this as "inbound" → WRONG!
6. All inbound calls now use outbound prompt
```

**Verification:**
- Add direction field to all logs (Locations A-F)
- Check if "PROMPT FALLBACK" warnings appear in logs
- Verify cache key always matches actual call direction

---

### 🥉 HYPOTHESIS #3: Stale Prompt from stream_registry (MEDIUM PROBABILITY)

**Evidence:**
1. ✅ Prompts are pre-built in webhook and stored in `stream_registry` (media_ws_ai.py:3554)
2. ⚠️ If webhook re-uses old registry entry, prompt could be stale
3. ⚠️ No TTL or invalidation detected for stream_registry

**Root Cause:**
```python
# File: media_ws_ai.py:3554-3575
from server.stream_state import stream_registry

pre_computed = stream_registry.get_prompt_for_call(self.call_sid)
if pre_computed:
    greeting_prompt = pre_computed
    # Uses pre-built prompt from webhook
else:
    # Builds fresh prompt
    greeting_prompt = build_realtime_system_prompt(...)
```

**Scenario:**
```
1. Webhook receives call → pre-builds prompt → stores in stream_registry
2. User updates prompt in CRM
3. Call starts (before webhook timeout) → uses OLD prompt from registry
```

**Verification:**
- Check if `stream_registry.get_prompt_for_call()` is returning non-None
- Add log before `if pre_computed:` with prompt hash
- Compare registry prompt hash vs fresh-built prompt hash

**Fix Strategy:**
- Invalidate stream_registry on prompt update
- OR: Skip registry and always build fresh (safer but slower)

---

### 🏅 HYPOTHESIS #4: Session Reuse Between Calls (LOW PROBABILITY)

**Evidence:**
1. ✅ Code shows fresh session for each call (media_ws_ai.py:3153)
2. ❌ No session pooling or reuse detected
3. ✅ WebSocket is per-call (closed after call ends)

**Why Low Probability:**
```python
# Each call creates new OpenAI Realtime client
await asyncio.wait_for(client.connect(max_retries=3, backoff_base=0.5), timeout=8.0)
# New session.update is sent for each connection
# No session ID reuse detected
```

**Verification:**
- Check logs for multiple `session.created` events with same session_id
- Should see unique session_id for each call

---

### 🎖️ HYPOTHESIS #5: Tenant ID Leak (LOW PROBABILITY)

**Evidence:**
1. ✅ Cache keys include business_id (good isolation)
2. ❌ No evidence of global state leaking business_id
3. ✅ Each MediaStreamHandler has its own self.business_id

**Potential Issue:**
```python
# If business_id is None or 0:
cache_key = f"{None}:inbound"  # All calls with None share this!
```

**Scenario:**
```
1. Call A (business 123) sets cache: "123:inbound"
2. Call B (business 456, but business_id=None due to bug)
3. Call B cache key becomes "None:inbound"
4. All future calls with business_id=None share this cache
```

**Verification:**
- Add log at Location J with business_id value
- Check for calls with business_id=None or 0
- Grep logs for cache_key="None:" or cache_key="0:"

---

## 8. VERIFICATION SCRIPTS (Proposed)

### 8.1 Cache State Inspector

```python
# File: /tmp/inspect_cache_state.py
"""
Run this script to inspect current cache state without modifying anything.
"""
import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from server.services.prompt_cache import get_prompt_cache
from server.services.ai_service import get_ai_service
import time

def inspect_caches(business_id):
    print(f"\n🔍 Inspecting Caches for Business {business_id}")
    print("=" * 60)
    
    # 1. PromptCache
    cache = get_prompt_cache()
    for direction in ["inbound", "outbound"]:
        entry = cache.get(business_id, direction=direction)
        if entry:
            age = time.time() - entry.cached_at
            import hashlib
            prompt_hash = hashlib.md5(entry.system_prompt.encode()).hexdigest()[:12]
            print(f"\n📦 PromptCache ({direction}):")
            print(f"  ✅ EXISTS")
            print(f"  Age: {age:.1f}s (TTL: 600s)")
            print(f"  Hash: {prompt_hash}")
            print(f"  Length: {len(entry.system_prompt)} chars")
        else:
            print(f"\n📦 PromptCache ({direction}):")
            print(f"  ❌ NOT CACHED")
    
    # 2. AIService Cache
    service = get_ai_service()
    for channel in ["calls", "whatsapp"]:
        key = f"business_{business_id}_{channel}"
        if key in service._cache:
            data, timestamp = service._cache[key]
            age = time.time() - timestamp
            print(f"\n📦 AIService._cache ({channel}):")
            print(f"  ✅ EXISTS")
            print(f"  Age: {age:.1f}s (TTL: 300s)")
        else:
            print(f"\n📦 AIService._cache ({channel}):")
            print(f"  ❌ NOT CACHED")
    
    # 3. Database State
    from server.models_sql import Business, BusinessSettings, db
    from server.app_factory import create_app
    
    app = create_app()
    with app.app_context():
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if settings:
            import hashlib
            inbound_hash = hashlib.md5((settings.ai_prompt or "").encode()).hexdigest()[:12]
            outbound_hash = hashlib.md5((settings.outbound_ai_prompt or "").encode()).hexdigest()[:12]
            print(f"\n💾 Database:")
            print(f"  Inbound Hash: {inbound_hash}")
            print(f"  Outbound Hash: {outbound_hash}")
            print(f"  Updated At: {settings.updated_at}")
        else:
            print(f"\n💾 Database:")
            print(f"  ❌ No settings found")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_cache_state.py <business_id>")
        sys.exit(1)
    
    business_id = int(sys.argv[1])
    inspect_caches(business_id)
```

### 8.2 Cache Invalidation Tester

```python
# File: /tmp/test_cache_invalidation.py
"""
Test if cache invalidation works correctly.
"""
import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from server.services.prompt_cache import get_prompt_cache
from server.services.ai_service import invalidate_business_cache

def test_invalidation(business_id):
    print(f"\n🧪 Testing Cache Invalidation for Business {business_id}")
    print("=" * 60)
    
    cache = get_prompt_cache()
    
    # Check initial state
    print("\n1️⃣ Checking initial cache state...")
    for direction in ["inbound", "outbound"]:
        entry = cache.get(business_id, direction=direction)
        status = "CACHED" if entry else "EMPTY"
        print(f"  {direction}: {status}")
    
    # Call invalidation
    print("\n2️⃣ Calling invalidate_business_cache()...")
    invalidate_business_cache(business_id)
    
    # Check AIService cache (should be cleared)
    from server.services.ai_service import get_ai_service
    service = get_ai_service()
    print("\n3️⃣ AIService Cache After Invalidation:")
    for channel in ["calls", "whatsapp"]:
        key = f"business_{business_id}_{channel}"
        status = "CACHED" if key in service._cache else "CLEARED"
        print(f"  {channel}: {status}")
    
    # Check PromptCache (PROBLEM: NOT cleared!)
    print("\n4️⃣ PromptCache After Invalidation:")
    for direction in ["inbound", "outbound"]:
        entry = cache.get(business_id, direction=direction)
        status = "CACHED" if entry else "CLEARED"
        result = "❌ PROBLEM" if entry else "✅ OK"
        print(f"  {direction}: {status} {result}")
    
    # Test manual PromptCache invalidation
    print("\n5️⃣ Manual PromptCache Invalidation Test...")
    cache.invalidate(business_id)
    for direction in ["inbound", "outbound"]:
        entry = cache.get(business_id, direction=direction)
        status = "CACHED" if entry else "CLEARED"
        result = "✅ OK" if not entry else "❌ STILL CACHED"
        print(f"  {direction}: {status} {result}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_cache_invalidation.py <business_id>")
        sys.exit(1)
    
    business_id = int(sys.argv[1])
    test_invalidation(business_id)
```

---

## 9. SUMMARY & ACTION ITEMS

### 9.1 Confirmed Issues

1. **✅ CONFIRMED:** PromptCache is NOT invalidated when prompts are updated
   - Severity: HIGH
   - Impact: Users see old prompts for up to 10 minutes
   - Fix: Add `cache.invalidate(business_id)` to `invalidate_business_cache()`

2. **⚠️ POTENTIAL:** Direction fallback can cause wrong prompt to be cached
   - Severity: MEDIUM
   - Impact: Inbound calls might use outbound prompts (or vice versa)
   - Fix: Improve fallback logging + validation

3. **⚠️ POTENTIAL:** stream_registry might serve stale prompts
   - Severity: LOW-MEDIUM
   - Impact: First few seconds of call might use old prompt
   - Fix: Invalidate registry on prompt update OR skip registry

### 9.2 Recommended Logging

**Priority 1 (MUST HAVE):**
- Location B: Cache Hit (with hash + age)
- Location C: DB Read (with hash + updated_at)
- Location E: Session Update Send (with hash)
- Location F: Session Updated (with hash match verification)

**Priority 2 (SHOULD HAVE):**
- Location A: Prompt Load Start
- Location D: Cache Write
- Location G: API Update
- Location I: PromptCache Invalidation (NEW CODE NEEDED!)

**Priority 3 (NICE TO HAVE):**
- Location H: AIService Invalidation
- Location J: WS Connect

### 9.3 Root Cause Analysis

**Primary Root Cause:**
```
invalidate_business_cache() only clears AIService._cache,
but does NOT clear PromptCache (10-minute TTL).

Result: New prompts are in DB, but old prompts are served from cache.
```

**Secondary Root Cause:**
```
No logging of prompt hashes makes it impossible to verify
which version of the prompt is being used for each call.
```

### 9.4 Fix Priority

**P0 (Critical - Fix Immediately):**
```python
# File: server/services/ai_service.py
def invalidate_business_cache(business_id: int):
    # ... existing AIService cache clear ...
    
    # ADD THIS:
    try:
        from server.services.prompt_cache import get_prompt_cache
        cache = get_prompt_cache()
        cache.invalidate(business_id)
        logger.info(f"✅ PromptCache invalidated for business {business_id}")
    except Exception as e:
        logger.error(f"❌ Failed to invalidate PromptCache: {e}")
```

**P1 (High - Add Logging):**
- Add Locations B, C, E, F from section 6
- Enables debugging of future issues

**P2 (Medium - Improve Validation):**
- Add direction validation in fallback chain
- Warn if wrong direction prompt is used
- Add cache key validation (reject None/0 business_id)

---

## 10. CONCLUSION

The investigation reveals a **dual-cache system** where:
1. **AIService._cache** is correctly invalidated on prompt updates
2. **PromptCache** is NOT invalidated, causing stale prompts for 10 minutes

The fix is straightforward: add PromptCache invalidation to the existing invalidation function.

**Confidence Level:** HIGH (95%)

**Verification Method:**
1. Run test script to confirm PromptCache is not invalidated
2. Apply fix (one line of code)
3. Run test again to confirm both caches are cleared
4. Monitor logs for prompt hash changes after update

---

## APPENDIX A: File Location Quick Reference

| Component | File Path | Line Numbers |
|-----------|-----------|--------------|
| PromptCache | `server/services/prompt_cache.py` | 1-170 |
| build_realtime_system_prompt | `server/services/realtime_prompt_builder.py` | 1240-1360 |
| build_inbound_system_prompt | `server/services/realtime_prompt_builder.py` | 1460-1596 |
| build_outbound_system_prompt | `server/services/realtime_prompt_builder.py` | 1599-1699 |
| invalidate_business_cache | `server/services/ai_service.py` | 255-275 |
| API update endpoint | `server/routes_ai_prompt.py` | 129-273 |
| session.update send | `server/media_ws_ai.py` | 3023-3107 |
| session.updated handler | `server/media_ws_ai.py` | 5410-5497 |

---

**END OF INVESTIGATION REPORT**

*This report contains no fixes - only analysis, findings, and recommendations.*
