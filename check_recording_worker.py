#!/usr/bin/env python3
"""
Diagnostic script to check if recording worker is running and processing jobs.
Run this to diagnose why recordings are not being downloaded.
"""
import os
import sys
import redis
from rq import Queue
from server.app_factory import get_process_app
from server.models_sql import RecordingRun, db

def main():
    print("=" * 80)
    print("Recording Worker Diagnostic Check")
    print("=" * 80)
    
    # Check REDIS_URL
    REDIS_URL = os.getenv('REDIS_URL')
    if not REDIS_URL:
        print("❌ REDIS_URL environment variable not set")
        return 1
    else:
        print(f"✅ REDIS_URL is set")
    
    # Check Redis connection
    try:
        redis_conn = redis.from_url(REDIS_URL)
        redis_conn.ping()
        print(f"✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return 1
    
    # Check RQ queues
    try:
        queue = Queue('recordings', connection=redis_conn)
        queue_length = len(queue)
        print(f"✅ RQ 'recordings' queue exists, length: {queue_length}")
        
        if queue_length > 0:
            print(f"   📋 Jobs in queue:")
            for job in queue.jobs[:10]:  # Show first 10
                print(f"      - {job.id}: {job.func_name}")
        
        # Check for failed jobs
        failed_queue = queue.failed_job_registry
        failed_count = len(failed_queue)
        if failed_count > 0:
            print(f"   ⚠️  Failed jobs: {failed_count}")
            for job_id in list(failed_queue.get_job_ids())[:5]:  # Show first 5
                job = queue.fetch_job(job_id)
                if job:
                    print(f"      - {job_id}: {job.exc_info[:200] if job.exc_info else 'No error info'}")
        
    except Exception as e:
        print(f"❌ Error checking RQ queue: {e}")
        return 1
    
    # Check RecordingRun entries
    try:
        app = get_process_app()
        with app.app_context():
            # Count queued and running jobs
            queued_count = RecordingRun.query.filter(
                RecordingRun.status.in_(['queued', 'running'])
            ).count()
            
            print(f"\n📊 RecordingRun Statistics:")
            print(f"   - Queued/Running: {queued_count}")
            
            if queued_count > 0:
                print(f"   📋 Recent queued/running jobs:")
                runs = RecordingRun.query.filter(
                    RecordingRun.status.in_(['queued', 'running'])
                ).order_by(RecordingRun.created_at.desc()).limit(10).all()
                
                for run in runs:
                    age = (db.func.now() - run.created_at).total_seconds() if run.created_at else 0
                    print(f"      - Run {run.id}: call_sid={run.call_sid} status={run.status} job_type={run.job_type} age={int(age)}s")
            
            # Count completed jobs (last hour)
            from datetime import datetime, timedelta
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            completed_count = RecordingRun.query.filter(
                RecordingRun.status == 'completed',
                RecordingRun.completed_at >= one_hour_ago
            ).count()
            
            print(f"   - Completed (last hour): {completed_count}")
            
            # Count failed jobs (last hour)
            failed_count = RecordingRun.query.filter(
                RecordingRun.status == 'failed',
                RecordingRun.completed_at >= one_hour_ago
            ).count()
            
            if failed_count > 0:
                print(f"   - Failed (last hour): {failed_count}")
                
                failed_runs = RecordingRun.query.filter(
                    RecordingRun.status == 'failed',
                    RecordingRun.completed_at >= one_hour_ago
                ).order_by(RecordingRun.completed_at.desc()).limit(5).all()
                
                print(f"   📋 Recent failures:")
                for run in failed_runs:
                    print(f"      - Run {run.id}: call_sid={run.call_sid} error={run.error_message[:100] if run.error_message else 'No error'}")
    
    except Exception as e:
        print(f"❌ Error checking RecordingRun: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Check recordings directory
    try:
        from server.services.recording_service import _get_recordings_dir
        recordings_dir = _get_recordings_dir()
        if os.path.exists(recordings_dir):
            file_count = len([f for f in os.listdir(recordings_dir) if f.endswith('.mp3')])
            print(f"\n✅ Recordings directory exists: {recordings_dir}")
            print(f"   - MP3 files: {file_count}")
        else:
            print(f"\n⚠️  Recordings directory does not exist: {recordings_dir}")
    except Exception as e:
        print(f"❌ Error checking recordings directory: {e}")
    
    print("\n" + "=" * 80)
    print("Diagnostic Summary:")
    print("=" * 80)
    
    if queued_count > 0 and queue_length == 0:
        print("⚠️  WARNING: RecordingRun entries exist but RQ queue is empty")
        print("   This suggests jobs were created but not enqueued to RQ properly")
    elif queue_length > 0 and completed_count == 0:
        print("⚠️  WARNING: Jobs in RQ queue but no completions in last hour")
        print("   This suggests the worker may not be running or processing jobs")
    elif failed_count > 0:
        print("⚠️  WARNING: Failed jobs detected - check errors above")
    else:
        print("✅ System appears healthy")
    
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
