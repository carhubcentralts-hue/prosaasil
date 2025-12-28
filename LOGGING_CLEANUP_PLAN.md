# LOGGING_CLEANUP_PLAN.md
## Logging Cleanup Plan - Production Noise Reduction

**Date**: 2025-12-28
**Goal**: Reduce logging noise in production while maintaining debug capability

---

## 🎯 Current State

### Hot Path Analysis (media_ws_ai.py)
- **Total lines**: 15,346
- **Logging statements**: 1,630
- **Ratio**: 10.6% logging density ⚠️

### Issues Identified

1. **Loop Logging** - Logs inside hot loops (every 20ms)
2. **Duplicate Messages** - Same event logged multiple times
3. **DEBUG logs in production** - Not properly gated
4. **Per-frame logs** - Audio chunks logged individually
5. **Verbose success messages** - Too many "✅" messages

---

## 📋 Cleanup Strategy

### Phase 1: Rate-Limit All Loop Logs ⚡ HIGH PRIORITY

**Target loops**:
1. `async for event in client.recv_events()` (line 4041)
2. `_realtime_audio_out_loop()` (audio transmission)
3. `_audio_tx_loop()` (if exists)
4. Session reaper loop (line 1226)

**Action**:
- Wrap all loop logs with rate limiter
- Use existing `RateLimiter` class from `logging_setup.py`
- Target: 1 log per 5 seconds minimum

**Example fix**:
```python
# BEFORE
for event in events:
    logger.debug(f"Processing event {event_type}")  # Every iteration!

# AFTER
rl = RateLimiter()
for event in events:
    if rl.every("event_loop", 5.0):
        logger.debug(f"Processing event {event_type}")  # Once per 5 seconds
```

---

### Phase 2: Remove Per-Frame DEBUG Logs ⚡ HIGH PRIORITY

**Target patterns**:
```python
# BAD - logs every audio frame
if DEBUG:
    logger.debug(f"Audio chunk {i}: {len(chunk)} bytes")

# BAD - logs every delta
if event_type.endswith(".delta"):
    logger.debug(f"Delta: {event_type}")
```

**Action**:
- Remove all per-frame logs
- Keep only: first frame, last frame, errors
- Use counter + periodic summary

**Example fix**:
```python
# BEFORE
for chunk in audio_chunks:
    if DEBUG:
        logger.debug(f"Chunk {i}: {len(chunk)} bytes")

# AFTER
chunk_counter = 0
for chunk in audio_chunks:
    chunk_counter += 1
    if chunk_counter == 1:
        logger.info(f"Started audio transmission")
# After loop:
logger.info(f"Completed audio transmission: {chunk_counter} chunks")
```

---

### Phase 3: Consolidate Duplicate Messages 🟡 MEDIUM PRIORITY

**Target**: Messages that say the same thing differently

**Examples**:
```python
# DUPLICATE 1
logger.info("Started recording download")
logger.info("Downloading recording") 
logger.info("Recording download started")

# SHOULD BE:
logger.info("Recording download started for {call_sid}")

# DUPLICATE 2  
logger.info("✅ Cache HIT")
logger.debug("Cache hit for key {key}")

# SHOULD BE:
logger.info(f"Cache HIT: {key}")
```

**Action**:
- Audit all logger.info/debug calls
- Remove duplicates
- Standardize message format

---

### Phase 4: Strict DEBUG Gating 🟡 MEDIUM PRIORITY

**Issue**: Some DEBUG logs execute even when DEBUG=1 (production)

**Check**:
```python
# Ensure this pattern is used everywhere:
if DEBUG:
    # Expensive log operation
    logger.debug(f"Detail: {expensive_computation()}")
```

**Action**:
- Audit all logger.debug calls
- Ensure DEBUG flag gate BEFORE expensive operations
- Move heavy computations inside DEBUG block

---

### Phase 5: Eliminate Print Statements 🟢 LOW PRIORITY

**Target**: `print()` calls that bypass logging system

**Action**:
- Find all `print()` calls
- Replace with proper logging
- Keep only `force_print()` for critical errors

**Exception**: Keep `_orig_print()` for session lifecycle events (already rate-limited)

---

## 🎯 Success Metrics

After cleanup:

- [ ] No logs in hot loops without rate limiting
- [ ] No per-frame logs in production
- [ ] Logging density < 2% (down from 10.6%)
- [ ] Production logs show only: macro events, errors, warnings
- [ ] DEBUG mode still usable for development
- [ ] No performance impact from logging

---

## 🔍 Files to Audit

### Priority 1 (Must Fix)
1. `server/media_ws_ai.py` - Main hot path (15K lines, 1.6K logs)
2. `server/services/openai_realtime_client.py` - Realtime API client
3. `server/services/audio_dsp.py` - Audio processing

### Priority 2 (Should Fix)
4. `server/tasks_recording.py` - Background worker
5. `server/routes_webhook.py` - WhatsApp webhook
6. `server/routes_twilio.py` - Twilio webhooks

### Priority 3 (Nice to Have)
7. `server/services/recording_service.py` - Recording downloads
8. `server/services/realtime_prompt_builder.py` - Prompt building

---

## 📊 Logging Policy (Reference)

From `logging_setup.py`:

### Production (DEBUG=1 - default)
- **INFO**: Macro events only (call start/end, session updates, response created/done)
- **WARNING**: Noisy modules (media_ws_ai, audio_dsp, openai_realtime_client)
- **ERROR**: Always enabled
- **DEBUG**: Disabled
- **Forbidden**: Per-frame logs, polling logs, retry logs, loop logs

### Development (DEBUG=0)
- **INFO**: Normal events
- **DEBUG**: Full debugging
- **Rate-limited**: Still apply rate limits to loops

---

## 🛠️ Tools Available

### Rate Limiting
```python
from server.logging_setup import RateLimiter

rl = RateLimiter()
if rl.every("my_key", 5.0):  # Once per 5 seconds
    logger.debug("Periodic status")
```

### Once-Per-Call
```python
from server.logging_setup import OncePerCall

once = OncePerCall()
if once.once("config_loaded"):  # Only once per call
    logger.info("Configuration loaded")
```

### Legacy Rate Limiting
```python
from server.logging_setup import log_every

log_every(logger, "my_key", "Message", level=logging.INFO, seconds=5)
```

---

## 📝 Implementation Steps

1. ✅ Create this plan
2. ⏳ Audit media_ws_ai.py for loop logs
3. ⏳ Add rate limiters to identified loops
4. ⏳ Remove per-frame DEBUG logs
5. ⏳ Consolidate duplicate messages
6. ⏳ Test in development (DEBUG=0)
7. ⏳ Test in production simulation (DEBUG=1)
8. ⏳ Measure before/after metrics
9. ⏳ Document changes

---

## ⚠️ Rules

### DO:
- ✅ Use rate limiters for all loop logs
- ✅ Log macro events (call start/end)
- ✅ Log errors with context
- ✅ Use structured logging (JSON)
- ✅ Keep logs actionable

### DON'T:
- ❌ Log inside hot loops without rate limiting
- ❌ Log per-frame/per-chunk data
- ❌ Log successful polling
- ❌ Log expected retries
- ❌ Create log spam

---

## 🎯 Expected Outcome

**Before**:
```
[DEBUG] Processing audio chunk 1
[DEBUG] Processing audio chunk 2
[DEBUG] Processing audio chunk 3
... (50+ times per second)
[INFO] ✅ Audio chunk sent
[INFO] ✅ Queue size: 100
[DEBUG] Event received: audio.delta
[DEBUG] Event received: audio.delta
... (endless spam)
```

**After**:
```
[INFO] Audio transmission started
[INFO] Received 1,234 events in last 5s (rate-limited summary)
[INFO] Audio transmission completed: 1,234 frames sent
[ERROR] Audio queue overflow detected (actionable)
```

---

## 📈 Monitoring

After deployment, monitor:

1. **Log volume**: Should decrease by 80-90%
2. **Log file size**: Should be manageable (<100MB/day)
3. **Production clarity**: Errors stand out clearly
4. **Debug capability**: Still works in DEBUG=0 mode
5. **Performance**: No impact on call quality

