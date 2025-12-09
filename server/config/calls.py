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

# AUDIO GUARD: ENHANCED - Intelligent noise filtering with proper VAD
# Prevents noise, breathing, and background sounds from triggering AI responses
# Uses dynamic noise floor + duration gating + RMS thresholds
AUDIO_GUARD_ENABLED = True  # ON - Enhanced VAD for noise handling

# VAD CALIBRATION THRESHOLDS (used in media_ws_ai.py)
VAD_BASELINE_TIMEOUT = 80.0     # Baseline when calibration times out
VAD_ADAPTIVE_CAP = 120.0        # Maximum adaptive threshold
VAD_ADAPTIVE_OFFSET = 60.0      # noise_floor + this = threshold

# ECHO GATE (protects against AI echo triggering barge-in)
ECHO_GATE_MIN_RMS = 300.0       # Minimum RMS to trigger barge-in during AI speech
ECHO_GATE_MIN_FRAMES = 5        # Consecutive frames needed (100ms)

# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Audio Guard parameters for intelligent noise filtering
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_GUARD_INITIAL_NOISE_FLOOR = 30.0          # Starting noise floor baseline
AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR = 3.5       # noise_floor * factor = speech threshold
AUDIO_GUARD_MIN_ZCR_FOR_SPEECH = 0.025          # Zero-crossing rate for speech detection
AUDIO_GUARD_MIN_RMS_DELTA = 8.0                 # Minimum RMS change between frames for speech
AUDIO_GUARD_MUSIC_ZCR_THRESHOLD = 0.04          # High ZCR indicates music/noise
AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER = 15          # Consecutive frames to enter music mode (~300ms)
AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES = 100         # Frames to stay in music mode (~2s)

# 🔥 NEW: Duration-based filtering (ignore short bursts)
AUDIO_GUARD_MIN_SPEECH_FRAMES = 15              # Minimum 15 frames (300ms) for valid speech
AUDIO_GUARD_SILENCE_RESET_FRAMES = 25           # Reset speech counter after 25 frames (500ms) of silence
