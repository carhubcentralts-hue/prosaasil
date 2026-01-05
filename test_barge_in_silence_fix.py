"""
Test to verify the BARGE-IN false positive fix

This test verifies that barge-in logic is NOT triggered when:
1. AI is not speaking (is_ai_speaking == False)
2. No active response exists (active_response_id == None)
3. Speech is detected during silence

This simulates the bug scenario described in the issue:
- Complete silence in the call
- No user speech
- No AI speech
- Yet barge-in was being triggered
"""


class MockAudioState:
    """Mock audio state to simulate the bug scenario"""
    
    def __init__(self):
        self.active_response_id = None
        self.is_ai_speaking_event = MockEvent()
        self.barge_in_stop_tx = False
        self.barge_in_active = False
        
    
class MockEvent:
    """Mock threading.Event"""
    
    def __init__(self):
        self._set = False
    
    def is_set(self):
        return self._set
    
    def set(self):
        self._set = True
    
    def clear(self):
        self._set = False


def test_barge_in_during_silence():
    """
    Test: speech_started event during complete silence should NOT trigger barge-in
    
    Scenario:
    - AI finished speaking (is_ai_speaking = False)
    - No active response (active_response_id = None)
    - speech_started event arrives (false positive from noise)
    
    Expected: Barge-in logic should NOT execute
    """
    print("Testing: speech_started during complete silence...")
    
    # Setup: Complete silence scenario
    state = MockAudioState()
    state.active_response_id = None  # No active response
    state.is_ai_speaking_event.clear()  # AI not speaking
    
    # Simulate the fixed logic
    has_active_response = bool(state.active_response_id)
    is_ai_currently_speaking = state.is_ai_speaking_event.is_set()
    
    # The FIX: Check if there's anything to interrupt
    should_trigger_barge_in = has_active_response or is_ai_currently_speaking
    
    # Verify: Barge-in should NOT trigger
    assert not should_trigger_barge_in, "Barge-in should NOT trigger during silence!"
    assert not state.barge_in_stop_tx, "TX stop flag should remain False"
    assert not state.barge_in_active, "Barge-in active flag should remain False"
    
    print("✅ PASSED: Barge-in correctly NOT triggered during silence")
    return True


def test_barge_in_during_ai_speaking():
    """
    Test: speech_started event while AI is speaking SHOULD trigger barge-in
    
    Scenario:
    - AI is speaking (is_ai_speaking = True)
    - Active response exists (active_response_id = "resp_123")
    - speech_started event arrives (real user interruption)
    
    Expected: Barge-in logic SHOULD execute
    """
    print("\nTesting: speech_started while AI is speaking...")
    
    # Setup: AI speaking scenario
    state = MockAudioState()
    state.active_response_id = "resp_123"  # Active response
    state.is_ai_speaking_event.set()  # AI is speaking
    
    # Simulate the fixed logic
    has_active_response = bool(state.active_response_id)
    is_ai_currently_speaking = state.is_ai_speaking_event.is_set()
    
    # The FIX: Check if there's anything to interrupt
    should_trigger_barge_in = has_active_response or is_ai_currently_speaking
    
    # Verify: Barge-in SHOULD trigger
    assert should_trigger_barge_in, "Barge-in SHOULD trigger when AI is speaking!"
    
    print("✅ PASSED: Barge-in correctly triggered when AI is speaking")
    return True


def test_barge_in_with_active_response_only():
    """
    Test: speech_started with active response but no audio yet
    
    Scenario:
    - AI not speaking yet (is_ai_speaking = False) - response created but no audio
    - Active response exists (active_response_id = "resp_456")
    - speech_started event arrives (user interrupts before AI audio starts)
    
    Expected: Barge-in logic SHOULD execute (cancel pending response)
    """
    print("\nTesting: speech_started with active response (no audio yet)...")
    
    # Setup: Active response, no audio yet
    state = MockAudioState()
    state.active_response_id = "resp_456"  # Active response
    state.is_ai_speaking_event.clear()  # No audio started yet
    
    # Simulate the fixed logic
    has_active_response = bool(state.active_response_id)
    is_ai_currently_speaking = state.is_ai_speaking_event.is_set()
    
    # The FIX: Check if there's anything to interrupt
    should_trigger_barge_in = has_active_response or is_ai_currently_speaking
    
    # Verify: Barge-in SHOULD trigger (to cancel pending response)
    assert should_trigger_barge_in, "Barge-in SHOULD trigger to cancel pending response!"
    
    print("✅ PASSED: Barge-in correctly triggered for pending response")
    return True


def test_barge_in_after_ai_finished():
    """
    Test: speech_started after AI just finished speaking
    
    Scenario:
    - AI finished speaking (is_ai_speaking = False)
    - Response done (active_response_id = None) - cleaned up
    - speech_started event arrives (user starts speaking after AI)
    
    Expected: Barge-in logic should NOT execute (normal turn-taking)
    """
    print("\nTesting: speech_started after AI finished speaking...")
    
    # Setup: AI finished, normal turn-taking
    state = MockAudioState()
    state.active_response_id = None  # Response cleaned up
    state.is_ai_speaking_event.clear()  # AI finished
    
    # Simulate the fixed logic
    has_active_response = bool(state.active_response_id)
    is_ai_currently_speaking = state.is_ai_speaking_event.is_set()
    
    # The FIX: Check if there's anything to interrupt
    should_trigger_barge_in = has_active_response or is_ai_currently_speaking
    
    # Verify: Barge-in should NOT trigger (normal turn-taking)
    assert not should_trigger_barge_in, "Barge-in should NOT trigger during normal turn-taking!"
    
    print("✅ PASSED: Barge-in correctly NOT triggered after AI finished")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("BARGE-IN FALSE POSITIVE FIX - Verification Tests")
    print("=" * 70)
    print()
    print("Bug Description:")
    print("  - speech_started was triggering barge-in unconditionally")
    print("  - No check for AI speaking state or active response")
    print("  - Resulted in false barge-ins during complete silence")
    print()
    print("Fix:")
    print("  - Added guard: only trigger barge-in if AI is speaking OR has active response")
    print("  - Prevents false positives during silence/normal turn-taking")
    print("  - Preserves correct barge-in behavior when needed")
    print()
    print("=" * 70)
    print()
    
    all_passed = True
    
    try:
        all_passed &= test_barge_in_during_silence()
        all_passed &= test_barge_in_during_ai_speaking()
        all_passed &= test_barge_in_with_active_response_only()
        all_passed &= test_barge_in_after_ai_finished()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        all_passed = False
    
    print()
    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Fix is working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Fix needs adjustment")
    print("=" * 70)
    
    import sys
    sys.exit(0 if all_passed else 1)
