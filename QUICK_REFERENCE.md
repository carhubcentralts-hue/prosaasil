# QUICK REFERENCE - System Integrity Guidelines
**For Developers**: Quick lookup for SSOT ownership and best practices

---

## 🎯 Golden Rules

1. **Single Source of Truth**: Every piece of data has ONE owner
2. **No Duplicate Logic**: If it exists elsewhere, import it - don't rewrite it
3. **Quiet Production**: Logs should be rare, meaningful, and actionable
4. **Dedup Everything**: If it can run twice, it MUST have deduplication
5. **Document Ownership**: Mark functions with `✅ OWNER` or `❌ NEVER`

---

## 📋 Quick Ownership Lookup

### Call State
**Owner**: `CallLog` database model  
**Primary Updater**: Twilio webhooks (`routes_twilio.py`)  
**Readers**: Realtime, Workers, API  
**Rule**: Only webhooks update status, others append data only

### Prompts (Calls)
**Owner**: `realtime_prompt_builder.py`  
**Entry Point**: `build_realtime_system_prompt(business_id, call_direction)`  
**Rule**: Always use this for call prompts, never build your own

### Prompts (WhatsApp)
**Owner**: `ai_service.py`  
**Entry Point**: `get_business_prompt(business_id, channel="whatsapp")`  
**Rule**: WhatsApp has different needs, use ai_service for this channel

### Recording Download
**Owner**: `recording_service.py`  
**Entry Point**: `get_recording_file_for_call(call_log)`  
**Rule**: Always use this, never download directly from Twilio

### Transcription
**Primary**: OpenAI Realtime (during call) → `ConversationTurn`  
**Secondary**: Whisper (after call) → `CallLog.final_transcript`  
**Rule**: Worker checks before transcribing, never transcribe twice

### Conversation Storage
**Owner**: `ConversationTurn` model  
**Writer**: Realtime WebSocket ONLY  
**Readers**: Everyone  
**Rule**: Only Realtime writes turns, others read only

---

## 🚫 Anti-Patterns (DON'T DO THIS)

### ❌ Building Prompts Yourself
```python
# BAD
def my_function():
    prompt = f"You are {business.name}..."  # Don't build prompts!
    
# GOOD
def my_function():
    from server.services.realtime_prompt_builder import build_realtime_system_prompt
    prompt = build_realtime_system_prompt(business_id, call_direction)
```

### ❌ Downloading Recordings Directly
```python
# BAD
response = requests.get(recording_url)  # No dedup!

# GOOD
from server.services.recording_service import get_recording_file_for_call
file_path = get_recording_file_for_call(call_log)
```

### ❌ Updating Call Status from Non-Webhook
```python
# BAD (in realtime handler)
call.status = "completed"  # Race condition with webhook!

# GOOD (in realtime handler)
# Just read the status, let webhook update it
if call.status == "completed":
    ...
```

### ❌ Logging in Hot Loops
```python
# BAD
for chunk in audio_stream:
    logger.debug(f"Processing chunk {i}")  # 50x per second!

# GOOD
from server.logging_setup import RateLimiter
rl = RateLimiter()
for chunk in audio_stream:
    if rl.every("audio_loop", 5.0):  # Once per 5 seconds
        logger.debug(f"Processing chunks (count: {i})")
```

### ❌ Expensive Operations Before DEBUG Check
```python
# BAD
debug_data = expensive_computation()
if DEBUG:
    logger.debug(f"Data: {debug_data}")  # Computed even when not logged!

# GOOD
if DEBUG:
    debug_data = expensive_computation()
    logger.debug(f"Data: {debug_data}")  # Only computed if needed
```

---

## ✅ Best Practices

### ✅ Document Ownership
```python
def update_call_status(call_sid, status):
    """
    Update call status from Twilio webhook.
    
    ✅ OWNER: Twilio webhooks ONLY
    ❌ NEVER: Call from Realtime or Workers
    """
```

### ✅ Use Rate Limiters
```python
from server.logging_setup import RateLimiter

rl = RateLimiter()

for item in stream:
    process(item)
    if rl.every("my_loop", 5.0):
        logger.debug(f"Processed {count} items")
```

### ✅ Use Once-Per-Call
```python
from server.logging_setup import OncePerCall

once = OncePerCall()

if once.once("config_loaded"):
    logger.info("Configuration loaded successfully")
```

### ✅ Check Deduplication
```python
from server.services.recording_service import is_download_in_progress

if is_download_in_progress(call_sid):
    logger.info("Download already in progress")
    return
```

### ✅ Use Transactions
```python
from server.db import db

with db.session.begin():
    call = CallLog.query.filter_by(call_sid=call_sid).with_for_update().first()
    call.status = new_status
    db.session.commit()
```

---

## 📊 Logging Guidelines

### Production (DEBUG=1 - default)
**DO LOG**:
- ✅ Call start/end (macro events)
- ✅ Errors with context
- ✅ State transitions
- ✅ Important warnings

**DON'T LOG**:
- ❌ Every audio frame
- ❌ Every event in loop
- ❌ Successful polling
- ❌ Expected retries
- ❌ Debug details

### Development (DEBUG=0)
**Additional logging allowed**:
- ✅ DEBUG level enabled
- ✅ Detailed event traces
- ✅ Performance metrics

**Still forbidden**:
- ❌ Per-frame logs (use rate limiting)
- ❌ Logs in tight loops (use rate limiting)

---

## 🔧 Common Tasks

### Task: Build a prompt for a call
```python
from server.services.realtime_prompt_builder import build_realtime_system_prompt

prompt = build_realtime_system_prompt(
    business_id=business_id,
    call_direction="inbound",  # or "outbound"
    use_cache=True  # default
)
```

### Task: Get recording file
```python
from server.services.recording_service import get_recording_file_for_call
from server.models_sql import CallLog

call_log = CallLog.query.filter_by(call_sid=call_sid).first()
file_path = get_recording_file_for_call(call_log)

if file_path:
    # Use the file
    with open(file_path, 'rb') as f:
        audio_data = f.read()
```

### Task: Store conversation turn
```python
from server.models_sql import ConversationTurn
from server.db import db

turn = ConversationTurn(
    call_sid=call_sid,
    call_log_id=call_log.id,
    speaker="user",  # or "assistant"
    message=transcript_text,
    confidence_score=confidence
)
db.session.add(turn)
db.session.commit()
```

### Task: Update call status (webhooks only!)
```python
# Only in routes_twilio.py!
from server.models_sql import CallLog
from server.db import db

call = CallLog.query.filter_by(call_sid=call_sid).first()
if call:
    call.status = new_status
    call.duration = duration
    db.session.commit()
```

### Task: Enqueue recording job
```python
from server.tasks_recording import enqueue_recording_download_only

# Has built-in deduplication
enqueue_recording_download_only(
    call_sid=call_sid,
    recording_url=recording_url,
    business_id=business_id
)
```

---

## 🧪 Testing Checklist

Before committing code, verify:

- [ ] No new prompt building logic (use existing builders)
- [ ] No direct recording downloads (use recording_service)
- [ ] All loop logs are rate-limited
- [ ] No expensive operations before DEBUG check
- [ ] Ownership documented in docstrings
- [ ] Deduplication in place for repeated operations
- [ ] Transactions used for status updates
- [ ] No logging in hot paths (or rate-limited)

---

## 📞 Who to Ask

### Prompts / AI Integration
- File: `realtime_prompt_builder.py`, `ai_service.py`
- Expertise: Prompt design, OpenAI API

### Call Handling / Realtime
- File: `media_ws_ai.py`, `routes_twilio.py`
- Expertise: Call flow, WebSocket, Twilio

### Recording / Transcription
- File: `tasks_recording.py`, `recording_service.py`
- Expertise: Background jobs, STT, file handling

### Database / Models
- File: `models_sql.py`, `db.py`
- Expertise: Schema, migrations, queries

### Logging / Performance
- File: `logging_setup.py`, `config/calls.py`
- Expertise: Production optimization

---

## 📚 Key Documents

1. **SSOT_ARCHITECTURE.md** - Complete ownership map
2. **AUDIT_SUMMARY.md** - Executive summary & action plan
3. **LOGGING_CLEANUP_PLAN.md** - Detailed logging fixes
4. **AUDIT_FINDINGS.md** - Critical issues identified
5. **THIS DOCUMENT** - Quick reference for daily work

---

## 🚨 Red Flags (Stop and Ask)

If you're about to:
- ❌ Build a prompt from scratch
- ❌ Download a recording directly from Twilio
- ❌ Update CallLog.status from Realtime
- ❌ Add logging inside an audio processing loop
- ❌ Duplicate logic that exists elsewhere

**STOP** and consult the SSOT architecture document first!

---

## ✅ Green Lights (Good to Go)

If you're:
- ✅ Using existing builders/services
- ✅ Adding rate-limited logs
- ✅ Reading from database (not updating)
- ✅ Following documented ownership
- ✅ Adding deduplication for new operations
- ✅ Writing tests for state machines

**PROCEED** with confidence!

---

## 🎯 Remember

> **"If two parts of the system think they are responsible for the same thing — that is a bug, even if nothing crashes."**

When in doubt:
1. Check SSOT_ARCHITECTURE.md
2. Look for existing implementation
3. Ask before duplicating
4. Document your ownership

**Keep it simple. Keep it single. Keep it clear.**
