"""
Test suite for playout truth barge-in fix

Tests that is_ai_speaking_now() correctly detects when AI audio
is actually PLAYING to the customer, not just when we received it.
"""
import time


class MockMediaHandler:
    """Mock version of MediaStreamHandler with playout truth tracking"""
    
    def __init__(self):
        # Playout truth tracking
        self.ai_playout_until_ts = 0.0
        self.ai_generation_id = 0
        self.current_generation_id = 0
        self._frame_pacing_ms = 20
        self._playout_grace_ms = 250
        
        # Legacy tracking (for fallback)
        self.last_ai_audio_ts = None
        
        # Mock queue
        class MockQueue:
            def __init__(self):
                self._size = 0
            
            def qsize(self):
                return self._size
            
            def set_size(self, size):
                self._size = size
        
        self.tx_q = MockQueue()
    
    def is_ai_speaking_now(self) -> bool:
        """
        🔥 PLAYOUT TRUTH FIX: Determine if AI is TRULY speaking to the customer RIGHT NOW
        
        Primary truth sources (checked in order):
        1. ai_playout_until_ts - Calculated timestamp when playout will complete
        2. tx_queue size > 0 with small grace (150-250ms for network buffer)
        3. Fallback to legacy last_ai_audio_ts for backwards compatibility
        
        Returns:
            True if AI audio is actively PLAYING to customer, False otherwise
        """
        now = time.time()
        
        # Rule 1: PLAYOUT TRUTH - Primary source of truth
        if hasattr(self, 'ai_playout_until_ts') and self.ai_playout_until_ts > 0:
            if now < self.ai_playout_until_ts:
                return True
        
        # Rule 2: TX QUEUE SIZE - Audio waiting to be sent to Twilio (with grace period)
        tx_q_size = self.tx_q.qsize() if hasattr(self, 'tx_q') else 0
        if tx_q_size > 0:
            grace_ms = getattr(self, '_playout_grace_ms', 250)
            if self.last_ai_audio_ts:
                elapsed_ms = (now - self.last_ai_audio_ts) * 1000
                if elapsed_ms < grace_ms:
                    return True
        
        # Rule 3: FALLBACK - Legacy last_ai_audio_ts check
        if self.last_ai_audio_ts:
            elapsed_ms = (now - self.last_ai_audio_ts) * 1000
            if elapsed_ms < 400:
                return True
        
        # Rule 4: No active playout detected
        return False


class TestPlayoutTruthBargeIn:
    """Test playout truth detection for barge-in"""
    
    def test_playout_truth_active(self):
        """Test that AI is considered speaking when playout timestamp is in future"""
        handler = MockMediaHandler()
        
        # Set playout timestamp to 2 seconds in future
        handler.ai_playout_until_ts = time.time() + 2.0
        
        # Should detect AI is speaking
        assert handler.is_ai_speaking_now() == True, "Should detect AI speaking when playout_until_ts is in future"
        print("✅ Test passed: playout_truth_active")
    
    def test_playout_truth_expired(self):
        """Test that AI is NOT speaking when playout timestamp has passed"""
        handler = MockMediaHandler()
        
        # Set playout timestamp to 2 seconds in past
        handler.ai_playout_until_ts = time.time() - 2.0
        
        # Should NOT detect AI speaking
        assert handler.is_ai_speaking_now() == False, "Should NOT detect AI speaking when playout_until_ts is in past"
        print("✅ Test passed: playout_truth_expired")
    
    def test_tx_queue_with_recent_audio(self):
        """Test that AI is speaking when tx_queue has frames and audio was recent"""
        handler = MockMediaHandler()
        
        # Set recent audio timestamp
        handler.last_ai_audio_ts = time.time() - 0.1  # 100ms ago
        
        # Set tx_queue to have frames
        handler.tx_q.set_size(50)
        
        # Should detect AI speaking (queue has frames, audio was recent)
        assert handler.is_ai_speaking_now() == True, "Should detect AI speaking with tx_queue frames and recent audio"
        print("✅ Test passed: tx_queue_with_recent_audio")
    
    def test_tx_queue_with_old_audio(self):
        """Test that AI is NOT speaking when tx_queue has frames but audio is old"""
        handler = MockMediaHandler()
        
        # Set old audio timestamp (beyond grace period)
        handler.last_ai_audio_ts = time.time() - 1.0  # 1000ms ago (> 250ms grace)
        
        # Set tx_queue to have frames
        handler.tx_q.set_size(50)
        
        # Should NOT detect AI speaking (audio too old, even with queue frames)
        assert handler.is_ai_speaking_now() == False, "Should NOT detect AI speaking with old audio despite tx_queue frames"
        print("✅ Test passed: tx_queue_with_old_audio")
    
    def test_legacy_fallback_recent(self):
        """Test legacy fallback works for recent audio (< 400ms)"""
        handler = MockMediaHandler()
        
        # Clear playout timestamp
        handler.ai_playout_until_ts = 0.0
        
        # Set recent audio (within 400ms window)
        handler.last_ai_audio_ts = time.time() - 0.2  # 200ms ago
        
        # Should detect AI speaking via legacy fallback
        assert handler.is_ai_speaking_now() == True, "Should detect AI speaking via legacy fallback (< 400ms)"
        print("✅ Test passed: legacy_fallback_recent")
    
    def test_legacy_fallback_old(self):
        """Test legacy fallback returns False for old audio (> 400ms)"""
        handler = MockMediaHandler()
        
        # Clear playout timestamp
        handler.ai_playout_until_ts = 0.0
        
        # Set old audio (beyond 400ms window)
        handler.last_ai_audio_ts = time.time() - 0.5  # 500ms ago
        
        # Should NOT detect AI speaking
        assert handler.is_ai_speaking_now() == False, "Should NOT detect AI speaking via legacy fallback (> 400ms)"
        print("✅ Test passed: legacy_fallback_old")
    
    def test_playout_priority_over_legacy(self):
        """Test that playout truth takes priority over legacy timestamp"""
        handler = MockMediaHandler()
        
        # Set old legacy audio (would return False via fallback)
        handler.last_ai_audio_ts = time.time() - 1.0  # 1000ms ago
        
        # But set playout timestamp in future
        handler.ai_playout_until_ts = time.time() + 2.0
        
        # Should detect AI speaking via playout truth (takes priority)
        assert handler.is_ai_speaking_now() == True, "Playout truth should take priority over legacy timestamp"
        print("✅ Test passed: playout_priority_over_legacy")
    
    def test_no_audio_state(self):
        """Test that AI is NOT speaking when no audio state exists"""
        handler = MockMediaHandler()
        
        # No playout timestamp, no legacy audio, empty queue
        handler.ai_playout_until_ts = 0.0
        handler.last_ai_audio_ts = None
        handler.tx_q.set_size(0)
        
        # Should NOT detect AI speaking
        assert handler.is_ai_speaking_now() == False, "Should NOT detect AI speaking with no audio state"
        print("✅ Test passed: no_audio_state")


def run_all_tests():
    """Run all playout truth tests"""
    print("\n" + "="*70)
    print("Running Playout Truth Barge-In Tests")
    print("="*70 + "\n")
    
    test_suite = TestPlayoutTruthBargeIn()
    
    tests = [
        test_suite.test_playout_truth_active,
        test_suite.test_playout_truth_expired,
        test_suite.test_tx_queue_with_recent_audio,
        test_suite.test_tx_queue_with_old_audio,
        test_suite.test_legacy_fallback_recent,
        test_suite.test_legacy_fallback_old,
        test_suite.test_playout_priority_over_legacy,
        test_suite.test_no_audio_state,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ Test failed: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ Test error: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
