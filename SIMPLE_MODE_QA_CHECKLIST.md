# SIMPLE_MODE Telephony Fixes - QA Checklist

## Test Environment
- Branch: `copilot/fix-silence-handler-bugs`
- Commits: efaeafa, c7efc8e, 42c8cbc
- Mode: SIMPLE_MODE (telephony - 8kHz G.711 calls)

---

## Test 1: Outbound Call - Lead Collection Only (goal="lead_only")

### Setup:
- Business settings: `call_goal = "lead_only"`
- UI toggle: "סיום אוטומטי כשהלקוח נפרד" = OFF
- Silence settings: timeout=15s, max_warnings=2

### Test Steps:
1. **Make outbound call**
   - ✅ Check logs: `[BUILD] SIMPLE_MODE=True direction=outbound goal=lead_only`
   - ✅ Verify AI uses correct OUTBOUND prompt (not inbound)

2. **User stays silent for 15s after greeting**
   - ✅ Expected: AI asks "אתה עדיין שם?" (first warning)
   - ✅ Check logs: `[SILENCE] SIMPLE_MODE=True action=ask_are_you_there`

3. **User stays silent for another 15s**
   - ✅ Expected: AI asks again (second/last warning)
   - ✅ Check logs: Warning 2/2

4. **User stays silent for another 15s (max warnings exceeded)**
   - ✅ Expected: AI says "אשאיר את הקו פתוח אם תצטרך אותי"
   - ✅ Expected: Call stays ACTIVE (no hangup)
   - ✅ Check logs: `[SILENCE] SIMPLE_MODE - max warnings exceeded but NOT hanging up`

5. **User finally speaks: "לא צריך, תודה ביי"**
   - ✅ Expected: AI responds politely
   - ✅ Expected: Call DOES NOT hangup (toggle is OFF)
   - ✅ Check logs: `[GOODBYE] will_hangup=False` or no goodbye detection

6. **With toggle ON: User says "תודה, יום נעים"**
   - ✅ Expected: AI says goodbye and HANGS UP
   - ✅ Check logs: `[GOODBYE] SIMPLE_MODE=True goal=lead_only lead_complete=False will_hangup=True`

---

## Test 2: Inbound Call - Lead Collection Only (goal="lead_only")

### Setup:
- Business settings: `call_goal = "lead_only"`
- UI toggle: "סיום אוטומטי כשהלקוח נפרד" = ON

### Test Steps:
1. **Receive inbound call**
   - ✅ Check logs: `[BUILD] SIMPLE_MODE=True direction=inbound goal=lead_only`
   - ✅ Verify AI uses correct INBOUND prompt (not outbound)

2. **After greeting, user provides some details but not all required fields**
   - ✅ Expected: AI continues conversation per prompt

3. **User says "תודה רבה, אחלה"**
   - ✅ Expected: AI says goodbye and HANGS UP (goal=lead_only, no hard guards)
   - ✅ Check logs: `[GOODBYE] SIMPLE_MODE=True goal=lead_only will_hangup=True`

---

## Test 3: Outbound Call - Appointments (goal="appointment")

### Setup:
- Business settings: `call_goal = "appointment"`
- Required fields: name, phone, preferred_time
- UI toggle: "סיום אוטומטי כשהלקוח נפרד" = ON

### Test Steps:
1. **Make outbound call**
   - ✅ Check logs: `[BUILD] SIMPLE_MODE=True direction=outbound goal=appointment`

2. **User provides name and phone but NO time**
   - ✅ Expected: AI continues conversation

3. **User says "אוקי תודה, ביי"**
   - ✅ Expected: AI DOES NOT hangup, asks for missing time
   - ✅ Check logs: `[GOODBYE] SIMPLE_MODE=True goal=appointment lead_complete=False will_hangup=False`

4. **User provides preferred time: "ביום שלישי בבוקר"**
   - ✅ Expected: AI confirms appointment details

5. **User says "מצוין, תודה רבה"**
   - ✅ Expected: AI says goodbye and HANGS UP (all fields captured)
   - ✅ Check logs: `[GOODBYE] SIMPLE_MODE=True goal=appointment lead_complete=True will_hangup=True`

---

## Test 4: Prompt Cache Separation

### Setup:
- Same business with both inbound and outbound prompts configured

### Test Steps:
1. **Make inbound call**
   - ✅ Verify greeting uses INBOUND prompt style
   - ✅ Check logs: Cache key should be like `[PROMPT CACHE] get key=123:inbound`

2. **Make outbound call to same business**
   - ✅ Verify greeting uses OUTBOUND prompt style
   - ✅ Check logs: Cache key should be like `[PROMPT CACHE] get key=123:outbound`

3. **Verify no prompt mixing**
   - ✅ Inbound calls always use inbound prompt
   - ✅ Outbound calls always use outbound prompt

---

## Test 5: STT Filtering Permissiveness

### Setup:
- SIMPLE_MODE enabled

### Test Steps:
1. **User speaks with noise/distortion (typical in telephony)**
   - Example: "אממ... אני צריך... מנעול"
   
2. **Expected behavior:**
   - ✅ Text passes through to AI (not filtered as gibberish)
   - ✅ Check logs: `[SIMPLE_MODE] Bypassing all filters - accepting: '...'`
   - ✅ AI responds based on whatever was transcribed

3. **User speaks very quietly or with poor connection**
   - ✅ Expected: Even partial/noisy transcripts are sent to AI
   - ✅ AI can ask for clarification if needed

---

## Expected Log Patterns

### Call Start:
```
📞 [BUILD] SIMPLE_MODE=True direction=inbound goal=lead_only
```

### Silence Warning:
```
🔇 [SILENCE] Warning 1/2 after 15.3s silence
🔇 [SILENCE] SIMPLE_MODE=True action=ask_are_you_there
```

### Max Warnings (No Hangup):
```
🔇 [SILENCE] SIMPLE_MODE - max warnings exceeded but NOT hanging up
   Keeping line open - user may return or Twilio will disconnect
```

### Goodbye Detection:
```
🔇 [GOODBYE] SIMPLE_MODE=True goal=lead_only lead_complete=False
✅ [GOODBYE] will_hangup=True - goal=lead_only (no hard lead guards)
```

Or for appointments with incomplete lead:
```
🔇 [GOODBYE] SIMPLE_MODE=True goal=appointment lead_complete=False
🔒 [GOODBYE] will_hangup=False - goal=appointment, lead incomplete
   required_lead_fields=['name', 'phone', 'preferred_time'], lead_captured=False
```

---

## Regression Tests

### Verify existing fixes STILL WORK:

1. **Greeting State Machine**
   - ✅ First AI response is greeting
   - ✅ User audio blocked during greeting
   - ✅ Greeting completes properly

2. **TX Queue & Barge-in**
   - ✅ TX queue ~150 frames (~3s)
   - ✅ is_ai_speaking set/cleared correctly
   - ✅ Barge-in flushes both queues

3. **User Speech Detection**
   - ✅ user_has_spoken set from VAD/speech_started
   - ✅ Not blocked by hallucination filters in SIMPLE_MODE
   - ✅ Guards disabled in SIMPLE_MODE

---

## Success Criteria

All tests above should pass with:
- ✅ No premature hangups due to silence in SIMPLE_MODE
- ✅ Silence warnings work as configured (UI settings respected)
- ✅ Goodbye detection respects call_goal and UI toggles
- ✅ Inbound/outbound prompts never mixed
- ✅ STT filtering is permissive in SIMPLE_MODE
- ✅ Comprehensive logging for debugging
- ✅ No regressions in existing fixes
