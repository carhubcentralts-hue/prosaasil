# 🚨 CRITICAL: Recording Queue Architecture Issue

## The Problem

`RECORDING_QUEUE = queue.Queue()` is an **in-memory Python queue**.

### Why This DOESN'T Work

```python
# In server/tasks_recording.py
RECORDING_QUEUE = queue.Queue()  # ❌ IN-MEMORY - local to process!
```

**Result:**
- **prosaas-api** container: Enqueues job to ITS memory
- **worker** container: Has ITS OWN separate memory  
- **They NEVER communicate** = Jobs enqueued but never consumed = **INFINITE LOOP**

---

## The Solution: Convert to RQ (Redis Queue)

### Why RQ?
- ✅ Redis-backed - shared across containers
- ✅ Already configured (`recordings` queue exists)
- ✅ Worker already processes RQ jobs
- ✅ Proven, battle-tested

---

## Implementation Plan

### Step 1: Create RQ Job Function

Create `/home/runner/work/prosaasil/prosaasil/server/jobs/recording_job.py`:

```python
"""
Recording download and transcription job for RQ worker.
"""
import logging
from server.app_factory import get_process_app
from server.db import db

logger = logging.getLogger(__name__)

def process_recording_job(call_sid, recording_url, business_id, from_number="", to_number="", job_type="download_only", recording_sid=None):
    """
    RQ job function for processing recordings.
    
    Args:
        call_sid: Twilio call SID
        recording_url: URL to download recording from
        business_id: Business ID for slot management
        from_number: Caller phone number
        to_number: Callee phone number
        job_type: 'download_only' or 'full' (with transcription)
        recording_sid: Twilio recording SID (optional)
    
    Returns:
        dict: Job result with success status
    """
    app = get_process_app()
    
    with app.app_context():
        logger.info(f"🎯 [RQ_RECORDING] Processing job: call_sid={call_sid}, type={job_type}")
        
        try:
            if job_type == "download_only":
                # Import here to avoid circular imports
                from server.tasks_recording import download_recording_only
                
                # Acquire slot for business
                from server.recording_semaphore import try_acquire_slot, release_slot
                
                if business_id:
                    acquired, status = try_acquire_slot(business_id, call_sid)
                    if not acquired:
                        logger.warning(f"⚠️ [RQ_RECORDING] No slot available for business {business_id}, re-enqueueing")
                        # Re-enqueue with delay
                        from rq import get_current_job
                        job = get_current_job()
                        if job:
                            # Requeue via RQ retry mechanism
                            raise Exception("No slot available - will retry")
                        return {"success": False, "reason": "no_slot"}
                
                try:
                    # Download recording
                    success = download_recording_only(call_sid, recording_url)
                    
                    if success:
                        logger.info(f"✅ [RQ_RECORDING] Downloaded successfully: {call_sid}")
                        return {"success": True, "call_sid": call_sid}
                    else:
                        logger.error(f"❌ [RQ_RECORDING] Download failed: {call_sid}")
                        return {"success": False, "reason": "download_failed"}
                finally:
                    # Always release slot
                    if business_id:
                        release_slot(business_id, call_sid)
                        logger.info(f"🔓 [RQ_RECORDING] Slot released for business {business_id}")
            
            else:
                # Full processing (download + transcription)
                from server.tasks_recording import process_recording_async
                
                form_data = {
                    "CallSid": call_sid,
                    "RecordingUrl": recording_url,
                    "From": from_number,
                    "To": to_number,
                }
                
                success = process_recording_async(form_data)
                
                if success:
                    logger.info(f"✅ [RQ_RECORDING] Processed successfully: {call_sid}")
                    return {"success": True, "call_sid": call_sid}
                else:
                    logger.error(f"❌ [RQ_RECORDING] Processing failed: {call_sid}")
                    return {"success": False, "reason": "processing_failed"}
        
        except Exception as e:
            logger.error(f"❌ [RQ_RECORDING] Job error: {e}")
            raise
```

### Step 2: Replace RECORDING_QUEUE.put() with RQ enqueue

In `server/tasks_recording.py`, replace `enqueue_recording_download_only()`:

```python
def enqueue_recording_download_only(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0, recording_sid=None):
    """
    Enqueue recording download job to RQ (Redis Queue).
    """
    import os
    import redis
    from rq import Queue
    
    REDIS_URL = os.getenv('REDIS_URL')
    if not REDIS_URL:
        logger.error("❌ REDIS_URL not set - cannot enqueue recording job")
        return False
    
    try:
        redis_conn = redis.from_url(REDIS_URL)
        queue = Queue('recordings', connection=redis_conn)
        
        # Import job function
        from server.jobs.recording_job import process_recording_job
        
        # Enqueue to RQ
        rq_job = queue.enqueue(
            process_recording_job,
            call_sid=call_sid,
            recording_url=recording_url,
            business_id=business_id,
            from_number=from_number,
            to_number=to_number,
            job_type="download_only",
            recording_sid=recording_sid,
            job_timeout='10m',
            job_id=f"recording_{call_sid}_{int(time.time())}"
        )
        
        logger.info(f"✅ [RQ] Recording job enqueued: {call_sid} → RQ job {rq_job.id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to enqueue recording job: {e}")
        return False
```

### Step 3: Remove In-Memory Queue Code

In `server/tasks_recording.py`:
```python
# DELETE THIS:
# RECORDING_QUEUE = queue.Queue()

# DELETE THIS:
# def start_recording_worker(app):
#     ...
```

In `server/worker.py`:
```python
# DELETE THIS:
# from server.tasks_recording import start_recording_worker
# recording_thread = threading.Thread(...)
```

### Step 4: Worker Already Handles 'recordings' Queue

The worker is already configured to listen to the `recordings` queue:

```python
RQ_QUEUES = os.getenv('RQ_QUEUES', 'high,default,low,maintenance,broadcasts,recordings')
```

**No additional changes needed!**

---

## Advantages of RQ Solution

1. ✅ **Works across containers** - Redis is shared
2. ✅ **No threading complexity** - RQ handles concurrency
3. ✅ **Proven and stable** - Battle-tested
4. ✅ **Already configured** - Worker listens to `recordings` queue
5. ✅ **Job persistence** - Jobs survive container restarts
6. ✅ **Retry mechanism** - RQ handles retries automatically
7. ✅ **Monitoring** - Can use RQ dashboard to see queue status

---

## Migration Steps

### Phase 1: Add RQ Job (Non-Breaking)
1. Create `server/jobs/recording_job.py`
2. Test with manual enqueue
3. Verify worker processes it

### Phase 2: Switch Enqueue Logic
1. Update `enqueue_recording_download_only()` to use RQ
2. Update `enqueue_recording_job()` to use RQ
3. Keep old code for backward compat (comment out)

### Phase 3: Remove Old Code
1. Remove `RECORDING_QUEUE = queue.Queue()`
2. Remove `start_recording_worker()` function
3. Remove thread startup from `server/worker.py`
4. Clean up imports

---

## Alternative: Quick Fix (Not Recommended)

If you want a quick fix without RQ migration:

### Create Dedicated Recording Worker Container

**docker-compose.yml:**
```yaml
recording-worker:
  build:
    context: .
    dockerfile: Dockerfile.backend
  command: ["python", "-m", "server.recording_worker"]
  environment:
    DATABASE_URL: ${DATABASE_URL}
    REDIS_URL: redis://redis:6379/0
    RUN_MIGRATIONS: "0"
  depends_on:
    - redis
    - prosaas-api
```

**server/recording_worker.py:**
```python
"""Dedicated recording worker process"""
import os
from server.app_factory import create_app
from server.tasks_recording import start_recording_worker

if __name__ == '__main__':
    app = create_app()
    
    # Start recording worker in app context
    with app.app_context():
        print("✅ Starting dedicated recording worker...")
        start_recording_worker(app)
```

**Problem:** Still uses in-memory queue, so recording-worker must be in same process as API. Not clean.

---

## Recommendation

**Use the RQ solution.** It's the proper architecture and will solve all issues permanently.

The in-memory queue is fundamentally incompatible with multi-container deployments.
