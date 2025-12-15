# TX Audio Silence Diagnostic Probes

## Overview

This document describes the diagnostic probes added to locate the root cause of "complete silence" despite receiving `response.audio.delta` events from OpenAI. The TX counter stays at 1, suggesting audio transmission is blocked.

## Problem Statement

**Symptoms:**
- OpenAI sends `response.audio.delta` events (audio chunks from AI)
- TX counter stays at 1 (no frames transmitted to Twilio)
- Complete silence on the call

**Goal:** Find WHERE the audio pipeline is blocked:
1. TX loop died (exception/exit)
2. TX loop alive but `ws.send` is blocking
3. Audio not entering TX queue (bridge issue)

## Probes Implemented

### 📊 PROBE 1: TX Liveness Probe

**Location:** `_tx_loop()` in `server/media_ws_ai.py`

**Purpose:** Prove TX loop is alive and responsive

**Implementation:**
- Prints heartbeat every 1 second
- Shows: `alive=True, qsize, is_ai_speaking, active_response_id, frames_sent`

**Log Pattern:**
```
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc123, frames_sent=42
```

**Diagnosis:**
- ✅ **Heartbeat present during silence** → TX loop is alive (not crashed)
- ❌ **Heartbeat stops** → TX thread died/exited (check PROBE 2 for crash)

---

### 🚨 PROBE 2: TX Crash Probe

**Location:** `_tx_loop()` in `server/media_ws_ai.py`

**Purpose:** Catch and log TX loop crashes with full traceback

**Implementation:**
- Wraps entire TX loop in `try/except Exception`
- Prints `[TX_CRASH]` with full traceback before re-raising

**Log Pattern:**
```
[TX_CRASH] TX loop crashed with exception:
Traceback (most recent call last):
  File "server/media_ws_ai.py", line 11720, in _tx_loop
    ...
[TX_CRASH] Exception type: ValueError
[TX_CRASH] Exception message: stream_sid is None
```

**Diagnosis:**
- ✅ **No TX_CRASH logs** → TX loop didn't crash
- ❌ **TX_CRASH appears** → Root cause is exception in TX loop (see traceback)

---

### ⏱️ PROBE 3: Send Blocking Probe

**Location:** `_tx_loop()` in `server/media_ws_ai.py`

**Purpose:** Detect when `ws.send()` blocks the TX thread

**Implementation:**
- Measures time for every `_ws_send()` call
- Logs if send takes >50ms
- Dumps all thread stacks if send >500ms (once per call)

**Log Pattern:**
```
[TX_SEND_SLOW] type=media, send_ms=127.3, qsize=45
```

Or for severe blocking:
```
[TX_SEND_SLOW] CRITICAL: send blocked for 1523ms! Dumping all thread stacks:
  Thread: MainThread (id=139876543210)
  File "server/media_ws_ai.py", line 1464, in _safe_ws_send
    self._ws_send_method(data)
  ...
```

**Diagnosis:**
- ✅ **No TX_SEND_SLOW logs** → `ws.send` is fast (<50ms)
- ❌ **TX_SEND_SLOW appears** → WebSocket send is blocking TX loop
  - If >500ms → See stacktrace to find what's blocking the socket

---

### 📥 PROBE 4: Queue Flow Probe

**Location:** 
- Enqueue side: Where `realtime_audio_out_queue.put_nowait()` is called (3 locations in OpenAI event handler)
- Dequeue side: `_realtime_audio_out_loop()` where frames are dequeued

**Purpose:** Verify audio is entering the queue from OpenAI bridge

**Implementation:**
- Tracks frames enqueued per second to `realtime_audio_out_queue`
- Logs every 1 second with queue size

**Log Pattern (Enqueue side):**
```
[ENQ_RATE] frames_enqueued_per_sec=50, qsize=12
```

**Log Pattern (Dequeue side):**
```
[ENQ_RATE] frames_per_sec=50, rx_qsize=5
```

**Diagnosis:**
- ✅ **ENQ_RATE > 0 during silence** → Audio IS entering queue (problem is downstream)
- ❌ **ENQ_RATE = 0 during delta events** → Bridge not enqueuing (OpenAI event handler issue)
  - Check if `response.audio.delta` events are being received
  - Check if frames are being filtered/dropped before enqueue

---

## Diagnostic Flow

When you see "silence despite response.audio.delta":

### Step 1: Check TX Liveness
```
grep "TX_HEARTBEAT" logs.txt
```
- **Found heartbeats** → TX alive, go to Step 2
- **No heartbeats** → TX died, check Step 4 for crash

### Step 2: Check Queue Flow
```
grep "ENQ_RATE" logs.txt | tail -20
```
- **frames_enqueued_per_sec > 0** → Audio entering queue, go to Step 3
- **frames_enqueued_per_sec = 0** → Bridge not enqueuing despite delta
  - Root cause: OpenAI event handler blocking or filtering audio

### Step 3: Check Send Blocking
```
grep "TX_SEND_SLOW" logs.txt
```
- **Found TX_SEND_SLOW** → WebSocket send is blocking
  - If >500ms, see stacktrace for root cause
  - Likely: Network issue, eventlet blocking, or Twilio connection dead
- **Not found** → Send is fast, check TX queue size in heartbeat

### Step 4: Check TX Crash
```
grep "TX_CRASH" logs.txt
```
- **Found TX_CRASH** → TX loop crashed with exception
  - See traceback for root cause
  - Fix the bug and redeploy

---

## Expected Behavior (Healthy Call)

During AI speech, you should see:

```
[ENQ_RATE] frames_enqueued_per_sec=50, qsize=12        # ~50 fps = 1 second of audio
[TX_HEARTBEAT] alive=True, qsize=15, is_ai_speaking=True, active_response_id=resp_123, frames_sent=234
[ENQ_RATE] frames_per_sec=48, rx_qsize=8                # Slight variance is normal
```

No `TX_SEND_SLOW`, no `TX_CRASH`, consistent frame rates.

---

## Acceptance Criteria

After deploying these probes, during a 15-second call with silence:

You will get ONE of these diagnostics:

1. **TX_CRASH with traceback** → TX loop died
2. **TX_SEND_SLOW with stacktrace** → `ws.send` blocking
3. **ENQ_RATE = 0 despite delta** → Bridge not enqueuing

Provide:
- 30 lines of logs around the event
- One-line conclusion: "crash / send-block / enqueue-missing"
- Code location (line number) where issue occurs

---

## Minimal Changes Guarantee

These probes add ONLY diagnostic logging:
- ✅ No logic changes
- ✅ No new features
- ✅ No refactoring
- ✅ Logs use `_orig_print()` to bypass DEBUG mode
- ✅ All probes are deterministic (no random sampling)

The probes will help identify the exact failure point without changing behavior.
