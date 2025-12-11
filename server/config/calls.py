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
    "vad_rms": 60,                 # VAD RMS threshold (lowered from 80 for quiet speakers)
    "rms_silence_threshold": 30,   # Pure silence threshold (lowered from 40)
    "min_speech_rms": 40,          # Minimum speech RMS (lowered from 60 for quiet callers)
    "min_rms_delta": 5.0,          # Min RMS above noise floor (lowered from 25.0)
}

# SIMPLE_MODE: Trust Twilio + OpenAI VAD completely
SIMPLE_MODE = AUDIO_CONFIG["simple_mode"]  # All audio passes through - OpenAI handles speech detection

# COST OPTIMIZATION
# 🔥 BUILD 334: 100% AUDIO FOR PERFECT STT - No dropping any frames!
# Phone audio = 8kHz @ 20ms frames = 50 FPS. For Hebrew city names, we need EVERY frame.
# User priority: Perfect transcription > cost savings
COST_EFFICIENT_MODE = True   # Enabled but no actual dropping at 50 FPS
COST_MIN_RMS_THRESHOLD = 0   # No RMS gating - all audio passes through
COST_MAX_FPS = 50            # 50 FPS = 100% of audio (perfect STT quality)

# 🔥 BUILD 335: EXTENDED LIMITS - Allow up to 10 minutes for complex bookings!
# Only disconnect if customer asks or truly needs to hang up.
# These are ABSOLUTE safety limits to prevent infinite runaway costs.
MAX_REALTIME_SECONDS_PER_CALL = 600  # Max 10 minutes per call
MAX_AUDIO_FRAMES_PER_CALL = 30000    # 50 fps × 600s = 30000 frames maximum

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 MASTER FIX: SERVER-SIDE VAD THRESHOLDS for OpenAI Realtime API
# ═══════════════════════════════════════════════════════════════════════════════
SERVER_VAD_THRESHOLD = 0.72  # Balanced threshold for Hebrew speech detection
SERVER_VAD_SILENCE_MS = 380  # Silence duration to detect end of speech (ms)

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
# 🔥 MASTER FIX: ECHO GATE - Protect against AI echo during greeting
# ═══════════════════════════════════════════════════════════════════════════════
ECHO_GATE_MIN_RMS = 320.0       # Minimum RMS to trigger barge-in during AI speech
ECHO_GATE_MIN_FRAMES = 6        # Consecutive frames needed (120ms)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 MASTER FIX: BARGE-IN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
BARGE_IN_VOICE_FRAMES = 12  # Consecutive voice frames to trigger barge-in (240ms)
BARGE_IN_DEBOUNCE_MS = 400  # Debounce period to prevent double triggers (ms)

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
