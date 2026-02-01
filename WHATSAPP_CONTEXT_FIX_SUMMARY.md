# WhatsApp Context Loss and Repetitive Response Fix

## Problem Description

User reported two critical issues with the WhatsApp bot:

1. **Context Loss**: Bot loses conversation context after approximately 5 messages
2. **Repetitive Responses**: Bot repeats the same response ("מבין אותך, זה לא נעים בכלל") regardless of user input

## Root Causes Identified

### 1. Agent Cache TTL Too Short
- **Problem**: Agent cache was set to expire after only 5 minutes
- **Impact**: Every 5 minutes, a new agent was created with no memory of previous conversations
- **Location**: `server/agent_tools/agent_factory.py:37`

### 2. Max Tokens Too Restrictive
- **Problem**: `max_tokens` was set to 60 tokens (~15 words in Hebrew)
- **Impact**: Responses were truncated, leading to repetitive and incomplete answers
- **Location**: `server/agent_tools/agent_factory.py:69`

### 3. Temperature Too Deterministic
- **Problem**: Temperature was set to 0.0 (completely deterministic)
- **Impact**: Same user input would always produce the same response, causing repetition
- **Location**: `server/agent_tools/agent_factory.py:68`

### 4. Limited Conversation History
- **Problem**: Only 12 previous messages were loaded for context
- **Impact**: Insufficient context for longer conversations
- **Location**: `server/routes_whatsapp.py:1104`

## Solutions Implemented

### 1. Increased Agent Cache TTL (5 → 30 minutes)
```python
# Before:
_CACHE_TTL_MINUTES = 5  # Too short!

# After:
_CACHE_TTL_MINUTES = 30  # Maintains context for longer conversations
```
**Benefits**: Agents persist for full conversations, maintaining context across multiple messages.

### 2. Increased Max Tokens (60 → 150)
```python
# Before:
max_tokens=60,  # ~15 words in Hebrew - too restrictive!

# After:
max_tokens=150,  # ~40 words in Hebrew - allows proper responses
```
**Benefits**: Enables complete, natural Hebrew responses without truncation.

### 3. Adjusted Temperature (0.0 → 0.3)
```python
# Before:
temperature=0.0,  # Completely deterministic

# After:
temperature=0.3,  # Varied responses while maintaining consistency
```
**Benefits**: Responses vary appropriately while maintaining business tone and accuracy.

### 4. Increased Conversation History (12 → 20 messages)
```python
# Before:
.limit(12).all()  # 12 messages

# After:
.limit(20).all()  # 20 messages for better context
```
**Benefits**: Provides more context for the AI to understand conversation flow.

### 5. Added Conversation Tracking System
New functions added to detect and log repetitive responses:
- `track_conversation_turn()`: Tracks each conversation turn
- `get_conversation_stats()`: Retrieves conversation statistics
- `clear_conversation_stats()`: Clears statistics for debugging

**Benefits**: 
- Automatic detection of repetitive response patterns
- Better debugging capabilities
- Early warning system for context loss issues

### 6. Enhanced Logging
Added detailed logging for:
- `conversation_id` tracking
- Previous message count
- Response previews
- Context information

**Benefits**: Better visibility into conversation flow and easier debugging.

## How It Works

### OpenAI Conversation Management
The system uses OpenAI's Agents SDK which manages conversation history server-side via a `conversation_id`:

```python
conversation_id = self._generate_conversation_id(business_id, context, customer_phone)
runner.run(agent, message, context=agent_context, conversation_id=conversation_id)
```

Each customer gets a unique `conversation_id` based on:
- Business ID
- Remote JID (WhatsApp identifier)
- Phone number (E.164 format)

This ensures:
1. Each customer's conversation is isolated
2. Context is maintained across messages
3. Conversation history is managed reliably by OpenAI

### Agent Caching Strategy
Agents are now cached for 30 minutes with the following benefits:
- Reduced latency (no agent recreation overhead)
- Consistent conversation experience
- Automatic prompt updates after cache expiration
- Manual cache invalidation available via `invalidate_agent_cache(business_id)`

## Testing and Verification

### Automated Checks
The system now includes:
1. **Repetitive Response Detection**: Automatically logs warnings when same response appears repeatedly
2. **Conversation Statistics**: Tracks turn count, last updated time, and response patterns
3. **Enhanced Logging**: Clear visibility into conversation flow

### Manual Testing Checklist
- [ ] Send 10+ messages in a single conversation
- [ ] Verify responses vary based on user input
- [ ] Confirm no repeated "מבין אותך, זה לא נעים בכלל" responses
- [ ] Check conversation maintains context throughout
- [ ] Verify responses are complete and natural (not truncated)

## Monitoring

### Log Patterns to Watch For

**Healthy Conversation:**
```
[AGENTKIT] 🔑 conversation_id=wa_10_972501234567_s_whatsapp_net
[AGENTKIT] 📊 Context: business_id=10, has_previous_messages=True, previous_msg_count=8
[AGENTKIT] ✅ Agent response generated: 145 chars
[AGENTKIT] 📝 Response preview: היי! איך אני יכול לעזור לך היום?...
```

**Warning - Repetitive Responses:**
```
⚠️ [CONVERSATION] Possible repetitive responses detected: conversation_id=wa_10_..., turn_count=6, unique_responses=1
```

**Error - Agent Recreation:**
```
✅ Agent created for business 10 in 123ms
```
*Note: Should only appear once per 30 minutes per business+channel*

## Configuration

### Environment Variables
No new environment variables required. Existing variables:
- `AGENTS_ENABLED=1` (default: enabled)
- `OPENAI_API_KEY` (required for AI responses)

### Database Settings
Prompts are loaded from:
```sql
SELECT ai_prompt FROM business_settings WHERE tenant_id = :business_id
```

The `ai_prompt` field supports:
1. **JSON format** (recommended):
   ```json
   {
     "whatsapp": "Your WhatsApp prompt...",
     "calls": "Your phone calls prompt..."
   }
   ```

2. **Legacy format** (single string):
   ```
   Your universal prompt...
   ```

## Rollback Plan

If issues occur, revert these three files:
1. `server/agent_tools/agent_factory.py`
2. `server/services/ai_service.py`
3. `server/routes_whatsapp.py`

Command:
```bash
git revert <commit_hash>
```

## Files Modified

1. **server/agent_tools/agent_factory.py** (+76 lines)
   - Increased `_CACHE_TTL_MINUTES` from 5 to 30
   - Increased `max_tokens` from 60 to 150
   - Changed `temperature` from 0.0 to 0.3
   - Added conversation tracking functions

2. **server/services/ai_service.py** (+16 lines)
   - Enhanced logging for conversation tracking
   - Added conversation turn tracking
   - Better response preview in logs

3. **server/routes_whatsapp.py** (+11 lines)
   - Increased conversation history from 12 to 20
   - Added debug logging for message context

## Expected Outcomes

After deployment, users should experience:
1. ✅ **No Context Loss**: Conversations maintain context for 20+ messages
2. ✅ **Varied Responses**: AI responds appropriately to different user inputs
3. ✅ **Complete Responses**: Full Hebrew sentences (not truncated)
4. ✅ **Natural Flow**: Conversations feel natural and contextual
5. ✅ **Better Debugging**: Clear logs for troubleshooting

## Support and Troubleshooting

### Common Issues

**Issue**: Bot still repeating responses
- **Check**: Look for `⚠️ [CONVERSATION] Possible repetitive responses` in logs
- **Action**: Verify `temperature` is set to 0.3 in `agent_factory.py`

**Issue**: Responses still too short
- **Check**: Verify `max_tokens=150` in `agent_factory.py`
- **Action**: Consider increasing further if needed (max: 4096)

**Issue**: Context loss after 30 minutes
- **Expected**: Agent cache expires after 30 minutes
- **Action**: This is normal behavior to allow prompt updates
- **Workaround**: If longer retention needed, increase `_CACHE_TTL_MINUTES`

### Debug Commands

View conversation statistics:
```python
from server.agent_tools.agent_factory import get_conversation_stats
stats = get_conversation_stats()
print(stats)
```

Clear conversation stats:
```python
from server.agent_tools.agent_factory import clear_conversation_stats
clear_conversation_stats()  # Clear all
# or
clear_conversation_stats("wa_10_972501234567_s_whatsapp_net")  # Clear specific
```

Force agent cache refresh:
```python
from server.agent_tools.agent_factory import invalidate_agent_cache
invalidate_agent_cache(business_id=10)
```

## Summary

This fix addresses the core issues causing context loss and repetitive responses by:
1. Extending agent lifetime (5 → 30 minutes)
2. Allowing longer responses (60 → 150 tokens)
3. Enabling response variation (temperature 0.0 → 0.3)
4. Providing more context (12 → 20 messages)
5. Adding monitoring and detection systems

The changes are minimal, focused, and preserve all existing functionality while significantly improving conversation quality.
