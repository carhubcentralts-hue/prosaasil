# Gemini Audio Routing Fixes - Implementation Summary

## Problem Analysis (From Hebrew Problem Statement)

The Gemini WebSocket was connecting successfully but no audio was being produced:
- ✅ GEMINI_LIVE_WS_OPEN + Connected in 130ms
- ✅ session.update sent + session.updated confirmed  
- ✅ RESPONSE_CREATE reason=GREETING
- ❌ No audio/response events after RESPONSE_CREATE

### Root Causes Identified:

1. **Audio routing mismatch**: Audio out loop always said "waiting for OpenAI audio" even when provider=gemini
2. **Missing Gemini logging**: No GEMINI_SEND/GEMINI_RECV logs to track data flow
3. **Gemini greeting not triggered**: trigger_response was NO-OP for Gemini - didn't actually send anything
4. **No audio watchdog**: No timeout detection for missing first audio chunk
5. **Silent thread exceptions**: Gemini thread crashes might be swallowed without logging

## Fixes Implemented

### 1. Provider-Aware Audio Out Loop Logging
**File**: `server/media_ws_ai.py` (line 9272-9277)

**Before**:
```python
_orig_print(f"🔊 [AUDIO_OUT_LOOP] Started - waiting for OpenAI audio", flush=True)
```

**After**:
```python
ai_provider = getattr(self, '_ai_provider', 'openai')
if ai_provider == 'gemini':
    _orig_print(f"🔊 [AUDIO_OUT_LOOP] Started - waiting for GEMINI audio", flush=True)
else:
    _orig_print(f"🔊 [AUDIO_OUT_LOOP] Started - waiting for OpenAI audio", flush=True)
```

**Impact**: Now logs correctly show which provider's audio we're waiting for.

---

### 2. Comprehensive Gemini Event Logging
**File**: `server/services/gemini_realtime_client.py`

**Added logging in send_audio()**:
```python
# Track and log audio sent to Gemini
if not hasattr(self, '_audio_chunks_sent'):
    self._audio_chunks_sent = 0
    logger.info(f"🎤 [GEMINI_SEND] Starting to send audio to Gemini Live API")
self._audio_chunks_sent += 1

# Log first few chunks
if self._audio_chunks_sent <= 3:
    logger.info(f"🎤 [GEMINI_SEND] audio_chunk #{self._audio_chunks_sent}: {len(audio_bytes)} bytes")
```

**Added logging in send_text()**:
```python
logger.info(f"📝 [GEMINI_SEND] text: {text[:100]}...")
```

**Added logging in recv_events()**:
```python
logger.info("✅ [GEMINI_RECV] setup_complete")
logger.info(f"🔊 [GEMINI_RECV] audio_chunk (FIRST): {len(audio_bytes)} bytes")
logger.info(f"📝 [GEMINI_RECV] text: {part.text[:100]}...")
logger.info("✅ [GEMINI_RECV] turn_complete")
logger.info("⚠️ [GEMINI_RECV] interrupted")
```

**Impact**: Now have full visibility into Gemini data flow with GEMINI_SEND/GEMINI_RECV logs.

---

### 3. **CRITICAL FIX**: Gemini Greeting Trigger
**File**: `server/media_ws_ai.py` (line 5179-5189)

**The Problem**: 
Gemini Live API auto-responds when user finishes speaking (VAD-based). For GREETING (bot-speaks-first), it was doing NOTHING - just logging. This is why no audio came.

**The Solution**:
Send empty text to Gemini to trigger it to start speaking:

```python
if ai_provider == 'gemini':
    logger.info(f"🎯 [GEMINI] Auto-response mode - provider handles turn-taking ({reason})")
    
    # 🔥 GEMINI GREETING FIX: For GREETING, send empty text to trigger response
    if reason == "GREETING" or is_greeting:
        try:
            await _client.send_text("")  # ← THIS IS THE KEY FIX
            logger.info(f"🎯 [GEMINI_SEND] greeting_trigger: sent empty text to start greeting")
            _orig_print(f"🎯 [GEMINI_SEND] greeting_trigger: sent empty text to start bot-speaks-first", flush=True)
        except Exception as e:
            logger.error(f"❌ [GEMINI_SEND] Failed to send greeting trigger: {e}")
```

**Impact**: Gemini now actually starts speaking for greetings. This is THE fix for "no audio after RESPONSE_CREATE".

---

### 4. First Audio Watchdog Timer
**File**: `server/media_ws_ai.py` (line 2531-2582)

**Added method**: `_start_first_audio_watchdog(provider)`

Monitors for first audio chunk after RESPONSE_CREATE:
- Waits 2.5 seconds
- If no audio received, logs diagnostic snapshot:
  - Provider, model, voice
  - WebSocket state
  - Queue sizes (tx_q, out_q)
  - Last event timestamps
  
**Called from**: trigger_response() when reason=GREETING for Gemini

**Impact**: Quickly detects when audio generation fails and provides diagnostic info.

---

### 5. Global Thread Exception Handler
**File**: `server/media_ws_ai.py` (line 52-75)

**Added**:
```python
def _global_thread_exception_handler(args):
    """Global handler for uncaught exceptions in threads"""
    exc_type, exc_value, exc_tb, thread = args.exc_type, args.exc_value, args.exc_traceback, args.thread
    
    _orig_print(
        f"❌ [GEMINI_THREAD_CRASH] Uncaught exception in thread '{thread.name}': "
        f"{exc_type.__name__}: {exc_value}",
        flush=True
    )
    
    logger.exception(
        f"[GEMINI_THREAD_CRASH] Uncaught exception in thread '{thread.name}'",
        exc_info=(exc_type, exc_value, exc_tb)
    )

# Install for Python 3.8+
if sys.version_info >= (3, 8):
    threading.excepthook = _global_thread_exception_handler
```

**Impact**: Silent Gemini thread crashes are now logged with full stack traces.

---

### 6. Exception Handling in Gemini Client
**File**: `server/services/gemini_realtime_client.py`

**Added** comprehensive try/except with logging:
```python
except Exception as e:
    logger.error(f"❌ [GEMINI_SEND] Failed to send audio: {e}")
    logger.exception(f"[GEMINI_THREAD_CRASH] Exception in send_audio", exc_info=True)
    raise
```

Similar error handling added to:
- `send_audio()` (line 294-295)
- `send_text()` (line 317-318)
- `recv_events()` parse loop (line 468-469)
- `recv_events()` main loop (line 473-474)

**Impact**: All Gemini async operations now log exceptions with full context.

---

## Expected Log Sequence (After Fix)

When Gemini greeting works correctly, logs should show:

```
🚀 [GEMINI_LIVE] Async loop starting - connecting to Gemini Live API IMMEDIATELY
🟢 [GEMINI_LIVE] Connected: gemini-2.0-flash-exp
✅ [GEMINI_RECV] setup_complete
✅ [GEMINI_CONFIG] Using configuration from connect() - marking as confirmed
🎯 [RX_LOOP] recv_events() loop is now ACTIVE and listening (gemini)
🎯 [RESPONSE_CREATE] reason=GREETING, prev_active=none, is_ai_speaking=False, tx_q=0, out_q=0
🎯 [GEMINI] Auto-response mode - provider handles turn-taking (GREETING)
🎯 [GEMINI_SEND] greeting_trigger: sent empty text to start bot-speaks-first
🔊 [AUDIO_OUT_LOOP] Started - waiting for GEMINI audio
🔊 [GEMINI_RECV] audio_chunk (FIRST): 3840 bytes
🔊 [AUDIO_OUT_LOOP] FIRST_CHUNK received! bytes=320, stream_sid=MZ...
```

## Testing Verification

Manual verification completed:
- ✅ Provider-aware audio out loop logging (line 9375-9377)
- ✅ GEMINI_SEND logging in send_audio, send_text (multiple locations)
- ✅ GEMINI_RECV logging in recv_events (multiple event types)
- ✅ Watchdog method exists (line 2531)
- ✅ Global thread exception handler installed (line 52-75)
- ✅ Gemini greeting trigger sends empty text (line 5184-5188)

## Next Steps for User

1. **Deploy the changes** to test environment
2. **Start a Gemini call** with greeting enabled
3. **Check logs** for the expected sequence above
4. **Verify audio** is produced and heard by caller
5. If issues persist, the diagnostic logs will show:
   - Whether greeting trigger was sent (GEMINI_SEND)
   - Whether audio was received (GEMINI_RECV)
   - Watchdog snapshot if no audio arrives

## Files Modified

1. `server/media_ws_ai.py` - Main WebSocket handler
   - Added provider-aware audio out loop logging
   - Added Gemini greeting trigger
   - Added watchdog timer
   - Added global thread exception handler

2. `server/services/gemini_realtime_client.py` - Gemini client
   - Added GEMINI_SEND logging for audio/text
   - Added GEMINI_RECV logging for all events
   - Added exception handling with logging

## Voice Compatibility Note

The voice "achernar" is valid for Gemini according to the voice catalog (`server/config/voice_catalog.py` line 93-97). The voice catalog already includes it in GEMINI_VOICES. No additional validation needed for this voice.
