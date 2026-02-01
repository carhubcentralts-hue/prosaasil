# WhatsApp Context Fix - Testing Guide

## Quick Test Scenarios

### Scenario 1: Context Retention Test (10+ Messages)
**Goal**: Verify conversation maintains context across multiple turns

**Steps**:
1. Start new WhatsApp conversation with bot
2. Send: "היי"
3. Send: "אני רוצה הדברה לבית"
4. Send: "בתוך הבית"
5. Send: "זה כבר שבוע"
6. Send: "מה אתה ממליץ?"
7. Send: "כמה זה עולה?"
8. Send: "אפשר לקבוע תור?"
9. Send: "מה השעות שלכם?"
10. Send: "תודה"

**Expected Results**:
- ✅ Each response is relevant to the specific message
- ✅ Bot remembers previous context (e.g., knows you need pest control, in house, ongoing issue)
- ✅ No repetition of "מבין אותך, זה לא נעים בכלל"
- ✅ Natural conversation flow

**Failure Indicators**:
- ❌ Bot asks for same information twice
- ❌ Bot gives same response multiple times
- ❌ Bot forgets what service you wanted
- ❌ Generic responses not related to your messages

### Scenario 2: Response Variety Test
**Goal**: Verify bot doesn't repeat same response for different inputs

**Steps**:
1. Send: "היי"
2. Send: "שלום"
3. Send: "מה נשמע?"
4. Send: "אני צריך עזרה"
5. Send: "יש לי בעיה"

**Expected Results**:
- ✅ Each response is different
- ✅ Responses are contextually appropriate
- ✅ Bot doesn't use exact same wording repeatedly

**Failure Indicators**:
- ❌ Same response for different greetings
- ❌ Robotic, repetitive language
- ❌ Ignoring user's specific wording

### Scenario 3: Long Conversation Test (20+ Messages)
**Goal**: Verify context is maintained even in very long conversations

**Steps**:
1. Have a natural 20+ message conversation
2. Reference something mentioned early in the conversation
3. Verify bot still remembers it

**Expected Results**:
- ✅ Bot maintains context throughout
- ✅ Can reference earlier conversation points
- ✅ Natural conversation flow maintained

### Scenario 4: Multiple Topic Test
**Goal**: Verify bot can handle topic changes while maintaining context

**Steps**:
1. Start with pest control inquiry
2. Ask about pricing
3. Ask about scheduling
4. Ask about service area
5. Return to original pest control question

**Expected Results**:
- ✅ Bot handles each topic appropriately
- ✅ Can switch between topics smoothly
- ✅ Remembers context when returning to previous topic

## Automated Checks

### Log Monitoring

**Check 1: Conversation ID Consistency**
```bash
# Should see same conversation_id for same customer
grep "conversation_id=wa_10_" logs/app.log | tail -20
```

**Expected**: Same conversation_id appears for multiple messages from same customer

**Check 2: Agent Cache Hits**
```bash
# Should NOT see frequent agent creation (only once per 30 min)
grep "Agent created for business" logs/app.log | tail -20
```

**Expected**: Infrequent agent creation messages (max once per 30 minutes per business)

**Check 3: Repetitive Response Warnings**
```bash
# Should NOT see these warnings in healthy conversations
grep "Possible repetitive responses detected" logs/app.log
```

**Expected**: No warnings, or very rare warnings only in edge cases

**Check 4: Response Length**
```bash
# Should see varied response lengths, averaging around 100-400 chars in Hebrew
grep "Agent response generated:" logs/app.log | tail -20
```

**Expected**: Response lengths vary, typically 100-400 characters

**Check 5: Context Loading**
```bash
# Should see 20 messages loaded (or fewer for new conversations)
grep "Loaded .* previous messages for context" logs/app.log | tail -20
```

**Expected**: "Loaded N previous messages" where N increases with conversation length (up to 20)

## Performance Benchmarks

### Before Fix (Baseline)
- Agent cache: 5 minutes TTL
- Max tokens: 60
- Temperature: 0.0
- History: 12 messages
- **Issues**: Context loss after 5 min, repetitive responses, truncated messages

### After Fix (Target)
- Agent cache: 30 minutes TTL ✅
- Max tokens: 150 ✅
- Temperature: 0.3 ✅
- History: 20 messages ✅
- **Expected**: Maintained context, varied responses, complete messages

### Key Metrics to Monitor

1. **Conversation Length Before Context Loss**
   - Before: ~5 messages
   - Target: 20+ messages ✅

2. **Response Uniqueness Ratio**
   - Before: Low (same response repeated)
   - Target: High (varied responses) ✅

3. **Average Response Length (Hebrew)**
   - Before: ~60 chars (~15 words)
   - Target: ~150 chars (~40 words) ✅

4. **User Satisfaction Indicators**
   - Fewer repeated questions from users
   - Natural conversation flow
   - Successful task completion

## Debugging Commands

### View Conversation Statistics
```python
from server.agent_tools.agent_factory import get_conversation_stats

# Get all conversation stats
all_stats = get_conversation_stats()
print(f"Active conversations: {len(all_stats)}")
for conv_id, stats in all_stats.items():
    print(f"\n{conv_id}:")
    print(f"  Turn count: {stats['turn_count']}")
    print(f"  Last updated: {stats['last_updated']}")
    print(f"  Last message: {stats['last_message_preview']}")
    print(f"  Last response: {stats['last_response_preview']}")

# Get specific conversation stats
conv_stats = get_conversation_stats("wa_10_972501234567_s_whatsapp_net")
print(f"Stats: {conv_stats}")
```

### Clear Conversation Stats (Debug)
```python
from server.agent_tools.agent_factory import clear_conversation_stats

# Clear all stats
clear_conversation_stats()

# Clear specific conversation
clear_conversation_stats("wa_10_972501234567_s_whatsapp_net")
```

### Force Agent Cache Refresh
```python
from server.agent_tools.agent_factory import invalidate_agent_cache

# Force refresh for specific business
invalidate_agent_cache(business_id=10)
```

### Check Agent Cache Status
```python
from server.agent_tools.agent_factory import _AGENT_CACHE
from datetime import datetime
import pytz

print(f"Cached agents: {len(_AGENT_CACHE)}")
for key, (agent, cached_time) in _AGENT_CACHE.items():
    business_id, channel = key
    age_minutes = (datetime.now(pytz.UTC) - cached_time).total_seconds() / 60
    print(f"Business {business_id} ({channel}): cached {age_minutes:.1f} minutes ago")
```

## Rollback Procedure

If issues occur after deployment:

```bash
# Revert to previous version
git revert 65bd38e  # Most recent commit
git revert 5d7c59f  # Documentation
git revert bac1bde  # Main fix
git push origin copilot/fix-decrypt-message-error

# Or full rollback to before changes
git reset --hard 7da02c1
git push origin copilot/fix-decrypt-message-error --force
```

## Success Criteria

### Deployment is successful when:
- ✅ No Python syntax errors in logs
- ✅ Bot responds to messages (basic functionality works)
- ✅ Conversations maintain context for 10+ messages
- ✅ No "Possible repetitive responses" warnings in logs
- ✅ Response lengths average 100-400 characters
- ✅ Users can complete tasks without context loss

### Deployment needs investigation if:
- ❌ Python import errors or syntax errors appear
- ❌ Bot doesn't respond to messages
- ❌ Frequent "Possible repetitive responses" warnings
- ❌ Users complain about bot forgetting context
- ❌ Response lengths still very short (<80 chars)

## Monitoring Dashboard

### Key Log Patterns

**Good Signs**:
```
✅ Agent created for business 10 in 123ms
   (Should appear max once per 30 minutes)

📚 Loaded 15 previous messages for context
   (Shows context is being loaded)

[AGENTKIT] ✅ Agent response generated: 145 chars
   (Good response length)

[AGENTKIT] 📝 Response preview: היי! איך אני יכול לעזור לך היום?
   (Natural, relevant response)
```

**Warning Signs**:
```
⚠️ [CONVERSATION] Possible repetitive responses detected
   (Indicates bot is repeating itself)

[AGENTKIT] Agent response generated: 45 chars
   (Too short - may be truncated)

Agent created for business 10 in 123ms
   (If appearing frequently - cache not working)

⚠️ Could not load conversation history
   (Context loading failing)
```

## Contact & Support

If you encounter issues:
1. Check logs for error messages
2. Run debugging commands above
3. Check conversation statistics
4. Review monitoring dashboard
5. Consider rollback if critical

## Summary

This fix should result in:
- ✅ Natural, context-aware conversations
- ✅ Varied responses based on user input
- ✅ Complete Hebrew sentences (not truncated)
- ✅ Maintained context across 20+ messages
- ✅ Better user experience overall

Test thoroughly and monitor logs during initial deployment.
