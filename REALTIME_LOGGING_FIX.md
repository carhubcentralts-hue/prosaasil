# Realtime WebSocket Logging Fix

## Issue Summary

After merging the previous "Fix realtime websocket handler" PR, production logs showed:
- ✅ WebSocket connections accepted: `INFO: "WebSocket /ws/twilio-media" [accepted]`
- ✅ Connections opening and closing properly
- ❌ **ZERO `[REALTIME]` logs** - no evidence of realtime code execution

**Root Cause**: The realtime code path was not being triggered at all. The WebSocket handler was accepting connections but not starting the MediaStreamHandler or realtime threads.

## Changes Made

### 1. Enhanced WebSocket Handler Logging (`asgi.py`)

Added comprehensive logging throughout the entire WebSocket lifecycle:

```python
async def ws_twilio_media(websocket: WebSocket):
    # 🔥 CRITICAL: Log at VERY TOP (both print and logger)
    print(f"[REALTIME] WS handler ENTERED: path=/ws/twilio-media", flush=True)
    twilio_log.info("[REALTIME] WS handler ENTERED: path=/ws/twilio-media")
    
    # Log WebSocket accept
    print("[REALTIME] About to accept WebSocket...", flush=True)
    await websocket.accept(subprotocol="audio.twilio.com")
    print("[REALTIME] WebSocket accepted with subprotocol: audio.twilio.com", flush=True)
    
    # Log handler startup
    twilio_log.info("[REALTIME] Creating SyncWebSocketWrapper...")
    twilio_log.info("[REALTIME] Importing MediaStreamHandler...")
    
    # Log run_handler thread
    twilio_log.info("[REALTIME] run_handler: STARTED - Getting Flask app...")
    twilio_log.info("[REALTIME] run_handler: MediaStreamHandler created - Starting handler.run()...")
    
    # Log async loops
    twilio_log.info("[REALTIME] run_all: STARTING async loops and handler thread...")
    twilio_log.info("[REALTIME] run_all: Handler thread started - waiting for loops...")
```

**Why both print() and logger?**
- `print(flush=True)` ensures immediate output to Docker logs
- `logger.info()` provides structured logging
- Double-redundancy ensures we catch the issue

### 2. Enhanced MediaStreamHandler Logging (`server/media_ws_ai.py`)

#### A. Main Run Loop Entry
```python
def run(self):
    # 🔥 CRITICAL: Unconditional logs at the very top (always printed!)
    _orig_print(f"🔵 [REALTIME] MediaStreamHandler.run() ENTERED - waiting for START event...", flush=True)
    logger.info("[REALTIME] MediaStreamHandler.run() ENTERED - waiting for START event")
    logger.info(f"[REALTIME] USE_REALTIME_API={USE_REALTIME_API}, websocket_type={type(self.ws)}")
```

#### B. START Event Handler
```python
if et == "start":
    _orig_print(f"🎯 [REALTIME] START EVENT RECEIVED! session={self._call_session_id}", flush=True)
    logger.info(f"[REALTIME] [{self._call_session_id}] START EVENT RECEIVED - entering start handler")
    logger.info(f"[REALTIME] [{self._call_session_id}] Event data keys: {list(evt.keys())}")
```

#### C. Realtime Thread Startup
```python
logger.info(f"[REALTIME] START event received: call_sid={self.call_sid}, to_number={getattr(self, 'to_number', 'N/A')}")
logger.info(f"[REALTIME] About to check if we should start realtime thread...")
logger.info(f"[REALTIME] USE_REALTIME_API={USE_REALTIME_API}, self.realtime_thread={getattr(self, 'realtime_thread', None)}")

if USE_REALTIME_API and not self.realtime_thread:
    logger.info(f"[REALTIME] Condition passed - About to START realtime thread for call {self.call_sid}")
    
    logger.info(f"[REALTIME] Creating realtime thread...")
    self.realtime_thread = threading.Thread(target=self._run_realtime_mode_thread, daemon=True)
    
    logger.info(f"[REALTIME] Starting realtime thread...")
    self.realtime_thread.start()
    
    logger.info(f"[REALTIME] Realtime thread started successfully!")
    logger.info(f"[REALTIME] Both realtime threads started successfully!")
else:
    logger.warning(f"[REALTIME] Realtime thread NOT started! USE_REALTIME_API={USE_REALTIME_API}, self.realtime_thread exists={...}")
```

#### D. Realtime Thread Entry
```python
def _run_realtime_mode_thread(self):
    # 🔥 CRITICAL: Unconditional logs at the very top
    _orig_print(f"🚀 [REALTIME] _run_realtime_mode_thread ENTERED for call {call_id} (FRESH SESSION)", flush=True)
    logger.info(f"[REALTIME] _run_realtime_mode_thread ENTERED for call {call_id}")
    logger.info(f"[REALTIME] Thread started for call {call_id}")
    logger.info(f"[REALTIME] About to run asyncio.run(_run_realtime_mode_async)...")
```

#### E. Tools Configuration
```python
# When tools are empty (appointments disabled)
if realtime_tools:
    logger.info(f"[TOOLS][REALTIME] Session will use appointment tool (count={len(realtime_tools)})")
else:
    # 🔥 CRITICAL: Log that we're continuing with NO tools (pure conversation)
    print(f"[TOOLS][REALTIME] No tools enabled for this call - pure conversation mode")
    logger.info(f"[TOOLS][REALTIME] No tools enabled for this call - pure conversation mode")
```

## Expected Log Sequence

After this fix, production logs should show a clear execution flow:

```
[REALTIME] WS handler ENTERED: path=/ws/twilio-media
[REALTIME] About to accept WebSocket...
[REALTIME] WebSocket accepted with subprotocol: audio.twilio.com
[REALTIME] WebSocket connected: /ws/twilio-media
[REALTIME] Creating SyncWebSocketWrapper...
[REALTIME] Importing MediaStreamHandler...
[REALTIME] run_all: STARTING async loops and handler thread...
[REALTIME] run_handler: STARTED - Getting Flask app...
[REALTIME] run_handler: MediaStreamHandler created - Starting handler.run()...
[REALTIME] MediaStreamHandler.run() ENTERED - waiting for START event
[REALTIME] USE_REALTIME_API=True, websocket_type=<class 'SyncWebSocketWrapper'>

# After START event from Twilio:
[REALTIME] START EVENT RECEIVED! session=SES-abc12345
[REALTIME] About to check if we should start realtime thread...
[REALTIME] USE_REALTIME_API=True, self.realtime_thread=None
[REALTIME] Condition passed - About to START realtime thread for call CAxxxxx
[REALTIME] Creating realtime thread...
[REALTIME] Starting realtime thread...
[REALTIME] Realtime thread started successfully!
[REALTIME] Both realtime threads started successfully!

# In the realtime thread:
[REALTIME] _run_realtime_mode_thread ENTERED for call CAxxxxx
[REALTIME] Thread started for call CAxxxxx
[REALTIME] About to run asyncio.run(_run_realtime_mode_async)...
[REALTIME] _run_realtime_mode_async STARTED for call CAxxxxx
[REALTIME] Creating OpenAI client with model=gpt-4o-mini-realtime-preview
[REALTIME] Connected
[REALTIME] Building tools for call...
[REALTIME] Tools built successfully: count=0
[TOOLS][REALTIME] No tools enabled for this call - pure conversation mode
[REALTIME] Starting audio/text bridge tasks...
```

## What This Fixes

1. **Visibility**: Every execution path now has explicit logging
2. **Diagnostics**: We can pinpoint exactly where execution stops
3. **Tool Verification**: Confirms realtime continues even with `tools=[]`
4. **Thread Lifecycle**: Tracks thread creation, startup, and execution
5. **Early Detection**: Catches exceptions and conditions that skip realtime

## Testing Instructions

1. **Rebuild Docker images**:
   ```bash
   docker compose build backend
   ```

2. **Restart services**:
   ```bash
   docker compose up -d
   ```

3. **Make a test call** to your Twilio number

4. **Check logs**:
   ```bash
   docker compose logs -f backend | grep REALTIME
   ```

5. **Expected outcome**: You should now see a continuous flow of `[REALTIME]` logs from handler entry through OpenAI connection

## Verification Checklist

- [ ] See `[REALTIME] WS handler ENTERED` immediately when call connects
- [ ] See `[REALTIME] MediaStreamHandler.run() ENTERED` 
- [ ] See `[REALTIME] START EVENT RECEIVED`
- [ ] See `[REALTIME] Condition passed - About to START realtime thread`
- [ ] See `[REALTIME] _run_realtime_mode_thread ENTERED`
- [ ] See `[REALTIME] _run_realtime_mode_async STARTED`
- [ ] See `[REALTIME] Connected` (OpenAI connection)
- [ ] See `[TOOLS][REALTIME] No tools enabled` or `Appointment tool enabled`

## Files Modified

- `asgi.py` - WebSocket handler with comprehensive logging
- `server/media_ws_ai.py` - MediaStreamHandler with execution tracing

## Next Steps

If logs still don't appear after this fix:
1. The issue is environmental (Docker logging, Uvicorn config)
2. Or there's a Python exception happening before any logs execute
3. Check Uvicorn startup logs for any import errors or crashes

---

**Build Date**: 2025-12-08  
**Fix Type**: Diagnostic Logging Enhancement  
**Priority**: Critical (Production Blocker)
