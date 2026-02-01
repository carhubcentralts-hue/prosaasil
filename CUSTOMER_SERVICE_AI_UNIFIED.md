# Customer Service AI Unification - Architecture Documentation

## Overview

This document describes the unified Customer Service AI architecture implemented to create a single source of truth for lead context and status updates across WhatsApp and Calls channels.

## Problem Statement

Previously, the system had duplicated and inconsistent implementations:
- Lead context was built differently for WhatsApp vs Calls
- Status updates happened in multiple places without audit logging
- Feature flags were not consistently applied
- Context injection was partially implemented

## Solution

### Core Principles

1. **Single Source of Truth**: One authoritative service for each concern
2. **Channel Agnostic**: Same data structure and behavior for WhatsApp and Calls
3. **Feature Flag Controlled**: `enable_customer_service` controls everything
4. **Audit Trail**: All changes logged with reason and confidence
5. **Multi-tenant Safe**: All operations scoped to business_id

## New Components

### 1. Unified Lead Context Service

**File**: `server/services/unified_lead_context_service.py`

**Purpose**: Single source of truth for lead context across all channels

**Key Features**:
- Standard `UnifiedLeadContextPayload` schema
- Loads: lead info, status, appointments, notes, summaries, tags, memory
- Feature flag aware (`enable_customer_service`)
- Multi-tenant secure
- Formatting for AI prompt injection

**API**:
```python
# Get context by phone
context = get_unified_context_for_phone(business_id, phone, channel="whatsapp")

# Get context by WhatsApp JID
context = get_unified_context_for_whatsapp_jid(business_id, jid)

# Get context by lead ID
context = get_unified_context_for_lead(business_id, lead_id, channel="call")

# Format for prompt
service = UnifiedLeadContextService(business_id)
text = service.format_context_for_prompt(context)
```

**Context Payload Structure**:
```python
{
    "found": bool,
    "lead_id": int,
    "lead_name": str,
    "lead_phone": str,
    "current_status": str,
    "pipeline_stage": str,
    "next_appointment": {...},
    "past_appointments": [...],
    "recent_notes": [...],  # AI-visible only (call_summary, system, customer_service_ai)
    "last_call_summary": str,
    "customer_memory": str,
    "tags": [...],
    "service_type": str,
    "city": str,
    "recent_calls_count": int,
    "recent_whatsapp_count": int
}
```

### 2. Unified Status Service

**File**: `server/services/unified_status_service.py`

**Purpose**: Single source of truth for status updates

**Key Features**:
- Status validation and progression logic
- Status family equivalence checking
- Audit logging (who, when, channel, reason, confidence)
- Multi-tenant security
- Webhook notification support

**API**:
```python
# Update status
result = update_lead_status_unified(
    business_id=1,
    lead_id=123,
    new_status="appointment_scheduled",
    reason="לקוח קבע פגישה ליום ראשון",
    confidence=1.0,
    channel="whatsapp",
    metadata={"tool": "update_lead_status"}
)

# Result
{
    "success": bool,
    "message": str,
    "old_status": str,
    "new_status": str,
    "skipped": bool,
    "audit_id": int
}
```

**Status Families** (for equivalence checking):
- NO_ANSWER: no_answer, voicemail, busy, failed
- INTERESTED: interested, hot, warm
- QUALIFIED: qualified, appointment, meeting
- NOT_RELEVANT: not_relevant, not_interested, lost
- FOLLOW_UP: follow_up, callback
- CONTACTED: contacted, answered
- ATTEMPTING: attempting, trying
- NEW: new, fresh, lead

### 3. Status Update Tool

**File**: `server/agent_tools/tools_status_update.py`

**Purpose**: AI agent tool for updating lead status

**Tool Signature**:
```python
@function_tool
def update_lead_status(input: UpdateLeadStatusInput) -> UpdateLeadStatusOutput:
    """
    Update lead status with audit logging and validation.
    
    Args:
        business_id: Business ID
        lead_id: Lead ID
        status: New status value
        reason: Clear reason for status change
        confidence: Confidence level (0.0-1.0)
    """
```

**AI Guidelines**:
- Only update when there's a CLEAR signal from conversation
- Do NOT guess or assume
- Always provide specific reason
- Use confidence scoring

**Examples**:
- ✅ "נקבעה פגישה ליום ראשון" → status=appointment_scheduled
- ✅ "תתקשרו אליי מחר" → status=callback_requested
- ✅ "טעיתם במספר" → status=not_relevant
- ❌ Updating to "interested" just because lead answered
- ❌ Guessing status based on tone

## Integration Points

### WhatsApp Pipeline

**Files Modified**:
1. `server/jobs/webhook_process_job.py`
   - Loads unified lead context before AI generation
   - Passes context to AI service

2. `server/services/ai_service.py`
   - Injects lead context as system message
   - Formats context for AI consumption

3. `server/agent_tools/agent_factory.py`
   - Adds status update tool when customer service enabled
   - Conditionally exposes CRM tools

**Flow**:
```
Webhook → Load Lead Context (if enabled) → Build Context Dict → AI Service
         ↓
    Format Context → Prepend as System Message → Agent.run()
                     ↓
              Status Update Tool (if needed) → Unified Status Service
```

### Calls Pipeline

**Files Modified**:
1. `server/media_ws_ai.py`
   - Passes caller phone to prompt builder
   - Enables lead context lookup

2. `server/services/realtime_prompt_builder.py`
   - Added Layer 4: Lead Context injection
   - Loads context only when enabled
   - Formats context for realtime AI

**Flow**:
```
Call Starts → Build Prompt → Load Lead Context (if enabled)
              ↓
      Format Context → Inject as Layer 4 → Full Prompt
                       ↓
               Realtime API Session
```

**Prompt Layers** (in order):
1. Universal System Prompt (behavior only)
2. Appointment Instructions (if enabled)
3. Business Prompt (all content and flow)
4. **Lead Context (if customer service enabled)** ← NEW
5. Call Type (INBOUND/OUTBOUND)

## Feature Flag Control

**Flag**: `BusinessSettings.enable_customer_service`

**Controls**:
- ✅ Lead context injection (both channels)
- ✅ CRM tools exposure (find_lead, get_context, create_note, etc.)
- ✅ Status update tool exposure
- ✅ Auto-status updates

**When Disabled**:
- ❌ No lead context loaded
- ❌ No CRM tools available
- ❌ No status update tool
- ❌ No auto-status updates
- ✅ Basic AI still works (from DB prompt only)

## Audit Logging

**Status Update Audit**:
```python
{
    "lead_id": int,
    "tenant_id": int,
    "old_status": str,
    "new_status": str,
    "changed_by": None,  # AI/automated
    "change_reason": str,
    "confidence_score": float,
    "channel": str,  # "whatsapp", "call", "manual", "system"
    "metadata_json": {...},
    "created_at": datetime
}
```

**Log Examples**:
```
[UnifiedStatus] ✅ Updated lead 123 status: new → appointment_scheduled (channel=whatsapp, confidence=1.0, audit_id=456)
[UnifiedContext] ✅ Loaded context for lead #123: 5 notes, next_apt=Yes
```

## Migration Notes

### Backward Compatibility

- Existing code continues to work (no breaking changes)
- New unified services are opt-in via feature flag
- Old services still exist but are now partially redundant:
  - `customer_intelligence.py` - find/create logic still used
  - `customer_memory_service.py` - memory loading now in unified service
  - `tools_crm_context.py` - tools still available, context building unified
  - `lead_auto_status_service.py` - status logic now in unified service

### Recommended Migration Path

1. **Enable feature flag** for one test business
2. **Test both channels** (WhatsApp + Calls)
3. **Verify context injection** in logs
4. **Test status updates** and check audit logs
5. **Roll out gradually** to more businesses
6. **Monitor for issues** in production
7. **Deprecate old services** after full migration

## Testing Checklist

### WhatsApp
- [ ] Existing lead shows context awareness
- [ ] Status update creates audit log
- [ ] Feature flag disabled = no context/tools
- [ ] Cross-channel: same context as Calls

### Calls
- [ ] Existing lead shows context in prompt
- [ ] Status update works correctly
- [ ] Feature flag disabled = no context
- [ ] Cross-channel: same context as WhatsApp

### Status Updates
- [ ] Audit log created with all fields
- [ ] Status families prevent duplicates
- [ ] Progression validation works
- [ ] Confidence scoring recorded

### Feature Flags
- [ ] Enabled: context + tools available
- [ ] Disabled: no context, no tools
- [ ] Per-business control works

## Performance Considerations

1. **Import Overhead**: All imports moved to module level
2. **Database Queries**: Context loading batched efficiently
3. **Caching**: Prompt cache still works (10min TTL)
4. **Agent Cache**: Agents cached 30min per business/channel

## Security

1. **Multi-tenant Isolation**: All queries scoped to business_id
2. **Data Redaction**: Sensitive data redacted in notes
3. **Feature Flag Control**: Unauthorized access prevented
4. **Audit Trail**: All changes logged

## Modified Files Summary

### New Files (3)
1. `server/services/unified_lead_context_service.py` - Lead context (565 lines)
2. `server/services/unified_status_service.py` - Status updates (436 lines)
3. `server/agent_tools/tools_status_update.py` - Status tool (118 lines)

### Modified Files (5)
1. `server/jobs/webhook_process_job.py` - WhatsApp context injection
2. `server/services/ai_service.py` - Context formatting for AI
3. `server/agent_tools/agent_factory.py` - Status tool registration
4. `server/services/realtime_prompt_builder.py` - Calls context injection
5. `server/media_ws_ai.py` - Pass caller phone to prompt builder

## Future Enhancements

1. **Status History**: Implement LeadStatusHistory model if not exists
2. **Webhook Triggers**: Complete status change webhook integration
3. **Cross-channel Memory**: Enhanced memory persistence
4. **Analytics**: Context usage and status change analytics
5. **A/B Testing**: Compare with/without context performance

## Support

For questions or issues:
1. Check logs for `[UnifiedContext]` and `[UnifiedStatus]` markers
2. Verify feature flag is enabled: `BusinessSettings.enable_customer_service`
3. Check audit logs for status updates
4. Review this documentation for expected behavior

---

**Last Updated**: 2026-02-01
**Version**: 1.0
**Author**: AI Copilot Agent
