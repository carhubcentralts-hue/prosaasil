# Single Source of Truth (SSOT) Architecture
**Date**: 2025-12-28
**Purpose**: Define clear ownership and responsibilities for all system components

---

## 🎯 Core Principle

> **"If two parts of the system think they are responsible for the same thing — that is a bug, even if nothing crashes."**

Every piece of data, every decision, every action must have **exactly one owner** and **one canonical source**.

---

## 📋 SSOT Ownership Map

### 1. Call State Management

#### Owner: `CallLog` Database Model
- **File**: `server/models_sql.py`
- **Fields**: 
  - `status` - Current call status (SSOT)
  - ~~`call_status`~~ - DEPRECATED, kept for DB compatibility only
  - `direction` - Normalized direction (inbound/outbound)
  - `twilio_direction` - Raw Twilio direction (for audit)

#### Updaters (with specific responsibilities):
1. **Twilio Webhooks** (`routes_twilio.py`):
   - ✅ PRIMARY OWNER of status updates
   - ✅ Updates: `status`, `duration`, `direction`
   - ✅ Triggered by: Twilio status callbacks
   - ❌ NEVER: Update conversation content

2. **Realtime WebSocket** (`media_ws_ai.py`):
   - ✅ Creates initial CallLog if needed
   - ✅ Stores conversation turns (ConversationTurn table)
   - ❌ NEVER: Update call status after creation
   - ❌ NEVER: Compete with webhook for status

3. **Recording Worker** (`tasks_recording.py`):
   - ✅ Appends post-call data ONLY
   - ✅ Updates: `final_transcript`, `recording_url`, `audio_bytes_len`, `transcript_source`
   - ❌ NEVER: Update status or duration
   - ❌ NEVER: Touch active calls

#### State Machine:
```
initiated → ringing → in-progress → completed
                   ↘ busy
                   ↘ no-answer
                   ↘ failed
```

#### Atomic Update Rule:
- All status updates MUST use DB transactions
- No race conditions allowed
- Use optimistic locking if needed

---

### 2. Prompt Building

#### Owner: `realtime_prompt_builder.py`
- **File**: `server/services/realtime_prompt_builder.py`
- **Function**: `build_realtime_system_prompt()` - SINGLE ENTRY POINT

#### Components:
1. **System Prompt** - Behavior rules ONLY
   - `build_inbound_system_prompt()` - Inbound calls
   - `build_outbound_system_prompt()` - Outbound calls
   
2. **Business Prompt** - Business content ONLY
   - `build_full_business_prompt()` - Full business context
   - `build_compact_business_instructions()` - Compact version

3. **Greeting Prompt** - Fast greeting
   - `build_compact_greeting_prompt()` - Minimal greeting
   - `get_greeting_prompt_fast()` - Cached version

#### Cache Layer:
- **File**: `server/services/prompt_cache.py`
- **Class**: `PromptCache`
- **Key Format**: `{business_id}_{call_direction}_{prompt_type}`
- **TTL**: Configurable (default: 300 seconds)

#### ❌ DEPRECATED (DO NOT USE):
- ~~`ai_service.py:get_business_prompt()`~~ - Use realtime_prompt_builder instead
- ~~`ai_service.py:_get_default_hebrew_prompt()`~~ - Use realtime_prompt_builder instead

#### Callers MUST:
1. Import: `from server.services.realtime_prompt_builder import build_realtime_system_prompt`
2. Call: `prompt = build_realtime_system_prompt(business_id, call_direction="inbound")`
3. Use cache: Pass `use_cache=True` (default)

#### Fallback Chain:
```
1. BusinessSettings.ai_prompt (inbound) or .outbound_ai_prompt (outbound)
   ↓ (if missing)
2. Business.system_prompt (legacy)
   ↓ (if missing)
3. FALLBACK_INBOUND_PROMPT_TEMPLATE or FALLBACK_OUTBOUND_PROMPT_TEMPLATE
```

---

### 3. Recording Download

#### Owner: `recording_service.py`
- **File**: `server/services/recording_service.py`
- **Function**: `get_recording_file_for_call(call_log)` - SINGLE ENTRY POINT

#### Deduplication Mechanisms:
1. **In-Memory Tracking**: `_download_in_progress` set
2. **File Locks**: `.{call_sid}.lock` files (cross-process)
3. **Local File Check**: Check before download
4. **Cooldown**: 60 seconds between retries (in tasks_recording.py)

#### Flow:
```
1. Check local file exists → return path
   ↓ (if missing)
2. Check download in progress → wait
   ↓ (if not in progress)
3. Acquire file lock
   ↓
4. Download from Twilio
   ↓
5. Save to: /app/server/recordings/{call_sid}.mp3
   ↓
6. Release lock, return path
```

#### Callers:
1. **UI/API** (`routes_calls.py`):
   - Calls recording_service directly
   
2. **Background Worker** (`tasks_recording.py`):
   - Enqueues jobs to RECORDING_QUEUE
   - Worker calls recording_service
   - Has cooldown dedup: `_should_enqueue_download()`

#### ❌ DEPRECATED:
- ~~`tasks_recording.py:download_recording()`~~ (line 847) - Use recording_service instead

---

### 4. Transcription

#### Primary Source: OpenAI Realtime API (during call)
- **File**: `media_ws_ai.py`
- **Output**: ConversationTurn records (real-time)
- **Quality**: Good, but may have gaps

#### Secondary Source: Whisper (post-call)
- **File**: `tasks_recording.py`
- **Function**: `transcribe_hebrew(audio_file)`
- **Output**: CallLog.final_transcript
- **Quality**: Best, full recording

#### Policy:
1. **During call**: Store Realtime transcript in ConversationTurn
2. **After call**: Worker transcribes recording with Whisper
3. **Final transcript**: 
   - IF recording transcription succeeds → Use it (set transcript_source="recording")
   - ELSE IF realtime transcript exists → Use it (set transcript_source="realtime")
   - ELSE → Mark as failed (set transcript_source="failed")

#### Deduplication:
- Worker checks if `final_transcript` exists and `transcript_source` is set
- Only transcribe if missing or source is "failed"
- Never transcribe same call twice

#### Fields:
- `CallLog.final_transcript` - The canonical transcript
- `CallLog.transcript_source` - Source indicator ("realtime", "recording", "failed")

---

### 5. Greeting & Hangup

#### Greeting Owner: Realtime WebSocket
- **File**: `media_ws_ai.py`
- **Logic**: 
  - Inbound: Wait for user to speak first (unless configured otherwise)
  - Outbound: AI speaks first always
  - Greeting injected via `greeting_prompt` or TTS

#### Greeting Coordination:
1. **TwiML** (`routes_twilio.py`):
   - ✅ Can play static greeting audio
   - ❌ Does NOT inject text greeting (conflicts with Realtime)
   
2. **Realtime** (`media_ws_ai.py`):
   - ✅ Injects greeting into AI system
   - ✅ Controls timing (speaks first mode)

#### Hangup Owner: Realtime WebSocket
- **File**: `media_ws_ai.py`
- **Logic**: Detects end-of-conversation intent

#### Hangup Coordination:
1. **Realtime** sends hangup when:
   - User says goodbye (detected)
   - Call timeout reached
   - Error occurs
   
2. **Webhook** receives "completed" status:
   - Only records status change
   - Does NOT send duplicate hangup

#### Guard: `self.hangup_sent` flag prevents double hangup

---

### 6. Conversation Storage

#### Owner: `ConversationTurn` Model
- **File**: `server/models_sql.py`
- **Writer**: Realtime WebSocket ONLY
- **Reader**: Anyone (read-only)

#### Flow:
```
Realtime receives transcript → Store in ConversationTurn → Associate with CallLog
```

#### Fields:
- `call_sid` - Links to call
- `speaker` - "user" or "assistant"
- `message` - The transcript text
- `confidence_score` - STT confidence
- `timestamp` - When spoken

---

## 🔒 Enforcement Rules

### Rule 1: No Duplicate Writes
- Only ONE component may write to each field
- All others must read-only

### Rule 2: Clear Ownership
- Every function/class documents what it owns
- Comments mark: `✅ OWNER`, `✅ READER`, `❌ NEVER`

### Rule 3: Atomic Operations
- All state changes use DB transactions
- No partial updates

### Rule 4: Deduplication Required
- Any operation that could run twice MUST have dedup
- File locks, in-memory sets, cooldowns, etc.

### Rule 5: Single Entry Point
- Each subsystem has ONE main function
- All paths go through it

---

## 🚫 Anti-Patterns to Avoid

### ❌ Multiple Truth Sources
```python
# BAD
def get_prompt_v1(): ...
def get_prompt_v2(): ...
# Different paths may call different versions!
```

### ❌ Implicit Ownership
```python
# BAD
def update_call_anywhere(call_sid):
    call = CallLog.query.filter_by(call_sid=call_sid).first()
    call.status = "completed"  # Who owns this?
```

### ❌ No Deduplication
```python
# BAD
def download_recording(call_sid):
    # Just downloads, no check if already downloading
    response = requests.get(recording_url)
```

### ❌ Competing Writers
```python
# BAD
# In webhook:
call.status = "completed"

# In realtime (simultaneously):
call.status = "in-progress"

# Race condition! Who wins?
```

---

## ✅ Best Practices

### ✅ Document Ownership
```python
def update_call_status_from_webhook(call_sid, new_status):
    """
    ✅ OWNER: Updates call status - ONLY called from Twilio webhooks
    ❌ NEVER call from Realtime or Workers
    """
```

### ✅ Single Entry Point
```python
# GOOD
def get_prompt(business_id, call_direction):
    """Single entry point for all prompt building"""
    return build_realtime_system_prompt(business_id, call_direction)
```

### ✅ Deduplication
```python
# GOOD
if is_download_in_progress(call_sid):
    logger.info("Download already in progress, skipping")
    return None
```

### ✅ Atomic Updates
```python
# GOOD
with db.session.begin():
    call = CallLog.query.filter_by(call_sid=call_sid).with_for_update().first()
    call.status = new_status
    db.session.commit()
```

---

## 📊 Validation Checklist

Use this checklist to validate SSOT compliance:

- [ ] Each data field has ONE owner documented
- [ ] All writers go through single entry point
- [ ] Deduplication in place for all repeated operations
- [ ] No race conditions possible
- [ ] Cache is transparent (single cache, single builder)
- [ ] Deprecated functions removed or clearly marked
- [ ] Documentation up to date

---

## 🔄 Migration Path

For existing duplicated code:

1. **Identify** the canonical owner
2. **Mark** duplicates as DEPRECATED with warnings
3. **Redirect** all callers to canonical owner
4. **Monitor** for deprecated warnings in logs
5. **Remove** deprecated code after 1 sprint

Example:
```python
# OLD (DEPRECATED)
def get_prompt_old(business_id):
    logger.warning("[DEPRECATED] Use realtime_prompt_builder.build_realtime_system_prompt() instead")
    from server.services.realtime_prompt_builder import build_realtime_system_prompt
    return build_realtime_system_prompt(business_id)
```

---

## 📝 References

- **Models**: `server/models_sql.py`
- **Prompt Builder**: `server/services/realtime_prompt_builder.py`
- **Recording Service**: `server/services/recording_service.py`
- **Realtime Handler**: `server/media_ws_ai.py`
- **Webhooks**: `server/routes_twilio.py`
- **Workers**: `server/tasks_recording.py`

---

## ✅ Compliance Status

| Subsystem | SSOT Owner | Status | Notes |
|-----------|------------|--------|-------|
| Call State | CallLog model | ✅ Defined | Webhooks primary updater |
| Prompts | realtime_prompt_builder.py | ⚠️ Partial | ai_service.py needs migration |
| Recording Download | recording_service.py | ✅ Good | Deprecated function exists |
| Transcription | Worker + Realtime | ✅ Good | Policy documented |
| Greeting/Hangup | Realtime WebSocket | ✅ Good | Guards in place |
| Conversation | ConversationTurn | ✅ Good | Single writer |

**Legend**:
- ✅ Good - SSOT enforced
- ⚠️ Partial - SSOT defined but not fully enforced
- ❌ Broken - Multiple owners competing
