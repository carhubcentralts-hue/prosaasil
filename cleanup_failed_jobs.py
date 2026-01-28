#!/usr/bin/env python3
"""
Cleanup Failed Jobs Script
סקריפט ניקוי jobs שנכשלו

Removes failed jobs from RQ registry, especially those with timeout errors.
"""

import os
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent / 'server'))

def main():
    print("🧹 Cleaning Failed Jobs")
    print("=" * 60)
    print()
    
    try:
        from server.services.jobs import get_redis, get_queue
        from rq.registry import FailedJobRegistry
        from rq.job import Job
        
        redis_conn = get_redis()
        
        # Queue names to clean
        queue_names = ['default', 'high', 'low', 'maintenance', 'broadcasts', 
                      'recordings', 'receipts', 'receipts_sync']
        
        total_cleaned = 0
        
        for queue_name in queue_names:
            try:
                queue = get_queue(queue_name)
                failed_registry = FailedJobRegistry(queue=queue)
                failed_count = len(failed_registry)
                
                if failed_count == 0:
                    continue
                
                print(f"📋 Queue: {queue_name}")
                print(f"   Failed jobs: {failed_count}")
                
                # Ask for confirmation
                response = input(f"   Clear all {failed_count} failed jobs? [y/N]: ")
                
                if response.lower() == 'y':
                    failed_registry.empty()
                    print(f"   ✅ Cleared {failed_count} jobs")
                    total_cleaned += failed_count
                else:
                    print(f"   ⏭️  Skipped")
                
                print()
                
            except Exception as e:
                print(f"   ❌ Error cleaning {queue_name}: {e}")
                print()
        
        print("=" * 60)
        print(f"✅ Total cleaned: {total_cleaned} jobs")
        print()
        
        if total_cleaned > 0:
            print("Next steps:")
            print("  1. Restart workers: systemctl restart rq-worker")
            print("  2. Test WhatsApp from Android")
            print("  3. Monitor logs: tail -f /var/log/rq-worker.log")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
