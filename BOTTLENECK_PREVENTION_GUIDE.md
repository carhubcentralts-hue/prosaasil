# Code Sections for Additional Bottleneck Prevention

## Status: Core AttributeError Fix is LOCKED ✅

The critical fix is complete and verified:
- ✅ Counters initialized in `__init__` (line 1809-1810)
- ✅ Direct increments with no getattr masking (lines 4901, 8635)
- ✅ Queue backlog monitoring (warn-only with full context)
- ✅ Thread management (per-instance guards with proper cleanup)

---

## Code Sections for Next 5 Requirements

### 1. response.create Function - Prevent Duplicates

**Location**: `server/media_ws_ai.py` lines 3651-3750

**Current Code**:
```python
async def trigger_response(self, reason: str, client=None, is_greeting: bool = False, force: bool = False) -> bool:
    """
    🎯 BUILD 200: Central function for triggering response.create
    
    ALL response.create calls MUST go through this function!
    """
    # Use stored client if not provided
    _client = client or self.realtime_client
    if not _client:
        print(f"⚠️ [RESPONSE GUARD] No client available - cannot trigger ({reason})")
        return False
    
    # 🔥 CRITICAL SESSION GATE: Block response.create until session is confirmed
    if not getattr(self, '_session_config_confirmed', False):
        # ... session checks ...
        return False
    
    # 🔥 CRITICAL GUARD: Block response.create while user is speaking
    if getattr(self, 'user_speaking', False) and not is_greeting:
        print(f"🛑 [RESPONSE GUARD] USER_SPEAKING=True - blocking response until speech complete ({reason})")
        return False
    
    # 🛡️ GUARD 0.25: BUILD 310 - Block new AI responses when hangup is pending
    if getattr(self, 'pending_hangup', False):
        print(f"⏸️ [RESPONSE GUARD] Hangup pending - blocking new responses ({reason})")
        return False
```

**What to Add** (after line 3719):
```python
    # 🔥 NEW: DUPLICATE RESPONSE GUARD - Prevent concurrent responses
    # Check if there's already an active response in progress
    current_status = getattr(self, 'active_response_status', None)
    current_id = getattr(self, 'active_response_id', None)
    
    if current_status == "in_progress" and not is_greeting and not force:
        # There's already a response being generated - must cancel or wait
        print(f"🚨 [RESPONSE_GUARD] BLOCKED duplicate response.create | "
              f"reason={reason}, active_id={current_id[:8] if current_id else 'none'}, "
              f"active_status={current_status}")
        
        # Option 1: Block and return False (safest - let barge-in handler cancel)
        return False
        
        # Option 2: Auto-cancel previous and proceed (more aggressive)
        # if current_id and _client:
        #     await _client.send_event({"type": "response.cancel"})
        #     self.active_response_status = "cancelled"
        #     print(f"🪓 [AUTO_CANCEL] Cancelled {current_id[:8]}... to create new response")
```

**Log to Add** (before the actual send_event at line ~3751):
```python
    # Log the response.create with full context
    tx_q_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
    out_q_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
    is_speaking = self.is_ai_speaking_event.is_set() if hasattr(self, 'is_ai_speaking_event') else False
    
    _orig_print(
        f"🎯 [RESPONSE_CREATE] reason={reason}, "
        f"prev_active={getattr(self, 'active_response_id', 'none')[:8] if getattr(self, 'active_response_id', None) else 'none'}, "
        f"is_ai_speaking={is_speaking}, "
        f"tx_q={tx_q_size}, out_q={out_q_size}",
        flush=True
    )
```

---

### 2. response.audio.delta Handler - Bind is_ai_speaking to response_id

**Location**: `server/media_ws_ai.py` lines 4759-4900

**Current Code** (simplified):
```python
if event_type == "response.audio.delta":
    audio_b64 = event.get("delta", "")
    response_id = event.get("response_id", "")
    if audio_b64:
        # ... various guards ...
        
        # 🔥 STATE FIX: This is the CORRECT place to set is_ai_speaking (not on response.created)
        if not self.is_ai_speaking_event.is_set():
            # ... first delta logging ...
            print(f"🔊 [STATE] AI started speaking (first audio.delta) - is_ai_speaking=True")
            self.ai_speaking_start_ts = now
            # ... more setup ...
        
        # 🔥 BARGE-IN FIX: Ensure flag is ALWAYS set (safety redundancy)
        self.is_ai_speaking_event.set()  # Thread-safe: AI is speaking
```

**What to Change**:
```python
if event_type == "response.audio.delta":
    audio_b64 = event.get("delta", "")
    response_id = event.get("response_id", "")
    if audio_b64:
        # 🔥 NEW: STRICT BINDING - Only set is_ai_speaking for active response_id
        current_active_id = getattr(self, 'active_response_id', None)
        
        # Verify this delta belongs to the currently active response
        if response_id != current_active_id:
            print(f"⚠️ [AUDIO_DELTA_SKIP] Ignoring delta from non-active response | "
                  f"delta_resp={response_id[:8] if response_id else 'none'}, "
                  f"active={current_active_id[:8] if current_active_id else 'none'}")
            continue  # Skip this delta - not from active response
        
        # ... guards ...
        
        # Set is_ai_speaking ONLY for first delta of THIS response_id
        if not self.is_ai_speaking_event.is_set():
            print(f"🔊 [STATE] AI started speaking | response_id={response_id[:8]}...")
            self.ai_speaking_start_ts = now
            self.ai_speaking_start_ts = now
            self.speaking = True
            self._last_ai_audio_start_ts = now
            # 🔥 NEW: Bind speaking flag to this response_id
            self._speaking_response_id = response_id
        
        # Continue to set the event (but only for active response)
        self.is_ai_speaking_event.set()
```

---

### 3. response.audio.done Handler - Only Clear for Matching response_id

**Location**: `server/media_ws_ai.py` lines 4994-5095

**Current Code** (simplified):
```python
elif event_type in ("response.audio.done", "response.output_item.done"):
    # ... greeting lock handling ...
    
    # 🎯 Mark AI response complete
    if self.is_ai_speaking_event.is_set():
        print(f"🔇 [REALTIME] AI stopped speaking ({event_type})")
    self.is_ai_speaking_event.clear()  # Thread-safe: AI stopped speaking
    self.speaking = False
```

**What to Change**:
```python
elif event_type in ("response.audio.done", "response.output_item.done"):
    done_resp_id = event.get("response_id") or (event.get("response", {}) or {}).get("id")
    
    # ... greeting lock handling ...
    
    # 🔥 NEW: STRICT BINDING - Only clear is_ai_speaking for matching response_id
    speaking_resp_id = getattr(self, '_speaking_response_id', None)
    
    if self.is_ai_speaking_event.is_set():
        # Only clear if this audio.done is for the response that's currently speaking
        if speaking_resp_id and done_resp_id and speaking_resp_id != done_resp_id:
            print(f"⚠️ [AUDIO_DONE_SKIP] Ignoring audio.done from non-speaking response | "
                  f"done_resp={done_resp_id[:8] if done_resp_id else 'none'}, "
                  f"speaking={speaking_resp_id[:8] if speaking_resp_id else 'none'}")
            # Don't clear is_ai_speaking - wrong response_id
        else:
            # This is the audio.done for the currently speaking response
            print(f"🔇 [STATE] AI stopped speaking | response_id={done_resp_id[:8] if done_resp_id else 'unknown'}...")
            self.is_ai_speaking_event.clear()
            self.speaking = False
            self._speaking_response_id = None  # Clear binding
    
    # ... rest of handler ...
```

---

### 4. Enhanced Backlog Diagnostics

**New Helper Method** (add after `_check_queue_backlog` around line 2180):

```python
def _log_pipeline_metrics(self) -> None:
    """
    🔥 PIPELINE DIAGNOSTICS: Log comprehensive metrics to identify bottlenecks
    Distinguishes between: OpenAI slow, Twilio slow, CPU/event loop congestion
    
    Call this once every 3 seconds max (throttled)
    """
    now = time.monotonic()
    if now - getattr(self, '_last_pipeline_metrics_log', 0) < 3.0:
        return  # Throttled
    
    self._last_pipeline_metrics_log = now
    
    try:
        # Queue sizes
        tx_q_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
        out_q_size = self.realtime_audio_out_queue.qsize() if hasattr(self, 'realtime_audio_out_queue') else 0
        
        # Calculate FPS (frames per second) for TX
        frames_sent = getattr(self, 'tx', 0)
        elapsed = now - getattr(self, '_pipeline_metrics_start', now)
        avg_tx_fps = frames_sent / elapsed if elapsed > 0 else 0
        
        # Frames sent in last 3 seconds
        last_frames = frames_sent - getattr(self, '_pipeline_last_frames', 0)
        self._pipeline_last_frames = frames_sent
        
        # WebSocket send blocking time (if tracked)
        ws_block_ms = getattr(self, '_last_ws_send_block_ms', 0)
        
        # OpenAI audio delta rate (if tracked)
        delta_count = getattr(self, '_openai_audio_chunks_received', 0)
        delta_rate = delta_count / elapsed if elapsed > 0 else 0
        
        # Call context
        call_sid_short = self.call_sid[:8] if hasattr(self, 'call_sid') and self.call_sid else 'unknown'
        is_speaking = self.is_ai_speaking_event.is_set() if hasattr(self, 'is_ai_speaking_event') else False
        
        _orig_print(
            f"📊 [PIPELINE] call={call_sid_short} | "
            f"tx_q={tx_q_size} out_q={out_q_size} | "
            f"tx_fps={avg_tx_fps:.1f} frames_3s={last_frames} | "
            f"ws_block={ws_block_ms:.1f}ms delta_rate={delta_rate:.1f}/s | "
            f"ai_speaking={is_speaking}",
            flush=True
        )
        
        # Initialize start time if not set
        if not hasattr(self, '_pipeline_metrics_start'):
            self._pipeline_metrics_start = now
            
    except Exception as e:
        # Don't let metrics crash the call
        pass
```

**Where to Call It**: In the main event loop around line 3850, add:
```python
# Log pipeline metrics periodically
self._log_pipeline_metrics()
```

---

### 5. Verify TX Loop is Clean (No Blocking)

**TX Loop Location**: `server/media_ws_ai.py` lines 14024-14090

**Current Code Review**:
```python
def _tx_loop(self):
    """
    ✅ ZERO LOGS INSIDE: Clean TX loop - take frame, send to Twilio, sleep 20ms
    
    NO LOGS, NO WATCHDOGS, NO STALL RECOVERY, NO FLUSH
    Only: get frame → send → sleep
    """
    # ... setup ...
    
    try:
        while self.tx_running or not self.tx_q.empty():
            # Get frame
            item = self.tx_q.get(timeout=0.5)
            
            # Send frame to Twilio WS
            success = self._ws_send(json.dumps(item))
            
            if success:
                self.tx += 1
            
            # Strict 20ms timing
            next_deadline += FRAME_INTERVAL
            delay = next_deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
```

**✅ VERIFIED CLEAN**: No DB calls, no HTTP, no heavy work. Only get/send/sleep.

**Audio Out Loop Location**: Lines 7735-7850

**Review**: Also clean - just dequeues from `realtime_audio_out_queue` and enqueues to `tx_q`.

---

## Summary

**Core Fix Status**: ✅ LOCKED - AttributeError prevention complete

**Next 5 Requirements** (exact locations provided above):
1. ✅ Code for duplicate response.create prevention (add at line ~3719)
2. ✅ Code for is_ai_speaking binding to response_id (modify lines 4845-4861, 5028-5030)
3. ✅ Code for enhanced pipeline diagnostics (new method after line 2180)
4. ✅ TX loops verified clean (no changes needed)
5. ✅ Cleanup already has proper thread joins and flag clearing (lines 8094-8109)

**All code sections ready for implementation.**
