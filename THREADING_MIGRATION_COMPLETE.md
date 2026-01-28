# Thread-to-RQ Worker Migration Complete

## Overview

This document explains the complete refactoring of background tasks from threading to RQ (Redis Queue) workers, eliminating all non-realtime threads and preventing duplicate execution issues.

## Problem Statement

The original architecture had the following issues:
1. **Duplicate Execution**: Multiple API instances spawning threads caused duplicate processing
2. **Ghost State**: Daemon threads continued running after restarts
3. **No Visibility**: Thread execution couldn't be monitored or retried
4. **Progress Bar Issues**: Multiple threads updating state caused UI inconsistencies
5. **Resource Leaks**: Thread pools without proper cleanup

## Solution: Clean Architecture

### Golden Rule
```
API → Enqueue Only
Worker → Process Only  
Scheduler → Schedule Only
Realtime → Threads OK (for WebSocket/streaming)
```

## Architecture Components

### 1. SERVICE_ROLE Environment Variable

Controls what each service does:

| SERVICE_ROLE | Purpose | Allowed Operations |
|--------------|---------|-------------------|
| `api` | REST API endpoints | Auth, CRUD, enqueue jobs, return responses |
| `calls` | WebSocket + Twilio | Same as api + realtime threads for media |
| `worker` | Background job processing | Process RQ jobs, retries, long-running tasks |
| `scheduler` | Periodic job scheduling | Enqueue periodic jobs with Redis locks |
| `all` | Development only | API + Worker (not recommended for production) |

### 2. Docker Compose Services

```yaml
services:
  prosaas-api:
    environment:
      SERVICE_ROLE: api
      ENABLE_SCHEDULERS: "false"
  
  prosaas-calls:
    environment:
      SERVICE_ROLE: calls
      ENABLE_SCHEDULERS: "false"
  
  worker:
    environment:
      SERVICE_ROLE: worker
    command: ["python", "-m", "server.worker"]
  
  scheduler:
    environment:
      SERVICE_ROLE: scheduler
    command: ["python", "-m", "server.scheduler.run_scheduler"]
```

### 3. Job Types

#### Enqueued Jobs (On-Demand)
These jobs are enqueued when events occur:

- **webhook_process_job** - Process WhatsApp webhook messages
- **push_send_job** - Send push notifications to user devices
- **recording_job** - Transcribe call recordings
- **broadcast_job** - Send WhatsApp broadcasts
- **gmail_sync_job** - Sync Gmail receipts

#### Scheduled Jobs (Periodic)
These jobs are enqueued by the scheduler service:

- **reminders_tick_job** - Check reminders every 1 minute
- **whatsapp_sessions_cleanup_job** - Process stale sessions every 5 minutes
- **reminders_cleanup_job** - Clean old reminder logs daily at 3 AM
- **cleanup_old_recordings_job** - Clean old recordings daily at 4 AM

### 4. Scheduler Service

The scheduler service (`server/scheduler/run_scheduler.py`):

1. **Runs independently** - Separate process from API/Worker
2. **Redis Lock** - Prevents duplicate execution across multiple instances
3. **Enqueues jobs** - Only adds jobs to RQ queues, doesn't execute them
4. **Handles timing** - Determines when periodic jobs should run
5. **Graceful shutdown** - Handles SIGTERM/SIGINT properly

Example cycle:
```python
# Every 60 seconds:
1. Acquire Redis lock "scheduler:global_lock" (TTL 90s)
2. If lock acquired:
   - Enqueue reminders_tick_job
   - If minute % 5 == 0: Enqueue whatsapp_sessions_cleanup_job
   - If hour == 3 and minute == 0: Enqueue reminders_cleanup_job
   - If hour == 4 and minute == 0: Enqueue cleanup_old_recordings_job
3. Release lock
4. Sleep until next cycle
```

## Changes Made

### Files Modified

#### 1. `server/routes_webhook.py`
**Before:**
```python
Thread(target=_process_whatsapp_with_cleanup, args=(tenant_id, messages), daemon=True).start()
```

**After:**
```python
from server.jobs.webhook_process_job import webhook_process_job
queue.enqueue(webhook_process_job, tenant_id=tenant_id, messages=messages, business_id=business_id)
```

#### 2. `server/services/notifications/dispatcher.py`
**Before:**
```python
thread = threading.Thread(target=_dispatch_push_sync, args=(user_id, business_id, payload), daemon=True)
thread.start()
```

**After:**
```python
from server.jobs.push_send_job import push_send_job
queue.enqueue(push_send_job, user_id=user_id, business_id=business_id, title=payload.title, body=payload.body)
```

#### 3. `server/services/notifications/reminder_scheduler.py`
**Before:**
```python
_scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True, name="ReminderNotificationScheduler")
_scheduler_thread.start()
```

**After:**
```python
def start_reminder_scheduler(app):
    """DEPRECATED: Reminders now handled by scheduler service + RQ jobs"""
    log.warning("⚠️ Reminders are now handled by scheduler service")
    return
```

#### 4. `server/services/whatsapp_session_service.py`
**Before:**
```python
processor_thread = threading.Thread(target=_session_processor_loop, daemon=True, name="WhatsAppSessionProcessor")
processor_thread.start()
```

**After:**
```python
def start_session_processor():
    """DEPRECATED: Session processing now handled by scheduler service + RQ jobs"""
    logger.warning("⚠️ Session processing is now handled by scheduler service")
    return False
```

#### 5. `server/app_factory.py`
- Updated SERVICE_ROLE validation to include 'scheduler' and 'calls'
- Removed all thread starting logic
- Added deprecation warnings for ENABLE_SCHEDULERS
- Enforced that api/calls/scheduler modes never start background threads

#### 6. `docker-compose.yml`
- Added new `scheduler` service
- Set `SERVICE_ROLE=api` for prosaas-api
- Set `SERVICE_ROLE=calls` for prosaas-calls
- Set `SERVICE_ROLE=worker` for worker
- Set `ENABLE_SCHEDULERS=false` for all services except scheduler

### Files Created

#### 1. `server/jobs/webhook_process_job.py`
Processes WhatsApp webhook messages asynchronously.

**Key Features:**
- Idempotent (messages have unique IDs)
- Full AI response generation
- Lead/customer management
- Session tracking
- N8N integration

#### 2. `server/jobs/push_send_job.py`
Sends push notifications to user devices.

**Key Features:**
- Idempotent (client-side deduplication)
- Batch processing for multiple subscriptions
- Auto-deactivates invalid subscriptions
- Retry support via RQ

#### 3. `server/jobs/reminders_tick_job.py`
Checks for upcoming reminders and sends notifications.

**Key Features:**
- DB-backed deduplication (ReminderPushLog table)
- Sends notifications at 30min and 15min before due time
- Includes cleanup job for old log entries

#### 4. `server/jobs/whatsapp_sessions_cleanup_job.py`
Processes stale WhatsApp sessions and generates summaries.

**Key Features:**
- Idempotent (sessions marked as processed)
- AI-generated conversation summaries
- Batch processing (50 sessions at a time)
- Handles missing data gracefully

#### 5. `server/scheduler/run_scheduler.py`
Main scheduler service with Redis lock protection.

**Key Features:**
- Redis lock prevents duplicate execution
- Configurable cycle interval (default 60s)
- Graceful shutdown on SIGTERM/SIGINT
- Automatic job enqueuing based on time
- Health check support

## Remaining Realtime Threads

These threads are **KEPT** because they handle real-time streaming:

### 1. `server/media_ws_ai.py`
**Purpose:** Twilio WebSocket audio streaming
**Threads:**
- Session reaper loop
- TX audio thread
- Audio watchdog thread
- Recording threads
- Realtime API threads
- Hangup threads

**Justification:** These threads handle real-time audio streaming from Twilio. They MUST run in the same process as the WebSocket connection because:
- Audio packets arrive continuously via WebSocket
- Sub-100ms latency required for natural conversation
- Can't be queued to Redis without breaking real-time flow

### 2. `server/services/gcp_stt_stream.py`
**Purpose:** Google Cloud Speech-to-Text streaming
**Threads:**
- STT stream worker thread

**Justification:** Streaming audio to Google STT requires persistent connection with continuous data flow.

### 3. `server/services/gcp_stt_stream_optimized.py`
**Purpose:** Optimized Google STT streaming
**Threads:**
- Stream worker thread

**Justification:** Same as above - real-time speech recognition.

### 4. `server/worker.py`
**Purpose:** RQ worker heartbeat
**Threads:**
- Heartbeat logging thread

**Justification:** Internal RQ worker thread for monitoring. Not user-facing.

### 5. `server/utils/safe_thread.py`
**Purpose:** Thread wrapper utilities
**Status:** Only used by realtime components above

## Benefits

### 1. No Duplicate Execution
- Single worker processes each job
- Scheduler uses Redis lock
- Idempotent job design

### 2. Visibility & Observability
```bash
# View queue status
redis-cli LLEN rq:queue:default

# View running jobs
rq info --url redis://localhost:6379

# View failed jobs
rq info --url redis://localhost:6379 --failed
```

### 3. Retry Support
```python
# Jobs automatically retry on failure
queue.enqueue(job_func, retry=Retry(max=3, interval=[10, 30, 60]))
```

### 4. Clean Separation
- API: Fast response times (no blocking)
- Worker: Heavy processing isolated
- Scheduler: Timing logic centralized
- Realtime: Only where absolutely necessary

### 5. Scalability
```yaml
# Scale workers independently
docker-compose up --scale worker=5
```

### 6. Development Simplicity
```yaml
# Development: Use all-in-one mode
services:
  backend:
    environment:
      SERVICE_ROLE: all
```

## Testing

### 1. Verify Services Are Running
```bash
docker-compose ps

# Expected:
# - prosaas-api (healthy)
# - prosaas-calls (healthy)
# - worker (healthy)
# - scheduler (healthy)
# - redis (healthy)
```

### 2. Check Logs
```bash
# Scheduler logs
docker-compose logs -f scheduler

# Worker logs
docker-compose logs -f worker

# API logs
docker-compose logs -f prosaas-api
```

### 3. Verify Job Enqueuing
```bash
# Redis CLI
redis-cli

# Check queues
LLEN rq:queue:default
LLEN rq:queue:low
LLEN rq:queue:maintenance

# Check scheduler lock
GET scheduler:global_lock
```

### 4. Test Webhook Processing
```bash
# Send test webhook
curl -X POST http://localhost/webhook/whatsapp/incoming \
  -H "X-Internal-Secret: YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"tenantId": "1", "payload": {"messages": [...]}}'

# Check that job was enqueued (not processed inline)
redis-cli LLEN rq:queue:default
```

### 5. Verify No Thread Spawning in API
```bash
# API logs should NOT show:
# - "Thread started"
# - "Spawning background thread"
# - "Background processor thread"

# API logs SHOULD show:
# - "Enqueued webhook_process_job"
# - "Enqueued push_send_job"
```

## Deployment

### Production Deployment

1. **Update environment variables:**
```bash
# .env
SERVICE_ROLE=api  # For API service
ENABLE_SCHEDULERS=false  # For all services
```

2. **Deploy services:**
```bash
docker-compose up -d prosaas-api prosaas-calls worker scheduler
```

3. **Verify health:**
```bash
# All services should be healthy
docker-compose ps
```

4. **Monitor logs:**
```bash
# Check for errors
docker-compose logs --tail=100 -f
```

### Rolling Updates

To update without downtime:

1. **Update worker first:**
```bash
docker-compose up -d worker
```

2. **Update scheduler:**
```bash
docker-compose up -d scheduler
```

3. **Update API:**
```bash
docker-compose up -d prosaas-api prosaas-calls
```

## Troubleshooting

### Issue: Jobs Not Processing
**Symptoms:** Jobs enqueued but not executed
**Solution:**
```bash
# Check worker is running
docker-compose ps worker

# Check worker logs
docker-compose logs worker

# Check Redis connection
redis-cli PING
```

### Issue: Duplicate Job Execution
**Symptoms:** Same job runs multiple times
**Solution:**
```bash
# Check scheduler lock
redis-cli GET scheduler:global_lock

# Verify only one scheduler instance
docker-compose ps scheduler

# Check job IDs (should be unique)
redis-cli LRANGE rq:queue:default 0 -1
```

### Issue: Jobs Failing
**Symptoms:** Jobs in failed queue
**Solution:**
```bash
# View failed jobs
rq info --url redis://localhost:6379 --failed

# Retry failed jobs
rq requeue --all --url redis://localhost:6379

# Check job logs
docker-compose logs worker | grep ERROR
```

### Issue: Scheduler Not Running
**Symptoms:** Periodic jobs not enqueued
**Solution:**
```bash
# Check scheduler logs
docker-compose logs scheduler

# Verify scheduler service is up
docker-compose ps scheduler

# Check Redis connectivity
docker-compose exec scheduler python -c "import redis; redis.from_url('redis://redis:6379/0').ping()"
```

## Migration Checklist

For existing deployments, follow this checklist:

- [ ] ✅ Backup database
- [ ] ✅ Update docker-compose.yml with scheduler service
- [ ] ✅ Set SERVICE_ROLE environment variables
- [ ] ✅ Set ENABLE_SCHEDULERS=false for all services
- [ ] ✅ Deploy scheduler service
- [ ] ✅ Verify scheduler logs show job enqueuing
- [ ] ✅ Verify worker logs show job processing
- [ ] ✅ Test webhook processing (should be async)
- [ ] ✅ Test push notifications (should be async)
- [ ] ✅ Verify no threads in API logs
- [ ] ✅ Monitor for duplicate execution
- [ ] ✅ Verify progress bars work correctly
- [ ] ✅ Check Redis queue sizes

## Summary

This refactoring completely eliminates non-realtime threading and establishes a clean, scalable architecture:

- **Before:** API spawned threads → duplicate execution, ghost state, no visibility
- **After:** API enqueues jobs → single worker execution, full visibility, retry support

All background tasks now flow through RQ, with a dedicated scheduler service handling periodic job enqueuing. This eliminates the "duplicate execution" and "progress bar without queue" issues mentioned in the problem statement.

The architecture is now production-ready with proper separation of concerns:
- API = Enqueue only
- Worker = Process only
- Scheduler = Schedule only
- Realtime = Threads only where absolutely necessary
