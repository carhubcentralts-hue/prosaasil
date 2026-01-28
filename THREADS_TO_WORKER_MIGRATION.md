# Threading to RQ Worker Migration Map

**Goal:** Complete migration of all non-realtime threading to RQ Worker system.

---

## Thread Usage Inventory

### ✅ REALTIME_KEEP - DO NOT TOUCH

These threads handle real-time audio/WebSocket operations and MUST remain as threads:

| File | Line | Thread Name | Purpose | Category |
|------|------|------------|---------|----------|
| `server/media_ws_ai.py` | 568 | `reaper_loop` | Session timeout watchdog | REALTIME_WATCHDOG |
| `server/media_ws_ai.py` | 700 | `_tx_loop` | TX audio streaming to Twilio | REALTIME_TX_LOOP |
| `server/media_ws_ai.py` | 710 | `watchdog_thread` | Audio quality monitoring (VAD, echo) | REALTIME_WATCHDOG |
| `server/media_ws_ai.py` | 660 | `realtime_thread` | OpenAI/Gemini streaming API | REALTIME_API_LOOP |
| `server/media_ws_ai.py` | 670 | `realtime_out_thread` | Realtime audio output | REALTIME_AUDIO_OUT |
| `server/services/gcp_stt_stream.py` | 98 | `_t` | Google Cloud STT streaming | REALTIME_STT |
| `server/services/gcp_stt_stream_optimized.py` | 85 | `_stream_worker` | Optimized STT (30ms batches) | REALTIME_STT |
| `server/routes_twilio.py` | 442-550 | Multiple webhook handlers | Twilio call state webhooks | REALTIME_WEBHOOKS |

**Total REALTIME threads to keep:** 13+

---

## ❌ MOVE_TO_WORKER - MUST MIGRATE

All the following threads perform background work and MUST be converted to RQ jobs:

### A) App Factory Threads (`server/app_factory.py`)

| Line | Thread Name | Purpose | Operations | RQ Job Name | Priority |
|------|------------|---------|-----------|-------------|----------|
| 1323 | `init_thread` | Background migrations & DB init | DB writes (migrations) | `worker_startup_migrations` | HIGH |
| 1488 | `warmup_thread` | AI agent warmup/preload | DB reads (business queries) | `warmup_agents_job` | MEDIUM |
| 1526 | `cleanup_thread` (RecordingCleanup) | 7-day recording retention | DB deletes (old recordings) | `cleanup_old_recordings_job` | HIGH |
| 1546 | `recording_thread` (RecordingWorker) | Recording transcription | DB writes (transcription, leads) | `process_recording_job` | HIGH |

**Replacement Plan:**
- `init_thread` → Move to Docker entrypoint or worker startup
- `warmup_thread` → Lazy initialization or optional worker job
- `cleanup_thread` → Scheduled cron job (daily at 3 AM)
- `recording_thread` → Already has RQ infrastructure in `server/tasks_recording.py`

---

### B) Routes Threads

#### `server/routes_twilio.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 383 | `send_thread` | WhatsApp message sending | Network I/O (WhatsApp API) | `send_whatsapp_message_job` |
| Various | Background lead/prompt creation | DB writes (lead creation, prompt prebuild) | `create_lead_job`, `prebuild_prompt_job` | `create_lead_job`, `prebuild_prompt_job` |

#### `server/routes_whatsapp.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 150+ | `send_thread` | Background WhatsApp send | Network I/O | `send_whatsapp_message_job` |
| 57-99 | `_send_whatsapp_message_background` | WhatsApp send with retry | Network I/O, DB writes | `send_whatsapp_with_retry_job` |

#### `server/routes_webhook.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 79 | WhatsApp processor thread | WhatsApp message processing | DB writes (lead, conversation) | `process_whatsapp_webhook_job` |
| 100+ | `_async_conversation_analysis` | Conversation NLP & lead updates | DB writes (lead fields) | `analyze_conversation_job` |

**Note:** Routes_webhook already has semaphore limiting (`MAX_CONCURRENT_WA_THREADS=10`). Replace with RQ queue.

#### `server/routes_business_management.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 340 | `warmup_new_business` | Business settings preload | DB reads | `warmup_business_job` |

#### `server/media_ws_ai.py` (Background DB Writes)

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 730+ | `create_in_background` | Lead creation after call | DB writes (lead) | `create_lead_from_call_job` |
| 730+ | `save_in_background` | Call log finalization | DB writes (call_log) | `finalize_call_log_job` |
| 730+ | `finalize_in_background` | Call session cleanup | DB writes (session state) | `finalize_call_session_job` |
| 685 | `_start_call_recording` | Recording initiation | Network I/O (Twilio API) | Keep as async (already fast) |
| 695 | `_deferred_call_setup` | Delayed call initialization | DB writes (call_log, lead) | `deferred_call_setup_job` |

---

### C) Services Threads

#### `server/services/n8n_integration.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 50 | `_send_to_n8n` thread | Webhook relay to n8n | Network I/O | `send_webhook_to_n8n_job` |

#### `server/services/generic_webhook_service.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 280 | `send_with_retry` thread | Webhook retry with backoff | Network I/O | `send_webhook_with_retry_job` |

#### `server/services/whatsapp_session_service.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 200 | `processor_thread` | 15-min auto-summary | DB writes (session summaries) | `auto_summary_whatsapp_session_job` |

#### `server/services/notifications/dispatcher.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 57 | Push dispatch thread | Push notification sending | Network I/O | `send_push_notification_job` |

#### `server/services/notifications/reminder_scheduler.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 140 | `_scheduler_thread` | Reminder push scheduler | DB reads + Network I/O | `schedule_reminders_job` |

#### `server/services/lazy_services.py`

| Line | Function | Purpose | Operations | RQ Job Name |
|------|----------|---------|-----------|-------------|
| 30 | `warmup_thread` | Service warmup | DB reads | `warmup_lazy_services_job` |

#### `server/worker.py`

| Line | Function | Purpose | Operations | Action |
|------|----------|---------|-----------|--------|
| 117 | `heartbeat_thread` | Worker heartbeat logging | DB writes | **KEEP** - already integrated in worker loop |

---

## Migration Strategy

### Phase 1: Infrastructure Setup

**Create unified job enqueue service:**
```python
# server/services/jobs.py
def enqueue_job(
    queue_name: str,
    func: callable,
    *args,
    business_id: int = None,
    run_id: int = None,
    job_id: str = None,
    ttl: int = 600,
    timeout: int = 300,
    retry: int = 3,
    **kwargs
) -> Job:
    """Unified job enqueue with business isolation"""
    pass

def enqueue_unique(
    queue_name: str,
    func: callable,
    dedup_key: str,
    *args,
    **kwargs
) -> Job:
    """Enqueue with deduplication"""
    pass
```

**Add SERVICE_ROLE guard:**
```python
# server/app_factory.py
SERVICE_ROLE = os.getenv('SERVICE_ROLE', 'api')  # api|worker

if SERVICE_ROLE == 'worker':
    # Worker: no HTTP server, only job processing
    pass
elif SERVICE_ROLE == 'api':
    # API: expose endpoints, enqueue only
    pass
```

### Phase 2: Job Implementation

For each thread in MOVE_TO_WORKER table:
1. Create RQ job in `server/jobs/<job_name>.py`
2. Add business_id parameter and validation
3. Add logging (start/success/fail)
4. Replace thread creation with `enqueue_job()`
5. Test isolation and idempotency

### Phase 3: Outbound Queue Complete Fix

Current issues in `server/routes_outbound.py`:
- Uses `from threading import Thread` (line 16)
- No Thread().start() calls found (good!)
- Already uses RQ for job processing

**Verify:**
- [ ] No direct Thread creation in outbound
- [ ] All job processing goes through RQ
- [ ] Idempotent job claiming with DB locks
- [ ] Cancel support with worker check

### Phase 4: Cleanup

- [ ] Remove unused `from threading import Thread` imports
- [ ] Remove thread helper functions
- [ ] Update documentation
- [ ] Add thread count to health endpoint

---

## Acceptance Tests

### Test 1: No Threading Outside Realtime
```bash
# Should only find realtime files
grep -r "threading.Thread(" server/ --include="*.py" | grep -v media_ws_ai | grep -v gcp_stt
```

### Test 2: Outbound No Duplicates
```python
# Start same outbound run twice - should return 409
# Cancel run - should stop immediately
# Restart server - no stuck "running" runs
```

### Test 3: Business Isolation
```python
# Job from business_1 should never access business_2 data
# All jobs must validate business_id on every DB query
```

### Test 4: Progress Bar Accuracy
```python
# Progress bar only shows when run is actually active
# No "ghost" progress bars after restart
```

---

## Security Checklist

- [ ] All jobs enforce business_id filtering
- [ ] No cross-tenant data access possible
- [ ] Sensitive data not logged (passwords, tokens)
- [ ] Job retry limits prevent infinite loops
- [ ] Timeouts prevent hanging jobs

---

## Performance Metrics

**Before Migration:**
- Daemon threads: 39+
- Thread pool: Unmanaged
- Memory: Growing with each background task

**After Migration:**
- Daemon threads: ~13 (realtime only)
- Thread pool: Centralized in RQ worker
- Memory: Bounded by worker count
- Monitoring: Redis queue depth, job latency

---

## Rollback Plan

If issues arise:
1. Set `ENABLE_SCHEDULERS=false` to disable worker jobs
2. Restore threading for critical paths (recording, cleanup)
3. Deploy hotfix with minimal threading for stability
4. Investigate root cause

---

**Last Updated:** 2026-01-28
**Status:** IN PROGRESS - Phase 1 Discovery Complete
