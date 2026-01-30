#!/usr/bin/env python3
"""
Kill idle transactions that might be blocking migrations.

This script terminates PostgreSQL sessions that are:
- In "idle in transaction" state
- Have been running for more than 60 seconds
- Are not the current session

This is useful before running migrations to clear any stuck connections
that might hold locks and cause DDL operations to timeout.

Usage:
    python scripts/kill_idle_transactions.py
    python scripts/kill_idle_transactions.py --dry-run
"""
import sys
import os
import argparse
from sqlalchemy import text, create_engine

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_database_url():
    """Get database URL from environment or default."""
    # Try to get from environment (Docker compose sets this)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url
    
    # Fallback: construct from individual components
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'prosaas')
    db_user = os.environ.get('DB_USER', 'postgres')
    db_pass = os.environ.get('DB_PASSWORD', 'postgres')
    
    return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


KILL_IDLE_TX_SQL = """
SELECT 
    pid,
    state,
    now() - xact_start as duration,
    query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '60 seconds'
  AND pid <> pg_backend_pid()
ORDER BY xact_start
"""


def list_idle_transactions(engine):
    """List all idle transactions that would be killed."""
    print("\n🔍 Searching for idle transactions...")
    
    with engine.connect() as conn:
        result = conn.execute(text(KILL_IDLE_TX_SQL))
        rows = result.fetchall()
        
        if not rows:
            print("✅ No idle transactions found (all clear)")
            return []
        
        print(f"\n⚠️  Found {len(rows)} idle transaction(s):\n")
        print("-" * 80)
        
        for row in rows:
            pid, state, duration, query = row
            print(f"PID: {pid}")
            print(f"  State: {state}")
            print(f"  Duration: {duration}")
            print(f"  Query: {query[:200] if query else 'N/A'}")
            print("-" * 80)
        
        return [row[0] for row in rows]


def kill_idle_transactions(engine, pids, dry_run=False):
    """Kill the specified idle transactions."""
    if not pids:
        return
    
    if dry_run:
        print(f"\n🔸 DRY RUN: Would terminate {len(pids)} process(es)")
        return
    
    print(f"\n🔥 Terminating {len(pids)} idle transaction(s)...")
    
    killed_count = 0
    failed_count = 0
    
    with engine.connect() as conn:
        for pid in pids:
            try:
                result = conn.execute(
                    text("SELECT pg_terminate_backend(:pid)"),
                    {"pid": pid}
                )
                if result.scalar():
                    print(f"  ✅ Terminated PID {pid}")
                    killed_count += 1
                else:
                    print(f"  ⚠️  Could not terminate PID {pid} (may have already ended)")
                    failed_count += 1
            except Exception as e:
                print(f"  ❌ Error terminating PID {pid}: {e}")
                failed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"  Terminated: {killed_count}")
    print(f"  Failed: {failed_count}")
    
    if killed_count > 0:
        print("\n✅ Idle transactions cleared - ready for migrations")
    else:
        print("\n⚠️  No transactions were terminated")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Kill idle transactions blocking migrations"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be killed without actually killing"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🧹 Idle Transaction Killer")
    print("=" * 80)
    print("\nThis script terminates PostgreSQL sessions that are:")
    print("  • In 'idle in transaction' state")
    print("  • Have been idle for more than 60 seconds")
    print("  • Are not the current session")
    print()
    
    if args.dry_run:
        print("🔸 DRY RUN MODE - No transactions will be terminated")
    else:
        print("⚠️  LIVE MODE - Transactions will be terminated")
    
    # Create database engine
    db_url = get_database_url()
    print(f"\n🔌 Connecting to database...")
    engine = create_engine(db_url)
    
    # List idle transactions
    pids = list_idle_transactions(engine)
    
    if not pids:
        print("\n✅ No action needed")
        return 0
    
    # Kill them if not dry run
    kill_idle_transactions(engine, pids, dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
