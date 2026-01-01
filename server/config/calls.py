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
# TUNING RATIONALE - FALSE POSITIVE REDUCTION:
# - threshold 0.87: INCREASED from 0.85 to further reduce false triggers from background noise
#   User reported "AI speaks for ~20s then enters CLOSING state" due to background noise
#   Higher threshold ensures only real customer speech is detected, not ambient sounds
# - silence_duration_ms 600: HEBREW-SAFE - doesn't cut off natural pauses (unchanged)
# - prefix_padding_ms 300: Standard padding for Hebrew syllables (unchanged)
# - create_response: true (automatic response generation on turn end)
#
# 🎯 HYSTERESIS APPROACH:
# OpenAI's server_vad has built-in hysteresis:
# - 0.87 start threshold: Higher to avoid false triggers from ambient noise
# - Implicit higher continue threshold: Maintains speech detection once started
#
# 🎯 ENV OVERRIDE: Can be tuned in production without code changes
# export SERVER_VAD_THRESHOLD=0.90  # Further increase if still too many false triggers
# export SERVER_VAD_THRESHOLD=0.85  # Decrease if missing too much quiet speech
# export SERVER_VAD_SILENCE_MS=550  # Faster response (test with Hebrew first!)
# export SERVER_VAD_SILENCE_MS=700  # Safer for Hebrew natural pauses
#
# ⚠️ MONITORING REQUIRED:
# - If still false triggers → increase to 0.90 (more conservative)
# - If missing quiet speech ("כן", "לא") → decrease gradually to 0.85-0.82
# - If cutting off Hebrew speech → increase silence_ms to 650-700
# - If feels sluggish → can try 550ms (test carefully!)
#
# Current settings (0.87/600ms/300ms) provide:
# ✅ Reduced false positives from background noise (main fix)
# ✅ Still catches real speech including quiet speakers
# ✅ Hebrew-safe silence duration (600ms handles natural pauses)
# ✅ Better barge-in accuracy without false interruptions
# ═══════════════════════════════════════════════════════════════════════════════
import os

# Read from environment with validation
_vad_threshold_str = os.getenv("SERVER_VAD_THRESHOLD", "0.87")
_vad_silence_str = os.getenv("SERVER_VAD_SILENCE_MS", "600")

try:
    SERVER_VAD_THRESHOLD = float(_vad_threshold_str)
    # Validate bounds: 0.0 to 1.0
    if not 0.0 <= SERVER_VAD_THRESHOLD <= 1.0:
        print(f"⚠️ WARNING: SERVER_VAD_THRESHOLD={SERVER_VAD_THRESHOLD} out of bounds [0.0, 1.0], using default 0.87")
        SERVER_VAD_THRESHOLD = 0.87
except ValueError:
    print(f"⚠️ WARNING: Invalid SERVER_VAD_THRESHOLD='{_vad_threshold_str}', using default 0.87")
    SERVER_VAD_THRESHOLD = 0.87

try:
    SERVER_VAD_SILENCE_MS = int(_vad_silence_str)
    # Validate positive integer
    if SERVER_VAD_SILENCE_MS <= 0:
        print(f"⚠️ WARNING: SERVER_VAD_SILENCE_MS={SERVER_VAD_SILENCE_MS} must be positive, using default 600")
        SERVER_VAD_SILENCE_MS = 600
except ValueError:
    print(f"⚠️ WARNING: Invalid SERVER_VAD_SILENCE_MS='{_vad_silence_str}', using default 600")
    SERVER_VAD_SILENCE_MS = 600

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
# 🔥 GREETING FIX: INCREASED ECHO GATE - Stronger protection from false triggers
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (based on production log analysis):
# - RMS 270: Higher threshold reduces false positives from background noise
#   (was 250 - user reported AI enters CLOSING after ~20s of speaking due to false triggers)
# - Frames 6: Requires 120ms of consistent audio (stronger noise rejection)
#   (unchanged - already provides good noise filtering)
#
# Production log analysis showed:
# ❌ Call enters CLOSING state after AI speaks for ~20s
# ❌ Background noise triggers speech detection when user NOT speaking
# ❌ Watchdog incorrectly times out during active AI responses
#
# Current strengthened setting (270.0/6 frames) provides:
# ✅ Stronger protection from background noise
# ✅ Natural interruption still works - real user speech (RMS > 270) passes
# ✅ More consistent call flow - fewer false state transitions
# ═══════════════════════════════════════════════════════════════════════════════
ECHO_GATE_MIN_RMS = 270.0       # Increased: stronger protection from background noise
ECHO_GATE_MIN_FRAMES = 6        # Unchanged: requires 120ms consistent audio

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 GREETING FIX: BALANCED BARGE-IN - Protect greeting, allow natural interruption
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (balanced approach per expert feedback):
# - Frames 6: Requires 120ms of consistent speech to trigger interruption (was 4 frames/80ms)
#   Balanced: More robust than 4 frames (80ms) - reduces false triggers from noise/breathing
#   Expert feedback: 5 frames risks some false triggers, 6-8 frames (120-160ms) is optimal
# - Debounce 350ms: Prevents rapid re-triggering after barge-in (unchanged)
#
# APPROACH:
# ❌ OLD: Required 80ms of voice (4 frames) - too fast, risks false barge-in from noise
# ⚠️ TRIED: 160ms (8 frames) - too slow for natural interruption
# ✅ NEW: 120ms (6 frames) - balanced between speed and accuracy, fewer false triggers
#
# Golden Rule: speech_started => cancel ALWAYS when active_response_id exists
# - voice_frames provides reliable noise filtering (120ms sustained sound)
# - Primary trigger is speech_started event itself
# - Idempotency protection via _should_send_cancel() prevents double-cancel
#
# ⚠️ MONITORING REQUIRED:
# - If still false triggers from noise → increase to 7-8 frames (140-160ms)
# - If barge-in feels slow → can decrease to 5 frames but monitor closely
# - Check logs for "false barge-in" patterns (cancel without real speech)
#
# Current settings (6 frames/350ms) provide:
# ✅ Reliable barge-in response (120ms vs old 80ms)
# ✅ Reduced false triggers from noise/breathing/clicks
# ✅ More confident interruption detection (trusts OpenAI VAD)
# ✅ No double triggers - 350ms debounce prevents rapid re-triggering
# ═══════════════════════════════════════════════════════════════════════════════
BARGE_IN_VOICE_FRAMES = 6   # Balanced: 120ms - reliable detection, fewer false triggers (was 4)
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
