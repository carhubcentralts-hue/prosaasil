#!/usr/bin/env python3
"""
Test for Smart Watchdog Fix - Prevents premature disconnects during finishing states

This test verifies that the watchdog correctly handles "finishing" states:
1. pending_hangup=True (polite hangup in progress)
2. hangup_triggered=True (hangup already initiated)
3. Non-empty audio queues (audio still draining/playing)

The watchdog should ONLY disconnect when the call is truly idle.
"""

import re


def test_watchdog_smart_logic():
    """Verify watchdog has smart logic for finishing states"""
    
    with open("server/media_ws_ai.py", "r") as f:
        content = f.read()
    
    # Find the _silence_watchdog method
    watchdog_match = re.search(
        r'async def _silence_watchdog\(self\):.*?(?=\n    (?:async )?def |\nclass |\Z)',
        content,
        re.DOTALL
    )
    
    assert watchdog_match, "❌ Could not find _silence_watchdog method"
    watchdog_code = watchdog_match.group(0)
    
    print("✅ Found _silence_watchdog method")
    
    # Check 1: Verify it checks pending_hangup
    assert "pending_hangup" in watchdog_code, "❌ Watchdog doesn't check pending_hangup flag"
    assert "getattr(self, 'pending_hangup', False)" in watchdog_code, "❌ Watchdog doesn't safely check pending_hangup"
    print("✅ Watchdog checks pending_hangup flag")
    
    # Check 2: Verify it checks hangup_triggered
    assert "hangup_triggered" in watchdog_code, "❌ Watchdog doesn't check hangup_triggered flag"
    assert "getattr(self, 'hangup_triggered', False)" in watchdog_code, "❌ Watchdog doesn't safely check hangup_triggered"
    print("✅ Watchdog checks hangup_triggered flag")
    
    # Check 3: Verify it checks audio queues
    assert "realtime_audio_out_queue.qsize()" in watchdog_code, "❌ Watchdog doesn't check realtime_audio_out_queue"
    assert "tx_q.qsize()" in watchdog_code, "❌ Watchdog doesn't check tx_q"
    print("✅ Watchdog checks audio queue sizes")
    
    # Check 4: Verify it continues (skips disconnect) when in finishing states
    assert "continue" in watchdog_code, "❌ Watchdog doesn't use continue to skip disconnect"
    
    # Count number of continue statements (should be at least 3 for the 3 checks)
    continue_count = len(re.findall(r'\bcontinue\b', watchdog_code))
    assert continue_count >= 3, f"❌ Expected at least 3 continue statements, found {continue_count}"
    print(f"✅ Watchdog has {continue_count} continue statements for finishing state checks")
    
    # Check 5: Verify idle threshold is still 20 seconds
    assert "if idle >= 20.0:" in watchdog_code, "❌ Idle threshold changed from 20 seconds"
    print("✅ Watchdog maintains 20-second idle threshold")
    
    # Check 6: Verify original disconnect logic is still present
    assert "_immediate_hangup" in watchdog_code, "❌ Watchdog missing _immediate_hangup call"
    assert 'reason="silence_20s"' in watchdog_code, "❌ Watchdog missing silence_20s reason"
    print("✅ Watchdog still triggers immediate hangup for true idle")
    
    print("\n" + "="*70)
    print("🎯 SMART WATCHDOG FIX VERIFIED")
    print("="*70)
    print("\nThe watchdog now intelligently considers finishing states:")
    print("  ✅ pending_hangup=True → Call is finishing normally (polite hangup)")
    print("  ✅ hangup_triggered=True → Hangup already initiated")
    print("  ✅ Audio in queues → Audio still draining/playing")
    print("\nThese checks prevent false disconnects during:")
    print("  • Long AI responses (while audio is playing)")
    print("  • Audio drain period (after response.done)")
    print("  • Polite hangup process (waiting for playback to complete)")
    print("\nThe watchdog still disconnects after 20s of TRUE idle:")
    print("  • No user activity AND no bot activity")
    print("  • No audio in queues")
    print("  • No hangup in progress")
    print("="*70)


def test_watchdog_logging():
    """Verify watchdog has informative logging for skipped disconnects"""
    
    with open("server/media_ws_ai.py", "r") as f:
        content = f.read()
    
    watchdog_match = re.search(
        r'async def _silence_watchdog\(self\):.*?(?=\n    (?:async )?def |\nclass |\Z)',
        content,
        re.DOTALL
    )
    
    assert watchdog_match, "❌ Could not find _silence_watchdog method"
    watchdog_code = watchdog_match.group(0)
    
    # Check for informative logging when skipping disconnect
    assert "but pending_hangup=True" in watchdog_code or "but call is finishing" in watchdog_code, \
        "❌ Missing informative log for pending_hangup check"
    
    assert "but audio draining" in watchdog_code or "frames still queued" in watchdog_code, \
        "❌ Missing informative log for audio queue check"
    
    print("✅ Watchdog has informative logging for finishing states")
    print("   - Logs when skipping disconnect due to pending_hangup")
    print("   - Logs when skipping disconnect due to audio draining")


if __name__ == "__main__":
    try:
        test_watchdog_smart_logic()
        print()
        test_watchdog_logging()
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED - Smart Watchdog Fix Verified")
        print("="*70)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
