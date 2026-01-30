#!/usr/bin/env python3
"""
Database Backfill Tool - Wrapper for Registry System
====================================================

This is a simple wrapper that runs the central backfill system.

⚠️ ONE SOURCE OF TRUTH: All backfill logic is in:
   - server/db_backfills.py (registry definitions)
   - server/db_run_backfills.py (runner)

This file exists only for backward compatibility with:
- docker-compose.prod.yml
- deploy_production.sh

Usage:
    python server/db_backfill.py [--max-time=600] [--batch-size=100]

Note: This wrapper simply calls db_run_backfills.py --all
"""

import sys
import os
import subprocess
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Main entry point - delegates to db_run_backfills.py."""
    parser = argparse.ArgumentParser(description='Run database backfill operations')
    parser.add_argument('--max-time', type=int, default=600,
                        help='Maximum time to run in seconds (default: 600)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of rows per batch (default: 100) - DEPRECATED, set in registry')
    args = parser.parse_args()
    
    # Convert seconds to minutes for db_run_backfills.py
    max_minutes = args.max_time // 60
    
    print("=" * 80)
    print("Database Backfill Tool (Wrapper)")
    print("=" * 80)
    print(f"Delegating to db_run_backfills.py --all --max-minutes={max_minutes}")
    print("=" * 80)
    print()
    
    # Call the central runner
    runner_path = os.path.join(os.path.dirname(__file__), 'db_run_backfills.py')
    
    try:
        result = subprocess.run(
            ['python', runner_path, '--all', f'--max-minutes={max_minutes}'],
            check=False  # Don't raise on non-zero exit
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Error running backfill runner: {e}")
        # Always exit 0 to not block deployment
        sys.exit(0)


if __name__ == '__main__':
    main()
