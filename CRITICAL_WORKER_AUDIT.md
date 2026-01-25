# 🔥 CRITICAL: Worker System Audit - Bulk Operations

## Summary

**תוצאה**: לא הכל עובר דרך Worker! יש כפיליות וסכנה בפרודקשן.

## ❌ פעולות שלא עוברות דרך Worker (מסוכן!)

### 1. bulk_delete_leads (routes_leads.py:1468)
```python
# ❌ INLINE PROCESSING - NO WORKER
def bulk_delete_leads():
    leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
    LeadActivity.query.filter(...).delete()  # ❌ ישירות ב-request
    LeadReminder.query.filter(...).delete()   # ❌ ישירות ב-request  
    LeadNote.query.filter(...).delete()       # ❌ ישירות ב-request
    # ... עוד מחיקות ...
    db.session.commit()                        # ❌ הכל בבת אחת
```

**בעיה**: 
- מחיקה של 100+ לידים יכולה לקחת דקות
- ה-request תקוע עד הסיום
- אין heartbeat/progress/cancel
- אם נופל באמצע - אין recovery

**פתרון נדרש**:
```python
def bulk_delete_leads():
    # Create BackgroundJob
    job = BackgroundJob(
        business_id=business_id,
        job_type='delete_leads_bulk',
        status='queued',
        total=len(lead_ids)
    )
    db.session.add(job)
    db.session.commit()
    
    # Enqueue to maintenance queue
    maintenance_queue.enqueue(
        delete_leads_batch_job,
        job.id,
        lead_ids
    )
    
    return jsonify({"job_id": job.id}), 202
```

### 2. create_broadcast (routes_whatsapp.py:2883)
```python
# ❌ THREADING.THREAD - לא RQ Worker!
import threading
from server.services.broadcast_worker import process_broadcast

thread = threading.Thread(
    target=process_broadcast,
    args=(broadcast.id,),
    daemon=True
)
thread.start()  # ❌ כפילות! יש worker נפרד!
```

**בעיה**:
- משתמש ב-threading.Thread ולא ב-RQ
- יש `broadcast_worker.py` נפרד - כפילות!
- אין integration עם המערכת המרכזית
- אין tracking דרך BackgroundJob
- daemon=True = אם השרת נופל, התפוצה הולכת לאיבוד

**פתרון נדרש**:
```python
def create_broadcast():
    # Create BackgroundJob
    job = BackgroundJob(
        business_id=business_id,
        job_type='whatsapp_broadcast',
        status='queued',
        total=len(recipients)
    )
    db.session.add(job)
    db.session.commit()
    
    # Enqueue to broadcasts queue
    broadcasts_queue = Queue('broadcasts', connection=redis_conn)
    broadcasts_queue.enqueue(
        process_broadcast_job,
        job.id,
        broadcast.id
    )
    
    return jsonify({"job_id": job.id, "broadcast_id": broadcast.id}), 202
```

## ✅ פעולות שכן עוברות דרך Worker (נכון!)

### 1. delete_all_receipts ✅
```python
maintenance_queue = Queue('maintenance', connection=redis_conn)
rq_job = maintenance_queue.enqueue(
    delete_receipts_batch_job,
    job.id,
    job_timeout='1h'
)
```
**מצוין**: משתמש ב-BackgroundJob + RQ + maintenance queue

### 2. Gmail Sync ✅
```python
queue.enqueue(
    sync_gmail_receipts_job,
    business_id,
    connection_id
)
```
**מצוין**: משתמש ב-RQ worker

### 3. Recording Downloads ✅
```python
RECORDING_QUEUE.put({
    "call_sid": call_sid,
    "type": "download_only"
})
```
**טוב**: יש in-memory queue עם deduplication + rate limiting

## 🔥 מה צריך לתקן עכשיו

### תיקון 1: bulk_delete_leads → Worker
**קובץ**: `server/jobs/delete_leads_job.py` (חדש)
```python
def delete_leads_batch_job(job_id: int, lead_ids: list):
    """Delete leads in batches with progress tracking"""
    job = BackgroundJob.query.get(job_id)
    job.status = 'running'
    job.total = len(lead_ids)
    
    BATCH_SIZE = 50
    for i in range(0, len(lead_ids), BATCH_SIZE):
        batch = lead_ids[i:i+BATCH_SIZE]
        
        # Delete related records
        LeadActivity.query.filter(LeadActivity.lead_id.in_(batch)).delete()
        LeadReminder.query.filter(LeadReminder.lead_id.in_(batch)).delete()
        # ... etc
        
        # Delete leads
        Lead.query.filter(Lead.id.in_(batch)).delete()
        
        # Update progress
        job.processed += len(batch)
        job.heartbeat_at = datetime.utcnow()
        db.session.commit()
        
        time.sleep(0.1)  # Throttle
```

### תיקון 2: Broadcasts → Worker
**קובץ**: `server/jobs/broadcast_job.py` (חדש)
```python
def process_broadcast_job(job_id: int, broadcast_id: int):
    """Process broadcast with progress tracking"""
    job = BackgroundJob.query.get(job_id)
    broadcast = WhatsAppBroadcast.query.get(broadcast_id)
    
    job.status = 'running'
    
    recipients = WhatsAppBroadcastRecipient.query.filter_by(
        broadcast_id=broadcast_id,
        status='queued'
    ).limit(50).all()
    
    for recipient in recipients:
        # Send message
        send_whatsapp(recipient.phone, broadcast.message_text)
        
        # Update status
        recipient.status = 'sent'
        job.processed += 1
        job.heartbeat_at = datetime.utcnow()
        db.session.commit()
```

### תיקון 3: עדכון Worker לטפל בכל התורים
**קובץ**: `server/worker.py`
```python
# Current
RQ_QUEUES = os.getenv('RQ_QUEUES', 'high,default,low')

# Required
RQ_QUEUES = os.getenv('RQ_QUEUES', 'high,default,low,maintenance,broadcasts,recordings')
```

**קובץ**: `docker-compose.yml`
```yaml
worker:
  environment:
    - RQ_QUEUES=high,default,low,maintenance,broadcasts,recordings
```

## 📋 Checklist תיקון מערכתי

- [ ] צור `server/jobs/delete_leads_job.py`
- [ ] צור `server/jobs/broadcast_job.py`  
- [ ] עדכן `server/routes_leads.py:bulk_delete_leads()` להשתמש ב-job
- [ ] עדכן `server/routes_whatsapp.py:create_broadcast()` להשתמש ב-job
- [ ] מחק `server/services/broadcast_worker.py` (כפילות)
- [ ] עדכן `server/worker.py` לייבא את כל הjobs
- [ ] עדכן `server/jobs/__init__.py` לייצא את כל הjobs
- [ ] עדכן `RQ_QUEUES` ב-worker ו-docker-compose
- [ ] בדוק שכל פעולת bulk עוברת דרך worker
- [ ] הוסף לוגים: `JOB_START`, `JOB_PROGRESS`, `JOB_DONE`

## 🎯 סטנדרט אחיד לכל המערכת

**כל פעולה שיכולה לקחת >2 שניות חייבת:**
1. ✅ BackgroundJob record in DB
2. ✅ Enqueue to RQ (NOT threading.Thread)
3. ✅ Process in chunks (50-100 items)
4. ✅ Update heartbeat every batch
5. ✅ Support cancel/pause/resume
6. ✅ Return 202 + job_id immediately
7. ✅ Logs: JOB_START / JOB_PROGRESS / JOB_DONE

**אין חריגים. הכל דרך Worker. נקודה.**
