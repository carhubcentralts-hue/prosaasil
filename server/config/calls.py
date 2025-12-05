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
