# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 325: CALL CONFIGURATION - Optimal settings for Hebrew phone calls
# ═══════════════════════════════════════════════════════════════════════════════

# SIMPLE_MODE: Trust Twilio + OpenAI VAD completely
SIMPLE_MODE = True  # All audio passes through - OpenAI handles speech detection

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
# 🔥 BUILD 340: SERVER-SIDE VAD THRESHOLDS for OpenAI Realtime API
# ═══════════════════════════════════════════════════════════════════════════════
# Lower threshold (0.65) catches softer speech and prevents cutoffs
# Longer silence (700ms) lets users finish their thoughts naturally
SERVER_VAD_THRESHOLD = 0.65  # Lower threshold for better Hebrew speech detection
SERVER_VAD_SILENCE_MS = 700  # Longer silence to prevent choppy interruptions (ms)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 MASTER FIX: AUDIO GUARD - Local smoothing and duration guards
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_GUARD_ENABLED = True  # Enable local filtering on top of OpenAI VAD
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
