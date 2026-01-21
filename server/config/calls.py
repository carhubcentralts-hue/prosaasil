# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 325: CALL CONFIGURATION - Optimal settings for Hebrew phone calls
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 MASTER AUDIO CONFIG - Single source of truth for all audio filtering
# ═══════════════════════════════════════════════════════════════════════════════
import logging

logger = logging.getLogger(__name__)

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
# TUNING RATIONALE - FALSE POSITIVE REDUCTION (Updated per הנחיה):
# - threshold 0.90: INCREASED from 0.87 (+0.03) to reduce false triggers from background noise
#   Per requirement: "VAD פחות טריגרי" - higher threshold filters beeps/clicks/background noise
#   Still catches real customer speech but requires stronger signal to trigger
# - silence_duration_ms 700: INCREASED from 600ms (+100ms) to avoid triggering on clicks
#   Per requirement: "להאריך Silence כדי לא להידלק על קליק"
#   Requires longer true silence before considering turn complete
# - prefix_padding_ms 600: INCREASED from 500ms (+100ms) for better speech capture
#   Per requirement: "להעלות Prefix padding קצת" - prevents clipping first syllables
# - create_response: true (automatic response generation on turn end)
#
# 🎯 HYSTERESIS APPROACH:
# OpenAI's server_vad has built-in hysteresis:
# - 0.90 start threshold: Higher to avoid false triggers from ambient noise/beeps
# - Implicit higher continue threshold: Maintains speech detection once started
#
# 🎯 ENV OVERRIDE: Can be tuned in production without code changes
# export SERVER_VAD_THRESHOLD=0.92  # Further increase if still too many false triggers
# export SERVER_VAD_THRESHOLD=0.88  # Decrease if missing too much quiet speech
# export SERVER_VAD_SILENCE_MS=650  # Compromise between 600-700
# export SERVER_VAD_SILENCE_MS=800  # Even safer for Hebrew natural pauses
#
# ⚠️ MONITORING REQUIRED:
# - If still false triggers → increase to 0.92 (more conservative)
# - If missing quiet speech ("כן", "לא") → decrease gradually to 0.88-0.85
# - If cutting off Hebrew speech → increase silence_ms to 750-800
# - If feels sluggish → can try 650ms (test carefully!)
#
# Current settings (0.90/700ms/600ms) provide:
# ✅ Significantly reduced false positives from background noise (main fix)
# ✅ Still catches real speech including quiet speakers
# ✅ Hebrew-safe silence duration (700ms handles natural pauses + prevents click triggers)
# ✅ Better barge-in accuracy without false interruptions
# ═══════════════════════════════════════════════════════════════════════════════
import os

# Read from environment with validation
_vad_threshold_str = os.getenv("SERVER_VAD_THRESHOLD", "0.90")
_vad_silence_str = os.getenv("SERVER_VAD_SILENCE_MS", "700")

try:
    SERVER_VAD_THRESHOLD = float(_vad_threshold_str)
    # Validate bounds: 0.0 to 1.0
    if not 0.0 <= SERVER_VAD_THRESHOLD <= 1.0:
        logger.warning(f"⚠️ WARNING: SERVER_VAD_THRESHOLD={SERVER_VAD_THRESHOLD} out of bounds [0.0, 1.0], using default 0.90")
        SERVER_VAD_THRESHOLD = 0.90
except ValueError:
    logger.warning(f"⚠️ WARNING: Invalid SERVER_VAD_THRESHOLD='{_vad_threshold_str}', using default 0.90")
    SERVER_VAD_THRESHOLD = 0.90

try:
    SERVER_VAD_SILENCE_MS = int(_vad_silence_str)
    # Validate positive integer
    if SERVER_VAD_SILENCE_MS <= 0:
        logger.warning(f"⚠️ WARNING: SERVER_VAD_SILENCE_MS={SERVER_VAD_SILENCE_MS} must be positive, using default 700")
        SERVER_VAD_SILENCE_MS = 700
except ValueError:
    logger.warning(f"⚠️ WARNING: Invalid SERVER_VAD_SILENCE_MS='{_vad_silence_str}', using default 700")
    SERVER_VAD_SILENCE_MS = 700

# 🔥 TRANSCRIPTION IMPROVEMENT: Increased from 500ms to 600ms (+100ms per הנחיה)
# Prevents clipping of initial syllables when speech starts from complete silence
# Per requirement: "להעלות Prefix padding קצת" for better speech capture without clipping
SERVER_VAD_PREFIX_PADDING_MS = 600  # Increased padding to avoid clipping speech start (was 500ms)

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
# 🔥 GREETING FIX: ECHO GATE - Balance between noise protection and speech capture
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (optimized for transcription accuracy + FALSE POSITIVE REDUCTION):
# - RMS 275: INCREASED from 250 (+10% per הנחיה) to reduce false triggers
#   Per requirement: "סף אנרגיה (RMS) — הכי עדין, הכי אפקטיבי נגד פיפס"
#   Higher threshold filters beeps/clicks while still allowing real speech
#   +10% increase (250 → 275) provides better noise rejection without blocking speech
# - Frames 6: Requires 120ms of consistent audio (unchanged - proven noise filtering)
#
# 🎯 TRANSCRIPTION IMPROVEMENT + NOISE FILTERING:
# The +10% increase (250→275) provides optimal balance:
# ✅ Filters out beeps/clicks/background noise effectively
# ✅ Still allows real speech to pass through easily
# ✅ Better transcription accuracy overall
# ✅ Reduces false barge-in triggers significantly
#
# Per הנחיה: "העלאה קטנה של הסף: +8% עד +15%" - we use +10% (middle of range)
# ═══════════════════════════════════════════════════════════════════════════════
ECHO_GATE_MIN_RMS = 275.0       # Increased: +10% for better noise filtering (was 250.0)
ECHO_GATE_MIN_FRAMES = 6        # Unchanged: requires 120ms consistent audio

# 🔥 TRANSCRIPTION IMPROVEMENT: Gate re-enable decay after END OF UTTERANCE
# Prevents clipping of utterance ending or start of next turn
# When speech stops, wait this duration before re-activating strict gate
ECHO_GATE_DECAY_MS = 200  # 200ms decay - prevents clipping end/start of turns

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BARGE-IN FIX: Stricter validation to reduce false positives
# ═══════════════════════════════════════════════════════════════════════════════
# TUNING RATIONALE (per הנחיה - debouncing + consecutive frames):
# - Debounce 150ms: NEW REQUIREMENT - Wait 150ms before triggering barge-in
#   Per requirement: "Debounce לברג-אין: אל תעצור מיד על speech_started"
#   Prevents false triggers from single beeps/clicks - requires sustained speech
# - Frames 7: DECREASED from 10 to 7 (140ms) for balanced responsiveness
#   Per requirement: "N פריימים רצופים במקום פיפס אחד - 6–8 פריימים"
#   7 frames = 140ms of consecutive audio (middle of 6-8 range, 20ms per frame)
#   Filters out brief noise while still allowing natural barge-in
# - RMS Multiplier 1.4: NEW - Minimum RMS threshold for barge-in validation
#   Per requirement: "סף RMS מינימלי לברג-אין (baseline_noise * 1.4)"
#   Ensures audio is real speech, not ambient noise
#
# 🎯 DEBOUNCE + FRAMES APPROACH:
# ❌ OLD: Immediate cancel on speech_started - caused false positives from noise
# ✅ NEW: Wait 150ms + verify 7 consecutive frames above RMS threshold
#
# Golden Rule: speech_started => wait 150ms => verify frames => cancel if valid
# - Debounce provides time window to verify real speech vs noise
# - Consecutive frames ensure sustained audio, not brief spikes
# - RMS threshold ensures audio has sufficient energy (not background hum)
# - Idempotency protection via _should_send_cancel() prevents double-cancel
#
# ⚠️ MONITORING REQUIRED:
# - If barge-in feels slow → can decrease debounce to 120ms (minimum safe)
# - If still false triggers → increase frames to 8-9 or RMS multiplier to 1.5-1.6
# - If missing real interruptions → decrease frames to 6 or debounce to 120ms
#
# Current settings (150ms/7frames/1.4x) provide:
# ✅ Significantly reduced false positives from beeps/clicks/noise
# ✅ Still fast enough for natural conversation interruption (~290ms total)
# ✅ Better validation of real speech vs ambient sounds
# ✅ No double triggers - debounce prevents rapid re-triggering
# ═══════════════════════════════════════════════════════════════════════════════
BARGE_IN_DEBOUNCE_MS = 150  # NEW: Wait 150ms before triggering barge-in (per הנחיה)
BARGE_IN_VOICE_FRAMES = 7   # Balanced: 140ms - reduced from 10 for responsiveness (was 10)
BARGE_IN_MIN_RMS_MULTIPLIER = 1.4  # NEW: RMS must be 1.4x baseline for barge-in (per הנחיה)

# 🔥 EARLY BARGE-IN: Minimum continuous speech duration before triggering interrupt
# User requirement: Interrupt should happen on speech START, not END OF UTTERANCE
# Requires 120-180ms of verified continuous speech (not just spike/echo)
EARLY_BARGE_IN_MIN_DURATION_MS = 150  # 150ms sweet spot (120-180ms range)
EARLY_BARGE_IN_VERIFY_RMS = True  # Verify RMS above threshold during duration

# 🔥 CRITICAL FIX: ANTI-ECHO PROTECTION
# 100ms was too short - AI echo bounces back within this window causing false barge-in
# Changed to 200ms for safer echo protection (compromise between 100ms and old 300ms)
ANTI_ECHO_COOLDOWN_MS = 200  # 200ms anti-echo window (was 100ms - too short!)
ANTI_ECHO_RMS_MULTIPLIER = 1.8  # During cooldown, require RMS > (vad_threshold * 1.8) for "real speech"

# 🔥 CRITICAL FIX: Last AI Audio Age Gate
# Additional gate: If AI sent audio very recently (<150ms ago), block barge-in (likely echo)
LAST_AI_AUDIO_MIN_AGE_MS = 150  # Must be 150ms+ since last AI audio to allow barge-in

# 🔥 CRITICAL FIX: Interrupt Lock Duration
# Prevent multiple cancel/clear/flush in rapid succession from same utterance
BARGE_IN_INTERRUPT_LOCK_MS = 700  # 700ms interrupt lock (prevents spam interrupts)

# Greeting-specific protection (applied during greeting playback only)
GREETING_PROTECT_DURATION_MS = 500  # Protect greeting for first 500ms
GREETING_MIN_SPEECH_DURATION_MS = 220  # Require 220ms continuous speech to interrupt greeting (was 250ms)

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
