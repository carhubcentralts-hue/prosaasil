# OpenAI Conversation ID Error Fix

## Problem

The system was failing with OpenAI Agents SDK errors:

```
Error code: 400 - {'error': {'message': "Invalid 'conversation': 'wa_10_972504294724_s_whatsapp_net'. Expected an ID that begins with 'conv'.", 'type': 'invalid_request_error', 'param': 'conversation', 'code': 'invalid_value'}}
```

This caused AgentKit to fail and fall back to regular response generation, losing tool-calling capabilities (appointment booking, lead search, etc.).

## Root Cause

The system was generating custom conversation IDs like:
- `wa_10_972504294724_s_whatsapp_net`
- `wa_10_972501234567`

And passing them to OpenAI's Agents SDK via the `conversation_id` parameter in `runner.run()`.

However, OpenAI's API has strict requirements:
- Conversation IDs must start with `conv` prefix
- OR conversation_id should not be specified (let OpenAI generate)

## Solution

**Removed the `conversation_id` parameter** from the OpenAI Agents SDK call.

### Changes Made

**File: `server/services/ai_service.py`**

```python
# BEFORE (causing 400 error):
agent_coroutine = runner.run(
    agent, 
    message,
    context=agent_context,
    conversation_id=conversation_id  # ❌ Custom ID not accepted
)

# AFTER (fixed):
agent_coroutine = runner.run(
    agent, 
    message,
    context=agent_context
    # NOTE: conversation_id removed - OpenAI expects 'conv' prefix or generates its own
)
```

### How Conversation History Works Now

1. **Internal Tracking**: We still generate conversation_id internally for monitoring/logging
   - Shows in logs as `tracking_id=wa_10_972504294724_s_whatsapp_net`
   - Used by `track_conversation_turn()` for repetitive response detection

2. **OpenAI History**: Conversation context is provided via `previous_messages` in agent_context
   - Load last 20 messages from database
   - Format as: `["לקוח: message", "עוזר: response", ...]`
   - Pass in context dict to agent

3. **Result**: 
   - AgentKit calls succeed without 400 errors
   - Tool calling works (appointments, lead search, etc.)
   - Context maintained through previous_messages

## Testing

### Before Fix
```log
2026-02-01 11:00:35 [ERROR] openai.agents: Error getting response: Error code: 400
2026-02-01 11:00:35 [ERROR] server.services.ai_service: [AGENTKIT] Agent error (falling back to regular response)
2026-02-01 11:00:40 [INFO] server.routes_whatsapp: [WA-OUTGOING] 📤 Sending AI reply (fallback response)
```

### After Fix
```log
2026-02-01 11:05:35 [INFO] server.services.ai_service: [AGENTKIT] 🔑 tracking_id=wa_10_972504294724_s_whatsapp_net
2026-02-01 11:05:35 [INFO] server.services.ai_service: [AGENTKIT] 📊 Context: business_id=10, channel=whatsapp, has_previous_messages=True, previous_msg_count=15
2026-02-01 11:05:36 [INFO] server.services.ai_service: [AGENTKIT] ✅ Agent response generated: 150 chars
2026-02-01 11:05:36 [INFO] server.routes_whatsapp: [WA-SUCCESS] ✅✅✅ FULL FLOW COMPLETED: webhook → AgentKit → sendMessage queued ✅✅✅
```

## Impact

### Positive
- ✅ AgentKit calls work reliably
- ✅ Tool calling available (appointments, leads, etc.)
- ✅ No more 400 errors from OpenAI
- ✅ Conversation context maintained via previous_messages
- ✅ Internal tracking still works for monitoring

### Potential Considerations
- OpenAI manages conversation state internally (no custom IDs)
- Previous_messages array provides context for each request
- If OpenAI's internal conversation tracking has limits, we handle via previous_messages

## Monitoring

### Logs to Watch

**Success Pattern**:
```
[AGENTKIT] 🔑 tracking_id=wa_10_...
[AGENTKIT] 📊 Context: ... previous_msg_count=N
[AGENTKIT] ✅ Agent response generated: N chars
```

**Error Pattern** (should not appear anymore):
```
[ERROR] openai.agents: Error getting response: Error code: 400
```

### Metrics
- **AgentKit Success Rate**: Should be ~100% (was failing before)
- **Tool Usage**: Should see tool calls (calendar_find_slots, leads_search, etc.)
- **Response Quality**: Should maintain context across messages

## Related Documentation

- `WHATSAPP_CONTEXT_FIX_SUMMARY.md` - Previous context retention improvements
- `WHATSAPP_CONTEXT_TESTING_GUIDE.md` - Testing conversation flows
- `server/agent_tools/agent_factory.py` - Agent creation and configuration

## Summary

**Problem**: Custom conversation IDs caused 400 errors with OpenAI Agents SDK  
**Solution**: Remove conversation_id parameter, rely on previous_messages for context  
**Result**: AgentKit works reliably with full tool-calling capabilities  
**Status**: ✅ FIXED and deployed
