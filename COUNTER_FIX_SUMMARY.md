# Critical Fix Summary: AttributeError realtime_audio_in_chunks

## Problem
`AttributeError: 'MediaStreamHandler' object has no attribute 'realtime_audio_in_chunks'`
- Crashed at line ~8565 in `run()` method
- Caused Twilio "Application error" messages
- Primarily affected outbound calls (different initialization paths)

## Solution Summary

### ✅ 1. Counter Initialization in `__init__` (Single Source of Truth)

**Location**: `server/media_ws_ai.py` lines 1806-1814

```python
# 🔥 CRITICAL FIX: Initialize audio counters in __init__ to prevent AttributeError
# These counters MUST exist for every call direction (inbound/outbound)
# Previously initialized in _run_realtime_mode_async which could run after first use
self.realtime_audio_in_chunks = 0   # Count of audio chunks received from Twilio
self.realtime_audio_out_chunks = 0  # Count of audio chunks sent to Twilio

# 🔥 NEW: Initialize backlog monitoring timestamps
self._last_backlog_warning = 0.0  # For tx_q backlog warnings
self._last_realtime_backlog_warning = 0.0  # For realtime_audio_out_queue backlog warnings
```

**Why this works**:
- Counters exist from the moment `MediaStreamHandler(ws)` is created
- No race condition - guaranteed to exist before `run()` or any async method
- Works for both inbound and outbound calls

---

### ✅ 2. Direct Increment (No getattr Masking)

**Location 1**: `server/media_ws_ai.py` line 8635 (inbound audio)

```python
if et == "media":
    self.rx += 1
    # Counter initialized in __init__ - direct increment (no getattr masking)
    self.realtime_audio_in_chunks += 1
```

**Location 2**: `server/media_ws_ai.py` line 4901 (outbound audio)

```python
# Counter initialized in __init__ - direct increment (no getattr masking)
self.realtime_audio_out_chunks += 1
```

**Why direct increment**:
- Using `getattr(..., 0) + 1` masks bugs - if counter is missing, you get silent failures
- Direct `+= 1` fails fast if counter is missing (which it never is now)
- Clear, simple, no overhead

---

## Verification Checklist ✅

1. **Counters exist in `__init__` (always)** ✅
2. **No repeated getattr()+1—only direct increments** ✅
3. **Backlog monitor is warn-only (no drops)** ✅
4. **Double-loop guards are per-call instance** ✅
5. **Pre-deploy gate enforced** ✅

## Status: LOCKED 🔒

All critical requirements addressed. Production-ready.
