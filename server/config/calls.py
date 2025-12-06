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
# Setting this to 100 filters pure silence but passes all speech (speech = 200+)
COST_MIN_RMS_THRESHOLD = 100  # Don't send audio below this RMS

# Maximum audio frames per second to OpenAI (prevents runaway costs)
# 50 FPS is typical for real-time audio. Lower = cheaper but may affect quality.
COST_MAX_FPS = 40  # Maximum 40 frames/second to OpenAI
