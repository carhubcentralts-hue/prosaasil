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

# AUDIO GUARD: DISABLED - was blocking real speech!
# Analysis showed rms=8 frames being blocked while user was speaking.
AUDIO_GUARD_ENABLED = False  # OFF - trust OpenAI VAD

# VAD CALIBRATION THRESHOLDS (used in media_ws_ai.py)
VAD_BASELINE_TIMEOUT = 80.0     # Baseline when calibration times out
VAD_ADAPTIVE_CAP = 120.0        # Maximum adaptive threshold
VAD_ADAPTIVE_OFFSET = 60.0      # noise_floor + this = threshold

# ECHO GATE (protects against AI echo triggering barge-in)
ECHO_GATE_MIN_RMS = 300.0       # Minimum RMS to trigger barge-in during AI speech
ECHO_GATE_MIN_FRAMES = 5        # Consecutive frames needed (100ms)

# ═══════════════════════════════════════════════════════════════════════════════
# Legacy Audio Guard parameters (not used when AUDIO_GUARD_ENABLED = False)
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_GUARD_INITIAL_NOISE_FLOOR = 20.0
AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR = 4.0
AUDIO_GUARD_MIN_ZCR_FOR_SPEECH = 0.02
AUDIO_GUARD_MIN_RMS_DELTA = 5.0
AUDIO_GUARD_MUSIC_ZCR_THRESHOLD = 0.03
AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER = 15
AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES = 100
