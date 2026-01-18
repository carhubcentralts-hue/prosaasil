#!/usr/bin/env python3
"""
Test for 5-minute notification warning

Verifies that the reminder scheduler now sends notifications at:
- 30 minutes before
- 15 minutes before  
- 5 minutes before (NEW)
"""

import os
import sys
import re

def test_scheduler_has_5_minute_warning():
    """Test that reminder_scheduler.py includes 5-minute warning logic"""
    print("Testing for 5-minute notification warning...")
    
    # Use relative path from script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scheduler_path = os.path.join(script_dir, 'server/services/notifications/reminder_scheduler.py')
    
    with open(scheduler_path, 'r') as f:
        content = f.read()
    
    # Check for 5-minute window definition
    if 'window_5_start' not in content or 'window_5_end' not in content:
        print("  ❌ FAIL: Missing 5-minute window variables")
        return False
    
    print("  ✅ Found 5-minute window variables")
    
    # Check for 5-minute check in the loop
    if 'window_5_start <= reminder.due_at <= window_5_end' not in content:
        print("  ❌ FAIL: Missing 5-minute window check")
        return False
    
    print("  ✅ Found 5-minute window check")
    
    # Check for 5-minute deduplication call
    if '_try_send_with_dedupe(db, reminder, lead, 5)' not in content:
        print("  ❌ FAIL: Missing 5-minute deduplication call")
        return False
    
    print("  ✅ Found 5-minute deduplication call")
    
    # Check for 5-minute message formatting
    if "minutes_before == 5" not in content:
        print("  ❌ FAIL: Missing 5-minute message formatting")
        return False
    
    print("  ✅ Found 5-minute message formatting")
    
    # Check for Hebrew text for 5 minutes
    if "5 דקות" not in content:
        print("  ❌ FAIL: Missing Hebrew text for 5 minutes")
        return False
    
    print("  ✅ Found Hebrew text for 5 minutes")
    
    # Check that docstring mentions 5 minutes
    if "5 minutes before" not in content:
        print("  ⚠️  WARNING: Docstring might not mention 5 minutes")
    else:
        print("  ✅ Docstring mentions 5 minutes")
    
    print("\n✅ All checks passed! 5-minute warning is implemented.")
    return True

def test_popup_window_is_30_minutes():
    """Test that popup window is set to 30 minutes"""
    print("\nTesting popup window duration...")
    
    # Use relative path from script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    context_path = os.path.join(script_dir, 'client/src/shared/contexts/NotificationContext.tsx')
    
    with open(context_path, 'r') as f:
        content = f.read()
    
    # Check for 30 minute constant
    if 'thirtyMinutesFromNow' not in content:
        print("  ❌ FAIL: Missing thirtyMinutesFromNow variable")
        return False
    
    print("  ✅ Found thirtyMinutesFromNow variable")
    
    # Check for 30 * 60 * 1000 calculation
    if '30 * 60 * 1000' not in content:
        print("  ❌ FAIL: Missing 30 minute calculation")
        return False
    
    print("  ✅ Found 30 minute calculation")
    
    # Check comment mentions 30 minutes
    if 'within 30 minutes' not in content and 'within the next 30 minutes' not in content:
        print("  ⚠️  WARNING: Comment might not mention 30 minutes")
    else:
        print("  ✅ Comment mentions 30 minutes")
    
    print("\n✅ Popup window is set to 30 minutes!")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TESTING 5-MINUTE NOTIFICATION WARNING")
    print("=" * 70)
    print()
    
    try:
        success1 = test_scheduler_has_5_minute_warning()
        success2 = test_popup_window_is_30_minutes()
        
        if success1 and success2:
            print("\n" + "=" * 70)
            print("✅ ALL TESTS PASSED!")
            print("=" * 70)
            print("\nNotification warnings are now sent at:")
            print("  • 30 minutes before")
            print("  • 15 minutes before")
            print("  • 5 minutes before (NEW!)")
            print("\nPopup alerts will show for tasks within 30 minutes")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
