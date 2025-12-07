# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 BUILD 325: CALL CONFIGURATION - Optimal settings for Hebrew phone calls
# ═══════════════════════════════════════════════════════════════════════════════

# SIMPLE_MODE: Trust Twilio + OpenAI VAD completely
SIMPLE_MODE = True  # All audio passes through - OpenAI handles speech detection

# COST OPTIMIZATION
# 🔥 BUILD 330: DISABLED FPS LIMITER - was dropping 20% of audio causing bad transcription!
# Phone audio = 8kHz @ 20ms frames = 50 FPS required. Limiting to 40 was dropping audio!
COST_EFFICIENT_MODE = False  # DISABLED - must send ALL audio for good STT!
COST_MIN_RMS_THRESHOLD = 0   # No RMS gating - all audio passes through
COST_MAX_FPS = 60            # Raised to 60 (above 50 FPS phone requirement)

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
