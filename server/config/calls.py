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
# 🔥 STABLE VAD CONFIGURATION - Production-ready values for Hebrew calls
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (updated per new requirements):
# - threshold 0.91: LESS SENSITIVE - filters noise better, prevents false triggers
# - silence_duration_ms 650: LONGER WAIT - doesn't cut off speech too early
# - prefix_padding_ms 300: Standard padding for Hebrew syllables (unchanged)
# - create_response: true (automatic response generation on turn end)
#
# These updated values prevent:
# ❌ Transcription triggering on background noise (too sensitive VAD)
# ❌ Transcription cutting mid-sentence (too short silence threshold)
# ❌ False speech detection from ambient sounds
#
# Current stable settings (0.91/650ms/300ms) provide:
# ✅ Less sensitive VAD - only real speech triggers transcription
# ✅ Longer silence wait - allows natural pauses in Hebrew speech
# ✅ Reliable detection of intentional speech (not noise)
# ✅ Natural conversation flow with proper turn-taking
# ═══════════════════════════════════════════════════════════════════════════════
SERVER_VAD_THRESHOLD = 0.91         # Less sensitive: filters noise better (was 0.50)
SERVER_VAD_SILENCE_MS = 650         # Longer wait before cutting (was 500)
SERVER_VAD_PREFIX_PADDING_MS = 300  # Standard padding for Hebrew (unchanged)

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
# 🔥 GREETING FIX: BALANCED ECHO GATE - Protect greeting from false triggers
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (based on log analysis):
# - RMS 200: Balanced sensitivity - real speech passes, echo/noise blocked
#   (was 150 - too low, caused greeting interruption from background noise)
# - Frames 5: Requires 100ms of consistent audio (prevents single-frame noise spikes)
#   (was 4 - too low, allowed brief echo to trigger false speech_started)
#
# Log analysis showed:
# ❌ Greeting interrupted by echo/ambient noise (RMS < 200)
# ❌ speech_started fired within first 200ms of greeting (before real user speech)
#
# Current balanced setting (200.0/5 frames) provides:
# ✅ Greeting protection - ignores echo and background noise
# ✅ Natural interruption - real user speech (RMS > 200) can still interrupt
# ✅ Consistent greeting delivery - completes unless user truly speaks
# ═══════════════════════════════════════════════════════════════════════════════
ECHO_GATE_MIN_RMS = 200.0       # Balanced: real speech without echo/noise false triggers
ECHO_GATE_MIN_FRAMES = 5        # Requires 100ms consistent audio (prevents greeting interruption)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 GREETING FIX: BALANCED BARGE-IN - Protect greeting, allow natural interruption
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (updated per new requirements):
# - Frames 3: Requires 60ms of consistent speech to trigger interruption (was 8 frames/160ms)
#   Lower threshold makes barge-in more responsive - trusts speech_started event more
# - Debounce 350ms: Prevents rapid re-triggering after barge-in (unchanged)
#
# NEW APPROACH:
# ❌ OLD: Required 160ms of voice (8 frames) before barge-in
# ✅ NEW: Reduced to 60ms (3 frames) - trust speech_started event primarily
#
# Golden Rule: speech_started => cancel ALWAYS when active_response_id exists
# - voice_frames is only used for supplementary validation
# - Primary trigger is speech_started event itself
#
# Current settings (3 frames/350ms) provide:
# ✅ Faster barge-in response (60ms vs 160ms)
# ✅ More reliable interruption (trusts OpenAI VAD)
# ✅ No double triggers - 350ms debounce prevents rapid re-triggering
# ═══════════════════════════════════════════════════════════════════════════════
BARGE_IN_VOICE_FRAMES = 3   # Reduced to 60ms - trust speech_started event (was 8)
BARGE_IN_DEBOUNCE_MS = 350  # Prevents double triggers after barge-in (unchanged)

# Greeting-specific protection (applied during greeting playback only)
GREETING_PROTECT_DURATION_MS = 500  # Protect greeting for first 500ms
GREETING_MIN_SPEECH_DURATION_MS = 250  # Require 250ms continuous speech to interrupt greeting

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
