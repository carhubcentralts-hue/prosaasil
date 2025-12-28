# System Audit Report - Single Source of Truth Analysis
**Date**: 2025-12-28
**Purpose**: Deep architectural audit to identify duplications, establish SSOT, reduce noise, ensure stability

---

## 🎯 Executive Summary

This audit examines the AI Call Center SaaS platform to establish Single Source of Truth (SSOT) for all critical subsystems, eliminate duplications, reduce logging noise, and identify performance bottlenecks.

**System Components**:
- Realtime calls (Twilio Media Streams + OpenAI Realtime API)
- Multi-tenant CRM
- Recording/transcription workers (offline)
- WhatsApp integration
- Prompt management system
- Background workers (async processing)

---

## 📋 Phase 1: Single Source of Truth Mapping

### 1.1 Call State Management

**Current State Analysis**:
- **Primary Model**: `CallLog` in `models_sql.py`
  - Fields: `call_status` (legacy), `status` (current), `direction`, `twilio_direction`
  - ⚠️ **ISSUE**: Two status fields (`call_status` and `status`) - potential confusion
  
**Who manages call state?**:
1. **Twilio Webhooks** (`routes_twilio.py`):
   - Receives status callbacks (initiated, ringing, answered, completed)
   - Updates CallLog.status
   
2. **Realtime WebSocket** (`media_ws_ai.py`):
   - Manages active call state during conversation
   - May create/update CallLog entries
   
3. **Recording Worker** (`tasks_recording.py`):
   - Updates CallLog after call completion
   - Adds transcription, recording metadata

**⚠️ DUPLICATION RISK**: Multiple components updating same CallLog - need to verify no race conditions

**SSOT Recommendation**:
- ✅ Database (CallLog) is the SSOT
- ✅ Webhooks should be primary updater
- ✅ Realtime should only read (not update status)
- ✅ Workers should only append data (transcription, metadata)

---

### 1.2 Prompt Building

**Current State Analysis**:

**Prompt Builders Found**:
1. `services/realtime_prompt_builder.py`:
   - `build_realtime_system_prompt()` - Main entry point
   - `build_inbound_system_prompt()` - Inbound calls
   - `build_outbound_system_prompt()` - Outbound calls
   - `build_compact_business_instructions()` - Business content
   - `get_greeting_prompt_fast()` - Fast greeting
   - `_get_prompt_with_fallback()` - Fallback logic

2. `services/ai_service.py`:
   - `get_business_prompt()` - Alternative prompt builder
   - `_get_default_hebrew_prompt()` - Fallback

3. `services/dynamic_stt_service.py`:
   - `build_dynamic_stt_prompt()` - STT enhancement prompt

4. `routes_ai_prompt.py`:
   - `_get_business_prompt_internal()` - API endpoint helper
   - Multiple prompt getters

5. `services/prompt_cache.py`:
   - `PromptCache` class - Caching layer

**⚠️ CRITICAL DUPLICATION**: Multiple prompt builders with overlapping responsibilities!

**SSOT Recommendation**:
- ✅ `realtime_prompt_builder.py` should be the ONLY builder for call prompts
- ✅ `ai_service.py` should delegate to prompt_builder (not build its own)
- ✅ Cache should be transparent (single cache, single builder)
- ⚠️ Need to verify no double-building occurs

---

### 1.3 Recording Download Logic

**Current State Analysis**:

**Recording Download Paths Found**:
1. `services/recording_service.py`:
   - `get_recording_file_for_call()` - Main download function
   - `_download_from_twilio()` - Actual HTTP download
   - ✅ Has deduplication: `_download_in_progress` set
   - ✅ Has file-based locking
   - ✅ Checks for existing local files

2. `tasks_recording.py`:
   - `download_recording()` - Worker function (line 847)
   - `download_recording_only()` - Queue processor (line 375)
   - `enqueue_recording_download_only()` - Queue enqueuer (line 156)
   - ✅ Has deduplication: `_should_enqueue_download()`
   - ✅ Cooldown period: 60 seconds

3. `routes_calls.py`:
   - `download_recording()` - API endpoint (line 224)
   - Likely calls recording_service

**⚠️ POTENTIAL DUPLICATION**: Two download implementations - recording_service vs tasks_recording

**Deduplication Mechanisms**:
✅ `recording_service.py`:
  - In-memory set: `_download_in_progress`
  - File locks: `.{call_sid}.lock`
  - Local file check before download

✅ `tasks_recording.py`:
  - Cooldown tracking: `_last_enqueue_time`
  - Calls `is_download_in_progress()` from recording_service
  - Queue prevents duplicates

**SSOT Recommendation**:
- ✅ `recording_service.py` should be the ONLY download executor
- ✅ `tasks_recording.py` should only queue jobs
- ✅ All paths (API, webhook, worker) should use recording_service
- ⚠️ Need to verify tasks_recording doesn't duplicate download logic

---

### 1.4 STT/Transcription Flows

**Current State Analysis**:

**Transcription Triggers Found**:
1. **Realtime** (`media_ws_ai.py`):
   - OpenAI Realtime API provides transcript in real-time
   - Stored in ConversationTurn as conversation progresses
   - May set CallLog.final_transcript from realtime

2. **Recording Worker** (`tasks_recording.py`):
   - Downloads recording after call ends
   - Transcribes using STT (likely OpenAI Whisper)
   - Sets CallLog.final_transcript from recording
   - Sets `transcript_source` field

3. **Webhook** (`routes_webhook.py` / `routes_twilio.py`):
   - May trigger recording download/transcription

**⚠️ CRITICAL QUESTION**: Can same call be transcribed twice (once realtime, once from recording)?

**Fields tracking transcript source**:
- `CallLog.final_transcript` - The transcript
- `CallLog.transcript_source` - Source: "realtime", "recording", or "failed"

**SSOT Recommendation**:
- ✅ CallLog.final_transcript is the SSOT
- ✅ Realtime transcript should be default
- ✅ Recording transcription should be fallback or quality upgrade
- ⚠️ Need clear policy: overwrite realtime with recording, or only if missing?
- ⚠️ Need to verify no duplicate transcription jobs

---

### 1.5 Greeting/Hangup Logic

**Current State Analysis**:

**Greeting Handlers Found**:
1. `media_ws_ai.py`:
   - Realtime greeting logic
   - "speaks first" mode for outbound
   - Greeting injection in WebSocket

2. `routes_twilio.py`:
   - TwiML generation with greeting
   - Webhook response with initial message

3. `services/realtime_prompt_builder.py`:
   - `get_greeting_prompt_fast()` - Greeting prompt
   - May inject greeting in system prompt

**⚠️ POTENTIAL DUPLICATION**: Multiple places deciding when/how to greet

**Hangup Handlers Found**:
1. `media_ws_ai.py`:
   - Detects end-of-conversation
   - Sends hangup command
   
2. Webhooks (status callbacks):
   - Detect call completed from Twilio
   
3. `services/generic_webhook_service.py`:
   - May handle status updates

**SSOT Recommendation**:
- ✅ Realtime should own active call greeting/hangup
- ✅ Webhooks should only record status changes
- ⚠️ Need to verify no double-greeting
- ⚠️ Need to verify no conflicting hangup commands

---

## 📋 Phase 2: Identified Duplications

### 2.1 Duplicate Call SID Processing

**Analysis**:
Searching for places where call_sid is processed...

**Processors**:
1. **Realtime WebSocket** (`media_ws_ai.py`):
   - Processes audio for active calls
   - Creates/updates CallLog
   - Stores conversation turns

2. **Status Webhook** (`routes_twilio.py`):
   - Receives Twilio status updates
   - Updates CallLog status

3. **Recording Webhook** (`routes_twilio.py`):
   - Triggered when recording available
   - May enqueue download job

4. **Recording Worker** (`tasks_recording.py`):
   - Background processing
   - Downloads + transcribes
   - Updates CallLog with transcript

**⚠️ RISK**: Same call_sid touched by 4+ components - need clear ownership

**Verification Needed**:
- [ ] Can same call_sid be in Realtime AND webhook simultaneously?
- [ ] Can worker process call while still active?
- [ ] Are updates atomic (DB transactions)?

---

### 2.2 Duplicate Recording Downloads

**Analysis**:

Current deduplication mechanisms:
1. `recording_service.py`:
   - ✅ In-memory: `_download_in_progress` set
   - ✅ File-based: `.{call_sid}.lock` files
   - ✅ Check local file exists before download

2. `tasks_recording.py`:
   - ✅ Cooldown: `_last_enqueue_time` (60 sec)
   - ✅ Checks: `_should_enqueue_download()`
   - ✅ Delegates to recording_service

**⚠️ POTENTIAL ISSUE**:
- Two separate implementations (recording_service vs tasks_recording)
- `tasks_recording.py` has its own `download_recording()` function (line 847)
- Need to verify it delegates to recording_service, not duplicate implementation

**Verification Needed**:
- [ ] Does tasks_recording.download_recording() call recording_service?
- [ ] Or does it have duplicate download logic?
- [ ] Can UI download + worker download same recording simultaneously?

---

### 2.3 Duplicate STT Processing

**Analysis**:

**Transcription sources**:
1. Realtime API - built-in transcription
2. Recording + Whisper - offline transcription

**Question**: Can same call have both?

**From models**: `transcript_source` field suggests:
- "realtime" - from OpenAI Realtime
- "recording" - from Whisper on recording
- "failed" - transcription failed

**Logic needed**:
- If realtime transcript exists, should recording still transcribe?
- Or only transcribe from recording if realtime failed?

**Verification Needed**:
- [ ] Check recording worker: does it skip if final_transcript exists?
- [ ] Or does it always overwrite?
- [ ] Policy: should recording transcript replace realtime?

---

### 2.4 Duplicate Prompt Building

**Analysis**:

Multiple prompt builders found (see 1.2 above).

**Issue**: Different code paths may build prompts differently:
- Realtime calls: `realtime_prompt_builder.py`
- WhatsApp: may use `ai_service.py`
- API endpoints: may use `routes_ai_prompt.py`

**Cache Issues**:
- `prompt_cache.py` exists
- But multiple builders = cache misses
- Same business_id + call type should return same prompt

**Verification Needed**:
- [ ] Do all paths use same builder?
- [ ] Is cache shared across all paths?
- [ ] Can same call get different prompts if rebuilt?

---

### 2.5 Duplicate Greeting/Hangup

**Analysis**:

**Greeting duplication risk**:
- Realtime may send greeting
- TwiML may include greeting
- Both could fire for same call

**Hangup duplication risk**:
- Realtime detects end-of-conversation → sends hangup
- Twilio fires completed webhook → may trigger hangup
- Could send multiple hangup commands

**Verification Needed**:
- [ ] Can call receive two greetings?
- [ ] Can call receive multiple hangup commands?
- [ ] Is there guard against duplicate greeting/hangup?

---

## 📋 Phase 3: Logging Analysis

### 3.1 Hot Path Logging

**File**: `media_ws_ai.py` (15,346 lines, 1,630 logging statements)
**Ratio**: ~10.6% of code is logging

**⚠️ CONCERN**: Very high logging density in hot path

**Analysis**:
- File handles real-time audio streaming (every 20ms)
- Any logs in audio loop = massive spam
- Needs rate-limiting or elimination

**Logging Policy** (from `logging_setup.py`):
- ✅ Has `DEBUG` flag (0=dev, 1=prod)
- ✅ Has rate-limiting: `RateLimiter` class
- ✅ Has once-per-call: `OncePerCall` class
- ✅ Production: WARNING level for noisy modules
- ✅ Blocks Twilio, httpx, uvicorn in production

**Good practices found**:
- ✅ `log_every()` for rate-limiting
- ✅ `once.once()` for one-time logs
- ✅ Level-based filtering (DEBUG=1 → INFO only)

**Issues to verify**:
- [ ] Are all loop logs rate-limited?
- [ ] Are DEBUG logs actually suppressed in production?
- [ ] Are per-frame logs eliminated?

---

### 3.2 Loop Logging Patterns

**Anti-patterns to find**:
```python
# BAD - logs every frame
for chunk in audio_stream:
    logger.info(f"Processing chunk {i}")  # 50+ times per second!
```

**Need to search for**:
- Logs inside `while True` loops
- Logs inside audio processing loops
- Logs inside polling loops
- Logs without rate-limiting

---

### 3.3 Redundant Log Messages

**Patterns to consolidate**:
- Multiple "starting X" messages
- Duplicate error messages
- Overly verbose success messages

**Example issues**:
- "Started recording download" + "Downloading recording" + "Recording download started" = 3 messages for 1 event
- Should be: 1 message at start, 1 at end

---

## 📋 Phase 4: Performance Bottlenecks

### 4.1 Synchronous Operations in Webhooks

**Anti-pattern**: Webhook does heavy work before returning 200 OK

**Files to check**:
- `routes_webhook.py` - WhatsApp webhook
- `routes_twilio.py` - Twilio webhooks

**Good pattern found** (routes_webhook.py):
```python
# ⚡ ACK immediately - don't wait for processing
Thread(target=_process_whatsapp_fast, args=(tenant_id, messages), daemon=True).start()
return '', 200
```
✅ This is correct - spawn thread, return immediately

**Need to verify**:
- [ ] All webhooks return quickly (<50ms)?
- [ ] No DB queries in webhook before return?
- [ ] No HTTP calls in webhook before return?

---

### 4.2 DB Queries in Realtime Callbacks

**Anti-pattern**: Real-time audio callback queries database

**Risk**: DB query = 5-50ms latency = audio glitches

**Need to check**:
- [ ] Does media_ws_ai.py query DB in audio loop?
- [ ] Are prompts pre-loaded (not fetched during call)?
- [ ] Are business settings cached?

---

### 4.3 Unnecessary Locks

**Files with locks**:
- `recording_service.py` - File locks for downloads
- `routes_webhook.py` - Semaphore for thread limits
- `tasks_recording.py` - Lock for enqueue dedup

**Need to verify**:
- [ ] Are locks necessary?
- [ ] Could any be replaced with lock-free structures?
- [ ] Are lock timeouts reasonable?

---

### 4.4 Polling vs Event-Driven

**Pattern to find**: `while True: check_status(); sleep(1)`

**Should be**: Event/callback driven

**Files to check**:
- Worker loops
- Status checkers
- Recording availability checks

---

## 📋 Phase 5: Recommendations

### Critical Issues to Fix

1. **Prompt Building Duplication**:
   - CONSOLIDATE: All prompt building through `realtime_prompt_builder.py`
   - REMOVE: Duplicate builders in `ai_service.py`
   - VERIFY: Cache is single source

2. **Call State Ownership**:
   - CLARIFY: Webhooks own status updates
   - CLARIFY: Realtime reads only (doesn't update status)
   - CLARIFY: Workers append data (don't change status)

3. **Recording Download**:
   - VERIFY: `tasks_recording.download_recording()` delegates to `recording_service`
   - REMOVE: Any duplicate download implementation
   - DOCUMENT: Single path for all downloads

4. **Logging Cleanup**:
   - AUDIT: All logs in `media_ws_ai.py`
   - RATE-LIMIT: All loop logs
   - REMOVE: Per-frame debug logs
   - KEEP: Only actionable errors

5. **Transcription Policy**:
   - DOCUMENT: When to use realtime vs recording transcript
   - PREVENT: Double transcription of same call
   - CLARIFY: Does recording overwrite realtime?

---

## 📋 Next Steps

1. ✅ Complete detailed code audit (this document)
2. ⏳ Implement fixes for identified duplications
3. ⏳ Add validation tests
4. ⏳ Update architecture documentation
5. ⏳ Create ownership map

---

## 🔍 Files to Audit in Detail

Priority files for deep inspection:

1. `media_ws_ai.py` - Realtime handler (15K lines - needs cleanup)
2. `tasks_recording.py` - Recording worker
3. `services/recording_service.py` - Download logic
4. `services/realtime_prompt_builder.py` - Prompt building
5. `services/ai_service.py` - Alternate prompt builder (?)
6. `routes_twilio.py` - Webhook handlers
7. `routes_webhook.py` - WhatsApp webhook

---

## 📊 Metrics

- **Total .py files in server/**: ~100+
- **Lines in media_ws_ai.py**: 15,346
- **Logging statements in media_ws_ai.py**: 1,630
- **Prompt builder functions**: 15+
- **Recording download functions**: 6+
- **Call state update points**: 4+

**Concern Level**: 🔴 HIGH - Multiple duplications found, requires systematic cleanup

