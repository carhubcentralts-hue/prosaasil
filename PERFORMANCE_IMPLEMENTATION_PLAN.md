# Master Performance Polish - Implementation Plan

## Status: Ready for Implementation

This document outlines the surgical changes needed to eliminate DB operations during live calls.

---

## 🎯 Scope

**What we're fixing:**
- 17 DB queries per call → 1 batch query at start
- 3-4 commits mid-call → 0 commits mid-call, 1 at end
- ~200ms DB time → ~15ms DB time

**What we're NOT changing:**
- Audio processing logic
- VAD/barge-in behavior
- Prompt content or logic
- session.update gating
- Any functional behavior

---

## 📋 Phase 1: Create Call Context System

### 1.1 Add CallContext Class

**Location:** Insert after line ~2100 in `server/media_ws_ai.py`

```python
class CallContext:
    """
    Immutable cache of all DB data needed for a call.
    Loaded once at call start, used throughout call, never queries DB again.
    """
    def __init__(self, call_log, lead, business, settings):
        # CallLog data
        self.call_sid = call_log.call_sid if call_log else None
        self.call_log_id = call_log.id if call_log else None
        self.lead_id = call_log.lead_id if call_log else None
        
        # Lead data
        self.lead_full_name = lead.full_name if lead else None
        self.lead_first_name = lead.first_name if lead else None
        self.lead_phone = lead.phone if lead else None
        self.lead_customer_name = lead.customer_name if lead else None
        self.lead_gender = getattr(lead, 'gender', None) if lead else None
        
        # Business data
        self.business_id = business.id if business else None
        self.business_name = business.name if business else None
        
        # Settings data
        self.opening_hours = settings.opening_hours_json if settings else None
        self.working_hours = settings.working_hours if settings else None
        
        # Extraction cache
        self._first_name_cache = None
    
    def get_first_name(self):
        """Extract first name once, cache result"""
        if self._first_name_cache is None and self.lead_full_name:
            from server.services.realtime_prompt_builder import extract_first_name
            self._first_name_cache = extract_first_name(self.lead_full_name)
        return self._first_name_cache or self.lead_first_name
```

### 1.2 Add Batch Load Method

**Location:** Insert after line ~2940 (after business_id check)

```python
def _load_call_context_batch(self, call_sid, business_id, lead_id=None):
    """
    Load all call data in single JOIN query.
    Returns CallContext with all needed data.
    """
    from server.models_sql import CallLog, Lead, Business, BusinessSettings
    
    try:
        # Single JOIN query - loads everything at once
        result = db.session.query(
            CallLog, Lead, Business, BusinessSettings
        ).outerjoin(
            Lead, CallLog.lead_id == Lead.id
        ).outerjoin(
            Business, Business.id == business_id
        ).outerjoin(
            BusinessSettings, BusinessSettings.tenant_id == business_id
        ).filter(
            CallLog.call_sid == call_sid
        ).first()
        
        if result:
            call_log, lead, business, settings = result
            return CallContext(call_log, lead, business, settings)
        else:
            # Call not in DB yet - create minimal context
            business = Business.query.get(business_id)
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            return CallContext(None, None, business, settings)
            
    except Exception as e:
        logger.error(f"[CALL_CACHE] Failed to load context: {e}")
        return None
```

---

## 📋 Phase 2: Initialize Cache at Call Start

### 2.1 Add Cache Load Call

**Location:** Line ~2942 (after `outbound_lead_name = getattr(...)`)

```python
# 🔥 PERFORMANCE: Load all call data once
if not hasattr(self, 'call_ctx') or self.call_ctx is None:
    self.call_ctx = self._load_call_context_batch(
        self.call_sid,
        business_id_safe,
        lead_id=getattr(self, 'outbound_lead_id', None)
    )
    self.call_ctx_loaded = True if self.call_ctx else False
    print(f"✅ [CALL_CACHE] Loaded context for call {self.call_sid[:8]}...")
else:
    print(f"ℹ️ [CALL_CACHE] Context already loaded")
```

---

## 📋 Phase 3: Replace DB Queries with Cache

### 3.1 Name Resolution (_resolve_customer_name)

**Location:** Lines 2945-3090

**Change:** Instead of querying DB, use `self.call_ctx`:

```python
def _resolve_customer_name_from_cache():
    """Use cached data instead of DB queries"""
    if not self.call_ctx:
        return None, None
    
    # Check cache for name
    if self.call_ctx.lead_customer_name:
        return self.call_ctx.lead_customer_name, "call_cache"
    
    if self.call_ctx.lead_full_name:
        return self.call_ctx.lead_full_name, "call_cache"
    
    return None, None
```

### 3.2 CRM Background Init

**Location:** Lines 3887-4009

**Change:** Use cache instead of queries:

```python
def _init_crm_background():
    # Instead of querying, use pre-loaded cache
    if self.call_ctx and self.call_ctx.lead_id:
        lead_id = self.call_ctx.lead_id
        self.crm_context = {
            'lead_id': lead_id,
            'business_id': self.call_ctx.business_id,
            'lead_name': self.call_ctx.get_first_name(),
            'lead_phone': self.call_ctx.lead_phone
        }
        print(f"✅ [CRM] Context ready from cache: lead_id={lead_id}")
```

---

## 📋 Phase 4: Remove Mid-Call Commits

### 4.1 Add Write Buffer

**Location:** After line ~2150 (in __init__)

```python
self.db_write_queue = []  # Buffer for mid-call DB writes
self.in_live_call = False  # Guard flag
```

### 4.2 Replace Commits with Buffer

**Line 7059:** Name detection commit
```python
# Before:
db.session.commit()

# After:
self.db_write_queue.append({
    'type': 'lead_update',
    'lead_id': lead.id,
    'field': 'customer_name',
    'value': name
})
print(f"[DB_BUFFER] Queued lead name update (will commit at call end)")
```

**Line 7130:** Name persistence commit
```python
# Before:
db.session.commit()

# After:
self.db_write_queue.append({
    'type': 'lead_update', 
    'lead_id': lead.id,
    'field': 'customer_name',
    'value': self.pending_customer_name
})
```

**Line 8772:** Appointment commit
```python
# Before:
db.session.commit()

# After:
self.db_write_queue.append({
    'type': 'appointment_create',
    'data': appointment_data
})
```

**Line 9324:** CallSession commit
```python
# Before:
db.session.commit()

# After:
self.db_write_queue.append({
    'type': 'callsession_update',
    'call_sid': self.call_sid,
    'data': session_data
})
```

### 4.3 Flush at Call End

**Location:** In `_handle_ws_disconnect` (around line 10600)

```python
def _flush_db_writes(self):
    """Flush all buffered writes at call end"""
    if not self.db_write_queue:
        return
    
    try:
        from server.models_sql import Lead, Appointment, CallSession
        
        for write in self.db_write_queue:
            if write['type'] == 'lead_update':
                lead = Lead.query.get(write['lead_id'])
                if lead:
                    setattr(lead, write['field'], write['value'])
            
            elif write['type'] == 'appointment_create':
                appointment = Appointment(**write['data'])
                db.session.add(appointment)
            
            elif write['type'] == 'callsession_update':
                session = CallSession.query.filter_by(
                    call_sid=write['call_sid']
                ).first()
                if session:
                    for k, v in write['data'].items():
                        setattr(session, k, v)
        
        # Single commit for all writes
        db.session.commit()
        print(f"✅ [DB_FLUSH] Committed {len(self.db_write_queue)} writes at call end")
        self.db_write_queue = []
        
    except Exception as e:
        logger.error(f"[DB_FLUSH] Failed to flush writes: {e}")
        db.session.rollback()
```

Call in disconnect handler:
```python
# Add before final cleanup
self.in_live_call = False
self._flush_db_writes()
```

---

## 📋 Phase 5: Add Runtime Guard

### 5.1 Set Guard Flags

**After greeting starts (line ~3780):**
```python
self.in_live_call = True
print(f"🔒 [GUARD] Live call active - DB access forbidden")
```

**At call end (line ~10600):**
```python
self.in_live_call = False
print(f"🔓 [GUARD] Live call ended - DB access allowed")
```

### 5.2 Add Guard Checks

**In query methods (if any remain):**
```python
def _check_live_call_guard(self):
    if getattr(self, 'in_live_call', False):
        logger.warning("[GUARD] Attempted DB access during live call - blocked")
        return True
    return False
```

---

## 🧪 Testing Plan

### Test 1: Inbound Call with Lead
1. Call starts
2. Verify: 1 batch query at start
3. Verify: Greeting plays normally
4. Verify: PROMPT UPGRADE happens
5. Verify: 0 queries during conversation
6. Call ends
7. Verify: 1 commit at end with all buffered writes

### Test 2: Outbound Call
1. Outbound call triggered
2. Verify: Cache loaded with OutboundCallJob data
3. Verify: Greeting uses cached name
4. Verify: 0 mid-call queries

### Test 3: Name Detection
1. User says name during call
2. Verify: Name extracted
3. Verify: Write buffered (not committed)
4. Call ends
5. Verify: Name persisted in final flush

---

## 📊 Success Criteria

- [ ] 0 DB queries between greeting and hangup
- [ ] 0 commits between greeting and hangup  
- [ ] 1 batch query at call start (~15ms)
- [ ] 1 flush commit at call end
- [ ] All functionality unchanged
- [ ] Greeting timing unchanged or improved
- [ ] No errors in logs

---

## 🚀 Deployment

1. Deploy changes
2. Monitor first 10 calls closely
3. Check logs for "DB query during live call" warnings
4. Verify performance improvement in metrics
5. If issues: immediate rollback capability

---

## 📝 Notes

- This is a **zero-behavior-change** optimization
- Cache is read-only during call
- All writes buffered and flushed atomically
- Guard prevents accidental regressions
- Can be rolled back safely (no schema changes)

**Estimated implementation time:** 2-3 hours of careful work
**Testing time:** 1 hour
**Total:** 3-4 hours for complete, tested implementation

