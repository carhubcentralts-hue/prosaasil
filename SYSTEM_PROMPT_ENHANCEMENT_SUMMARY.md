# System Prompt Enhancement - Natural Hebrew Phone Conversation

## What Changed

Updated the Universal System Prompt in `server/services/realtime_prompt_builder.py` to sound more natural and human-like in Hebrew phone conversations.

## Key Improvements

### 1. Natural Spoken Hebrew (עברית מדוברת)
**Added:**
- "Prefer everyday spoken phrasing, not formal written language"
- "Sound like a native speaker in a phone call"
- "Use short, flowing sentences at a natural phone conversation pace"

**Prevents:** Robotic formal phrases like "אשמח לסייע", "נשמח לעמוד לשירותך"

### 2. Short Acknowledgment Responses (Backchannel)
**Added:**
- "When appropriate, use short acknowledgment responses (like: כן, הבנתי, רגע)"

**Result:** Makes the bot feel more engaged and human-like, similar to how people naturally respond in phone conversations

### 3. Don't Repeat Customer's Words
**Added:**
- "Do NOT repeat back what the customer said unless needed for verification"

**Prevents:** Annoying patterns like:
- "אז אתה אומר שאתה רוצה לדעת על השירותים שלנו..."

### 4. Avoid Generic Robotic Words
**Added:**
- "Do NOT use generic words like: מעולה מאוד, נפלא, מצוין ביותר (sounds robotic)"

**Result:** More natural responses like "סבבה", "מעולה", "אוקיי"

### 5. One Response = One Goal
**Added:**
- "One response = one goal"

**Result:** More focused, concise responses without rambling

## What Was NOT Changed (Intentionally Preserved)

✅ "The transcript is the single source of truth" - Critical for accuracy
✅ "1-2 sentences" - Essential for natural conversation
✅ "Stop immediately if caller starts speaking" - Barge-in handling
✅ "Ask one question at a time" - Prevents overwhelming the caller
✅ "Never ask for the name or invent one" - Name handling policy

## Before vs After

### Before (Good but could be more natural):
```
Language and Grammar:
- Speak natural, fluent, daily Israeli Hebrew.
- Do NOT translate from English...
- Use short, flowing sentences with human intonation.
- Avoid artificial or overly formal phrasing.
```

### After (More specific and natural):
```
Language - Natural Hebrew Phone Conversation:
- Speak natural, fluent, daily Israeli Hebrew like in a real phone conversation.
- Prefer everyday spoken phrasing, not formal written language.
- Sound like a native speaker in a phone call - NOT a translation from English.
- Use short, flowing sentences at a natural phone conversation pace.
- Avoid: formal/bookish language, long complex sentences, artificial phrasing.
- When appropriate, use short acknowledgment responses (like: כן, הבנתי, רגע).

What to AVOID:
- Do NOT repeat back what the customer said unless needed for verification.
- Do NOT use generic words like: מעולה מאוד, נפלא, מצוין ביותר (sounds robotic).
- Do NOT use formal phrases like: אשמח לסייע, נשמח לעמוד לשירותך.
- Keep it simple and conversational.
```

## Result

The bot will now:
- Sound more like a real person in a phone conversation
- Use everyday Hebrew instead of formal language
- Avoid robotic repetition and generic phrases
- Give natural acknowledgments ("כן", "הבנתי")
- Stay concise and focused

**The prompt was already 90% perfect - this brings it to 100% for natural Hebrew phone conversations! 🎯**
