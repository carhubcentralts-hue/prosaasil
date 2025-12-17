# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 325: CALL CONFIGURATION - Optimal settings for Hebrew phone calls
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 MASTER AUDIO CONFIG - Single source of truth for all audio filtering
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_CONFIG = {
    "simple_mode": True,           # SIMPLE, ROBUST telephony mode - trust OpenAI VAD
    "audio_guard_enabled": False,  # DISABLED: No aggressive RMS/ZCR filtering
    "music_mode_enabled": False,   # DISABLED: No music detection (blocks speech)
    "noise_gate_min_frames": 0,    # DISABLED: No consecutive frame requirements
    "echo_guard_enabled": True,    # Minimal, conservative echo control only
    "frame_pacing_ms": 20,         # Standard telephony frame interval (20ms)
    # RMS Thresholds - Lowered for better microphone sensitivity (telephony)
    # 🔥 FIX: Further reduced for easier barge-in and better short sentence detection
    "vad_rms": 50,                 # VAD RMS threshold (lowered from 60 for easier barge-in)
    "rms_silence_threshold": 25,   # Pure silence threshold (lowered from 30)
    "min_speech_rms": 35,          # Minimum speech RMS (lowered from 40 for quiet callers)
    "min_rms_delta": 3.0,          # Min RMS above noise floor (lowered from 5.0)
}

# SIMPLE_MODE: Trust Twilio + OpenAI VAD completely
SIMPLE_MODE = AUDIO_CONFIG["simple_mode"]  # All audio passes through - OpenAI handles speech detection

# COST OPTIMIZATION
# 🔥 BUILD 341: AUDIO QUALITY FIX - Increased FPS limit to handle jitter
# Phone audio = 8kHz @ 20ms frames = 50 FPS nominal, but jitter can cause bursts
# 70 FPS = 40% headroom above nominal (allows ±20% timing variation)
# Calculation: 50 FPS * 1.4 = 70 FPS (handles worst-case burst scenarios)
# This prevents frame drops during normal operation while maintaining cost control
COST_EFFICIENT_MODE = True   # Enabled with higher limit to handle jitter
COST_MIN_RMS_THRESHOLD = 0   # No RMS gating - all audio passes through
COST_MAX_FPS = 70            # 70 FPS = 40% headroom for jitter (was 50)

# 🔥 BUILD 335: EXTENDED LIMITS - Allow up to 10 minutes for complex bookings!
# Only disconnect if customer asks or truly needs to hang up.
# These are ABSOLUTE safety limits to prevent infinite runaway costs.
MAX_REALTIME_SECONDS_PER_CALL = 600  # Max 10 minutes per call
MAX_AUDIO_FRAMES_PER_CALL = 42000    # 70 fps × 600s = 42000 frames maximum

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 350: BALANCED VAD THRESHOLDS - Optimized for Hebrew with noise resilience
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (based on OpenAI Realtime API best practices):
# - threshold 0.5: Balanced sensitivity for Hebrew short utterances while avoiding false positives
#   from background noise (research shows 0.3-0.5 for quiet environments, 0.6-0.7 for noisy)
# - silence_duration_ms 400: OpenAI recommends 250-400ms for short utterances in rapid exchanges
#   (too low causes premature cutoff, too high causes sluggish responses)
# - prefix_padding_ms 300: Standard padding (OpenAI default), sufficient for Hebrew syllables
#   (was 500ms but caused delayed speech start detection)
#
# Previous aggressive settings (0.45/600ms/500ms) caused:
# ❌ False positives from background noise being detected as speech
# ❌ Premature speech cutoff when users pause briefly
# ❌ System not responding at all during entire call
# ❌ Unwanted greeting interruptions from ambient sounds
#
# Current balanced settings (0.5/400ms/300ms) provide:
# ✅ Reliable detection of short Hebrew utterances ("כן", "לא", "איך עובדים")
# ✅ Noise resilience - ignores most background sounds
# ✅ Natural conversation flow - no premature cutoffs
# ✅ Fast response - 400ms silence is enough for turn-taking
# ═══════════════════════════════════════════════════════════════════════════════
SERVER_VAD_THRESHOLD = 0.5          # Balanced: detects speech without false positives (OpenAI best practice)
SERVER_VAD_SILENCE_MS = 400         # Optimal for short Hebrew utterances (OpenAI recommendation: 250-400ms)
SERVER_VAD_PREFIX_PADDING_MS = 300  # Standard padding, prevents delayed speech detection (OpenAI default)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 CRITICAL HOTFIX: AUDIO GUARD - DISABLED to prevent blocking real speech
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_GUARD_ENABLED = AUDIO_CONFIG["audio_guard_enabled"]  # Controlled by AUDIO_CONFIG
AUDIO_GUARD_MIN_SPEECH_FRAMES = 12  # Min consecutive frames to start sending (240ms)
AUDIO_GUARD_SILENCE_RESET_FRAMES = 20  # Silence frames to reset utterance (400ms)
AUDIO_GUARD_EMA_ALPHA = 0.12  # EMA alpha for noise floor smoothing
AUDIO_GUARD_MIN_VOICE_MS = 220  # Minimum voice duration before commit (ms)
AUDIO_GUARD_MIN_SILENCE_MS = 320  # Minimum silence duration to reset (ms)

# VAD CALIBRATION THRESHOLDS (used in media_ws_ai.py)
VAD_BASELINE_TIMEOUT = 80.0     # Baseline when calibration times out
VAD_ADAPTIVE_CAP = 120.0        # Maximum adaptive threshold
VAD_ADAPTIVE_OFFSET = 55.0      # noise_floor + this = dynamic threshold

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 350: BALANCED ECHO GATE - Protect against AI echo with noise resilience
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE:
# - RMS 200: Moderate sensitivity - allows real interruptions while ignoring ambient noise
#   (was 150 - too low, caused false triggers from background noise)
#   (was 320 originally - too high, required shouting to interrupt)
# - Frames 5: Requires 100ms of consistent audio to trigger (prevents spurious noise spikes)
#   (was 4 - too low, allowed single-frame noise to trigger)
#
# Previous aggressive setting (150.0) caused:
# ❌ Background noise triggering barge-in during AI greeting
# ❌ System interrupting itself from echo or ambient sounds
# ❌ Greeting not being read at all due to false triggers
#
# Current balanced setting (200.0) provides:
# ✅ Natural interruption capability - no need to shout
# ✅ Noise resilience - ignores ambient sounds and echo
# ✅ Consistent greeting delivery - completes unless user truly interrupts
# ═══════════════════════════════════════════════════════════════════════════════
ECHO_GATE_MIN_RMS = 200.0       # Moderate sensitivity: real interruptions without false triggers
ECHO_GATE_MIN_FRAMES = 5        # Requires 100ms consistent audio (prevents noise spikes)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 350: BALANCED BARGE-IN - Natural interruption with noise resilience
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE:
# - Frames 8: Requires 160ms of consistent speech to trigger interruption
#   (was 6/120ms - too low, caused false triggers from brief noises or speaker pauses)
#   (was 12/240ms originally - too high, felt unresponsive)
# - Debounce 350ms: Prevents rapid re-triggering while allowing natural follow-up
#   (was 300ms - too short, allowed unwanted double interruptions)
#   (was 400ms originally - felt slightly sluggish)
#
# Previous aggressive settings (6 frames/300ms) caused:
# ❌ AI interrupting mid-sentence when user pauses briefly
# ❌ False barge-in triggers from background noise
# ❌ Response flow disruption from spurious interruptions
# ❌ System not speaking at all during calls due to constant false triggers
#
# Current balanced settings (8 frames/350ms) provide:
# ✅ Natural interruption - responds to real user speech
# ✅ Noise resilience - ignores brief sounds and pauses
# ✅ Smooth conversation flow - allows natural speaking patterns
# ✅ No double triggers - proper debounce for follow-up responses
# ═══════════════════════════════════════════════════════════════════════════════
BARGE_IN_VOICE_FRAMES = 8   # Requires 160ms consistent speech (balanced: responsive without false triggers)
BARGE_IN_DEBOUNCE_MS = 350  # Debounce period prevents double triggers while allowing natural follow-up

# ═══════════════════════════════════════════════════════════════════════════════
# Legacy Audio Guard parameters (kept for compatibility)
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_GUARD_INITIAL_NOISE_FLOOR = 20.0
AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR = 4.0
AUDIO_GUARD_MIN_ZCR_FOR_SPEECH = 0.02
AUDIO_GUARD_MIN_RMS_DELTA = 5.0
AUDIO_GUARD_MUSIC_ZCR_THRESHOLD = 0.03
AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER = 15
AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES = 100

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 CRITICAL HOTFIX: MUSIC MODE - DISABLED to prevent speech misclassification
# ═══════════════════════════════════════════════════════════════════════════════
MUSIC_MODE_ENABLED = AUDIO_CONFIG["music_mode_enabled"]  # Controlled by AUDIO_CONFIG

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 CRITICAL HOTFIX: NOISE GATE - Disabled in Simple Mode
# ═══════════════════════════════════════════════════════════════════════════════
NOISE_GATE_MIN_FRAMES = AUDIO_CONFIG["noise_gate_min_frames"]  # 0 = disabled in Simple Mode
