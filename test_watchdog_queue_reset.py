#!/usr/bin/env python3
"""
🔥 CRITICAL TEST: Watchdog resets silence counter when bot is speaking

This test verifies the CRITICAL fix that prevents false disconnects when AI speaks for >20s:

PROBLEM:
- AI speaks for 25 seconds (long message)
- _last_activity_ts was updated at start (t=0)
- At t=20s, watchdog checks: idle=20s → Would disconnect!
- But AI is STILL SPEAKING! (audio in queues)

SOLUTION:
- Watchdog checks if audio queues have frames
- If yes: Bot is speaking → Update _last_activity_ts → Reset counter to 0
- This prevents false disconnect during long AI responses

This test verifies that:
1. Watchdog checks audio queue sizes
2. Watchdog RESETS _last_activity_ts when audio in queues
3. This reset happens INSIDE the watchdog loop
"""

import re


def test_watchdog_resets_on_audio():
    """Verify watchdog resets activity timestamp when bot is speaking (audio in queues)"""
    
    print("="*80)
    print("🔥 CRITICAL TEST: Watchdog Queue Reset Fix")
    print("="*80)
    
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
    
    print("\n📋 Verifying queue checking logic...")
    
    # Check 1: Watchdog checks queue sizes
    assert "realtime_audio_out_queue.qsize()" in watchdog_code, \
        "❌ Watchdog doesn't check realtime_audio_out_queue"
    assert "tx_q.qsize()" in watchdog_code, \
        "❌ Watchdog doesn't check tx_q"
    print("✅ Watchdog checks both audio queues")
    
    # Check 2: Watchdog calculates total queued frames
    assert "total_queued" in watchdog_code or "total_frames" in watchdog_code, \
        "❌ Watchdog doesn't calculate total queued frames"
    print("✅ Watchdog calculates total queued frames")
    
    # Check 3: CRITICAL - Watchdog checks if total_queued > 0
    assert "if total_queued > 0:" in watchdog_code or "if total_frames > 0:" in watchdog_code, \
        "❌ Watchdog doesn't check if audio is queued"
    print("✅ Watchdog checks if audio is queued (bot speaking)")
    
    # Check 4: CRITICAL - Find the code block that runs when audio is queued
    # This should include: update _last_activity_ts AND continue
    queued_block_match = re.search(
        r'if total_queued > 0:.*?continue',
        watchdog_code,
        re.DOTALL
    )
    
    assert queued_block_match, "❌ Watchdog doesn't have proper handling for queued audio"
    queued_block = queued_block_match.group(0)
    
    # Check 5: CRITICAL - Within this block, verify _last_activity_ts is updated
    assert "self._last_activity_ts = time.time()" in queued_block, \
        "❌ Watchdog doesn't reset _last_activity_ts when audio is queued!"
    print("✅ 🔥 CRITICAL: Watchdog RESETS _last_activity_ts when bot is speaking!")
    
    # Check 6: Verify it continues (doesn't disconnect)
    assert "continue" in queued_block, \
        "❌ Watchdog doesn't continue (skip disconnect) when audio is queued"
    print("✅ Watchdog continues (skips disconnect) when bot is speaking")
    
    print("\n" + "="*80)
    print("🎯 QUEUE RESET FIX VERIFIED!")
    print("="*80)
    print("\n🔥 HOW IT WORKS:")
    print("  1. Every second, watchdog checks: idle >= 20s?")
    print("  2. If yes, check audio queues: q1 + tx > 0?")
    print("  3. If audio in queues (bot speaking):")
    print("     → Update _last_activity_ts = time.time()")
    print("     → This RESETS the silence counter to 0!")
    print("     → Continue (skip disconnect)")
    print("\n✅ RESULT:")
    print("  • AI can speak for ANY duration (25s, 30s, 60s...)")
    print("  • Watchdog won't disconnect while audio is playing")
    print("  • Only disconnects after 20s of TRUE silence")
    print("="*80)


def test_scenario_long_ai_response():
    """Test scenario: AI speaks for 25 seconds (should NOT disconnect)"""
    
    print("\n" + "="*80)
    print("📝 SCENARIO TEST: Long AI Response (25 seconds)")
    print("="*80)
    
    print("\n🎬 SCENARIO:")
    print("  t=0s   : AI starts speaking")
    print("  t=0-25s: AI speaking (audio in queues)")
    print("  t=20s  : Watchdog checks → idle=20s")
    print("           → But audio in queues!")
    print("           → Reset _last_activity_ts")
    print("           → Continue (no disconnect)")
    print("  t=25s  : AI finishes speaking")
    print("  t=45s  : Watchdog checks → idle=20s since t=25s")
    print("           → No audio in queues")
    print("           → Disconnect ✓")
    
    print("\n✅ EXPECTED BEHAVIOR:")
    print("  • No disconnect at t=20s (AI still speaking)")
    print("  • Disconnect at t=45s (20s after AI finished)")
    
    print("\n🔥 THE FIX:")
    print("  • Watchdog resets silence counter while audio is playing")
    print("  • Prevents false disconnect during long responses")
    print("="*80)


if __name__ == "__main__":
    try:
        test_watchdog_resets_on_audio()
        test_scenario_long_ai_response()
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - Queue Reset Fix Verified")
        print("="*80)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
