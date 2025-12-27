# Prompt Architecture Documentation - Production Ready ✅

## Overview

The conversation system uses a **layered prompt architecture** with perfect separation between system rules and business content. This ensures:
- ✅ No duplicated rules
- ✅ No hardcoded content
- ✅ No cross-business contamination
- ✅ Full dynamic control via database

## Architecture Layers

### Layer 1: Universal System Prompt (Behavior Rules Only)

**File**: `server/services/realtime_prompt_builder.py` → `_build_universal_system_prompt()`

**Purpose**: Technical behavior rules that apply to ALL businesses

**Contains**:
- Call isolation rules (prevent cross-business contamination)
- Language rules (Hebrew, natural speech)
- Customer name usage rules
- Turn-taking rules (barge-in handling)
- Transcription truth rules (STT is source of truth)
- Conversation style rules (concise, warm, natural)

**Does NOT contain**:
- ❌ Business-specific content
- ❌ Hardcoded greetings
- ❌ Service-specific logic
- ❌ Hardcoded Hebrew examples
- ❌ Domain-specific examples

**Key Features**:
- Direction-aware (inbound vs outbound)
- English instructions (AI speaks Hebrew to customers)
- ~1200 chars sanitized, ~1900 chars raw
- Single source of truth for behavioral rules

### Layer 2: Appointment Instructions (Technical Only)

**Conditions**: Only injected when `call_goal='appointment'` AND `enable_calendar_scheduling=True`

**Purpose**: Technical scheduling rules (not business content)

**Contains**:
- Date/time handling rules
- Availability checking procedures
- Booking confirmation requirements
- Field collection order

**Does NOT contain**:
- ❌ Business-specific scheduling policies
- ❌ Hardcoded appointment phrases

### Layer 3: Business Prompt (Content and Flow)

**File**: `server/services/realtime_prompt_builder.py` → `build_full_business_prompt()`

**Purpose**: ALL business-specific content, flow, and script

**Contains**:
- Business greeting
- Service descriptions
- Conversation flow
- Information collection process
- Closing phrases
- Business-specific rules

**Source**: Database (`BusinessSettings.ai_prompt` or `BusinessSettings.outbound_ai_prompt`)

**Key Features**:
- Completely dynamic (loaded from DB)
- No hardcoded fallbacks in production
- Supports placeholder replacement (`{{business_name}}`)
- Separate prompts for inbound/outbound

## Prompt Delivery Strategy

### Strategy: COMPACT → FULL

The system uses a two-phase prompt delivery:

1. **COMPACT Prompt** (Phase 1: Greeting)
   - Sent via `session.update.instructions`
   - Contains: Business-only excerpt (~300-400 chars)
   - Purpose: Ultra-fast greeting (<2s)
   - Source: `build_compact_greeting_prompt()`

2. **FULL Prompt** (Phase 2: Post-Greeting)
   - Injected via `conversation.item.create`
   - Contains: Complete business prompt
   - Purpose: Full context for conversation
   - Source: `build_full_business_prompt()`

3. **Global System Prompt** (Injected Separately)
   - Injected via `conversation.item.create` as system message
   - Contains: Universal behavior rules
   - Purpose: Applies to all responses
   - Source: `build_global_system_prompt()`

## Separation Enforcement

### What Goes Where

| Content Type | System Prompt | Business Prompt |
|-------------|---------------|-----------------|
| Behavior rules | ✅ | ❌ |
| Turn-taking | ✅ | ❌ |
| Language rules | ✅ | ❌ |
| Call isolation | ✅ | ❌ |
| Business flow | ❌ | ✅ |
| Greetings | ❌ | ✅ |
| Services | ❌ | ✅ |
| Closing phrases | ❌ | ✅ |

### Validation

Use `validate_business_prompts(business_id)` to check:
- ✅ Inbound prompt exists
- ✅ Outbound prompt exists
- ✅ Greeting exists
- ⚠️ Warnings for missing prompts
- ❌ Errors for critical issues

## Direction-Aware Architecture

### Inbound Calls
- Uses: `BusinessSettings.ai_prompt`
- Function: `build_inbound_system_prompt()`
- Includes: Appointment scheduling if enabled
- Flow: Customer called business → respond naturally

### Outbound Calls
- Uses: `BusinessSettings.outbound_ai_prompt`
- Function: `build_outbound_system_prompt()`
- Includes: Pure prompt mode, no call control
- Flow: Business initiated call → be brief and polite

## Prompt Cache

**File**: `server/services/prompt_cache.py`

**Purpose**: Eliminate DB/prompt building latency

**Key Features**:
- Thread-safe in-memory cache
- TTL: 10 minutes
- Direction-aware keys (`business_id:direction`)
- Automatic invalidation on settings change

**Usage**:
```python
cache = get_prompt_cache()
cached = cache.get(business_id, direction='inbound')
```

## Fallback Handling

### Fallback Chain (in order):

1. **Primary**: `BusinessSettings.ai_prompt` (inbound) or `BusinessSettings.outbound_ai_prompt` (outbound)
2. **Fallback 1**: Alternate direction prompt
3. **Fallback 2**: `Business.system_prompt` (legacy)
4. **Fallback 3**: Minimal generic prompt (logged as ERROR)

### Important Notes:
- ✅ All fallbacks attempt DB first
- ✅ Fallbacks log warnings/errors
- ✅ No hardcoded Hebrew in fallbacks
- ⚠️ Minimal fallback should NEVER happen in production

## Testing

### Test Suite: `test_prompt_architecture.py`

Run: `python3 test_prompt_architecture.py`

Tests:
1. ✅ No hardcoded Hebrew in system prompts
2. ✅ No business-specific content in system prompts
3. ✅ Proper prompt separation
4. ✅ Fallback paths work correctly
5. ✅ Validation function structure
6. ✅ No duplicate rules between layers

## Production Requirements

### For Each Business:

1. **Required**:
   - `BusinessSettings.ai_prompt` (inbound calls)
   - `Business.greeting_message` (first impression)

2. **Optional but Recommended**:
   - `BusinessSettings.outbound_ai_prompt` (outbound calls)
   - `BusinessSettings.enable_calendar_scheduling` (if appointments)

3. **Validation**:
   ```python
   result = validate_business_prompts(business_id)
   if not result['valid']:
       # Handle errors
       print(result['errors'])
   ```

## Best Practices

### DO ✅
- Load ALL content from database
- Use validation before production
- Monitor fallback logs
- Invalidate cache on settings change
- Test with actual business prompts

### DON'T ❌
- Add hardcoded Hebrew in system prompt
- Mix business content in system rules
- Add business logic to universal prompt
- Skip validation
- Ignore fallback ERROR logs

## Troubleshooting

### Issue: Business speaks wrong content
**Solution**: Check `BusinessSettings.ai_prompt` - ensure correct business_id

### Issue: Appointment flow not working
**Solution**: Verify `call_goal='appointment'` AND `enable_calendar_scheduling=True`

### Issue: Bot uses wrong language
**Solution**: System prompt enforces Hebrew - check if business prompt overrides

### Issue: Fallback prompt used
**Solution**: Check logs for `[FALLBACK]` - indicates missing DB configuration

## Monitoring

### Key Log Messages:

- `[PROMPT_CONTEXT]` - Tracks prompt source and mode
- `[PROMPT_DEBUG]` - Prompt length and hash
- `[BUSINESS_ISOLATION]` - Tracks business context
- `[FALLBACK]` - Indicates missing configuration
- `[PROMPT_CACHE HIT/MISS]` - Cache performance

### Critical Errors:

- `CRITICAL: Business X not found` - DB issue
- `[PROMPT ERROR] No prompts available` - Configuration issue
- `Using absolute minimal fallback` - Serious issue, should never happen

## Architecture Benefits

1. **Zero Duplication**: Each rule exists in exactly one place
2. **Zero Hardcoding**: All content from database
3. **Zero Cross-Contamination**: Each call isolated by business_id
4. **Full Control**: Business admins control all content
5. **Fast Greeting**: Cache eliminates latency
6. **Clear Separation**: System vs business perfectly separated
7. **Easy Testing**: Validation functions and test suite
8. **Production Safe**: Multiple fallback layers with logging

## Version History

- **Build 324+**: Perfect separation architecture
- **Build 333**: Phase-based flow
- **Build 340**: Appointment scheduling separation
- **Current**: Zero hardcoded content, full validation ✅
