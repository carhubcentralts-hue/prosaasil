# Recording Cleanup System

## Overview
AgentLocator automatically manages call recordings with a **2-day retention policy** (48 hours exactly).

## What Gets Cleaned Up
After 48 hours from creation, recordings are:
1. **Deleted from disk** - Physical `.mp3` files removed from `server/recordings/`
2. **Cleared from database** - `recording_url` set to `NULL` in `CallLog` table
3. **Transcripts preserved** - Text transcriptions remain intact for reference

## Manual Cleanup
Admins can trigger cleanup manually:

```bash
POST /api/calls/cleanup
Authorization: Bearer <admin_token>
```

Response:
```json
{
  "success": true,
  "deleted_count": 15,
  "files_deleted": 12,
  "message": "נמחקו 15 הקלטות (12 קבצים מהדיסק)"
}
```

## Automated Cleanup
To run cleanup automatically, set up a cron job:

### Option 1: Cron Job (Recommended)
```cron
# Run cleanup daily at 3 AM
0 3 * * * curl -X POST http://localhost:5000/api/calls/cleanup \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Option 2: Python Scheduler
Add to your application startup:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from server.tasks_recording import auto_cleanup_old_recordings

scheduler = BackgroundScheduler()
scheduler.add_job(
    auto_cleanup_old_recordings,
    'cron',
    hour=3,  # Run at 3 AM daily
    minute=0
)
scheduler.start()
```

## Implementation Details

### Function: `auto_cleanup_old_recordings()`
Location: `server/tasks_recording.py`

```python
def auto_cleanup_old_recordings():
    """✨ Automatic cleanup of recordings older than 2 days"""
    # 1. Query recordings older than 48 hours
    cutoff_date = datetime.utcnow() - timedelta(days=2)
    old_calls = CallLog.query.filter(
        CallLog.created_at < cutoff_date,
        CallLog.recording_url.isnot(None)
    ).all()
    
    # 2. Delete physical files
    for call in old_calls:
        file_path = f"server/recordings/{call.call_sid}.mp3"
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # 3. Clear URLs from DB (keep transcriptions)
    call.recording_url = None
    db.session.commit()
```

### Expiry Check
Location: `server/routes_calls.py`

```python
# Downloads blocked after 48 hours exactly
if call.created_at and (datetime.utcnow() - call.created_at) > timedelta(days=2):
    return jsonify({"error": "Recording expired and deleted"}), 410
```

## Testing Cleanup

1. **Create test recording** - Make a call to generate a recording
2. **Wait 48+ hours** OR manually adjust `created_at` in database
3. **Run cleanup**:
   ```bash
   curl -X POST http://localhost:5000/api/calls/cleanup \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
4. **Verify** - Check that file is deleted and URL is NULL

## Monitoring

Track cleanup effectiveness:
```bash
# Check recordings count
GET /api/calls/stats

# Response includes expiring_soon count
{
  "total_calls": 150,
  "with_recording": 45,
  "expiring_soon": 8
}
```

## Important Notes

⚠️ **Retention Period**: Exactly 48 hours (not "2 days" which could be up to 71h59m)
✅ **Transcripts Safe**: Text transcriptions are never deleted
🔒 **Admin Only**: Cleanup endpoint requires admin role
📁 **Disk Space**: Cleanup removes both DB entries and physical files
