# Testing Guide for TX Diagnostic Probes

## Quick Start

After deploying these changes, make a 15-second test call and check the logs.

## What to Look For

### During a Normal Call (AI Speaking)

You should see logs like this every second:

```
[TX_HEARTBEAT] alive=True, qsize=15, is_ai_speaking=True, active_response_id=resp_..., frames_sent=234
[ENQ_RATE] frames_enqueued_per_sec=50, qsize=12
```

### During the "Silent Bug" (TX=1, No Audio)

Look for one of these patterns:

#### Pattern 1: TX Loop Crashed
```
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, ...
[TX_CRASH] TX loop crashed with exception:
Traceback (most recent call last):
  ...
```

**What it means:** TX thread died. Fix the exception shown in the traceback.

---

#### Pattern 2: WebSocket Send Blocking
```
[TX_HEARTBEAT] alive=True, qsize=120, is_ai_speaking=True, ...
[TX_SEND_SLOW] type=media, send_ms=1523.4, qsize=120
[TX_SEND_SLOW] CRITICAL: send blocked for 1523ms! Dumping all thread stacks:
  ...
```

**What it means:** `ws.send()` is blocking the TX thread. Check:
- Network connectivity
- Twilio connection health
- Eventlet/gevent blocking

---

#### Pattern 3: Audio Not Entering Queue
```
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc, frames_sent=1
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
```

Plus in OpenAI logs you see:
```
response.audio.delta received: chunk#42, bytes=160
```

**What it means:** OpenAI is sending audio, but it's not being enqueued to `realtime_audio_out_queue`. Check:
- Audio guards/filters blocking audio
- Queue Full exceptions
- Event handler logic

---

## How to Collect Logs

### Option 1: Live Logs (Development)
```bash
# Watch logs in real-time
tail -f /var/log/prosaasil/app.log | grep -E "TX_HEARTBEAT|TX_CRASH|TX_SEND_SLOW|ENQ_RATE"
```

### Option 2: Post-Call Analysis (Production)
```bash
# Extract relevant logs for a specific call_sid
grep "call_sid_abc123" /var/log/prosaasil/app.log | \
  grep -E "TX_HEARTBEAT|TX_CRASH|TX_SEND_SLOW|ENQ_RATE|response.audio.delta" > /tmp/call_diagnostics.txt

# View the file
less /tmp/call_diagnostics.txt
```

### Option 3: Structured Search
```bash
# Check if TX loop is alive
grep "TX_HEARTBEAT" logs.txt

# Check for crashes
grep "TX_CRASH" logs.txt

# Check for send blocking
grep "TX_SEND_SLOW" logs.txt

# Check enqueue rate
grep "ENQ_RATE" logs.txt | tail -20
```

---

## Sample Diagnostic Session

### Scenario: "TX stays at 1, no audio"

**Step 1:** Check TX liveness
```bash
$ grep TX_HEARTBEAT logs.txt
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc, frames_sent=1
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc, frames_sent=1
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc, frames_sent=1
```

✅ TX loop is alive (not crashed). `frames_sent=1` confirms TX counter is stuck.

**Step 2:** Check enqueue rate
```bash
$ grep ENQ_RATE logs.txt | tail -5
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
```

❌ **ROOT CAUSE FOUND:** Audio is NOT being enqueued despite OpenAI sending `response.audio.delta`!

**Step 3:** Check OpenAI events
```bash
$ grep "response.audio.delta" logs.txt | head -5
[AI_TALK] Audio chunk from OpenAI: chunk#1, bytes=160
[AI_TALK] Audio chunk from OpenAI: chunk#2, bytes=160
[AI_TALK] Audio chunk from OpenAI: chunk#3, bytes=160
```

✅ OpenAI IS sending audio chunks.

**Conclusion:** Audio is being received from OpenAI but NOT enqueued to `realtime_audio_out_queue`. 

**Next steps:**
- Check if audio guards are blocking (SIMPLE_MODE vs guards)
- Check if `user_has_spoken` is False (pre-user guard)
- Check for Queue.Full exceptions
- Review event handler logic around lines 3920, 4002, 4018

---

## Expected Timeline (15-second call)

```
T+0.0s: [AUDIO_TX_LOOP] started
T+0.5s: [AUDIO_OUT_LOOP] Started - waiting for OpenAI audio
T+1.0s: [TX_HEARTBEAT] alive=True, qsize=0, ...
T+1.5s: [GREETING] Passing greeting audio to caller
T+1.5s: [ENQ_RATE] frames_enqueued_per_sec=50, qsize=12
T+2.0s: [TX_HEARTBEAT] alive=True, qsize=15, is_ai_speaking=True, frames_sent=50
T+2.5s: [ENQ_RATE] frames_per_sec=48, rx_qsize=8
...
T+15.0s: [AUDIO_TX_LOOP] exiting (frames_sent=750, call_sid=...)
```

If any of these patterns deviate, you've found the issue!

---

## Reporting Results

When reporting the bug, include:

1. **Call SID** for correlation
2. **30 lines of logs** around the silent period
3. **One-line conclusion:**
   - "TX crashed: [exception type]" 
   - "ws.send blocked: [duration]ms"
   - "Audio not enqueued despite delta events"
4. **Code location** if identified (line number)

Example report:
```
Call SID: CA123abc456def
Issue: Audio not enqueued despite delta events
Location: server/media_ws_ai.py line 3928 (pre-user guard)
Evidence: ENQ_RATE=0 while response.audio.delta chunks received

Logs:
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
[AI_TALK] Audio chunk from OpenAI: chunk#1, bytes=160
[GUARD] Blocking AI audio response before first real user utterance
...
```

This helps quickly identify and fix the root cause!
