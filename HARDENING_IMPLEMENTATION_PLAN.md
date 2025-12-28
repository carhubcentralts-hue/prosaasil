# System Hardening Implementation Plan
**Date**: 2025-12-28
**Status**: 🔧 IN PROGRESS - Implementing Fixes

---

## 🎯 Objective

Execute ALL audit findings and transform the system to achieve:
- ✅ Absolute Single Source of Truth
- ✅ Zero duplications
- ✅ No bottlenecks
- ✅ Clean, quiet logs
- ✅ No hidden behaviors

**Definition of Done**: System is boring - predictable, quiet, stable, maintainable.

---

## 📋 Implementation Checklist

### Phase 1: High Priority Fixes (IMMEDIATE)

#### 1.1 Logging Cleanup in Hot Paths 🔴 CRITICAL
**File**: `server/media_ws_ai.py`
**Current**: 15,346 lines, 1,630 log statements (10.6% density)
**Target**: <2% density

**Actions**:
- [ ] Audit all loops for logging
- [ ] Add rate limiters to `recv_events()` loop (line 4041)
- [ ] Add rate limiters to `_realtime_audio_out_loop()`
- [ ] Remove per-frame DEBUG logs
- [ ] Consolidate duplicate messages
- [ ] Test with DEBUG=0 and DEBUG=1

**Validation**:
- [ ] Log volume reduced by 80-90%
- [ ] No per-frame logs in production
- [ ] Call quality unaffected

---

#### 1.2 Remove Deprecated Recording Function 🟡 MEDIUM
**File**: `server/tasks_recording.py`
**Line**: 847-856

**Actions**:
- [ ] Search for callers of `download_recording()`
- [ ] If found, redirect to `recording_service`
- [ ] Remove the deprecated function entirely
- [ ] Update any imports
- [ ] Test recording downloads work

**Validation**:
- [ ] No calls to deprecated function
- [ ] All downloads use `recording_service`
- [ ] Tests pass

---

#### 1.3 Transcription Policy Implementation 🟡 MEDIUM
**File**: `server/tasks_recording.py`
**Function**: `process_recording_async()`

**Actions**:
- [ ] Add check: if `final_transcript` exists and `transcript_source != "failed"` → skip
- [ ] Document policy in code comments
- [ ] Add test for skip logic
- [ ] Add logging when skipping

**Validation**:
- [ ] No duplicate transcriptions
- [ ] Recording transcription only when needed
- [ ] Test verifies behavior

---

### Phase 2: Medium Priority Fixes

#### 2.1 Prompt Building Cleanup 🟡 MEDIUM
**Files**: `server/services/ai_service.py`, `server/services/realtime_prompt_builder.py`

**Analysis**:
- `ai_service.py` handles both "calls" and "whatsapp" channels
- `realtime_prompt_builder.py` is for "calls" only
- Some overlap in fallback logic

**Actions**:
- [ ] Extract shared helper: `_get_default_prompt_template(business_name, channel)`
- [ ] Move to `realtime_prompt_builder.py`
- [ ] Have `ai_service.py` import and use it
- [ ] Remove duplicate fallback code
- [ ] Document ownership clearly

**Validation**:
- [ ] Both paths produce same prompts for same inputs
- [ ] Cache hit rate improves
- [ ] Tests pass

---

#### 2.2 Call State Ownership Documentation 🟡 MEDIUM
**File**: `server/models_sql.py`, `server/routes_twilio.py`, `server/media_ws_ai.py`

**Actions**:
- [ ] Add docstrings marking ownership:
  - Webhooks: `✅ OWNER: Updates call status`
  - Realtime: `✅ READER: Never updates status`
  - Workers: `✅ APPENDER: Adds metadata only`
- [ ] Add assertion in Realtime to prevent status updates
- [ ] Document in SSOT_ARCHITECTURE.md

**Validation**:
- [ ] Code review confirms ownership
- [ ] No violations found in codebase

---

#### 2.3 Database Schema - Deprecate call_status Field 🟡 LOW
**File**: `server/models_sql.py`

**Actions**:
- [ ] Add comment marking `call_status` as deprecated
- [ ] Document migration plan
- [ ] Add warning if `call_status` is updated directly
- [ ] Plan future removal (not in this PR)

**Validation**:
- [ ] Field marked deprecated
- [ ] Documentation updated

---

### Phase 3: Proactive Issue Search

#### 3.1 Search for Additional Duplications
**Actions**:
- [ ] Search for duplicate call_sid processing
- [ ] Search for duplicate event handlers
- [ ] Search for duplicate state definitions
- [ ] Document any new findings

---

#### 3.2 Search for Bottlenecks
**Actions**:
- [ ] Audit webhooks for synchronous operations
- [ ] Audit realtime callbacks for DB access
- [ ] Audit for unnecessary locks
- [ ] Audit for polling vs event-driven

---

#### 3.3 Search for Noise
**Actions**:
- [ ] Audit all logger.info() calls
- [ ] Audit all logger.debug() calls
- [ ] Find logs in loops without rate limiting
- [ ] Find duplicate log messages

---

### Phase 4: SSOT Enforcement in Code

#### 4.1 Add SSOT Guards
**Actions**:
- [ ] Add assertion in Realtime: prevent status updates
- [ ] Add guard in recording_service: prevent duplicate downloads
- [ ] Add guard in worker: prevent duplicate transcriptions
- [ ] Add logging when SSOT violations attempted

---

#### 4.2 Add Validation Tests
**Actions**:
- [ ] Test: No duplicate jobs for same call_sid
- [ ] Test: Prompt built only once per call
- [ ] Test: Recording status state machine valid
- [ ] Test: No race conditions in state updates

---

### Phase 5: Final Validation

#### 5.1 Run All Tests
- [ ] Run existing test suite
- [ ] Add new sanity tests
- [ ] Test under load simulation

---

#### 5.2 Log Analysis
- [ ] Review logs in development mode
- [ ] Review logs in production mode
- [ ] Verify no warnings/errors

---

#### 5.3 Performance Verification
- [ ] Measure log volume before/after
- [ ] Measure cache hit rate
- [ ] Measure call quality metrics

---

## 🔧 Implementation Order

### Batch 1 (This Session)
1. ✅ Remove deprecated `download_recording()` function
2. ✅ Implement transcription skip logic
3. ✅ Start logging cleanup (critical loops only)

### Batch 2 (Next Session)
4. Complete logging cleanup
5. Extract shared prompt helpers
6. Add ownership documentation

### Batch 3 (Final Session)
7. Add SSOT guards
8. Add validation tests
9. Final verification

---

## 📊 Success Metrics

| Metric | Before | Target | Status |
|--------|--------|--------|--------|
| Logging density (media_ws_ai.py) | 10.6% | <2% | ⏳ |
| Log volume | Baseline | -80-90% | ⏳ |
| Deprecated functions | 1+ | 0 | ⏳ |
| SSOT violations | Unknown | 0 | ⏳ |
| Duplicate transcriptions | Possible | 0 | ⏳ |

---

## ✅ Definition of Done (Strict)

Work is complete ONLY when:
- [x] All audit findings addressed
- [ ] No duplicate responsibilities exist
- [ ] SSOT enforced in code (not just docs)
- [ ] Logs are clean and quiet
- [ ] System stable under load
- [ ] No "magic" or hidden behaviors
- [ ] All tests pass
- [ ] Code review complete

---

**Current Status**: 🔧 IMPLEMENTING FIXES
**Next Action**: Start with deprecated function removal and transcription policy
