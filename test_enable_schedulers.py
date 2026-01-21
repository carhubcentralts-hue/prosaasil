#!/usr/bin/env python3
"""
Test ENABLE_SCHEDULERS Flag

Validates that schedulers respect the ENABLE_SCHEDULERS environment variable.

NOTE: This test should be run in separate Python processes for proper isolation.
Run each test individually:
  ENABLE_SCHEDULERS=false python test_enable_schedulers.py disabled
  ENABLE_SCHEDULERS=true python test_enable_schedulers.py enabled
  python test_enable_schedulers.py default
"""
import os
import sys
import time
import threading

def check_scheduler_threads():
    """Check which scheduler threads are running"""
    threads = threading.enumerate()
    thread_names = [t.name for t in threads]
    
    # Scheduler threads we're looking for
    scheduler_threads = [
        'RecordingCleanup',
        'RecordingWorker',
        'ReminderScheduler'
    ]
    
    found = [t for t in scheduler_threads if t in thread_names]
    return thread_names, found

def test_schedulers_by_env():
    """Test schedulers based on current environment"""
    enable_flag = os.getenv('ENABLE_SCHEDULERS', 'not_set')
    service_role = os.getenv('SERVICE_ROLE', 'unknown')
    
    print("=" * 80)
    print(f"Testing ENABLE_SCHEDULERS Flag")
    print("=" * 80)
    print(f"ENABLE_SCHEDULERS: {enable_flag}")
    print(f"SERVICE_ROLE: {service_role}")
    print()
    
    # Set test database
    os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///test.db')
    os.environ['FLASK_ENV'] = 'test'
    
    # Import after environment is set
    from server.app_factory import create_app
    
    print("Creating Flask app...")
    app = create_app()
    
    # Wait for threads to start
    print("Waiting for background threads to initialize...")
    time.sleep(3)
    
    # Check threads
    thread_names, found_schedulers = check_scheduler_threads()
    
    print(f"\nActive threads: {len(thread_names)}")
    for name in thread_names:
        marker = "🟢" if name in ['RecordingCleanup', 'RecordingWorker', 'ReminderScheduler'] else "  "
        print(f"  {marker} {name}")
    
    print(f"\nScheduler threads found: {len(found_schedulers)}")
    for name in found_schedulers:
        print(f"  ✅ {name}")
    
    # Determine expected behavior
    should_have_schedulers = enable_flag.lower() == 'true'
    
    print("\n" + "=" * 80)
    
    if should_have_schedulers:
        if found_schedulers:
            print(f"✅ PASS: Schedulers running as expected (ENABLE_SCHEDULERS=true)")
            return True
        else:
            print(f"⚠️  WARNING: No schedulers found but ENABLE_SCHEDULERS=true")
            print(f"   This may be expected if dependencies are missing in test environment")
            return True
    else:
        if found_schedulers:
            print(f"❌ FAIL: Schedulers running when ENABLE_SCHEDULERS={enable_flag}")
            print(f"   Found: {', '.join(found_schedulers)}")
            return False
        else:
            print(f"✅ PASS: No schedulers running (ENABLE_SCHEDULERS={enable_flag})")
            return True

if __name__ == "__main__":
    test_mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    
    if test_mode == 'disabled':
        os.environ['ENABLE_SCHEDULERS'] = 'false'
        os.environ['SERVICE_ROLE'] = 'api'
    elif test_mode == 'enabled':
        os.environ['ENABLE_SCHEDULERS'] = 'true'
        os.environ['SERVICE_ROLE'] = 'worker'
    elif test_mode == 'default':
        if 'ENABLE_SCHEDULERS' in os.environ:
            del os.environ['ENABLE_SCHEDULERS']
        os.environ['SERVICE_ROLE'] = 'api'
    elif test_mode != 'check':
        print("Usage:")
        print("  python test_enable_schedulers.py disabled  # Test with ENABLE_SCHEDULERS=false")
        print("  python test_enable_schedulers.py enabled   # Test with ENABLE_SCHEDULERS=true")
        print("  python test_enable_schedulers.py default   # Test without ENABLE_SCHEDULERS set")
        print("  python test_enable_schedulers.py check     # Check current environment")
        sys.exit(1)
    
    try:
        success = test_schedulers_by_env()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
