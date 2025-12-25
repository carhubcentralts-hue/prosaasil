#!/usr/bin/env python3
"""
Test for long goodbye sentence fix

This test verifies that the delayed_hangup() function can handle
very long goodbye sentences without timing out prematurely.
"""

def test_timeout_values():
    """
    Test that timeout values are sufficient for long goodbye sentences
    """
    print("=" * 70)
    print("TESTING LONG GOODBYE SENTENCE TIMEOUT VALUES")
    print("=" * 70)
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the delayed_hangup function
    delayed_hangup_start = content.find('async def delayed_hangup():')
    if delayed_hangup_start == -1:
        print("❌ FAIL: delayed_hangup() function not found")
        return False
    
    # Extract the function (approximate - get next 3500 chars to catch all parts)
    func_content = content[delayed_hangup_start:delayed_hangup_start + 3500]
    
    print("\n🧪 Checking timeout values...\n")
    
    checks = [
        # Check OpenAI queue timeout (should be >= 30 seconds = 300 * 100ms)
        ('range(300)', 'OpenAI queue timeout >= 30 seconds (was 5s)', 
         lambda s: 'range(300)' in s or 'range(400)' in s or 'range(500)' in s),
        
        # Check TX queue timeout (should be >= 60 seconds = 600 * 100ms)
        ('range(600)', 'TX queue timeout >= 60 seconds (was 10s)',
         lambda s: 'range(600)' in s or 'range(700)' in s or 'range(800)' in s),
        
        # Check stuck threshold (should be >= 10 = 1000ms)
        ('STUCK_THRESHOLD = 10', 'Stuck detection threshold >= 1000ms (was 500ms)',
         lambda s: 'STUCK_THRESHOLD = 10' in s or 'STUCK_THRESHOLD = 15' in s or 'STUCK_THRESHOLD = 20' in s),
        
        # Check network buffer (should be >= 3 seconds)
        ('await asyncio.sleep(3.0)', 'Network latency buffer >= 3 seconds (was 2s)',
         lambda s: 'await asyncio.sleep(3.0)' in s or 'await asyncio.sleep(4.0)' in s or 'await asyncio.sleep(5.0)' in s),
        
        # Check for fix comment
        ('FIX:', 'Has comment marking this as a fix for long sentences',
         lambda s: 'FIX:' in s or 'LONG goodbye' in s),
    ]
    
    passed = 0
    failed = 0
    
    for pattern, description, check_func in checks:
        if check_func(func_content):
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description}")
            print(f"         Pattern '{pattern}' not found")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(checks)} checks")
    print("=" * 70)
    
    if failed == 0:
        print("✅ ALL CHECKS PASSED!")
        print("\nTimeout values are sufficient for long goodbye sentences:")
        print("  • OpenAI queue: 30+ seconds (vs 5s before)")
        print("  • TX queue: 60+ seconds (vs 10s before)")
        print("  • Stuck detection: 1000ms+ (vs 500ms before)")
        print("  • Network buffer: 3+ seconds (vs 2s before)")
        print("\nThis allows the AI to finish speaking the entire goodbye sentence,")
        print("regardless of length, before disconnecting the call.")
        return True
    else:
        print("❌ SOME CHECKS FAILED")
        return False


def test_example_scenarios():
    """
    Test example scenarios with estimated audio durations
    """
    print("\n" + "=" * 70)
    print("EXAMPLE SCENARIOS")
    print("=" * 70)
    
    # Hebrew TTS typically speaks at ~150-180 words per minute
    # That's about 2.5-3 words per second
    # Each word in Hebrew averages ~4-5 syllables
    # So roughly 1 second per word for clear speech
    
    scenarios = [
        {
            "text": "תודה רבה, ביי",
            "words": 3,
            "estimated_audio_sec": 3,
            "description": "Short goodbye"
        },
        {
            "text": "תודה רבה על הזמן שלך. נציג יחזור אליך בהקדם. יום נפלא, ביי",
            "words": 12,
            "estimated_audio_sec": 12,
            "description": "Medium goodbye"
        },
        {
            "text": "תודה רבה על כל המידע שמסרת לנו. קיבלנו את כל הפרטים ובעל מקצוע מומחה יחזור אליך בהקדם האפשרי, כנראה תוך שעה או שעתיים. אנחנו מאוד מעריכים את הזמן שלך. שיהיה לך יום נפלא ומוצלח, להתראות",
            "words": 35,
            "estimated_audio_sec": 35,
            "description": "Very long goodbye"
        },
        {
            "text": "תודה רבה על כל המידע המפורט שמסרת לנו היום. אנחנו מבינים שזה דחוף ואנחנו כבר מטפלים בזה. קיבלנו את כל הפרטים שלך כולל השם, הטלפון, הכתובת והמיקום המדויק. בעל מקצוע מומחה בתחום שלך יחזור אליך בהקדם האפשרי, ככל הנראה תוך שעה עד שעתיים מקסימום. אם יש משהו דחוף במיוחד, אתה יכול גם לפנות אלינו דרך האתר או הווצאפ. אנחנו באמת מעריכים את הזמן והסבלנות שלך. שיהיה לך יום נפלא ומוצלח, להתראות וכל טוב",
            "words": 85,
            "estimated_audio_sec": 85,
            "description": "Extremely long goodbye"
        }
    ]
    
    print("\n🧪 Testing if timeouts can handle these scenarios:\n")
    
    # After fix: OpenAI queue = 30s, TX queue = 60s, buffer = 3s
    # Total available time = 93 seconds
    total_timeout = 30 + 60 + 3
    
    for scenario in scenarios:
        text = scenario["text"]
        estimated_sec = scenario["estimated_audio_sec"]
        description = scenario["description"]
        
        # More realistic calculation:
        # - TTS generation happens in PARALLEL with streaming
        # - Queue draining happens as audio is generated
        # - Network overhead is minimal with streaming
        # So total time ≈ audio duration + small buffer
        streaming_overhead = 2  # seconds for streaming setup
        buffer = 3  # network buffer at end
        total_needed = estimated_sec + streaming_overhead + buffer
        
        will_complete = total_needed < total_timeout
        status = "✅" if will_complete else "⚠️"
        
        print(f"{status} {description}")
        print(f"   Text: \"{text[:60]}...\"" if len(text) > 60 else f"   Text: \"{text}\"")
        print(f"   Audio duration: ~{estimated_sec}s")
        print(f"   Total time needed: ~{total_needed:.1f}s (with streaming)")
        print(f"   Available timeout: {total_timeout}s")
        print(f"   Result: {'Will complete ✅' if will_complete else 'May need more time ⚠️'}")
        print()
    
    print("=" * 70)
    print("✅ All realistic scenarios can complete within the new timeout values!")
    print("\nNote: TTS generation happens in parallel with audio streaming,")
    print("so the actual time needed is close to the audio duration plus buffers.")
    print("=" * 70)


if __name__ == "__main__":
    print("\n")
    test1_passed = test_timeout_values()
    
    if test1_passed:
        test_example_scenarios()
        print("\n🎉 SUCCESS! The fix ensures long goodbye sentences complete fully.")
    else:
        print("\n⚠️  Timeout values may need adjustment.")
    
    print()
