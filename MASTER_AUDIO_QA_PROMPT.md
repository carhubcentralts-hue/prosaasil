# 🎯 MASTER PROMPT – Telephony Audio BUG HUNT + SIMPLE MODE, Human STT & Barge-in

@workspace

## Context:
- **Telephony**: Twilio WebSocket Media Streams (8kHz, PCMU μ-law, mono)
- **AI**: OpenAI Realtime API (audio + text + server VAD)
- **Backend**: Python
- **Multi-tenant**: Behavior, tone, and business logic are driven PER BUSINESS from DB (no hard-coded business rules).

## GLOBAL GOALS:
1. Fix the current audio bug: AI speech and greeting sound choppy, stops mid-sentence, restarts, or plays in weird chunks.
2. High-quality STT for phone calls (Hebrew, noisy, 8kHz).
3. Reliable, human-like barge-in (user can naturally interrupt the AI).
4. No robotic / choppy / fast audio.
5. No aggressive filters that drop real human speech.
6. Filler-only utterances like "אממ", "אההה", "אמממ…" do NOT trigger bot responses.
7. Conversation behavior feels human: waits, listens, doesn't jump on every sound.
8. All behavior is dynamic and driven by system prompt + per-business config (from DB), not hard-coded logic.

## IMPORTANT SCOPE:
- Do NOT change the high-level state machine / call lifecycle.
- Do NOT redesign business logic or timers.
- Focus ONLY on:
  - audio format
  - audio pacing
  - TX/RX audio pipeline (bug hunt!)
  - STT + VAD + barge-in behavior
  - filler / non-meaningful speech handling
  - system prompt structure & per-business behavior
  - ensuring Simple Mode (no guards) is respected everywhere.

---

## [0] CRITICAL AUDIO BUG HUNT – FIND AND FIX ROOT CAUSE

### Symptoms from logs & real calls:
- Greeting audio is sent repeatedly in many chunks:
  - `[GREETING] Passing greeting audio to caller ...` logged tens/hundreds of times.
- AI sometimes starts a sentence, then audio cuts, then later finishes the sentence → user hears broken / choppy speech.
- Logs show:
  - `💰 [FPS LIMIT] Throttling audio - 50 frames this second (max=50)`
  - `🔊 [REALTIME] response.audio.delta: ...` repeated many times interleaved with GREETING lines.
- STT looks fine (transcripts are correct), but audio playback to caller feels wrong.

### Hypothesis:
There is more than one TX path sending media frames to Twilio in parallel (or greeting path bypasses the paced TX loop), causing:
- Double-sending frames,
- Broken pacing,
- Choppy/fast/duplicated audio,
- Audio that pauses mid-sentence and then resumes.

### 0.1 TASK – VERIFY SINGLE TX LOOP ONLY
1. Locate ALL code paths that send media to Twilio WebSocket, e.g.:
   - Any direct `ws.send(...)` or `ws.send_json(...)` with:
     - `"event": "media"`
     - or Twilio media payloads (`"media": {"payload": ...}`).
2. Ensure there is exactly ONE canonical `audio_tx_loop` that:
   - Reads μ-law frames from a `tx_queue` (or equivalent),
   - Sends them to Twilio,
   - Enforces 20ms pacing per frame.
3. Refactor so that:
   - All components that want to play audio (greeting, AI responses, beeps, TTS fallback, etc.):
     - ONLY enqueue frames into `tx_queue`.
     - Never call `ws.send(...)` directly in a tight loop.
4. Remove or refactor any helper that does something like:

```python
for frame in frames:
    ws.send_json({"event": "media", ...})
```

→ This must instead be:

```python
for frame in frames:
    await tx_queue.put(frame)
```

and rely solely on `audio_tx_loop` for actual sending.

### 0.2 TASK – GREETING MUST USE TX LOOP (NO SPECIAL FAST-PATH)
1. Find the greeting-related code:
   - `play_greeting(...)`
   - any `[GREETING] Passing greeting audio...` log sites,
   - any function that handles Realtime `response.audio.delta` events for greeting.
2. Ensure:
   - Greeting audio is converted to μ-law frames (20ms, 160 bytes),
   - Those frames are only enqueued into `tx_queue`,
   - You do not have a separate "greeting loop" that sends frames directly to Twilio.
3. Eliminate patterns like:
   - "For each Realtime `response.audio.delta` → directly send to Twilio" AND "also push to TX loop".
   - There must be one path from Realtime to Twilio via TX queue.

### 0.3 TASK – CHECK FOR DUPLICATE PIPES / LOOPS
1. Search for:
   - `audio_tx_loop`
   - `send_audio_frame`
   - `send_pcm16_as_mulaw`
   - any other "sender" coroutine or function that might run in parallel.
2. Ensure:
   - Only one loop is running per call that sends Twilio media events.
   - Any other function that currently sends media directly is refactored to only enqueue.

### 0.4 TASK – LOGGING TO CONFIRM FIX

Add/verify concise logging:
- At TX loop start:
  - `[AUDIO_TX_LOOP] started (call_sid=..., frame_pacing=20ms)`
- When sending each frame batch (throttled log):
  - `[PIPELINE STATUS] sent={sent_count} blocked={blocked_count} ...`
- At TX loop end:
  - `[AUDIO_TX_LOOP] exiting (frames_enqueued=..., frames_sent=...)`

After fix, we expect:
- No massive repetition of `[GREETING] Passing greeting audio...` beyond the real greeting length.
- No double-sending of the same audio segments.
- AI audio should sound smooth, with stable pacing and no mid-sentence cut-offs.

**Do this bug-hunt FIRST**, then continue with the rest of the tasks below.

---

## [1] GLOBAL AUDIO MODE – SIMPLE, NO GUARD

We are in SIMPLE MODE. That must be a single source of truth and respected everywhere.

### Requirements:
1. Central `AUDIO_CONFIG` (already exists – verify and enforce):

```python
AUDIO_CONFIG = {
    "simple_mode": True,           # SIMPLE MODE ON
    "audio_guard_enabled": False,  # No RMS/ZCR filtering
    "music_mode_enabled": False,   # No music detection
    "noise_gate_min_frames": 0,    # No consecutive-frame gating
    "echo_guard_enabled": True,    # Minimal echo control only
    "frame_pacing_ms": 20,         # 20ms per frame (50 FPS telephony)
    # Telephony RMS thresholds (already lowered)
    "vad_rms": ...,
    "rms_silence_threshold": ...,
    "min_speech_rms": ...,
    "min_rms_delta": ...,
}
```

2. In ALL code paths (Twilio RX, Realtime bridge, barge-in, echo checks, etc):
   - If `AUDIO_CONFIG["simple_mode"]` is True:
     - Bypass AudioGuard logic completely.
     - Bypass Music Mode logic completely.
     - Bypass any "noise gate" logic that requires N consecutive frames.
     - Do NOT locally override guard flags (no local `audio_guard_enabled=True`).

3. Startup log MUST show:

```
[AUDIO_MODE] simple_mode=True, audio_guard_enabled=False,
             music_mode_enabled=False, noise_gate_min_frames=0
```

This guarantees:
- No speech frames are dropped by "smart" filters in SIMPLE MODE.
- We fully trust OpenAI's VAD and our own logic, not local audio guards.

---

## [2] INPUT AUDIO: Twilio → OpenAI Realtime (STT path)

### 2.1 Audio format (MUST):
- Twilio sends: 8kHz, μ-law (PCMU), mono.
- Realtime session MUST either:
  - `input_audio_format="g711_ulaw"`, OR
  - receive 16-bit PCM that we convert once from μ-law.
- No double conversions, no resampling to weird sample rates.

### 2.2 Frame handling:
- Twilio media → 20ms frames (160 μ-law bytes).
- For EACH incoming frame:
  - Do NOT buffer large chunks before sending.
  - Do NOT drop frames based on:
    - RMS threshold,
    - ZCR,
    - "music detection",
    - "insufficient_consecutive_frames".
  - In SIMPLE MODE:
    - Every frame that is not obviously silence/noise floor should be forwarded to Realtime.
    - Logging can show RMS and counters, but must NOT block sending.

### 2.3 Preprocessing (light / optional ONLY):
- **Allowed:**
  - Very soft normalization if RMS is extremely low or extremely high.
  - Optional high-pass filter ~150–200 Hz to remove hum.
- **NOT allowed in SIMPLE MODE:**
  - Hard RMS thresholds that drop entire frames.
  - Frequency cuts inside 300–3400 Hz band.
  - Any noise gate that discards full frames based on short-term RMS.

### 2.4 Turn detection / STT:
- Realtime `turn_detection` (server VAD) is used ONLY for:
  - end-of-user-turn detection,
  - barge-in timing,
  - state transitions.
- NOT for muting / dropping incoming audio frames.

Telephony-friendly VAD:
- threshold ≈ 0.4 (more sensitive)
- min_consecutive_frames = 1
- prefix_padding_ms ≈ 300
- silence_duration_ms ≈ 500–800

---

## [3] OUTPUT AUDIO: OpenAI → Twilio (AI voice path)

This is critical for avoiding robotic / fast / choppy audio.

### 3.1 Single paced TX loop:
There must be ONE canonical TX loop responsible for sending ALL audio frames to Twilio.

This loop:
- dequeues one frame from `tx_queue`,
- sends it to Twilio WebSocket,
- waits `FRAME_INTERVAL` (20ms) before sending the next.

Conceptual:

```python
FRAME_INTERVAL = AUDIO_CONFIG["frame_pacing_ms"] / 1000.0  # 0.02s
FRAME_SIZE = 160  # μ-law bytes per 20ms @ 8kHz

async def audio_tx_loop():
    next_deadline = time.monotonic()
    while running:
        frame = await tx_queue.get()
        if frame is None:
            break

        # Send frame as "media" event with base64 μ-law payload
        await ws.send_json(...)

        next_deadline += FRAME_INTERVAL
        delay = next_deadline - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
```

### 3.2 No burst sending:
- Any helper that converts PCM→μ-law (greeting, normal responses, beeps, fallback TTS) must:
  - Split PCM into 20ms μ-law frames (160 bytes),
  - Enqueue into `tx_queue`,
  - Let the TX loop handle timing.
- No tight for/while loops with consecutive `ws.send(...)` of media frames.

### 3.3 Output format:
- AI output must be μ-law 8kHz mono, base64-encoded in Twilio `"media.payload"`.
- If Realtime gives PCM:
  - convert to μ-law once,
  - slice into 160-byte frames,
  - push to `tx_queue`.

---

## [4] BARGE-IN LOGIC: Two-Phase, Audio-First

Goal: User always "wins" when speaking over AI, but we don't overreact to "אממ…" and noise.

We want a two-phase barge-in:

### PHASE A – AUDIO-BASED CANDIDATE
- While AI is speaking (`is_ai_speaking=True`):
  - Continuously monitor incoming Twilio frames:
    - If `RMS > (noise_floor + TELEPHONY_DELTA)`
    - For at least ~200–300ms accumulated audio
    - Mark `candidate_barge_in = True`.
  - Optionally: temporarily lower AI volume (ducking) instead of immediate cut.

### PHASE B – TRANSCRIPTION-BASED CONFIRMATION

When Realtime completes transcription for that chunk:

```python
def on_transcription_completed(text):
    normalized = normalize(text)

    if not is_valid_transcript(normalized):
        candidate_barge_in = False
        # DO NOT cancel AI, DO NOT flush queue.
        return

    if candidate_barge_in:
        # This is a real barge-in:
        cancel_active_response()
        flush_tx_queue()
        user_has_spoken = True
        barge_in_events += 1
```

Definition of `is_valid_transcript(text)`:
- Returns False if:
  - text is empty / whitespace
  - `len(text) < 3`
  - text consists only of filler words like:
    - `["אמ", "אם", "אממ", "אמממ", "אה", "אהה", "אההה", "הממ", "אהם", "אהממ"]`
  - text is only sound-like vocalizations with no semantic content.
- Returns True if:
  - contains at least one meaningful word (not only filler),
  - examples that should be valid:
    - "אממ כן"
    - "אממ אני רוצה לשמוע עוד"
    - "אהה טוב, תסביר לי איך זה עובד"

Behavior:
- Filler-only = NO response, keep listening.
- Filler + real text = VALID USER TURN → barge-in, full AI answer.

---

## [5] GREETING + PROTECTION
- Greeting audio must go through the SAME TX loop (no special fast-path).
- During greeting:
  - It's OK to block sending user audio to OpenAI (`[GREETING PROTECT] Blocking audio input`) if that's desired.
- AFTER `greeting_done`:
  - Audio to OpenAI must be resumed (already logged: `[GREETING PROTECT] Greeting done - resuming audio to OpenAI`).
  - Ensure there is no leftover protection that continues blocking audio or barge-in after greeting is done.

Also verify:
- Barge-in is disabled only during greeting, and correctly enabled afterward:
  - `✅ [GREETING] Barge-in now ENABLED for rest of call`

---

## [6] SYSTEM PROMPT & PER-BUSINESS BEHAVIOR

We want ALL conversation behavior to be driven by:
- Global system prompt (telephony + AI behavior).
- Per-business "business prompt" loaded from DB, including:
  - business name, industry, services, tone,
  - whether this is lead-gen / support / scheduling, etc.
  - permissions (e.g. can schedule appointments, can take payments, etc.)

### 6.1 Layered SYSTEM PROMPT

Build a SYSTEM PROMPT with layered structure:

**LAYER 1 – Core role:**
- You are a human-like digital assistant for phone calls.
- You speak and understand Hebrew (and other languages if needed).
- You are connected to a CRM/call-center platform.
- You must sound natural: calm, clear, polite, never robotic.

**LAYER 2 – Telephony context:**
- You listen to narrow-band telephony audio (8kHz, G.711 μ-law).
- Expect line noise, echoes, distortions.
- Focus on understanding user intent, even if words are imperfect.
- Do not get confused by "אממ…", "אה…", "הממ…", background sounds.

**LAYER 3 – Conversation behavior:**
- Let the caller finish: do not interrupt mid-sentence.
- Do not answer to filler-only utterances ("אממ", "אההה", breathing).
- If the user is silent, wait a short moment, then ask a short follow-up.
- When the user asks a question – respond directly, then offer the next helpful step.
- Always explain what you're doing in simple language (like a human).
- Keep answers concise unless user asks for details.

**LAYER 4 – Business-specific logic (dynamic, from DB):**
- Insert per-business prompt:
  - business name
  - value proposition
  - what the assistant is allowed to do:
    - collect lead details (name, phone, city, service),
    - schedule appointments,
    - answer FAQs,
    - transfer to human, etc.
  - DO NOT hard-code cities or services in the code.
  - Use only what is provided from the business prompt! Dynamic by each business! Not hardcoded in code!

For each call:
- System prompt = CORE + TELEPHONY + CONVERSATION BEHAVIOR + BUSINESS PROMPT (from DB).
- No business-specific logic in code – only in prompts + DB.

---

## [7] MONITORING & METRICS

Per call, log:

**STT:**
- `stt_utterances_total`
- `stt_empty_count`
- `stt_very_short_count` (len < 5 chars)
- `stt_filler_only_count` (e.g. "אממ", "אההה" only)

**Audio pipeline:**
- `frames_in_from_twilio`
- `frames_forwarded_to_realtime`
- `frames_dropped_by_filters` (should be ~0 in SIMPLE MODE)

**Barge-in:**
- `barge_in_events` count

End-of-call summary example:

```
[CALL_METRICS] stt_utterances=..., empty=..., short=..., filler_only=...,
               frames_in=..., frames_forwarded=..., frames_dropped=...,
               barge_in_events=...
```

If `frames_dropped_by_filters > 0` in SIMPLE MODE → log WARNING.

---

## TASKS FOR YOU (Copilot):

1. **Bug Hunt & TX Pipeline**
   - Locate all code paths for:
     - Twilio → Realtime audio,
     - Realtime → Twilio audio,
     - Greeting playback,
     - Any direct Twilio media sending.
   - Ensure:
     - Only ONE paced TX loop sends media to Twilio.
     - Greeting and all other audio sources use the TX queue.
     - No burst/parallel sends.

2. **SIMPLE MODE**
   - Ensure SIMPLE MODE is respected:
     - `audio_guard_enabled=False`
     - `music_mode_enabled=False`
     - `noise_gate_min_frames=0`
     - No re-enabling of guards in deeper functions.

3. **STT & Barge-in**
   - Implement / refine:
     - Two-phase barge-in (audio-based candidate + transcription-based confirmation).
     - Filler-only detection (do not respond to "אממ"/"אההה" alone).
     - Logic that treats "אממ כן…", "אממ אני רוצה…" as valid utterances.

4. **System Prompt & Business Config**
   - Implement layered SYSTEM PROMPT:
     - core role,
     - telephony context,
     - conversation behavior,
     - per-business configuration (loaded from DB).

5. **Metrics**
   - Add / verify metrics:
     - STT quality metrics,
     - frames in/out/dropped,
     - barge_in_events,
     - end-of-call summary log.

Then:
- Show me the key functions before/after (audio RX, TX loop, greeting path, barge-in, system prompt builder).
- Explain how each change:
  - fixes the audio bug (no more choppy / restarting sentences),
  - improves STT quality,
  - prevents choppy/robotic audio,
  - handles fillers correctly,
  - keeps conversation human-like and dynamic per business configuration.

---

זהו.
ככה הוא חייב קודם לצוד את הבאג בסאונד (TX כפול / גריטינג עוקף לופ), ואז לבנות סביב זה Simple Mode נקי, ברג־אין חכם, ופילטר פילרים כמו בן אדם.
