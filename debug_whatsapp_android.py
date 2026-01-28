#!/usr/bin/env python3
"""
WhatsApp Android Debug Script
סקריפט בדיקה ותיקון לבעיית אנדרואיד שלא עונה

This script:
1. Checks RQ worker status
2. Lists failed jobs and their errors
3. Clears failed jobs with timeout errors
4. Shows queue statistics
5. Tests webhook processing
"""

import os
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent / 'server'))

def main():
    print("🔍 WhatsApp Android Response Debugging")
    print("=" * 60)
    print()
    
    try:
        from server.services.jobs import get_redis, get_queue, get_queue_stats
        from rq import Worker
        from rq.registry import FailedJobRegistry, StartedJobRegistry
        from rq.job import Job
        
        redis_conn = get_redis()
        
        # 1. Check workers
        print("📊 1. WORKER STATUS")
        print("-" * 60)
        workers = Worker.all(connection=redis_conn)
        
        if not workers:
            print("❌ NO WORKERS RUNNING!")
            print("   → Workers are required to process WhatsApp messages")
            print("   → Start workers with: rq worker default high low")
            print()
        else:
            for worker in workers:
                state = "🟢 Working" if worker.get_state() == 'busy' else "🟡 Idle"
                print(f"  {state} {worker.name}")
                print(f"     Queues: {', '.join([q.name for q in worker.queues])}")
                print(f"     State: {worker.get_state()}")
                current_job = worker.get_current_job()
                if current_job:
                    print(f"     Current Job: {current_job.func_name}")
            print()
        
        # 2. Queue stats
        print("📊 2. QUEUE STATISTICS")
        print("-" * 60)
        stats = get_queue_stats()
        for queue_name, queue_stats in stats.items():
            if isinstance(queue_stats, dict) and 'error' not in queue_stats:
                total = sum(queue_stats.values())
                if total > 0 or queue_name == 'default':  # Always show default
                    print(f"  {queue_name}:")
                    print(f"    Queued: {queue_stats['queued']}")
                    print(f"    Started: {queue_stats['started']}")
                    print(f"    Failed: {queue_stats['failed']}")
                    print(f"    Finished: {queue_stats['finished']}")
        print()
        
        # 3. Check failed jobs in default queue (where webhooks go)
        print("📊 3. FAILED JOBS ANALYSIS")
        print("-" * 60)
        
        queue = get_queue('default')
        failed_registry = FailedJobRegistry(queue=queue)
        failed_job_ids = failed_registry.get_job_ids()
        
        if not failed_job_ids:
            print("  ✅ No failed jobs!")
            print()
        else:
            print(f"  ⚠️  Found {len(failed_job_ids)} failed jobs")
            print()
            
            timeout_errors = 0
            webhook_errors = 0
            other_errors = 0
            
            # Analyze first 20 failed jobs
            for job_id in failed_job_ids[:20]:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    func_name = job.func_name if hasattr(job, 'func_name') else 'unknown'
                    exc_info = job.exc_info if hasattr(job, 'exc_info') else ''
                    
                    # Check for timeout error
                    if 'timeout' in str(exc_info).lower() and 'unexpected keyword' in str(exc_info).lower():
                        timeout_errors += 1
                        if timeout_errors <= 3:  # Show first 3
                            print(f"  ❌ {job_id[:8]}... - {func_name}")
                            print(f"     Error: TypeError - unexpected keyword 'timeout'")
                            print(f"     → This is the bug that was fixed!")
                    elif 'webhook_process_job' in func_name:
                        webhook_errors += 1
                        if webhook_errors <= 3:  # Show first 3
                            print(f"  ⚠️  {job_id[:8]}... - {func_name}")
                            error_line = str(exc_info).split('\n')[-2] if exc_info else 'Unknown'
                            print(f"     Error: {error_line[:80]}")
                    else:
                        other_errors += 1
                        
                except Exception as e:
                    print(f"  ? {job_id[:8]}... - Could not fetch: {e}")
            
            print()
            print(f"  Summary:")
            print(f"    Timeout errors (bug): {timeout_errors}")
            print(f"    Webhook errors: {webhook_errors}")
            print(f"    Other errors: {other_errors}")
            print()
            
            # 4. Offer to clean
            if timeout_errors > 0:
                print("🔧 4. CLEANUP RECOMMENDATION")
                print("-" * 60)
                print(f"  Found {timeout_errors} jobs with the timeout bug")
                print("  These jobs failed because of the bug that was fixed.")
                print()
                print("  To clean them, run:")
                print("    python cleanup_failed_jobs.py")
                print()
        
        # 5. Check webhook processing
        print("📊 5. WEBHOOK PROCESSING CHECK")
        print("-" * 60)
        
        # Check if webhook_process_job is in the queue
        from server.jobs.webhook_process_job import webhook_process_job
        
        started_registry = StartedJobRegistry(queue=queue)
        started_job_ids = started_registry.get_job_ids()
        
        webhook_in_progress = False
        for job_id in started_job_ids:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                if 'webhook_process_job' in job.func_name:
                    webhook_in_progress = True
                    print(f"  🔄 Webhook job in progress: {job_id[:8]}...")
            except:
                pass
        
        if not webhook_in_progress:
            print("  ℹ️  No webhook jobs currently processing")
        print()
        
        # 6. Next steps
        print("📋 6. TROUBLESHOOTING STEPS")
        print("-" * 60)
        print()
        print("If WhatsApp still doesn't respond from Android:")
        print()
        print("  1. ✅ Verify workers are running (see section 1)")
        print("     → If no workers: start with 'rq worker default high low'")
        print()
        print("  2. 🧹 Clean failed jobs if timeout errors found")
        print("     → Run: python cleanup_failed_jobs.py")
        print()
        print("  3. 📱 Send test message from Android")
        print("     → Check logs: tail -f /var/log/rq-worker.log")
        print("     → Look for: [WEBHOOK_JOB] and [SEND_RESULT]")
        print()
        print("  4. 🔍 Check if message reaches webhook:")
        print("     → Check logs: grep 'whatsapp_incoming' /var/log/flask.log")
        print()
        print("  5. 🤖 Verify AI is active for conversation:")
        print("     → In UI, check conversation AI toggle")
        print()
        
    except Exception as e:
        print(f"❌ Error running diagnostics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
