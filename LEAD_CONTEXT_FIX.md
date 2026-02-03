# Lead Context and Agent Context Critical Fixes

## Problem Statement (Hebrew Original)

The issue report identified critical bugs in the AI lead context handling system:

### Key Symptoms from Logs:
1. **PAYLOAD_DEBUG** shows:
   - `lead_context: null` 
   - `appointments: null`
   - All context fields are null

2. **Lead Resolution Works But Context Missing**:
   - `Lead resolved: lead_id=3714, phone=+972...` ✅
   - But lead_context is null ❌

3. **Agent Context Has Wrong Phone**:
   - `[AGENTKIT] Set g.agent_context for tools: phone=135...@lid`
   - ❌ CRITICAL: phone should be E164 format (+972...), not @lid JID

4. **LID Mapping Fails**:
   - `[LID-STORE] Failed to store mapping: Entity namespace for "leads" has no property "business_id"`
   - ❌ Database error prevents mapping storage

## Root Causes Identified

### 1. Database Field Mismatch (contact_identity_service.py)
**Location**: `store_lid_phone_mapping()` method, lines 677-685

**Bug**: Code uses `business_id` field on Lead model, but the model actually uses `tenant_id`

```python
# BEFORE (BROKEN):
lead = Lead.query.filter_by(
    business_id=business_id,  # ❌ Field doesn't exist
    phone_e164=phone_e164
).first()
lead.business_id = business_id  # ❌ Field doesn't exist

# AFTER (FIXED):
lead = Lead.query.filter_by(
    tenant_id=business_id,  # ✅ Correct field name
    phone_e164=phone_e164
).first()
lead.tenant_id = business_id  # ✅ Correct field name
```

**Impact**: LID→phone mapping couldn't be stored, breaking the "single source of truth"

### 2. Lead Context Not Loaded (routes_whatsapp.py)
**Location**: Two places where `ai_context` is built (lines 1363-1411, 2614-2652)

**Bug**: WhatsApp message handler never loads unified lead context from `UnifiedLeadContextService`

```python
# BEFORE (BROKEN):
ai_context = {
    'lead_id': lead.id,
    'phone': from_number_e164,
    # ... other fields ...
    # ❌ NO lead_context field
}

# AFTER (FIXED):
# Load unified lead context
lead_context_payload = None
if lead and lead.id:
    from server.services.unified_lead_context_service import get_unified_context_for_lead
    lead_context_payload = get_unified_context_for_lead(
        business_id=business_id,
        lead_id=lead.id,
        channel='whatsapp'
    )

ai_context = {
    'lead_id': lead.id,
    'phone': from_number_e164,
    # ... other fields ...
    'lead_context': lead_context_payload.dict() if lead_context_payload else None  # ✅ Added
}
```

**Impact**: AI never received appointments, notes, status labels, or any CRM context

### 3. Agent Context Uses Wrong Phone (ai_service.py)
**Location**: `generate_response_with_agent()` method, lines 1032-1060

**Bug**: `g.agent_context` uses `customer_phone` parameter which can be an @lid JID, not a real phone

```python
# BEFORE (BROKEN):
g.agent_context = {
    "customer_phone": customer_phone,  # ❌ May be @lid JID like "135...@lid"
    "phone": customer_phone,           # ❌ Same problem
    "whatsapp_from": customer_phone,
    # ...
}

# AFTER (FIXED):
# Extract phone_e164 from lead_context if available
phone_e164 = None
if context and context.get('lead_context'):
    lead_ctx = context['lead_context']
    phone_e164 = lead_ctx.get('lead_phone')  # ✅ Real E.164 phone

# Fallback chain
if not phone_e164 and context:
    phone_e164 = context.get('phone')
if not phone_e164:
    phone_e164 = customer_phone  # Last resort

g.agent_context = {
    "phone": phone_e164,          # ✅ E.164 format
    "phone_e164": phone_e164,     # ✅ Explicit E.164 field
    "customer_phone": customer_phone,  # Original for reference
    "whatsapp_from": customer_phone,   # Conversation key
    # ...
}
```

**Impact**: Tools received @lid JIDs instead of phone numbers, breaking SMS, calls, etc.

### 4. Missing Error Detection (ai_service.py)
**Location**: Before lead context injection, line 1110

**Added**: Critical validation check

```python
# NEW VALIDATION:
if context and context.get('lead_id'):
    if not context.get('lead_context'):
        logger.error(f"[CONTEXT] ❌ CRITICAL: lead_id={context.get('lead_id')} "
                   f"exists but lead_context is None! Check UnifiedLeadContextService.")
```

**Impact**: Makes it immediately obvious when "single source of truth" is broken

## Files Changed

1. **server/services/contact_identity_service.py**
   - Fixed `store_lid_phone_mapping()` to use `tenant_id` instead of `business_id`
   - Lines 677-680, 685

2. **server/routes_whatsapp.py** 
   - Added lead context loading in Baileys handler (lines 1377-1411)
   - Added lead context loading in Meta WhatsApp handler (lines 2624-2652)
   - Both locations now include `lead_context` in `ai_context`

3. **server/services/ai_service.py**
   - Fixed `g.agent_context` phone extraction (lines 1032-1060)
   - Added critical validation check (lines 1110-1115)

4. **tests/test_lead_context_fix.py** (NEW)
   - Test suite validating all fixes
   - Covers: tenant_id usage, phone extraction, context loading, validation

## Expected Improvements

After these fixes:

### ✅ Logs Should Show:
```
[WA-CONTEXT] ✅ Loaded unified lead context: lead_id=3714, appointments=2
[AGENTKIT] 🎧 Injected lead context: lead_id=3714, notes=5, next_apt=Yes
[AGENTKIT] ✅ Set g.agent_context for tools: phone_e164=+972557270844
[PAYLOAD_DEBUG] lead_context: {found: true, lead_id: 3714, ...}
```

### ✅ No More Errors:
- ❌ `Entity namespace for "leads" has no property "business_id"` → GONE
- ❌ `lead_context: null` → FIXED
- ❌ `phone=135...@lid` in agent_context → FIXED

## Testing

Run the test suite:
```bash
pytest tests/test_lead_context_fix.py -v
```

Manual verification:
1. Send WhatsApp message from @lid user
2. Check logs for:
   - Lead context loaded successfully
   - phone_e164 in agent_context is E.164 format
   - PAYLOAD_DEBUG shows lead_context with actual data
3. Verify tools receive correct phone numbers

## References

- Original issue: See problem_statement (Hebrew)
- Unified Lead Context Service: `server/services/unified_lead_context_service.py`
- Contact Identity Service: `server/services/contact_identity_service.py`
- Lead Model: `server/models_sql.py` (uses `tenant_id`, not `business_id`)
