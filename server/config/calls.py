# 🔥 BUILD 309: SIMPLE_MODE Configuration
# Purpose: Enable simplified, stable call flow without aggressive filters
# - Disables: majority vote, autocorrect, infinite silence warnings, loop guards
# - Enables: greeting + barge-in + dynamic field management per call_profile

SIMPLE_MODE = True  # Set to False only if you need aggressive filtering (not recommended)

# SIMPLE_MODE Behavior:
# 1. Audio/Noise Gate: Disabled - trust Twilio + OpenAI
# 2. Gibberish/Hebrew/Length filters: Disabled - all text passes through
# 3. Majority vote for city: Disabled - direct field assignment
# 4. Silence handler: Single 25-30s timeout instead of multiple warnings
# 5. Smart hangup: Immediate after fields filled + confirmation received

# 🔥 BUILD 318: COST OPTIMIZATION Settings
# Even in SIMPLE_MODE, apply minimal RMS threshold to avoid sending pure silence
COST_EFFICIENT_MODE = True  # Enable cost-saving filters (recommended!)

# Minimum RMS to send audio to OpenAI (pure silence = ~0-50 RMS)
# 🔥 BUILD 319: DISABLED - Twilio audio comes with RMS ~12, threshold 100 blocked ALL speech!
# Set to 0 to let all audio through. Re-enable with lower threshold (e.g., 5) after testing.
COST_MIN_RMS_THRESHOLD = 0  # DISABLED - was blocking all user audio!

# Maximum audio frames per second to OpenAI (prevents runaway costs)
# 50 FPS is typical for real-time audio. Lower = cheaper but may affect quality.
COST_MAX_FPS = 40  # Maximum 40 frames/second to OpenAI

# 🔥 BUILD 320: AUDIO_GUARD for noisy PSTN calls (Twilio → OpenAI)
# Lightweight audio filtering to handle background music, TV, conversations
# - Dynamic noise floor adaptation
# - Speech detection using RMS + ZCR (zero-crossing rate)
# - Music mode detection (filters continuous background music)
# Changed only in code - no .env needed
AUDIO_GUARD_ENABLED = True  # ON by default for noisy PSTN robustness

# Audio guard tuning parameters
AUDIO_GUARD_INITIAL_NOISE_FLOOR = 20.0  # Initial noise floor estimate
AUDIO_GUARD_SPEECH_THRESHOLD_FACTOR = 4.0  # Speech = noise_floor * this factor
AUDIO_GUARD_MIN_ZCR_FOR_SPEECH = 0.02  # Minimum zero-crossing rate for speech
AUDIO_GUARD_MIN_RMS_DELTA = 5.0  # Minimum RMS change between frames for speech
AUDIO_GUARD_MUSIC_ZCR_THRESHOLD = 0.03  # ZCR threshold for music detection
AUDIO_GUARD_MUSIC_FRAMES_TO_ENTER = 15  # ~300ms at 20ms/frame to enter music mode
AUDIO_GUARD_MUSIC_COOLDOWN_FRAMES = 100  # ~2s cooldown before exiting music mode
