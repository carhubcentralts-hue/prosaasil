#!/usr/bin/env python3
"""
Report Failed RQ Jobs
P3-3: Worker Reliability - Dead-letter / report script

This script queries Redis for failed jobs and generates a summary report.
Useful for monitoring and debugging production worker issues.

Usage:
    python scripts/report_failed_jobs.py
    python scripts/report_failed_jobs.py --detailed
    python scripts/report_failed_jobs.py --queue=receipts
"""
import os
import sys
import argparse
from datetime import datetime, timezone
from collections import defaultdict

# Add server to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def report_failed_jobs(detailed=False, queue_name=None):
    """
    Report failed RQ jobs from Redis
    
    Args:
        detailed: If True, show full job details
        queue_name: Optional queue name filter
    """
    try:
        import redis
        from rq import Queue, get_failed_queue
        from rq.job import Job
        from rq.registry import FailedJobRegistry
    except ImportError:
        print("ERROR: RQ not installed. Install with: pip install rq")
        sys.exit(1)
    
    # Get Redis URL from environment
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print("ERROR: REDIS_URL environment variable not set")
        sys.exit(1)
    
    # Mask password for display
    masked_url = redis_url
    if '@' in redis_url:
        parts = redis_url.split('@')
        if ':' in parts[0]:
            user_pass = parts[0].split(':')
            masked_url = f"{user_pass[0]}:{user_pass[1].split('//')[0]}//***@{parts[1]}"
    
    print("=" * 80)
    print("Failed RQ Jobs Report")
    print("=" * 80)
    print(f"Redis: {masked_url}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Connect to Redis
    try:
        redis_conn = redis.from_url(redis_url)
        redis_conn.ping()
    except Exception as e:
        print(f"ERROR: Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Get failed jobs
    try:
        # Get failed queue
        failed_queue = get_failed_queue(connection=redis_conn)
        failed_job_ids = failed_queue.job_ids
        
        print(f"Total failed jobs: {len(failed_job_ids)}")
        print()
        
        if not failed_job_ids:
            print("✓ No failed jobs found!")
            print("=" * 80)
            return
        
        # Statistics
        stats = {
            'by_func': defaultdict(int),
            'by_queue': defaultdict(int),
            'by_error': defaultdict(int),
        }
        
        failed_jobs = []
        
        # Collect job details
        for job_id in failed_job_ids:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                
                # Apply queue filter if specified
                if queue_name and job.origin != queue_name:
                    continue
                
                failed_jobs.append(job)
                
                # Update stats
                func_name = job.func_name if hasattr(job, 'func_name') else 'unknown'
                stats['by_func'][func_name] += 1
                stats['by_queue'][job.origin] += 1
                
                # Get error type
                exc_info = job.exc_info or ''
                error_type = 'unknown'
                if exc_info:
                    # Extract first line of exception
                    first_line = exc_info.split('\n')[-2] if '\n' in exc_info else exc_info
                    if ':' in first_line:
                        error_type = first_line.split(':')[0].strip()
                stats['by_error'][error_type] += 1
                
            except Exception as e:
                print(f"WARNING: Failed to fetch job {job_id}: {e}")
        
        # Print summary statistics
        print("Summary by Function:")
        print("-" * 80)
        for func_name, count in sorted(stats['by_func'].items(), key=lambda x: -x[1]):
            print(f"  {func_name}: {count}")
        print()
        
        print("Summary by Queue:")
        print("-" * 80)
        for queue, count in sorted(stats['by_queue'].items(), key=lambda x: -x[1]):
            print(f"  {queue}: {count}")
        print()
        
        print("Summary by Error Type:")
        print("-" * 80)
        for error_type, count in sorted(stats['by_error'].items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")
        print()
        
        # Detailed report if requested
        if detailed and failed_jobs:
            print("=" * 80)
            print("Detailed Job Information:")
            print("=" * 80)
            
            for i, job in enumerate(failed_jobs, 1):
                print()
                print(f"Job #{i}: {job.id}")
                print("-" * 80)
                print(f"  Function: {job.func_name if hasattr(job, 'func_name') else 'unknown'}")
                print(f"  Queue: {job.origin}")
                print(f"  Created: {job.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if job.created_at else 'unknown'}")
                print(f"  Failed: {job.ended_at.strftime('%Y-%m-%d %H:%M:%S UTC') if job.ended_at else 'unknown'}")
                
                # Print arguments
                if hasattr(job, 'args') and job.args:
                    print(f"  Args: {job.args}")
                if hasattr(job, 'kwargs') and job.kwargs:
                    print(f"  Kwargs: {job.kwargs}")
                
                # Print metadata
                if hasattr(job, 'meta') and job.meta:
                    print(f"  Metadata:")
                    for key, value in job.meta.items():
                        print(f"    {key}: {value}")
                
                # Print exception
                if job.exc_info:
                    print(f"  Exception:")
                    # Print last 500 chars of exception to avoid spam
                    exc_preview = job.exc_info[-500:] if len(job.exc_info) > 500 else job.exc_info
                    for line in exc_preview.split('\n'):
                        print(f"    {line}")
        else:
            print()
            print("Run with --detailed flag to see full job information")
        
        print()
        print("=" * 80)
        print(f"Total failed jobs reported: {len(failed_jobs)}")
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: Failed to fetch failed jobs: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Report failed RQ jobs from Redis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/report_failed_jobs.py
  python scripts/report_failed_jobs.py --detailed
  python scripts/report_failed_jobs.py --queue=default
  python scripts/report_failed_jobs.py --queue=receipts --detailed
        """
    )
    parser.add_argument(
        '--detailed', '-d',
        action='store_true',
        help='Show detailed job information including exceptions'
    )
    parser.add_argument(
        '--queue', '-q',
        type=str,
        help='Filter by queue name (e.g., default, receipts, high)'
    )
    
    args = parser.parse_args()
    report_failed_jobs(detailed=args.detailed, queue_name=args.queue)


if __name__ == '__main__':
    main()
