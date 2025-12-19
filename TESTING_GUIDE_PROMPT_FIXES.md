# Testing Guide: Prompt Confusion Fixes

## Overview
This guide provides step-by-step testing procedures to verify the prompt confusion fixes work correctly.

## Prerequisites
- Access to server logs (to verify mandatory logging)
- Ability to make test calls (inbound and outbound)
- Access to business settings UI

---

## Test 1: Verify SYSTEM Messages Are Blocked

### Objective
Confirm that NO [SYSTEM] or [SERVER] messages are sent to the AI as user input

### Steps
1. Make an inbound test call
2. Let the call run for 20+ seconds to trigger silence warning
3. Review server logs

### Expected Results
**Logs should show:**
```
[AI_INPUT_BLOCKED] kind=server_event reason=never_send_to_model text_preview='[SYSTEM] Customer is silent...'
⚠️ [SERVER_EVENT] BLOCKED - server events disabled to prevent prompt confusion
```

**Logs should NOT show:**
```
[AI_INPUT] kind=user_transcript text_preview='[SYSTEM]...'
```

### Success Criteria
✅ All [SYSTEM] messages blocked  
✅ Only actual customer speech sent to AI  
✅ AI does NOT respond to system messages

---

## Test 2: Verify Semantic Repair Is Disabled

### Objective
Confirm that customer's exact words are preserved, not modified

### Steps
1. Make a test call
2. Say Hebrew phrases that might be "corrected" (e.g., short, unusual words)
3. Review server logs and conversation transcript

### Expected Results
**Logs should show:**
```
[SEMANTIC_REPAIR] DISABLED globally - returning original text: 'מה מדם'
```

**Logs should NOT show:**
```
[STT_REPAIR] before='מה מדם' after='מה המצב'
```

### Success Criteria
✅ Semantic repair disabled (see DISABLED log)  
✅ Customer's exact words preserved  
✅ No unwanted transcript modifications

---

## Test 3: Verify Inbound/Outbound Separation

### Objective  
Confirm that inbound calls get inbound prompts, outbound calls get outbound prompts

### Steps
1. Make an **inbound** test call
2. Review logs for prompt building
3. Make an **outbound** test call  
4. Review logs for prompt building

### Expected Results (Inbound)
**Logs should show:**
```
📞 [PROMPT_ROUTER] Building INBOUND prompt for business 123
✅ [INBOUND] Prompt built: 3500 chars (system + business)
🔍 [PROMPT_VERIFICATION] business_id=123, direction=INBOUND, call_type_in_prompt=True
```

### Expected Results (Outbound)
**Logs should show:**
```
📤 [PROMPT_ROUTER] Building OUTBOUND prompt for business 123
✅ [OUTBOUND] Prompt built: 3200 chars (system + outbound)
🔍 [PROMPT_VERIFICATION] business_id=123, direction=OUTBOUND, call_type_in_prompt=True
```

### Success Criteria
✅ Inbound calls use inbound prompts (with scheduling)  
✅ Outbound calls use outbound prompts (sales script)  
✅ No mixing between directions

---

## Test 4: Verify Prompt Cache

### Objective
Confirm that prompt cache correctly separates inbound and outbound

### Steps
1. Make first **inbound** call to business 123
2. Make second **inbound** call to business 123
3. Make **outbound** call to business 123
4. Review logs

### Expected Results
**First inbound call (cache MISS):**
```
❌ [PROMPT_CACHE] MISS for 123:inbound
📞 [PROMPT_ROUTER] Building INBOUND prompt for business 123
💾 [PROMPT CACHE STORE] Cached prompt for business 123 (inbound)
```

**Second inbound call (cache HIT):**
```
✅ [PROMPT CACHE HIT] Returning cached prompt for business 123 (inbound)
```

**Outbound call (cache MISS for outbound):**
```
❌ [PROMPT_CACHE] MISS for 123:outbound
📤 [PROMPT_ROUTER] Building OUTBOUND prompt for business 123
💾 [PROMPT CACHE STORE] Cached prompt for business 123 (outbound)
```

### Success Criteria
✅ First call builds prompt (cache MISS)  
✅ Subsequent calls use cache (cache HIT)  
✅ Inbound/outbound cached separately

---

## Test 5: Verify AI Input Logging

### Objective
Confirm that all AI inputs are logged with proper classification

### Steps
1. Make a test call
2. Say something to the customer (e.g., "מה המחיר")
3. Review logs

### Expected Results
**Logs should show:**
```
[AI_INPUT] kind=user_transcript text_preview='מה המחיר'
```

**Logs should NOT show:**
- Full sensitive text (should be truncated at 100 chars)
- System messages as user input

### Success Criteria
✅ Every user transcript logged  
✅ Sensitive data truncated (max 100 chars)  
✅ Clear distinction: user_transcript vs server_event

---

## Test 6: End-to-End Conversation Quality

### Objective
Verify AI stays on topic and responds to actual customer speech

### Steps
1. Make a natural test call
2. Have a 2-3 minute conversation
3. Observe AI responses

### Expected AI Behavior
✅ Responds ONLY to what customer actually said  
✅ Does NOT respond to silences as if customer spoke  
✅ Does NOT say things like "I didn't hear you say that" when customer didn't speak  
✅ Does NOT repeat or rephrase customer's words unless customer asked  
✅ Stays focused on conversation topic

### Red Flags (Should NOT Happen)
❌ AI responds to silence as if customer said something  
❌ AI says "you mentioned..." when customer didn't mention it  
❌ AI changes customer's words (e.g., "you said X" when customer said Y)  
❌ AI goes off-topic without customer input

---

## Verification Checklist

After running all tests, verify:

- [ ] NO [SYSTEM]/[SERVER] messages sent to AI
- [ ] ALL system messages blocked (see `[AI_INPUT_BLOCKED]` logs)
- [ ] Semantic repair disabled globally
- [ ] Customer's exact words preserved
- [ ] Inbound prompts used for inbound calls
- [ ] Outbound prompts used for outbound calls
- [ ] Prompt cache works correctly
- [ ] Cache separates inbound/outbound
- [ ] All AI inputs logged with privacy protection
- [ ] AI responds only to actual customer speech
- [ ] AI stays on topic throughout conversation

---

## Troubleshooting

### Issue: AI still goes off-topic
**Check logs for:**
```
[AI_INPUT] kind=user_transcript text_preview='[SYSTEM]...'
```
This means system messages are still being sent. File a bug report.

### Issue: Customer's words are being changed
**Check logs for:**
```
[STT_REPAIR] before='X' after='Y'
```
This means semantic repair is still active. Verify `SEMANTIC_REPAIR_ENABLED = False`.

### Issue: Inbound call uses outbound prompt
**Check logs for:**
```
🔍 [PROMPT_VERIFICATION] business_id=X, direction=OUTBOUND
```
when you made an inbound call. File a bug report.

### Issue: Cache not working
**Check logs for:**
```
✅ [PROMPT CACHE HIT]
```
If you only see MISS, cache may not be persisting. Check cache TTL.

---

## Success Criteria Summary

**All tests must pass** for the fix to be considered complete:

1. ✅ SYSTEM messages completely blocked
2. ✅ Semantic repair disabled globally
3. ✅ Inbound/Outbound separation verified
4. ✅ Prompt cache working correctly
5. ✅ AI input logging functional
6. ✅ End-to-end conversation quality improved

If any test fails, review logs and file a detailed bug report with:
- Test number that failed
- Expected vs actual behavior
- Relevant log excerpts
- Steps to reproduce
