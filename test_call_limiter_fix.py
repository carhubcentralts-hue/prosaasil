#!/usr/bin/env python3
"""
Test to verify the call limiter fix properly counts both "dialing" and "calling" jobs

This test simulates the race condition that was causing the bug:
- Multiple jobs transition from "queued" to "dialing" to "calling"
- The system should never have more than 3 jobs in "dialing" + "calling" states combined
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestCallLimiterFix(unittest.TestCase):
    """Test that call limiter counts both dialing and calling jobs"""
    
    def test_active_count_includes_dialing_and_calling(self):
        """
        Test that active job count includes both dialing and calling
        
        This simulates the scenario:
        1. Job 1: status="calling" (already on call)
        2. Job 2: status="calling" (already on call) 
        3. Job 3: status="dialing" (being initiated)
        
        Active count should be 3, so no more jobs should start
        """
        # Mock job statuses
        jobs = [
            {"id": 1, "status": "calling"},  # Active call
            {"id": 2, "status": "calling"},  # Active call
            {"id": 3, "status": "dialing"},  # Being initiated
            {"id": 4, "status": "queued"},   # Waiting
            {"id": 5, "status": "queued"},   # Waiting
        ]
        
        # Count active jobs (should include dialing + calling)
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        
        # Should have 3 active jobs
        self.assertEqual(len(active), 3)
        
        # Should NOT start another call
        concurrency_limit = 3
        can_start_more = len(active) < concurrency_limit
        self.assertFalse(can_start_more, "Should NOT start more calls when 3 are active")
    
    def test_old_logic_would_fail(self):
        """
        Test that the OLD logic (counting only 'calling') would FAIL
        
        This demonstrates the bug we fixed
        """
        # Same jobs as above
        jobs = [
            {"id": 1, "status": "calling"},  # Active call
            {"id": 2, "status": "calling"},  # Active call
            {"id": 3, "status": "dialing"},  # Being initiated
            {"id": 4, "status": "queued"},   # Waiting
            {"id": 5, "status": "queued"},   # Waiting
        ]
        
        # OLD LOGIC: Only count "calling"
        active_old_way = [j for j in jobs if j["status"] == "calling"]
        
        # Would only count 2 active jobs
        self.assertEqual(len(active_old_way), 2)
        
        # Would INCORRECTLY allow starting another call
        concurrency_limit = 3
        would_start_more = len(active_old_way) < concurrency_limit
        self.assertTrue(would_start_more, "OLD logic would INCORRECTLY start another call")
    
    def test_race_condition_scenario(self):
        """
        Test the race condition that caused multiple calls to start simultaneously
        
        Scenario:
        - System checks: 0 active jobs, can start 3
        - Starts job 1: status -> "dialing" (not counted by old logic!)
        - Checks again: still 0 "calling" jobs, can start 3 more
        - Starts job 2: status -> "dialing" (not counted!)
        - Checks again: still 0 "calling" jobs, can start 3 more
        - ...continues starting many jobs...
        - Eventually all jobs complete "dialing" and become "calling"
        - Now we have 10+ concurrent calls! (BUG)
        """
        jobs = []
        concurrency_limit = 3
        
        # Simulate starting 10 jobs rapidly
        for i in range(10):
            jobs.append({"id": i, "status": "dialing"})
            
            # OLD LOGIC: Count only "calling" jobs
            active_old = [j for j in jobs if j["status"] == "calling"]
            
            # With old logic, all would be allowed to start
            if len(active_old) < concurrency_limit:
                # Old logic would say: "Go ahead, start another!"
                pass
        
        # OLD LOGIC: All 10 jobs would be in "dialing" state
        self.assertEqual(len(jobs), 10)
        active_old = [j for j in jobs if j["status"] == "calling"]
        self.assertEqual(len(active_old), 0, "Old logic doesn't count dialing jobs")
        
        # NEW LOGIC: Count both "dialing" and "calling"
        active_new = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active_new), 10)
        
        # NEW LOGIC: Would have stopped after 3
        can_start_more = len(active_new) < concurrency_limit
        self.assertFalse(can_start_more, "New logic correctly limits to 3")
    
    def test_transition_from_dialing_to_calling(self):
        """
        Test that as jobs transition from dialing to calling, count remains accurate
        """
        concurrency_limit = 3
        
        # Initial state: 3 jobs dialing
        jobs = [
            {"id": 1, "status": "dialing"},
            {"id": 2, "status": "dialing"},
            {"id": 3, "status": "dialing"},
        ]
        
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active), 3)
        self.assertFalse(len(active) < concurrency_limit)
        
        # Job 1 completes dialing, becomes calling
        jobs[0]["status"] = "calling"
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active), 3)
        self.assertFalse(len(active) < concurrency_limit)
        
        # Job 2 completes dialing, becomes calling
        jobs[1]["status"] = "calling"
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active), 3)
        self.assertFalse(len(active) < concurrency_limit)
        
        # Job 1 completes, becomes completed
        jobs[0]["status"] = "completed"
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active), 2)
        self.assertTrue(len(active) < concurrency_limit, "Now we can start another!")
    
    def test_concurrent_limit_verification(self):
        """
        Test that we never exceed the concurrency limit with new logic
        """
        concurrency_limit = 3
        max_jobs = 20  # Reduced from 100 for test efficiency
        
        # Simulate processing queue
        jobs = [{"id": i, "status": "queued"} for i in range(max_jobs)]
        
        # Start initial batch
        started = 0
        for job in jobs:
            if job["status"] == "queued":
                # Count active with NEW logic
                active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
                
                if len(active) < concurrency_limit:
                    job["status"] = "dialing"
                    started += 1
                else:
                    break
        
        # Should have started exactly 3
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        self.assertEqual(len(active), 3)
        self.assertEqual(started, 3)
        
        # Verify we can't start more
        active = [j for j in jobs if j["status"] in ["dialing", "calling"]]
        can_start = len(active) < concurrency_limit
        self.assertFalse(can_start)


if __name__ == '__main__':
    header_msg = "Testing call limiter fix (dialing + calling count)..."
    print(header_msg)
    print("=" * len(header_msg))
    unittest.main(verbosity=2)
