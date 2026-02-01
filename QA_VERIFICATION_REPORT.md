# QA Verification Report for Customer Service AI Unification

## Executive Summary

This document provides a comprehensive QA verification checklist and test results for the Customer Service AI unification. All tests must pass before merging to production.

## Test Environment Setup

```bash
# Ensure enable_customer_service flag exists in database
#BusinessSettings table should have enable_customer_service column (boolean)
```

---

## 1. Smoke Tests - Nothing Broken ✅

### WhatsApp Tests

#### Test 1.1: Basic Message Flow
**Steps**:
1. Send WhatsApp message "היי" to business number
2. Expect: AI responds appropriately
3. Send second message immediately
4. Expect: Conversation continues, no reset

**Expected Logs**:
```
🚀 [WEBHOOK_JOB] tenant=business_1 messages=1
✅ [LEAD_UPSERT_DONE] lead_id=123 action=updated
🤖 [AGENTKIT_START] business_id=1
✅ [AGENTKIT_DONE] latency_ms=1200
📤 [SEND_ATTEMPT] success
```

**Status**: ⏸️ Pending Manual Test

---

#### Test 1.2: Tools Work When Flag ON
**Steps**:
1. Set `enable_customer_service=True` for business
2. Send WhatsApp message that triggers tool use
3. Expect: Tool executes successfully

**Expected Logs**:
```
🎧 Customer service mode ENABLED for business 1 - CRM tools + status update added
[AGENTKIT] 🔧 TOOL: update_lead_status
[UnifiedStatus] ✅ Updated lead 123 status
```

**Status**: ⏸️ Pending Manual Test

---

#### Test 1.3: No Tools When Flag OFF
**Steps**:
1. Set `enable_customer_service=False` for business
2. Send WhatsApp message
3. Expect: No CRM tools available, no context injection

**Expected Logs**:
```
[UnifiedContext] Customer service disabled for business 1
[AGENTKIT] Agent created without CRM tools (flag disabled)
```

**Status**: ⏸️ Pending Manual Test

---

### Calls Tests

#### Test 1.4: Call Connection and Greeting
**Steps**:
1. Make inbound call to business number
2. Expect: Connection succeeds, greeting plays

**Expected Logs**:
```
📞 [PROMPT_ROUTER] Building INBOUND prompt for business 1
✅ [INBOUND] Prompt built: 2500 chars
🚀 [PROMPT] Using PRE-BUILT FULL prompt
✅ [AGENT_CONTEXT] Agent context stored
```

**Status**: ⏸️ Pending Manual Test

---

#### Test 1.5: Transcription Works
**Steps**:
1. During call, speak clearly
2. Expect: Speech recognized and AI responds

**Expected Logs**:
```
[STT] Transcription received
[AI] Response generated
[TTS] Audio sent to caller
```

**Status**: ⏸️ Pending Manual Test

---

#### Test 1.6: Tools Work When Flag ON (Calls)
**Steps**:
1. Set `enable_customer_service=True`
2. Make call from known lead
3. Expect: Lead context injected into prompt

**Expected Logs**:
```
🎧 [LEAD_CONTEXT] Injected context for lead #123 (450 chars)
✅ [INBOUND] Prompt built: 2500 chars (system + business + context)
```

**Status**: ⏸️ Pending Manual Test

---

#### Test 1.7: No Context When Flag OFF (Calls)
**Steps**:
1. Set `enable_customer_service=False`
2. Make call
3. Expect: No lead context in prompt

**Expected Logs**:
```
🎧 [LEAD_CONTEXT] Customer service disabled for business 1
✅ [INBOUND] Prompt built: 2000 chars (system + business only)
```

**Status**: ⏸️ Pending Manual Test

---

### Jobs/Worker Tests

#### Test 1.8: No ImportErrors
**Steps**:
1. Restart worker: `python worker.py`
2. Check logs for import errors

**Expected**: No `ImportError` or `ModuleNotFoundError` for new services

**Status**: ⏸️ Pending Manual Test

---

## 2. Feature Flag Verification (CRITICAL) 🔥

### Test 2.1: Flag OFF - No Context, No Tools

**Setup**:
```sql
UPDATE business_settings SET enable_customer_service = FALSE WHERE tenant_id = 1;
```

**WhatsApp Test**:
1. Send message from existing lead
2. Capture logs

**Required Log Evidence**:
```
[UnifiedContext] Customer service disabled for business 1
customer_service_enabled=False
lead_context_injected=False
tools_exposed=[] (or without update_lead_status)
```

**Calls Test**:
1. Make call from existing lead
2. Capture logs

**Required Log Evidence**:
```
🎧 [LEAD_CONTEXT] Customer service disabled for business 1
[PROMPT] Prompt does NOT contain "LEAD CONTEXT" section
```

**Status**: ⏸️ Pending Manual Test

---

### Test 2.2: Flag ON - Context + Tools Available

**Setup**:
```sql
UPDATE business_settings SET enable_customer_service = TRUE WHERE tenant_id = 1;
```

**WhatsApp Test**:
1. Send message from existing lead (must exist in database)
2. Capture logs

**Required Log Evidence**:
```
[UnifiedContext] ✅ Loaded context for lead #123: 5 notes, next_apt=Yes
[AGENTKIT] 🎧 Injected lead context: lead_id=123, notes=5, next_apt=Yes
[AGENTKIT] 🎧 Prepended lead context to conversation (450 chars)
🎧 Customer service mode ENABLED for business 1 - CRM tools + status update added
tools_exposed=['crm_find_lead_by_phone', 'crm_get_lead_context', 'crm_create_note', 'update_lead_status']
```

**Calls Test**:
1. Make call from existing lead
2. Capture logs

**Required Log Evidence**:
```
🎧 [LEAD_CONTEXT] Injected context for lead #123 (450 chars)
✅ [INBOUND] Prompt built: 2500 chars (system + business + context)
[PROMPT] Contains "LEAD CONTEXT (מידע פנימי על הלקוח)"
```

**Status**: ⏸️ Pending Manual Test

---

## 3. Name Routing Verification ✅

### Test 3.1: Lead with Name → Uses Actual Name

**Setup**:
```sql
-- Ensure lead has name
UPDATE leads SET first_name = 'יוסי', last_name = 'כהן' WHERE id = 123;
```

**Test**:
1. Send WhatsApp or make call from this lead
2. Check logs and AI response

**Expected**:
- Logs show `lead_name="יוסי כהן"`
- AI uses actual name, NOT "לקוח יקר" or generic
- Context includes: `📋 לקוח: יוסי כהן (+972501234567)`

**Status**: ⏸️ Pending Manual Test

---

### Test 3.2: Lead WITHOUT Name → No Generic Name

**Setup**:
```sql
-- Remove name from lead
UPDATE leads SET first_name = NULL, last_name = NULL WHERE id = 456;
```

**Test**:
1. Send WhatsApp or make call from this lead
2. Check logs

**Expected**:
- Logs show `lead_name=None` or empty
- AI uses generic greeting without name: "היי, אשמח לעזור"
- Does NOT invent name like "לקוח" or "מר/גברת"

**Status**: ⏸️ Pending Manual Test

---

### Test 3.3: Business Name Appears Correctly

**Test**:
1. Check logs from any interaction
2. Verify business name appears

**Expected**:
```
[PROMPT] BUSINESS PROMPT (Business ID: 1):
business_name="שם העסק"
```

**Status**: ⏸️ Pending Manual Test

---

### Test 3.4: Calls - Name Anchor Not Broken

**Test**:
1. Check if `realtime_prompt_builder` has name policy
2. Verify name anchor still works

**Expected**:
- If business prompt requests name usage, it should work
- Name detection and usage logic not broken by context injection

**Status**: ⏸️ Pending Manual Test

---

## 4. Status Update Safety 🛡️

### Test 4.1: Same Status → No-Op

**Test**:
```python
# Lead current status: "interested"
# Try to update to: "interested"
result = update_lead_status_unified(
    business_id=1,
    lead_id=123,
    new_status="interested",
    reason="Test",
    confidence=1.0,
    channel="whatsapp"
)
```

**Expected**:
- `result.success = True`
- `result.skipped = True`
- `result.message` contains "unchanged"
- Log: `[UnifiedStatus] Status unchanged for lead 123`

**Status**: ⏸️ Pending Manual Test

---

### Test 4.2: Downgrade → Blocked

**Test**:
```python
# Lead current status: "qualified" (high)
# Try to update to: "contacted" (low)
result = update_lead_status_unified(
    business_id=1,
    lead_id=123,
    new_status="contacted",
    reason="Test downgrade",
    confidence=1.0,
    channel="whatsapp"  # Automated channel
)
```

**Expected**:
- `result.success = False` OR `result.skipped = True`
- Log: `[UnifiedStatus] Invalid status progression`

**Status**: ⏸️ Pending Manual Test

---

### Test 4.3: No Duplicate Updates in Same Interaction

**Test**:
1. In single WhatsApp conversation, trigger status update twice
2. Check logs

**Expected**:
- First update: succeeds
- Second update: skipped (same status or family)
- No loop created

**Status**: ⏸️ Pending Manual Test

---

### Test 4.4: Audit Log Created

**Test**:
1. Update status successfully
2. Check audit log

**Expected**:
```
[UnifiedStatus] ✅ Updated lead 123 status: interested → qualified
                 (channel=whatsapp, confidence=1.0, audit_id=789)
[UnifiedStatus] Created audit log #789 for lead 123
```

**Audit log should contain**:
- `lead_id`, `tenant_id`
- `old_status`, `new_status`
- `changed_by` (None for AI)
- `change_reason`
- `confidence_score`
- `channel`
- `created_at`

**Status**: ⏸️ Pending Manual Test

---

## 5. Performance Verification ⚡

### Test 5.1: Context Build Time - WhatsApp

**Test**:
1. Enable debug logging for context service
2. Send WhatsApp message from existing lead
3. Measure time

**Expected**:
```
[UnifiedContext] Context build completed in 85ms
```

**Requirement**: < 150ms

**Status**: ⏸️ Pending Manual Test

---

### Test 5.2: Context Build Time - Calls

**Test**:
1. Enable debug logging
2. Make call from existing lead
3. Measure time in prompt builder

**Expected**:
```
🎧 [LEAD_CONTEXT] Context build completed in 45ms
```

**Requirement**: < 80ms (realtime requirement)

**Status**: ⏸️ Pending Manual Test

---

### Test 5.3: Query Count Verification

**Test**:
1. Enable SQL query logging
2. Build context for lead
3. Count queries

**Expected**:
- Uses JOINs where possible
- Maximum 5-6 queries per context build
- NOT 10+ individual queries

**Status**: ⏸️ Pending Manual Test

---

## 6. Backward Compatibility ✅

### Test 6.1: Context Payload Has All Fields

**Test**:
```python
from server.services.unified_lead_context_service import UnifiedLeadContextPayload

payload = UnifiedLeadContextPayload(found=True, lead_id=123)

# Check all expected fields exist
assert hasattr(payload, 'lead_name')
assert hasattr(payload, 'current_status')
assert hasattr(payload, 'next_appointment')
assert hasattr(payload, 'recent_notes')
assert hasattr(payload, 'tags')
```

**Status**: ✅ PASS (verified in code)

---

### Test 6.2: Old Code Still Works

**Test**:
1. Check that `tools_crm_context.py` tools still work
2. Verify `customer_intelligence.py` find methods work
3. Ensure no breaking changes to existing APIs

**Expected**:
- Old tools callable
- Return expected formats
- No ImportError or AttributeError

**Status**: ⏸️ Pending Manual Test

---

## Summary Checklist

### Critical Tests (Must Pass) 🔴
- [ ] Feature Flag OFF → No context, no tools (verified in logs)
- [ ] Feature Flag ON → Context injected, tools available (verified in logs)
- [ ] Name routing: actual name used when exists
- [ ] Name routing: no generic when name missing
- [ ] Status update: same status → no-op
- [ ] Status update: downgrade → blocked
- [ ] Performance: WhatsApp < 150ms
- [ ] Performance: Calls < 80ms

### Important Tests (Should Pass) 🟡
- [ ] WhatsApp basic flow works
- [ ] Calls connection works
- [ ] No ImportErrors in worker
- [ ] Audit logs created correctly
- [ ] No duplicate status updates
- [ ] Backward compatibility maintained

### Nice-to-Have Tests (Optional) 🟢
- [ ] Business name appears correctly
- [ ] Query count optimized
- [ ] Status family equivalence works

---

## Required Deliverables

### 1. Log Samples (10 lines each channel)

#### WhatsApp with Flag ON:
```
[Paste actual logs here showing:]
- customer_service_enabled=True
- lead_context_injected=True
- tools_exposed with update_lead_status
- lead_name and business_name
```

#### WhatsApp with Flag OFF:
```
[Paste actual logs here showing:]
- customer_service_enabled=False
- lead_context_injected=False
- no CRM tools
```

#### Calls with Flag ON:
```
[Paste actual logs here showing:]
- lead_context injection
- prompt includes "LEAD CONTEXT" section
- lead_name in context
```

#### Calls with Flag OFF:
```
[Paste actual logs here showing:]
- no lead_context
- prompt without "LEAD CONTEXT" section
```

### 2. Status Update Audit Sample

```
[Paste audit log entry showing all required fields]
```

### 3. Performance Measurements

```
WhatsApp context build: __ms
Calls context build: __ms
Query count: __
```

---

## Approval Criteria

**DO NOT APPROVE UNTIL**:
1. ✅ All Critical Tests pass
2. ✅ Log samples provided for each scenario
3. ✅ Performance requirements met
4. ✅ Name routing verified
5. ✅ No breaking changes confirmed

---

## Notes for Manual Testing

### How to Enable/Disable Feature Flag

```sql
-- Enable customer service AI
UPDATE business_settings SET enable_customer_service = TRUE WHERE tenant_id = 1;

-- Disable customer service AI
UPDATE business_settings SET enable_customer_service = FALSE WHERE tenant_id = 1;
```

### How to Check Logs

```bash
# Tail application logs
tail -f logs/app.log | grep -E "UnifiedContext|UnifiedStatus|LEAD_CONTEXT|customer_service"

# Tail worker logs
tail -f logs/worker.log | grep -E "UnifiedContext|UnifiedStatus"
```

### How to Create Test Lead

```sql
-- Create test lead with name
INSERT INTO leads (tenant_id, phone_e164, first_name, last_name, status, created_at)
VALUES (1, '+972501234567', 'יוסי', 'כהן', 'interested', NOW());

-- Create test lead without name
INSERT INTO leads (tenant_id, phone_e164, status, created_at)
VALUES (1, '+972525951893', 'new', NOW());
```

---

**Document Version**: 1.0
**Date**: 2026-02-01
**Status**: ⏸️ Awaiting Manual Verification
