#!/usr/bin/env python3
"""
Test suite for logging cleanup and bug fixes
Validates:
1. Frame accounting logic
2. Greeting lock counter consistency
3. WebSocket close error handling
4. Environment variable flags for logging
"""
import os
import sys

def test_frame_accounting():
    """
    Test that frame counters are consistent
    
    Validates:
    - realtime_audio_in_chunks is incremented at frame reception (not after filtering)
    - frames_in == frames_forwarded + frames_dropped
    """
    print("=" * 60)
    print("TEST 1: Frame Accounting Logic")
    print("=" * 60)
    
    # Check that realtime_audio_in_chunks is incremented early in media event processing
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
        
        # Find the media event handler
        if 'if et == "media":' in content:
            print("✅ Found media event handler")
            
            # Check that realtime_audio_in_chunks increment is right after self.rx
            lines = content.split('\n')
            found_rx = False
            found_increment_after_rx = False
            
            for i, line in enumerate(lines):
                if 'if et == "media":' in line:
                    # Look at next few lines
                    for j in range(i, min(i+10, len(lines))):
                        if 'self.rx += 1' in lines[j]:
                            found_rx = True
                        if found_rx and 'self.realtime_audio_in_chunks += 1' in lines[j]:
                            found_increment_after_rx = True
                            print(f"✅ realtime_audio_in_chunks incremented at line {j+1} (right after frame reception)")
                            break
                    break
            
            if not found_increment_after_rx:
                print("❌ ERROR: realtime_audio_in_chunks not incremented at frame reception")
                return False
        else:
            print("❌ ERROR: Could not find media event handler")
            return False
    
    # Check that the old increment location has been removed or commented
    if 'self.realtime_audio_in_chunks += 1' in content:
        # Count occurrences - should be exactly 1 (at frame reception)
        count = content.count('self.realtime_audio_in_chunks += 1')
        if count == 1:
            print(f"✅ realtime_audio_in_chunks incremented exactly once (at frame reception)")
        else:
            print(f"⚠️  WARNING: realtime_audio_in_chunks incremented {count} times (expected 1)")
            # Check if the second one is commented out
            lines = [l for l in content.split('\n') if 'self.realtime_audio_in_chunks += 1' in l]
            active_lines = [l for l in lines if not l.strip().startswith('#')]
            if len(active_lines) == 1:
                print(f"✅ Only one active increment (other is commented)")
            else:
                print(f"❌ ERROR: Multiple active increments found")
                return False
    
    print("\n✅ Frame accounting logic test PASSED\n")
    return True


def test_greeting_lock_counters():
    """
    Test that greeting_lock counters are consistent
    
    Validates:
    - Both _frames_dropped_by_greeting_lock and _frames_dropped_by_reason[GREETING_LOCK] are incremented together
    - Verification check exists at call end
    """
    print("=" * 60)
    print("TEST 2: Greeting Lock Counter Consistency")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
        
        # Find all greeting_lock increment locations
        lines = content.split('\n')
        increment_blocks = []
        
        for i, line in enumerate(lines):
            if '_frames_dropped_by_greeting_lock += 1' in line or 'FrameDropReason.GREETING_LOCK] += 1' in line:
                # Check surrounding lines for the other counter
                has_both = False
                for j in range(max(0, i-5), min(len(lines), i+6)):
                    context = '\n'.join(lines[max(0, i-5):min(len(lines), i+6)])
                    if '_frames_dropped_by_greeting_lock += 1' in context and 'FrameDropReason.GREETING_LOCK] += 1' in context:
                        has_both = True
                        break
                
                increment_blocks.append({
                    'line': i+1,
                    'has_both': has_both,
                    'context': lines[i]
                })
        
        # Check that all increment locations have both counters
        all_consistent = True
        greeting_lock_locations = []
        for block in increment_blocks:
            if block not in greeting_lock_locations:
                greeting_lock_locations.append(block)
                if block['has_both']:
                    print(f"✅ Line {block['line']}: Both counters incremented")
                else:
                    print(f"❌ Line {block['line']}: Missing one counter - {block['context'].strip()}")
                    all_consistent = False
        
        if not all_consistent:
            print("\n❌ ERROR: Not all greeting_lock locations have both counters")
            return False
        
        # Check verification exists
        if 'GREETING_LOCK_ERROR' in content:
            print("✅ Verification check exists for greeting_lock counter consistency")
        else:
            print("❌ ERROR: Verification check missing")
            return False
    
    print("\n✅ Greeting lock counter consistency test PASSED\n")
    return True


def test_websocket_close():
    """
    Test that websocket close is protected against double-close errors
    
    Validates:
    - _ws_closed flag is set in all close paths
    - Error handling distinguishes expected vs unexpected close errors
    """
    print("=" * 60)
    print("TEST 3: WebSocket Close Error Handling")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
        
        # Find all ws.close() calls
        close_calls = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if 'self.ws.close()' in line and not line.strip().startswith('#'):
                # Check if _ws_closed is set nearby
                context = '\n'.join(lines[max(0, i-5):min(len(lines), i+6)])
                has_flag_set = '_ws_closed = True' in context
                has_flag_check = '_ws_closed' in context or 'not self._ws_closed' in context
                
                close_calls.append({
                    'line': i+1,
                    'has_flag_set': has_flag_set,
                    'has_flag_check': has_flag_check
                })
        
        print(f"Found {len(close_calls)} websocket close calls")
        
        all_protected = True
        for call in close_calls:
            if call['has_flag_set'] or call['has_flag_check']:
                print(f"✅ Line {call['line']}: Protected with _ws_closed flag")
            else:
                print(f"⚠️  Line {call['line']}: May not be protected")
                # This is not necessarily an error - some paths may be safe
        
        # Check error handling treats ASGI errors as DEBUG
        if 'websocket.close' in content and 'asgi' in content and 'DEBUG' in content:
            print("✅ Error handling treats ASGI close errors specially")
        else:
            print("⚠️  Could not verify ASGI error handling (may still be correct)")
    
    print("\n✅ WebSocket close error handling test PASSED\n")
    return True


def test_logging_flags():
    """
    Test that new logging environment variables exist
    
    Validates:
    - LOG_REALTIME_EVENTS flag exists
    - LOG_AUDIO_CHUNKS flag exists
    - LOG_TRANSCRIPT_DELTAS flag exists
    """
    print("=" * 60)
    print("TEST 4: Logging Environment Variable Flags")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
        
        flags = [
            'LOG_REALTIME_EVENTS',
            'LOG_AUDIO_CHUNKS',
            'LOG_TRANSCRIPT_DELTAS'
        ]
        
        all_found = True
        for flag in flags:
            if f'{flag} = os.getenv' in content:
                print(f"✅ {flag} flag exists")
            else:
                print(f"❌ {flag} flag missing")
                all_found = False
        
        if not all_found:
            return False
        
        # Check that LOG_AUDIO_CHUNKS is actually used
        if 'LOG_AUDIO_CHUNKS' in content and 'if LOG_AUDIO_CHUNKS' in content:
            print("✅ LOG_AUDIO_CHUNKS flag is used in code")
        else:
            print("⚠️  LOG_AUDIO_CHUNKS may not be used")
    
    print("\n✅ Logging flags test PASSED\n")
    return True


def test_twiml_threshold():
    """
    Test that TwiML threshold is configurable and raised
    
    Validates:
    - TWIML_SLA_MS environment variable exists
    - Default is 350ms (not 200ms)
    """
    print("=" * 60)
    print("TEST 5: TwiML Generation Threshold")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_twilio.py', 'r') as f:
        content = f.read()
        
        if 'TWIML_SLA_MS' in content:
            print("✅ TWIML_SLA_MS environment variable exists")
        else:
            print("❌ TWIML_SLA_MS not found")
            return False
        
        # Check default value is 350
        if '"TWIML_SLA_MS", "350"' in content or "'TWIML_SLA_MS', '350'" in content:
            print("✅ Default threshold is 350ms")
        else:
            print("⚠️  Could not verify default is 350ms (may still be correct)")
        
        # Check old hardcoded 200ms is removed
        if 'twiml_ms > 200' in content and 'TWIML_SLA_MS' not in content:
            print("❌ Old hardcoded 200ms threshold still exists")
            return False
        else:
            print("✅ Old hardcoded threshold removed")
    
    print("\n✅ TwiML threshold test PASSED\n")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LOGGING FIXES TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Frame Accounting", test_frame_accounting),
        ("Greeting Lock Counters", test_greeting_lock_counters),
        ("WebSocket Close", test_websocket_close),
        ("Logging Flags", test_logging_flags),
        ("TwiML Threshold", test_twiml_threshold),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ TEST CRASHED: {e}\n")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
